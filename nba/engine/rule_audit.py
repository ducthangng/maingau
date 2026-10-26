"""Legacy audit (docs/rule-center.md §8): run today's rules over every past send in nba_action_history.

Owner: Agent NBA. Each delivered, non-control action is checked at its own send time (decided_at): which
Rule Center rules would have stopped it. Approximations are listed in `notes` (consent_status and the
contract tables hold only the latest state).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from nba.kg.contacts import contact_events, window

EPS = timedelta(microseconds=1)  # the send itself is not part of its own contact window
AVAILABILITY = "C-01 (no app / portal)"
NOTES = [
    "consent_status holds only the latest status: a consent withdrawn after the send counts as granted then; "
    "one never granted counts as missing",
    "customer_master (app, portal) and energy_contracts (dunning, cancellation) are the current state",
    "complaints use created_at / resolved_at, so an open complaint is exact at send time",
]
NOT_AUDITED = ["B-07 (holdings at send time are unknown)", "B-08 (needs today's valuation)", "B-09 (weekly plan)"]


def _consent_at(consent: dict, ctype: str, ts) -> bool:
    r = consent.get(ctype)
    if r is None or r.get("status") == "granted":
        return r is not None  # latest status granted: assume granted at the send
    return r.get("status") == "withdrawn" and r.get("updated_at") is not None and r["updated_at"] > ts


def audit_send(row: dict, state, policy, rules) -> list[str]:
    """Rule Center IDs that would have stopped this send."""
    ts, ch, rows = row["decided_at"], row.get("channel"), state.rows
    consent = {r["consent_type"]: r for r in rows["consent_status"]}
    master = state.one("customer_master") or {}
    out: list[str] = []
    spec = policy.channels.get(ch)
    if spec is not None:
        granted = _consent_at(consent, spec.consent, ts)
        if not granted:
            out.append("C-01")
        if spec.requires_field and not master.get(spec.requires_field):
            out.append(AVAILABILITY)
        doi = (consent.get(spec.consent) or {}).get("double_opt_in_confirmed_at")
        if spec.needs_doi and granted and (doi is None or doi > ts):
            out.append("C-02")
        if spec.consent == "newsletter_email" and any(
                r.get("unsubscribed") and r.get("campaign_sent_at") and r["campaign_sent_at"] <= ts
                for r in rows["newsletter_performance"]):
            out.append("C-03")
    if any((r.get("dunning_level") or 0) >= 1 for r in rows["energy_contracts"]):
        out.append("C-06")
    if any(r.get("category") == "complaint" and r.get("created_at") and r["created_at"] <= ts
           and (r.get("resolved_at") is None or r["resolved_at"] > ts) for r in rows["service_interactions"]):
        out.append("C-07")
    if any(r.get("status") == "cancellation_pending" and (r.get("cancellation_received_at") or ts) <= ts
           for r in rows["energy_contracts"]) or any(r.get("status") == "cancelled" for r in rows["autostrom_contracts"]):
        out.append("C-08")
    limit, days = policy.contact_cap
    cap_events = [e for e in contact_events(state, policy.contact_cap_sources) if e.channel != policy.service_channel]
    if len(window(cap_events, days, ts - EPS)) >= limit:
        out.append("B-02")
    for rule in rules:
        if not rule.active:
            continue
        p = rule.params
        if rule.kind == "channel_frequency" and ch in p["channels"]:
            if len(window(contact_events(state, p["sources"]), p["window_days"], ts - EPS, p["channels"])) >= p["max"]:
                out.append(rule.id)
        elif rule.kind == "offer_cooldown":
            times = sorted(t for r in rows["nba_action_history"] if r.get("offer_id") == row.get("offer_id")
                           and r.get("response") in p["responses"]
                           for t in [r.get("response_at") or r.get("decided_at")] if t is not None and t < ts)
            if len(times) >= p["min_responses"] and times[-1] + timedelta(days=p["cooldown_days"]) > ts:
                out.append(rule.id)
        elif rule.kind == "post_ticket_cooldown":
            if any(r.get("resolved_at") and r["resolved_at"] <= ts < r["resolved_at"] + timedelta(days=p["cooldown_days"])
                   for r in rows["service_interactions"]):
                out.append(rule.id)
    return out


def legacy_audit(runtime) -> dict:
    """How many past sends today's rules would have stopped, per rule and per channel."""
    by_rule, by_channel, examples = Counter(), defaultdict(Counter), []
    sends = stopped = tier1 = 0
    for cid, state in sorted(runtime.states.items()):
        for row in sorted(state.rows["nba_action_history"], key=lambda r: (r.get("decided_at"), r.get("action_id"))):
            if row.get("delivery_status") != "delivered" or row.get("control_group") or row.get("decided_at") is None:
                continue
            sends += 1
            hits = audit_send(row, state, runtime.policy, runtime.cfg.rules)
            if not hits:
                continue
            stopped += 1
            tier1 += any(h.startswith("C-") for h in hits)
            by_rule.update(hits)
            by_channel[row.get("channel")].update(hits)
            if len(examples) < 10:
                examples.append({"customer_id": cid, "action_id": row.get("action_id"), "offer_id": row.get("offer_id"),
                                 "channel": row.get("channel"), "decided_at": row["decided_at"].isoformat(), "rules": hits})
    return {"sends": sends, "would_be_stopped": stopped, "stopped_by_compliance": tier1,
            "by_rule": dict(sorted(by_rule.items())),
            "by_channel": {ch: dict(sorted(c.items())) for ch, c in sorted(by_channel.items())},
            "examples": examples, "notes": NOTES, "not_audited": NOT_AUDITED}
