"""End-to-end build for one year — runs fetch_year + fetch_year_wiki + rank_year.

Usage: python scripts/build_year.py 1750
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = sys.executable


def build_one(year: int) -> int:
    print(f"=== {year} ===")
    for script in ("fetch_year.py", "fetch_year_wiki.py", "rank_year.py"):
        rc = subprocess.call([PY, str(ROOT / "scripts" / script), str(year)])
        if rc != 0:
            print(f"  [FAIL] {script} {year} exited {rc}", file=sys.stderr)
            return rc
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/build_year.py <year>", file=sys.stderr)
        return 2
    return build_one(int(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
