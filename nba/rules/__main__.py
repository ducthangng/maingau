"""Rulebook CLI.

  python -m nba.rules export            write rules.yaml from the four rule files
  python -m nba.rules diff              what you changed, effect on all customers, hard-rule check
                                        (report in out/rules/diff.md; --customers to limit)
  python -m nba.rules apply             write the edits back into the source files (refused on FAIL)
  python -m nba.rules reset             throw the edits away (re-export)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from nba.data import REPO
from nba.rules.book import BOOK, all_changes, apply, edited_sections, export, load_sources, plain
from nba.rules.impact import impact
from nba.rules.report import markdown, terminal, verdict


def run_diff(args):
    found, moved = all_changes()
    if not found:
        print("rules.yaml has no edits.")
        return None, None, moved
    ids = [x.strip() for x in args.customers.split(",")] if args.customers else None
    base = {n: plain(v) for n, v in load_sources().items()}
    imp = impact(base, edited_sections(), customer_ids=ids, hold_to_edited=bool(args.sign_off))
    if args.sign_off and any(c.hard for c in found):
        print(f"Hard rules held to the EDITED version, signed off by {args.sign_off}.")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown(found, imp, moved), encoding="utf-8")
    print(terminal(found, imp, moved))
    print(f"Report: {args.report}")
    return found, imp, moved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="Write rules.yaml from the source files")
    e.add_argument("--force", action="store_true", help="Overwrite rules.yaml even if it has edits")
    for name in ("diff", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--customers", help="Comma-separated customer IDs (default: all)")
        p.add_argument("--report", type=Path, default=Path("out/rules/diff.md"))
        p.add_argument("--sign-off", metavar="NAME", help="Owner sign-off for a hard-rule edit: hold the check to the edited rule")
    sub.choices["apply"].add_argument("--force", action="store_true", help="Apply even if the source files moved")
    sub.add_parser("reset", help="Discard the edits in rules.yaml")
    args = parser.parse_args(argv)

    if args.cmd in {"export", "reset"}:
        if args.cmd == "export" and (REPO / BOOK).exists() and not args.force and all_changes()[0]:
            print("rules.yaml has unapplied edits; run `diff`/`apply`, or `export --force` / `reset` to discard them.")
            return 1
        print(f"Wrote {export()}")
        return 0
    if not (REPO / BOOK).exists():
        print("No rules.yaml yet; run `python -m nba.rules export` first.")
        return 1
    found, imp, moved = run_diff(args)
    if args.cmd == "diff" or found is None:
        return 0
    status, _ = verdict(found, imp)
    if status == "FAIL":
        print("Not applied: the verdict is FAIL.")
        return 1
    if moved and not args.force:
        print("Not applied: the source files changed after export. Re-export and redo the edit, or use --force.")
        return 1
    if args.customers:
        print("Not applied: apply needs the impact on all customers (drop --customers).")
        return 1
    hard = [c for c in found if c.hard]
    if hard and not args.sign_off:
        print("Not applied: hard rule(s) edited; the rule owner signs off with --sign-off NAME.")
        return 1
    written = apply()
    for path, items in written.items():
        print(f"  wrote {path}: {len(items)} change(s)")
    log = REPO / "out" / "rules" / "apply_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sign_off": args.sign_off,
                            "changes": [{"where": c.where, "before": c.before, "after": c.after, "hard": c.hard} for c in found],
                            "decisions_changed": len(imp.changed), "verdict": status}, ensure_ascii=False, default=str) + "\n")
    export()
    print("rules.yaml re-exported from the updated sources. Run the tests and scripts/validate_learn.py, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
