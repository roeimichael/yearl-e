"""One-time slice: extract just the V-Dem columns we use into a small file.

V-Dem CY-Core is 200 MB (1818 columns) — too slow to reparse per build.
Slice it down to ~5 MB so the lookup loads in <1s.

Run once after fetch_sources.py. Re-run when V-Dem ships a new version.
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "raw" / "vdem_v15_core.csv"
DST = ROOT / "data" / "raw" / "vdem_governance.csv"

WANT = ["country_name", "country_text_id", "year", "v2x_polyarchy", "v2x_libdem"]


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC} — run fetch_sources.py first", file=sys.stderr)
        return 1
    n = 0
    with SRC.open(encoding="utf-8", newline="") as fin, \
         DST.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=WANT)
        writer.writeheader()
        for row in reader:
            writer.writerow({k: row.get(k, "") for k in WANT})
            n += 1
    size = DST.stat().st_size / 1024
    print(f"wrote {DST} ({size:.1f} KB, {n} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
