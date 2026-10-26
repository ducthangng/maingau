"""Named predicates referenced by kg/policy.yaml (README §6.2–§6.4). Owner: Agent KG.

Three kinds, each registered by name:
- signal predicates return a `Hit` (or None when the signal does not fire);
- holding predicates return (bool, detail) and back REQUIRES / NOT-HELD checks;
- exclusion predicates return a `Hit` describing the active exclusion (or None).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from nba.state import (
    SHOP_OWNERSHIP,
    CustomerState,
    active_electricity,
    active_lines,
    delivered_products,
    devices,
)

SIGNALS: dict[str, Callable[[CustomerState, dict], "Hit | None"]] = {}
HOLDINGS: dict[str, Callable[[CustomerState], tuple[bool, str]]] = {}
EXCLUSIONS: dict[str, Callable[[CustomerState], "Hit | None"]] = {}


@dataclass
class Hit:
    detail: str  # plain-language fact, shown in labels and "why"
    src: str  # "table.column"
    date: datetime | None = None
    evidence: list[str] = field(default_factory=list)
    needs: list[str] | None = None  # narrows the signal's needs (S8 variants)


def _signal(fn):
    SIGNALS[fn.__name__] = fn
    return fn


def _holding(fn):
    HOLDINGS[fn.__name__] = fn
    return fn


def _exclusion(fn):
    EXCLUSIONS[fn.__name__] = fn
    return fn


def _param(prm: dict | None, name: str) -> float:
    """A tunable threshold from kg/policy.yaml `parameters` (README §6.3); required, never guessed."""
    if not prm or name not in prm:
        raise KeyError(f"policy parameter {name!r} missing; load it with nba.kg.policy.load_policy()")
    return prm[name]


def _d(dt: datetime | None) -> str:
    return dt.date().isoformat() if dt else "unknown date"


def _active(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("status") == "active"]


def _master(state: CustomerState) -> dict:
    return state.one("customer_master") or {}


def churn_driver_text(state: CustomerState) -> str:
    """customer_value.churn_drivers as a string; non-string values (None, NaN) count as empty."""
    raw = (state.one("customer_value") or {}).get("churn_drivers")
    return raw if isinstance(raw, str) else ""


def has_profiling(state: CustomerState) -> bool:
    return any(
        r["consent_type"] == "profiling_analytics" and r["status"] == "granted"
        for r in state.rows["consent_status"]
    )


# ---------------------------------------------------------------- signals (README §6.3)


@_signal
def gas_meter_deregistered(s: CustomerState, prm: dict | None = None) -> Hit | None:
    rows = [r for r in s.rows["energy_contracts"] if r["commodity"] == "gas" and r.get("meter_deregistered_at")]
    if not rows:
        return None
    r = max(rows, key=lambda x: x["meter_deregistered_at"])
    days = (s.eval_time - r["meter_deregistered_at"]).days
    eff = r.get("meter_deregistration_effective")  # set by event replay (README §7.1 step 5)
    if eff is not None and eff > s.eval_time:
        detail = f"gas meter deregistration received on {_d(r['meter_deregistered_at'])}, effective {_d(eff)}"
    else:
        detail = f"gas meter deregistered on {_d(r['meter_deregistered_at'])} ({days} days ago)"
    return Hit(detail, "energy_contracts.meter_deregistered_at", r["meter_deregistered_at"], [f"contract:{r['contract_id']}"])


@_signal
def failed_charges_30d(s: CustomerState, prm: dict | None = None) -> Hit | None:
    window, minimum = _param(prm, "failed_charges_window_days"), _param(prm, "failed_charges_min")
    start = s.eval_time - timedelta(days=window)
    fails = [r for r in s.rows["charge_sessions"]
             if r.get("session_status") == "failed" and r.get("started_at") and start < r["started_at"] <= s.eval_time]
    if len(fails) < minimum:
        return None
    reasons = sorted({r.get("failure_reason") or "unknown" for r in fails})
    last = max(r["started_at"] for r in fails)
    return Hit(f"{len(fails)} failed charging sessions in {window} days ({', '.join(reasons)}), last on {_d(last)}",
               "charge_sessions.session_status", last, [f"session:{r['session_id']}" for r in sorted(fails, key=lambda x: x["started_at"])])


@_signal
def wallbox_without_autostrom(s: CustomerState, prm: dict | None = None) -> Hit | None:
    if "autostrom" in active_lines(s):
        return None
    orders = [r for r in s.rows["shop_orders"]
              if r.get("order_status") == "delivered" and r.get("product_name") in SHOP_OWNERSHIP["P-SH-02"]]
    if not orders:
        return None
    o = max(orders, key=lambda x: x["order_created_at"])
    return Hit(f"bought a Wallbox 11 kW on {_d(o['order_created_at'])} but has no Autostrom contract",
               "shop_orders.product_name", o["order_created_at"], [f"order:{o['order_id']}"])


@_signal
def price_guarantee_ending(s: CustomerState, prm: dict | None = None) -> Hit | None:
    hits = []
    for r in _active(s.rows["energy_contracts"]):
        until = r.get("price_guarantee_until")
        if until is not None:
            days = (until.date() - s.eval_time.date()).days
            if 0 <= days < _param(prm, "price_guarantee_window_days"):
                hits.append((days, r))
    if not hits:
        return None
    days, r = min(hits, key=lambda x: x[0])
    return Hit(f"{r['commodity']} price guarantee ends on {_d(r['price_guarantee_until'])} (in {days} days)",
               "energy_contracts.price_guarantee_until", r["price_guarantee_until"], [f"contract:{r['contract_id']}"])


@_signal
def data_limit_repeated(s: CustomerState, prm: dict | None = None) -> Hit | None:
    for r in _active(s.rows["mobile_contracts"]):
        n = r.get("data_limit_reached_3m") or 0
        if n >= _param(prm, "data_limit_min_months"):
            return Hit(f"data limit reached in {n} of the last 3 months ({r.get('plan')}, {r.get('data_volume_gb')} GB)",
                       "mobile_contracts.data_limit_reached_3m", r.get("record_updated_at"), [f"contract:{r['contract_id']}"])
    return None


@_signal
def household_exceeds_sims(s: CustomerState, prm: dict | None = None) -> Hit | None:
    hh = _master(s).get("household_size") or 0
    for r in _active(s.rows["mobile_contracts"]):
        sims = r.get("sim_count") or 0
        if hh > sims:
            return Hit(f"household of {hh} with {sims} SIM(s)", "customer_master.household_size",
                       r.get("record_updated_at") or r.get("start_date"), [f"contract:{r['contract_id']}"])
    return None


@_signal
def pv_without_hems(s: CustomerState, prm: dict | None = None) -> Hit | None:
    devs = devices(s)
    if "hems_gateway" in devs:
        return None
    elec = active_electricity(s)
    if elec and elec.get("feed_in_meter"):
        return Hit("has a feed-in meter (PV) but no HEMS gateway", "energy_contracts.feed_in_meter",
                   elec.get("record_updated_at") or elec.get("start_date"), [f"contract:{elec['contract_id']}"])
    inv = [d for d in s.rows["hems_devices"] if d.get("device_type") == "pv_inverter"]
    if inv:
        return Hit("has a PV inverter but no HEMS gateway", "hems_devices.device_type",
                   inv[0].get("activated_at"), [f"device:{inv[0]['device_id']}"])
    return None


@_signal
def hems_battery_or_wallbox(s: CustomerState, prm: dict | None = None) -> Hit | None:
    devs = devices(s)
    if "hems_gateway" not in devs:
        return None
    needs, parts = [], []
    if "home_battery" in devs:
        needs.append("N-STORAGE-OPT")
        parts.append("home battery")
    if "wallbox" in devs or "autostrom" in active_lines(s):
        needs.append("N-WALLBOX-INTEGRATION")
        parts.append("wallbox/EV")
    if not needs:
        return None
    cited = [d for d in s.rows["hems_devices"] if d.get("device_type") in ("hems_gateway", "home_battery", "wallbox")]
    when = max((d["activated_at"] for d in cited if d.get("activated_at")), default=None)
    return Hit(f"HEMS gateway with {' and '.join(parts)}", "hems_devices.device_type", when,
               [f"device:{d['device_id']}" for d in cited], needs)


@_signal
def smart_meter_flexible_load(s: CustomerState, prm: dict | None = None) -> Hit | None:
    elec = active_electricity(s)
    if not elec or elec.get("meter_type") != "smart_meter_imsys":
        return None
    devs, loads = devices(s), []
    if "hems_gateway" in devs:
        loads.append("HEMS")
    if "autostrom" in active_lines(s):
        loads.append("EV (Autostrom)")
    if "heat_pump" in devs or elec.get("tariff") == "StromWärme":
        loads.append("heat pump")
    if not loads:
        return None
    return Hit(f"smart meter with {', '.join(loads)}", "energy_contracts.meter_type",
               elec.get("record_updated_at") or elec.get("start_date"), [f"contract:{elec['contract_id']}"])


@_signal
def clicked_energy_content(s: CustomerState, prm: dict | None = None) -> Hit | None:
    targets = {"heat_pump_article", "smart_living_landingpage"}
    clicks = [r for r in s.rows["newsletter_performance"]
              if r.get("clicked_at") and r.get("click_target") in targets and r["clicked_at"] <= s.eval_time]
    if not clicks:
        return None
    last = max(clicks, key=lambda r: r["clicked_at"])
    return Hit(f"clicked {last['click_target'].replace('_', ' ')} on {_d(last['clicked_at'])}",
               "newsletter_performance.click_target", last["clicked_at"], [f"click:{last['campaign_id']}"])


@_signal
def autostrom_without_electricity(s: CustomerState, prm: dict | None = None) -> Hit | None:
    lines = active_lines(s)
    if "autostrom" not in lines or "electricity" in lines:
        return None
    a = _active(s.rows["autostrom_contracts"])[0]
    car = " ".join(x for x in (a.get("car_brand"), a.get("car_model")) if x)
    other = [r for r in s.rows["energy_contracts"] if r["commodity"] == "electricity"]
    evidence = [f"contract:{a['contract_id']}"] + [f"contract:{r['contract_id']}" for r in other]
    if other:
        states = ", ".join(f"{r['contract_id']} is {r['status']}" for r in other)
        detail = f"charges with Autostrom ({car}); no active MAINGAU electricity contract ({states})"
    else:
        detail = f"charges with Autostrom ({car}); no MAINGAU home electricity contract"
    return Hit(detail, "autostrom_contracts.status", a.get("start_date"), evidence)


@_signal
def open_ticket(s: CustomerState, prm: dict | None = None) -> Hit | None:
    tickets = [r for r in s.rows["service_interactions"] if r.get("status") == "open"]
    if not tickets:
        return None
    t = sorted(tickets, key=lambda r: (r.get("category") != "complaint", r["created_at"]))[0]
    return Hit(f"open {t['category']} ticket {t['ticket_id']} since {_d(t['created_at'])}",
               "service_interactions.status", t["created_at"], [f"ticket:{r['ticket_id']}" for r in tickets])


@_signal
def dunning_or_cancellation(s: CustomerState, prm: dict | None = None) -> Hit | None:
    for fn in (excl_cancellation, excl_dunning):
        hit = fn(s)
        if hit:
            return hit
    return None


# ---------------------------------------------------------------- holdings (README §6.4)


@_holding
def has_active_electricity(s: CustomerState) -> tuple[bool, str]:
    e = active_electricity(s)
    return (True, f"active electricity contract ({e.get('tariff')})") if e else (False, "no active electricity contract")


@_holding
def has_active_mobile(s: CustomerState) -> tuple[bool, str]:
    m = _active(s.rows["mobile_contracts"])
    return (True, f"active mobile contract ({m[0].get('plan')})") if m else (False, "no active mobile contract")


@_holding
def has_active_autostrom(s: CustomerState) -> tuple[bool, str]:
    return ("autostrom" in active_lines(s), "active Autostrom contract" if "autostrom" in active_lines(s) else "no Autostrom contract")


@_holding
def has_tariff_stromwaerme(s: CustomerState) -> tuple[bool, str]:
    e = active_electricity(s)
    on = bool(e and e.get("tariff") == "StromWärme")
    return on, "already on StromWärme" if on else "not on StromWärme"


@_holding
def has_smart_meter(s: CustomerState) -> tuple[bool, str]:
    e = active_electricity(s)
    ok = bool(e and e.get("meter_type") == "smart_meter_imsys")
    return ok, "smart meter (iMSys)" if ok else "no smart meter"


@_holding
def has_price_guarantee_driver(s: CustomerState) -> tuple[bool, str]:
    ok = "price guarantee ends <90d" in churn_driver_text(s)
    return ok, "churn driver 'price guarantee ends <90d' present" if ok else "no price-guarantee churn driver"


@_holding
def has_hems_gateway(s: CustomerState) -> tuple[bool, str]:
    ok = "hems_gateway" in devices(s)
    return ok, "HEMS gateway installed" if ok else "no HEMS gateway"


@_holding
def has_home_battery(s: CustomerState) -> tuple[bool, str]:
    ok = "home_battery" in devices(s)
    return ok, "home battery installed" if ok else "no home battery"


@_holding
def has_wallbox_or_ev(s: CustomerState) -> tuple[bool, str]:
    ok = "wallbox" in devices(s) or "autostrom" in active_lines(s)
    return ok, "wallbox or EV present" if ok else "no wallbox or EV"


@_holding
def owns_pv_or_balkonkraftwerk(s: CustomerState) -> tuple[bool, str]:
    e = active_electricity(s)
    ok = bool(SHOP_OWNERSHIP["P-SH-01"] & delivered_products(s)) or "pv_inverter" in devices(s) or bool(e and e.get("feed_in_meter"))
    return ok, "already has PV or a Balkonkraftwerk" if ok else "no PV"


@_holding
def owns_wallbox(s: CustomerState) -> tuple[bool, str]:
    ok = bool(SHOP_OWNERSHIP["P-SH-02"] & delivered_products(s)) or "wallbox" in devices(s)
    return ok, "already has a wallbox" if ok else "no wallbox"


@_holding
def owns_thermostats(s: CustomerState) -> tuple[bool, str]:
    ok = bool(SHOP_OWNERSHIP["P-SH-03"] & delivered_products(s))
    return ok, "already bought smart thermostats" if ok else "no smart thermostats"


@_holding
def owns_smart_plug(s: CustomerState) -> tuple[bool, str]:
    ok = bool(SHOP_OWNERSHIP["P-SH-04"] & delivered_products(s)) or "smart_plug" in devices(s)
    return ok, "already has smart plugs" if ok else "no smart plugs"


# ---------------------------------------------------------------- exclusions (README §6.2)


@_exclusion
def excl_dunning(s: CustomerState) -> Hit | None:
    rows = [r for r in s.rows["energy_contracts"] if (r.get("dunning_level") or 0) >= 1]
    if not rows:
        return None
    r = max(rows, key=lambda x: x["dunning_level"])
    return Hit(f"dunning_level = {r['dunning_level']}", "energy_contracts.dunning_level",
               r.get("record_updated_at"), [f"contract:{r['contract_id']}"])


@_exclusion
def excl_cancellation(s: CustomerState) -> Hit | None:
    rows = [r for r in s.rows["energy_contracts"] if r.get("status") == "cancellation_pending"]
    if not rows:
        return None
    r = rows[0]
    return Hit(f"{r['commodity']} cancellation received on {_d(r.get('cancellation_received_at'))}",
               "energy_contracts.status", r.get("cancellation_received_at"), [f"contract:{r['contract_id']}"])


@_exclusion
def excl_open_ticket(s: CustomerState) -> Hit | None:
    return open_ticket(s)


@_exclusion
def excl_autostrom_cancelled(s: CustomerState) -> Hit | None:
    rows = [r for r in s.rows["autostrom_contracts"] if r.get("status") == "cancelled"]
    if not rows:
        return None
    r = rows[0]
    return Hit(f"Autostrom cancelled on {_d(r.get('cancelled_at'))}", "autostrom_contracts.status",
               r.get("cancelled_at"), [f"contract:{r['contract_id']}"])


# ---------------------------------------------------------------- helpers shared with triage


def driver_flags(state: CustomerState) -> set[str]:
    """Churn-driver labels without the multi-product tag, e.g. {'open complaint', '2 tickets in 12m'}."""
    raw = churn_driver_text(state)
    return {t.strip() for t in raw.split(";") if t.strip() and not re.match(r"multi-product", t.strip())}
