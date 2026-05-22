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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import regions as regions_mod
from .scoring import score_guess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("yearle")

app = FastAPI(title="yearl-e")

_origins_raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
_origins = ["*"] if not _origins_raw else [o.strip() for o in _origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

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
    Same date → same year for every player."""
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
def get_regions():
    """Region geometry for the globe overlay. Cached client-side."""
    return {"regions": list(regions_mod.REGIONS.values())}


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
    }


class GuessIn(BaseModel):
    year: int
    lat: float
    lon: float


@app.post("/api/today/guess")
def today_guess(body: GuessIn):
    y = regions_mod.load_year(body.year)
    if not y:
        raise HTTPException(400, f"unknown year {body.year}")
    pick = score_guess(body.year, body.lat, body.lon)
    ranking = regions_mod.ranked(body.year)
    top_id, top = ranking[0]
    rank_idx = next((i for i, (rid, _) in enumerate(ranking) if rid == pick["region_id"]), -1)
    return {
        "guess": pick,
        "rank": rank_idx + 1,
        "total_regions": len(ranking),
        "top": {
            "region_id": top_id,
            "region_name": regions_mod.REGIONS[top_id]["name"],
            "score": top["score"],
            "summary": top["summary"],
            "factors": top.get("factors", {}),
            "sources": top.get("sources", []),
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
