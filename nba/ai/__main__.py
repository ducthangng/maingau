"""AI steps CLI.

  python -m nba.ai review   [--no-ai] [--out out/]   who is ready for bulk approval, who needs a person (out/ai_review.json)
  python -m nba.ai feedback [--no-ai] [--out out/]   remember what people said no to (out/customer_memory.jsonl)
  python -m nba.ai qa       [--no-ai] [--scenarios N] [--out out/]   AI tests of the whole workflow (out/ai_qa/report.md)
  python -m nba.ai ping                                    check that the AI backend answers (key, model, JSON)

Backend: MAINGAU_LLM = auto | hessian | claude | ollama | none (nba/ai/llm.py; settings in .env, see .env.example).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from nba.ai import feedback
from nba.ai.llm import LLM, from_env
from nba.ai.review import review
from nba.engine.runtime import Runtime


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["review", "feedback", "qa", "ping"])
    ap.add_argument("--no-ai", action="store_true", help="Code only, no AI backend")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--scenarios", type=int, default=8, help="qa: scenarios the AI tester may write (seed scenarios always run)")
    args = ap.parse_args(argv)
    llm = LLM() if args.no_ai else from_env()
    if args.step == "ping":
        return ping(llm)
    if args.step == "qa":  # a fresh runtime and its own folder: the test decisions never touch out/decision_log.jsonl
        from nba.ai import qa

        report = qa.run(Runtime.load(), llm, args.out / "ai_qa", n_ai=args.scenarios)
        s = report["summary"]
        print(f"{s['scenarios']} scenarios ({s['seed']} seed, {s['ai']} AI): {s['passed']} passed, {s['failed']} failed, "
              f"{s['tester_mismatches']} tester mismatches, {s['suspicious']} suspicious; workflow "
              f"{'passed' if s['workflow_passed'] else 'FAILED'} (AI: {report['backend']}) -> {args.out / 'ai_qa' / 'report.md'}")
        return 0 if s["failed"] == 0 and s["workflow_passed"] else 1
    memory = args.out / "customer_memory.jsonl"
    rt = Runtime.load(memory_path=memory)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step == "review":
        result = review(rt, llm)
        (args.out / "ai_review.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        s = result["summary"]
        print(f"{s['proposals']} proposals in {s['clusters']} clusters: {s['ready']} ready, {s['needs_review']} need a person "
              f"(AI: {result['ai']['backend']}, {result['ai']['reviewed']} reviewed) -> {args.out / 'ai_review.json'}")
    else:
        decisions = [r for r in feedback.read_jsonl(args.out / "decision_log.jsonl") if isinstance(r.get("entry"), dict)]
        rows = feedback.agent_rows(rt.tables["service_nba_feedback"].to_dict("records"),
                                   feedback.read_jsonl(args.out / "service_feedback.jsonl"))
        items = feedback.from_decisions(decisions) + feedback.from_agent_feedback(rows)
        result = feedback.process(rt, items, memory, llm)
        (args.out / "ai_proposals.json").write_text(json.dumps(result["proposals"], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(items)} feedback items, {len(result['added'])} new memory entries (AI: {result['ai']['backend']}) -> {memory}; "
              f"{len(result['proposals'])} proposals for a person -> {args.out / 'ai_proposals.json'}")
    return 0


def ping(llm: LLM) -> int:
    """One tiny structured request: shows the backend, the model and whether valid JSON comes back."""
    if not llm.enabled or llm.name == "none":
        print("No AI backend: set MAINGAU_LLM and the backend's key (for Hessian.AI: HAI_API_KEY in .env, see .env.example)")
        return 1
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "answer": {"type": "string"}},
              "required": ["ok", "answer"], "additionalProperties": False}
    start = time.perf_counter()
    answer = llm.structured("You check that a connection works. Reply with ok = true and answer = \"pong\".", {"ping": "hello"}, schema)
    took = time.perf_counter() - start
    model = getattr(llm, "model", "?")
    if not answer:
        print(f"{llm.name} ({model}): no valid answer after {took:.1f}s; see the warning above (key, model name or gateway)")
        return 1
    print(f"{llm.name} ({model}): {json.dumps(answer, ensure_ascii=False)} in {took:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
