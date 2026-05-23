"""Bulk build year files for a range.

Usage: python scripts/build_years.py 1700 1815
Skips years that already have a year_scores file unless --force.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

from build_year import build_one

ROOT = Path(__file__).parent.parent
SCORED = ROOT / "data" / "year_scores"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--force", action="store_true",
                    help="Rebuild years that already have a year_scores file.")
    ap.add_argument("--sleep", type=float, default=0.4,
                    help="Seconds to sleep between years (Wikipedia REST rate limit).")
    args = ap.parse_args()

    fail = 0
    for year in range(args.start, args.end + 1):
        out = SCORED / f"{year:04d}.json"
        if out.exists() and not args.force:
            print(f"[skip] {year} — already built")
            continue
        rc = build_one(year)
        if rc != 0:
            fail += 1
        time.sleep(args.sleep)
    if fail:
        print(f"\n{fail} years failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
