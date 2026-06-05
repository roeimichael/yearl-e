<div align="center">

# 🌍 yearl-e

**A daily history puzzle.** Each day rolls one random year from the early modern
world (currently **1500–1815**). Click the 3D globe where you'd want to live that
year — your guess is scored on the *real* living conditions of that region, from
historical datasets, with cited sources.

**▶ Play: <https://yearl-e.vercel.app>**

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![MapLibre](https://img.shields.io/badge/MapLibre%20GL-5.0-396CB1?logo=maplibre&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

</div>

---

## Screenshot

> _Placeholder — add `docs/screenshot.png` and it renders here._

![yearl-e gameplay screenshot](docs/screenshot.png)

---

## What it is

- **One year per day, same for everyone.** The year is rolled deterministically
  from the date, so every player gets the same puzzle. Resets at **00:00 Israel
  time**.
- You **click anywhere on the 3D globe**. The historical polity (region) whose
  polygon contains your click is graded for that year.
- Your **score** is that region's living-conditions score for the year (0–100).
- The **reveal** shows your pick's summary, its five factor scores, and its
  sources — plus the #1 best region to have lived in that year.
- After the reveal, **explore mode** lets you click any region on the globe to
  read its data.

Regions are not arbitrary grid cells: they are **real historical polities**
(empires, kingdoms, republics) drawn from the Cliopatria / Seshat dataset, so the
map literally reshapes as the centuries pass.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | **FastAPI** + uvicorn, in-memory (no DB, no auth). Deployed on **Railway** via `Dockerfile`. |
| Frontend | Vanilla **HTML / CSS / JS** (no build step). Deployed on **Vercel**, which proxies `/api/*` to Railway. |
| Map engine | [MapLibre GL JS](https://maplibre.org/) v5 — native globe projection. |
| Geometry | [shapely](https://shapely.readthedocs.io/) for point-in-polygon hit testing. |
| Data prep | Python scripts (`scripts/`) that fetch raw datasets and bake committed JSON. |

---

## Architecture overview

There are two distinct flows: an **offline data pipeline** (run by hand to build
the committed JSON) and the **online request flow** (what serves players).

### Data pipeline (offline)

```
 raw public datasets                 build + score scripts                 committed JSON (ships)
 ───────────────────                 ─────────────────────                 ──────────────────────
 data/raw/  (gitignored)
   cliopatria.geojson  ─┐
   ne_110m_admin_0      ─┼─▶ build_cliopatria_era.py ─▶ data/region_sets/early_modern_{year}.json
   (Natural Earth)      ─┘     (polities × Natural Earth          (14 snapshots: 1500…1800, 1815)
                               spatial overlap → member_iso3)
   maddison.xlsx        ─┐
   brecke.xlsx          ─┤
   vdem_v15_core.csv    ─┼─▶ fetch_year.py ─▶ data/raw/{year}_extract.json ─┐
   owid_life_exp.csv    ─┤    fetch_year_wiki.py ─▶ data/raw/{year}_wiki.json
   witch_trials.csv     ─┘                                                  │
                                                                           ▼
                              rank_year.py {year}  ─▶ data/year_scores/{year:04d}.json
                              (snapshot_for(year) picks the nearest
                               region_set; scores 5 factors per region;
                               normalizes overall 1…100 within the year)
```

Only `data/region_sets/` and `data/year_scores/` are committed and shipped to
production — the `Dockerfile` copies exactly those two directories. Everything in
`data/raw/` is large and regenerable, so it is gitignored.

### Request flow (online)

```
 Browser ──▶ Vercel (static frontend) ──/api/*──▶ Railway (FastAPI)
   │                                                  │
   │  GET /api/today        (roll year for date)      │ reads data/year_scores/{year}.json
   │  GET /api/regions      (globe polygons)          │ reads data/region_sets/{set}.json
   │  POST /api/today/guess (lat/lon → region+score)  │ shapely point-in-polygon
   ▼                                                  ▼
 MapLibre globe                              in-memory caches (lru_cache + dict)
```

The daily year is chosen by seeding a PRNG with `sha256(date)` and picking from
the years that have a `data/year_scores/*.json` file — deterministic, so the
whole world sees the same puzzle. (`FORCE_YEAR` overrides it for local demos.)

For the deeper version of this — the four storage layers, the snapshot model, the
scoring math, and the JSON schemas — see **[docs/architecture.md](docs/architecture.md)**.

---

## The 5 scoring factors

Each region gets five 0–100 factor scores. The overall score is the weighted mean
below, then **normalized per year** so the year's worst region maps to 1 and the
best to 100 (keeps rankings legible when raw composites cluster).

```
overall = 0.30·safety + 0.20·governance + 0.20·economy + 0.15·health + 0.15·tolerance
```

| Factor | Weight | How it's computed | Source |
|---|---|---|---|
| **Safety** | 0.30 | 85 baseline minus penalties for active conflicts. Polity-name keyword matches are penalized heavily (precise); Brecke macro-region matches lightly (coarse, capped). | [Brecke Conflict Catalog](https://brecke.inta.gatech.edu/research/conflict/) |
| **Governance** | 0.20 | V-Dem polyarchy (electoral democracy index) of the best-covered member country. Coverage starts **1789**; earlier years fall back to a neutral 50. | [V-Dem v15](https://www.v-dem.net/data/the-v-dem-dataset/) |
| **Economy** | 0.20 | GDP/capita of the best-covered member country, percentile-ranked within that year's coverage. No coverage → neutral 50. | [Maddison Project 2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) |
| **Health** | 0.15 | Life expectancy of the dominant member country (within ~25 yr), else its continental aggregate; mapped to 0–100, then nudged by conflict (penalty) and economy (buffer). | [Our World in Data life expectancy](https://ourworldindata.org/life-expectancy) |
| **Religious tolerance** | 0.15 | A modeled per-macro-region early-modern baseline, minus a real persecution penalty from recorded witch-trial intensity by (country, decade). | [Leeson & Russ witch-trials](https://github.com/JakeRuss/witch-trials) |

Regions are joined to these country-keyed datasets through `member_iso3` — the
list of modern countries each polity spatially overlaps (computed from
[Natural Earth](https://www.naturalearthdata.com/) admin-0 shapes).

---

## Run it locally (Windows PowerShell)

```powershell
git clone https://github.com/roeimichael/yearl-e
cd yearl-e

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# Serve the frontend from FastAPI and pin a known year for the demo
$env:SERVE_FRONTEND = "1"
$env:FORCE_YEAR = "1700"
python -m uvicorn backend.main:app --port 8799
```

Then open **<http://127.0.0.1:8799/>**.

- `SERVE_FRONTEND=1` mounts `frontend/` at `/` and `/static` (off by default, since
  prod serves the frontend from Vercel).
- `FORCE_YEAR=1700` pins today's roll to a specific year. Omit it to get the real
  deterministic daily roll.
- The committed `data/region_sets/` + `data/year_scores/` are enough to play; you
  only need the data-prep steps below to add new years/eras.

---

## Add a new year

Years that already have a `data/year_scores/{year}.json` file are eligible to be
rolled. To add one (it must fall inside an era's snapshot range, currently
1500–1815):

```powershell
# one-time: download the raw datasets into data/raw/ (cached, ~hundreds of MB)
pip install -r scripts\requirements.txt
python scripts\fetch_sources.py

# per year: build the raw extract + (optional) Wikipedia summary, then score it
python scripts\fetch_year.py 1740          # -> data/raw/1740_extract.json
python scripts\fetch_year_wiki.py 1740     # -> data/raw/1740_wiki.json (optional)
python scripts\rank_year.py 1740           # -> data/year_scores/1740.json

# play it
$env:SERVE_FRONTEND = "1"; $env:FORCE_YEAR = "1740"
python -m uvicorn backend.main:app --port 8799
```

`rank_year.py` calls `snapshot_for(year)` to bind the year to its nearest
Cliopatria snapshot, scores every region in that snapshot, and writes the year
file. Commit the resulting `data/year_scores/{year}.json` to ship it.

## Add a new era

An "era" is a contiguous year range backed by its own set of Cliopatria boundary
snapshots. To add one (e.g. a medieval era):

1. **Build the snapshots** from Cliopatria + Natural Earth. Pick snapshot years
   (every ~25 yr is the current convention) and a prefix:

   ```powershell
   python scripts\build_cliopatria_era.py medieval --snapshots 1000,1025,1050,1075,1100
   # -> data/region_sets/medieval_1000.json, _1025.json, ...
   ```

2. **Register the era** in `scripts/rank_year.py` by adding it to `ERA_SNAPSHOTS`:

   ```python
   ERA_SNAPSHOTS = {
       "early_modern": (1500, 1815, list(range(1500, 1801, 25)) + [1815]),
       "medieval":     (1000, 1100, [1000, 1025, 1050, 1075, 1100]),
   }
   ```

   The tuple is `(lo, hi, [snapshot_years])`; `snapshot_for(year)` snaps each
   game-year to the nearest snapshot in whichever era's range contains it.

3. **Score the years** in the new range with `rank_year.py` (as above) and commit
   the resulting `data/region_sets/` + `data/year_scores/` files.

See **[docs/architecture.md](docs/architecture.md)** for the snapshot model in
detail. (Research catalogs for extending into earlier periods live in
[docs/data-sources.md](docs/data-sources.md) and
[docs/data-sources-pre1500.md](docs/data-sources-pre1500.md).)

---

## Deployment

| Target | What | Config |
|---|---|---|
| **Railway** (backend) | Builds the `Dockerfile` (python:3.11-slim + libgeos for shapely), copies `backend/`, `data/region_sets/`, `data/year_scores/`, runs uvicorn on `$PORT`. Health check at `/api/healthz`. | `Dockerfile`, `railway.json` |
| **Vercel** (frontend) | Serves `frontend/` statically. Rewrites `/api/*` to the Railway backend and `/static/*` to the frontend root. `/api/*` responses are `no-store`. | `vercel.json` |

The frontend never calls Railway directly — Vercel's rewrite proxy keeps it
same-origin. Set `ALLOWED_ORIGINS` on the backend for CORS in production.

```
Browser ──▶ vercel.app (static + /api/* rewrite) ──▶ *.up.railway.app (FastAPI)
```

---

## Data sources & attribution

yearl-e is built on public historical datasets. Please respect each source's
license; Cliopatria is **CC-BY 4.0** and requires attribution.

| Source | Used for | License / notes |
|---|---|---|
| [Cliopatria (Seshat Global History Databank)](https://github.com/Seshat-Global-History-Databank/cliopatria) | Region boundaries — year-keyed historical polities, 3400 BCE–2024 CE | **CC-BY 4.0** |
| [Maddison Project Database 2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) | Economy (GDP/capita) | CC-BY 4.0 |
| [Brecke Conflict Catalog](https://brecke.inta.gatech.edu/research/conflict/) | Safety (conflicts 1400–2000) | Academic use |
| [V-Dem v15](https://www.v-dem.net/data/the-v-dem-dataset/) | Governance (polyarchy, 1789+) | Free for research |
| [Our World in Data — life expectancy](https://ourworldindata.org/life-expectancy) | Health (Riley; Zijdeman; UN) | CC-BY |
| [Leeson & Russ — Witch Trials](https://github.com/JakeRuss/witch-trials) | Religious tolerance (persecution penalty) | Economic Journal 2018 |
| [Natural Earth](https://www.naturalearthdata.com/) | Mapping polities → modern countries (`member_iso3`) | Public domain |
| [Wikipedia](https://en.wikipedia.org/) | Per-year era summaries | CC-BY-SA |

A fuller research catalog of candidate datasets (integrated and planned) lives in
[docs/data-sources.md](docs/data-sources.md) and
[docs/data-sources-pre1500.md](docs/data-sources-pre1500.md).

---

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/today` | `{date, day_number, year, label, era_summary, region_set}` |
| `POST` | `/api/today/guess` | `{guess, rank, total_regions, top, era_summary, label}` |
| `GET` | `/api/year/{y}/regions` | full ranked dataset for the year (explore mode) |
| `GET` | `/api/regions?set=` | region polygons (GeoJSON) for the globe layer |
| `GET` | `/api/healthz` | liveness probe |

---

## Repo layout

```
backend/        FastAPI app — main.py (routes), regions.py (loaders),
                scoring.py (point-in-polygon + factor lookup)
frontend/       index.html, app.js, style.css (vanilla, no build step)
scripts/        data pipeline — fetch_sources, build_cliopatria_era,
                fetch_year, rank_year, factors, vdem_lookup, …
data/
  raw/            (gitignored) downloaded datasets + per-year extracts
  region_groupings/  legacy hand-curated groupings (pre-Cliopatria)
  region_sets/    committed Cliopatria snapshots (early_modern_{year}.json)
  year_scores/    committed per-year scored output ({year:04d}.json)
docs/           architecture.md + data-source research catalogs
Dockerfile      Railway backend image
railway.json    Railway deploy config
vercel.json     Vercel static deploy + /api/* rewrite proxy
```

---

## License

MIT — see [LICENSE](LICENSE).

Sibling project: [israel-e.com](https://israel-e.com).
