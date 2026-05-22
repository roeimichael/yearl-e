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

SOURCES = {
    "maddison.xlsx": "https://dataverse.nl/api/access/datafile/421302",  # MPD2023 dataverse file
    "brecke.xlsx": "https://brecke.inta.gatech.edu/wp-content/uploads/sites/19/2018/09/Conflict-Catalog-18-vars.xlsx",
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


def main() -> int:
    for name, url in SOURCES.items():
        try:
            fetch(name, url)
        except Exception as e:
            print(f"  [FAIL] {name}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
