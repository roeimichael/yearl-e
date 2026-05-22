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

## Data sources (planned)

| Source | Use |
|---|---|
| Seshat Global History Databank | governance, economy, safety per NGA per century |
| Maddison Project | GDP/capita 1 CE → present |
| UCDP/PRIO + Brecke catalogs | conflict-driven safety scores |
| CLIO-INFRA | life expectancy, height, literacy |
| LLM gap-fill (Claude) | for (year, region) cells not covered, with mandatory citations |

See [`scripts/README.md`](scripts/README.md) for the pipeline plan.

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

**v1 scaffold.** Two hand-written years (`1 CE`, `1453 CE`) × 18 regions as proof of schema. The dataset is the actual hard work — see `scripts/README.md`.

## License

MIT — see [LICENSE](LICENSE).

Sibling project: [israel-e.com](https://israel-e.com).
