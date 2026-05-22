"""Download Natural Earth 1:110m admin-0 countries GeoJSON.

Used to replace bbox polygons with real country shapes. ~250KB, 241 features.
Each feature has ISO_A3 (e.g. "FRA") + geometry. Our region groupings union
multiple ISO3 shapes into each game region.

Run: python scripts/fetch_natural_earth.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
OUT = RAW / "ne_110m_admin_0.geojson"


def main() -> int:
    if OUT.exists() and OUT.stat().st_size > 100_000:
        print(f"[cache] {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")
        return 0
    print(f"[GET] {URL}")
    r = requests.get(URL, timeout=120, headers={"User-Agent": "yearl-e/0.1"})
    r.raise_for_status()
    OUT.write_bytes(r.content)
    fc = json.loads(r.content)
    print(f"[ok] {OUT.name} ({len(r.content)/1024:.1f} KB), {len(fc['features'])} features")
    # Quick sanity: list some ISO3 codes.
    samples = sorted({f["properties"].get("ISO_A3") for f in fc["features"]})
    print(f"[iso] {len(samples)} unique ISO_A3 codes. First 20: {samples[:20]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
