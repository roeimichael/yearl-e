"""Download raw historical datasets once, cache under data/raw/.

Run: python scripts/fetch_sources.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# Directly downloadable raw datasets. Keep this list ordered by size so users
# with thin pipes can Ctrl-C after the small ones land.
SOURCES = {
    # ── Already wired into scoring ────────────────────────────────────────
    "maddison.xlsx": "https://dataverse.nl/api/access/datafile/421302",
    "brecke.xlsx": "https://brecke.inta.gatech.edu/wp-content/uploads/sites/19/2018/09/Conflict-Catalog-18-vars.xlsx",
    # ── Small CSVs (<1 MB each) ───────────────────────────────────────────
    "buringh_literacy.csv": "https://raw.githubusercontent.com/manjunath5496/CSV-Datasets_1/master/Estimated%20historical%20literacy%20rates%20-%20Buringh%20and%20Van%20Zanden%20(2009).csv",
    # ── Mid (~few MB each) ────────────────────────────────────────────────
    "ucdp_acd.zip": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-251-csv.zip",
    "cshapes2.zip": "https://icr.ethz.ch/data/cshapes/CShapes-2.0.zip",
    "polity5.xls": "https://www.systemicpeace.org/inscr/p5v2018.xls",
    # ── Big (>100 MB) — V-Dem covers 1789-present, 500+ indicators ───────
    "vdem_v15_core.csv": "https://zenodo.org/api/records/16413929/files/V-Dem-CY-Core-v15.csv/content",
}

# Historical polygons — separate from SOURCES because they live under
# data/raw/historical_basemaps/ and download as a bundle of snapshot years.
AOUREDNIK_YEARS = [1500, 1600, 1700, 1715, 1783, 1815, 1880, 1900, 1914, 1920, 1938, 1945, 1960, 1994, 2000]
AOUREDNIK_BASE = "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_{year}.geojson"


# Manual-download datasets (require account / form). Print a hint, do not fetch.
GATED = {
    "RCS-Dem 2.0 (denomination shares)": "https://www.thearda.com/data-archive?fid=RCSDEM2 — free ARDA account",
    "Pew Global Restrictions on Religion": "https://www.pewresearch.org/dataset/dataset-global-restrictions-on-religion-2007-2022/ — free account",
    "EM-DAT disasters": "https://www.emdat.be/ — free academic account",
    "Reba/SEDAC historic urban populations": "https://sedac.ciesin.columbia.edu/data/set/urbanspatial-hist-urban-pop-3700bc-ad2000 — NASA Earthdata Login",
    "ICPSR Levy great-power wars 1495-1815": "https://www.icpsr.umich.edu/web/ICPSR/studies/9955 — ICPSR registration",
}


def fetch(name: str, url: str) -> Path:
    out = RAW / name
    if out.exists() and out.stat().st_size > 1024:
        print(f"  [cache] {name} ({out.stat().st_size / 1024:.1f} KB)")
        return out
    print(f"  [GET ] {name} <- {url}")
    r = requests.get(url, timeout=120, headers={"User-Agent": "yearl-e/0.1"})
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"  [ok  ] {name} ({len(r.content) / 1024:.1f} KB)")
    return out


def fetch_basemaps() -> None:
    out_dir = RAW / "historical_basemaps"
    out_dir.mkdir(exist_ok=True)
    for year in AOUREDNIK_YEARS:
        name = f"world_{year}.geojson"
        out = out_dir / name
        if out.exists() and out.stat().st_size > 1024:
            print(f"  [cache] basemaps/{name}")
            continue
        url = AOUREDNIK_BASE.format(year=year)
        print(f"  [GET ] basemaps/{name} <- {url}")
        r = requests.get(url, timeout=60, headers={"User-Agent": "yearl-e/0.1"})
        if r.status_code != 200:
            print(f"  [skip] {name}: HTTP {r.status_code}")
            continue
        out.write_bytes(r.content)
        print(f"  [ok  ] basemaps/{name} ({len(r.content)/1024:.1f} KB)")


def main() -> int:
    fail = 0
    for name, url in SOURCES.items():
        try:
            fetch(name, url)
        except Exception as e:
            print(f"  [FAIL] {name}: {e}", file=sys.stderr)
            fail += 1
    print("\n── historical basemaps (aourednik) ──")
    try:
        fetch_basemaps()
    except Exception as e:
        print(f"  [FAIL] basemaps: {e}", file=sys.stderr)
        fail += 1
    print("\n── gated (manual download required) ──")
    for name, url in GATED.items():
        print(f"  [manual] {name}: {url}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
