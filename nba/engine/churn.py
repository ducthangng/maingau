"""Reconstruct the supplied model and expose the service drivers separately."""
from __future__ import annotations

import re
from dataclasses import dataclass

from nba.engine.config import EngineConfig, MissingDataError, load_config, number

DRIVER_PARAMETERS = {
    "price guarantee ends <90d": "price_guarantee_ends_90d",
    "open complaint": "open_complaint",
    "low CSAT": "csat_le2",
    "3 failed charges in 30d": "failed_charges_30d_ge3",
    "HEMS user": "hems_user",
}
SERVICE_PARAMETERS = {"open_complaint", "tickets_12m_ge2", "csat_le2", "dunning_ge2", "failed_charges_30d_ge3"}


@dataclass(frozen=True)
class ChurnBreakdown:
    given: float
    reconstructed: float
    base: float | None
    multi_line_factor: float | None
    increments: dict[str, float]
    service_increment: float
    cancellation_pending: bool
    used_given: bool


def driver_increments(state, cfg: EngineConfig) -> dict[str, float]:
    row = state.one("customer_value") or {}
    labels = {s.strip() for s in (row.get("churn_drivers") or "").split(";") if s.strip()}
    increments = {}
    for label in sorted(labels):
        if label.startswith("multi-product") or label == "cancellation pending":
            continue
        key = DRIVER_PARAMETERS.get(label)
        if re.fullmatch(r"[2-9]\d* tickets in 12m", label):
            key = "tickets_12m_ge2"
        if re.fullmatch(r"dunning level [23]", label):
            key = "dunning_ge2"
        if key is None:
            raise MissingDataError(f"Unknown churn driver: {label}")
        increments[key] = cfg.parameter(key)
    return increments


def churn_breakdown(state, cfg: EngineConfig | None = None) -> ChurnBreakdown:
    cfg = load_config() if cfg is None else cfg
    row = state.one("customer_value") or {}
    given = number(row.get("churn_prob_12m"), "customer_value.churn_prob_12m")
    bases = []
    cancelled = False
    for r in state.rows.get("energy_contracts", []):
        cancelled |= r.get("status") == "cancellation_pending"
        if r.get("status") in {"active", "cancellation_pending"}:
            bases.append(cfg.parameter("base_" + r["commodity"]))
    for sheet, key in (("mobile_contracts", "base_mobile"), ("autostrom_contracts", "base_autostrom")):
        bases.extend(cfg.parameter(key) for r in state.rows.get(sheet, []) if r.get("status") == "active")
    inc = driver_increments(state, cfg)
    service = sum(v for k, v in inc.items() if k in SERVICE_PARAMETERS)
    if not bases:
        return ChurnBreakdown(given, given, None, None, inc, service, cancelled, True)
    base = sum(bases) / len(bases)
    lines = number(row.get("active_business_lines"), "customer_value.active_business_lines")
    factor = max(cfg.parameter("multi_line_factor") ** (lines - 1), 0.5)
    reconstructed = cfg.parameter("cancellation_pending") if cancelled else base * factor + sum(inc.values())
    # The source model stores probabilities to three decimal places.
    return ChurnBreakdown(given, round(reconstructed, 3), base, factor, inc, service, cancelled, False)
