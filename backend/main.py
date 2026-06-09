"""FastAPI app for yearl-e. v1: no DB, no auth, in-memory only.

Endpoints:
  GET  /api/today                 → today's rolled year + metadata
  POST /api/today/guess           → score a click on the globe
  GET  /api/year/{y}/regions      → all regions ranked (post-reveal explore)
  GET  /api/regions               → region geometry for the globe layer
  GET  /api/healthz               → liveness probe
"""
import hashlib
import logging
import os
import random
from functools import lru_cache
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import regions as regions_mod
from .scoring import score_guess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("yearle")

app = FastAPI(title="yearl-e")

_origins_raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
if _origins_raw:
    _origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
else:
    log.warning("ALLOWED_ORIGINS unset — defaulting to localhost only. Set in prod.")
    _origins = ["http://127.0.0.1:8000", "http://127.0.0.1:8765", "http://localhost:8000", "http://localhost:8765"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)
# Compress region_set payloads (162KB → ~30KB) and other large JSON.
app.add_middleware(GZipMiddleware, minimum_size=1024)

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend"
SERVE_FRONTEND = os.environ.get("SERVE_FRONTEND", "0") == "1"

IL_TZ = ZoneInfo("Asia/Jerusalem")
EPOCH = date(2026, 5, 22)  # day 1


def _today_iso() -> str:
    return datetime.now(IL_TZ).date().isoformat()


def _day_number(d_iso: str) -> int:
    return (date.fromisoformat(d_iso) - EPOCH).days + 1


def _roll_year(d_iso: str) -> int:
    """Deterministic year pick from available year_scores files.
    Same date → same year for every player.

    Override with FORCE_YEAR env var while the dataset is being built —
    so we can demo a specific year before all 500 are scored."""
    forced = os.environ.get("FORCE_YEAR", "").strip()
    if forced:
        return int(forced)
    years = regions_mod.available_years()
    if not years:
        raise HTTPException(500, "no year data on disk")
    seed = int(hashlib.sha256(d_iso.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    return rng.choice(years)


# ─── routes ──────────────────────────────────────────────────────────────────


@app.get("/api/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/regions")
def get_regions(set_name: str | None = Query(None, alias="set")):
    """Region geometry (real polygons, GeoJSON) for the globe overlay.
    Cached client-side. `?set=` selects a specific snapshot; with no `set` it
    resolves to TODAY's rolled year's snapshot so the globe matches the puzzle."""
    if not set_name:
        y = regions_mod.load_year(_roll_year(_today_iso()))
        set_name = regions_mod.region_set_of(y) if y else regions_mod.DEFAULT_REGION_SET
    try:
        return {"set": set_name, "regions": regions_mod.region_set_for_serving(set_name)}
    except FileNotFoundError:
        raise HTTPException(404, f"unknown region set: {set_name}")


@app.get("/api/today")
def today():
    d = _today_iso()
    year = _roll_year(d)
    y = regions_mod.load_year(year)
    if not y:
        raise HTTPException(500, f"missing year file for {year}")
    return {
        "date": d,
        "day_number": _day_number(d),
        "year": year,
        "label": y["label"],
        "era_summary": y["era_summary"],
        "region_set": regions_mod.region_set_of(y),
    }


class GuessIn(BaseModel):
    year: int = Field(..., ge=-1000, le=2100)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


@app.post("/api/today/guess")
def today_guess(body: GuessIn):
    y = regions_mod.load_year(body.year)
    if not y:
        raise HTTPException(400, f"unknown year {body.year}")
    set_name = regions_mod.region_set_of(y)
    set_regions = regions_mod.load_region_set(set_name)
    pick = score_guess(body.year, body.lat, body.lon)
    ranking = regions_mod.ranked(body.year)
    if not ranking:
        raise HTTPException(500, "year file has no scored regions")
    # Headline "best place that year": the highest-scoring region we actually have
    # data for — so a barely-documented region (scored on a single factor and
    # floated to the top by per-year normalization) never headlines. Prefer >=3 of
    # 5 real factors, but in thin eras (ancient years rarely reach 3) drop only to
    # the best data quality actually available that year, never to dq=1 when dq=2
    # exists. The player's rank below still uses the full, unfiltered ranking.
    _max_dq = max((c.get("data_quality", 0) for _, c in ranking), default=0)
    _floor = min(3, _max_dq)
    top_id, top = next(
        ((rid, c) for rid, c in ranking if c.get("data_quality", 0) >= _floor),
        ranking[0])
    # Open-ocean miss has no region_id, so it has no rank in the year's ranking.
    is_miss = pick.get("region_id") is None
    rank_idx = -1 if is_miss else next(
        (i for i, (rid, _) in enumerate(ranking) if rid == pick["region_id"]), -1)
    return {
        "guess": pick,
        "rank": None if is_miss else rank_idx + 1,
        "total_regions": len(ranking),
        "miss": is_miss,
        "top": {
            "region_id": top_id,
            "region_name": set_regions[top_id]["name"],
            "score": top["score"],
            "summary": top["summary"],
            "factors": top.get("factors", {}),
            "factor_sources": top.get("factor_sources", {}),
            "scored_factors": top.get("scored_factors", []),
            "sources": top.get("sources", []),
            "ruler": top.get("ruler"),
            "data_quality": top.get("data_quality", 0),
            "sparse_data": top.get("sparse_data", True),
        },
        "era_summary": y["era_summary"],
        "label": y["label"],
        # how this year's score was weighted (dynamic per-year weights)
        "emphasis": y.get("emphasis"),
        "weights": y.get("weights", {}),
    }


@app.get("/api/year/{year}/regions")
def year_regions(year: int):
    """Full ranked dataset for the year — for post-reveal explore mode."""
    y = regions_mod.load_year(year)
    if not y:
        raise HTTPException(404, "no data")
    return {
        "year": year,
        "label": y["label"],
        "era_summary": y["era_summary"],
        "regions": y["regions"],
    }


# Factor → dataset, for the archive page (kept in sync with scripts/rank_year + factors).
_ARCHIVE_SOURCES = [
    {"factor": "Safety", "dataset": "Brecke Conflict Catalog (to 1999) + UCDP/PRIO (2000+)", "coverage": "active wars/rebellions per region-year"},
    {"factor": "Economy", "dataset": "Maddison Project 2023 + modeled regional baseline", "coverage": "real GDP/cap where available (39%), else modeled macro-region baseline"},
    {"factor": "Governance", "dataset": "V-Dem v15 + State Antiquity Index", "coverage": "V-Dem 1789+; State-continuity proxy before (92% statehist)"},
    {"factor": "Health", "dataset": "Our World in Data — life expectancy", "coverage": "country (Tier 1) + continental aggregate (Tier 2, from 1770)"},
    {"factor": "Religious tolerance", "dataset": "V-Dem freedom-of-religion (1789+) + witch-trials + modeled baseline", "coverage": "real V-Dem religious freedom 1789+ (84% of modern cells); modeled baseline minus witch-trial penalty before"},
    {"factor": "Borders", "dataset": "Cliopatria / Seshat (CC-BY 4.0)", "coverage": "year-keyed historical polities, 3400 BCE-2024 CE"},
]
_ARCHIVE_STORAGE = [
    {"path": "data/raw/", "what": "downloaded source datasets + per-year extracts", "ships": False},
    {"path": "data/region_sets/", "what": "Cliopatria time-snapshots (borders + member_iso3)", "ships": True},
    {"path": "data/year_scores/", "what": "scored year files (one per year)", "ships": True},
]


@lru_cache(maxsize=1)
def _quality_summary() -> dict:
    """Per-factor real-vs-modeled fill, the data_quality histogram, AND a per-year
    grid (region count + average real-factor fraction + emphasis) across every
    scored cell. One scan of all year files, cached, for the /archive page."""
    from collections import Counter
    factors_fill = {f: Counter() for f in
                    ["safety", "health", "economy", "governance", "religious_tolerance"]}
    dq = Counter()
    cells = 0
    year_grid = []
    for yr in regions_mod.available_years():
        y = regions_mod.load_year(yr)
        if not y:
            continue
        yr_cells = y["regions"].values()
        dq_sum = 0
        for c in yr_cells:
            cells += 1
            d = c.get("data_quality", 0)
            dq[d] += 1
            dq_sum += d
            for f, fill in factors_fill.items():
                fill[c.get("factor_sources", {}).get(f, "?")] += 1
        n = len(y["regions"])
        year_grid.append({
            "year": yr,
            "regions": n,
            # mean real-factor fraction 0–1 (how much of this year rests on real data)
            "quality": round(dq_sum / n / 5, 3) if n else 0,
            "emphasis": y.get("emphasis"),
            "set": y.get("region_set"),
        })
    if not cells:
        return {}
    def pct(counter):
        return {k: round(100 * v / cells) for k, v in counter.most_common()}
    return {
        "cells": cells,
        "factor_fill": {f: pct(c) for f, c in factors_fill.items()},
        "data_quality_hist": {str(k): round(100 * v / cells) for k, v in sorted(dq.items())},
        "note": "factor_fill = % of cells per source; data_quality = how many of the 5 "
                "factors rest on real measured data (vs modeled/neutral fallback).",
        "year_grid": year_grid,
    }


@app.get("/api/archive")
def archive():
    """Inventory of everything the game ships: snapshots, regions, years, sources.
    Powers the /archive data-browser page."""
    import re
    from collections import Counter
    rs_dir = ROOT / "data" / "region_sets"
    snaps = []
    for p in sorted(rs_dir.glob("*.json")):
        m = re.search(r"_(-?\d+)\.json$", p.name)
        snap_year = int(m.group(1)) if m else None
        regions = regions_mod.load_region_set(p.stem)
        snaps.append({
            "set": p.stem,
            "snapshot_year": snap_year,
            "region_count": len(regions),
            "regions": sorted(r["name"] for r in regions.values()),
        })
    years = regions_mod.available_years()
    snap_years = [s["snapshot_year"] for s in snaps if s["snapshot_year"] is not None]
    usage = Counter(min(snap_years, key=lambda s: abs(s - y)) for y in years) if snap_years else Counter()
    for s in snaps:
        s["years_using"] = usage.get(s["snapshot_year"], 0)
    return {
        "title": "yearl-e data archive",
        "era": "early modern + modern (1500–2026)",
        "years": {"count": len(years), "min": min(years), "max": max(years)} if years else {},
        "snapshots": snaps,
        "sources": _ARCHIVE_SOURCES,
        "storage": _ARCHIVE_STORAGE,
        "quality": _quality_summary(),
    }


@app.get("/api/archive/year/{year}")
def archive_year(year: int):
    """Read-only 'play from archive' view of one year: every region with its name,
    score, the 5 factors + their sources, summary and citations, sorted best-first.
    Joins region names from the snapshot onto the scored cells."""
    y = regions_mod.load_year(year)
    if not y:
        raise HTTPException(404, f"no data for {year}")
    set_name = regions_mod.region_set_of(y)
    try:
        rs = regions_mod.load_region_set(set_name)
    except FileNotFoundError:
        rs = {}
    out = []
    for rid, cell in y["regions"].items():
        meta = rs.get(rid, {})
        out.append({
            "id": rid,
            "name": meta.get("name", rid),
            "member_iso3": meta.get("member_iso3", []),
            "score": cell.get("score"),
            "raw_score": cell.get("raw_score"),
            "factors": cell.get("factors", {}),
            "factor_sources": cell.get("factor_sources", {}),
            "scored_factors": cell.get("scored_factors", []),
            "summary": cell.get("summary", ""),
            "sources": cell.get("sources", []),
            "data_quality": cell.get("data_quality", 0),
            "sparse_data": cell.get("sparse_data", True),
            "ruler": cell.get("ruler"),
        })
    out.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return {
        "year": year,
        "label": y["label"],
        "region_set": set_name,
        "era_summary": y.get("era_summary", ""),
        "emphasis": y.get("emphasis"),
        "weights": y.get("weights", {}),
        "regions": out,
    }


# ─── static (local dev) ──────────────────────────────────────────────────────

if SERVE_FRONTEND and FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/archive")
    def archive_page():
        return FileResponse(FRONTEND / "archive.html")
else:
    log.info("frontend mount disabled (SERVE_FRONTEND=%s)", SERVE_FRONTEND)
