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

# V-Dem country_text_id mostly matches ISO3 but has a handful of exceptions
# we care about. Map V-Dem code → ISO3.
VDEM_TO_ISO3 = {
    "ZZB": "ZAR",  # Burma → Myanmar (V-Dem uses BMA, but accommodate variants)
    "DRV": "VNM",  # Democratic Republic of Vietnam
    "RVN": "VNM",  # Republic of Vietnam (South)
    "PSG": "PSE",  # Palestine/Gaza
    "TWN": "TWN",
    # Most others are 1:1 ISO3.
}


@lru_cache(maxsize=1)
def _load() -> dict[tuple[str, int], dict]:
    """Return {(iso3, year): {polyarchy, libdem}}. Lazy + cached."""
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
            if not poly and not libd:
                continue
            try:
                poly_f = float(poly) if poly else None
                libd_f = float(libd) if libd else None
            except ValueError:
                continue
            out[(iso, year)] = {"polyarchy": poly_f, "libdem": libd_f}
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


def available() -> bool:
    return VDEM_PATH.exists()
