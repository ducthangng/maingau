"""Per-customer state and the shared holding/contact helpers (README §5.2).

Owner: Agent KG. Every agent uses these helpers so that "owned", "active" and
"contact" mean the same thing everywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd

DEFAULT_EVAL_TIME = datetime(2026, 9, 30, 23, 59, 59)

# Sheets keyed by customer_id. Reference sheets and newsletter_campaigns are global.
CUSTOMER_SHEETS = (
    "customer_master", "customer_value", "energy_contracts", "mobile_contracts", "autostrom_contracts",
    "charge_sessions", "hems_devices", "hems_telemetry_daily", "shop_orders", "service_interactions",
    "call_transcripts", "service_nba_feedback", "consent_status", "nba_action_history",
    "newsletter_performance", "portal_sessions",
)

# Delivered shop product names that count as owning a catalog product (README §6.4).
SHOP_OWNERSHIP = {
    "P-SH-01": {"Balkonkraftwerk 800 W"},
    "P-SH-02": {"Wallbox 11 kW"},
    "P-SH-03": {"Smarte Thermostate 3er"},
    "P-SH-04": {"Smart Plug 4er-Set"},
}


@dataclass(frozen=True)
class CustomerState:
    customer_id: str
    eval_time: datetime
    snapshot_mode: str
    rows: dict[str, list[dict]]
    applied_events: list[dict] = field(default_factory=list)
    revision: str = ""

    def one(self, sheet: str) -> dict | None:
        rs = self.rows.get(sheet) or []
        return rs[0] if rs else None


def _revision(rows: dict[str, list[dict]], events: Iterable[dict]) -> str:
    payload = json.dumps(
        {"rows": rows, "events": sorted(e["event_id"] for e in events)}, sort_keys=True, default=str
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_states(
    tables: dict[str, pd.DataFrame],
    eval_time: datetime = DEFAULT_EVAL_TIME,
    events: list[dict] | None = None,
    snapshot_mode: str = "provided",
    customer_ids: Iterable[str] | None = None,
) -> dict[str, CustomerState]:
    """Group every customer-keyed sheet by customer_id.

    snapshot_mode "provided" uses the snapshot as given (README §10, K8).
    "strict_asof" and event replay are Agent KG's M3 stretch goals.
    """
    if snapshot_mode != "provided":
        raise NotImplementedError("strict_asof replay is Agent KG M3 (README §7.1)")
    if events:
        raise NotImplementedError("event replay is Agent KG M3 (README §7.1); use nba.kg.events")
    wanted = set(customer_ids) if customer_ids is not None else None
    grouped: dict[str, dict[str, list[dict]]] = {}
    for cid in tables["customer_master"]["customer_id"]:
        if wanted is None or cid in wanted:
            grouped[cid] = {s: [] for s in CUSTOMER_SHEETS}
    for sheet in CUSTOMER_SHEETS:
        for rec in tables[sheet].to_dict("records"):
            cid = rec.get("customer_id")
            if cid in grouped:
                grouped[cid][sheet].append(rec)
    return {
        cid: CustomerState(cid, eval_time, snapshot_mode, rows, [], _revision(rows, []))
        for cid, rows in grouped.items()
    }


# ---------------------------------------------------------------- holdings


def _active(rows: list[dict], **match) -> list[dict]:
    return [r for r in rows if r.get("status") == "active" and all(r.get(k) == v for k, v in match.items())]


def active_electricity(state: CustomerState) -> dict | None:
    rs = _active(state.rows["energy_contracts"], commodity="electricity")
    return rs[0] if rs else None


def devices(state: CustomerState) -> set[str]:
    return {r["device_type"] for r in state.rows["hems_devices"] if r.get("device_type")}


def delivered_products(state: CustomerState) -> set[str]:
    return {r["product_name"] for r in state.rows["shop_orders"] if r.get("order_status") == "delivered"}


def active_lines(state: CustomerState) -> set[str]:
    """Business lines held right now: electricity, gas, mobile, autostrom, smart_living."""
    lines = {r["commodity"] for r in _active(state.rows["energy_contracts"])}
    if _active(state.rows["mobile_contracts"]):
        lines.add("mobile")
    if _active(state.rows["autostrom_contracts"]):
        lines.add("autostrom")
    if "hems_gateway" in devices(state):
        lines.add("smart_living")
    return lines


def owns(state: CustomerState, product_id: str) -> bool:
    """True if the customer already holds what the offer sells (README §6.4 "must not hold")."""
    lines, devs, bought = active_lines(state), devices(state), delivered_products(state)
    elec = active_electricity(state)
    if product_id == "P-EN-01":
        return "electricity" in lines
    if product_id == "P-EN-03":
        return bool(elec and elec.get("tariff") == "StromWärme")
    if product_id == "P-EN-04":
        return "gas" in lines
    if product_id == "P-MO-01":
        return "mobile" in lines
    if product_id == "P-AS-01":
        return "autostrom" in lines
    if product_id == "P-SL-01":
        return "hems_gateway" in devs
    if product_id == "P-SH-01":
        return bool(SHOP_OWNERSHIP["P-SH-01"] & bought) or "pv_inverter" in devs or bool(elec and elec.get("feed_in_meter"))
    if product_id == "P-SH-02":
        return bool(SHOP_OWNERSHIP["P-SH-02"] & bought) or "wallbox" in devs
    if product_id == "P-SH-03":
        return bool(SHOP_OWNERSHIP["P-SH-03"] & bought)
    if product_id == "P-SH-04":
        return bool(SHOP_OWNERSHIP["P-SH-04"] & bought) or "smart_plug" in devs
    # Retention, upsells, service and offers without ownership data (P-IN-01, P-EN-05, P-SL-02/03, P-MO-02/03).
    return False


# ---------------------------------------------------------------- contacts


def contacts(state: CustomerState, days: int) -> list[dict]:
    """Delivered, non-control marketing actions decided in (eval_time - days, eval_time]."""
    start = state.eval_time - timedelta(days=days)
    return [
        r for r in state.rows["nba_action_history"]
        if r.get("delivery_status") == "delivered" and not r.get("control_group")
        and r.get("decided_at") and start < r["decided_at"] <= state.eval_time
    ]


# ---------------------------------------------------------------- population


def population(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per customer for percentiles and highlights (Agent CARDS extends the columns)."""
    cv = tables["customer_value"][
        ["customer_id", "clv_eur", "annual_margin_eur", "cost_to_serve_12m_eur", "churn_prob_12m", "active_business_lines"]
    ]
    cm = tables["customer_master"][["customer_id", "birth_year", "household_size", "city"]]
    return cm.merge(cv, on="customer_id", how="left")
