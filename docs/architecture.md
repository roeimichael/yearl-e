# yearl-e architecture

This is the deep technical companion to the [README](../README.md). It covers the
data storage layers, the snapshot model, the scoring model and its normalization,
the on-disk JSON schemas, and how an HTTP request flows end to end.

The mental model in one line: **an offline pipeline bakes two committed JSON
directories; an in-memory FastAPI app reads them and grades clicks.** There is no
database.

---

## 1. The four data storage layers

`data/` holds four layers, each a different stage of the pipeline. Only the last
two ship to production.

```
data/
  raw/                ← layer 1: downloaded source datasets + per-year extracts (gitignored)
  region_groupings/   ← layer 2: legacy hand-curated region groupings (pre-Cliopatria)
  region_sets/        ← layer 3: Cliopatria boundary snapshots         (committed, shipped)
  year_scores/        ← layer 4: per-year scored output                (committed, shipped)
```

### Layer 1 — `data/raw/` (build inputs, gitignored)

The large, regenerable inputs. Two kinds:

- **Source datasets** downloaded by `scripts/fetch_sources.py`: `cliopatria.geojson`
  (~157 MB unzipped), `ne_110m_admin_0.geojson` (Natural Earth), `maddison.xlsx`,
  `brecke.xlsx`, `vdem_v15_core.csv`, `owid_life_exp.csv`, `witch_trials.csv`, and
  the `historical_basemaps/` bundle.
- **Per-year extracts** written by `scripts/fetch_year.py` / `fetch_year_wiki.py`:
  `{year}_extract.json` (the Maddison GDP + Brecke conflict slice needed to score
  one year) and `{year}_wiki.json` (the Wikipedia era summary).

This whole layer is **gitignored** — it is reproducible from the fetch scripts and
far too large to version. (Two files are deliberately force-tracked as fixtures:
`ne_110m_admin_0.geojson`, which the build needs and is small, and a legacy
`1719_extract.json` from the original single-year pipeline.)

### Layer 2 — `data/region_groupings/` (legacy)

The original hand-curated region model from before Cliopatria: `early_modern.json`
with manual `manual_{year}` blocks (governance/tolerance/ruler notes and sources,
hand-written per region). The current pipeline does **not** read this; it is kept
for reference and history. New work should not extend it.

### Layer 3 — `data/region_sets/` (committed, shipped)

The Cliopatria **boundary snapshots** built by `scripts/build_cliopatria_era.py`.
One file per snapshot year: `early_modern_{year}.json` for
`{1500, 1525, … 1800, 1815}` (14 snapshots). Each holds the polities active that
snapshot year, as polygons, each tagged with the modern countries it overlaps
(`member_iso3`). There is also a legacy non-snapshot `early_modern.json` (the
default fallback name); the shipped game uses the dated snapshots.

The backend loads these via `backend/regions.py::load_region_set` (cached with
`lru_cache`), keeping both a GeoJSON dict (for serving) and a parsed shapely
geometry (for point-in-polygon).

### Layer 4 — `data/year_scores/` (committed, shipped)

The scored output, one file per game-year: `{year:04d}.json` (negative years use a
`-NNNN` form). Each declares which `region_set` snapshot it used and carries the
full per-region scores. Produced by `scripts/rank_year.py`. **The set of files
here defines which years can be rolled** — `available_years()` simply globs this
directory. Currently 1500–1815 are present.

The `Dockerfile` copies only layers 3 and 4 into the image:

```dockerfile
COPY data/region_sets/  data/region_sets/
COPY data/year_scores/  data/year_scores/
```

---

## 2. The snapshot model

Borders move constantly, but maintaining a distinct region map for all ~300 years
would be wasteful and noisy. Instead each **era** has a coarse grid of boundary
**snapshots**, and every game-year binds to its nearest snapshot.

Eras are declared in `scripts/rank_year.py`:

```python
ERA_SNAPSHOTS = {
    "early_modern": (1500, 1815, list(range(1500, 1801, 25)) + [1815]),
}
```

The tuple is `(lo, hi, [snapshot_years])`. `snapshot_for(year)` finds the era whose
`[lo, hi]` contains the year, then snaps to the nearest snapshot:

```
year 1738  ──snapshot_for──▶  "early_modern_1725"   (1725 is nearer than 1750)
year 1700  ──snapshot_for──▶  "early_modern_1700"   (exact)
year 1808  ──snapshot_for──▶  "early_modern_1815"   (1815 is nearer than 1800)
```

So ~13 game-years share each boundary snapshot. The snapshot name is stored in the
year file's `region_set` field, and the backend uses that to load matching
geometry — guaranteeing the globe overlay matches the puzzle. To add an era, build
its snapshots, add a row to `ERA_SNAPSHOTS`, and re-score the years (see README →
"Add a new era").

---

## 3. The scoring model

`scripts/rank_year.py::score_region` computes five factors per region, all 0–100.
Regions are real polities; they reach the country-keyed datasets through
`member_iso3` (the modern ISO-3 countries each polity overlaps, ordered
biggest-overlap-first so "dominant territory" lookups are sensible).

| Factor | Logic | Provider | `factor_source` values |
|---|---|---|---|
| **safety** | 85 baseline. Conflicts matched by polity-name keywords get the full penalty (−12, or −25 if >50k fatalities); conflicts matched only by Brecke macro-region code get a light penalty (−4 / −8) and are capped at 6, so a big multi-region polity isn't dragged down by every regional war. Floor 5. | `compute_safety` + Brecke | `brecke` |
| **economy** | Best member country's Maddison GDP/capita, percentile-ranked within the year's covered countries → `25 + pct·65`. No coverage → 50. | `compute_economy` + Maddison | `maddison` / `neutral` |
| **governance** | V-Dem polyarchy of the best member (×100). Coverage begins **1789**; before that → neutral 50. | `vdem_lookup.governance` | `vdem` / `neutral` |
| **health** | Tier 1: dominant member's real life expectancy within ~25 yr. Tier 2: its continental OWID aggregate (floored at 1770). Map `le 22→8, 50→92`; then −6 per conflict hit (cap −18) and a small ±7 economy nudge. Fallback baseline le=28. | `factors.health` + OWID | `lifeexp` / `modeled` |
| **religious_tolerance** | A modeled per-macro-region early-modern `TOLERANCE_BASELINE`, minus a real penalty `min(30, round(√peak·2))` from peak witch-trial intensity among member countries that decade. | `factors.tolerance` + Leeson-Russ | `witch-trials` / `modeled` |

`factor_source` is reported honestly per factor so the UI can distinguish a real
measured value (`lifeexp`, `maddison`, `vdem`, `witch-trials`) from a fallback
(`neutral`, `modeled`).

### Composite + normalization

The raw composite is the fixed-weight mean:

```
raw = round(0.30·safety + 0.20·governance + 0.20·economy + 0.15·health + 0.15·tolerance)
```

Raw composites tend to cluster in a narrow band (many regions share neutral
fallbacks), so each year is **min-max normalized across its own regions**:

```
score = round(1 + 99·(raw − min) / (max − min))     # worst region → 1, best → 100
                                                     # all equal (spread 0) → 50
```

The original composite is preserved as `raw_score`; the normalized value is
`score` (what the game grades and ranks on). Normalization is **per-year**, so
scores are comparable *within* a year's puzzle but not across different years.

The backend does no scoring at request time — it only awards the precomputed
`region.score` for the clicked region (`backend/scoring.py`).

---

## 4. On-disk JSON schemas

### Region set — `data/region_sets/{set}.json`

```jsonc
{
  "regions": [
    {
      "id": "tsardom_of_russia",        // slug, unique within the set
      "name": "Tsardom of Russia",      // display name
      "centroid": [62.98, 96.45],       // [lat, lon] — nearest-centroid fallback
      "member_iso3": ["RUS"],           // modern countries it overlaps (dominant first)
      "wikidata": "Q186096",            // Wikidata QID (provenance)
      "seshat_id": "ru_romanov_dyn_1",  // Cliopatria/Seshat polity id
      "geometry": { "type": "Polygon", "coordinates": [ /* … */ ] },  // GeoJSON
      "min_zoom": 1.0                   // area-rank tier for label/render zoom
    }
    // … one per active polity in the snapshot year
  ]
}
```

On load, `regions.py` keys these by `id` and attaches a parsed shapely `_shape`
(stripped before serving to the client).

### Year file — `data/year_scores/{year:04d}.json`

```jsonc
{
  "year": 1700,
  "label": "1700 CE",
  "region_set": "early_modern_1700",    // which snapshot was scored (snapshot_for)
  "era_summary": "1700 (MDCC) was …",   // Wikipedia year summary (may be "")
  "regions": {
    "tsardom_of_russia": {
      "score": 1,                       // NORMALIZED 1–100 (what the game grades)
      "raw_score": 41,                  // pre-normalization composite
      "summary": "Active conflicts in 1700: …",   // generated prose
      "factors": {
        "safety": 32, "health": 27, "economy": 50,
        "governance": 50, "religious_tolerance": 48
      },
      "factor_sources": {               // provenance per factor
        "safety": "brecke", "health": "lifeexp", "economy": "neutral",
        "governance": "neutral", "religious_tolerance": "modeled"
      },
      "sources": [                      // cited links shown on reveal
        { "label": "Cliopatria (Seshat) …", "url": "https://…" },
        { "label": "Brecke Conflict Catalog 1400-2000", "url": "https://…" }
        // Maddison / V-Dem / OWID / witch-trials / Wikipedia added when used
      ],
      "ruler": null,
      "sparse_data": true,
      "wikidata": "Q186096"
    }
    // … keyed by region id; must match the region_set's ids
  }
}
```

`regions` is a **map keyed by region id** (the region set is a **list**); the ids
must line up so a clicked polygon resolves to its scored cell.

---

## 5. Request flow

```
                         Vercel (static frontend + /api/* rewrite)
 Browser ───────────────────────────┬───────────────────────────────▶ Railway (FastAPI)
   MapLibre globe                    │
                                     │
 1) GET /api/today                   │   _roll_year(date): sha256(date)-seeded PRNG
    {date, day_number, year,         │   picks from available_years() (year_scores/*.json).
     label, era_summary, region_set} │   FORCE_YEAR overrides. load_year() → cached.
                                     │
 2) GET /api/regions  (no ?set)      │   resolves today's year → its region_set, returns
    {set, regions:[…GeoJSON…]}       │   region_set_for_serving() (shapely stripped).
                                     │   GZip middleware compresses (~162KB → ~30KB).
                                     │
 3) POST /api/today/guess            │   score_guess(year, lat, lon):
    {year, lat, lon}                 │     region_for_point() — shapely contains();
        ▼                            │       ties broken by smaller area; falls back to
    {guess:{region_id, score,        │       nearest centroid (haversine) if no polygon hits.
      factors, factor_sources,       │     awards the region's precomputed score;
      sources, ruler},               │     ranked(year) gives rank + the year's #1 region.
     rank, total_regions, top, …}    │
                                     │
 4) GET /api/year/{y}/regions        │   full ranked dataset for post-reveal explore mode.
                                     │
 5) GET /api/healthz {ok:true}       │   Railway liveness probe.
```

Key properties:

- **Determinism** — the daily year is a pure function of the date, so all players
  share one puzzle. `EPOCH = 2026-05-22` is day 1; the clock uses Asia/Jerusalem.
- **No request-time scoring** — guessing is a point-in-polygon lookup plus a table
  read. All the heavy work happened offline in `rank_year.py`.
- **In-memory caching** — region sets via `lru_cache`, year files via a module
  dict; the process is stateless beyond these read caches.
- **CORS** — controlled by `ALLOWED_ORIGINS`; in production the Vercel rewrite keeps
  calls same-origin so CORS rarely fires.

---

## See also

- [README](../README.md) — pitch, run, deploy, attribution.
- [`scripts/rank_year.py`](../scripts/rank_year.py) — the scoring source of truth.
- [`scripts/factors.py`](../scripts/factors.py) — health + tolerance providers and
  the ISO3 → Brecke macro-region table.
- [docs/data-sources.md](data-sources.md), [docs/data-sources-pre1500.md](data-sources-pre1500.md)
  — research catalogs for extending coverage.
