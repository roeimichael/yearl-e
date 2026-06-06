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
        # pre-guess hint: what this year weighted most (dynamic per-year weights)
        "emphasis": y.get("emphasis"),
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
    top_id, top = ranking[0]
    rank_idx = next((i for i, (rid, _) in enumerate(ranking) if rid == pick["region_id"]), -1)
    return {
        "guess": pick,
        "rank": rank_idx + 1,
        "total_regions": len(ranking),
        "top": {
            "region_id": top_id,
            "region_name": set_regions[top_id]["name"],
            "score": top["score"],
            "summary": top["summary"],
            "factors": top.get("factors", {}),
            "factor_sources": top.get("factor_sources", {}),
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
    {"factor": "Safety", "dataset": "Brecke Conflict Catalog 1400-2000", "coverage": "active wars/rebellions per region-year"},
    {"factor": "Economy", "dataset": "Maddison Project 2023 + modeled regional baseline", "coverage": "real GDP/cap where available (39%), else modeled macro-region baseline"},
    {"factor": "Governance", "dataset": "V-Dem v15 + State Antiquity Index", "coverage": "V-Dem 1789+; State-continuity proxy before (92% statehist)"},
    {"factor": "Health", "dataset": "Our World in Data — life expectancy", "coverage": "country (Tier 1) + continental aggregate (Tier 2, from 1770)"},
    {"factor": "Religious tolerance", "dataset": "Leeson-Russ Witch Trials + modeled regional baseline", "coverage": "real persecution penalty (Europe) over a modeled era baseline"},
    {"factor": "Borders", "dataset": "Cliopatria / Seshat (CC-BY 4.0)", "coverage": "year-keyed historical polities, 3400 BCE-2024 CE"},
]
_ARCHIVE_STORAGE = [
    {"path": "data/raw/", "what": "downloaded source datasets + per-year extracts", "ships": False},
    {"path": "data/region_sets/", "what": "the 14 Cliopatria time-snapshots (borders + member_iso3)", "ships": True},
    {"path": "data/year_scores/", "what": "scored year files (one per year)", "ships": True},
]


@lru_cache(maxsize=1)
def _quality_summary() -> dict:
    """Per-factor real-vs-modeled fill and the data_quality histogram across every
    scored cell. Scans all year files once (cached) for the /archive page."""
    from collections import Counter
    real = {"safety": "brecke", "health": "lifeexp", "economy": "maddison"}
    real_gov = {"vdem", "statehist"}
    factors_fill = {f: Counter() for f in
                    ["safety", "health", "economy", "governance", "religious_tolerance"]}
    dq = Counter()
    cells = 0
    for yr in regions_mod.available_years():
        y = regions_mod.load_year(yr)
        if not y:
            continue
        for c in y["regions"].values():
            cells += 1
            dq[c.get("data_quality", 0)] += 1
            for f, fill in factors_fill.items():
                fill[c.get("factor_sources", {}).get(f, "?")] += 1
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
        "era": "early modern (1500–1815)",
        "years": {"count": len(years), "min": min(years), "max": max(years)} if years else {},
        "snapshots": snaps,
        "sources": _ARCHIVE_SOURCES,
        "storage": _ARCHIVE_STORAGE,
        "quality": _quality_summary(),
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
