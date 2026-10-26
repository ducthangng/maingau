"""Value and risk (README §4.1 A2): CLV, margin, cost, churn with driver tags, percentiles."""

from __future__ import annotations

import re

import pandas as pd

from nba.contracts import ChurnDriver, Percentiles, ValueRisk
from nba.profile.facts import clean, fact
from nba.profile.population import combo

# Churn driver increments from README §6.5, shown on the tags. None = label only.
DRIVER_DELTAS = [
    (re.compile(r"^price guarantee ends <90d$"), lambda m: 0.10),
    (re.compile(r"^open complaint$"), lambda m: 0.12),
    (re.compile(r"^(\d+) tickets in 12m$"), lambda m: 0.04 if int(m.group(1)) >= 2 else None),
    (re.compile(r"^low CSAT$"), lambda m: 0.05),
    (re.compile(r"^dunning level (\d+)$"), lambda m: 0.08 if int(m.group(1)) >= 2 else None),
    (re.compile(r"^\d+ failed charges in 30d$"), lambda m: 0.10),
    (re.compile(r"^HEMS user$"), lambda m: -0.04),
]


def churn_drivers(raw) -> list[ChurnDriver]:
    out = []
    for label in [p.strip() for p in str(clean(raw) or "").split(";") if p.strip()]:
        delta = None
        for rx, fn in DRIVER_DELTAS:
            if m := rx.match(label):
                delta = fn(m)
                break
        out.append(ChurnDriver(label=label, delta=delta))
    return out


def percentile(values: pd.Series, x) -> float | None:
    """Share of customers with a lower value, 0–100."""
    values = values.dropna()
    if x is None or values.empty:
        return None
    return round(100.0 * float((values < x).mean()))


def build_value_risk(state, pop: pd.DataFrame) -> ValueRisk:
    cv = state.one("customer_value") or {}
    cid = state.customer_id

    def f(col: str):
        return fact(cv.get(col), f"customer_value.{col}", cv, row_key=cid)

    clv = clean(cv.get("clv_eur"))
    peer = combo(state)
    same = pop[pop["combo"] == peer]["clv_eur"] if "combo" in pop.columns else pd.Series(dtype=float)
    return ValueRisk(
        clv_eur=f("clv_eur"),
        annual_margin_eur=f("annual_margin_eur"),
        cost_to_serve_12m_eur=f("cost_to_serve_12m_eur"),
        active_business_lines=f("active_business_lines"),
        churn_prob_12m=f("churn_prob_12m"),
        churn_drivers=churn_drivers(cv.get("churn_drivers")),
        clv_service_impact_eur=f("clv_service_impact_eur"),
        percentiles=Percentiles(
            clv_all=percentile(pop["clv_eur"], clv) if "clv_eur" in pop.columns else None,
            clv_same_combo=percentile(same, clv) if len(same) >= 5 else None,
            combo=peer,
        ),
    )
