"""Two or three highlights (README §4.1 A5): only facts that are rare in the population."""

from __future__ import annotations

import pandas as pd

from nba.contracts import Highlight
from nba.profile.facts import clean


def _rarity(share: float) -> str:
    return "<1% of customers" if share < 0.01 else f"{share * 100:.0f}% of customers"


def build_highlights(state, pop: pd.DataFrame, cfg: dict) -> list[Highlight]:
    """Candidates are kept only if at most `rarity_max_share` of customers share them; rarest first."""
    if "combo" not in pop.columns or state.customer_id not in pop.index:
        return []
    me = pop.loc[state.customer_id]
    n = len(pop)
    found: list[tuple[float, str, list[str]]] = []

    def add(mask: pd.Series, text: str, basis: list[str]) -> None:
        found.append((float(mask.sum()) / n, text, basis))

    clv = clean(me["clv_eur"])
    if clv is not None:
        p90 = pop["clv_eur"].quantile(0.9)
        if clv >= p90:
            add(pop["clv_eur"] >= p90, f"Top 10% CLV (€{clv:,.0f})", ["customer_value.clv_eur"])
        if clv < 0:
            add(pop["clv_eur"] < 0, f"Negative CLV (€{clv:,.0f})", ["customer_value.clv_eur"])

    impact = clean(me["clv_service_impact_eur"])
    if impact:
        mag = pop["clv_service_impact_eur"].abs()
        if abs(impact) >= mag.quantile(0.9) and abs(impact) > 0:
            add(mag >= abs(impact), f"Service issues are costing €{abs(impact):,.0f} of CLV",
                ["customer_value.clv_service_impact_eur"])

    dc = clean(me["dc_share"])
    avg_dc = pop["dc_share"].mean()
    if dc and avg_dc and dc >= 2 * avg_dc:
        add(pop["dc_share"] >= dc, f"DC charging {dc / avg_dc:.1f}× the average share",
            ["charge_sessions.charge_type", "charge_sessions.energy_kwh"])

    if (clean(me["failed_charges_30d"]) or 0) >= 3:
        add(pop["failed_charges_30d"] >= 3, f"{int(me['failed_charges_30d'])} failed charging sessions in 30 days",
            ["charge_sessions.session_status"])

    if bool(me["has_pv"]) and not bool(me["has_hems_gateway"]):
        add(pop["has_pv"].astype(bool) & ~pop["has_hems_gateway"].astype(bool), "Has PV but no HEMS",
            ["energy_contracts.feed_in_meter", "hems_devices.device_type"])

    if clean(me["data_limit_reached_3m"]) == 3:
        add(pop["data_limit_reached_3m"] == 3, "Hit the data limit 3 of 3 months",
            ["mobile_contracts.data_limit_reached_3m"])

    tenure = clean(me["tenure_years"])
    if tenure is not None and tenure >= pop["tenure_years"].quantile(0.9):
        add(pop["tenure_years"] >= tenure, f"Customer for {tenure:.0f} years", ["customer_master.customer_since"])

    portal = clean(me["portal_sessions_90d"]) or 0
    if portal and portal >= pop["portal_sessions_90d"].quantile(0.9):
        add(pop["portal_sessions_90d"] >= portal, f"{portal} portal sessions in 90 days",
            ["portal_sessions.session_start"])

    keep = sorted(x for x in found if x[0] <= cfg.get("rarity_max_share", 0.10))
    return [Highlight(text=t, basis=b, rarity=_rarity(s)) for s, t, b in keep[: cfg.get("max", 3)]]
