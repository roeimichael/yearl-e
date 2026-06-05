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
import json
import re
import sys
from pathlib import Path

import factors
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


def compute_economy(member_iso3: list[str], raw_gdppc: dict,
                    sorted_values: list[float]) -> tuple[int, str | None, float | None, str]:
    best_iso, best_val = None, -1.0
    for iso in member_iso3:
        v = raw_gdppc.get(iso)
        if v and v["gdppc"] > best_val:
            best_iso, best_val = iso, v["gdppc"]
    if best_iso is None:
        return 50, None, None, "neutral"
    n = len(sorted_values)
    if n < 2:
        return 50, best_iso, best_val, "maddison"
    pct = sum(1 for v in sorted_values if v < best_val) / (n - 1)
    return round(25 + pct * 65), best_iso, best_val, "maddison"


# ─── score one region ────────────────────────────────────────────────────────

CLIO_SOURCE = {
    "label": "Cliopatria (Seshat) — historical political boundaries, CC-BY 4.0",
    "url": "https://github.com/Seshat-Global-History-Databank/cliopatria",
}


def score_region(year: int, region: dict, raw_gdppc: dict,
                 sorted_gdppc: list[float], conflicts: list[dict]) -> dict:
    name = region["name"]
    members = region.get("member_iso3", [])

    safety, conflict_hits = compute_safety(name, members, conflicts)
    econ_score, econ_iso, econ_val, econ_src = compute_economy(members, raw_gdppc, sorted_gdppc)
    vdem_score, vdem_iso = vdem_lookup.governance(members, year)

    if vdem_score is not None:
        gov, gov_src = vdem_score, "vdem"
    else:
        gov, gov_src = 50, "neutral"
    health, health_src = factors.health(members, year, len(conflict_hits), econ_score)
    relig, relig_src, witch_pen = factors.tolerance(members, year)

    parts = []
    if conflict_hits:
        parts.append(f"Active conflicts in {year}: " + "; ".join(conflict_hits[:3]) + ".")
    else:
        parts.append(f"Brecke records no major conflict touching {name} in {year} "
                     f"(safety at the era baseline of 85).")
    if econ_iso:
        parts.append(f"Maddison GDP/capita {econ_val:.0f} ({econ_iso}, {year}) — "
                     f"economy proxy for the territory.")
    else:
        parts.append("No Maddison GDP coverage — economy held neutral, reflecting the "
                     "thin pre-modern record outside the European core.")
    if vdem_score is not None:
        label = ("highly autocratic" if vdem_score < 15 else
                 "limited representation" if vdem_score < 35 else
                 "early democratic" if vdem_score < 60 else "broadly democratic")
        parts.append(f"V-Dem polyarchy {vdem_score}/100 ({vdem_iso}, {year}) — {label}.")
    else:
        parts.append("Governance neutral (V-Dem coverage starts 1789).")
    if health_src == "lifeexp":
        parts.append(f"Health {health}/100, anchored on life-expectancy data for the region.")
    if witch_pen:
        parts.append(f"Religious tolerance {relig}/100 — lowered by recorded witch-trial "
                     f"persecution in this period.")
    else:
        parts.append(f"Religious tolerance {relig}/100 (modeled from the era's state-religion "
                     f"pattern for this region).")
    summary = " ".join(parts)

    overall = round(0.30 * safety + 0.20 * gov + 0.20 * econ_score +
                    0.15 * health + 0.15 * relig)

    sources = [CLIO_SOURCE]
    if conflict_hits:
        sources.append({"label": "Brecke Conflict Catalog 1400-2000",
                        "url": "https://brecke.inta.gatech.edu/research/conflict/"})
    if econ_iso:
        sources.append({
            "label": f"Maddison Project 2023 — {econ_iso} {year} gdppc={econ_val:.0f}",
            "url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
        })
    if gov_src == "vdem":
        sources.append({
            "label": f"V-Dem v15 — {vdem_iso} {year} polyarchy={vdem_score}",
            "url": "https://www.v-dem.net/data/the-v-dem-dataset/",
        })
    if health_src == "lifeexp":
        sources.append({
            "label": "Our World in Data — life expectancy (Riley; Zijdeman; UN)",
            "url": "https://ourworldindata.org/life-expectancy",
        })
    if witch_pen:
        sources.append({
            "label": "Leeson & Russ — Witch Trials database (Economic Journal 2018)",
            "url": "https://github.com/JakeRuss/witch-trials",
        })

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
        "factor_sources": {
            "safety": "brecke",
            "health": health_src,
            "economy": econ_src,
            "governance": gov_src,
            "religious_tolerance": relig_src,
        },
        "sources": sources,
        "ruler": None,
        "sparse_data": True,
        "wikidata": region.get("wikidata", ""),
    }


def rank(year: int, raw: dict, wiki: dict | None = None) -> dict:
    set_name = snapshot_for(year)
    regions = load_region_set(set_name)

    era_summary = wiki.get("summary", "") if wiki else ""

    used_isos = {iso for r in regions for iso in r.get("member_iso3", [])}
    sorted_gdppc = sorted(v["gdppc"] for iso, v in raw["gdppc"].items() if iso in used_isos)

    out_regions = {}
    for r in regions:
        out_regions[r["id"]] = score_region(
            year, r, raw["gdppc"], sorted_gdppc, raw["conflicts"])

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
        "regions": out_regions,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/rank_year.py <year>", file=sys.stderr)
        return 2
    year = int(sys.argv[1])
    raw_path = RAW / f"{year}_extract.json"
    if not raw_path.exists():
        print(f"missing {raw_path}; run scripts/fetch_year.py {year} first", file=sys.stderr)
        return 1
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
    print(f"wrote {out_path.name} ({out_path.stat().st_size/1024:.1f} KB, {len(out['regions'])} regions, set={out['region_set']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
