"""Historical Conflict Event Dataset (Dincecco, Onorato, Wang et al.) → the same
conflict schema Brecke/UCDP use, for PRE-1400 safety (Brecke's catalog starts
~1400). HCED catalogs geolocated, dated battles 1468 BCE-2003 CE.

Each battle row maps to {name, sy, ey, region_code, fatalities} so
rank_year.compute_safety scores it exactly like a Brecke conflict:
  - name        = "<Battle> (<War>)" so any polity-name keyword still has a shot
  - region_code = the battle country's Brecke macro-region (the coarse match that
                  does the real work pre-modern, since medieval polity names rarely
                  keyword-match a modern battle place name)
  - fatalities  = proxy from the Lehmann-Zhukov intensity scale (log10 of battle
                  deaths): scale >=5 (~>=100k) → 100000 (compute_safety's "major"
                  branch); lower / blank → None (minor)

We only feed years where Brecke is absent (pre-1400); 1400+ keeps Brecke. So the
country coverage that matters is the medieval heartlands, which are clean names.
Oceans, typos and "City, Country" forms in the long tail resolve where we can and
are skipped otherwise.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from factors import ISO3_TO_BRECKE

ROOT = Path(__file__).parent.parent
HCED_CSV = ROOT / "data" / "raw" / "hced_v3.csv"

# HCED `Country` (modern name) → ISO3. Lowercased keys; input is lowercased and
# .strip()ed before lookup, with a comma-split fallback (see _iso). Includes the
# dataset's typos/variants (mauritannia, phillipines, united kingom, ...).
COUNTRY_TO_ISO: dict[str, str] = {
    "afghanistan": "AFG", "albania": "ALB", "algeria": "DZA", "angola": "AGO",
    "argentina": "ARG", "armenia": "ARM", "australia": "AUS", "austria": "AUT",
    "azerbaijan": "AZE", "bahrain": "BHR", "bangladesh": "BGD", "belarus": "BLR",
    "belgium": "BEL", "belize": "BLZ", "benin": "BEN", "bhutan": "BTN",
    "bolivia": "BOL", "bosnia and hercegovina": "BIH", "bosnia and herzegovina": "BIH",
    "brazil": "BRA", "britain": "GBR", "brunei": "BRN", "bulgaria": "BGR",
    "cambodia": "KHM", "cameroon": "CMR", "canada": "CAN", "chad": "TCD",
    "chile": "CHL", "china": "CHN", "colombia": "COL", "congo": "COG",
    "costa rica": "CRI", "croatia": "HRV", "cuba": "CUB", "cyprus": "CYP",
    "czech republic": "CZE", "czechia": "CZE", "denmark": "DNK", "djibouti": "DJI",
    "dominican republic": "DOM", "democratic republic of the congo": "COD",
    "ecuador": "ECU", "egypt": "EGY", "el salvador": "SLV", "eritrea": "ERI",
    "estonia": "EST", "ethiopia": "ETH", "finland": "FIN", "france": "FRA",
    "georgia": "GEO", "germany": "DEU", "ghana": "GHA", "greece": "GRC",
    "guatemala": "GTM", "guinea": "GIN", "guinea-bissau": "GNB", "guyana": "GUY",
    "haiti": "HTI", "holland": "NLD", "honduras": "HND", "hungary": "HUN",
    "india": "IND", "indonesia": "IDN", "iran": "IRN", "iraq": "IRQ",
    "ireland": "IRL", "israel": "ISR", "italy": "ITA", "ivory coast": "CIV",
    "jamaica": "JAM", "japan": "JPN", "jordan": "JOR", "kazakhstan": "KAZ",
    "kenya": "KEN", "korea": "KOR", "kosovo": "KOS", "kuwait": "KWT",
    "kyrgyzstan": "KGZ", "laos": "LAO", "latvia": "LVA", "lebanon": "LBN",
    "lesotho": "LSO", "libya": "LBY", "liechtenstein": "LIE", "lithuania": "LTU",
    "luxembourg": "LUX", "macedonia": "MKD", "macedonia (fyrom)": "MKD",
    "madagascar": "MDG", "malaysia": "MYS", "mali": "MLI", "malta": "MLT",
    "mauritania": "MRT", "mauritannia": "MRT", "mauritius": "MUS", "mexico": "MEX",
    "moldavia": "MDA", "moldova": "MDA", "mongolia": "MNG", "montenegro": "MNE",
    "morocco": "MAR", "mozambique": "MOZ", "myanmar": "MMR", "namibia": "NAM",
    "nepal": "NPL", "netherlands": "NLD", "the netherlands": "NLD",
    "new zealand": "NZL", "nicaragua": "NIC", "nigeria": "NGA",
    "north korea": "PRK", "norway": "NOR", "oman": "OMN", "pakistan": "PAK",
    "panama": "PAN", "papua new guinea": "PNG", "paraguay": "PRY",
    "palesinian territories": "PSE", "west bank and gaza": "PSE",
    "peru": "PER", "philippines": "PHL", "phillipines": "PHL", "poland": "POL",
    "portugal": "PRT", "romania": "ROU", "russia": "RUS", "saudi arabi": "SAU",
    "saudi arabia": "SAU", "senegal": "SEN", "serbia": "SRB", "sicily": "ITA",
    "sierra leone": "SLE", "singapore": "SGP", "slovakia": "SVK",
    "slovenia": "SVN", "solomon islands": "SLB", "somalia": "SOM",
    "south africa": "ZAF", "south african republic": "ZAF", "south africsa": "ZAF",
    "south korea": "KOR", "south sudan": "SSD", "spain": "ESP", "sri lanka": "LKA",
    "sudan": "SDN", "suriname": "SUR", "swaziland": "SWZ", "sweden": "SWE",
    "switzerland": "CHE", "syria": "SYR", "taiwan": "TWN", "tajikistan": "TJK",
    "tanzania": "TZA", "thailand": "THA", "togo": "TGO", "tunisia": "TUN",
    "turkey": "TUR", "turkmenistan": "TKM", "uganda": "UGA", "ukraine": "UKR",
    "united arab emirates": "ARE", "united kingdom": "GBR", "united kingom": "GBR",
    "united states": "USA", "uruguay": "URY", "uzbekistan": "UZB",
    "venezuela": "VEN", "vietnam": "VNM", "western sahara": "SAH", "yemen": "YEM",
    "zambia": "ZMB", "zimbabwe": "ZWE",
}


def _iso(country: str) -> str | None:
    """Resolve an HCED country string to ISO3. Tries the whole name, then the
    last comma-part then the first (HCED writes both 'City, Country' and a few
    'CountryA, CountryB' rows). Returns None for oceans / unmappable."""
    c = country.strip().lower()
    if c in COUNTRY_TO_ISO:
        return COUNTRY_TO_ISO[c]
    if "," in c:
        parts = [p.strip() for p in c.split(",")]
        for p in (parts[-1], parts[0]):
            if p in COUNTRY_TO_ISO:
                return COUNTRY_TO_ISO[p]
    return None


def _intensity(row: dict) -> int | None:
    """Lehmann-Zhukov scale as an int, falling back to the inferred scale."""
    for key in ("Lehmann Zhukov Scale", "Infered Scale"):
        v = (row.get(key) or "").strip()
        try:
            return int(float(v))
        except (ValueError, TypeError):
            continue
    return None


def _clean_war(raw: str) -> str:
    """Normalize the War field ("['World War II']" / "3rd Dutch War" / "NA")."""
    w = (raw or "").strip().strip("[]").replace("'", "").replace('"', "").strip()
    return "" if w.lower() in ("", "na") else w


# A war's recorded battles split into separate conflict-spans wherever there is a
# gap longer than this — generic names ("Civil War", "Sino-Indian War") are reused
# across millennia, so grouping by name alone would fuse unrelated wars into one
# absurd span. 30 years comfortably keeps real campaigns (battles every few years)
# whole while separating distinct historical instances of a reused name.
WAR_GAP = 30


@lru_cache(maxsize=1)
def _wars() -> tuple[list[dict], list[dict]]:
    """Group HCED battles into war-spans. Battles sharing a War name are collected,
    then split into sessions wherever consecutive battle years are >WAR_GAP apart;
    each session becomes one conflict active from its first to last battle (Brecke's
    span model), carrying the Brecke macro-regions that saw a battle and whether any
    was major. Unnamed battles stay single-year events. Rows whose country can't be
    resolved to a macro-region are dropped."""
    raw: dict[str, list[tuple[int, int, bool]]] = defaultdict(list)  # war -> [(year, code, major)]
    singles: list[dict] = []
    with open(HCED_CSV, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                year = int(float((r.get("Year") or "").strip()))
            except ValueError:
                continue
            iso = _iso(r.get("Country") or "")
            if not iso:
                continue
            code = ISO3_TO_BRECKE.get(iso)
            if code is None:
                continue
            major = (lambda s: s is not None and s >= 5)(_intensity(r))
            war = _clean_war(r.get("War") or "")
            if war:
                raw[war].append((year, code, major))
            else:
                battle = (r.get("Battle") or "battle").strip() or "battle"
                singles.append({"name": battle, "year": year,
                                "code": code, "major": major})

    wars: list[dict] = []
    for name, evts in raw.items():
        evts.sort()
        session: list[tuple[int, int, bool]] = []

        def flush(s: list[tuple[int, int, bool]]):
            if s:
                wars.append({"name": name, "sy": s[0][0], "ey": s[-1][0],
                             "codes": {c for _, c, _ in s},
                             "major": any(m for _, _, m in s)})
        for evt in evts:
            if session and evt[0] - session[-1][0] > WAR_GAP:
                flush(session)
                session = []
            session.append(evt)
        flush(session)
    return wars, singles


@lru_cache(maxsize=1)
def _by_year() -> dict[int, list[dict]]:
    """{year: [conflict dicts]} in the Brecke-compatible schema — one entry per
    (war, macro-region) for every year the war was active, plus single battles."""
    wars, singles = _wars()
    out: dict[int, list[dict]] = defaultdict(list)
    for w in wars:
        fatal = 100000 if w["major"] else None
        for y in range(w["sy"], w["ey"] + 1):
            for code in w["codes"]:
                out[y].append({"name": w["name"], "sy": w["sy"], "ey": w["ey"],
                               "region_code": code, "fatalities": fatal})
    for s in singles:
        out[s["year"]].append({"name": s["name"], "sy": s["year"], "ey": s["year"],
                               "region_code": s["code"],
                               "fatalities": 100000 if s["major"] else None})
    return dict(out)


def active_in(year: int) -> list[dict]:
    """Conflicts active in `year`, Brecke-schema. Empty outside HCED coverage."""
    return _by_year().get(year, [])


def coverage() -> tuple[int, int]:
    """(min_year, max_year) the dataset covers (after country resolution)."""
    ys = _by_year().keys()
    return (min(ys), max(ys)) if ys else (0, 0)
