"""Join KG, CARDS and model outputs into the shared CustomerCard contract."""
from __future__ import annotations

from dataclasses import replace

from nba.contracts import (
    Alternative, Blocked, Candidate, ChecklistItem, Chosen, CustomerCard, DataQuality,
    DecisionLogEntry, LegacyComparison, Meta, NO_ACTION, tuple_id,
)

from nba.engine.config import MissingDataError
from nba.engine.content import agent_script, render_content
from nba.engine.profile_adapter import build_sections, infer_tone
from nba.engine.propensity import p_accept, personalise
from nba.engine.rank import rank
from nba.engine.value import value
from nba.kg.paths import explain
from nba.kg.bundle import kg_bundle
from nba.kg.rules import check_tuple, is_profiled


def value_candidate(candidate, state, cfg, *, p_scale=1.0, margin_scale=1.0):
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
    if look is not None:
        evidence += f". {look.evidence()}"
    notes = list(candidate.notes)
    if p.confidence == "low":
        notes.append("Low confidence: parent-level rate or assumed success probability")
    if candidate.origin == "generic":
        notes.append("No signal; catalog-wide acceptance rate adjusted by similar customers" if look
                     else "Not personalised; catalog-wide acceptance rate")
    if candidate.offer_id == "P-EN-02":
        dates = sorted(r["price_guarantee_until"] for r in state.rows.get("energy_contracts", [])
                       if r.get("status") == "active" and r.get("price_guarantee_until")
                       and 0 <= (r["price_guarantee_until"].date() - state.eval_time.date()).days < 90)
        if dates:
            notes.append(f"Contact before the price guarantee expires on {dates[0].date().isoformat()}; check the proposed date")
    return candidate.model_copy(update={"valuation": valuation, "why": candidate.why + [evidence], "notes": notes})


def evaluate_candidates(candidates, state, policy, cfg, *, p_scale=1.0, margin_scale=1.0):
    """Value the primary tier before deciding whether generic tuples may compete."""
    blocked = []

    def evaluate(items):
        evaluated = []
        for c in items:
            try:
                evaluated.append(value_candidate(c, state, cfg, p_scale=p_scale, margin_scale=margin_scale))
            except MissingDataError as exc:
                blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="DATA-MISSING",
                                       reason=str(exc), src="customer_value; product_catalog; value_assumptions"))
        return evaluated

    primary = evaluate([c for c in candidates if c.origin != "generic"])
    positive_primary = any(c.valuation.delta_clv > 0 for c in primary)
    profiled = is_profiled(state, policy)
    fallback = policy.config.get("generic", {}).get("fallback_for_profiled", True)
    evaluated = primary
    if not profiled or (not positive_primary and fallback):
        evaluated += evaluate([c for c in candidates if c.origin == "generic"])
    for c in evaluated:
        if c.valuation.delta_clv <= 0:
            blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="ECON-NONPOSITIVE",
                                   reason=f"{c.tuple_id}: expected ΔCLV €{c.valuation.delta_clv:.2f} ≤ 0",
                                   src="nba.engine.value.delta_clv", counterfactual_delta_clv=c.valuation.delta_clv))
    chosen, ordered = rank(evaluated)
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
        valuation = value_candidate(target, state, cfg).valuation
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


def checklist_for(chosen, quality):
    quality = [q for q in quality if q.code != "PROFILE-PENDING"]
    if chosen is None:
        return [ChecklistItem(item=key, passed=False, detail="No eligible action selected", src=src)
                for key, src in (("consent_for_channel", "consent_status.status"),
                                 ("profiling_consent", "consent_status.status"),
                                 ("no_exclusion", "nba.kg.rules"), ("not_owned", "nba.state.owns"),
                                 ("contact_cap", "nba_action_history.decided_at"), ("data_fresh", "sources"))]
    service = chosen.action_type == "service"
    return [
        ChecklistItem(item="consent_for_channel", passed=True, detail="Service contact" if service else "Channel consent and availability checked", src="consent_status.status"),
        ChecklistItem(item="profiling_consent", passed=True,
                      detail="Not required: not personalised" if not chosen.personalised else "Profiling consent granted", src="consent_status.status"),
        ChecklistItem(item="no_exclusion", passed=True, detail="Service is exempt" if service else "No exclusion blocks this offer", src="nba.kg.rules"),
        ChecklistItem(item="not_owned", passed=True, detail="Service is exempt" if service else "Ownership and preconditions checked", src="nba.state.owns"),
        ChecklistItem(item="contact_cap", passed=True, detail="Service is exempt" if service else "Contact cap checked", src="nba_action_history.decided_at"),
        ChecklistItem(item="data_fresh", passed=not quality,
                      detail="; ".join(q.detail for q in quality) if quality else "No warnings", src="sources"),
    ]


def build_chosen(selected, state, cfg, service_mode=False):
    from nba.engine.schedule import suggested_send_time

    v = selected.valuation
    lead = next(iter(selected.why), "Catalog offer")
    reason = f"{lead} → {selected.offer_name} via {selected.channel}; ΔCLV +{v.delta_clv:.2f} €, p {v.p_accept:.1%} ({v.confidence})"
    return Chosen(tuple_id=selected.tuple_id, reason_line=reason,
                  send_at=suggested_send_time(selected, state, cfg), service_mode=service_mode,
                  content=render_content(selected, selected.tone, selected.personalised, state=state, template_dir=cfg.template_dir),
                  agent_script=agent_script(selected.tone, cfg.template_dir) if service_mode else None)


def assemble(state, pop, policy, cfg) -> CustomerCard:
    tone = infer_tone(state, policy)
    bundle = kg_bundle(state, policy, pop, tone.value)
    signals, candidates, blocked = bundle.signals, bundle.candidates, list(bundle.blocked)
    profile, timeline, profile_available = build_sections(state, pop, policy, tone, bundle=bundle)
    selected, ranked, economics = evaluate_candidates(candidates, state, policy, cfg)
    blocked += economics
    quality = list(bundle.data_quality)
    if not profile_available:
        quality.append(DataQuality(code="PROFILE-PENDING", level="info", detail="Profile and timeline are not fully available; not enough data"))
    for c in ranked:
        c.notes += [f"{q.code}: {q.detail}" for q in quality]
    service_mode = any(s.id in {"S2", "S12", "S13"} for s in signals)
    versions = cfg.versions(policy)
    if selected:
        chosen = build_chosen(selected, state, cfg, service_mode)
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
    proposed = DecisionLogEntry(ts=state.eval_time.isoformat(), actor="engine", action="proposed",
                                tuple_id=chosen.tuple_id, state_revision=state.revision,
                                versions=versions.model_dump(), rules_applied=sorted({c.rule_id for c in selected.checks}) if selected else sorted({b.rule_id for b in blocked}),
                                scores=scores)
    return CustomerCard(customer_id=state.customer_id,
                        meta=Meta(eval_time=state.eval_time.isoformat(), snapshot_mode=state.snapshot_mode,
                                  mode_default="service" if service_mode else "marketing", versions=versions, state_revision=state.revision),
                        sources=cfg.sources, triage=bundle.triage, profile=profile,
                        timeline=timeline, signals=signals, candidates=ranked, blocked=blocked, chosen=chosen,
                        alternatives=alternatives, legacy_comparison=legacy_comparison(state, policy, cfg, candidates),
                        explanation_path=path, checklist=checklist_for(selected, quality), data_quality=quality, decision_log=[proposed])
