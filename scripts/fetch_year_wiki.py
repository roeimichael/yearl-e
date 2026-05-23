"""Pull Wikipedia year summary (REST API) — gives us year-specific event prose.

This is what stops bulk-generated year files from feeling smoothed: every year
gets its own Wikipedia lead paragraph mentioning the events that defined it.

Output: data/raw/YYYY_wiki.json
  {
    "year": 1719,
    "summary": "...lead paragraph from en.wikipedia.org/wiki/1719...",
    "url": "https://en.wikipedia.org/wiki/1719"
  }
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

UA = "yearl-e/0.1 (https://github.com/roeym/yearl-e)"
REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


def fetch_year(year: int) -> dict:
    title = str(year)  # Wikipedia year articles live at /wiki/1719 etc.
    url = REST.format(title=title)
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return {
        "year": year,
        "summary": j.get("extract", ""),
        "url": j.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{year}"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/fetch_year_wiki.py <year>", file=sys.stderr)
        return 2
    year = int(sys.argv[1])
    out_path = RAW / f"{year}_wiki.json"
    if out_path.exists() and out_path.stat().st_size > 100:
        print(f"  [cache] {out_path.name}")
        return 0
    data = fetch_year(year)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_path} ({len(data['summary'])} chars of summary)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
