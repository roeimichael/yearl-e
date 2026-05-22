<div align="center">

# 🌍 yearl-e

**A daily history game.** Each day, one random year between 1000 BCE and today.
Click the globe where you'd want to live in that year — score based on actual
living conditions (peace, health, economy, governance, religious tolerance), with cited sources.

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![MapLibre](https://img.shields.io/badge/MapLibre%20GL-5.0-396CB1?logo=maplibre&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

</div>

---

## How it works

- **One year per day**, same for everyone. Resets at 00:00 Israel time.
- Click anywhere on the 3D globe. The region containing your click is graded.
- Score = that region's "living conditions" score for that year (0–100).
- Reveal shows: your pick's summary + factors + sources, AND the #1 best region.
- After reveal, **explore mode** lets you click any region to see its data.

### Scoring factors (per region, per year)

| Factor | What it captures |
|---|---|
| `safety` | War, raids, banditry, civil unrest |
| `health` | Disease, sanitation, life expectancy |
| `economy` | GDP/capita proxy, food security, trade |
| `governance` | Rule of law, ruler quality, stability |
| `religious_tolerance` | Persecution risk if outside dominant faith |

Overall `score` is a weighted mean. No physical-distance penalty — what matters is *what kind of place* you picked.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + uvicorn on **Railway** (Nixpacks) |
| Frontend | Static HTML/JS/CSS on **Vercel** (`/api/*` proxied to Railway) |
| Map engine | [MapLibre GL JS](https://maplibre.org/) v5 (native globe projection) |
| Basemap | None — solid dark backdrop, vector regions on top (historical parchment vibe) |
| Region polygons | Hand-curated bbox stubs for v1; will swap to Natural Earth admin-0 |
| Year data | JSON per year under `data/year_scores/`. Hybrid: dataset anchors + LLM gap-fill |

## Data sources (live in v0.2)

| Source | Used for | Status |
|---|---|---|
| [Maddison Project 2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) | economy (GDP/cap, normalized within year) | **wired** — XLSX, 4.7 MB, 169 countries, 1 CE → 2022 |
| [Brecke Conflict Catalog](https://brecke.inta.gatech.edu/research/conflict/) | safety (active conflicts in year, fatality-weighted) | **wired** — XLSX, 301 KB, 886 conflicts 1400–2000 |
| Wikipedia per-region URLs | governance + religious tolerance + ruler (manual) | **wired** — cited inline |
| [Seshat Global History Databank](http://seshatdatabank.info) | governance/economy NGA per century | planned |
| CLIO-INFRA | life expectancy, height, literacy | planned |
| LLM gap-fill (Claude) | (year, region) cells without anchors | planned |

See [`scripts/rank_year.py`](scripts/rank_year.py) for the scoring formula.

## Local dev

```bash
git clone https://github.com/roeimichael/yearl-e
cd yearl-e
python -m venv .venv
.venv/Scripts/activate                  # Windows
pip install -r backend/requirements.txt
$env:SERVE_FRONTEND=1                   # PowerShell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000** → click *Spin the globe*.

## Repo layout

```
backend/        FastAPI — routes, scoring, region + year loader
frontend/       index.html, app.js, style.css (vanilla, no build step)
scripts/        data pipeline (anchors + LLM gap-fill, stubbed)
data/           regions.json (~18 sample), year_scores/{year}.json
nixpacks.toml   Railway build config
railway.json    Railway deploy config
vercel.json     Vercel static deploy + /api/* rewrite to Railway
```

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/today` | `{date, day_number, year, label, era_summary}` |
| `POST` | `/api/today/guess` | `{guess, rank, total_regions, top, era_summary, label}` |
| `GET` | `/api/year/{y}/regions` | full ranked dataset for the year |
| `GET` | `/api/regions` | region polygons for the globe layer |
| `GET` | `/api/healthz` | liveness |

## Status

**v0.2 — one fully-pipelined year.** 1719 CE × 18 regions, scored from real datasets:

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_sources.py           # ~5 MB raw, cached
python scripts/fetch_year.py 1719         # → data/raw/1719_extract.json
python scripts/rank_year.py 1719          # → data/year_scores/1719.json
FORCE_YEAR=1719 uvicorn backend.main:app  # play it
```

Top 5 for 1719 (Kangxi China #1, Tokugawa Japan #3, Tulip-era Istanbul #4, Hanoverian England #5).
Bottom: Sweden (Great Northern War devastation), fragmented Italy, collapsing Safavid Persia.

See `scripts/rank_year.py` for the exact formula. Manual context (governance + religious tolerance + ruler) is inline + sourced via Wikipedia links per region.

Two stubbed sample years also ship: `1 CE` and `1453 CE` (hand-written, no data pipeline).

## License

MIT — see [LICENSE](LICENSE).

Sibling project: [israel-e.com](https://israel-e.com).
