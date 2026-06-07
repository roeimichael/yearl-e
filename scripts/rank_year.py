"""Score a year against its Cliopatria snapshot region-set.

Run: python scripts/rank_year.py 1719
Reads:
  data/raw/{year}_extract.json    (Maddison gdppc + Brecke conflicts)
  data/raw/{year}_wiki.json       (era summary, optional)
  data/region_sets/{snapshot}.json (Cliopatria polities w/ member_iso3)
Writes:
  data/year_scores/{year:04d}.json

## Model

Regions come from Cliopatria (Seshat) — real historical polities, year-keyed,
sampled at ~25-year snapshots. Each region already carries `member_iso3`
(modern countries it spatially overlaps), so scoring keys off that:

  - safety   → Brecke conflicts attributed by polity-name keywords (precise)
               + ISO3→Brecke macro-region code (coarse fallback)
  - economy  → Maddison gdppc of the best-covered member country, percentile-ranked
  - governance → V-Dem polyarchy (1789+) of best member, else neutral 50
  - health   → era baseline 45 (no per-polity manual layer yet)
  - religious_tolerance → neutral 50 (no global pre-modern source yet)

Overall = 0.30*safety + 0.20*governance + 0.20*economy + 0.15*health + 0.15*tolerance,
then normalized per-year so the year's worst region = 1, best = 100.
"""
from __future__ import annotations
import bisect
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

import factors
import maddison_lookup
import statehist_lookup
import vdem_lookup
from factors import ISO3_TO_BRECKE  # shared with the health/tolerance providers

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
REGION_SETS = ROOT / "data" / "region_sets"
YEAR_OUT = ROOT / "data" / "year_scores"

# ─── era → snapshot grid ─────────────────────────────────────────────────────
# Maps an era to (first_year, last_year, [snapshot years]). Each game-year is
# scored against the nearest snapshot's region-set. Snapshot files are named
# data/region_sets/{era}_{snapshot_year}.json. To add an era, build its
# snapshots with build_cliopatria_era.py then add a row here.
ERA_SNAPSHOTS: dict[str, tuple[int, int, list[int]]] = {
    "early_modern": (1500, 1815, list(range(1500, 1801, 25)) + [1815]),
    # Modern era: snapshots denser where borders move fast (WWI redraw, WW2,
    # decolonization, Soviet collapse). Cliopatria runs to 2024, so 2025/2026
    # bind to the 2024 snapshot.
    "modern": (1816, 2026, [1816, 1840, 1860, 1880, 1900, 1914, 1920, 1938,
                            1945, 1960, 1975, 1991, 2000, 2010, 2024]),
}


def snapshot_for(year: int) -> str:
    """Return the region-set name (e.g. 'early_modern_1700') whose snapshot year
    is nearest to `year`, within the era that covers it."""
    for era, (lo, hi, snaps) in ERA_SNAPSHOTS.items():
        if lo <= year <= hi:
            best = min(snaps, key=lambda s: abs(s - year))
            return f"{era}_{best}"
    raise ValueError(f"no era snapshot grid covers year {year}")


def load_region_set(set_name: str) -> list[dict]:
    """Read the region list from a snapshot file under data/region_sets/."""
    p = REGION_SETS / f"{set_name}.json"
    return json.loads(p.read_text(encoding="utf-8"))["regions"]


# Words to strip from a polity name before using the rest as conflict keywords.
NAME_STOP: frozenset[str] = frozenset({
    "empire", "kingdom", "sultanate", "dynasty", "khanate", "republic", "of",
    "the", "and", "confederation", "principality", "duchy", "states", "state",
    "lords", "grand", "new", "house", "colonial", "minor", "dutch", "monarchy",
    "shogunate", "reducciones", "commonwealth",
})


def name_keywords(name: str) -> list[str]:
    """Distinctive lowercase tokens (>3 chars, non-stopword) from a polity name,
    used to match conflicts to the polity by name."""
    toks = re.findall(r"[a-z]+", name.lower())
    return [t for t in toks if len(t) > 3 and t not in NAME_STOP]


def compute_safety(name: str, member_iso3: list[str], conflicts: list[dict]) -> tuple[int, list[str]]:
    """85 baseline minus conflict hits. Polity-name match = precise (full
    penalty). Brecke macro-region code match = coarse (light penalty), so wars
    don't bleed heavily across every region sharing a macro-region."""
    score = 85
    hits: list[str] = []
    codes = {ISO3_TO_BRECKE[i] for i in member_iso3 if i in ISO3_TO_BRECKE}
    kws = name_keywords(name)
    code_only = 0
    for c in conflicts:
        nm = (c.get("name") or "").lower()
        name_match = any(k in nm for k in kws)
        code_match = c.get("region_code") in codes
        if not (name_match or code_match):
            continue
        fatal = c.get("fatalities") or 0
        if name_match:
            score -= 25 if fatal > 50_000 else 12
            hits.append(c["name"])
        else:
            # coarse: cap how many code-only wars can drag a big multi-region
            # polity down, and penalize lightly.
            if code_only >= 6:
                continue
            code_only += 1
            score -= 8 if fatal > 50_000 else 4
    return max(score, 5), hits


# ─── economy from Maddison ───────────────────────────────────────────────────


def economy_estimate(members: list[str], year: int) -> tuple[float | None, str | None, str]:
    """A region's GDP/cap estimate for the year: real Maddison if any member
    country has a (interpolated) point, else the modeled macro-region baseline.
    Returns (value, real_iso_or_None, source) where source ∈ maddison|modeled|neutral."""
    iso, val = maddison_lookup.best_for(members, year)
    if val is not None:
        return val, iso, "maddison"
    bval = factors.economy_baseline(members)
    if bval is not None:
        return bval, None, "modeled"
    return None, None, "neutral"


def compute_economy(value: float | None, source: str,
                    sorted_values: list[float]) -> tuple[int, str]:
    """Percentile-rank a region's GDP/cap estimate against every region's estimate
    this year. value/source come from economy_estimate (real or modeled)."""
    if value is None:
        return 50, "neutral"
    n = len(sorted_values)
    if n < 2:
        return 50, source
    pct = sum(1 for v in sorted_values if v < value) / (n - 1)
    return round(25 + pct * 65), source


# ─── score one region ────────────────────────────────────────────────────────

CLIO_SOURCE = {
    "label": "Cliopatria (Seshat) — historical political boundaries, CC-BY 4.0",
    "url": "https://github.com/Seshat-Global-History-Databank/cliopatria",
}

# factor_source tags that rest on real measured data (not modeled/neutral). Used
# to compute per-cell data_quality / sparse_data honestly.
REAL_SOURCES = frozenset({"brecke", "ucdp", "lifeexp", "maddison", "vdem",
                          "vdem-relig", "statehist", "witch-trials"})

# Brecke's conflict catalog ends here; build_extracts switches to UCDP after it,
# so safety provenance is tagged accordingly (kept in sync with build_extracts).
BRECKE_LAST_YEAR = 1999


def score_region(year: int, region: dict, sorted_gdppc: list[float],
                 conflicts: list[dict], weights: dict[str, float]) -> dict:
    name = region["name"]
    members = region.get("member_iso3", [])

    safety, conflict_hits = compute_safety(name, members, conflicts)
    safety_src = "brecke" if year <= BRECKE_LAST_YEAR else "ucdp"
    econ_val, econ_iso, econ_est_src = economy_estimate(members, year)
    econ_score, econ_src = compute_economy(econ_val, econ_est_src, sorted_gdppc)

    # Governance: V-Dem electoral democracy from 1789; Statehist state-continuity
    # proxy before that; neutral only if neither has the territory.
    vdem_score, vdem_iso = vdem_lookup.governance(members, year)
    if vdem_score is not None:
        gov, gov_src, gov_iso = vdem_score, "vdem", vdem_iso
    else:
        sh_score, sh_iso = statehist_lookup.governance(members, year)
        if sh_score is not None:
            gov, gov_src, gov_iso = sh_score, "statehist", sh_iso
        else:
            gov, gov_src, gov_iso = 50, "neutral", None
    health, health_src = factors.health(members, year, len(conflict_hits), econ_score)
    # Religious tolerance: real V-Dem freedom-of-religion (1789+) where available,
    # else the era-aware modeled baseline minus witch-trial penalty (pre-1789).
    relig_v, relig_iso = vdem_lookup.religious_freedom(members, year)
    if relig_v is not None:
        relig, relig_src, witch_pen = relig_v, "vdem-relig", 0
    else:
        relig, relig_src, witch_pen = factors.tolerance(members, year)

    conflict_db = "UCDP" if year > BRECKE_LAST_YEAR else "Brecke"
    parts = []
    if conflict_hits:
        parts.append(f"Active conflicts in {year}: " + "; ".join(conflict_hits[:3]) + ".")
    else:
        parts.append(f"{conflict_db} records no major conflict touching {name} in {year} "
                     f"(safety at the era baseline of 85).")
    if econ_src == "maddison":
        parts.append(f"Maddison GDP/capita {econ_val:.0f} ({econ_iso}, {year}) — "
                     f"economy proxy for the territory.")
    elif econ_src == "modeled":
        parts.append(f"No direct Maddison point — economy modeled from the early-modern "
                     f"GDP/capita baseline for this macro-region (~{econ_val:.0f} 1990 int$).")
    else:
        parts.append("Economy held neutral (no economic geography mapped for this territory).")
    if gov_src == "vdem":
        label = ("highly autocratic" if gov < 15 else
                 "limited representation" if gov < 35 else
                 "early democratic" if gov < 60 else "broadly democratic")
        parts.append(f"V-Dem polyarchy {gov}/100 ({gov_iso}, {year}) — {label}.")
    elif gov_src == "statehist":
        label = ("fragmented / weak state" if gov < 35 else
                 "established state" if gov < 70 else "long-entrenched state")
        parts.append(f"State-continuity {gov}/100 ({gov_iso}) — {label} "
                     f"(pre-democracy governance proxy).")
    else:
        parts.append("Governance neutral (no state-history coverage for this territory).")
    if health_src == "lifeexp":
        parts.append(f"Health {health}/100, anchored on life-expectancy data for the region.")
    if relig_src == "vdem-relig":
        parts.append(f"Religious tolerance {relig}/100 — V-Dem freedom-of-religion "
                     f"({relig_iso}, {year}), measured.")
    elif witch_pen:
        parts.append(f"Religious tolerance {relig}/100 — lowered by recorded witch-trial "
                     f"persecution in this period.")
    else:
        parts.append(f"Religious tolerance {relig}/100 (modeled from the era's state-religion "
                     f"pattern for this region).")
    summary = " ".join(parts)

    overall = round(weights["safety"] * safety + weights["governance"] * gov +
                    weights["economy"] * econ_score + weights["health"] * health +
                    weights["religious_tolerance"] * relig)

    sources = [CLIO_SOURCE]
    if conflict_hits:
        if safety_src == "ucdp":
            sources.append({"label": "UCDP/PRIO Armed Conflict Dataset v25.1",
                            "url": "https://ucdp.uu.se/downloads/"})
        else:
            sources.append({"label": "Brecke Conflict Catalog 1400-2000",
                            "url": "https://brecke.inta.gatech.edu/research/conflict/"})
    if econ_src == "maddison":
        sources.append({
            "label": f"Maddison Project 2023 — {econ_iso} {year} gdppc={econ_val:.0f}",
            "url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
        })
    elif econ_src == "modeled":
        sources.append({
            "label": "Economy modeled from Maddison early-modern regional GDP/capita baseline",
            "url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
        })
    if gov_src == "vdem":
        sources.append({
            "label": f"V-Dem v15 — {gov_iso} {year} polyarchy={gov}",
            "url": "https://www.v-dem.net/data/the-v-dem-dataset/",
        })
    elif gov_src == "statehist":
        sources.append({
            "label": f"State Antiquity Index (Borcan-Olsson-Putterman) — {gov_iso}",
            "url": "https://sites.google.com/site/econolaols/extended-state-history-index",
        })
    if health_src == "lifeexp":
        sources.append({
            "label": "Our World in Data — life expectancy (Riley; Zijdeman; UN)",
            "url": "https://ourworldindata.org/life-expectancy",
        })
    if relig_src == "vdem-relig":
        sources.append({
            "label": f"V-Dem v15 — {relig_iso} {year} freedom of religion",
            "url": "https://www.v-dem.net/data/the-v-dem-dataset/",
        })
    elif witch_pen:
        sources.append({
            "label": "Leeson & Russ — Witch Trials database (Economic Journal 2018)",
            "url": "https://github.com/JakeRuss/witch-trials",
        })

    factor_sources = {
        "safety": safety_src,
        "health": health_src,
        "economy": econ_src,
        "governance": gov_src,
        "religious_tolerance": relig_src,
    }
    # Honest data quality: how many of the 5 factors rest on real measured data
    # (vs a modeled baseline / neutral fallback). 'sparse_data' now means the cell
    # genuinely leans on assumptions (≤2 real), not a blanket era flag.
    real_count = sum(1 for s in factor_sources.values() if s in REAL_SOURCES)

    return {
        "score": overall,
        "summary": summary,
        "factors": {
            "safety": safety,
            "health": health,
            "economy": econ_score,
            "governance": gov,
            "religious_tolerance": relig,
        },
        "factor_sources": factor_sources,
        "data_quality": real_count,
        "sources": sources,
        "ruler": None,
        "sparse_data": real_count <= 2,
        "wikidata": region.get("wikidata", ""),
    }


# Dynamic per-year weights. What makes a place "good to live" shifts with the
# world-state of the year: a violent year weights safety highest, an age of
# persecution weights tolerance highest, calmer years lean on prosperity/health.
# War/persecution are scored as ERA-PERCENTILES (so they vary year to year, not
# saturate — Brecke has active wars every year). The SAME weights apply to every
# region that year, so the within-year comparison stays fair.
# Base already favours peace + freedom (the "where would a person want to live"
# reading), which on its own spreads winners well beyond the European core.
BASE_WEIGHTS = {"safety": 0.28, "religious_tolerance": 0.24, "governance": 0.16,
                "economy": 0.16, "health": 0.16}  # sum 1.00
_EMPHASIS = {
    "safety": "a violent year — peace counted for most",
    "religious_tolerance": "an age of persecution — tolerance counted for most",
    "governance": "judged most by the reach of the state",
    "economy": "judged most by prosperity",
    "health": "judged most by health and survival",
}


def _war_raw(conflicts: list[dict]) -> int:
    return sum((c.get("fatalities") or 0) for c in conflicts)


def era_of(year: int) -> str | None:
    """Era name covering `year`, or None."""
    for era, (lo, hi, _) in ERA_SNAPSHOTS.items():
        if lo <= year <= hi:
            return era
    return None


def persecution_signal(year: int) -> float:
    """How persecutory the world was in `year` — real V-Dem global religious
    repression (1789+, 0–1) where available, else recorded witch-trial intensity
    (pre-1789). Compared only WITHIN an era (see _era_distributions) so the two
    sources never share a scale."""
    rep = vdem_lookup.global_repression(year)
    return rep if rep is not None else float(factors.persecution_level(year))


@lru_cache(maxsize=1)
def _era_distributions() -> dict[str, tuple[list[float], list[float]]]:
    """Per-era sorted (war, persecution) distributions. Percentiles are taken
    within an era so a violent/persecuting year is judged against its OWN era —
    avoiding the cross-era scale mismatch (Brecke vs UCDP fatalities; witch-trial
    counts vs V-Dem repression)."""
    tmp: dict[str, tuple[list[float], list[float]]] = {}
    for p in RAW.glob("*_extract.json"):
        try:
            yr = int(p.name.split("_")[0])
        except ValueError:
            continue
        era = era_of(yr)
        if era is None:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        wars, pers = tmp.setdefault(era, ([], []))
        wars.append(_war_raw(d.get("conflicts", [])))
        pers.append(persecution_signal(yr))
    return {era: (sorted(w), sorted(pr)) for era, (w, pr) in tmp.items()}


def _pct(val: float, sorted_vals: list[float]) -> float:
    if not sorted_vals:
        return 0.5
    return bisect.bisect_right(sorted_vals, val) / len(sorted_vals)


def year_weights(war_pct: float, pers_pct: float) -> tuple[dict[str, float], str]:
    """Return (normalized weights, human emphasis label) for the year, given the
    year's war/persecution era-percentiles (0–1)."""
    w = dict(BASE_WEIGHTS)
    w["safety"] += 0.22 * war_pct
    w["religious_tolerance"] += 0.22 * pers_pct
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    return w, _EMPHASIS[max(w, key=w.get)]


def rank(year: int, raw: dict, wiki: dict | None = None) -> dict:
    set_name = snapshot_for(year)
    regions = load_region_set(set_name)

    era_summary = wiki.get("summary", "") if wiki else ""

    dist_war, dist_pers = _era_distributions().get(era_of(year), ([], []))
    weights, emphasis = year_weights(
        _pct(_war_raw(raw["conflicts"]), dist_war),
        _pct(persecution_signal(year), dist_pers),
    )

    # Per-year economy percentile baseline: every region's GDP/cap estimate —
    # real Maddison (interpolated benchmarks: China/India/Japan/Ottoman/Mexico)
    # where available, else the modeled macro-region baseline — so the spread is
    # full and no region sits flat-neutral just because Maddison is silent.
    sorted_gdppc = sorted(
        v for r in regions
        if (v := economy_estimate(r.get("member_iso3", []), year)[0]) is not None
    )

    out_regions = {}
    for r in regions:
        out_regions[r["id"]] = score_region(year, r, sorted_gdppc, raw["conflicts"], weights)

    # Normalize overall per year: worst region -> 1, best -> 100. Keeps ranking
    # legible when raw composites cluster in a narrow band.
    if out_regions:
        raws = [r["score"] for r in out_regions.values()]
        rmin, rmax = min(raws), max(raws)
        spread = rmax - rmin
        for r in out_regions.values():
            r["raw_score"] = r["score"]
            r["score"] = round(1 + 99 * (r["score"] - rmin) / spread) if spread > 0 else 50

    return {
        "year": year,
        "label": f"{year} CE",
        "region_set": set_name,
        "era_summary": era_summary,
        "weights": {k: round(v, 3) for k, v in weights.items()},
        "emphasis": emphasis,
        "regions": out_regions,
    }


def build_year_file(year: int) -> Path | None:
    """Score one year and write its data/year_scores/{year}.json. Returns the
    path, or None if the raw extract is missing. Reusable in-process (loaders
    are lru-cached) so bulk re-scoring all years stays a single process."""
    raw_path = RAW / f"{year}_extract.json"
    if not raw_path.exists():
        return None
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    wiki_path = RAW / f"{year}_wiki.json"
    wiki = json.loads(wiki_path.read_text(encoding="utf-8")) if wiki_path.exists() else None
    out = rank(year, raw, wiki)
    if wiki and wiki.get("url"):
        wiki_src = {"label": f"Wikipedia — {year}", "url": wiki["url"]}
        for cell in out["regions"].values():
            cell.setdefault("sources", []).append(wiki_src)
    YEAR_OUT.mkdir(parents=True, exist_ok=True)
    out_path = YEAR_OUT / f"{year:04d}.json"
    # newline="\n": keep LF on every platform so re-runs match the committed data
    # byte-for-byte (Windows would otherwise rewrite all files with CRLF).
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                        encoding="utf-8", newline="\n")
    return out_path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/rank_year.py <year>", file=sys.stderr)
        return 2
    year = int(sys.argv[1])
    out_path = build_year_file(year)
    if out_path is None:
        print(f"missing {RAW / f'{year}_extract.json'}; run scripts/fetch_year.py {year} first",
              file=sys.stderr)
        return 1
    print(f"wrote {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
