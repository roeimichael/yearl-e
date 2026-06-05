# yearl-e data pipeline

All scoring is sourced from real public datasets — no LLM gap-fill. Regions are
real historical polities from Cliopatria (Seshat), sampled at 25-year snapshots
across an era; each game-year is scored against its nearest snapshot.

## One-time setup (downloads + slices)

```
python scripts/fetch_sources.py        # all raw datasets -> data/raw/
python scripts/fetch_natural_earth.py  # ne_110m_admin_0.geojson (ISO3 shapes)
python scripts/prep_vdem.py            # slice 200 MB V-Dem core -> 5-col CSV
```

## Build region snapshots (one per era)

```
python scripts/build_cliopatria_era.py early_modern --snapshots 1500,1525,...,1800,1815
```

Writes `data/region_sets/early_modern_{year}.json`. Each region carries
`member_iso3` (modern countries it overlaps), so ISO3-keyed scoring works.

## Score years

```
python scripts/build_year.py 1700       # fetch_year + fetch_year_wiki + rank_year
python scripts/build_years.py 1500 1815 # bulk, skips already-built years
```

`rank_year.py` resolves the nearest snapshot (see `ERA_SNAPSHOTS`) and writes
`data/year_scores/{year}.json`.

## Scoring model (`rank_year.py` + `factors.py` + `vdem_lookup.py`)

Per region, per year, five 0-100 factors:

| Factor | Source |
|---|---|
| safety | Brecke Conflict Catalog, matched by polity name + macro-region |
| economy | Maddison Project GDP/capita of the best-covered member country |
| governance | V-Dem electoral-democracy index (1789+), else neutral 50 |
| health | OWID life expectancy (country → continent → baseline) + conflict/economy nudge |
| religious_tolerance | modeled era baseline − Leeson-Russ witch-trial penalty |

Overall `score` = `0.30*safety + 0.20*governance + 0.20*economy + 0.15*health
+ 0.15*religious_tolerance`, then normalized per year (worst region → 1,
best → 100). `raw_score` keeps the pre-normalization composite.

## Score schema (per region, per year)

```json
{
  "score": 1-100,
  "raw_score": 0-100,
  "summary": "cited explanation",
  "factors": { "safety": 0-100, "health": 0-100, "economy": 0-100,
               "governance": 0-100, "religious_tolerance": 0-100 },
  "factor_sources": { "safety": "brecke", "...": "..." },
  "sources": [ { "label": "...", "url": "https://..." } ],
  "ruler": null,
  "wikidata": "Q..."
}
```
