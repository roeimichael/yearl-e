"""Load region SETS (era snapshots) + per-year score files.

Each per-year score file declares the snapshot region-set it was scored against
(e.g. ``"early_modern_1700"``). Snapshots are ``data/region_sets/{set}.json``,
built by ``scripts/build_cliopatria_era.py`` from Cliopatria (Seshat) polities
plus Natural Earth shapes for ISO3 membership.

Each region stores both a shapely geometry (for fast point-in-region tests) and
the original GeoJSON dict (for serving to the frontend)."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

# Fallback snapshot for the rare case a request must resolve a region set but no
# year context is available (e.g. /api/regions before any year has rolled).
# Every scored year file declares its own snapshot, so this is only a safety net.
DEFAULT_REGION_SET = "early_modern_1700"


def region_set_of(year_payload: dict) -> str:
    """Snapshot name a year was scored against, falling back to a real snapshot.

    Year files always carry ``region_set``; the fallback only guards malformed or
    legacy payloads and points at an existing snapshot (never a deleted set)."""
    return year_payload.get("region_set") or DEFAULT_REGION_SET


@lru_cache(maxsize=8)
def load_region_set(name: str) -> dict[str, dict]:
    """Load a snapshot keyed by region id.

    Each value carries ``id``, ``name``, ``centroid``, ``member_iso3``,
    ``geometry`` (GeoJSON) and ``_shape`` (a cached shapely geometry for
    point-in-region tests). Raises ``FileNotFoundError`` for an unknown set."""
    p = DATA / "region_sets" / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for r in raw["regions"]:
        out[r["id"]] = {
            "id": r["id"],
            "name": r["name"],
            "centroid": r["centroid"],
            "member_iso3": r.get("member_iso3", []),
            "geometry": r["geometry"],
            "_shape": shape(r["geometry"]),
        }
    return out


def region_set_for_serving(name: str) -> list[dict]:
    """Strip the heavy shapely object before sending to client."""
    rs = load_region_set(name)
    return [{k: v for k, v in r.items() if k != "_shape"} for r in rs.values()]


# Per-year cache: year_int -> full year payload (declares region_set, has regions).
_YEAR_CACHE: dict[int, dict] = {}


def _year_path(year: int) -> Path:
    if year < 0:
        return DATA / "year_scores" / f"-{abs(year):04d}.json"
    return DATA / "year_scores" / f"{year:04d}.json"


def available_years() -> list[int]:
    """Sorted list of years that have a score file on disk."""
    out: list[int] = []
    for p in (DATA / "year_scores").glob("*.json"):
        try:
            out.append(int(p.stem))
        except ValueError:
            pass
    return sorted(out)


def load_year(year: int) -> dict | None:
    """Return a year's full score payload (cached), or ``None`` if not scored."""
    if year in _YEAR_CACHE:
        return _YEAR_CACHE[year]
    p = _year_path(year)
    if not p.exists():
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    _YEAR_CACHE[year] = payload
    return payload


def ranked(year: int) -> list[tuple[str, dict]]:
    """Regions for the year, sorted desc by score."""
    y = load_year(year)
    if not y:
        return []
    items = list(y["regions"].items())
    items.sort(key=lambda kv: kv[1]["score"], reverse=True)
    return items
