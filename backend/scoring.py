"""Yearl-e scoring.

Score a click by finding which region polygon contains it within the year's
region set. Award `region.score` directly (0-100). The reveal also shows the
top-ranked region for that year.
"""
from __future__ import annotations
from math import asin, cos, radians, sin, sqrt

from shapely.geometry import Point

from .regions import load_region_set, load_year, region_set_of


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def region_for_point(set_name: str, lat: float, lon: float) -> str | None:
    """Return region_id containing this point, or nearest-centroid fallback."""
    regions = load_region_set(set_name)
    pt = Point(lon, lat)
    # Real polygons can overlap (e.g. disputed territory); prefer smaller area
    # (more specific) on tie.
    candidates = []
    for rid, r in regions.items():
        if r["_shape"].contains(pt):
            candidates.append((r["_shape"].area, rid))
    if candidates:
        candidates.sort()
        return candidates[0][1]
    # Fallback: nearest centroid by great-circle.
    best, best_d = None, float("inf")
    for rid, r in regions.items():
        clat, clon = r["centroid"]
        d = haversine_km(lat, lon, clat, clon)
        if d < best_d:
            best, best_d = rid, d
    return best


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
        # Should be unreachable given the centroid fallback, but defend anyway.
        return _empty_guess(None, "(unknown)", "Could not resolve a region for this point.")
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
