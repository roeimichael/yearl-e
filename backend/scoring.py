"""Yearl-e scoring.

Unlike israelle (where score = quadratic falloff on physical distance), yearl-e
scores the user's *guess region* by its actual living-conditions score that
year. Distance to the top region is irrelevant — what matters is "how good
was the place you picked, that year".

User clicks a lat/lng. We:
  1. Find which region polygon contains it (or nearest centroid if none).
  2. Look up that region's score for the year.
  3. Award `region.score` directly (0-100). The reveal also shows top region.
"""
from math import asin, cos, radians, sin, sqrt

from .regions import REGIONS, load_year


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting on a [lon, lat] ring. Good enough for our bbox-style polygons."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def region_for_point(lat: float, lon: float) -> str:
    """Region containing this point, or nearest centroid as fallback."""
    for rid, r in REGIONS.items():
        if _point_in_ring(lon, lat, r["polygon"]):
            return rid
    # fallback: nearest centroid
    best, best_d = None, float("inf")
    for rid, r in REGIONS.items():
        clat, clon = r["centroid"]
        d = haversine_km(lat, lon, clat, clon)
        if d < best_d:
            best, best_d = rid, d
    return best


def score_guess(year: int, lat: float, lon: float) -> dict:
    y = load_year(year)
    if not y:
        raise ValueError(f"no data for year {year}")
    rid = region_for_point(lat, lon)
    cell = y["regions"].get(rid)
    if not cell:
        return {"region_id": rid, "score": 0, "summary": "No data for this region this year.", "factors": {}, "sources": []}
    return {
        "region_id": rid,
        "region_name": REGIONS[rid]["name"],
        "score": cell["score"],
        "summary": cell["summary"],
        "factors": cell.get("factors", {}),
        "sources": cell.get("sources", []),
    }
