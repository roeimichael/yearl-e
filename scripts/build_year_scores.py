"""Stub: orchestrate per-year score builds.

Real pipeline TBD — see scripts/README.md. This file exists so the build entry
point has a known path. For now it just prints which years still need data.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
YEAR_DIR = ROOT / "data" / "year_scores"
REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]

# Medium scope: 500 years × ~80 regions. Sample window for v1.
YEAR_RANGE = list(range(1, 2026, 50))  # placeholder cadence


def main() -> None:
    have = {int(p.stem) for p in YEAR_DIR.glob("*.json")}
    todo = [y for y in YEAR_RANGE if y not in have]
    print(f"regions: {len(REGIONS)}  years_have: {sorted(have)}  years_todo: {todo}")


if __name__ == "__main__":
    main()
