# yearl-e data pipeline

Two-stage build:

1. **Anchor pass** — fetch hard data from public datasets, write per-(year, region) factor scores where coverage exists.
2. **LLM gap-fill** — for missing cells, generate factor scores + cited reasoning via Claude/GPT against the same schema. Sources must be real and linkable.

## Datasets to pull

| Source | What | Use for factor |
|---|---|---|
| Seshat Global History Databank | NGAs by century, governance/economy/war metrics | governance, economy, safety |
| Maddison Project | GDP/capita 1 CE → present | economy |
| UCDP / PRIO Battle Deaths | Conflicts since ~1400 | safety |
| CLIO-INFRA | Life expectancy, height, literacy | health |
| Brecke conflict catalog | Pre-1400 conflicts | safety |

## Scripts (planned)

- `fetch_seshat.py` — pull NGA + variable tables → `data/raw/seshat.json`
- `fetch_maddison.py` — GDP/capita series → `data/raw/maddison.csv`
- `fetch_conflicts.py` — UCDP + Brecke merged → `data/raw/conflicts.json`
- `build_anchors.py` — collapse raw datasets → `data/year_scores/anchors/{year}.json`
- `gap_fill_llm.py` — for each (year, region) without anchor, call LLM → write cited factor scores
- `merge_year_scores.py` — anchors override LLM → `data/year_scores/{year}.json`

## Score schema (per region, per year)

```json
{
  "score": 0-100,
  "summary": "1-2 sentence explanation",
  "factors": {
    "safety": 0-100,
    "health": 0-100,
    "economy": 0-100,
    "governance": 0-100,
    "religious_tolerance": 0-100
  },
  "sources": [
    { "label": "Human-readable citation", "url": "https://..." }
  ]
}
```

Overall `score` = weighted mean of factors. Weights tuned in `backend/scoring.py`.

## Status

Stubs only. v1 ships with hand-written `0001.json` + `1453.json` as proof of schema.
