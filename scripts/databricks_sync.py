"""Connect the project to a Databricks workspace (nba/lakehouse.py, docs/databricks.md).

  python scripts/databricks_sync.py check [--mcp]   connection, raw layer vs the local files, results layer, MCP tools
  python scripts/databricks_sync.py upload          data/ -> <catalog>.maingau_raw (23 sheets, events_raw, _manifest)
  python scripts/databricks_sync.py publish         out/ (after nba.build) -> <catalog>.maingau_nba + MCP functions

Settings: config/databricks.yaml (catalog, schemas, warehouse) and MAINGAU_DATABRICKS_* variables.
Credentials: DATABRICKS_HOST / DATABRICKS_TOKEN or ~/.databrickscfg; never in this repo.
To build from Databricks: MAINGAU_DATA_SOURCE=databricks python -m nba.build --out out/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from nba import lakehouse as lh  # noqa: E402
from nba.data import DEFAULT_EVENTS, DEFAULT_WORKBOOK, event_lines  # noqa: E402


def compare_with_local(raw: lh.RawData) -> list[str]:
    """Differences between the raw layer and the local files (empty = identical, cell by cell)."""
    diffs = []
    local = pd.read_excel(DEFAULT_WORKBOOK, sheet_name=None, dtype=str)
    if list(local) != list(raw.sheets):
        diffs.append(f"sheet order/names differ: {sorted(set(local) ^ set(raw.sheets))}")
    for name, df in local.items():
        if name in raw.sheets:
            try:
                pd.testing.assert_frame_equal(raw.sheets[name], df)
            except AssertionError as exc:
                diffs.append(f"{name}: {' '.join(str(exc).split())[:160]}")
    if raw.event_lines != event_lines(DEFAULT_EVENTS):
        diffs.append("events_raw differs from the local event stream")
    return diffs


def check(s: lh.Settings, wh: lh.Warehouse, mcp: bool) -> int:
    me = wh.client.current_user.me()
    print(f"Workspace  {wh.client.config.host} as {me.user_name}")
    print(f"Warehouse  {wh.warehouse_id}")
    print(f"Source     config/databricks.yaml source: {s.source} (MAINGAU_DATA_SOURCE overrides)")
    try:
        raw = lh.read_raw(wh, s)
    except lh.LakehouseError as exc:
        print(f"Raw layer  NOT READY: {exc}")
        return 1
    print(f"Raw layer  {raw.detail}")
    for m in raw.manifest:
        print(f"           {m['table_name']:28s} {int(m['n_rows']):6d} rows")
    diffs = compare_with_local(raw) if DEFAULT_WORKBOOK.exists() else ["no local workbook to compare with"]
    print("Compare    identical to data/ (every cell and event line)" if not diffs else "Compare    DIFFERENT:")
    for d in diffs:
        print(f"           {d}")
    try:
        _, rows = wh.query(f"SELECT `eval_time`, `n_customers`, `data_source`, `published_at` FROM {s.out('run_info')}")
        print(f"Results    {s.catalog}.{s.out_schema}: eval_time {rows[0][0]}, {rows[0][1]} customers from "
              f"{rows[0][2]}, published {rows[0][3]}")
    except lh.LakehouseError:
        print(f"Results    none yet in {s.catalog}.{s.out_schema} (run publish after a build)")
    if mcp:
        try:
            client = lh.MCPClient(s, wh.client)
            tools = client.tools()
            print(f"MCP        {client.url}: {len(tools)} tools")
            for t in tools:
                print(f"           {t['name']}: {(t.get('description') or '')[:70]}")
            name = next((t["name"] for t in tools if t["name"].endswith("customer_360")), None)
            if name:
                result = client.call(name, {"customer_id": "MG-100068"})
                text = " ".join(c.get("text", "") for c in result.get("content", []))
                print(f"           {name}(MG-100068) -> {text[:300]}")
        except Exception as exc:  # the managed MCP server is a workspace preview; report, do not fail the check
            print(f"MCP        not available: {' '.join(str(exc).split())[:200]} "
                  "(an admin enables 'Managed MCP Servers' under Settings > Previews)")
    return 0 if not diffs else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="connection, raw layer, results layer")
    c.add_argument("--mcp", action="store_true", help="also list the managed MCP server's tools and call one")
    u = sub.add_parser("upload", help="local files -> raw layer")
    u.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    u.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    p = sub.add_parser("publish", help="build output -> results layer and MCP functions")
    p.add_argument("--out", type=Path, default=REPO / "out")
    args = ap.parse_args()
    s = lh.load_settings()
    try:
        wh = lh.Warehouse(s)
    except Exception as exc:  # no SDK, no credentials, unreachable host: say what to set up
        print(f"Cannot connect to Databricks: {' '.join(str(exc).split())[:240]}\n"
              "Set DATABRICKS_HOST and DATABRICKS_TOKEN, or create ~/.databrickscfg (docs/databricks.md, section 4).")
        return 1
    if args.cmd == "check":
        return check(s, wh, args.mcp)
    if args.cmd == "upload":
        manifest = lh.upload_raw(wh, s, args.workbook, args.events)
        print(f"Uploaded {len(manifest) - 1} sheets and {manifest[-1]['n_rows']} event lines to "
              f"{s.catalog}.{s.raw_schema} (files in {s.volume_dir}/files)")
        return 0
    if not (args.out / "index.json").exists():
        ap.error(f"{args.out}/index.json not found: run python -m nba.build --out {args.out} first")
    counts = lh.publish(wh, s, args.out)
    source = json.loads((args.out / "data_source.json").read_text(encoding="utf-8")) if (args.out / "data_source.json").exists() else {}
    print(f"Published to {s.catalog}.{s.out_schema} (build read: {source.get('source', 'unknown')})")
    for table, n in counts.items():
        print(f"  {table:18s} {n:6d} rows")
    print("  functions: customer_360, next_best_actions, why_blocked, action_group")
    return 0


if __name__ == "__main__":
    sys.exit(main())
