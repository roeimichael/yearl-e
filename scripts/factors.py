"""Health + religious-tolerance factor providers (layered, honest).

Pre-1800 has no clean global per-year datasets for either factor, so each uses
a tiered model:

  HEALTH
    Tier 1  real life expectancy for the region's dominant modern country
            (OWID, mostly 1800+ and a few European countries earlier)
    Tier 2  the continental life-expectancy aggregate (OWID, back to 1770;
            extrapolated flat before that — pre-modern life-exp was ~stable)
    + conflict penalty (war wrecks health) and a small economy nudge
            (wealth buffers mortality)

  RELIGIOUS TOLERANCE
    Base    a modeled macro-region baseline for the early-modern era, grounded
            in established history of state-religion enforcement
    - real persecution-event penalty from the Leeson-Russ witch-trial database
            (10,940 European trials 1300-1850), by (country, decade)

`factor_source` is reported honestly: "lifeexp" (real), "modeled" (baseline),
"witch-trials" when a real persecution penalty was applied.

Also the single home for the ISO3 -> Brecke macro-region table (shared with
rank_year's safety scoring) to avoid duplication / circular imports.
"""
from __future__ import annotations
import bisect
import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"

# ─── Brecke macro-regions (shared with rank_year safety) ─────────────────────
# 1 British Isles, 2 W Europe, 3 Central Europe, 4 E Europe, 5 Middle East,
# 6 N Africa, 7 Sub-Saharan, 8 South Asia, 9 SE Asia, 10 East Asia,
# 11 Oceania, 12 Central Asia, 13 Latin America, 14 N America.
BRECKE_MEMBERS = {
    1: "GBR IRL",
    2: "FRA ESP PRT ITA BEL LUX NLD CHE MCO AND",
    3: "DEU AUT CZE SVK HUN POL SVN HRV LIE",
    4: "RUS UKR BLR LTU LVA EST ROU MDA BGR GRC SRB BIH MKD ALB MNE",
    5: "TUR IRN IRQ SYR LBN ISR PSE JOR SAU YEM OMN ARE KWT QAT BHR AZE ARM GEO AFG",
    6: "MAR DZA TUN LBY EGY SDN SSD MRT ESH",
    7: ("ETH ERI SOM DJI KEN TZA UGA RWA BDI COD COG AGO ZMB ZWE MOZ MWI MDG "
        "ZAF NAM BWA LSO SWZ NGA NER TCD CMR CAF GAB GNQ BEN TGO GHA CIV BFA "
        "MLI SEN GMB GNB GIN SLE LBR"),
    8: "IND PAK BGD NPL BTN LKA MDV",
    9: "MMR THA LAO KHM VNM MYS SGP IDN PHL BRN TLS",
    10: "CHN MNG TWN JPN KOR PRK",
    11: "AUS NZL PNG FJI",
    12: "KAZ UZB TKM TJK KGZ",
    13: ("MEX GTM BLZ HND SLV NIC CRI PAN CUB JAM HTI DOM BHS TTO COL VEN ECU "
         "PER BOL BRA PRY URY ARG CHL GUY SUR"),
    14: "USA CAN",
}
ISO3_TO_BRECKE = {iso: code for code, isos in BRECKE_MEMBERS.items() for iso in isos.split()}

# Brecke code -> continent bucket for the OWID life-exp regional fallback.
BRECKE_TO_CONT = {
    1: "EUR", 2: "EUR", 3: "EUR", 4: "EUR",
    5: "ASI", 6: "AFR", 7: "AFR", 8: "ASI", 9: "ASI", 10: "ASI", 12: "ASI",
    11: "OCE", 13: "AMR", 14: "AMR",
}
CONT_TO_OWID = {"EUR": "OWID_EUR", "AFR": "OWID_AFR", "ASI": "OWID_ASI",
                "OCE": "OWID_OCE", "AMR": "OWID_WRL"}  # no American aggregate in OWID

# ─── early-modern tolerance baseline by macro-region ─────────────────────────
# Modeled (not measured): typical degree of state-religion enforcement / minority
# treatment, 1500-1815. Coarse by design; refined by real witch-trial penalties
# for Europe. Higher = more tolerant. Rationale in comments.
TOLERANCE_BASELINE = {
    1:  42,  # British Isles — Protestant establishment, Catholic disabilities
    2:  40,  # W Europe — France revokes Edict of Nantes 1685; Spain Inquisition
    3:  44,  # Central Europe — HRE cuius-regio coexistence after Westphalia
    4:  48,  # E Europe — tolerant Poland-Lithuania; Ottoman Balkan millet
    5:  52,  # Middle East — Ottoman/Safavid dhimmi: protected, second-class
    6:  48,  # N Africa — Islamic dhimmi system
    7:  55,  # Sub-Saharan — diverse, mostly non-centralized enforcement
    8:  50,  # South Asia — Mughal swings Akbar(tolerant)->Aurangzeb(harsh)
    9:  55,  # SE Asia — syncretic, cosmopolitan trade ports
    10: 44,  # East Asia — China folk-tolerant but anti-Christian; Japan crushes Christianity
    11: 60,  # Oceania — indigenous, no state religion
    12: 48,  # Central Asia — Islamic khanates
    13: 26,  # Latin America — colonial Inquisition + forced conversion
    14: 46,  # N America — Puritan intolerance vs Pennsylvania/Rhode Island pluralism
}
GLOBAL_TOL = 45

# witch-trial country name (gadm.adm0) -> ISO3
WT_NAME_TO_ISO = {
    "United Kingdom": "GBR", "Germany": "DEU", "Switzerland": "CHE", "France": "FRA",
    "Belgium": "BEL", "Sweden": "SWE", "Netherlands": "NLD", "Italy": "ITA",
    "Denmark": "DNK", "Spain": "ESP", "Hungary": "HUN", "Norway": "NOR",
    "Luxembourg": "LUX", "Estonia": "EST", "Finland": "FIN", "Austria": "AUT",
    "Poland": "POL", "Ireland": "IRL", "Czech Republic": "CZE",
}


# ─── data loaders (cached) ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _life_exp() -> dict[str, tuple[list[int], list[float]]]:
    """entity_code -> (sorted_years, life_exp[]) for nearest-year lookup.
    Keeps ISO3 countries and OWID_* aggregates."""
    out: dict[str, list[tuple[int, float]]] = {}
    p = RAW / "owid_life_exp.csv"
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("code") or ""
            le = row.get("life_expectancy_0") or ""
            yr = row.get("year") or ""
            if not code or not le or not yr.lstrip("-").isdigit():
                continue
            try:
                out.setdefault(code, []).append((int(yr), float(le)))
            except ValueError:
                continue
    packed = {}
    for code, pairs in out.items():
        pairs.sort()
        packed[code] = ([y for y, _ in pairs], [v for _, v in pairs])
    return packed


def _nearest_le(code: str, year: int, max_gap: int | None = None) -> float | None:
    """Life expectancy for `code` at the nearest available year. With `max_gap`,
    reject matches farther than that many years (so a 1700 game never borrows a
    country's 1950 life-expectancy)."""
    le = _life_exp().get(code)
    if not le:
        return None
    years, vals = le
    i = bisect.bisect_left(years, year)
    cands = []
    if i < len(years):
        cands.append((abs(years[i] - year), vals[i]))
    if i > 0:
        cands.append((abs(years[i - 1] - year), vals[i - 1]))
    if not cands:
        return None
    gap, val = min(cands)
    if max_gap is not None and gap > max_gap:
        return None
    return val


@lru_cache(maxsize=1)
def _witch_intensity() -> dict[tuple[str, int], int]:
    """(iso3, decade) -> total persons tried. Persecution-intensity signal."""
    out: dict[tuple[str, int], int] = {}
    p = RAW / "witch_trials.csv"
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            iso = WT_NAME_TO_ISO.get((row.get("gadm.adm0") or "").strip())
            dec = row.get("decade") or ""
            tried = row.get("tried") or ""
            if not iso or not dec.isdigit():
                continue
            try:
                n = int(float(tried)) if tried not in ("", "NA") else 1
            except ValueError:
                n = 1
            out[(iso, int(dec))] = out.get((iso, int(dec)), 0) + n
    return out


# ─── factor providers ────────────────────────────────────────────────────────


def health(member_iso3: list[str], year: int, conflict_hits: int,
           econ_score: int) -> tuple[int, str]:
    """Life-expectancy-anchored health, 1-100. Tier1 country -> Tier2 continent
    -> global; then conflict penalty + small economy buffer."""
    le = None
    source = "modeled"
    # Tier 1: dominant member country's real life expectancy (only if a data
    # point exists within ~25 years — no borrowing modern values for old games).
    for iso in member_iso3:
        v = _nearest_le(iso, year, max_gap=25)
        if v is not None:
            le, source = v, "lifeexp"
            break
    # Tier 2: continental aggregate for the dominant member's region.
    if le is None and member_iso3:
        code = ISO3_TO_BRECKE.get(member_iso3[0])
        cont = BRECKE_TO_CONT.get(code) if code else None
        owid = CONT_TO_OWID.get(cont) if cont else None
        if owid:
            v = _nearest_le(owid, max(year, 1770))  # floor: aggregates start 1770
            if v is not None:
                le, source = v, "lifeexp"
    if le is None:
        le = 28.0  # pre-modern global baseline

    # life expectancy -> base health score (le 22->8, 50->92)
    base = (le - 22.0) / (50.0 - 22.0) * 84.0 + 8.0
    base -= min(18, 6 * conflict_hits)          # war wrecks health
    base += max(-7, min(7, (econ_score - 50) * 0.12))  # wealth buffers it
    return max(1, min(100, round(base))), source


def tolerance(member_iso3: list[str], year: int) -> tuple[int, str, int]:
    """Modeled regional baseline minus real witch-trial persecution penalty.
    Returns (score, source, witch_penalty_applied)."""
    codes = [ISO3_TO_BRECKE[i] for i in member_iso3 if i in ISO3_TO_BRECKE]
    base = TOLERANCE_BASELINE[codes[0]] if codes else GLOBAL_TOL

    # real penalty: peak witch-trial intensity among member countries this decade
    decade = (year // 10) * 10
    wt = _witch_intensity()
    peak = max((wt.get((iso, decade), 0) for iso in member_iso3), default=0)
    penalty = min(30, round((peak ** 0.5) * 2)) if peak else 0

    score = max(1, min(100, base - penalty))
    source = "witch-trials" if penalty else "modeled"
    return score, source, penalty
