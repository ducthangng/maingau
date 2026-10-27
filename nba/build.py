"""Deterministic offline build and static export: python -m nba.build --help."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from nba.ai import feedback
from nba.ai.llm import LLM
from nba.contracts import CustomerCard, IndexRow, RulesFile, Summary
from nba.data import DEFAULT_WORKBOOK
from nba.engine.export import export_card
from nba.engine.impact import impact_report
from nba.engine.report import test_report
from nba.engine.rule_registry import rules_file
from nba.engine.runtime import Runtime, index_rows, summary
from nba.kg.journey import build_journey, export_journey, lookups


def json_text(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"


def read_jsonl(path) -> list[dict]:
    """Rows of a JSON-lines file; a missing file is empty and a bad line is skipped."""
    rows = []
    for line in (Path(path).read_text(encoding="utf-8").splitlines() if Path(path).exists() else []):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def learn(runtime: Runtime, memory_path) -> tuple[int, list[dict]]:
    """Code-only feedback step (`python -m nba.ai feedback --no-ai`): the workbook's service_nba_feedback plus
    decision_log.jsonl and service_feedback.jsonl next to the memory file become customer memory. Returns
    (feedback items, new memory entries); an item already remembered (same source_ref) is not added twice."""
    folder = Path(memory_path).parent
    decisions = [r for r in read_jsonl(folder / "decision_log.jsonl") if r.get("customer_id") and isinstance(r.get("entry"), dict)]
    service = [r for r in read_jsonl(folder / "service_feedback.jsonl") if r.get("customer_id") and r.get("feedback_id")]
    items = feedback.from_decisions(decisions) + feedback.from_agent_feedback(
        runtime.tables["service_nba_feedback"].to_dict("records") + service)
    llm = LLM()
    llm.enabled = False  # no backend: no card is valued for a prompt, and the memory is reproducible
    return len(items), feedback.process(runtime, items, memory_path, llm)["added"]


def build(runtime: Runtime, out_dir, customer_ids=None, *, export_dir=None, report=True):
    ids = sorted(runtime.states if customer_ids is None else set(customer_ids))
    unknown = sorted(set(ids) - set(runtime.states))
    if unknown:
        raise ValueError("Unknown customers: " + ", ".join(unknown))
    if not ids:
        raise ValueError("Select at least one customer")
    full = runtime.cards(ids)
    cards = [export_card(card) for card in full]
    rows = index_rows(cards, runtime.states)
    totals = summary(cards, runtime.cfg, runtime.states[ids[0]].eval_time, runtime.policy)
    out = Path(out_dir)
    (out / "customers").mkdir(parents=True, exist_ok=True)
    files = []
    for card in cards:
        CustomerCard.model_validate(card.model_dump())
        path = out / "customers" / f"{card.customer_id}.json"
        path.write_text(json_text(card), encoding="utf-8")
        files.append(path)
    # Customer journey for the Customer 360° view (nba.kg.journey): one file per customer next to the card
    (out / "journey").mkdir(exist_ok=True)
    journey_lookups = lookups(runtime.tables, runtime.policy)
    for cid in ids:
        path = out / "journey" / f"{cid}.json"
        path.write_text(json_text(export_journey(build_journey(runtime.states[cid], **journey_lookups))), encoding="utf-8")
        files.append(path)
    (out / "index.json").write_text(json_text([IndexRow.model_validate(r).model_dump(mode="json") for r in rows]), encoding="utf-8")
    (out / "summary.json").write_text(json_text(Summary.model_validate(totals)), encoding="utf-8")
    eval_time = runtime.states[ids[0]].eval_time.isoformat()
    rules = rules_file(runtime.cfg.settings, runtime.policy, runtime.tables, eval_time)
    (out / "rules.json").write_text(json_text(RulesFile.model_validate(rules)), encoding="utf-8")
    files += [out / "index.json", out / "summary.json", out / "rules.json"]
    # Rule Center log (docs/rule-center.md §6): every rule's result per customer for this run; not exported
    with (out / "rule_log.jsonl").open("w", encoding="utf-8") as log:
        for card in full:
            log.write(json_text({"customer_id": card.customer_id, "eval_time": eval_time,
                                 "rule_set_version": card.rules.rule_set_version,
                                 "final_action": card.chosen.tuple_id, "deferred_until": card.chosen.deferred_until,
                                 "results": [r.model_dump(mode="json") for r in card.rules.results]}))
    if report:
        (out / "test_report.md").write_text(test_report(runtime.states, runtime.pop, runtime.policy, runtime.cfg), encoding="utf-8")
        (out / "impact_report.md").write_text(impact_report(cards, runtime.states, runtime.pop, runtime.policy, runtime.cfg), encoding="utf-8")
    if export_dir is not None:
        target = Path(export_dir)
        for file in files:
            destination = target / file.relative_to(out)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if file.resolve() != destination.resolve():
                shutil.copyfile(file, destination)
        # A real export replaces the mock dataset, including its visible mock marker.
        (target / "manifest.json").unlink(missing_ok=True)
    return cards, rows, totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", help="Comma-separated customer IDs; defaults to all 750")
    parser.add_argument("--out", default="out/")
    parser.add_argument("--export", dest="export_dir")
    parser.add_argument("--p-mode", choices=("rate", "uplift"))
    parser.add_argument("--asof", type=datetime.fromisoformat)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--no-report", action="store_true", help="Skip regenerating the reference and impact reports")
    parser.add_argument("--skip-validation", action="store_true", help="Build even if the data contract reports an ERROR")
    parser.add_argument("--memory", type=Path, default=Path("out/customer_memory.jsonl"),
                        help="Customer memory from feedback (nba.ai.feedback); used if the file exists")
    memory = parser.add_mutually_exclusive_group()
    memory.add_argument("--no-memory", action="store_true", help="Ignore the customer memory")
    memory.add_argument("--learn", action="store_true", help="First turn new feedback into memory (code only, no AI)")
    args = parser.parse_args(argv)
    start = time.perf_counter()
    ids = [x.strip() for x in args.customers.split(",") if x.strip()] if args.customers is not None else None
    if not args.skip_validation:  # README §6.15: a new workbook must pass kg/data_contract.yaml first (Q-KG-24)
        from nba.kg.intake import validate_workbook

        errors = [i for i in validate_workbook(args.workbook) if i.level == "ERROR"]
        if errors:
            parser.error(f"{len(errors)} data contract error(s), e.g. {errors[0].code} {errors[0].where}: {errors[0].detail}; "
                         "run scripts/validate_data.py, or pass --skip-validation")
    try:
        runtime = Runtime.load(args.workbook, p_mode=args.p_mode, eval_time=args.asof)
        if args.learn:
            n_items, added = learn(runtime, args.memory)
            print(f"Learned {len(added)} new memory entries from {n_items} feedback items -> {args.memory}")
        if not args.no_memory and args.memory.exists():
            runtime = runtime.with_memory(args.memory)
        cards, _, _ = build(runtime, args.out, ids, export_dir=args.export_dir, report=not args.no_report)
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        parser.error(str(exc))
    entries = [m for ms in runtime.cfg.memory.values() for m in ms]
    at = runtime.states[cards[0].customer_id].eval_time
    used = f"{len(entries)} entries ({sum(feedback.active(m, at) for m in entries)} active) from {args.memory}" if entries else "none"
    print(f"Built {len(cards)} customers in {time.perf_counter() - start:.2f}s; mode={runtime.cfg.p_mode}; "
          f"memory={used}; output={args.out}")


if __name__ == "__main__":
    main()
