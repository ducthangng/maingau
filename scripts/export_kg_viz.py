"""Export the knowledge graph for the Knowledge Base page in static mode (nba/kg/viz.py); the API serves the
same thing live at GET /api/kb. Uses the engine as configured, without the API's state files (memory, outcomes).

  .venv/bin/python scripts/export_kg_viz.py --out web/public/data/kg_viz.json   # what the static page reads
  .venv/bin/python scripts/export_kg_viz.py --customers MG-100023,MG-100112 --out out/kg_viz.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.engine.runtime import Runtime  # noqa: E402
from nba.kg.viz import DEMO, export  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--customers", default=",".join(DEMO))
    ap.add_argument("--out", type=Path, default=REPO / "out" / "kg_viz.json")
    args = ap.parse_args()
    rt = Runtime.load()
    ids = [c.strip() for c in args.customers.split(",") if c.strip()]
    unknown = [c for c in ids if c not in rt.states]
    if unknown:
        ap.error(f"unknown customers: {', '.join(unknown)}")
    data = export(rt, ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
    print(f"{len(ids)} customers -> {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
