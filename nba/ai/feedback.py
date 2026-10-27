"""AI step 2: learn from people who said no. Customer memory in the knowledge graph.

Feedback comes from two places:
- the decision log, when a person rejects the proposed action or overrides it with another one;
- the workbook's service_nba_feedback, when a service agent dismissed a suggested offer or the
  customer declined it, plus the rows agents record in Customer 360° (out/service_feedback.jsonl).
Code turns each item into a memory entry for that one customer (a Feedback node in the KG): pause the
offer, block the channel, pause all sales, or flag the customer for review, until a date. The engine
reads the memory on the next run (nba.engine.rulecenter, rule ID MEMORY), so the same proposal does not
come back. The AI, where a backend is available, reads the reason, the proposal and the customer's
evidence, writes the note, classifies free-text reasons, may make the memory stricter (never looser) and
suggests changes for everyone, which only a person can apply (Rule Center what-if and versions).
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from nba.ai.llm import LLM

REASON_CODES = ["already_has_product", "customer_upset", "no_time", "not_relevant", "wrong_channel",
                "wrong_timing", "data_wrong", "other"]
KINDS = ["pause_sales", "block_channel", "pause_offer", "review", "note"]  # strictest first
DEFAULT = {"already_has_product": ("pause_offer", 365), "customer_upset": ("pause_sales", 30),
           "no_time": ("pause_offer", 14), "wrong_timing": ("pause_offer", 14), "not_relevant": ("pause_offer", 90),
           "wrong_channel": ("block_channel", 90), "data_wrong": ("review", 30), "other": ("note", 30)}
AGENT_REASONS = {"customer_already_has_product": "already_has_product", "customer_upset": "customer_upset",
                 "no_time": "no_time", "not_relevant": "not_relevant"}
SYSTEM = (
    "A person rejected or replaced an action the Next Best Action engine proposed for one customer. You get "
    "the feedback, the proposal with its value, and the customer's evidence from the knowledge graph. Classify "
    "the reason (reason_code), choose what the engine should remember for this customer (memory_kind, offer, "
    "channel, days), and write a note of at most two sentences in English for the next reviewer. Use only offer "
    "and channel IDs from the lists given. If the same issue probably affects other customers, describe it in "
    "global_hint (one sentence), otherwise leave it empty. Never suggest loosening a rule or sending anything."
)


def schema(offers: list[str], channels: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "reason_code": {"type": "string", "enum": REASON_CODES},
            "memory_kind": {"type": "string", "enum": KINDS},
            "offer_id": {"type": "string", "enum": offers + ["none"]},
            "channel": {"type": "string", "enum": channels + ["none"]},
            "days": {"type": "integer"},
            "note": {"type": "string"},
            "global_hint": {"type": "string"},
        },
        "required": ["reason_code", "memory_kind", "offer_id", "channel", "days", "note", "global_hint"],
        "additionalProperties": False,
    }


def _naive(ts) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return ts.replace(tzinfo=None)


# ---------------------------------------------------------------- memory store (KG instance layer)


def read_jsonl(path) -> list[dict]:
    """The records of a JSON-lines file; a line that cannot be decoded (a torn last line) is skipped, not fatal."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def load_memory(path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for m in read_jsonl(path):
        if m.get("customer_id") and m.get("source_ref") is not None:  # a line that is not a memory entry is skipped
            out.setdefault(m["customer_id"], []).append(m)
    return out


def append_memory(path, entries: list[dict]) -> None:
    """Whole lines in one write, after a newline if the file ends in a torn line; flushed to disk."""
    if not entries:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(m, ensure_ascii=False, sort_keys=True, default=str) + "\n" for m in entries).encode("utf-8")
    with p.open("a+b") as f:
        if f.seek(0, os.SEEK_END):
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                data = b"\n" + data
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def active(m: dict, at: datetime) -> bool:
    until = _naive(m.get("until"))
    return until is not None and until > at


# ---------------------------------------------------------------- feedback items


def from_decisions(records: list[dict]) -> list[dict]:
    """Rejections and overrides from the API decision log ({customer_id, entry} envelopes)."""
    items = []
    for r in records:
        e = r["entry"]
        if (e.get("action") not in {"rejected", "overridden"} or not isinstance(e.get("from_tuple"), str)
                or e["from_tuple"] == "NO_ACTION" or not isinstance(e.get("ts"), str)):
            continue
        offer, channel, _ = (e["from_tuple"].split("|") + ["", ""])[:3]
        items.append({"source": "decision_log", "ref": f"{r['customer_id']}@{e['ts']}", "customer_id": r["customer_id"],
                      "at": e["ts"], "action": e["action"], "offer_id": offer, "channel": channel,
                      "to_tuple": e.get("to_tuple"), "reason": e.get("reason"), "reason_code": e.get("reason_code"),
                      "predicted_delta_clv": (e.get("scores") or {}).get("delta_clv"), "by": e.get("actor")})
    return items


def agent_rows(workbook: list[dict], posted: list[dict]) -> list[dict]:
    """The workbook's service_nba_feedback plus the rows agents posted through the API
    (out/service_feedback.jsonl), once per feedback_id (the first one is kept)."""
    seen, out = set(), []
    for r in [*workbook, *posted]:
        fid = r.get("feedback_id")
        if fid and fid in seen:
            continue
        seen.add(fid)
        out.append(r)
    return out


def from_agent_feedback(rows: list[dict]) -> list[dict]:
    """Offers a service agent dismissed, or the customer declined, in service_nba_feedback."""
    items = []
    for r in rows:
        code = AGENT_REASONS.get(r.get("dismiss_reason") or "")
        if r.get("customer_reaction") == "annoyed":
            code = "customer_upset"
        elif code is None and r.get("customer_reaction") == "declined":
            code = "not_relevant"
        if r.get("agent_action") != "dismissed" and r.get("customer_reaction") not in {"annoyed", "declined"}:
            continue
        items.append({"source": "agent_feedback", "ref": r.get("feedback_id"), "customer_id": r["customer_id"],
                      "at": r.get("shown_at"), "action": "dismissed", "offer_id": r.get("suggested_offer_id"),
                      "channel": None, "reason": r.get("dismiss_reason") or r.get("customer_reaction"),
                      "reason_code": code or "other", "outcome": {"converted": r.get("converted_within_14d")}})
    return items


# ---------------------------------------------------------------- turning feedback into memory


def _entry(item, kind, days, offer, channel, note, by, code, n) -> dict:
    since = _naive(item["at"]) or datetime(1970, 1, 1)
    return {"id": f"M-{item['customer_id']}-{n}", "customer_id": item["customer_id"], "kind": kind,
            "offer_id": offer if kind == "pause_offer" else None, "channel": channel if kind == "block_channel" else None,
            "since": since.isoformat(), "until": (since + timedelta(days=days)).isoformat(), "reason_code": code,
            "source": item["source"], "source_ref": item["ref"], "note": note, "by": by,
            "predicted_delta_clv": item.get("predicted_delta_clv"), "outcome": item.get("outcome")}


def _pack(item, card) -> dict:
    cand = next((c for c in card.candidates if c.offer_id == item["offer_id"]), None) if card else None
    return {"feedback": {k: item.get(k) for k in ("source", "action", "offer_id", "channel", "to_tuple", "reason",
                                                    "reason_code", "predicted_delta_clv")},
            "customer": None if card is None else {
                "id": card.customer_id, "segment": card.triage.archetype.name,
                "signals": [{"id": s.id, "detail": s.detail} for s in card.signals],
                "flags": [f.id for f in card.triage.flags],
                "proposal_now": card.chosen.tuple_id,
                "offer_valuation": None if cand is None or cand.valuation is None else {
                    "delta_clv": round(cand.valuation.delta_clv, 2), "p": round(cand.valuation.p_accept, 4)}}}


def process(runtime, items: list[dict], memory_path, llm: LLM | None = None, ai_limit: int = 60) -> dict:
    """Append memory for the feedback items not yet remembered; return the new entries and the proposals."""
    llm = llm or LLM()
    memory = load_memory(memory_path)
    seen = {m["source_ref"] for ms in memory.values() for m in ms}
    offers = sorted(runtime.policy.offers)
    channels = sorted(runtime.policy.channels)
    new, hints, ai_calls = [], [], 0
    for item in sorted(items, key=lambda i: (str(i["at"]), str(i["ref"]))):
        if item["ref"] in seen or item["customer_id"] not in runtime.states:
            continue
        code = item.get("reason_code") if item.get("reason_code") in REASON_CODES else None
        kind, days = DEFAULT[code or "other"]
        offer, channel = item.get("offer_id"), item.get("channel")
        note, by = f"{item['action']}: {item.get('reason') or code or 'no reason given'}", "rule"
        if llm.enabled and ai_calls < ai_limit:
            card = runtime.card(item["customer_id"])
            answer = llm.structured(SYSTEM, _pack(item, card), schema(offers, channels), effort="medium")
            ai_calls += 1
            if answer and answer.get("memory_kind") in KINDS and answer.get("reason_code") in REASON_CODES:
                code = code or answer["reason_code"]  # a person's code wins; the AI classifies free text
                kind, base_days = DEFAULT[code]
                ai_kind = answer["memory_kind"]
                if KINDS.index(ai_kind) < KINDS.index(kind):  # stricter only, never looser
                    kind = ai_kind
                    offer = answer["offer_id"] if answer["offer_id"] in offers else offer
                    channel = answer["channel"] if answer["channel"] in channels else channel
                days = max(base_days, min(365, max(1, int(answer.get("days") or 0))))
                note, by = str(answer.get("note") or note)[:400], f"ai:{llm.name}"
                if answer.get("global_hint"):
                    hints.append({"customer_id": item["customer_id"], "offer_id": item.get("offer_id"),
                                  "reason_code": code, "hint": str(answer["global_hint"])[:300]})
        code = code or "other"
        if kind == "block_channel" and not channel:
            kind = "pause_offer"  # service-agent feedback has no marketing channel to block
        n = len(memory.get(item["customer_id"], [])) + sum(m["customer_id"] == item["customer_id"] for m in new) + 1
        new.append(_entry(item, kind, days, offer, channel, note, by, code, n))
        seen.add(item["ref"])
    append_memory(memory_path, new)
    return {"added": new, "proposals": proposals(items, hints), "ai": {"backend": llm.name if llm.enabled else "none",
                                                                     "calls": ai_calls}}


def proposals(items: list[dict], hints: list[dict]) -> list[dict]:
    """Patterns worth a rule for everyone; only a person can apply them (Rule Center what-if first)."""
    by_offer = Counter((i.get("offer_id"), i.get("reason_code") or "other") for i in items if i.get("offer_id"))
    out = [{"offer_id": o, "reason_code": c, "customers": n,
            "suggestion": f"{n} customers turned down {o} ({c.replace('_', ' ')}): review its targeting or add a rule"}
           for (o, c), n in by_offer.most_common() if n >= 3]
    for h in hints:
        out.append({"offer_id": h["offer_id"], "reason_code": h["reason_code"], "customers": 1,
                    "suggestion": h["hint"], "from": h["customer_id"]})
    return out
