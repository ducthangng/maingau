"""Expected incremental CLV on the model basis, including the reject branch."""
from __future__ import annotations

from nba.contracts import Valuation
from nba.engine.churn import churn_breakdown
from nba.engine.clv import clv
from nba.engine.config import EngineConfig, MissingDataError, number

CHANNEL_COST_PARAMETER = {
    "newsletter_email": "contact_cost_email_eur", "email": "contact_cost_email_eur",
    "sms": "contact_cost_sms_eur", "portal_popup": "contact_cost_popup_eur",
    "app_push": "contact_cost_popup_eur",
    "outbound_call": "contact_cost_call_eur",
}


def contact_cost(channel, cfg: EngineConfig) -> float:
    # Service has no marketing contact fee; the workbook's resolution cost is in its accept branch.
    if channel == "service_agent":
        return 0.0
    return cfg.parameter(CHANNEL_COST_PARAMETER[channel])


def value(candidate, state, propensity, cfg: EngineConfig, *, margin_scale=1.0) -> Valuation:
    row = state.one("customer_value") or {}
    offer = cfg.offers.get(candidate.offer_id)
    if offer is None:
        raise MissingDataError(f"Nicht genug Daten: product_catalog.{candidate.offer_id}")
    margin = number(row.get("annual_margin_eur"), "customer_value.annual_margin_eur")
    cost = number(row.get("cost_to_serve_12m_eur"), "customer_value.cost_to_serve_12m_eur")
    churn = number(row.get("churn_prob_12m"), "customer_value.churn_prob_12m")
    shown = number(row.get("clv_eur"), "customer_value.clv_eur")
    r, years = cfg.parameter("discount_rate"), int(cfg.parameter("horizon_years"))
    ceiling = cfg.parameter("cancellation_pending")
    clamp = lambda p: min(ceiling, max(0.0, p))
    model = lambda m, c, p: clv(m, c, clamp(p), r, years)
    now = model(margin, cost, churn)
    gain_margin = number(offer.get("annual_margin_if_bought_eur"), "product_catalog.annual_margin_if_bought_eur") * margin_scale
    breakdown = churn_breakdown(state, cfg)
    if candidate.offer_id == "P-SV-01":
        after_churn = ceiling if breakdown.cancellation_pending else clamp(churn - breakdown.service_increment)
        accept = model(margin, cost, after_churn) - cfg.parameter("service_resolution_cost_eur")
    elif candidate.offer_id == "P-EN-02":
        if "price_guarantee_ends_90d" not in breakdown.increments:
            raise MissingDataError("P-EN-02 requires the price guarantee churn driver")
        accept = model(margin, cost, churn - cfg.parameter("price_guarantee_ends_90d"))
    else:
        effect = number(offer.get("churn_effect_if_bought"), "product_catalog.churn_effect_if_bought")
        accept = (model(margin, cost, churn + effect) + gain_margin if candidate.action_type == "one_off"
                  else model(margin + gain_margin, cost, churn + effect))
    open_complaint = any(r.get("status") == "open" and r.get("category") == "complaint"
                         for r in state.rows.get("service_interactions", []))
    dunning = any((r.get("dunning_level") or 0) >= 1 for r in state.rows.get("energy_contracts", []))
    reject = (model(margin, cost, churn + cfg.parameter("contact_during_service_case"))
              if candidate.action_type != "service" and (open_complaint or dunning) else now)
    p = propensity.p_accept
    if not 0 <= p <= 1:
        raise ValueError("p_accept must be in [0, 1]")
    fee = contact_cost(candidate.channel, cfg)
    delta = p * (accept - now) + (1 - p) * (reject - now) - fee
    return Valuation(clv_now_shown=shown, clv_now_model=now, clv_after_accept=accept,
                     clv_after_reject=reject, p_accept=p, p_source=propensity.source,
                     contact_cost=fee, delta_clv=delta, confidence=propensity.confidence)
