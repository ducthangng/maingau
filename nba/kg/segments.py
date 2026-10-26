"""Triage: archetypes, urgency and flags (README §6.13). Owner: Agent KG.

Rule-based on purpose: every assignment is explainable in one sentence. Age and payment data
are never used, except the exclusion flags themselves.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

from nba.contracts import Archetype, Flag, Signal, Triage
from nba.kg import predicates as P
from nba.kg.policy import Policy
from nba.kg.rules import active_exclusions, consents, _channels
from nba.state import CustomerState, active_lines, contacts, devices

TIER_NUMBER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
OUTLIER_FLAGS = {"service_critical", "no_marketing_channel", "negative_clv", "annoyed_before", "prefers_en"}
INCONSISTENT_TICKETS = {"TK-200565", "TK-200640"}  # closed in the snapshot, resolved after the cutoff (README §3)


def clv_quantile(pop: pd.DataFrame, q: float) -> float:
    """clv_eur quantile, index-based like README §6.13 (cached on the DataFrame per q)."""
    key = f"clv_q{q}"
    if key not in pop.attrs:
        vals = sorted(float(v) for v in pop["clv_eur"])
        pop.attrs[key] = vals[int(q * len(vals))]
    return pop.attrs[key]


def clv_p90(pop: pd.DataFrame) -> float:
    return clv_quantile(pop, 0.9)


def _archetype(state: CustomerState, policy: Policy, has_excl: bool, churn: float) -> Archetype:
    risk = policy.params["risk_churn_min"]
    lines, devs = active_lines(state), devices(state)
    master = state.one("customer_master") or {}
    mobile = [r for r in state.rows["mobile_contracts"] if r.get("status") == "active"]
    if has_excl or churn >= risk:
        why = "active exclusion" if has_excl else f"churn probability {churn:.2f} ≥ {risk}"
        return Archetype(id="A4", name=policy.archetypes["A4"], reason=why)
    if "hems_gateway" in devs:
        return Archetype(id="A1", name=policy.archetypes["A1"], reason="has a HEMS gateway")
    if "autostrom" in lines:
        return Archetype(id="A3", name=policy.archetypes["A3"], reason="active Autostrom contract")
    if mobile:
        m = mobile[0]
        hh, sims, lim = master.get("household_size") or 0, m.get("sim_count") or 0, m.get("data_limit_reached_3m") or 0
        if hh > sims or lim >= 1:
            why = f"household of {hh} with {sims} SIM(s)" if hh > sims else f"data limit reached in {lim} of 3 months"
            return Archetype(id="A5", name=policy.archetypes["A5"], reason=f"active mobile; {why}")
    if lines and lines <= {"electricity", "gas"}:
        return Archetype(id="A2", name=policy.archetypes["A2"], reason=f"only energy contracts ({', '.join(sorted(lines))})")
    return Archetype(id="A0", name=policy.archetypes["A0"], reason="no archetype rule matched")


def triage(state: CustomerState, signals: list[Signal], policy: Policy, pop: pd.DataFrame) -> Triage:
    value = state.one("customer_value") or {}
    master = state.one("customer_master") or {}
    churn, clv = float(value.get("churn_prob_12m") or 0), float(value.get("clv_eur") or 0)
    excl = dict(active_exclusions(state, policy))
    sig = {s.id: s for s in signals}
    energy = state.rows["energy_contracts"]
    dunning = max([r.get("dunning_level") or 0 for r in energy] or [0])
    open_tickets = [r for r in state.rows["service_interactions"] if r.get("status") == "open"]
    complaint = [r for r in open_tickets if r.get("category") == "complaint"]

    # price guarantee days and recent gas deregistration
    prm = policy.params
    pg = P.price_guarantee_ending(state, prm)
    pg_days = (pg.date.date() - state.eval_time.date()).days if pg else None
    dereg = P.gas_meter_deregistered(state, prm)
    dereg_recent = bool(dereg and state.eval_time - dereg.date <= timedelta(days=prm["p3_dereg_recent_days"]))
    p1_dun, p2_days, risk = prm["p1_dunning_min"], prm["p2_price_guarantee_days"], prm["risk_churn_min"]

    reasons: list[str] = []
    deadline = None
    if "EXCL-CANCELLATION" in excl or complaint or dunning >= p1_dun or "S2" in sig:
        tier = "P1"
        if "EXCL-CANCELLATION" in excl:
            reasons.append(f"{excl['EXCL-CANCELLATION'].detail} [EXCL-CANCELLATION]")
        if complaint:
            reasons.append(f"open complaint {complaint[0]['ticket_id']} since {complaint[0]['created_at'].date()} [S12]")
        if dunning >= p1_dun:
            reasons.append(f"dunning level {dunning} [S13]")
        if "S2" in sig:
            reasons.append(f"{sig['S2'].detail} [S2]")
    elif open_tickets or 0 < dunning < p1_dun or (pg_days is not None and pg_days <= p2_days) or churn >= risk:
        tier = "P2"
        if open_tickets:
            reasons.append(f"open {open_tickets[0]['category']} ticket {open_tickets[0]['ticket_id']} [S12]")
        if 0 < dunning < p1_dun:
            reasons.append(f"dunning level {dunning} [S13]")
        if pg_days is not None and pg_days <= p2_days:
            reasons.append(f"{pg.detail} [S4]")
            deadline = pg.date.date().isoformat()
        if churn >= risk:
            reasons.append(f"churn probability {churn:.2f} ≥ {risk}")
    elif pg is not None or dereg_recent or "S5" in sig:
        tier = "P3"
        if pg is not None:
            reasons.append(f"{pg.detail} [S4]")
            deadline = pg.date.date().isoformat()
        if dereg_recent:
            reasons.append(f"{dereg.detail} [S1]")
        if "S5" in sig:
            reasons.append(f"{sig['S5'].detail} [S5]")
    elif any(s.id not in ("S10",) for s in signals):
        tier = "P4"
        reasons += [f"{s.detail} [{s.id}]" for s in signals if s.id != "S10"]
    else:
        tier = "P5"
        reasons.append("no trigger")
    # Secondary reasons: every other signal, so the worklist shows the full picture.
    cited = {tok for r in reasons for tok in re.findall(r"\[(S\d+)\]", r)}
    reasons += [f"{s.detail} [{s.id}]" for s in signals if s.id not in cited and s.id != "S10"]
    score = 100 * (5 - TIER_NUMBER[tier]) + min(99.0, max(0.0, clv) * churn / 10)

    # flags
    flags: list[Flag] = []
    cons = consents(state, policy)
    chans = _channels(state, policy, cons)
    if tier == "P1":
        p1_src = ("energy_contracts.status" if "EXCL-CANCELLATION" in excl else
                  "service_interactions.status" if complaint else
                  "energy_contracts.dunning_level" if dunning >= p1_dun else "charge_sessions.session_status")
        flags.append(Flag(id="service_critical", label="Service critical", detail=reasons[0] if reasons else None, src=p1_src))
    if not any(c.allowed for c in chans.values()):
        flags.append(Flag(id="no_marketing_channel", label="No marketing channel",
                          detail="; ".join(f"{c.channel}: {c.reason}" for c in chans.values()), src="consent_status.status"))
    if cons["profiling_analytics"].effective_status != "granted":
        flags.append(Flag(id="no_profiling", label="No profiling consent",
                          detail="generic, non-personalised offers only", src="consent_status.status"))
    if clv < 0:
        flags.append(Flag(id="negative_clv", label="Negative CLV", detail=f"clv_eur {clv:,.0f}", src="customer_value.clv_eur"))
    q = prm["top_clv_quantile"]
    top = clv_quantile(pop, q)
    if clv >= top:
        flags.append(Flag(id="top_clv", label=f"Top {round((1 - q) * 100)}% CLV",
                          detail=f"clv_eur {clv:,.0f} ≥ p{round(q * 100)} {top:,.0f}", src="customer_value.clv_eur"))
    n30 = len(contacts(state, 30))
    ignored = sum(1 for r in contacts(state, 90) if r.get("response") in ("ignored", "dismissed"))
    if n30 >= prm["fatigue_contacts_30d"] or ignored >= prm["fatigue_ignored_90d"]:
        flags.append(Flag(id="contact_fatigue", label="Contact fatigue",
                          detail=f"{n30} contacts in 30 days; {ignored} ignored/dismissed in 90 days", src="nba_action_history.response"))
    fb = [r for r in state.rows["service_nba_feedback"]
          if r.get("customer_reaction") == "annoyed" or r.get("dismiss_reason") == "customer_upset"]
    if fb:
        flags.append(Flag(id="annoyed_before", label="Annoyed before", detail=f"{len(fb)} service NBA feedback(s) annoyed/upset",
                          src="service_nba_feedback.customer_reaction"))
    if master.get("preferred_contact_language") == "en":
        flags.append(Flag(id="prefers_en", label="Prefers English", detail="content stays German per challenge rules",
                          src="customer_master.preferred_contact_language"))
    late_cdr = any(r.get("cdr_received_at") and r["cdr_received_at"] > state.eval_time for r in state.rows["charge_sessions"])
    odd_ticket = any(r.get("ticket_id") in INCONSISTENT_TICKETS for r in state.rows["service_interactions"])
    if late_cdr or odd_ticket:
        flags.append(Flag(id="data_inconsistent", label="Snapshot inconsistency",
                          detail="CDR received after the cutoff" if late_cdr else "ticket closed but resolved after the cutoff",
                          src="charge_sessions.cdr_received_at" if late_cdr else "service_interactions.resolved_at"))

    return Triage(
        archetype=_archetype(state, policy, bool(excl), churn),
        urgency_tier=tier,
        urgency_score=round(score, 2),
        urgency_reasons=reasons,
        deadline=deadline,
        flags=flags,
        outlier=any(f.id in OUTLIER_FLAGS for f in flags),
    )
