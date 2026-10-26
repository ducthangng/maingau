"""What-if for a Rule Center edit (docs/rule-center.md §5): every customer decided under the current rules
and under the proposed ones. Owner: Agent NBA. Nothing is saved."""
from __future__ import annotations

from collections import Counter

from nba.contracts import NO_ACTION

HELD = {"BUSINESS-RULE", "CONTACT-CAP"}  # tier 2 rows on the card (blocked, or waiting when `until` is set)


def _decision(card) -> str:
    wait = card.chosen.deferred_until
    return f"{card.chosen.tuple_id}@{wait[:10]}" if wait else card.chosen.tuple_id


def _value(card) -> float | None:
    c = next((x for x in card.candidates if x.tuple_id == card.chosen.tuple_id), None)
    return c.valuation.delta_clv if c and c.valuation else None


def _totals(cards) -> dict:
    by_channel, by_offer, by_rule = Counter(), Counter(), Counter()
    now = waiting = 0.0
    for card in cards:
        for b in card.blocked:
            if b.rule_id in HELD and b.offer_id != "*":
                by_channel[b.channel or "*"] += 1
                by_offer[b.offer_id] += 1
        for r in card.rules.results if card.rules else []:
            if r.result in {"block", "defer"} and r.tier != "compliance":
                by_rule[r.rule_id] += 1
        value = _value(card) or 0.0
        if card.chosen.tuple_id != NO_ACTION:
            if card.chosen.deferred_until:
                waiting += value
            else:
                now += value
    return {"held_tuples_by_channel": dict(sorted(by_channel.items())), "held_tuples_by_offer": dict(sorted(by_offer.items())),
            "customers_by_rule": dict(sorted(by_rule.items())),
            "act_now": sum(1 for c in cards if c.chosen.tuple_id != NO_ACTION and not c.chosen.deferred_until),
            "waiting": sum(1 for c in cards if c.chosen.deferred_until),
            "no_action": sum(1 for c in cards if c.chosen.tuple_id == NO_ACTION),
            "sum_delta_clv_now": round(now, 2), "sum_delta_clv_waiting": round(waiting, 2)}


def what_if(current, proposed, examples: int = 10) -> dict:
    """Customers whose decision changes (tuple or waiting date), rule hits and totals before vs after."""
    before, after = current.cards(), proposed.cards()
    changed = []
    for b, a in zip(before, after):
        if _decision(b) != _decision(a):
            changed.append({"customer_id": b.customer_id, "before": _decision(b), "after": _decision(a),
                            "delta_clv_before": _value(b), "delta_clv_after": _value(a), "reason_after": a.chosen.reason_line})
    changed.sort(key=lambda r: (-abs((r["delta_clv_after"] or 0) - (r["delta_clv_before"] or 0)), r["customer_id"]))
    return {"customers": len(before), "changed": len(changed), "examples": changed[:examples],
            "rule_set_version": {"before": current.cfg.versions(current.policy).rules,
                                 "after": proposed.cfg.versions(proposed.policy).rules},
            "before": _totals(before), "after": _totals(after)}
