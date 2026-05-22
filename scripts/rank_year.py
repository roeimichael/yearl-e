"""Convert raw extract (Maddison + Brecke) + manual context into a scored year file.

Run: python scripts/rank_year.py 1719
Reads:   data/raw/{year}_extract.json
Writes:  data/year_scores/{year:04d}.json

## Ranking formula

Each region gets 5 factor scores in [0, 100], then a weighted overall:

  overall = 0.30*safety + 0.20*governance + 0.20*economy
          + 0.15*health + 0.15*religious_tolerance

### safety
- Start 85.
- For each Brecke conflict active in this year whose region_code or
  region_hits includes this region: subtract 12 (or 25 if fatalities > 50k).
- Floor at 5 if the region was a primary belligerent in a >100k-fatality war.

### economy
- If Maddison gdppc available: linear scale across the year's distribution.
  Use percentile within that year, then map to [25, 90].
- If missing: pull manual_econ (0-100 hand estimate) or fall back to 50.

### governance
- 100% manual (this year, this region). 0-100, with notes.

### health
- Era baseline 45 (pre-industrial). +/- manual adjustments per region this year
  (e.g. plague outbreak, famine, exceptional sanitation).

### religious_tolerance
- 100% manual. Era + region specific.

Every factor cites the source of its number in `sources[]` per region.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "year_scores"

REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]
REGION_IDS = [r["id"] for r in REGIONS]

# Maddison ISO3 → our region_id. Multiple ISOs can map to one region.
MADDISON_TO_REGION = {
    "ITA": "rome_italy",
    "CHN": "han_china",
    "IND": "gupta_india",
    "IRN": "persia",
    "EGY": "egypt_nile",
    "TUR": "constantinople_balkans",
    "ESP": "andalusia_iberia",
    "PRT": "andalusia_iberia",
    "FRA": "francia",
    "GBR": "england",
    "SWE": "scandinavia",
    "DNK": "scandinavia",
    "NOR": "scandinavia",
    "FIN": "scandinavia",
    "RUS": "rus",
    "JPN": "japan",
    "MEX": "mesoamerica",
    "PER": "andes",
    "ETH": "ethiopia",
    "DEU": "francia",   # German lands not their own region; lump with francia (loose)
    "NLD": "francia",   # likewise — see overrides in 1719 if needed
}

# Brecke `Region` codes (per their codebook): rough mapping to our region_ids.
# 1=British Isles, 2=Western Europe, 3=Central Europe, 4=Eastern Europe,
# 5=Middle East, 6=North Africa, 7=Sub-Saharan Africa, 8=South Asia,
# 9=Southeast Asia, 10=East Asia, 11=Oceania, 12=Central Asia, 13=Latin America,
# 14=North America. (Approximate — Brecke's docs are sparse.)
BRECKE_REGION_TO_OURS = {
    1: ["england"],
    2: ["francia", "andalusia_iberia"],
    3: ["francia", "rome_italy"],   # central europe spans both loosely
    4: ["rus", "constantinople_balkans", "scandinavia"],
    5: ["persia", "egypt_nile", "constantinople_balkans"],
    6: ["egypt_nile", "sahel_west_africa"],
    7: ["sahel_west_africa", "ethiopia"],
    8: ["gupta_india"],
    9: [],
    10: ["han_china", "japan"],
    11: [],
    12: ["central_asia"],
    13: ["mesoamerica", "andes"],
    14: ["north_america_east"],
}


# ─── 1719 manual context ─────────────────────────────────────────────────────
# Per-region facts that aren't in datasets. Each is sourced. Keys must align
# with REGION_IDS. Numbers are hand-set with reasoning in `note`.

MANUAL_1719 = {
    "rome_italy": {
        "governance": 55,
        "health_adj": 0,
        "religious_tolerance": 40,
        "governance_note": "Fragmented: Papal States, Venice (post-Karlowitz peace), Savoy, Spanish then Austrian Naples (Treaty of London 1718 transferred Sicily/Sardinia). No unified leadership.",
        "religion_note": "Inquisition still active in many states; Jewish ghettos enforced.",
        "ruler": "Pope Clement XI; multiple secular rulers",
        "sources": [
            {"label": "Treaty of London 1718 (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Treaty_of_London_(1718)"}
        ],
    },
    "han_china": {
        "governance": 85,
        "health_adj": 5,
        "religious_tolerance": 55,
        "governance_note": "Kangxi Emperor's final years (d. 1722). Stable centralized rule, mature bureaucracy, peaceful interior. Tibet expedition (1718-20) active.",
        "religion_note": "Rites Controversy ongoing; Christian missions tolerated but restricted.",
        "ruler": "Kangxi Emperor (Qing)",
        "sources": [
            {"label": "Kangxi Emperor (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Kangxi_Emperor"}
        ],
    },
    "gupta_india": {
        "governance": 35,
        "health_adj": -5,
        "religious_tolerance": 45,
        "governance_note": "Mughal Empire under Muhammad Shah, dominated by Sayyid Brothers. Aurangzeb's death (1707) triggered ongoing succession chaos and noble revolts.",
        "religion_note": "Post-Aurangzeb, jizya repealed 1712-19; Hindu tolerance improving from prior decades but Marathas rising in opposition.",
        "ruler": "Muhammad Shah (Mughal), real power: Sayyid Brothers",
        "sources": [
            {"label": "Sayyid Brothers (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Sayyid_brothers"}
        ],
    },
    "persia": {
        "governance": 20,
        "health_adj": -10,
        "religious_tolerance": 30,
        "governance_note": "Safavid Empire collapsing. Sultan Husayn weak; Afghan Hotaki invasion (1717-22) underway, will sack Isfahan 1722.",
        "religion_note": "Shia state hostile to Sunni Afghans + Christians + Zoroastrians.",
        "ruler": "Sultan Husayn (Safavid)",
        "sources": [
            {"label": "Fall of Safavid Empire (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Fall_of_the_Safavid_dynasty"}
        ],
    },
    "egypt_nile": {
        "governance": 50,
        "health_adj": -5,
        "religious_tolerance": 50,
        "governance_note": "Ottoman province, Mamluk beys ascendant in practice. Stable but with periodic Mamluk power struggles.",
        "religion_note": "Ottoman millet system: Copts + Jews protected as dhimmis with restrictions.",
        "ruler": "Ottoman appointee + Mamluk beys (de facto)",
        "sources": [
            {"label": "Ottoman Egypt (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Ottoman_Egypt"}
        ],
    },
    "constantinople_balkans": {
        "governance": 70,
        "health_adj": 0,
        "religious_tolerance": 60,
        "governance_note": "Ottoman Tulip Period under Ahmed III + Grand Vizier Damat Ibrahim. Peace, cultural flowering, Westernizing reforms. Post-Passarowitz (1718).",
        "religion_note": "Millet system: Greek Orthodox, Armenians, Jews tolerated. Best European environment for Jews in this era.",
        "ruler": "Sultan Ahmed III (Ottoman)",
        "sources": [
            {"label": "Tulip Period (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Tulip_period"}
        ],
    },
    "andalusia_iberia": {
        "governance": 45,
        "health_adj": 0,
        "religious_tolerance": 20,
        "governance_note": "Spain under Philip V, in War of Quadruple Alliance vs Britain/France/Austria/Netherlands. Recently defeated at Cape Passaro (1718). Cardinal Alberoni's adventurism collapsing.",
        "religion_note": "Spanish Inquisition active; forced conversions, Moriscos already expelled.",
        "ruler": "Philip V (Bourbon)",
        "sources": [
            {"label": "War of the Quadruple Alliance (Wikipedia)", "url": "https://en.wikipedia.org/wiki/War_of_the_Quadruple_Alliance"}
        ],
    },
    "francia": {
        "governance": 65,
        "health_adj": 0,
        "religious_tolerance": 30,
        "governance_note": "France under Louis XV (age 9), regency of Philippe II d'Orléans. Stable but financially strained (John Law's bubble brewing). Allied with Britain in Quadruple Alliance.",
        "religion_note": "Revocation of Edict of Nantes (1685) still in force; Huguenots persecuted/exiled. Catholic mandatory.",
        "ruler": "Louis XV (regency of Philippe II d'Orléans)",
        "sources": [
            {"label": "Régence of Philippe d'Orléans (Wikipedia)", "url": "https://en.wikipedia.org/wiki/R%C3%A9gence"}
        ],
    },
    "england": {
        "governance": 75,
        "health_adj": 5,
        "religious_tolerance": 50,
        "governance_note": "George I, post-Jacobite-1715 stable. Whig supremacy, parliamentary government, Walpole's rise. Allied with France in Quadruple Alliance.",
        "religion_note": "Toleration Act 1689 — Protestant Dissenters tolerated; Catholics excluded from public life. No state persecution of Jews.",
        "ruler": "George I (Hanover)",
        "sources": [
            {"label": "George I of Great Britain (Wikipedia)", "url": "https://en.wikipedia.org/wiki/George_I_of_Great_Britain"}
        ],
    },
    "scandinavia": {
        "governance": 50,
        "health_adj": 0,
        "religious_tolerance": 35,
        "governance_note": "Sweden: Charles XII killed Dec 1718, succession to Ulrika Eleonora + parliamentary 'Age of Liberty' beginning. Devastated by Great Northern War. Denmark stable under Frederick IV.",
        "religion_note": "Lutheran state churches; Catholics + Jews excluded or restricted.",
        "ruler": "Ulrika Eleonora (Sweden); Frederick IV (Denmark)",
        "sources": [
            {"label": "Age of Liberty (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Age_of_Liberty"}
        ],
    },
    "rus": {
        "governance": 70,
        "health_adj": -5,
        "religious_tolerance": 25,
        "governance_note": "Peter the Great near end of Great Northern War (Nystad 1721 imminent). Massive centralizing reforms, new capital St Petersburg. Heavy taxation + conscription.",
        "religion_note": "Orthodox state, Old Believers persecuted (double tax 1716). Western tolerance only for foreign experts.",
        "ruler": "Peter I (Romanov)",
        "sources": [
            {"label": "Peter the Great (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Peter_the_Great"}
        ],
    },
    "central_asia": {
        "governance": 30,
        "health_adj": -5,
        "religious_tolerance": 50,
        "governance_note": "Khanates of Khiva, Bukhara, Kokand — small unstable states. Junghar Khanate strong further east, in conflict with Qing.",
        "religion_note": "Predominantly Sunni Muslim. Sufi orders influential. Minorities restricted.",
        "ruler": "Various khans",
        "sources": [
            {"label": "Khanate of Bukhara (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Khanate_of_Bukhara"}
        ],
    },
    "japan": {
        "governance": 80,
        "health_adj": 10,
        "religious_tolerance": 15,
        "governance_note": "Tokugawa shogunate under Yoshimune (Kyōhō Reforms underway since 1716). Famously peaceful Edo period — no wars, urban Edo > 1M.",
        "religion_note": "Sakoku in full force; Christianity banned, brutal persecution. Buddhism + Shinto state-aligned.",
        "ruler": "Tokugawa Yoshimune (8th Shogun)",
        "sources": [
            {"label": "Kyōhō Reforms (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Ky%C5%8Dh%C5%8D_Reforms"}
        ],
    },
    "mesoamerica": {
        "governance": 55,
        "health_adj": -10,
        "religious_tolerance": 25,
        "governance_note": "Spanish Viceroyalty of New Spain. Stable colonial admin, silver mining wealth. Indigenous societies devastated by prior epidemics + encomienda decline.",
        "religion_note": "Catholic compulsory; Inquisition prosecutes heresy + syncretism.",
        "ruler": "Viceroy Baltasar de Zúñiga (Spain)",
        "sources": [
            {"label": "Viceroyalty of New Spain (Wikipedia)", "url": "https://en.wikipedia.org/wiki/New_Spain"}
        ],
    },
    "andes": {
        "governance": 55,
        "health_adj": -10,
        "religious_tolerance": 25,
        "governance_note": "Spanish Viceroyalty of Peru. Potosí silver still flowing, mita labor system brutal. Stable colonial rule.",
        "religion_note": "Catholic compulsory; Andean traditional religion suppressed but syncretism widespread.",
        "ruler": "Viceroy Diego Morcillo Rubio de Auñón",
        "sources": [
            {"label": "Viceroyalty of Peru (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Viceroyalty_of_Peru"}
        ],
    },
    "sahel_west_africa": {
        "governance": 50,
        "health_adj": -10,
        "religious_tolerance": 60,
        "governance_note": "Decline of Mali; rise of Bambara states (Segou under Mamari Coulibaly from 1712). Asante Empire consolidating in Gold Coast. Atlantic slave trade peaking — coastal raids destabilizing interior.",
        "religion_note": "Islam dominant in Sahel, traditional African religions widespread further south. Coexistence outside slave-trade zones.",
        "ruler": "Various — Asantehene Osei Tutu, Bambara king Mamari Coulibaly",
        "sources": [
            {"label": "Atlantic slave trade (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Atlantic_slave_trade"}
        ],
    },
    "ethiopia": {
        "governance": 35,
        "health_adj": -5,
        "religious_tolerance": 40,
        "governance_note": "Gondarine period under Dawit III (deposed/poisoned 1721). Court intrigues, regional warlords growing. Decline of imperial authority.",
        "religion_note": "Ethiopian Orthodox state church; Muslims + traditional religions restricted but tolerated regionally.",
        "ruler": "Emperor Dawit III",
        "sources": [
            {"label": "Dawit III of Ethiopia (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Dawit_III"}
        ],
    },
    "north_america_east": {
        "governance": 50,
        "health_adj": -10,
        "religious_tolerance": 65,
        "governance_note": "British colonies: Massachusetts Bay, Virginia, Carolinas. Stable but small populations. Native nations (Iroquois, Cherokee) still autonomous. King George's War a generation away.",
        "religion_note": "Varies by colony: Puritans intolerant in MA, Quaker tolerance in PA, Anglican establishment in VA. Native religions intact.",
        "ruler": "Royal/Proprietary governors",
        "sources": [
            {"label": "Thirteen Colonies (Wikipedia)", "url": "https://en.wikipedia.org/wiki/Thirteen_Colonies"}
        ],
    },
}

# Era summary printed at the top of the year payload (shown in HUD).
ERA_SUMMARY_1719 = (
    "Great Northern War ending (Charles XII killed late 1718). War of the Quadruple "
    "Alliance ongoing (Spain vs Britain/France/Austria/Netherlands). Ottoman Tulip "
    "Period of peace + reform. Kangxi Emperor's final years in Qing China. Mughal "
    "succession chaos under Sayyid Brothers. Tokugawa Japan stable + closed."
)


def _percentile(value: float, sorted_values: list[float]) -> float:
    """Return position of value in sorted ascending list, in [0, 1]."""
    if not sorted_values:
        return 0.5
    n = len(sorted_values)
    below = sum(1 for v in sorted_values if v < value)
    return below / max(n - 1, 1)


def compute_safety(region_id: str, conflicts: list[dict]) -> tuple[int, list[str]]:
    """Return (score, list of conflict names that hit this region)."""
    score = 85
    hits = []
    for c in conflicts:
        rcode = c.get("region_code")
        ours = BRECKE_REGION_TO_OURS.get(rcode, [])
        # Also a crude name-match heuristic — e.g. conflict name contains region keyword.
        name_lower = (c["name"] or "").lower()
        keyword_hits = any(k in name_lower for k in REGION_KEYWORDS.get(region_id, []))
        if region_id in ours or keyword_hits:
            hits.append(c["name"])
            fatal = c.get("fatalities") or 0
            score -= 25 if fatal > 50_000 else 12
    return max(score, 5), hits


REGION_KEYWORDS = {
    "rome_italy": ["italy", "naples", "sicily", "venice", "sardinia"],
    "han_china": ["china"],
    "gupta_india": ["india", "mughal", "marathas"],
    "persia": ["persia", "afghanistan", "iran"],
    "egypt_nile": ["egypt"],
    "constantinople_balkans": ["turkey", "ottoman", "balkans", "hungary"],
    "andalusia_iberia": ["spain", "portugal", "iberia"],
    "francia": ["france", "germany", "holland", "netherlands", "united provinces", "hanover", "prussia", "saxony"],
    "england": ["britain", "england", "scotland", "ireland", "british"],
    "scandinavia": ["sweden", "denmark", "norway"],
    "rus": ["russia", "poland", "ukraine"],
    "central_asia": ["central asia", "khiva", "bukhara", "junghar"],
    "japan": ["japan"],
    "mesoamerica": ["mexico", "new spain"],
    "andes": ["peru", "andes", "inca"],
    "sahel_west_africa": ["gambia", "angola", "kakonda", "asante", "mali"],
    "ethiopia": ["ethiopia", "abyssinia"],
    "north_america_east": ["new england", "virginia", "carolina", "massachusetts"],
}


def compute_economy(region_id: str, gdppc_by_region: dict, sorted_vals: list[float]) -> tuple[int, str | None, float | None]:
    """Return (score, source_country_iso, gdppc_used)."""
    entry = gdppc_by_region.get(region_id)
    if not entry:
        return 50, None, None
    pct = _percentile(entry["gdppc"], sorted_vals)
    score = round(25 + pct * 65)  # range [25, 90]
    return score, entry["iso"], entry["gdppc"]


def rank(year: int, raw: dict) -> dict:
    # 1. Map Maddison entries → region (best, by GDP), keep one per region.
    gdppc_by_region: dict[str, dict] = {}
    for iso, v in raw["gdppc"].items():
        rid = MADDISON_TO_REGION.get(iso)
        if not rid:
            continue
        # If multiple countries map to same region, prefer the highest gdppc as the marker.
        cur = gdppc_by_region.get(rid)
        if cur is None or v["gdppc"] > cur["gdppc"]:
            gdppc_by_region[rid] = {**v, "iso": iso}
    sorted_vals = sorted(v["gdppc"] for v in gdppc_by_region.values())

    out_regions = {}
    for rid in REGION_IDS:
        manual = MANUAL_1719.get(rid, {})
        safety, conflict_names = compute_safety(rid, raw["conflicts"])
        econ_score, econ_iso, econ_val = compute_economy(rid, gdppc_by_region, sorted_vals)
        gov = manual.get("governance", 50)
        health = max(0, min(100, 45 + manual.get("health_adj", 0)))
        relig = manual.get("religious_tolerance", 50)

        # Overall: 0.30 safety + 0.20 governance + 0.20 economy + 0.15 health + 0.15 relig
        overall = round(0.30 * safety + 0.20 * gov + 0.20 * econ_score + 0.15 * health + 0.15 * relig)

        sources = [
            {"label": "Brecke Conflict Catalog 1400-2000", "url": "https://brecke.inta.gatech.edu/research/conflict/"}
        ]
        if econ_iso:
            sources.append({"label": f"Maddison Project 2023 — {econ_iso} 1719 gdppc={econ_val:.0f}", "url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023"})
        sources.extend(manual.get("sources", []))

        summary_bits = []
        if manual.get("governance_note"):
            summary_bits.append(manual["governance_note"])
        if conflict_names:
            summary_bits.append("Active conflicts: " + "; ".join(conflict_names[:3]))
        if manual.get("religion_note"):
            summary_bits.append("Religion: " + manual["religion_note"])

        out_regions[rid] = {
            "score": overall,
            "summary": " ".join(summary_bits)[:600],
            "factors": {
                "safety": safety,
                "health": health,
                "economy": econ_score,
                "governance": gov,
                "religious_tolerance": relig,
            },
            "sources": sources,
            "ruler": manual.get("ruler"),
            "_debug": {
                "conflicts": conflict_names,
                "gdppc_iso": econ_iso,
                "gdppc": econ_val,
            },
        }

    return {
        "year": year,
        "label": f"{year} CE",
        "era_summary": ERA_SUMMARY_1719,
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
    out = rank(year, raw)
    out_path = OUT_DIR / f"{year:04d}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_path}")
    # Print top 5 + bottom 3 for sanity.
    ranked = sorted(out["regions"].items(), key=lambda kv: -kv[1]["score"])
    print(f"\nTop 5 places to live in {year}:")
    for rid, c in ranked[:5]:
        print(f"  {c['score']:3d}  {rid:28s}  {c.get('ruler','')}")
    print(f"\nBottom 3:")
    for rid, c in ranked[-3:]:
        print(f"  {c['score']:3d}  {rid:28s}  {c.get('ruler','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
