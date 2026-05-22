"""Load region definitions + per-year score files. In-memory cache.

Year score files live under data/year_scores/{year}.json. Each region's
"polygon" is a [lon, lat] ring; centroids are [lat, lon] (matches israelle)."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

_regions_raw = json.loads((DATA / "regions.json").read_text(encoding="utf-8"))["regions"]
REGIONS: dict[str, dict] = {r["id"]: r for r in _regions_raw}

# Per-year cache: year_int -> {year, label, era_summary, regions: {...}}.
_YEAR_CACHE: dict[int, dict] = {}


def _year_path(year: int) -> Path:
    # File names are zero-padded 4 digits, with leading '-' for BCE.
    if year < 0:
        return DATA / "year_scores" / f"-{abs(year):04d}.json"
    return DATA / "year_scores" / f"{year:04d}.json"


def available_years() -> list[int]:
    out = []
    for p in (DATA / "year_scores").glob("*.json"):
        stem = p.stem
        try:
            out.append(int(stem))
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
