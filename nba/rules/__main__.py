"""Rulebook CLI.

  python -m nba.rules export                 write rules.yaml: every rule as a plain-language card
  python -m nba.rules diff                   what you changed, what happens to customers, safety check
                                             (full report in out/rules/diff.md; --customers to limit)
  python -m nba.rules apply --by "Name"      make the change the new rule (refused on FAIL)
  python -m nba.rules reset                  throw your changes away

  --technical on export / diff / apply uses rules.technical.yaml (the four rule files in one, for the team).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from nba.data import REPO, load_workbook
from nba.rules import book
from nba.rules.cards import CardError, Names, compile_cards, render, show_value, stats_for
from nba.rules.impact import impact, runtime_from
from nba.rules.report import markdown, terminal, verdict

CARDS = Path("rules.yaml")


def base_sections(root=REPO) -> dict:
    return {n: book.plain(v) for n, v in book.load_sources(root).items()}


def names_for(sections, tables) -> Names:
    return Names(sections, {r["product_id"]: r["product_name"] for r in tables["product_catalog"].to_dict("records")})


def export_cards(root=REPO, *, with_stats=True) -> Path:
    tables = load_workbook()
    base = base_sections(root)
    stats = stats_for(runtime_from(base, tables)) if with_stats else None
    path = root / CARDS
    path.write_text(render(base, names_for(base, tables), stats, book.fingerprint(root)), encoding="utf-8")
    return path


def load_edit(technical: bool, by: str, root=REPO):
    """-> (edited rule files, change rows for the report, sources moved since export, names)."""
    base = base_sections(root)
    names = names_for(base, load_workbook())
    if technical:
        found, moved = book.all_changes(root)
        rows = [{"where": c.where, "before": c.before, "after": c.after, "hard": c.hard} for c in found]
        return book.edited_sections(root), rows, moved, names
    path = root / CARDS
    if not path.exists():
        raise FileNotFoundError("No rules.yaml yet; run `python -m nba.rules export` first.")
    edited, found, fp = compile_cards(path.read_text(encoding="utf-8"), base, names, by)
    rows = [{"where": c.where, "before": show_value(c, c.before), "after": show_value(c, c.after), "hard": c.hard} for c in found]
    return edited, rows, fp != book.fingerprint(root), names


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="Write rules.yaml from the current rules")
    e.add_argument("--force", action="store_true", help="Overwrite even if the file has changes")
    for name in ("diff", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--customers", help="Comma-separated customer IDs (default: all)")
        p.add_argument("--report", type=Path, default=Path("out/rules/diff.md"))
        p.add_argument("--sign-off", metavar="NAME", help="Rule owner's sign-off for a 🔒 hard-rule change")
    sub.choices["apply"].add_argument("--by", required=True, metavar="NAME", help="Who makes this change (logged)")
    sub.choices["apply"].add_argument("--force", action="store_true", help="Apply even if the rules moved since export")
    sub.add_parser("reset", help="Throw your changes away")
    for p in (e, sub.choices["diff"], sub.choices["apply"], sub.choices["reset"]):
        p.add_argument("--technical", action="store_true", help="Use rules.technical.yaml")
    args = parser.parse_args(argv)
    target = book.BOOK if args.technical else CARDS

    if args.cmd in {"export", "reset"}:
        if args.cmd == "export" and (REPO / target).exists() and not args.force:
            try:
                pending = load_edit(args.technical, "preview")[1]
            except (CardError, ValueError):
                pending = ["unreadable"]
            if pending:
                print(f"{target} has changes that are not applied; run diff / apply, or reset to throw them away.")
                return 1
        written = book.export() if args.technical else export_cards()
        print(f"Wrote {written}")
        return 0

    try:
        edited, rows, moved, names = load_edit(args.technical, getattr(args, "by", None) or "preview")
    except (CardError, FileNotFoundError) as exc:
        print(f"Cannot read {target}: {exc}")
        return 1
    if not rows:
        print(f"{target} has no changes.")
        return 0
    ids = [x.strip() for x in args.customers.split(",")] if args.customers else None
    imp = impact(base_sections(), edited, customer_ids=ids, hold_to_edited=bool(args.sign_off))
    if args.sign_off and any(r["hard"] for r in rows):
        print(f"Hard rules checked against YOUR new version, signed off by {args.sign_off}.")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown(rows, imp, moved, names), encoding="utf-8")
    print(terminal(rows, imp, moved, names))
    print(f"Full report: {args.report}")
    if args.cmd == "diff":
        return 0

    status, _ = verdict(rows, imp)
    refusals = [(status == "FAIL", "the verdict is FAIL"),
                (moved and not args.force, "the rules changed after you opened the file; reset and redo, or use --force"),
                (bool(args.customers), "apply needs every customer (drop --customers)"),
                (any(r["hard"] for r in rows) and not args.sign_off, "a 🔒 hard rule changed; the rule owner adds --sign-off NAME")]
    for refused, why in refusals:
        if refused:
            print(f"Not applied: {why}.")
            return 1
    written = book.apply(REPO, edited)
    for path, items in written.items():
        print(f"  updated {path} ({len(items)} setting(s))")
    log = REPO / "out" / "rules" / "apply_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "by": args.by,
                            "sign_off": args.sign_off, "changes": rows, "customers_changed": len(imp.changed),
                            "verdict": status}, ensure_ascii=False, default=str) + "\n")
    book.export() if args.technical else export_cards()
    print(f"Done. {target} now shows the new rules. Run the tests and scripts/validate_learn.py, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
