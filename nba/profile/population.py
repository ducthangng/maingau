"""Population features for percentiles and highlights (README §4.1 A2, A5).

`population(tables)` in nba/state.py has the value columns; profile_population() repeats them and
adds the per-customer features the left card compares against. Pass it to build_profile as `pop`.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from nba.profile.facts import clean, to_datetime
from nba.state import active_lines, devices


def combo(state) -> str:
    """Product combination used as the peer group for the CLV percentile, e.g. "electricity+mobile"."""
    lines = sorted(active_lines(state))
    return "+".join(lines) if lines else "none"


def features(state) -> dict:
    cv = state.one("customer_value") or {}
    cm = state.one("customer_master") or {}
    eval_time = state.eval_time
    since = clean(cm.get("customer_since"))
    sessions = state.rows.get("charge_sessions", [])
    kwh = sum(clean(s.get("energy_kwh")) or 0 for s in sessions)
    dc_kwh = sum(clean(s.get("energy_kwh")) or 0 for s in sessions if s.get("charge_type") == "DC")
    failed_30d = sum(
        1 for s in sessions
        if s.get("session_status") == "failed" and s.get("started_at")
        and eval_time - timedelta(days=30) < s["started_at"] <= eval_time
    )
    portal_90d = sum(
        1 for s in state.rows.get("portal_sessions", [])
        if (t := to_datetime(s.get("session_start"))) and eval_time - timedelta(days=90) < t <= eval_time
    )
    devs = devices(state)
    elec_pv = any(r.get("commodity") == "electricity" and r.get("status") == "active" and r.get("feed_in_meter")
                  for r in state.rows.get("energy_contracts", []))
    mobile = [r for r in state.rows.get("mobile_contracts", []) if r.get("status") == "active"]
    return {
        "customer_id": state.customer_id,
        # the columns of nba.state.population(), so this frame can replace it everywhere
        "birth_year": clean(cm.get("birth_year")),
        "household_size": clean(cm.get("household_size")),
        "city": clean(cm.get("city")),
        "clv_eur": clean(cv.get("clv_eur")),
        "annual_margin_eur": clean(cv.get("annual_margin_eur")),
        "cost_to_serve_12m_eur": clean(cv.get("cost_to_serve_12m_eur")),
        "churn_prob_12m": clean(cv.get("churn_prob_12m")),
        "active_business_lines": clean(cv.get("active_business_lines")),
        # profile features
        "combo": combo(state),
        "clv_service_impact_eur": clean(cv.get("clv_service_impact_eur")),
        "tenure_years": (eval_time - since).days / 365.25 if since else None,
        "charge_kwh": kwh,
        "dc_share": dc_kwh / kwh if kwh else None,
        "failed_charges_30d": failed_30d,
        "portal_sessions_90d": portal_90d,
        "has_pv": elec_pv or "pv_inverter" in devs,
        "has_hems_gateway": "hems_gateway" in devs,
        "data_limit_reached_3m": max((clean(r.get("data_limit_reached_3m")) or 0 for r in mobile), default=None),
    }


def profile_population(states: dict) -> pd.DataFrame:
    """One row per customer: every column of nba.state.population() plus the profile features.

    Pass it as `pop` to build_profile (highlights and the same-combo percentile need the features);
    it also works wherever population() is expected, e.g. nba.kg.segments.triage.
    """
    return pd.DataFrame([features(s) for _, s in sorted(states.items())]).set_index("customer_id", drop=False)
