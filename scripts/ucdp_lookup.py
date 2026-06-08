"""UCDP/PRIO Armed Conflict Dataset v25.1 → the same conflict schema Brecke uses,
for post-1999 safety (Brecke's catalog ends 1999).

UCDP ACD is already year-keyed: one row per (conflict, year) it was active. We map
each row to {name, sy, ey, region_code, fatalities} so rank_year.compute_safety
scores it exactly like a Brecke conflict:
  - name        = the location country (so polity-name keyword matching hits the
                  specific country, e.g. "Iraq" → "Republic of Iraq")
  - region_code = the location's Brecke macro-region (coarse fallback match)
  - fatalities  = proxy from intensity_level: level 2 (war, ≥1000 battle deaths/yr)
                  → 60000 (compute_safety's "major" branch); level 1 (minor) → None

Covers 2000-2024; 2025+ has no data yet (those years fall back to no conflicts).
"""
from __future__ import annotations
import csv
import io
import zipfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from factors import ISO3_TO_BRECKE

ROOT = Path(__file__).parent.parent
UCDP_ZIP = ROOT / "data" / "raw" / "ucdp_acd.zip"

# UCDP `location` country name → ISO3 (only the 69 names that appear from 2000 on;
# parentheticals kept on the UCDP side, stripped for our display name).
LOC_TO_ISO = {
    "Afghanistan": "AFG", "Algeria": "DZA", "Angola": "AGO", "Australia": "AUS",
    "Azerbaijan": "AZE", "Bangladesh": "BGD", "Benin": "BEN", "Burkina Faso": "BFA",
    "Burundi": "BDI", "Cambodia (Kampuchea)": "KHM", "Cameroon": "CMR",
    "Central African Republic": "CAF", "Chad": "TCD", "China": "CHN",
    "Colombia": "COL", "Congo": "COG", "DR Congo (Zaire)": "COD", "Djibouti": "DJI",
    "Egypt": "EGY", "Eritrea": "ERI", "Ethiopia": "ETH", "Georgia": "GEO",
    "Guinea": "GIN", "Haiti": "HTI", "India": "IND", "Indonesia": "IDN",
    "Iran": "IRN", "Iraq": "IRQ", "Israel": "ISR", "Ivory Coast": "CIV",
    "Jordan": "JOR", "Kenya": "KEN", "Kyrgyzstan": "KGZ", "Lebanon": "LBN",
    "Liberia": "LBR", "Libya": "LBY", "Malaysia": "MYS", "Mali": "MLI",
    "Mauritania": "MRT", "Mozambique": "MOZ", "Myanmar (Burma)": "MMR",
    "Nepal": "NPL", "Niger": "NER", "Nigeria": "NGA", "North Macedonia": "MKD",
    "Pakistan": "PAK", "Peru": "PER", "Philippines": "PHL",
    "Russia (Soviet Union)": "RUS", "Rwanda": "RWA", "Senegal": "SEN",
    "Sierra Leone": "SLE", "Somalia": "SOM", "South Sudan": "SSD",
    "Sri Lanka": "LKA", "Sudan": "SDN", "Syria": "SYR", "Tajikistan": "TJK",
    "Tanzania": "TZA", "Thailand": "THA", "Togo": "TGO", "Tunisia": "TUN",
    "Turkey": "TUR", "Uganda": "UGA", "Ukraine": "UKR", "United Kingdom": "GBR",
    "United States of America": "USA", "Uzbekistan": "UZB",
    "Yemen (North Yemen)": "YEM",
}

# UCDP type_of_conflict → a short label for the conflict name.
_TYPE = {"1": "colonial", "2": "interstate", "3": "civil", "4": "internationalized"}


def _display(loc: str) -> str:
    """Strip the parenthetical alias UCDP appends ('DR Congo (Zaire)' → 'DR Congo')."""
    return loc.split("(")[0].strip()


@lru_cache(maxsize=1)
def _by_year() -> dict[int, list[dict]]:
    """{year: [conflict dicts]} in the Brecke-compatible schema."""
    out: dict[int, list[dict]] = defaultdict(list)
    with zipfile.ZipFile(UCDP_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                try:
                    year = int(r["year"])
                except (ValueError, KeyError):
                    continue
                level = (r.get("intensity_level") or "").strip()
                fatal = 60000 if level == "2" else None
                ctype = _TYPE.get((r.get("type_of_conflict") or "").strip(), "armed")
                side_b = (r.get("side_b") or "").strip()
                # one conflict can list several locations ("Israel, Lebanon")
                for loc in (r.get("location") or "").split(","):
                    loc = loc.strip()
                    iso = LOC_TO_ISO.get(loc)
                    if not iso:
                        continue
                    disp = _display(loc)
                    nm = f"{disp}: {ctype} conflict" + (f" vs {side_b}" if side_b else "")
                    out[year].append({
                        "name": nm,
                        "sy": year, "ey": year,
                        "region_code": ISO3_TO_BRECKE.get(iso),
                        "fatalities": fatal,
                    })
    return dict(out)


def active_in(year: int) -> list[dict]:
    """Conflicts active in `year`, Brecke-schema. Empty if outside UCDP coverage."""
    return _by_year().get(year, [])


def coverage() -> tuple[int, int]:
    """(min_year, max_year) the dataset covers."""
    ys = _by_year().keys()
    return (min(ys), max(ys)) if ys else (0, 0)
