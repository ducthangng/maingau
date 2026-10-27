"""AI step 1: check each cluster of proposed actions before a person approves them in bulk.

A cluster is the customers who got the same proposed action (offer × channel × tone) in the same segment.
Code decides first: warning flags, the "do no harm" segment, customer memory from feedback, a low
calibration factor and numeric outliers inside the cluster move a customer to "needs review"; everyone
else is "ready" for bulk approval. The AI then reads only the flagged customers (their KG evidence, value
and rules), explains each one, and settles the soft cases (borderline outliers). It can never clear a hard
flag and never sends anything.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from nba.ai.llm import LLM
from nba.contracts import NO_ACTION

HARD_FLAGS = {"service_critical", "negative_clv", "data_inconsistent", "annoyed_before"}
SOFT_FLAGS = {"contact_fatigue"}  # contact limits B-01 / B-02 already apply; the AI (or a person) judges the rest
REASON_CODES = ["flag_service_critical", "flag_negative_clv", "flag_data_inconsistent", "flag_contact_fatigue",
                "flag_annoyed_before", "segment_do_no_harm", "customer_memory", "calibration_low",
                "outlier_delta_clv", "outlier_p", "outlier_churn", "need_mismatch", "other"]
SALES = {"sales", "upsell", "one_off"}
HARD_Z, SOFT_Z, MIN_CLUSTER, LOW_K = 3.5, 2.5, 5, 0.85

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["needs_review", "fits_cluster"]},
        "reason_code": {"type": "string", "enum": REASON_CODES},
        "note": {"type": "string"},
        "cited": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "reason_code", "note", "cited"],
    "additionalProperties": False,
}
SYSTEM = (
    "You check a customer before a marketer approves a group of identical offers in bulk. You get the group "
    "(cluster), the customer's evidence from the knowledge graph, the value of the proposed action and the "
    "reasons code flagged. Decide whether this customer fits the group (fits_cluster) or needs an individual "
    "decision (needs_review). Pick the reason_code that explains it. Write a note of at most two sentences a "
    "marketer can act on, in English. In `cited`, list only IDs that appear in `allowed_ids`. Never propose "
    "sending anything and never argue against a compliance rule."
)


def _robust_z(values: list[float]) -> tuple[float, float] | None:
    if len(values) < MIN_CLUSTER:
        return None
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values) * 1.4826
    return (med, mad) if mad > 0 else None


def _chosen(card):
    return next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)


def _pack(card, cand, cluster, reasons, memory) -> dict:
    """The evidence the AI may use: graph facts with IDs, the value, the rules and the code's reasons."""
    allowed = sorted({s.id for s in card.signals} | {f.id for f in card.triage.flags} | {cand.offer_id, cand.channel}
                     | {r.rule_id for r in (card.rules.results if card.rules else [])})
    v = cand.valuation
    return {
        "customer_id": card.customer_id,
        "cluster": cluster,
        "proposed": {"offer": cand.offer_id, "name": cand.offer_name, "channel": cand.channel, "tone": cand.tone,
                     "action_type": cand.action_type, "delta_clv_eur": round(v.delta_clv, 2), "p": round(v.p_accept, 4),
                     "confidence": v.confidence, "k": v.p_source.k, "why": cand.why[:2]},
        "segment": {"archetype": card.triage.archetype.id, "name": card.triage.archetype.name,
                    "urgency": card.triage.urgency_tier, "reasons": card.triage.urgency_reasons[:3]},
        "flags": [{"id": f.id, "detail": f.detail} for f in card.triage.flags],
        "signals": [{"id": s.id, "label": s.label, "detail": s.detail} for s in card.signals],
        "rules": [{"id": r.rule_id, "result": r.result, "detail": r.detail}
                  for r in (card.rules.results if card.rules else []) if r.result in {"block", "defer"}],
        "memory": memory,
        "code_reasons": reasons,
        "allowed_ids": allowed,
    }


def review(runtime, llm: LLM | None = None, ai_limit: int = 80) -> dict:
    """Clusters of act-now proposals with each customer's status; AI notes where a backend is available."""
    llm = llm or LLM()
    cards = runtime.cards()
    memory = getattr(runtime.cfg, "memory", None) or {}
    rows = []
    for card in cards:
        cand = _chosen(card)
        if not cand or card.chosen.tuple_id == NO_ACTION or card.chosen.deferred_until or cand.action_type == "service":
            continue  # waiting, no action and service-first cases are handled elsewhere
        rows.append((card, cand, (card.chosen.tuple_id, card.triage.archetype.id)))
    clusters = defaultdict(list)
    for row in rows:
        clusters[row[2]].append(row)

    out_clusters, customers, ai_queue = [], {}, []
    for (tuple_id, archetype), members in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        offer, channel, tone = tuple_id.split("|")
        metrics = {
            "delta_clv": [m[1].valuation.delta_clv for m in members],
            "p": [m[1].valuation.p_accept for m in members],
            "churn": [float(m[0].profile.value_risk.churn_prob_12m.v or 0) for m in members],
        }
        stats = {k: _robust_z(v) for k, v in metrics.items()}
        info = {"key": f"{tuple_id}·{archetype}", "offer": offer, "channel": channel, "tone": tone, "archetype": archetype,
                "size": len(members), "median_delta_clv": round(statistics.median(metrics["delta_clv"]), 2)}
        for i, (card, cand, _) in enumerate(members):
            hard, soft = [], []
            for f in card.triage.flags:
                if f.id in HARD_FLAGS | SOFT_FLAGS:
                    (hard if f.id in HARD_FLAGS else soft).append({"code": f"flag_{f.id}", "detail": f.detail or f.label})
            if archetype == "A4" and cand.action_type in SALES:
                hard.append({"code": "segment_do_no_harm", "detail": "retention-risk segment: sales offer needs a person"})
            notes = [m for m in memory.get(card.customer_id, []) if m.get("kind") == "review"]
            if notes:
                hard.append({"code": "customer_memory", "detail": notes[-1].get("note") or notes[-1].get("reason_code")})
            k = cand.valuation.p_source.k
            if k is not None and k < LOW_K:
                soft.append({"code": "calibration_low", "detail": f"this offer × channel × tone sells below forecast (k {k:.2f})"})
            for name, st in stats.items():
                if st is None:
                    continue
                z = abs(metrics[name][i] - st[0]) / st[1]
                item = {"code": f"outlier_{name}", "detail": f"{name} {metrics[name][i]:.3f} vs cluster median {st[0]:.3f} (z {z:.1f})"}
                if z >= SOFT_Z:  # a very different value or chance is hard; an unusual churn risk is for judgement
                    (hard if z >= HARD_Z and name != "churn" else soft).append(item)
            status = "needs_review" if hard or soft else "ready"
            customers[card.customer_id] = {"status": status, "cluster": info["key"], "hard": hard, "soft": soft, "ai": None}
            if hard or soft:
                ai_queue.append((cand.valuation.delta_clv, card, cand, info, hard + soft))
        out_clusters.append(info)

    ai_queue.sort(key=lambda q: (-q[0], q[1].customer_id))
    reviewed = skipped = 0
    for _, card, cand, info, reasons in ai_queue:
        if not llm.enabled or reviewed >= ai_limit:
            skipped += 1
            continue
        pack = _pack(card, cand, info, reasons, memory.get(card.customer_id, []))
        answer = llm.structured(SYSTEM, pack, SCHEMA, effort="low")
        if not answer or answer.get("reason_code") not in REASON_CODES:
            skipped += 1
            continue
        reviewed += 1
        cited = [c for c in answer.get("cited", []) if c in pack["allowed_ids"]]  # drop IDs the evidence does not hold
        entry = customers[card.customer_id]
        entry["ai"] = {"verdict": answer["verdict"], "reason_code": answer["reason_code"],
                       "note": str(answer.get("note", ""))[:400], "cited": cited}
        if not entry["hard"]:  # the AI settles soft cases only; a hard flag always stays with a person
            entry["status"] = "needs_review" if answer["verdict"] == "needs_review" else "ready"
    for info in out_clusters:
        members = [c for c in customers.values() if c["cluster"] == info["key"]]
        info["ready"] = sum(c["status"] == "ready" for c in members)
        info["needs_review"] = len(members) - info["ready"]
    return {
        "clusters": out_clusters,
        "customers": customers,
        "summary": {"proposals": len(customers), "ready": sum(c["status"] == "ready" for c in customers.values()),
                    "needs_review": sum(c["status"] == "needs_review" for c in customers.values()),
                    "clusters": len(out_clusters)},
        "ai": {"backend": llm.name if llm.enabled else "none", "reviewed": reviewed, "not_reviewed": skipped,
               "limit": ai_limit},
    }
