"""V-Dem CY-Core v15 loader and lookup.

V-Dem covers 1789–present. Use it to source governance scores instead of
leaving them at the neutral 50 default. We pick the Electoral Democracy Index
(v2x_polyarchy) as our primary governance score because it's the most
intuitive 0–1 measure of "how democratic is this place" and is comparable
across the whole range.

For a region with multiple member countries we take the best-scored one
(matching the spirit of `compute_economy` which picks the richest member).
"""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Pre-sliced 5-column CSV from prep_vdem.py — full Core is 200 MB.
VDEM_PATH = ROOT / "data" / "raw" / "vdem_governance.csv"

# V-Dem country_text_id mostly matches ISO3 but has a handful of exceptions we
# care about. Map V-Dem code → ISO3. (None of these fire for the early-modern era
# we currently ship, but they keep the lookup correct as later eras are added.)
VDEM_TO_ISO3 = {
    "ZZB": "MMR",  # Zanzibar/Burma variant → Myanmar
    "DRV": "VNM",  # Democratic Republic of Vietnam (North)
    "RVN": "VNM",  # Republic of Vietnam (South)
    "PSG": "PSE",  # Palestine/Gaza
    # Everything else is 1:1 with ISO3.
}


@lru_cache(maxsize=1)
def _load() -> dict[tuple[str, int], dict]:
    """Return {(iso3, year): {polyarchy, libdem, relig}}. Lazy + cached.
    `relig` is v2clrelig_osp (freedom of religion, 0–4)."""
    if not VDEM_PATH.exists():
        return {}
    out = {}
    with VDEM_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iso = row.get("country_text_id", "").strip()
            iso = VDEM_TO_ISO3.get(iso, iso)
            try:
                year = int(row["year"])
            except (KeyError, ValueError, TypeError):
                continue
            poly = row.get("v2x_polyarchy", "").strip()
            libd = row.get("v2x_libdem", "").strip()
            relig = row.get("v2clrelig_osp", "").strip()
            if not poly and not libd and not relig:
                continue
            def _f(s):
                try:
                    return float(s) if s else None
                except ValueError:
                    return None
            out[(iso, year)] = {"polyarchy": _f(poly), "libdem": _f(libd),
                                "relig": _f(relig)}
    return out


def governance(iso3_members: list[str], year: int) -> tuple[int | None, str | None]:
    """Pick best V-Dem polyarchy across member ISOs for `year`.
    Returns (score_0_100, source_iso) or (None, None) if no coverage.
    """
    data = _load()
    if not data:
        return None, None
    best_iso, best_val = None, -1.0
    for iso in iso3_members:
        cell = data.get((iso, year))
        if not cell or cell.get("polyarchy") is None:
            continue
        if cell["polyarchy"] > best_val:
            best_iso, best_val = iso, cell["polyarchy"]
    if best_iso is None:
        return None, None
    return round(best_val * 100), best_iso


def religious_freedom(iso3_members: list[str], year: int) -> tuple[int | None, str | None]:
    """Best V-Dem freedom-of-religion (v2clrelig_osp, 0–4) across member ISOs for
    `year`, mapped to 0–100. Returns (score, source_iso) or (None, None)."""
    data = _load()
    if not data:
        return None, None
    best_iso, best_val = None, -1.0
    for iso in iso3_members:
        cell = data.get((iso, year))
        if not cell or cell.get("relig") is None:
            continue
        if cell["relig"] > best_val:
            best_iso, best_val = iso, cell["relig"]
    if best_iso is None:
        return None, None
    return round(best_val / 4.0 * 100), best_iso


@lru_cache(maxsize=1)
def _repression_by_year() -> dict[int, float]:
    """{year: mean global religious repression} = mean over all countries of
    (4 - v2clrelig_osp)/4, i.e. 0 (everyone free) … 1 (no one free). A real,
    time-varying global persecution signal for the dynamic year-weights, covering
    the V-Dem era (1789+) where witch-trials no longer apply."""
    by_year: dict[int, list[float]] = {}
    for (_, year), cell in _load().items():
        r = cell.get("relig")
        if r is not None:
            by_year.setdefault(year, []).append((4.0 - r) / 4.0)
    return {y: sum(v) / len(v) for y, v in by_year.items() if v}


def global_repression(year: int) -> float | None:
    """Mean global religious repression for `year` (0–1), or None pre-V-Dem."""
    return _repression_by_year().get(year)


def available() -> bool:
    return VDEM_PATH.exists()
