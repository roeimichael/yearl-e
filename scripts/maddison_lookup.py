"""Maddison Project 2023 GDP/capita lookup with benchmark interpolation.

Maddison's pre-1820 data is sparse and benchmark-keyed: China every ~10 yrs,
India/Japan/Turkey/Mexico at scattered benchmark years (1500/1600/1700/1750/1820).
The old pipeline matched the EXACT game year, so 1719 found Western Europe (which
has annual series) but missed China's 1710/1720, India's 1700/1750, etc. — leaving
~80% of regions with no economy signal.

This module loads Maddison once and returns GDP/cap for any (iso3, year) by linear
interpolation between bracketing benchmark points (or nearest within a gap), so the
benchmark data actually reaches the year being scored.
"""
from __future__ import annotations
import bisect
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent
MADDISON = ROOT / "data" / "raw" / "maddison.xlsx"

# Interpolate between two benchmarks only if they're within this span (years);
# otherwise fall back to the nearest single point within MAX_GAP. Pre-industrial
# GDP/cap moves slowly, so a few decades of carry is acceptable.
MAX_INTERP_SPAN = 80
MAX_GAP = 45


@lru_cache(maxsize=1)
def _series() -> dict[str, tuple[list[int], list[float]]]:
    """iso3 -> (sorted_years, gdppc[]) from Maddison 'Full data'."""
    import openpyxl
    wb = openpyxl.load_workbook(MADDISON, read_only=True, data_only=True)
    ws = wb["Full data"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))
    ci, yi, gi = hdr.index("countrycode"), hdr.index("year"), hdr.index("gdppc")
    raw: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        cc, yr, g = row[ci], row[yi], row[gi]
        if cc and yr and g is not None:
            raw.setdefault(cc, []).append((int(yr), float(g)))
    out = {}
    for cc, pairs in raw.items():
        pairs.sort()
        out[cc] = ([y for y, _ in pairs], [v for _, v in pairs])
    return out


def gdppc(iso3: str, year: int) -> float | None:
    """GDP/capita for iso3 at year, interpolated from Maddison benchmarks.
    None if no point lies within MAX_GAP (after interpolation attempt)."""
    s = _series().get(iso3)
    if not s:
        return None
    years, vals = s
    i = bisect.bisect_left(years, year)
    # exact hit
    if i < len(years) and years[i] == year:
        return vals[i]
    lo = i - 1 if i - 1 >= 0 else None
    hi = i if i < len(years) else None
    # bracketed: linear interpolation if the bracket isn't too wide
    if lo is not None and hi is not None:
        y0, y1 = years[lo], years[hi]
        if y1 - y0 <= MAX_INTERP_SPAN:
            t = (year - y0) / (y1 - y0)
            return vals[lo] + t * (vals[hi] - vals[lo])
    # otherwise nearest single point within MAX_GAP
    cands = []
    if lo is not None:
        cands.append((year - years[lo], vals[lo]))
    if hi is not None:
        cands.append((years[hi] - year, vals[hi]))
    if not cands:
        return None
    gap, val = min(cands)
    return val if gap <= MAX_GAP else None


def best_for(member_iso3: list[str], year: int) -> tuple[str | None, float | None]:
    """Highest GDP/cap among a region's member countries (dominant territory)."""
    best_iso, best_val = None, None
    for iso in member_iso3:
        v = gdppc(iso, year)
        if v is not None and (best_val is None or v > best_val):
            best_iso, best_val = iso, v
    return best_iso, best_val
