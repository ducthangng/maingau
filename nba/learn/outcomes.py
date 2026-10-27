"""Campaign fast-forward (POST /api/campaigns/{id}/fast-forward, the Campaigns pop-up).

A campaign approved in the UI is never sent, so it has no outcome. Fast-forward simulates the 14 days after the
send for every contacted customer: a seeded draw against the engine's own chance p decides whether the customer
bought, and the actual ΔCLV follows from the same valuation as the expected one:

    expected ΔCLV = p·(CLV_buy − CLV_no) + (CLV_no − CLV_now) − cost
    actual ΔCLV   = (CLV_buy if bought else CLV_no) − CLV_now − cost

The control group was not sent and gets no outcome. Every simulated send becomes a delivered nba_action_history
row (decision_source "campaign_fast_forward"), so the track record k and the look-alike model learn from it, and a
customer memory entry (out/customer_memory.jsonl, rule MEMORY) that pauses the offer for that customer, so the
next decision moves on: bought → 365 days, dismissed → 90, no response → 30.
"""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timedelta

from nba.ai.feedback import append_memory, load_memory
from nba.engine.propensity import p_accept

SOURCE = "campaign_fast_forward"
HORIZON_DAYS = 14
# What a sent customer's outcome teaches the engine about that customer: (reason_code, days the offer pauses)
PAUSE = {"bought": ("already_has_product", 365), "dismissed": ("not_relevant", 90), "no_response": ("wrong_timing", 30)}


def _rng(campaign: str, cid: str) -> random.Random:
    # Same campaign and customer → same outcome, on every machine (str seeds are hashed with SHA-512).
    return random.Random(f"{campaign}|{cid}")


def simulate(rt, campaign: str, members: list[dict], at: datetime) -> list[dict]:
    """One outcome per member: {customer_id, tuple_id, contacted, ...}; control members have no outcome."""
    out = []
    for m in members:
        cid, tid = m["customer_id"], m["tuple_id"]
        row = {"customer_id": cid, "tuple_id": tid, "contacted": not m.get("holdout")}
        if m.get("holdout"):
            out.append({**row, "status": "control"})
            continue
        card = rt.card(cid) if cid in rt.states else None
        c = next((x for x in card.candidates if x.tuple_id == tid), None) if card else None
        v = c.valuation if c else None
        if v is None:
            out.append({**row, "status": "not_valued"})  # unknown customer, or the action is no longer a candidate
            continue
        rng = _rng(campaign, cid)
        bought = rng.random() < v.p_accept
        hours = rng.uniform(1, 72) if bought else rng.uniform(1, HORIZON_DAYS * 24)
        response = "clicked" if bought else rng.choice(["ignored", "ignored", "dismissed", "viewed"])
        after = v.clv_after_accept if bought else v.clv_after_reject
        out.append({**row, "status": "bought" if bought else "not_bought", "response": response,
                    "response_at": (at + timedelta(hours=hours)).isoformat() if response != "ignored" else None,
                    "p": round(v.p_accept, 4), "expected_delta_clv": round(v.delta_clv, 2),
                    "actual_delta_clv": round(after - v.clv_now_model - v.contact_cost, 2),
                    "conversion_value_eur": round(max(v.clv_after_accept - v.clv_after_reject, 1.0), 2) if bought else None})
    return out


def history_rows(record: dict) -> list[dict]:
    """The nba_action_history rows of one stored fast-forward (simulated sends only)."""
    at = datetime.fromisoformat(record["sent_at"])
    rows = []
    for o in record["outcomes"]:
        if o["status"] not in {"bought", "not_bought"}:
            continue
        offer, channel, tone = o["tuple_id"].split("|")
        rows.append({"action_id": f"{record['campaign']}:{o['customer_id']}", "customer_id": o["customer_id"],
                     "decided_at": at, "decision_source": SOURCE, "rule_id": record["campaign"], "offer_id": offer,
                     "channel": channel, "tonality": tone, "content_variant": "A", "control_group": False,
                     "delivery_status": "delivered", "response": o["response"],
                     "response_at": datetime.fromisoformat(o["response_at"]) if o.get("response_at") else None,
                     "converted_within_14d": o["status"] == "bought", "conversion_value_eur": o["conversion_value_eur"],
                     "consent_checked": True})
    return rows


def with_outcomes(rt, records: list[dict]):
    """A copy of the runtime whose history also holds these fast-forwards; k and (when the runtime has one) the
    look-alike model are refit."""
    rows = [r for rec in records for r in history_rows(rec)]
    if not rows:
        return rt
    from nba.engine.runtime import Runtime
    from nba.learn.evidence import load_settings
    from nba.learn.lookalike import attach

    cfg = replace(rt.cfg, history=[*rt.cfg.history, *rows], _history_index=None, _versions=None, lookalike=None)
    out = Runtime(rt.tables, rt.states, rt.pop, rt.policy, cfg)
    return attach(out, load_settings()) if rt.cfg.lookalike is not None else out


def totals(outcomes: list[dict]) -> dict:
    sent = [o for o in outcomes if o["status"] in {"bought", "not_bought"}]
    return {"members": len(outcomes), "contacted": sum(o["contacted"] for o in outcomes), "simulated": len(sent),
            "control": sum(o["status"] == "control" for o in outcomes),
            "not_valued": sum(o["status"] == "not_valued" for o in outcomes),
            "bought": sum(o["status"] == "bought" for o in outcomes),
            "expected_bought": round(sum(o["p"] for o in sent), 2),
            "expected_delta_clv": round(sum(o["expected_delta_clv"] for o in sent), 2),
            "actual_delta_clv": round(sum(o["actual_delta_clv"] for o in sent), 2)}


def learned(before, after, outcomes: list[dict]) -> list[dict]:
    """Track record k per offer × channel × tone of the campaign, before and after its outcomes were added."""
    out = []
    for tid in sorted({o["tuple_id"] for o in outcomes if o["status"] in {"bought", "not_bought"}}):
        offer, channel, tone = tid.split("|")
        b = p_accept(offer, channel, tone, before.cfg.history, before.cfg)
        a = p_accept(offer, channel, tone, after.cfg.history, after.cfg)
        if a.k is None:  # not calibrated (service assumption, calibration off): nothing to learn here
            continue
        out.append({"tuple_id": tid, "k_before": round(b.k, 3) if b.k is not None else None,
                    "k_after": round(a.k, 3) if a.k is not None else None, "p_before": round(b.p_accept, 4), "p_after": round(a.p_accept, 4),
                    "bought": a.k_actual, "expected": round(a.k_expected, 2)})
    return out


def memory_entries(record: dict, memory: dict[str, list[dict]]) -> list[dict]:
    """Customer memory for the sends of one fast-forward that are not remembered yet (source_ref = campaign:customer)."""
    seen = {m.get("source_ref") for ms in memory.values() for m in ms}
    since = datetime.fromisoformat(record["sent_at"])
    out = []
    for o in record["outcomes"]:
        ref = f"{record['campaign']}:{o['customer_id']}"
        if o["status"] not in {"bought", "not_bought"} or ref in seen:
            continue
        offer = o["tuple_id"].split("|")[0]
        result = "bought" if o["status"] == "bought" else "dismissed" if o.get("response") == "dismissed" else "no_response"
        code, days = PAUSE[result]
        n = len(memory.get(o["customer_id"], [])) + sum(m["customer_id"] == o["customer_id"] for m in out) + 1
        out.append({"id": f"M-{o['customer_id']}-{n}", "customer_id": o["customer_id"], "kind": "pause_offer",
                    "offer_id": offer, "channel": None, "since": since.isoformat(),
                    "until": (since + timedelta(days=days)).isoformat(), "reason_code": code, "source": "campaign_outcome",
                    "source_ref": ref, "note": f"campaign {record['campaign']}: {result.replace('_', ' ')}", "by": "rule",
                    "predicted_delta_clv": o.get("expected_delta_clv"),
                    "outcome": {"converted": o["status"] == "bought", "actual_delta_clv": o.get("actual_delta_clv")}})
    return out


def remember(records: list[dict], memory_path) -> list[dict]:
    """Append the missing memory entries of these fast-forwards (idempotent: run on every start, so a crash between
    the two files, or a fast-forward stored before memory existed, is repaired). Returns the new entries."""
    memory = load_memory(memory_path)
    new = []
    for record in records:
        added = memory_entries(record, memory)
        for m in added:
            memory.setdefault(m["customer_id"], []).append(m)
        new += added
    append_memory(memory_path, new)
    return new
