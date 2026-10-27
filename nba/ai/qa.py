"""AI test harness for the whole NBA workflow: python -m nba.ai qa (tests/test_ai_qa.py).

Three AI roles work on the real pipeline; code oracles decide what passes.
- Tester: proposes scenarios. A scenario is a change to one customer, written as events of the real event
  stream (ticket, dunning, cancellation, consent, charging failures, gas meter, order). The values are taken
  from the ontology and the data, so the tester cannot invent a rule, signal or customer. Code applies the
  events (nba.kg.events.replay) and decides the customer again (nba.engine.assemble).
- Marketer: approves or rejects proposals through the API. Code then runs the feedback step and checks that
  a rejected offer does not come back. It also checks the journey, the Overview fields and the cluster review.
- Judge: reads each before/after pair and says whether the change is explainable. It flags suspicious cases
  for a person and must cite IDs from the evidence.
Oracles are the ground truth: hard rules (C-01..C-09), "nothing is sent without approval", positive value,
and the expected effect of each event. AI expectations that disagree with the result become findings for a
person. The AI can never clear an oracle failure.
Without a backend, the tester uses the seed scenarios, the marketer a fixed policy, and the judge is skipped.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from pathlib import Path

from nba.ai.llm import LLM
from nba.contracts import NO_ACTION, CustomerCard
from nba.engine.assemble import assemble
from nba.kg.events import replay

EVENT_TYPES = ["ticket_created", "dunning_level_changed", "contract_cancellation_received", "consent_changed",
               "charge_session_failed", "gas_meter_deregistration_received", "order_placed"]
CONSENT_TYPES = ["newsletter_email", "marketing_email", "marketing_phone", "marketing_sms",
                 "portal_app_personalisation", "profiling_analytics"]
CONSENT_STATUS = ["granted", "withdrawn", "not_given"]
TICKET_CATEGORIES = ["complaint", "billing", "tariff", "moving", "autostrom", "meter", "mobile", "hems"]
TICKET_CHANNELS = ["phone", "email", "chat", "portal_form"]
SALES = {"sales", "upsell", "retention", "one_off"}
EXCLUSION_RULE = {"ticket_created": "EXCL-OPEN-TICKET", "dunning_level_changed": "EXCL-DUNNING",
                  "contract_cancellation_received": "EXCL-CANCELLATION"}
JUDGE_CODES = ["ok", "engine_bug", "expectation_wrong", "data_gap", "explanation_unclear"]


@dataclass
class Scenario:
    id: str
    customer_id: str
    event_type: str
    params: dict
    story: str = ""
    source: str = "seed"
    expect: dict = field(default_factory=dict)  # tester's expectation: no_sales, rule, signal (findings only)


# ---------------------------------------------------------------- scenarios → events


def _events(sc: Scenario, state) -> list[dict]:
    """The scenario as events of the real stream (README §7.1 step 5), one hour after the snapshot."""
    t0, p = state.eval_time + timedelta(hours=1), sc.params

    def ev(i, payload, effective=None, at=None):
        occ = at or t0
        return {"event_id": f"QA-{sc.id}-{i}", "event_type": sc.event_type, "source_system": "ai_qa",
                "customer_id": sc.customer_id, "occurred_at": occ, "ingested_at": occ + timedelta(seconds=30),
                "payload": payload, "effective_date": effective}

    t = sc.event_type
    if t == "ticket_created":
        return [ev(0, {"category": p.get("category", "complaint"), "channel": p.get("channel", "phone"),
                       "message_text": sc.story or "test ticket"})]
    if t == "dunning_level_changed":
        old = max([r.get("dunning_level") or 0 for r in state.rows["energy_contracts"]] or [0])
        return [ev(0, {"old_level": old, "new_level": int(p.get("new_level", 2))})]
    if t == "contract_cancellation_received":
        return [ev(0, {"commodity": p.get("commodity", "electricity"), "reason": "ai_qa"})]
    if t == "consent_changed":
        return [ev(0, {"consent_type": p["consent_type"], "new_status": p.get("new_status", "withdrawn"), "source": "ai_qa"})]
    if t == "charge_session_failed":
        return [ev(i, {"charge_type": "AC", "energy_kwh": 0.0, "amount_eur": 0.0, "failure_reason": "connector_error"},
                   at=t0 + timedelta(hours=i)) for i in range(max(1, min(5, int(p.get("count", 3)))))]
    if t == "gas_meter_deregistration_received":
        return [ev(0, {"commodity": "gas"}, effective=t0 + timedelta(days=30))]
    if t == "order_placed":
        return [ev(0, {"product_name": p.get("product_name", "LED-Set 10 Stk")})]
    raise ValueError(f"unknown event type {t}")


def _chosen(card):
    return next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)


def _summary(card) -> dict:
    c = _chosen(card)
    return {"chosen": card.chosen.tuple_id, "action_type": c.action_type if c else None,
            "personalised": c.personalised if c else None, "delta_clv": round(c.valuation.delta_clv, 2) if c and c.valuation else None,
            "why": c.why[0] if c and c.why else card.chosen.reason_line, "deferred_until": card.chosen.deferred_until,
            "signals": sorted(s.id for s in card.signals),
            "rules": sorted({b.rule_id for b in card.blocked} | {b.rule_center_id for b in card.blocked if b.rule_center_id}),
            "exclusions": sorted(e.rule_id for e in card.profile.exclusions if e.active)}


# ---------------------------------------------------------------- oracles (ground truth)


def invariants(card: CustomerCard, policy) -> list[dict]:
    """Checks every decided card must pass, whatever happened to the customer."""
    out = []

    def check(name, ok, detail=""):
        out.append({"check": name, "ok": bool(ok), "detail": detail})

    try:
        CustomerCard.model_validate(card.model_dump())
        check("valid_card", True)
    except Exception as exc:  # noqa: BLE001 - any schema error is a failure
        check("valid_card", False, str(exc)[:200])
    c = _chosen(card)
    if card.chosen.tuple_id == NO_ACTION:
        check("no_action_has_no_candidate_chosen", c is None)
        return out
    check("chosen_is_a_candidate", c is not None, card.chosen.tuple_id)
    if c is None:
        return out
    check("nothing_sent_without_approval", card.chosen.status in (None, "proposed"), str(card.chosen.status))
    check("positive_value_or_service", c.action_type == "service" or (c.valuation and c.valuation.delta_clv > 0),
          f"{c.action_type} ΔCLV {c.valuation.delta_clv if c.valuation else None}")
    excl = [e.rule_id for e in card.profile.exclusions if e.active]
    check("exclusion_means_no_sales", not excl or c.action_type not in SALES, f"{excl} vs {c.action_type}")
    allowed = {ch.channel for ch in card.profile.channels if ch.allowed}
    check("channel_has_consent", c.channel in allowed or c.channel == policy.service_channel, c.channel)
    hard = [b for b in card.blocked if not b.until and b.offer_id in (c.offer_id, "*") and b.channel in (c.channel, None)
            and b.rule_id in {"CONSENT-CHANNEL", "CHANNEL-AVAILABLE"} and (b.channel or b.offer_id != "*")]
    check("chosen_not_blocked", not hard, ", ".join(f"{b.rule_id} {b.offer_id}/{b.channel}" for b in hard))
    if c.personalised:
        prof = next((x for x in card.profile.consent if x.type == "profiling_analytics"), None)
        check("personalised_needs_profiling", prof is not None and prof.effective_status == "granted",
              prof.effective_status if prof else "missing")
    return out


def _effect(sc: Scenario, before, after, statuses: list[str], transitions, policy) -> list[dict]:
    """The expected effect of the scenario's event on the decision (only when the event was applied)."""
    out = []

    def check(name, ok, detail=""):
        out.append({"check": name, "ok": bool(ok), "detail": detail})

    if "applied" not in statuses:
        check("event_not_applicable", True, ", ".join(sorted(set(statuses))))  # e.g. no gas contract: nothing to change
        return out
    a, c = _summary(after), _chosen(after)
    t, p = sc.event_type, sc.params
    rule = EXCLUSION_RULE.get(t)
    if rule and not (t == "dunning_level_changed" and int(p.get("new_level", 2)) < 1):
        check(f"{rule}_active", rule in a["exclusions"], str(a["exclusions"]))
        check("no_sales_after_exclusion", a["action_type"] not in SALES, str(a["action_type"]))
        was_sales = _summary(before)["action_type"] in SALES and not before.chosen.deferred_until
        pend = [tr.pending_status for tr in transitions if tr.pending]
        if was_sales:
            check("pending_sales_card_revoked", "revoked" in pend, str(pend))
    if t == "consent_changed" and p.get("new_status") in {"withdrawn", "not_given"}:
        ctype = p["consent_type"]
        if c:
            needs = policy.channels.get(c.channel).consent if c.channel in policy.channels else None
            check("withdrawn_consent_not_used", needs != ctype, f"{c.channel} needs {needs}")
            if ctype == "profiling_analytics":
                check("no_personalisation_without_profiling", not c.personalised, str(c.personalised))
    if t == "charge_session_failed" and statuses.count("applied") >= 3:
        check("S2_failed_charging_signal", "S2" in a["signals"], str(a["signals"]))
    if t == "gas_meter_deregistration_received":
        check("S1_gas_meter_signal", "S1" in a["signals"], str(a["signals"]))
    return out


def run_scenario(rt, sc: Scenario) -> dict:
    state = rt.states[sc.customer_id]
    before = rt.card(sc.customer_id)
    bc = _chosen(before)
    pending = {sc.customer_id: (before.chosen.tuple_id, bool(bc and bc.personalised), before.chosen.deferred_until)} if bc else {}
    events = _events(sc, state)
    res = replay({sc.customer_id: state}, events, rt.policy, rt.pop, until=events[-1]["ingested_at"], pending=pending)
    statuses = [o.status for o in res.outcomes]
    after = assemble(res.states[sc.customer_id], rt.pop, rt.policy, rt.cfg)
    checks = invariants(after, rt.policy) + _effect(sc, before, after, statuses, res.transitions, rt.policy)
    b, a = _summary(before), _summary(after)
    mismatch = []
    if sc.expect.get("no_sales") and a["action_type"] in SALES:
        mismatch.append(f"tester expected no sales, got {a['action_type']}")
    if sc.expect.get("rule") and sc.expect["rule"] not in a["rules"] + a["exclusions"]:
        mismatch.append(f"tester expected rule {sc.expect['rule']}")
    if sc.expect.get("signal") and sc.expect["signal"] not in a["signals"]:
        mismatch.append(f"tester expected signal {sc.expect['signal']}")
    return {"scenario": asdict(sc), "event_status": statuses, "before": b, "after": a,
            "checks": checks, "passed": all(x["ok"] for x in checks), "mismatch": mismatch, "judge": None}


# ---------------------------------------------------------------- seed scenarios (no AI needed)


def seed_scenarios(rt) -> list[Scenario]:
    """One scenario per event type, on the first customer (by ID) where the event matters."""
    cards = {cid: rt.card(cid) for cid in sorted(rt.states)}

    used: set[str] = set()

    def first(test):  # a different customer for each scenario, so more of the data is exercised
        cid = next((cid for cid, card in cards.items() if cid not in used and test(card, rt.states[cid])), None)
        if cid:
            used.add(cid)
        return cid

    def sales(card, _s):
        c = _chosen(card)
        return c is not None and c.action_type in SALES and not card.chosen.deferred_until

    def active(rows, **kw):
        return [r for r in rows if r.get("status") == "active" and all(r.get(k) == v for k, v in kw.items())]

    out = []

    def add(name, cid, event_type, params, story, expect):
        if cid:
            out.append(Scenario(f"seed-{name}", cid, event_type, params, story, "seed", expect))

    add("ticket", first(lambda c, s: sales(c, s) and not any(r.get("status") == "open" for r in s.rows["service_interactions"])),
        "ticket_created", {"category": "complaint", "channel": "phone"}, "Customer calls to complain about a bill",
        {"no_sales": True, "rule": "EXCL-OPEN-TICKET"})
    add("dunning", first(lambda c, s: sales(c, s) and s.rows["energy_contracts"]
                         and not any((r.get("dunning_level") or 0) for r in s.rows["energy_contracts"])),
        "dunning_level_changed", {"new_level": 2}, "First reminder unpaid; dunning level 2", {"no_sales": True, "rule": "EXCL-DUNNING"})
    add("cancellation", first(lambda c, s: sales(c, s) and active(s.rows["energy_contracts"], commodity="electricity")),
        "contract_cancellation_received", {"commodity": "electricity"}, "Electricity cancellation letter arrives",
        {"no_sales": True, "rule": "EXCL-CANCELLATION"})
    consent_of = {ch: d.consent for ch, d in rt.policy.channels.items()}
    cid = first(lambda c, s: sales(c, s) and _chosen(c).channel in {"email", "newsletter_email", "outbound_call", "sms"})
    if cid:
        add("consent", cid, "consent_changed", {"consent_type": consent_of[_chosen(cards[cid]).channel], "new_status": "withdrawn"},
            "Customer withdraws consent for the channel of the proposal", {})
    add("profiling", first(lambda c, s: sales(c, s) and _chosen(c).personalised),
        "consent_changed", {"consent_type": "profiling_analytics", "new_status": "withdrawn"},
        "Customer withdraws profiling consent", {})
    add("charging", first(lambda c, s: active(s.rows["autostrom_contracts"]) and "S2" not in {x.id for x in c.signals}),
        "charge_session_failed", {"count": 3}, "Three failed charging sessions in one evening", {"signal": "S2"})
    add("gas", first(lambda c, s: active(s.rows["energy_contracts"], commodity="gas")
                     and not any(r.get("meter_deregistered_at") for r in s.rows["energy_contracts"])),
        "gas_meter_deregistration_received", {}, "Gas meter deregistration received (moving to a heat pump?)", {"signal": "S1"})
    add("order", first(sales), "order_placed", {"product_name": "LED-Set 10 Stk"}, "Small shop order", {})
    return out


# ---------------------------------------------------------------- AI tester


TESTER_SYSTEM = (
    "You test a Next Best Action engine for an energy and mobile provider. You get customers with their "
    "knowledge-graph evidence and current proposal, and the event types the system understands. Write test "
    "scenarios: each is ONE change to ONE customer that should matter for the decision, such as a hard rule "
    "that must now block sales, a consent that must stop a channel, or a new need signal. Prefer changes that "
    "probe edge cases (a customer already waiting, a service-only customer, a generic offer). For each, state "
    "your expectation: whether sales must stop, which rule ID should appear and which signal ID should appear "
    "(use 'none' when you do not expect one). Use only the IDs and values given."
)


def _tester_schema(customers: list[str], rules: list[str], signals: list[str], products: list[str]) -> dict:
    scenario = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "enum": customers},
            "event_type": {"type": "string", "enum": EVENT_TYPES},
            "consent_type": {"type": "string", "enum": CONSENT_TYPES + ["none"]},
            "new_status": {"type": "string", "enum": CONSENT_STATUS + ["none"]},
            "ticket_category": {"type": "string", "enum": TICKET_CATEGORIES + ["none"]},
            "ticket_channel": {"type": "string", "enum": TICKET_CHANNELS + ["none"]},
            "commodity": {"type": "string", "enum": ["electricity", "gas", "none"]},
            "new_level": {"type": "integer"},
            "count": {"type": "integer"},
            "product_name": {"type": "string", "enum": products + ["none"]},
            "story": {"type": "string"},
            "expect_no_sales": {"type": "boolean"},
            "expect_rule": {"type": "string", "enum": rules + ["none"]},
            "expect_signal": {"type": "string", "enum": signals + ["none"]},
        },
        "required": ["customer_id", "event_type", "consent_type", "new_status", "ticket_category", "ticket_channel",
                     "commodity", "new_level", "count", "product_name", "story", "expect_no_sales", "expect_rule",
                     "expect_signal"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"scenarios": {"type": "array", "items": scenario}},
            "required": ["scenarios"], "additionalProperties": False}


def _evidence(card, state) -> dict:
    s = _summary(card)
    return {"customer_id": card.customer_id, "segment": card.triage.archetype.name, "proposal": s["chosen"],
            "action_type": s["action_type"], "personalised": s["personalised"], "waiting_until": s["deferred_until"],
            "signals": [{"id": x.id, "label": x.label} for x in card.signals], "exclusions": s["exclusions"],
            "consents": {c.type: c.effective_status for c in card.profile.consent},
            "contracts": sorted({f"{r.get('commodity', 'energy')}:{r.get('status')}" for r in state.rows["energy_contracts"]}
                                | {f"autostrom:{r.get('status')}" for r in state.rows["autostrom_contracts"]}
                                | {f"mobile:{r.get('status')}" for r in state.rows["mobile_contracts"]}),
            "dunning_level": max([r.get("dunning_level") or 0 for r in state.rows["energy_contracts"]] or [0])}


def _pool(rt, size: int) -> list[str]:
    """A spread of customers: by chosen action type and segment, then by ID."""
    seen, pool = set(), []
    for cid in sorted(rt.states):
        card = rt.card(cid)
        s = _summary(card)
        key = (s["action_type"], card.triage.archetype.id, bool(s["deferred_until"]), s["personalised"])
        if key not in seen:
            seen.add(key)
            pool.append(cid)
        if len(pool) >= size:
            break
    return pool


def ai_scenarios(rt, llm: LLM, n: int = 8, pool_size: int = 24, catalog_products: list[str] | None = None) -> tuple[list[Scenario], list[str]]:
    """Scenarios written by the AI tester; invalid ones are dropped with a note."""
    if not llm.enabled:
        return [], ["no AI backend: seed scenarios only"]
    pool = _pool(rt, pool_size)
    products = catalog_products or sorted(rt.tables["shop_orders"]["product_name"].dropna().unique().tolist())
    rules = sorted({*EXCLUSION_RULE.values(), "CONSENT-CHANNEL", "CONSENT-PROFILING", "CONTACT-CAP", "HOLDING-PRECONDITION",
                    *rt.policy.compliance})
    payload = {"customers": [_evidence(rt.card(c), rt.states[c]) for c in pool], "max_scenarios": n,
               "event_types": {"ticket_created": "ticket_category, ticket_channel", "dunning_level_changed": "new_level (0-3)",
                               "contract_cancellation_received": "commodity", "consent_changed": "consent_type, new_status",
                               "charge_session_failed": "count (1-5) failed sessions, one hour apart",
                               "gas_meter_deregistration_received": "-", "order_placed": "product_name"},
               "rules": {k: v.get("label") for k, v in rt.policy.compliance.items()} | {k: k for k in EXCLUSION_RULE.values()},
               "signals": {sid: s.label for sid, s in rt.policy.signals.items()}}
    answer = llm.structured(TESTER_SYSTEM, payload, _tester_schema(pool, rules, sorted(rt.policy.signals), products), effort="medium")
    out, notes = [], []
    for i, s in enumerate((answer or {}).get("scenarios", [])[:n]):
        t = s.get("event_type")
        if s.get("customer_id") not in pool or t not in EVENT_TYPES:
            notes.append(f"dropped #{i}: unknown customer or event type")
            continue
        if t == "consent_changed" and (s.get("consent_type") not in CONSENT_TYPES or s.get("new_status") not in CONSENT_STATUS):
            notes.append(f"dropped #{i}: consent change without type or status")
            continue
        params = {"consent_type": s.get("consent_type"), "new_status": s.get("new_status"),
                  "category": s.get("ticket_category") if s.get("ticket_category") != "none" else "complaint",
                  "channel": s.get("ticket_channel") if s.get("ticket_channel") != "none" else "phone",
                  "commodity": s.get("commodity") if s.get("commodity") != "none" else "electricity",
                  "new_level": max(0, min(3, int(s.get("new_level") or 0))), "count": max(1, min(5, int(s.get("count") or 1))),
                  "product_name": s.get("product_name") if s.get("product_name") in products else "LED-Set 10 Stk"}
        expect = {"no_sales": bool(s.get("expect_no_sales")),
                  "rule": None if s.get("expect_rule") in (None, "none") else s["expect_rule"],
                  "signal": None if s.get("expect_signal") in (None, "none") else s["expect_signal"]}
        out.append(Scenario(f"ai-{i}", s["customer_id"], t, params, str(s.get("story", ""))[:300], f"ai:{llm.name}", expect))
    return out, notes


# ---------------------------------------------------------------- AI judge


JUDGE_SYSTEM = (
    "You review one test of a Next Best Action engine. You get the scenario (a change to one customer), "
    "what the system did before and after, the code checks and any expectation the tester had that did not "
    "come true. Decide whether the result is explainable from the evidence (verdict 'explainable') or looks "
    "wrong and needs a person (verdict 'suspicious'). Pick a reason_code: ok, engine_bug (the engine "
    "seems wrong), expectation_wrong (the tester's expectation was wrong), data_gap (the data cannot "
    "support the change), explanation_unclear (the reason shown to people does not explain the change). "
    "Write at most two sentences. In `cited`, use only IDs from `allowed_ids`."
)
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["explainable", "suspicious"]},
                   "reason_code": {"type": "string", "enum": JUDGE_CODES},
                   "note": {"type": "string"}, "cited": {"type": "array", "items": {"type": "string"}}},
    "required": ["verdict", "reason_code", "note", "cited"],
    "additionalProperties": False,
}


def judge(results: list[dict], llm: LLM, limit: int = 20) -> int:
    """Adds a judge verdict to results, failed and mismatched first. It never changes `passed`."""
    if not llm.enabled:
        return 0
    calls = 0
    for r in sorted(results, key=lambda r: (r["passed"], not r["mismatch"])):
        if calls >= limit:
            break
        b, a = r["before"], r["after"]
        allowed = sorted({*b["signals"], *a["signals"], *b["rules"], *a["rules"], *a["exclusions"],
                          *(x.split("|")[0] for x in (b["chosen"], a["chosen"]) if x != NO_ACTION)})
        pack = {"scenario": {k: r["scenario"][k] for k in ("event_type", "params", "story", "expect")},
                "event_status": r["event_status"], "before": b, "after": a,
                "checks": [x for x in r["checks"] if not x["ok"]] or "all passed", "tester_mismatch": r["mismatch"],
                "allowed_ids": allowed}
        answer = llm.structured(JUDGE_SYSTEM, pack, JUDGE_SCHEMA, effort="low")
        calls += 1
        if not answer or answer.get("reason_code") not in JUDGE_CODES:
            continue
        r["judge"] = {"verdict": answer["verdict"], "reason_code": answer["reason_code"], "note": str(answer.get("note", ""))[:400],
                      "cited": [c for c in answer.get("cited", []) if c in allowed], "by": f"ai:{llm.name}"}
    return calls


# ---------------------------------------------------------------- marketer persona through the API


MARKETER_SYSTEM = (
    "You are a careful CRM marketer reviewing one proposed action before it goes to the campaign tool. "
    "Approve it if the reason and value make sense for this customer; otherwise reject it and pick the "
    "reason_code that fits. Write the reason in one short sentence."
)
MARKETER_SCHEMA = {
    "type": "object",
    "properties": {"action": {"type": "string", "enum": ["approve", "reject"]},
                   "reason_code": {"type": "string", "enum": ["already_has_product", "customer_upset", "no_time", "not_relevant",
                                                              "wrong_channel", "wrong_timing", "data_wrong", "other"]},
                   "reason": {"type": "string"}},
    "required": ["action", "reason_code", "reason"],
    "additionalProperties": False,
}


def workflow(rt, llm: LLM, out_dir, n: int = 6) -> dict:
    """The human-in-the-loop part, end to end through the API: decide, learn, decide again."""
    from fastapi.testclient import TestClient

    from api.app import create_app

    api = TestClient(create_app(runtime=rt, out_dir=Path(out_dir)))
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    rows = api.get("/api/customers").json()
    summ = api.get("/api/summary").json()
    acting = [r for r in rows if r["chosen_offer"] not in {NO_ACTION, "P-SV-01"} and not r.get("deferred_until")]
    counts = {}
    for r in rows:
        if r["chosen_offer"] != NO_ACTION:
            counts[r["chosen_offer"]] = counts.get(r["chosen_offer"], 0) + 1
    check("summary_matches_index", all(int(v["count"]) == counts.get(k, 0) for k, v in summ["chosen_by_offer"].items()))
    check("overview_reason_for_personalised", all(r["reason_signal"] and r["reason_need"] for r in acting if r["personalised"]))
    check("overview_labels_cover_reasons", all(r["reason_signal"] in summ["signal_labels"] for r in acting if r["reason_signal"]))
    picked, seen_offers = [], set()
    for r in sorted(acting, key=lambda r: r["customer_id"]):  # one customer per offer, for variety
        if r["chosen_offer"] not in seen_offers:
            seen_offers.add(r["chosen_offer"])
            picked.append(r)
        if len(picked) >= n:
            break
    decisions = []
    for i, r in enumerate(picked):
        card = api.get(f"/api/customers/{r['customer_id']}").json()
        c = next(x for x in card["candidates"] if x["tuple_id"] == card["chosen"]["tuple_id"])
        pack = {"offer": c["offer_name"], "channel": c["channel"], "tone": c["tone"], "why": c["why"][:2],
                "delta_clv_eur": round(c["valuation"]["delta_clv"], 2), "p_accept": round(c["valuation"]["p_accept"], 4),
                "segment": card["triage"]["archetype"]["name"], "flags": [f["id"] for f in card["triage"]["flags"]]}
        answer = llm.structured(MARKETER_SYSTEM, pack, MARKETER_SCHEMA, effort="low") if llm.enabled else None
        if not answer or answer.get("action") not in {"approve", "reject"}:
            answer = {"action": "reject" if i % 3 == 2 else "approve", "reason_code": "not_relevant", "reason": "fixed test policy"}
        body = {"action": answer["action"], "user": "ai-qa", "reason": answer.get("reason") or None}
        if answer["action"] == "reject":
            body["reason_code"] = answer.get("reason_code") or "other"
        res = api.post(f"/api/customers/{r['customer_id']}/decision", json=body)
        check(f"decision_accepted:{r['customer_id']}", res.status_code == 200, res.text[:200])
        decisions.append({"customer_id": r["customer_id"], "offer": c["offer_id"], **answer,
                          "by": f"ai:{llm.name}" if llm.enabled else "fixed"})
        after = api.get(f"/api/customers/{r['customer_id']}").json()
        if answer["action"] == "approve":
            check(f"approved_card_shows_status:{r['customer_id']}", after["chosen"]["status"] == "approved", after["chosen"]["status"])
        journey = api.get(f"/api/customers/{r['customer_id']}/journey")
        dates = [e["date"] for e in journey.json().get("events", [])] if journey.status_code == 200 else []
        check(f"journey_newest_first:{r['customer_id']}", journey.status_code == 200 and dates == sorted(dates, reverse=True))
    learned = api.post("/api/ai/feedback", params={"ai": bool(llm.enabled)}).json()
    for d in [d for d in decisions if d["action"] == "reject"]:
        card = api.get(f"/api/customers/{d['customer_id']}").json()
        check(f"rejected_offer_not_proposed_again:{d['customer_id']}", not card["chosen"]["tuple_id"].startswith(d["offer"] + "|"),
              card["chosen"]["tuple_id"])
        check(f"memory_rule_applied:{d['customer_id']}", any(x["rule_id"] == "MEMORY" for x in card["rules"]["results"]))
    review = api.get("/api/ai/review", params={"ai": False}).json()
    hard_ready = [cid for cid, c in review["customers"].items() if c["hard"] and c["status"] == "ready"]
    check("review_keeps_hard_flags_with_a_person", not hard_ready, ", ".join(hard_ready[:5]))
    return {"checks": checks, "passed": all(x["ok"] for x in checks), "decisions": decisions,
            "memory_added": len(learned.get("added", [])), "review": review["summary"]}


# ---------------------------------------------------------------- run and report


def run(rt, llm: LLM | None = None, out_dir="out/ai_qa", n_ai: int = 8, n_workflow: int = 6, judge_limit: int = 20) -> dict:
    llm = llm or LLM()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = seed_scenarios(rt)
    generated, notes = ai_scenarios(rt, llm, n_ai)
    results = [run_scenario(rt, sc) for sc in seeds + generated]
    judged = judge(results, llm, judge_limit)
    flow = workflow(rt, llm, out / "api", n_workflow)
    report = {
        "backend": llm.name if llm.enabled else "none",
        "summary": {"scenarios": len(results), "seed": len(seeds), "ai": len(generated), "passed": sum(r["passed"] for r in results),
                    "failed": sum(not r["passed"] for r in results), "tester_mismatches": sum(bool(r["mismatch"]) for r in results),
                    "suspicious": sum(bool(r["judge"]) and r["judge"]["verdict"] == "suspicious" for r in results),
                    "judged": judged, "workflow_passed": flow["passed"]},
        "notes": notes, "scenarios": results, "workflow": flow,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(markdown(report), encoding="utf-8")
    return report


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [f"# AI QA report (backend: {report['backend']})", "",
             f"{s['scenarios']} scenarios ({s['seed']} seed, {s['ai']} AI): {s['passed']} passed, {s['failed']} failed; "
             f"{s['tester_mismatches']} tester mismatches, {s['suspicious']} suspicious by the judge. "
             f"Workflow through the API: {'passed' if s['workflow_passed'] else 'FAILED'}.", ""]
    lines += [f"- {n}" for n in report["notes"]]
    lines += ["", "| Scenario | Customer | Event | Before → after | Checks | Tester | Judge |", "|---|---|---|---|---|---|---|"]
    for r in report["scenarios"]:
        sc, j = r["scenario"], r["judge"]
        failed = [x["check"] for x in r["checks"] if not x["ok"]]
        tup = lambda t: t.replace("|", " · ")  # noqa: E731 - tuple IDs would split the Markdown table
        lines.append(f"| {sc['id']} | {sc['customer_id']} | {sc['event_type']} | {tup(r['before']['chosen'])} → {tup(r['after']['chosen'])} | "
                     f"{'ok' if not failed else 'FAIL: ' + ', '.join(failed)} | {'; '.join(r['mismatch']) or '–'} | "
                     f"{(j['verdict'] + ': ' + j['note'].replace('|', '/')) if j else '–'} |")
    lines += ["", "## Workflow checks", ""]
    lines += [f"- {'ok' if x['ok'] else 'FAIL'} {x['check']}{(': ' + x['detail']) if x['detail'] and not x['ok'] else ''}"
              for x in report["workflow"]["checks"]]
    return "\n".join(lines) + "\n"
