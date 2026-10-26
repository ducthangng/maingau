"""Deterministic offline build and static export: python -m nba.build --help."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from nba.contracts import CustomerCard, IndexRow, Summary
from nba.data import DEFAULT_WORKBOOK
from nba.engine.report import test_report
from nba.engine.runtime import Runtime, index_rows, summary


def json_text(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def build(runtime: Runtime, out_dir, customer_ids=None, *, export_dir=None, report=True):
    ids = sorted(runtime.states if customer_ids is None else set(customer_ids))
    unknown = sorted(set(ids) - set(runtime.states))
    if unknown:
        raise ValueError("Unknown customers: " + ", ".join(unknown))
    if not ids:
        raise ValueError("Select at least one customer")
    cards = runtime.cards(ids)
    rows = index_rows(cards, runtime.states)
    totals = summary(cards, runtime.cfg, runtime.states[ids[0]].eval_time)
    out = Path(out_dir)
    (out / "customers").mkdir(parents=True, exist_ok=True)
    files = []
    for card in cards:
        CustomerCard.model_validate(card.model_dump())
        path = out / "customers" / f"{card.customer_id}.json"
        path.write_text(json_text(card), encoding="utf-8")
        files.append(path)
    (out / "index.json").write_text(json_text([IndexRow.model_validate(r).model_dump(mode="json") for r in rows]), encoding="utf-8")
    (out / "summary.json").write_text(json_text(Summary.model_validate(totals)), encoding="utf-8")
    files += [out / "index.json", out / "summary.json"]
    if report:
        (out / "test_report.md").write_text(test_report(runtime.states, runtime.pop, runtime.policy, runtime.cfg), encoding="utf-8")
    if export_dir is not None:
        target = Path(export_dir)
        for file in files:
            destination = target / file.relative_to(out)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if file.resolve() != destination.resolve():
                shutil.copyfile(file, destination)
    return cards, rows, totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", help="Comma-separated customer IDs; defaults to all 750")
    parser.add_argument("--out", default="out/")
    parser.add_argument("--export", dest="export_dir")
    parser.add_argument("--p-mode", choices=("rate", "uplift"))
    parser.add_argument("--asof", type=datetime.fromisoformat)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--no-report", action="store_true", help="Skip regenerating the two-mode reference report")
    args = parser.parse_args(argv)
    start = time.perf_counter()
    ids = [x.strip() for x in args.customers.split(",") if x.strip()] if args.customers is not None else None
    try:
        runtime = Runtime.load(args.workbook, p_mode=args.p_mode, eval_time=args.asof)
        cards, _, _ = build(runtime, args.out, ids, export_dir=args.export_dir, report=not args.no_report)
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        parser.error(str(exc))
    print(f"Built {len(cards)} customers in {time.perf_counter() - start:.2f}s; mode={runtime.cfg.p_mode}; output={args.out}")


if __name__ == "__main__":
    main()
