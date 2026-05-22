"""Build a region_set JSON by unioning Natural Earth admin-0 polygons.

Reads:
  data/raw/ne_110m_admin_0.geojson — source country shapes
  data/region_groupings/{set}.json — declares region_members, centroid hints, names

Writes:
  data/region_sets/{set}.json — { regions: [ {id, name, centroid, geometry} ] }
  where geometry is a GeoJSON Polygon/MultiPolygon.

Usage: python scripts/build_region_polygons.py early_modern
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
GROUPINGS = ROOT / "data" / "region_groupings"
OUT_DIR = ROOT / "data" / "region_sets"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_grouping(set_name: str) -> dict:
    """Load era-keyed grouping as plain data — never exec arbitrary code from disk."""
    p = GROUPINGS / f"{set_name}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def build(set_name: str) -> None:
    ne_path = RAW / "ne_110m_admin_0.geojson"
    fc = json.loads(ne_path.read_text(encoding="utf-8"))
    by_iso = {}
    for feat in fc["features"]:
        # ISO_A3 is set to "-99" for disputed regions (incl. France + Norway).
        # ADM0_A3 is NE's canonical 3-letter code and is always populated.
        iso = feat["properties"].get("ADM0_A3") or feat["properties"].get("ISO_A3")
        if iso and iso != "-99":
            by_iso[iso] = shape(feat["geometry"])

    g = load_grouping(set_name)
    members: dict[str, list[str]] = g["region_members"]
    centroids: dict[str, list[float]] = g.get("region_centroid_hints", {})
    names: dict[str, str] = g.get("region_names", {})

    out_regions = []
    missing = []
    for rid, isos in members.items():
        geoms = [by_iso[i] for i in isos if i in by_iso]
        skipped = [i for i in isos if i not in by_iso]
        if skipped:
            missing.append((rid, skipped))
        if not geoms:
            print(f"  [!] {rid}: no member geometries found, skipping")
            continue
        merged = unary_union(geoms) if len(geoms) > 1 else geoms[0]
        centroid_pt = merged.centroid
        out_regions.append({
            "id": rid,
            "name": names.get(rid, rid),
            "centroid": centroids.get(rid, [centroid_pt.y, centroid_pt.x]),
            "member_iso3": isos,
            "_area": merged.area,
            "geometry": mapping(merged),
        })

    # Assign min_zoom by area rank so big regions stay labelled at low zoom,
    # small ones only appear when zoomed in. Quartile bucketing.
    sorted_by_area = sorted(out_regions, key=lambda r: -r["_area"])
    n = len(sorted_by_area)
    for i, r in enumerate(sorted_by_area):
        if i < n / 3:
            r["min_zoom"] = 1.0
        elif i < 2 * n / 3:
            r["min_zoom"] = 2.0
        else:
            r["min_zoom"] = 2.6
        del r["_area"]

    out_path = OUT_DIR / f"{set_name}.json"
    out_path.write_text(
        json.dumps({"regions": out_regions}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB, {len(out_regions)} regions)")
    if missing:
        print(f"\n[warn] {len(missing)} regions had ISO3 codes not in NE — verify intent:")
        for rid, sk in missing[:10]:
            print(f"  {rid}: missing {sk}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/build_region_polygons.py <set_name>", file=sys.stderr)
        return 2
    build(sys.argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
