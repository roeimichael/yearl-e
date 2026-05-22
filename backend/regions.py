"""Load region SETS (era-keyed) + per-year score files.

Year files declare their region_set ("early_modern", etc.). Each set is a
data/region_sets/{set}.json built by scripts/build_region_polygons.py from
Natural Earth shapes + manual groupings.

Polygons are stored as shapely geometries (for fast point-in-region) plus
GeoJSON dicts (for serving to the frontend)."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"


@lru_cache(maxsize=8)
def load_region_set(name: str) -> dict[str, dict]:
    """Return {region_id: {id, name, centroid, geometry (geojson), shape (shapely)}}."""
    p = DATA / "region_sets" / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
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
    out = []
    for p in (DATA / "year_scores").glob("*.json"):
        try:
            out.append(int(p.stem))
        except ValueError:
            pass
    return sorted(out)


def load_year(year: int) -> dict | None:
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
