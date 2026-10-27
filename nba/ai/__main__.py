"""AI steps CLI.

  python -m nba.ai review   [--no-ai] [--out out/]   who is ready for bulk approval, who needs a person (out/ai_review.json)
  python -m nba.ai feedback [--no-ai] [--out out/]   remember what people said no to (out/customer_memory.jsonl)

Backend: MAINGAU_LLM = auto | claude | ollama | none (nba/ai/llm.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nba.ai import feedback
from nba.ai.llm import LLM, from_env
from nba.ai.review import review
from nba.engine.runtime import Runtime


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["review", "feedback"])
    ap.add_argument("--no-ai", action="store_true", help="Code only, no AI backend")
    ap.add_argument("--out", type=Path, default=Path("out"))
    args = ap.parse_args(argv)
    llm = LLM() if args.no_ai else from_env()
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
        decisions = []
        log = args.out / "decision_log.jsonl"
        if log.exists():
            decisions = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
        items = feedback.from_decisions(decisions) + feedback.from_agent_feedback(
            rt.tables["service_nba_feedback"].to_dict("records"))
        result = feedback.process(rt, items, memory, llm)
        (args.out / "ai_proposals.json").write_text(json.dumps(result["proposals"], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(items)} feedback items, {len(result['added'])} new memory entries (AI: {result['ai']['backend']}) -> {memory}; "
              f"{len(result['proposals'])} proposals for a person -> {args.out / 'ai_proposals.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
