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
def get_regions(set_name: str = Query("early_modern", alias="set")):
    """Region geometry (real polygons, GeoJSON) for the globe overlay.
    Cached client-side. `?set=` selects which era's grouping."""
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
        "region_set": y.get("region_set", "early_modern"),
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
    set_name = y.get("region_set", "early_modern")
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
        },
        "era_summary": y["era_summary"],
        "label": y["label"],
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


# ─── static (local dev) ──────────────────────────────────────────────────────

if SERVE_FRONTEND and FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")
else:
    log.info("frontend mount disabled (SERVE_FRONTEND=%s)", SERVE_FRONTEND)
