"""Convert raw extract (Maddison + Brecke) + manual context into a scored year file.

Run: python scripts/rank_year.py 1719
Reads:
  data/raw/{year}_extract.json
  data/region_groupings/{set}.py  (era-keyed manual context)
  data/region_sets/{set}.json     (built polygons, for region IDs)
Writes:
  data/year_scores/{year:04d}.json

## Strict source policy

Every factor declares its source in `factor_sources`:
  - safety       → "brecke" (always, derived from Brecke Conflict Catalog)
  - economy      → "maddison" if Maddison has a member-country GDP/cap, else "neutral"
  - governance   → "wiki" if region has Wikipedia citations, else "neutral"
  - health       → "baseline" (era baseline + manual adj) or "neutral"
  - religious_tolerance → "wiki" or "neutral"

If a region's MANUAL_1719 entry sets `sparse_data: True` (or is missing),
its 3 manual factors are held at neutral 50 and a warning summary is set.

Overall = 0.30*safety + 0.20*governance + 0.20*economy + 0.15*health + 0.15*religious_tolerance
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import vdem_lookup

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "year_scores"

# Year → region set resolver. Add new eras here as polygon sets ship.
# Range-based so we don't have to enumerate every year.
ERA_RANGES = [
    (1500, 1815, "early_modern"),
    # (1815, 1945, "industrial"),
    # (1945, 2100, "modern"),
]


def year_to_set(year: int) -> str:
    for lo, hi, name in ERA_RANGES:
        if lo <= year <= hi:
            return name
    raise ValueError(f"no region set covers year {year}")


def load_grouping(set_name: str) -> dict:
    """Era-keyed grouping. Plain JSON — never exec arbitrary code from disk."""
    p = ROOT / "data" / "region_groupings" / f"{set_name}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_region_set_meta(set_name: str) -> dict[str, dict]:
    p = ROOT / "data" / "region_sets" / f"{set_name}.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {r["id"]: r for r in raw["regions"]}


# ─── safety from Brecke ──────────────────────────────────────────────────────

# Brecke `Region` codes → our region_ids (multiple matches OK). Per Brecke
# codebook: 1=British Isles, 2=W Europe, 3=Central Europe, 4=E Europe,
# 5=Middle East, 6=N Africa, 7=Sub-Saharan, 8=South Asia, 9=SE Asia,
# 10=East Asia, 11=Oceania, 12=Central Asia, 13=Latin America, 14=N America.
BRECKE_REGION_TO_OURS = {
    1: ["england"],
    2: ["francia", "andalusia_iberia"],
    3: ["habsburg_austria", "prussia_brandenburg", "german_princes", "rome_italy"],
    4: ["rus", "polish_lithuanian_commonwealth", "swedish_baltic", "constantinople_balkans"],
    5: ["persia", "egypt_nile", "arabia", "constantinople_balkans"],
    6: ["egypt_nile", "sahel_interior"],
    7: ["asante_coast", "sahel_interior", "ethiopia", "kongo_angola", "southern_africa"],
    8: ["mughal_north", "maratha_confederacy", "bengal", "deccan_sultanates"],
    9: ["siam_vietnam_burma", "voc_indonesia", "spanish_philippines"],
    10: ["han_china", "japan"],
    11: [],
    12: ["central_asia"],
    13: ["new_spain", "andes", "brazil_amazon", "caribbean"],
    14: ["north_america_east"],
}

# Lower-cased substrings to scan conflict names for. Catches Brecke entries
# whose `Region` code is ambiguous but whose name contains a clear keyword.
REGION_KEYWORDS = {
    "rome_italy": ["italy", "naples", "sicily", "venice", "sardinia", "papal"],
    "andalusia_iberia": ["spain", "portugal", "iberia"],
    "francia": ["france", "holland", "netherlands", "united provinces", "low countries", "belgium"],
    "england": ["britain", "england", "scotland", "ireland", "british"],
    "habsburg_austria": ["austria", "habsburg", "hungary", "bohemia"],
    "prussia_brandenburg": ["prussia", "brandenburg"],
    "german_princes": ["saxony", "hanover", "bavaria", "germany"],
    "polish_lithuanian_commonwealth": ["poland", "lithuania", "polish"],
    "sweden_empire": ["sweden", "swedish", "finland"],
    "denmark_norway": ["denmark", "danish", "norway"],
    "swedish_baltic": ["livonia", "estonia", "ingria"],
    "rus": ["russia", "russian", "ukraine", "cossack", "muscovy"],
    "constantinople_balkans": ["turkey", "ottoman", "balkans", "anatolia"],
    "persia": ["persia", "afghanistan", "iran", "safavid", "hotaki"],
    "egypt_nile": ["egypt", "levant", "syria"],
    "arabia": ["arabia", "oman", "mecca", "hejaz", "yemen"],
    "ethiopia": ["ethiopia", "abyssinia"],
    "central_asia": ["khiva", "bukhara", "junghar", "khanate"],
    "mughal_north": ["mughal", "delhi"],
    "maratha_confederacy": ["maratha", "shahu"],
    "bengal": ["bengal"],
    "deccan_sultanates": ["deccan", "hyderabad", "mysore"],
    "han_china": ["china", "qing", "kangxi", "tibet"],
    "japan": ["japan", "korea"],
    "voc_indonesia": ["java", "batavia", "voc", "indonesia"],
    "siam_vietnam_burma": ["siam", "vietnam", "burma", "ayutthaya"],
    "spanish_philippines": ["philippines", "manila"],
    "asante_coast": ["asante", "gold coast", "dahomey", "gambia"],
    "sahel_interior": ["mali", "songhai", "bambara", "hausa"],
    "kongo_angola": ["kongo", "angola", "kakonda"],
    "southern_africa": ["lunda", "cape", "mozambique"],
    "new_spain": ["mexico", "new spain"],
    "caribbean": ["caribbean", "jamaica", "cuba", "saint-domingue", "pirate"],
    "andes": ["peru", "andes", "inca", "chile"],
    "brazil_amazon": ["brazil", "portuguese america"],
    "north_america_east": ["new england", "virginia", "carolina", "massachusetts"],
}


def compute_safety(region_id: str, conflicts: list[dict]) -> tuple[int, list[str]]:
    """Score 85 baseline minus conflict hits. Name keywords are primary signal;
    Brecke region_code is fallback only when the region has no keyword list, or
    when no other region's name matches (ambiguous code-only attribution to
    multi-region codes used to bleed wars into wrong neighbours)."""
    score = 85
    hits = []
    keywords = REGION_KEYWORDS.get(region_id, [])
    for c in conflicts:
        rcode = c.get("region_code")
        ours = BRECKE_REGION_TO_OURS.get(rcode, [])
        name_lower = (c.get("name") or "").lower()
        name_match = any(k in name_lower for k in keywords)
        code_match = region_id in ours
        if not (name_match or code_match):
            continue
        # If we have keywords and the name doesn't mention us, only trust the
        # code attribution when it points to one region (specific). When code
        # maps to many regions and name says nothing about us — skip.
        if keywords and code_match and not name_match and len(ours) > 1:
            continue
        hits.append(c["name"])
        fatal = c.get("fatalities") or 0
        score -= 25 if fatal > 50_000 else 12
    return max(score, 5), hits


# ─── economy from Maddison ───────────────────────────────────────────────────

# Multi-ISO3 → region. NB: Maddison's coverage is sparse for 1719 (only 11
# countries have a number). Most regions get "neutral" for economy.
# We thread Maddison through the agent's REGION_MEMBERS instead of hardcoding —
# this keeps the mapping single-source-of-truth.
def compute_economy(region_id: str, members_iso3: list[str],
                    raw_gdppc: dict, sorted_values: list[float]) -> tuple[int, str | None, float | None, str | None]:
    """Return (score, source_iso, gdppc_used, factor_source_key)."""
    best_iso, best_val = None, -1.0
    for iso in members_iso3:
        v = raw_gdppc.get(iso)
        if v and v["gdppc"] > best_val:
            best_iso, best_val = iso, v["gdppc"]
    if best_iso is None:
        return 50, None, None, "neutral"
    n = len(sorted_values)
    if n < 2:
        # With one datapoint a percentile is meaningless — fall to neutral mid.
        return 50, best_iso, best_val, "maddison"
    pct = sum(1 for v in sorted_values if v < best_val) / (n - 1)
    return round(25 + pct * 65), best_iso, best_val, "maddison"


# ─── score one region ────────────────────────────────────────────────────────


def score_region(year: int, region_id: str, members_iso3: list[str], manual: dict,
                 raw_gdppc: dict, sorted_gdppc: list[float], conflicts: list[dict]) -> dict:
    safety, conflict_hits = compute_safety(region_id, conflicts)
    econ_score, econ_iso, econ_val, econ_src = compute_economy(
        region_id, members_iso3, raw_gdppc, sorted_gdppc
    )

    # V-Dem governance (1789+ only) — best-scored member country.
    vdem_score, vdem_iso = vdem_lookup.governance(members_iso3, year)

    sparse = manual.get("sparse_data", False) or not manual.get("sources")
    if sparse:
        if vdem_score is not None:
            gov = vdem_score
            gov_src = "vdem"
        else:
            gov = 50
            gov_src = "neutral"
        relig = 50
        health = 45
        relig_src = "neutral"
        health_src = "baseline"
        # Build educational prose explaining WHAT the data shows and what's
        # neutral-by-absence. Every year reads differently because Brecke,
        # Maddison and V-Dem all change year-to-year.
        parts = []
        if conflict_hits:
            parts.append(f"Active conflicts in {year}: " + "; ".join(conflict_hits[:3]) + ".")
        else:
            parts.append(f"Brecke records no major conflicts touching this region in {year} "
                         f"(safety scored at the era baseline of 85).")
        if econ_iso:
            parts.append(f"Maddison records GDP/capita {econ_val:.0f} ({econ_iso}, {year}) — "
                         f"used as the economy proxy for the whole region.")
        else:
            parts.append("No Maddison GDP coverage for this region — economy held at neutral 50, "
                         "reflecting the thin pre-modern record outside the European core.")
        if vdem_score is not None:
            label = "highly autocratic" if vdem_score < 15 else (
                    "limited representation" if vdem_score < 35 else (
                    "early democratic" if vdem_score < 60 else "broadly democratic"))
            parts.append(f"V-Dem polyarchy {vdem_score}/100 ({vdem_iso}, {year}) — {label}.")
        else:
            parts.append("Governance held at neutral (V-Dem coverage starts 1789).")
        summary = " ".join(parts)
    else:
        # If a manual field is missing, fall to neutral 50 AND tag its source
        # as "neutral" — never claim a wiki citation for a default value.
        gov = manual.get("governance", 50)
        gov_src = "wiki" if "governance" in manual else "neutral"
        relig = manual.get("religious_tolerance", 50)
        relig_src = "wiki" if "religious_tolerance" in manual else "neutral"
        health = max(0, min(100, 45 + manual.get("health_adj", 0)))
        health_src = "baseline"
        bits = []
        if manual.get("governance_note"):
            bits.append(manual["governance_note"])
        if conflict_hits:
            bits.append("Active conflicts: " + "; ".join(conflict_hits[:3]))
        if manual.get("religion_note"):
            bits.append("Religion: " + manual["religion_note"])
        joined = " ".join(bits)
        # Truncate cleanly on word boundary rather than mid-word.
        summary = joined if len(joined) <= 700 else joined[:700].rsplit(" ", 1)[0] + "…"

    overall = round(0.30 * safety + 0.20 * gov + 0.20 * econ_score +
                    0.15 * health + 0.15 * relig)

    sources = list(manual.get("sources", []))
    if conflict_hits:
        sources.append({"label": "Brecke Conflict Catalog 1400-2000", "url": "https://brecke.inta.gatech.edu/research/conflict/"})
    if econ_iso:
        sources.append({
            "label": f"Maddison Project 2023 — {econ_iso} {year} gdppc={econ_val:.0f}",
            "url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
        })
    if vdem_score is not None and gov_src == "vdem":
        sources.append({
            "label": f"V-Dem v15 — {vdem_iso} {year} polyarchy={vdem_score}",
            "url": "https://www.v-dem.net/data/the-v-dem-dataset/",
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
        "ruler": manual.get("ruler"),
        "sparse_data": sparse,
    }


def rank(year: int, raw: dict, wiki: dict | None = None) -> dict:
    set_name = year_to_set(year)
    grouping = load_grouping(set_name)
    region_meta = load_region_set_meta(set_name)
    # The grouping JSON holds a single manual_{year} dict per known year; we
    # look it up by the year being ranked so new years can be added without
    # touching this file.
    manual_dict = grouping.get(f"manual_{year}", {})
    era_summary = grouping.get(f"era_summary_{year}", "")
    # If we don't have a hand-written era summary for this year, fall back to
    # the Wikipedia year article's lead paragraph — keeps it year-specific.
    if not era_summary and wiki:
        era_summary = wiki.get("summary", "")

    members = grouping["region_members"]
    # Maddison: collect numbers for percentile across all ISOs that map to any of our regions.
    used_isos = {iso for isos in members.values() for iso in isos}
    sorted_gdppc = sorted(v["gdppc"] for iso, v in raw["gdppc"].items() if iso in used_isos)

    out_regions = {}
    for rid in members:
        if rid not in region_meta:
            print(f"  [skip] {rid}: not in {set_name}.json (NE missing all members)")
            continue
        out_regions[rid] = score_region(
            year,
            rid,
            members[rid],
            manual_dict.get(rid, {}),
            raw["gdppc"],
            sorted_gdppc,
            raw["conflicts"],
        )

    # Normalize the overall score per year so the worst region of the year is
    # 1 and the best is 100. Without this, sparse-data years cluster every
    # region in a narrow band (50–65) and ranking-vs-score feels disconnected.
    # We keep the raw composite as `raw_score` for transparency.
    if out_regions:
        raws = [r["score"] for r in out_regions.values()]
        rmin, rmax = min(raws), max(raws)
        spread = rmax - rmin
        for r in out_regions.values():
            r["raw_score"] = r["score"]
            if spread > 0:
                r["score"] = round(1 + 99 * (r["score"] - rmin) / spread)
            else:
                r["score"] = 50

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
    # Cite the Wikipedia year article on every region whose summary came from it.
    if wiki and wiki.get("url"):
        wiki_src = {"label": f"Wikipedia — {year}", "url": wiki["url"]}
        for cell in out["regions"].values():
            cell.setdefault("sources", []).append(wiki_src)
    out_path = OUT_DIR / f"{year:04d}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB, {len(out['regions'])} regions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
