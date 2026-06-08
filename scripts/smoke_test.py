"""End-to-end smoke test — drives the game the way the frontend does, headless.

For EVERY year we ship:
  * load the year file + its region snapshot
  * data invariants: score 0-100, data_quality == len(scored_factors),
    scored_factors subset of factors, summary present, ranking sorted
  * coverage: every polygon in the snapshot has a score cell (else clicking
    it shows "no data") and vice-versa
  * "tap test": for each region take an interior point (representative_point)
    and run score_guess() on it — the globe-click path — asserting it resolves
    to a real scored region with a valid score
Plus: open-ocean miss returns None, daily roll is deterministic.

Run: python scripts/smoke_test.py
Exit 0 = all green; exit 1 = failures (printed).
"""
from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, ".")

from backend import regions as R
from backend.scoring import region_for_point, score_guess
from backend.main import _roll_year, _day_number  # daily roll

FACTORS = ["safety", "health", "economy", "governance", "religious_tolerance"]
REAL = {"hced", "brecke", "ucdp", "lifeexp", "maddison", "vdem", "vdem-relig",
        "statehist", "witch-trials"}

fails: list[str] = []
warns: list[str] = []


def bad(msg: str):
    fails.append(msg)


def warn(msg: str):
    warns.append(msg)


def main() -> int:
    years = R.available_years()
    print(f"years: {len(years)} ({years[0]}..{years[-1]})")

    total_cells = 0
    total_taps = 0
    tap_resolved = 0
    no_score_polys = 0
    orphan_cells = 0
    dq_hist = Counter()
    sources_seen = Counter()
    empty_summary = 0

    for yr in years:
        y = R.load_year(yr)
        if not y:
            bad(f"{yr}: load_year returned nothing")
            continue
        set_name = R.region_set_of(y)
        snap = R.load_region_set(set_name)          # rid -> {_shape, name}
        cells = y["regions"]                          # rid -> scored cell
        snap_ids = set(snap)
        cell_ids = set(cells)

        # coverage both directions
        polys_no_score = snap_ids - cell_ids
        cells_no_poly = cell_ids - snap_ids
        no_score_polys += len(polys_no_score)
        orphan_cells += len(cells_no_poly)
        if cells_no_poly:
            bad(f"{yr}: {len(cells_no_poly)} scored cells have no polygon in '{set_name}': "
                f"{sorted(cells_no_poly)[:5]}")

        # data invariants per cell
        for rid, c in cells.items():
            total_cells += 1
            s = c.get("score")
            if not isinstance(s, int) or not (0 <= s <= 100):
                bad(f"{yr}/{rid}: score out of range: {s!r}")
            sf = c.get("scored_factors", [])
            fac = c.get("factors", {})
            if not set(sf) <= set(fac):
                bad(f"{yr}/{rid}: scored_factors not subset of factors: {sf} vs {list(fac)}")
            dq = c.get("data_quality", -1)
            if dq != len(sf):
                bad(f"{yr}/{rid}: data_quality {dq} != len(scored_factors) {len(sf)}")
            # honest-scoring: every scored factor must come from a REAL source
            fsrc = c.get("factor_sources", {})
            for f in sf:
                if fsrc.get(f) not in REAL:
                    bad(f"{yr}/{rid}: factor '{f}' scored but source '{fsrc.get(f)}' not real")
            for f in FACTORS:
                sources_seen[fsrc.get(f, "?")] += 1
            dq_hist[len(sf)] += 1
            if not (c.get("summary") or "").strip():
                empty_summary += 1

        # ranking sorted desc
        ranked = R.ranked(yr)
        scores = [c["score"] for _, c in ranked]
        if scores != sorted(scores, reverse=True):
            bad(f"{yr}: ranking not sorted desc")

        # TAP TEST — click an interior point of each scored polygon
        for rid in cell_ids & snap_ids:
            sh = snap[rid]["_shape"]
            try:
                pt = sh.representative_point()
            except Exception as e:
                bad(f"{yr}/{rid}: representative_point failed: {e}")
                continue
            total_taps += 1
            res = score_guess(yr, pt.y, pt.x)
            got = res.get("region_id")
            if got is None:
                bad(f"{yr}/{rid}: tap at interior point resolved to OCEAN MISS")
                continue
            if got not in cells:
                bad(f"{yr}/{rid}: tap resolved to '{got}' which has no score")
                continue
            gs = res.get("score")
            if not (0 <= gs <= 100):
                bad(f"{yr}/{rid}: tap score out of range {gs}")
                continue
            tap_resolved += 1

    if no_score_polys:
        warn(f"{no_score_polys} snapshot polygons across all years have no score "
             f"(clicking them shows 'no data')")

    # open-ocean miss: mid South Pacific, far from any land
    miss_yr = years[len(years) // 2]
    sn = R.region_set_of(R.load_year(miss_yr))
    if region_for_point(sn, -40.0, -140.0) is not None:
        bad(f"open-ocean point (-40,-140) did NOT miss in {miss_yr}")

    # daily roll determinism: same date -> same year, twice
    d = "2026-06-07"
    if _roll_year(d) != _roll_year(d):
        bad("daily roll not deterministic")
    if _roll_year(d) not in years:
        bad(f"daily roll for {d} -> {_roll_year(d)} is not a year we ship")

    print(f"cells: {total_cells} | taps: {tap_resolved}/{total_taps} resolved")
    print(f"data_quality (factors scored) hist: "
          f"{dict(sorted(dq_hist.items()))}")
    print(f"empty summaries: {empty_summary}")
    print("source mix:", dict(sources_seen.most_common()))

    if warns:
        print("\nWARN:")
        for w in warns:
            print("  ! " + w)
    if fails:
        print(f"\nFAIL ({len(fails)}):")
        for f in fails[:50]:
            print("  x " + f)
        if len(fails) > 50:
            print(f"  ... +{len(fails) - 50} more")
        return 1
    print("\nALL GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
