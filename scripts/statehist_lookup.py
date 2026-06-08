"""Pre-1789 governance proxy from the Extended State History Index (Statehist).

V-Dem's electoral-democracy index only starts in 1789, leaving the whole
1500–1788 stretch with no governance signal (every region neutral 50). The
State Antiquity Index (Borcan, Olsson & Putterman v4.0, 3500 BCE–2000 CE) scores,
per modern-country territory in 50-year bins, how established/autonomous/
territorially-complete the state was (0–50). We use it as a "state continuity /
capacity" proxy for governance BEFORE democracy data exists — more organized
state vs fragmentation. Mapped 0–50 → 0–100.

NOTE: this measures state *presence*, not democracy — so it rewards long-lived
empires (China, Ottoman, Mughal, Persia). That is the intended pre-modern reading
(order over anarchy) and is labelled honestly as 'statehist' in factor_sources.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATEHIST = ROOT / "data" / "raw" / "statehist.xlsx"


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[int, float]]:
    """iso3 -> {period_end_year: state-antiquity score 0-50}.

    The summary sheet is a contiguous block of 50-year bins running back from
    1951-2000. We map them POSITIONALLY — the first range column = period-end
    2000, each next column −50 — so the BCE half is exposed too. (Its labels
    switch to ascending BCE ranges, e.g. '451-500' = 500-451 BCE; a label parser
    misreads those and stops at the CE↔BCE duplicate, which is why governance
    used to cut off at 1 CE.) Spans ~3450 BCE → 2000 CE."""
    import openpyxl
    import re
    wb = openpyxl.load_workbook(STATEHIST, read_only=True, data_only=True)
    rows = list(wb["statehist summary"].iter_rows(values_only=True))
    labels = rows[0]
    period_re = re.compile(r"^\s*\d+\s*-\s*\d+\s*$")
    period_cols = [i for i, lab in enumerate(labels)
                   if isinstance(lab, str) and period_re.match(lab)]
    # contiguous 50-year bins, newest first: col k → period-end 2000 − 50k
    col_end = {col: 2000 - 50 * k for k, col in enumerate(period_cols)}
    out: dict[str, dict[int, float]] = {}
    for r in rows[2:]:
        iso = r[0]
        if not iso or len(str(iso)) != 3:
            continue
        out[iso] = {end: float(r[i]) for i, end in col_end.items()
                    if i < len(r) and isinstance(r[i], (int, float))}
    return out


def _score(iso3: str, year: int) -> float | None:
    period_end = ((year - 1) // 50) * 50 + 50   # 1719 -> 1750, 1700 -> 1700
    v = _table().get(iso3, {}).get(period_end)
    return None if v is None else max(0.0, min(100.0, v * 2.0))


def governance(member_iso3: list[str], year: int) -> tuple[int | None, str | None]:
    """Best (most-established-state) member's score, 0-100, or (None, None)."""
    best, best_iso = None, None
    for iso in member_iso3:
        v = _score(iso, year)
        if v is not None and (best is None or v > best):
            best, best_iso = v, iso
    return (round(best), best_iso) if best is not None else (None, None)
