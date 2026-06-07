"""Yearl-e scoring.

Score a click by finding which region polygon contains it within the year's
region set. Award `region.score` directly (0-100). The reveal also shows the
top-ranked region for that year.
"""
from __future__ import annotations

from shapely.geometry import Point

from .regions import load_region_set, load_year, region_set_of


# Beyond this distance (degrees) from EVERY land polygon, a click is open ocean
# / Antarctica — not a near-miss off some coast. ~9° ≈ 1000 km at the equator.
# Inside it we still snap to the nearest region (clicking just off a coast counts
# for that coast); past it we return a miss instead of awarding a random region.
OCEAN_MISS_DEG = 9.0


def region_for_point(set_name: str, lat: float, lon: float) -> str | None:
    """Region_id containing the point, or the nearest land region if the click is
    close enough to count. Returns None for an open-ocean / Antarctica miss
    (farther than OCEAN_MISS_DEG from every region)."""
    regions = load_region_set(set_name)
    pt = Point(lon, lat)
    # Real polygons can overlap (e.g. disputed territory); prefer smaller area
    # (more specific) on tie.
    candidates = []
    nearest, nearest_d = None, float("inf")
    for rid, r in regions.items():
        sh = r["_shape"]
        if sh.contains(pt):
            candidates.append((sh.area, rid))
        else:
            d = sh.distance(pt)  # planar degrees; cheap and fine at this scale
            if d < nearest_d:
                nearest, nearest_d = rid, d
    if candidates:
        candidates.sort()
        return candidates[0][1]
    return nearest if nearest_d <= OCEAN_MISS_DEG else None


def _empty_guess(region_id: str | None, region_name: str, summary: str) -> dict:
    """A scored-guess payload with no factor data (unresolved point / no cell)."""
    return {
        "region_id": region_id,
        "region_name": region_name,
        "score": 0,
        "summary": summary,
        "factors": {},
        "factor_sources": {},
        "sources": [],
        "ruler": None,
        "data_quality": 0,
        "sparse_data": True,
    }


def score_guess(year: int, lat: float, lon: float) -> dict:
    """Resolve a globe click to a region in the year's snapshot and return its
    score payload. Always returns a dict (falls back to empty data on a miss)."""
    y = load_year(year)
    if not y:
        raise ValueError(f"no data for year {year}")
    set_name = region_set_of(y)
    regions = load_region_set(set_name)
    rid = region_for_point(set_name, lat, lon)
    if rid is None:
        # Open ocean / Antarctica — too far from any land region to count.
        return _empty_guess(None, "Open ocean",
                            "You picked open water — no region here that year. "
                            "Click on land to make a guess.")
    region_name = regions[rid]["name"] if rid in regions else "(no region)"
    cell = y["regions"].get(rid)
    if not cell:
        return _empty_guess(rid, region_name, "No data for this region this year.")
    return {
        "region_id": rid,
        "region_name": region_name,
        "score": cell["score"],
        "summary": cell["summary"],
        "factors": cell.get("factors", {}),
        "factor_sources": cell.get("factor_sources", {}),
        "sources": cell.get("sources", []),
        "ruler": cell.get("ruler"),
        "data_quality": cell.get("data_quality", 0),
        "sparse_data": cell.get("sparse_data", True),
    }
