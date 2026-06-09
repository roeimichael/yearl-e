"""Coverage audit — prove every year carries its correct regions + the data we
have, broken down by era. Complements smoke_test (which checks invariants); this
one is the human-readable inventory.

For each era it reports: year span, snapshots, regions/year, the per-factor REAL
fill rate, the data-quality spread, and flags anomalies (gap years, far-bound
snapshots, polygons with no score, cells with no factor). Run:

    python scripts/audit_coverage.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")

from backend import regions as R
import rank_year
ERA_SNAPSHOTS = rank_year.ERA_SNAPSHOTS
snapshot_for = rank_year.snapshot_for

FACTORS = ["safety", "health", "economy", "governance", "religious_tolerance"]
REAL = {"hced", "brecke", "ucdp", "lifeexp", "maddison", "vdem", "vdem-relig",
        "statehist", "witch-trials"}


def era_of(year: int):
    for era, (lo, hi, snaps) in ERA_SNAPSHOTS.items():
        if lo <= year <= hi:
            return era, snaps
    return None, None


def main() -> int:
    years = R.available_years()
    by_era: dict[str, list[int]] = defaultdict(list)
    for y in years:
        era, _ = era_of(y)
        by_era[era].append(y)

    anomalies: list[str] = []
    max_bind: dict[str, int] = {}

    # continuity: every year in each era's [lo,hi] (except 0) should have a file
    have = set(years)
    for era, (lo, hi, snaps) in ERA_SNAPSHOTS.items():
        missing = [y for y in range(lo, hi + 1) if y != 0 and y not in have]
        if missing:
            anomalies.append(f"{era}: {len(missing)} gap years, e.g. {missing[:5]}")

    print(f"TOTAL years: {len(years)}  ({years[0]}..{years[-1]})\n")
    print(f"{'era':12} {'years':>6} {'snaps':>6} {'reg/yr(min-avg-max)':>20} {'cells':>7}  factor real-fill")
    print("-" * 110)

    grand_cells = 0
    for era in ERA_SNAPSHOTS:
        ys = sorted(by_era.get(era, []))
        if not ys:
            continue
        snaps = ERA_SNAPSHOTS[era][2]
        reg_counts = []
        fill = {f: Counter() for f in FACTORS}
        dq = Counter()
        era_cells = 0
        for y in ys:
            d = R.load_year(y)
            regs = d["regions"]
            n = len(regs)
            reg_counts.append(n)
            # binding: the year must sit on its nearest snapshot (the "relevant
            # regions" guarantee). region_set written into the file must equal what
            # snapshot_for() resolves now.
            set_name = d.get("region_set", "")
            expect = snapshot_for(y)
            if set_name != expect:
                anomalies.append(f"{y}: region_set '{set_name}' != nearest snapshot '{expect}'")
            snap_yr = int(expect.split("_")[-1])
            max_bind[era] = max(max_bind.get(era, 0), abs(y - snap_yr))
            for c in regs.values():
                era_cells += 1
                grand_cells += 1
                fs = c.get("factor_sources", {})
                for f in FACTORS:
                    fill[f][fs.get(f, "?")] += 1
                dq[len(c.get("scored_factors", []))] += 1
            # polygons with no score (should be 0 — smoke covers it, re-confirm)
            snap = R.load_region_set(set_name)
            no_score = set(snap) - set(regs)
            if no_score:
                anomalies.append(f"{y}: {len(no_score)} polygons with no score")
        realpct = {}
        for f in FACTORS:
            tot = sum(fill[f].values())
            realpct[f] = round(100 * sum(v for k, v in fill[f].items() if k in REAL) / tot) if tot else 0
        rc = f"{min(reg_counts)}-{round(sum(reg_counts)/len(reg_counts))}-{max(reg_counts)}"
        fillstr = "  ".join(f"{f[:4]}:{realpct[f]}%" for f in FACTORS)
        print(f"{era:12} {len(ys):>6} {len(snaps):>6} {rc:>20} {era_cells:>7}  {fillstr}")
    print("\nmax snapshot-binding distance per era (years a game-year sits from its border snapshot):")
    for era, mb in max_bind.items():
        print(f"  {era}: {mb}y")

    # dq spread overall
    print("\ndata-quality (real factors per cell) across all eras:")
    dq_all = Counter()
    for y in years:
        for c in R.load_year(y)["regions"].values():
            dq_all[len(c.get("scored_factors", []))] += 1
    tot = sum(dq_all.values())
    for k in sorted(dq_all):
        print(f"  {k}/5 factors: {dq_all[k]:>7}  ({round(100*dq_all[k]/tot)}%)")
    print(f"  total cells: {tot}")

    print("\nANOMALIES:" if anomalies else "\nNo anomalies — every polygon has a score, no gap years.")
    for a in anomalies[:40]:
        print("  ! " + a)
    return 1 if anomalies else 0


if __name__ == "__main__":
    raise SystemExit(main())
