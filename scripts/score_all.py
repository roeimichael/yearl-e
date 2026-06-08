"""Re-score every year in one process (loaders cached once — fast).

Usage: python scripts/score_all.py
Scores all years that have a data/raw/{year}_extract.json.
"""
from __future__ import annotations
import glob
import os
import sys

import rank_year


def main() -> int:
    years = sorted(int(os.path.basename(p).split("_")[0])
                   for p in glob.glob(str(rank_year.RAW / "*_extract.json")))
    print(f"re-scoring {len(years)} years ({years[0]}..{years[-1]}) in-process...")
    ok = 0
    for i, y in enumerate(years):
        try:
            if rank_year.build_year_file(y):
                ok += 1
        except Exception as e:  # noqa: BLE001 — report and continue
            print(f"  FAIL {y}: {e}", file=sys.stderr)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(years)}")
    print(f"DONE {ok}/{len(years)} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
