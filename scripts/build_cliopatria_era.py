"""Build a region_set from Cliopatria (Seshat) polities active in a given year.

Cliopatria (CC-BY 4.0) is a year-keyed GeoJSON of ~1,600 world polities,
3400 BCE - 2024 CE. Each feature has FromYear/ToYear; the polities "active" in
a year are the rows whose [FromYear, ToYear] contains it.

This produces the SAME region_set schema the backend/frontend already consume:
  data/region_sets/{out}.json -> { regions: [ {id, name, centroid,
                                   member_iso3, geometry, min_zoom} ] }

member_iso3 is derived by SPATIAL OVERLAP with Natural Earth 110m, so the
existing ISO3-keyed scoring (Maddison economy, V-Dem governance) works unchanged.

Usage: python scripts/build_cliopatria_era.py <out_name> <year> [--min-area DEG2]
  e.g. python scripts/build_cliopatria_era.py early_modern_clio 1700
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "region_sets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIO = RAW / "cliopatria_polities_only.geojson"
NE = RAW / "ne_110m_admin_0.geojson"

# A polity gets a modern ISO3 as a "member" if their overlap is a meaningful
# share of the SMALLER of the two areas. Catches both "country sits inside
# empire" and "small polity sits inside one country".
OVERLAP_FRAC = 0.30

# Ocean-spanning empires (Dutch Republic = NLD + East Indies + Ceylon) are one
# polity but geographically incoherent as a single guess-region. Split a polity
# into separate regions when its parts are farther apart than this many degrees
# (regional seas like the Channel/Aegean/inter-island gaps stay joined; oceans
# split). Contiguous land empires (Ottoman, Spanish America) stay whole.
CLUSTER_GAP = 6.0


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "region"


def load_ne() -> list[tuple[str, object]]:
    fc = json.loads(NE.read_text(encoding="utf-8"))
    out = []
    for feat in fc["features"]:
        iso = feat["properties"].get("ADM0_A3") or feat["properties"].get("ISO_A3")
        if iso and iso != "-99":
            out.append((iso, shape(feat["geometry"])))
    return out


def active_by_years(years: list[int]) -> dict[int, list[dict]]:
    """Single streaming pass over Cliopatria. Returns {year: [features active]}.
    Skips non-POLITY rows and the parenthetical alliance/allegiance pseudo-entries.
    One pass beats re-reading the 157 MB file once per snapshot."""
    buckets: dict[int, list[dict]] = {y: [] for y in years}
    with open(CLIO, encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith('{ "type": "Feature"'):
                continue
            try:
                feat = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = feat["properties"]
            if p.get("Type") != "POLITY":
                continue
            if p.get("Name", "").startswith("("):  # alliance/allegiance rows
                continue
            fy, ty = p["FromYear"], p["ToYear"]
            for y in years:
                if fy <= y <= ty:
                    buckets[y].append(feat)
    return buckets


def _box_gap(a, b) -> float:
    """Min gap between two (minx,miny,maxx,maxy) boxes; 0 if they overlap."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def cluster_parts(geom, gap: float, min_part: float = 0.05) -> list:
    """Split a (Multi)Polygon into proximity clusters. Parts closer than `gap`
    degrees join the same cluster; ocean-separated parts become distinct."""
    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    parts = [p for p in parts if p.area >= min_part] or [geom]
    n = len(parts)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    boxes = [p.bounds for p in parts]
    for i in range(n):
        for j in range(i + 1, n):
            if _box_gap(boxes[i], boxes[j]) < gap and parts[i].distance(parts[j]) < gap:
                parent[find(i)] = find(j)
    groups: dict[int, list] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(parts[i])
    return [unary_union(v) if len(v) > 1 else v[0] for v in groups.values()]


def members_for(poly, ne_isos, ne_shapes, tree, idx_to_iso) -> list[str]:
    """ISO3s whose overlap with `poly` exceeds OVERLAP_FRAC of the smaller area."""
    members = []
    poly_area = poly.area
    if poly_area <= 0:
        return members
    for idx in tree.query(poly):
        iso = idx_to_iso[idx]
        cgeom = ne_shapes[idx]
        if not poly.intersects(cgeom):
            continue
        inter = poly.intersection(cgeom).area
        if inter <= 0:
            continue
        if inter >= OVERLAP_FRAC * min(poly_area, cgeom.area):
            members.append((iso, inter))
    # biggest-overlap first so economy/gov picks the dominant territory's number
    members.sort(key=lambda t: -t[1])
    return [iso for iso, _ in members]


def build_regions(feats: list[dict], ne_isos, ne_shapes, tree, idx_to_iso,
                  min_area: float) -> tuple[list[dict], int, int]:
    """Turn a year's active polity features into region dicts. Returns
    (regions, split_count, dropped_small)."""
    regions = []
    dropped_small = 0
    split_count = 0
    seen_ids: dict[str, int] = {}

    def new_id(base: str) -> str:
        if base not in seen_ids:
            seen_ids[base] = 0
            return base
        seen_ids[base] += 1
        return f"{base}_{seen_ids[base]}"

    for feat in feats:
        p = feat["properties"]
        whole = shape(feat["geometry"]).buffer(0)
        if whole.is_empty or whole.area < min_area:
            dropped_small += 1
            continue
        clusters = cluster_parts(whole, CLUSTER_GAP)
        clusters = [g for g in clusters if g.area >= min_area]
        if not clusters:
            dropped_small += 1
            continue
        if len(clusters) > 1:
            split_count += 1
        # largest cluster keeps the bare name; ocean-separated parts get the
        # dominant modern country appended so the id stays unique + meaningful.
        clusters.sort(key=lambda g: -g.area)
        for k, geom in enumerate(clusters):
            iso = members_for(geom, ne_isos, ne_shapes, tree, idx_to_iso)
            name = p["Name"]
            base = slugify(name)
            if k > 0:
                tag = iso[0] if iso else f"part{k}"
                name = f"{name} ({tag})"
                base = f"{base}_{slugify(tag)}"
            c = geom.centroid
            regions.append({
                "id": new_id(base),
                "name": name,
                "centroid": [c.y, c.x],
                "member_iso3": iso,
                "wikidata": p.get("Wikidata", ""),
                "seshat_id": p.get("SeshatID", ""),
                "_area": geom.area,
                "geometry": mapping(geom),
            })

    # min_zoom by area rank (thirds), same convention as build_region_polygons.
    regions.sort(key=lambda r: -r["_area"])
    n = len(regions)
    for i, r in enumerate(regions):
        r["min_zoom"] = 1.0 if i < n / 3 else (2.0 if i < 2 * n / 3 else 2.6)
        del r["_area"]
    return regions, split_count, dropped_small


def write_set(out_name: str, regions: list[dict]) -> None:
    out_path = OUT_DIR / f"{out_name}.json"
    out_path.write_text(json.dumps({"regions": regions}, ensure_ascii=False), encoding="utf-8")
    no_iso = [r["id"] for r in regions if not r["member_iso3"]]
    note = f" | {len(no_iso)} regions no-ISO3" if no_iso else ""
    print(f"wrote {out_path.name} ({out_path.stat().st_size/1024:.0f} KB, {len(regions)} regions){note}")


def build_snapshots(out_prefix: str, years: list[int], min_area: float) -> None:
    ne = load_ne()
    ne_isos = [iso for iso, _ in ne]
    ne_shapes = [g for _, g in ne]
    tree = STRtree(ne_shapes)
    idx_to_iso = {i: ne_isos[i] for i in range(len(ne_isos))}

    print(f"streaming Cliopatria once for {len(years)} snapshots: {years}")
    buckets = active_by_years(years)
    for y in years:
        feats = buckets[y]
        regions, splits, dropped = build_regions(
            feats, ne_isos, ne_shapes, tree, idx_to_iso, min_area)
        out_name = f"{out_prefix}_{y}"
        write_set(out_name, regions)
        print(f"  {y}: {len(feats)} active polities -> {len(regions)} regions "
              f"({splits} ocean-split, {dropped} dropped <{min_area})")


def main() -> int:
    # batch:  python scripts/build_cliopatria_era.py <prefix> --snapshots y1,y2,...
    # single: python scripts/build_cliopatria_era.py <prefix> <year>
    if len(sys.argv) < 3:
        print("usage: build_cliopatria_era.py <out_prefix> (<year> | --snapshots y1,y2,..) [--min-area DEG2]",
              file=sys.stderr)
        return 2
    prefix = sys.argv[1]
    min_area = 2.0
    if "--min-area" in sys.argv:
        min_area = float(sys.argv[sys.argv.index("--min-area") + 1])
    if "--snapshots" in sys.argv:
        years = [int(x) for x in sys.argv[sys.argv.index("--snapshots") + 1].split(",")]
    else:
        years = [int(sys.argv[2])]
    build_snapshots(prefix, years, min_area)
    return 0


if __name__ == "__main__":
    sys.exit(main())
