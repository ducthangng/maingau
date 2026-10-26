"""Join KG, CARDS and model outputs into the shared CustomerCard contract."""
from __future__ import annotations

from dataclasses import replace

from nba.contracts import (
    Alternative, Blocked, Candidate, ChecklistItem, Chosen, CustomerCard, DataQuality,
    DecisionLogEntry, LegacyComparison, Meta, NO_ACTION, tuple_id,
)

from nba.engine.config import MissingDataError
from nba.engine.content import agent_script, guarantee_dates, render_content
from nba.engine.profile_adapter import build_sections, infer_tone
from nba.engine.propensity import p_accept, personalise
from nba.engine.rank import rank
from nba.engine.rulecenter import Evaluator, apply_rules, deferred_rows, report
from nba.engine.value import value
from nba.kg.paths import explain
from nba.kg.bundle import kg_bundle
from nba.kg.rules import cap_reason, check_tuple, is_profiled


def _guarantee_window(policy):
    return policy.params.get("price_guarantee_window_days") if policy is not None else None


def value_candidate(candidate, state, cfg, *, p_scale=1.0, margin_scale=1.0, policy=None):
    p = p_accept(candidate.offer_id, candidate.channel, candidate.tone, cfg.history, cfg,
                 generic=candidate.origin == "generic")
    p, look = personalise(p, candidate.offer_id, state.customer_id, cfg)
    p = replace(p, p_accept=min(1.0, max(0.0, p.p_accept * p_scale)))
    valuation = value(candidate, state, p, cfg, margin_scale=margin_scale)
    src = p.source
    if p.baseline_level.startswith("override:"):
        _, key, case = p.baseline_level.split(":", 2)
        evidence = (f"Reviewed assumption {p.p_accept:.1%} for {key} from fix case {case} (feedback loop); "
                    f"evidence {src.conv_treated}/{src.n_treated} vs control {src.conv_control}/{src.n_control}")
    elif src.mode == "assumption":
        evidence = f"Service success: assumed probability {p.p_accept:.1%}; no historical observations"
    else:
        evidence = (f"Observed conversions {src.conv_treated}/{src.n_treated}, level {src.level}, mode {src.mode}; "
                    f"control group {src.conv_control}/{src.n_control}, baseline used {src.baseline_control:.2%} "
                    f"({p.baseline_level.removeprefix('lookalike:')}); descriptive difference {p.uplift:.2%}, not causal uplift")
    if p.k is not None and abs(p.k - 1) >= 0.01:
        evidence += (f"; calibrated ×{p.k:.2f}: {p.k_actual} bought where the model expected {p.k_expected:.1f} "
                     f"for this offer × channel × tone")
    if look is not None:
        evidence += f". {look.evidence()}"
    notes = list(candidate.notes)
    if p.confidence == "low":
        notes.append("Low confidence: parent-level rate or assumed success probability")
    if candidate.origin == "generic":
        notes.append("No signal; catalog-wide acceptance rate adjusted by similar customers" if look
                     else "Not personalised; catalog-wide acceptance rate")
    if candidate.offer_id == "P-EN-02":
        dates = guarantee_dates(state, _guarantee_window(policy))
        if dates:
            notes.append(f"Contact before the price guarantee expires on {dates[0].date().isoformat()}; check the proposed date")
    return candidate.model_copy(update={"valuation": valuation, "why": candidate.why + [evidence], "notes": notes})


def evaluate_candidates(candidates, state, policy, cfg, *, p_scale=1.0, margin_scale=1.0, evaluator=None):
    """Value the primary tier before deciding whether generic tuples may compete, then apply the Rule Center
    tier 2 rules (docs/rule-center.md §5): the best tuple allowed now wins; if none is, the best held-back
    tuple waits (DEFER_UNTIL, `deferred_until` set), preferring signal tuples over generic ones (K12)."""
    blocked = []
    ev = evaluator or Evaluator(state, policy, cfg)

    def evaluate(items):
        evaluated = []
        for c in items:
            try:
                evaluated.append(value_candidate(c, state, cfg, p_scale=p_scale, margin_scale=margin_scale, policy=policy))
            except MissingDataError as exc:
                blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="DATA-MISSING",
                                       reason=str(exc), src="customer_value; product_catalog; value_assumptions"))
        return evaluated

    allowed, deferred, ruled = apply_rules(evaluate([c for c in candidates if c.origin != "generic"]), ev)
    positive_primary = any(c.valuation.delta_clv > 0 for c in allowed)
    waiting_primary = [c for c in deferred if c.valuation.delta_clv > 0]
    profiled = is_profiled(state, policy)
    fallback = policy.config.get("generic", {}).get("fallback_for_profiled", True)
    if not profiled or (not positive_primary and fallback):
        g_allowed, g_deferred, g_ruled = apply_rules(evaluate([c for c in candidates if c.origin == "generic"]), ev)
        allowed, deferred, ruled = allowed + g_allowed, deferred + g_deferred, ruled + g_ruled
    blocked += ruled
    for c in allowed + deferred:
        if c.valuation.delta_clv <= 0:
            blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="ECON-NONPOSITIVE",
                                   reason=f"{c.tuple_id}: expected ΔCLV €{c.valuation.delta_clv:.2f} ≤ 0",
                                   src="nba.engine.value.delta_clv", counterfactual_delta_clv=c.valuation.delta_clv))
    chosen, ordered = rank(allowed)
    waiting = [c for c in deferred if c.valuation.delta_clv > 0]
    if chosen is None and waiting:
        chosen, ordered = rank(waiting_primary if waiting_primary and profiled else waiting)
        blocked += deferred_rows([c for c in waiting if c.tuple_id not in {o.tuple_id for o in ordered}])
    else:
        blocked += deferred_rows(waiting)
    return chosen, ordered, blocked


def legacy_comparison(state, policy, cfg, candidates):
    rows = [r for r in state.rows.get("nba_action_history", [])
            if r.get("decided_at") and r["decided_at"] <= state.eval_time]
    if not rows:
        return None
    row = max(rows, key=lambda r: (r["decided_at"], r["action_id"]))
    oid, channel, tone = row.get("offer_id"), row.get("channel"), row.get("tonality") or "sie"
    result = LegacyComparison(rule_id=row.get("rule_id"), offer_id=oid, channel=channel,
                              decided_at=row["decided_at"].isoformat())
    result.blocked_now_by = sorted({b.rule_id for b in check_tuple(state, oid, channel, policy)})
    if oid not in cfg.offers or channel not in policy.channels:
        return result
    target = next((c for c in candidates if c.offer_id == oid and c.channel == channel), None)
    if target is not None:
        target = target.model_copy(update={"tuple_id": tuple_id(oid, channel, tone), "tone": tone})
    if target is None:
        generic = row.get("rule_id") == "R-SHOP-GENERIC"
        target = Candidate(tuple_id=tuple_id(oid, channel, tone), offer_id=oid,
                           offer_name=cfg.offers[oid]["product_name"], action_type=cfg.offers[oid]["action_type"],
                           channel=channel, tone=tone, origin="generic" if generic else "signal", personalised=not generic)
    if not is_profiled(state, policy) and tone != "sie":
        result.blocked_now_by = sorted(set(result.blocked_now_by) | {"CONSENT-PROFILING"})
    try:
        valuation = value_candidate(target, state, cfg, policy=policy).valuation
        result.delta_clv_our_model = valuation.delta_clv
        if valuation.delta_clv <= 0:
            result.blocked_now_by = sorted(set(result.blocked_now_by) | {"ECON-NONPOSITIVE"})
    except MissingDataError:
        result.blocked_now_by = sorted(set(result.blocked_now_by) | {"DATA-MISSING"})
    return result


def valuation_scores(valuation):
    scores = valuation.model_dump(exclude={"p_source", "confidence"})
    scores.update({k: v for k, v in valuation.p_source.model_dump().items()
                   if k not in {"mode", "level"} and v is not None})
    return scores


def _held_back(candidate) -> str:
    return next((n for n in reversed(candidate.notes) if n.startswith("Held back until")), "Held back")


def checklist_for(chosen, quality):
    """Six checks for the proposed action; none for NO_ACTION (nothing to approve, Q-KG-19)."""
    quality = [q for q in quality if q.code != "PROFILE-PENDING"]
    if chosen is None:
        return []
    service = chosen.action_type == "service"
    if chosen.deferred_until:
        cap = ChecklistItem(item="contact_cap", passed=False, src="docs/rule-center.md §5",
                            detail=f"{_held_back(chosen)}; approve on or after that time")
    else:
        cap = ChecklistItem(item="contact_cap", passed=True, src="nba_action_history.decided_at",
                            detail="Service is exempt" if service else "Contact cap and Rule Center limits checked")
    return [
        ChecklistItem(item="consent_for_channel", passed=True, detail="Service contact" if service else "Channel consent and availability checked", src="consent_status.status"),
        ChecklistItem(item="profiling_consent", passed=True,
                      detail="Not required: not personalised" if not chosen.personalised else "Profiling consent granted", src="consent_status.status"),
        ChecklistItem(item="no_exclusion", passed=True, detail="Service is exempt" if service else "No exclusion blocks this offer", src="nba.kg.rules"),
        ChecklistItem(item="not_owned", passed=True, detail="Service is exempt" if service else "Ownership and preconditions checked", src="nba.state.owns"),
        cap,
        ChecklistItem(item="data_fresh", passed=not quality,
                      detail="; ".join(q.detail for q in quality) if quality else "No warnings", src="sources"),
    ]


def build_chosen(selected, state, cfg, service_mode=False, *, policy=None):
    from datetime import datetime

    from nba.engine.schedule import suggested_send_time

    v = selected.valuation
    lead = next(iter(selected.why), "Catalog offer")
    reason = f"{lead} → {selected.offer_name} via {selected.channel}; ΔCLV +{v.delta_clv:.2f} €, p {v.p_accept:.1%} ({v.confidence})"
    after = datetime.fromisoformat(selected.deferred_until) if selected.deferred_until else None
    if after:
        reason = f"{_held_back(selected)}. {reason}"
    return Chosen(tuple_id=selected.tuple_id, reason_line=reason, deferred_until=selected.deferred_until,
                  send_at=suggested_send_time(selected, state, cfg, after=after), service_mode=service_mode,
                  content=render_content(selected, selected.tone, selected.personalised, state=state, template_dir=cfg.template_dir,
                                         window_days=_guarantee_window(policy)),
                  agent_script=agent_script(selected.tone, cfg.template_dir) if service_mode else None)


def assemble(state, pop, policy, cfg, *, capacity=None) -> CustomerCard:
    """`capacity`: channel -> wait-until for a customer whose chosen action overflowed B-09 (Runtime)."""
    tone = infer_tone(state, policy)
    # The KG keeps capped tuples (failing CONTACT-CAP check) so B-02 can defer them instead of dropping them.
    bundle = kg_bundle(state, policy, pop, tone.value, apply_cap=False)
    signals, candidates, blocked = bundle.signals, bundle.candidates, list(bundle.blocked)
    profile, timeline, profile_available = build_sections(state, pop, policy, tone, bundle=bundle)
    ev = Evaluator(state, policy, cfg, capacity=capacity)
    selected, ranked, economics = evaluate_candidates(candidates, state, policy, cfg, evaluator=ev)
    if ev.cap.hit:
        blocked.append(Blocked(offer_id="*", rule_id="CONTACT-CAP", rule_center_id="B-02", src=ev.cap.src,
                               reason=f"{cap_reason(ev.cap)}; marketing waits",
                               until=ev.cap.free_at.isoformat() if ev.cap.free_at else None))
    blocked += economics
    quality = list(bundle.data_quality)
    if not profile_available:
        quality.append(DataQuality(code="PROFILE-PENDING", level="info", detail="Profile and timeline are not fully available; not enough data"))
    for c in ranked:
        c.notes += [f"{q.code}: {q.detail}" for q in quality]
    service_mode = any(s.id in {"S2", "S12", "S13"} for s in signals)
    versions = cfg.versions(policy)
    if selected:
        chosen = build_chosen(selected, state, cfg, service_mode, policy=policy)
        path = selected.path or explain(state, selected, policy)
    else:
        rules = ", ".join(sorted({b.rule_id for b in blocked})) or "DATA-MISSING"
        chosen = Chosen(tuple_id=NO_ACTION, service_mode=service_mode,
                        reason_line=f"No eligible action with positive expected ΔCLV. Reasons: {rules}")
        path = []
    alternatives = [Alternative(tuple_id=c.tuple_id, delta_clv=c.valuation.delta_clv,
                                why_lower=(f"Lower expected ΔCLV by €{selected.valuation.delta_clv - c.valuation.delta_clv:.2f}"
                                           if c.valuation.delta_clv != selected.valuation.delta_clv
                                           else "Equal expected ΔCLV; tie broken by probability, contact cost, offer ID and tuple ID"))
                    for c in ranked[1:4]] if selected else []
    scores = valuation_scores(selected.valuation) if selected else {}
    rule_report = report(ev, bundle.blocked, chosen.tuple_id, versions.rules)
    # tier 2 rules are identified by versions.rules (rule_set_version); list the ones that changed something
    tier2 = {r.rule_id for r in rule_report.results if r.tier != "compliance" and r.result in {"block", "defer"}}
    applied = ({c.rule_id for c in selected.checks} | tier2) if selected else ({b.rule_id for b in blocked} | tier2)
    proposed = DecisionLogEntry(ts=state.eval_time.isoformat(), actor="engine", action="proposed",
                                tuple_id=chosen.tuple_id, state_revision=state.revision,
                                versions=versions.model_dump(), rules_applied=sorted(applied), scores=scores)
    return CustomerCard(customer_id=state.customer_id,
                        meta=Meta(eval_time=state.eval_time.isoformat(), snapshot_mode=state.snapshot_mode,
                                  mode_default="service" if service_mode else "marketing", versions=versions, state_revision=state.revision),
                        sources=cfg.sources, triage=bundle.triage, profile=profile,
                        timeline=timeline, signals=signals, candidates=ranked, blocked=blocked, chosen=chosen,
                        alternatives=alternatives, legacy_comparison=legacy_comparison(state, policy, cfg, candidates),
                        explanation_path=path, checklist=checklist_for(selected, quality), data_quality=quality, decision_log=[proposed],
                        rules=rule_report)
