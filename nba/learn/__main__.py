"""Feedback loop CLI.

  python -m nba.learn run   [--out out/learn] [--decisions decisions.json]
  python -m nba.learn apply FIX-P-EN-05 --option A --reviewer "Name" [--out out/learn]
  python -m nba.learn similar MG-100001 [--top 5] [--out out/learn]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nba.data import DEFAULT_WORKBOOK, REPO
from nba.engine.runtime import Runtime
from nba.learn.backtest import backtest
from nba.learn.diagnose import cases as find_cases
from nba.learn.evidence import Evidence, load_settings
from nba.learn.health import ledger_entries, patterns
from nba.learn.lookalike import summary as lookalike_summary, summary_markdown
from nba.learn.report import case_markdown, report

NBA_CONFIG = REPO / "config" / "nba.yaml"


def dump(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def read_decisions(path) -> list[dict]:
    """UI export ({handoff, holdout} or a list) or the API's decision_log.jsonl."""
    if path is None:
        return []
    text = Path(path).read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data if isinstance(data, list) else [*data.get("handoff", []), *data.get("holdout", []), *data.get("decisions", [])]


def append_ledger(path: Path, entries: list[dict]) -> list[dict]:
    """Append-only; an entry already recorded with the same evidence is not written twice."""
    seen = {line for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
    new = [e for e in entries if json.dumps(e, sort_keys=True, ensure_ascii=False) not in seen]
    with path.open("a", encoding="utf-8") as f:
        for e in new:
            f.write(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n")
    return new


def run(runtime, out: Path, decisions=None, *, with_backtest=True):
    ev = Evidence.from_runtime(runtime, load_settings(), decisions)
    eval_time = next(iter(runtime.states.values())).eval_time.isoformat()
    found = patterns(ev)
    found_cases = find_cases(ev, found, runtime.policy, runtime.cfg.p_mode)
    if with_backtest and found_cases:
        base = {card.customer_id: card for card in runtime.cards()}
        for case in found_cases:
            case.backtests = {o.id: backtest(runtime, base, o.overrides, ev.settings.get("reference_customers", ()))
                              for o in case.options}
    meta = {"eval_time": eval_time, "learn_version": ev.settings["learn_version"], "p_mode": runtime.cfg.p_mode,
            "prior_strength": ev.prior_strength, "n_treated": len(ev.treated), "n_control": len(ev.control)}
    (out / "cases").mkdir(parents=True, exist_ok=True)
    (out / "health.json").write_text(dump({"meta": meta, "patterns": [p.as_dict() for p in found]}), encoding="utf-8")
    for case in found_cases:
        (out / "cases" / f"{case.id}.json").write_text(dump(case.as_dict()), encoding="utf-8")
        (out / "cases" / f"{case.id}.md").write_text(case_markdown(case, meta), encoding="utf-8")
    new = append_ledger(out / "ledger.jsonl", ledger_entries(found, ev, eval_time))
    learned = lookalike_summary(runtime.cfg.lookalike, _names(runtime))
    (out / "lookalike.json").write_text(dump(learned), encoding="utf-8")
    (out / "report.md").write_text(report(found, found_cases, new, meta) + "\n" + summary_markdown(learned), encoding="utf-8")
    return found, found_cases, new


def apply(out: Path, case_id: str, option_id: str, reviewer: str, config_path: Path = NBA_CONFIG) -> dict:
    case = json.loads((out / "cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    option = next((o for o in case["options"] if o["id"] == option_id), None)
    if option is None:
        raise SystemExit(f"{case_id} has no option {option_id}; options: {[o['id'] for o in case['options']]}")
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "case": case_id, "option": option_id,
              "title": option["title"], "reviewer": reviewer, "overrides": sorted(option["overrides"])}
    if option["overrides"]:
        text = config_path.read_text(encoding="utf-8")
        entries = [f"  {json.dumps(key)}: " + json.dumps({**value, "case": case_id, "option": option_id, "approved_by": reviewer,
                                                          "approved_at": record["ts"][:10]}, sort_keys=True, ensure_ascii=False)
                   for key, value in sorted(option["overrides"].items())]
        lines = text.splitlines()
        if "p_overrides:" not in lines:
            lines += ["", "# Reviewer-approved p from feedback-loop fix cases (python -m nba.learn apply). Hard rules still run first.",
                      "p_overrides:"]
        at = lines.index("p_overrides:") + 1
        keys = {json.dumps(k) for k in option["overrides"]}
        kept = [line for line in lines[at:] if not any(line.startswith(f"  {k}:") for k in keys)]
        config_path.write_text("\n".join(lines[:at] + entries + kept) + "\n", encoding="utf-8")
    else:
        record["note"] = f"No engine change; rewrite {option['needs_rewrite']} with a reviewed commit."
    with (out / "fix_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return record


def _names(runtime):
    from nba.rules.book import load_sources, plain
    from nba.rules.__main__ import names_for

    return names_for({n: plain(v) for n, v in load_sources().items()}, runtime.tables)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Score every pattern, record what works, open fix cases for what does not")
    r.add_argument("--out", type=Path, default=Path("out/learn"))
    r.add_argument("--decisions", type=Path, help="Reviewer decisions: UI export JSON or out/decision_log.jsonl")
    r.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    r.add_argument("--no-backtest", action="store_true")
    a = sub.add_parser("apply", help="Approve one option of a fix case")
    a.add_argument("case_id")
    a.add_argument("--option", required=True)
    a.add_argument("--reviewer", required=True)
    a.add_argument("--out", type=Path, default=Path("out/learn"))
    m = sub.add_parser("similar", help="Similar customers, what they bought, and what the engine learned for this customer")
    m.add_argument("customer_id")
    m.add_argument("--top", type=int, default=5)
    m.add_argument("--out", type=Path, default=Path("out/learn"))
    args = parser.parse_args(argv)
    if args.cmd == "similar":
        from nba.learn.similar import report as similar_report

        runtime = Runtime.load()
        text = similar_report(runtime, args.customer_id, _names(runtime), args.top)
        path = args.out / "similar" / f"{args.customer_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(text + f"\nSaved: {path}")
    elif args.cmd == "run":
        runtime = Runtime.load(args.workbook)
        found, found_cases, new = run(runtime, args.out, read_decisions(args.decisions), with_backtest=not args.no_backtest)
        counts = {s: sum(p.status == s for p in found) for s in ("green", "amber", "red")}
        print(f"{len(found)} patterns {counts}; {len(found_cases)} fix cases; {len(new)} new ledger entries; output={args.out}")
        for case in found_cases:
            print(f"  {case.id}: {case.layer} -> {args.out / 'cases' / (case.id + '.md')}")
    else:
        record = apply(args.out, args.case_id, args.option, args.reviewer)
        print(f"Applied {record['case']} option {record['option']} by {record['reviewer']}: {record.get('note') or record['overrides']}")


if __name__ == "__main__":
    main()
