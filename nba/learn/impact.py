"""What the feedback loop learned and how it changes decisions (GET /api/learn/impact, learn_impact.json,
the Knowledge Base "Learning" view).

Three runs of the same engine on the same data:
  baseline  nothing learned: no customer memory, k = 1 (calibration off), no look-alike lift
  evidence  + what the outcomes taught: k per offer × channel × tone and the look-alike lift (both scale p)
  learned   + customer memory from feedback (the run the cards use)
A decision that differs between baseline and evidence is caused by the evidence; one that differs between
evidence and learned by the memory. ΔCLV = p·(CLV_buy − CLV_no) + (CLV_no − CLV_now) − cost is linear in p,
so a change of p by Δp moves ΔCLV by Δp × (CLV_buy − CLV_no).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import replace

from nba.ai.feedback import active
from nba.contracts import NO_ACTION
from nba.engine.propensity import _index, p_accept

LIFT = re.compile(r"chance ×([\d.]+)")


def runs(rt):
    """(baseline, evidence, learned) runtimes over the same states."""
    from nba.engine.runtime import Runtime

    cfg = rt.cfg
    no_k = cfg.with_settings(calibration={**(cfg.settings.get("calibration") or {}), "active": False})
    baseline = Runtime(rt.tables, rt.states, rt.pop, rt.policy, replace(no_k, lookalike=None, memory={}))
    evidence = Runtime(rt.tables, rt.states, rt.pop, rt.policy, replace(cfg, memory={}))
    return baseline, evidence, rt


def decision(card, tuple_id: str | None = None) -> dict:
    """The chosen action (or `tuple_id`) of a card with the values that make its ΔCLV."""
    tid = tuple_id or card.chosen.tuple_id
    c = next((x for x in card.candidates if x.tuple_id == tid), None)
    v = c.valuation if c else None
    lift = next((float(m.group(1)) for w in (c.why if c else []) if (m := LIFT.search(w))), None)
    return {"tuple": tid, "waits_until": card.chosen.deferred_until if tuple_id is None else None,
            "p": round(v.p_accept, 4) if v else None, "k": v.p_source.k if v else None, "lift": lift,
            "delta_clv": round(v.delta_clv, 2) if v else None,
            "clv_buy": round(v.clv_after_accept, 2) if v else None, "clv_no": round(v.clv_after_reject, 2) if v else None,
            "reason": card.chosen.reason_line if tuple_id is None and tid == NO_ACTION else None}


def _eur(x) -> str:
    return "–" if x is None else f"€{x:,.2f}"


def _name(t: str, names: dict) -> str:
    if t == NO_ACTION:
        return "no action"
    offer, channel, _tone = (t.split("|") + ["", ""])[:3]
    return f"{names.get(offer, offer)} by {channel.replace('_', ' ')}"


def _moved(label: str, old: dict, new: dict) -> str:
    """'StromGarant by newsletter email: track record ×0.73, chance 7.91% → 5.80%, ΔCLV €13.19 → €9.67'."""
    k, lift = new.get("k"), new.get("lift")
    lever = f"track record ×{k:.2f}" if k and abs(k - 1) >= 0.01 else f"look-alike lift ×{lift:.2f}" if lift else "learned chance"
    out = f"{label}: {lever}"
    if old.get("p") is not None and new.get("p") is not None:
        out += f", chance {old['p']:.2%} → {new['p']:.2%}"
    if old.get("delta_clv") is not None and new.get("delta_clv") is not None:
        out += f", ΔCLV {_eur(old['delta_clv'])} → {_eur(new['delta_clv'])}"
    return out


def explain(cause: str, before: dict, after: dict, was: dict, card, names: dict, winner_was: dict | None = None) -> str:
    """One sentence a demo audience can follow: what was learned, which value moved, what won."""
    if cause == "memory":
        hits = [r for r in (card.rules.results if card.rules else []) if r.rule_id == "MEMORY"]
        why = (hits[0].detail or "").split(":")[-1].strip() if hits else "earlier feedback"
        why = re.sub(r"\s*\(M-[^)]*\)", "", why).replace("_", " ") or "earlier feedback"
        wait = f", until {after['waits_until'][:10]}" if after.get("waits_until") and before["tuple"] == after["tuple"] else ""
        return (f"Customer memory ({why}) holds back {_name(before['tuple'], names)}{wait}; "
                + ("the decision now waits." if before["tuple"] == after["tuple"] else f"next best: {_name(after['tuple'], names)}"
                   + (f" (ΔCLV {_eur(after['delta_clv'])})." if after.get("delta_clv") is not None else ".")))
    if was.get("p") is None and before["tuple"] != NO_ACTION:  # the old choice is now stopped by a rule (e.g. B-08's €10 call floor)
        head = f"{_name(before['tuple'], names)}: the learned chance pulls its ΔCLV below a rule threshold"
        return f"{head}; " + ("no action is worth it any more." if after["tuple"] == NO_ACTION
                              else f"{_name(after['tuple'], names)} wins with ΔCLV {_eur(after['delta_clv'])}.")
    old_fell = was.get("p") is not None and before.get("p") is not None and abs(was["p"] - before["p"]) > 1e-6
    if old_fell or not winner_was or after["tuple"] == NO_ACTION:
        moved = _moved(_name(before["tuple"], names), before, was)
    else:  # the old choice kept its chance: the winner's went up
        moved = _moved(_name(after["tuple"], names), winner_was, after)
        return f"{moved}; it now beats {_name(before['tuple'], names)} (ΔCLV {_eur(before['delta_clv'])})."
    if after["tuple"] == NO_ACTION:
        return f"{moved}; no action is worth it any more ({after.get('reason') or 'below a rule threshold'})."
    return f"{moved}; {_name(after['tuple'], names)} wins with ΔCLV {_eur(after['delta_clv'])}."


def k_table(rt, top: int = 15) -> list[dict]:
    """Calibration per offer × channel × tone: buys observed vs buys the model expected, and k."""
    index = _index(rt.cfg.history, rt.cfg)
    rows = []
    for key, (n, _conv) in index.treated.items():
        if len(key) != 3 or not n:
            continue
        prop = p_accept(*key, rt.cfg.history, rt.cfg)
        if prop.k is None or abs(prop.k - 1) < 0.01:
            continue
        rows.append({"offer": key[0], "channel": key[1], "tone": key[2], "sends": n, "bought": prop.k_actual,
                     "expected": round(prop.k_expected, 2), "k": round(prop.k, 3)})
    rows.sort(key=lambda r: (-abs(math.log(r["k"])), r["offer"], r["channel"], r["tone"]))
    return rows[:top]


def learning_impact(rt, examples: int = 60, customer_ids=None) -> dict:
    baseline, evidence, learned = runs(rt)
    names = {oid: o.name for oid, o in rt.policy.offers.items()}
    changes, totals = [], {"baseline": 0.0, "evidence": 0.0, "learned": 0.0}
    for cid in sorted(rt.states if customer_ids is None else customer_ids):
        b, e, l = baseline.card(cid), evidence.card(cid), learned.card(cid)
        db, de, dl = decision(b), decision(e), decision(l)
        for name, d in (("baseline", db), ("evidence", de), ("learned", dl)):
            totals[name] += d["delta_clv"] or 0.0
        for cause, before, after, card in (("evidence", db, de, e), ("memory", de, dl, l)):
            if (before["tuple"], before["waits_until"]) == (after["tuple"], after["waits_until"]):
                continue
            was = decision(card, before["tuple"]) if before["tuple"] != NO_ACTION else {}
            winner_was = decision(b, after["tuple"]) if cause == "evidence" and after["tuple"] != NO_ACTION else None
            changes.append({"customer_id": cid, "cause": cause, "before": before, "after": after, "before_now": was,
                            "winner_before": winner_was,
                            "sentence": explain(cause, before, after, was, card, names, winner_was)})
    memory = [m for ms in (rt.cfg.memory or {}).values() for m in ms]
    at = next(iter(rt.states.values())).eval_time
    from nba.learn.lookalike import summary as lookalike_summary

    look = lookalike_summary(rt.cfg.lookalike)
    return {
        "formula": "ΔCLV = p·(CLV_buy − CLV_no) + (CLV_no − CLV_now) − cost; p = rate × k × lift",
        "summary": {"customers": len(rt.states if customer_ids is None else customer_ids), "changed": len(changes),
                    "by_cause": dict(Counter(c["cause"] for c in changes)),
                    "delta_clv": {k: round(v, 2) for k, v in totals.items()}},
        "k": k_table(rt),
        "memory": {"entries": len(memory), "active": sum(active(m, at) for m in memory),
                   "by_kind": dict(Counter(m.get("kind") for m in memory)), "by_source": dict(Counter(m.get("source") for m in memory))},
        "lookalike": {"active": look.get("active", False),
                      "offers": [{"offer": o, "name": names.get(o, o), "recipients": v["recipients"], "buyers": v["buyers"],
                                  "more_likely": v["more_likely"], "less_likely": v["less_likely"],
                                  "scored": v["customers_scored"], "profile": v["profile"][:3]}
                                 for o, v in (look.get("offers") or {}).items()]},
        "changes": changes[:examples],
    }


def feedback_impact(before_rt, after_rt, customer_ids) -> list[dict]:
    """Decisions that a feedback step just changed (POST /api/ai/feedback), customer by customer."""
    names = {oid: o.name for oid, o in after_rt.policy.offers.items()}
    out = []
    for cid in sorted(set(customer_ids)):
        if cid not in after_rt.states:
            continue
        b, a = decision(before_rt.card(cid)), decision(after_rt.card(cid))
        if (b["tuple"], b["waits_until"]) == (a["tuple"], a["waits_until"]):
            continue
        card = after_rt.card(cid)
        out.append({"customer_id": cid, "cause": "memory", "before": b, "after": a,
                    "sentence": explain("memory", b, a, {}, card, names)})
    return out
