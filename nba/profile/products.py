"""Product grid (README §4.1 A3): six business lines; an empty cell is an opportunity."""

from __future__ import annotations

from nba.contracts import ProductLine, Products
from nba.profile.facts import clean, day, fact_dict
from nba.state import devices


def _item(row: dict, sheet: str, key: str, cols: list[str], extra: dict | None = None) -> dict:
    item = {c: fact_dict(row.get(c), f"{sheet}.{c}", row, row_key=row.get(key)) for c in cols}
    item.update(extra or {})
    return item


def _energy(state) -> ProductLine:
    rows = sorted(state.rows.get("energy_contracts", []), key=lambda r: (r.get("status") != "active", r["contract_id"]))
    items = []
    for r in rows:
        days_left = None
        if r.get("status") == "active" and clean(r.get("price_guarantee_until")):
            days_left = (r["price_guarantee_until"].date() - state.eval_time.date()).days
        cols = ["contract_id", "commodity", "tariff", "status", "annual_consumption_kwh", "price_guarantee_until",
                "meter_type", "feed_in_meter", "payment_method", "start_date"]
        cols += [c for c in ("cancellation_received_at", "meter_deregistered_at") if clean(r.get(c))]
        items.append(_item(r, "energy_contracts", "contract_id", cols, {
            "guarantee_days_left": fact_dict(days_left, "energy_contracts.price_guarantee_until", r, row_key=r["contract_id"]),
        }))
    held = any(r.get("status") in ("active", "cancellation_pending") for r in rows)
    pending = [r for r in rows if r.get("status") == "cancellation_pending"]
    note = f"cancellation pending (received {day(pending[0].get('cancellation_received_at'))})" if pending else None
    return ProductLine(held=held, opportunity=not held, items=items, note=note)


def _autostrom(state) -> ProductLine:
    sessions = state.rows.get("charge_sessions", [])
    items = []
    for r in sorted(state.rows.get("autostrom_contracts", []), key=lambda r: r["contract_id"]):
        own = [s for s in sessions if s.get("contract_id") == r["contract_id"] and s.get("session_status") == "completed"]
        kwh = sum(clean(s.get("energy_kwh")) or 0 for s in own)
        months = {s["started_at"].strftime("%Y-%m") for s in own if s.get("started_at")}
        dc = sum(clean(s.get("energy_kwh")) or 0 for s in own if s.get("charge_type") == "DC")
        car = " ".join(str(x) for x in (clean(r.get("car_brand")), clean(r.get("car_model"))) if x) or None
        cols = ["contract_id", "status", "battery_kwh", "charge_cards", "app_user", "start_date"]
        cols += [c for c in ("cancelled_at",) if clean(r.get(c))]
        items.append(_item(r, "autostrom_contracts", "contract_id", cols, {
            "car": fact_dict(car, "autostrom_contracts.car_model", r, row_key=r["contract_id"]),
            "kwh_per_month": fact_dict(round(kwh / len(months), 1) if months else None,
                                       "charge_sessions.energy_kwh", own[-1] if own else None, row_key=r["contract_id"]),
            "dc_share": fact_dict(round(dc / kwh, 3) if kwh else None,
                                  "charge_sessions.charge_type", own[-1] if own else None, row_key=r["contract_id"]),
        }))
    held = any(r.get("status") == "active" for r in state.rows.get("autostrom_contracts", []))
    return ProductLine(held=held, opportunity=not held, items=items)


def _mobile(state) -> ProductLine:
    cm = state.one("customer_master") or {}
    items = []
    for r in sorted(state.rows.get("mobile_contracts", []), key=lambda r: r["contract_id"]):
        items.append(_item(r, "mobile_contracts", "contract_id", [
            "contract_id", "plan", "status", "data_volume_gb", "avg_data_used_gb_3m", "data_limit_reached_3m",
            "sim_count", "esim", "min_term_end",
        ], {"household_size": fact_dict(cm.get("household_size"), "customer_master.household_size", cm,
                                        row_key=state.customer_id)}))
    held = any(r.get("status") == "active" for r in state.rows.get("mobile_contracts", []))
    return ProductLine(held=held, opportunity=not held, items=items)


def _shop(state, limit: int = 5) -> ProductLine:
    rows = sorted(state.rows.get("shop_orders", []),
                  key=lambda r: (r.get("order_created_at") is None, r.get("order_created_at")), reverse=True)
    rows = [r for r in rows if r.get("customer_id")]
    items = [_item(r, "shop_orders", "order_id", ["order_id", "product_name", "product_category", "order_status",
                                                  "order_created_at", "line_value_eur"]) for r in rows[:limit]]
    held = any(r.get("order_status") == "delivered" for r in rows)
    note = f"{len(rows) - limit} older orders not shown" if len(rows) > limit else None
    return ProductLine(held=held, opportunity=not held, items=items, note=note)


def _smart_living(state) -> ProductLine:
    rows = sorted(state.rows.get("hems_devices", []), key=lambda r: (r.get("device_type") or "", r["device_id"]))
    items = [_item(r, "hems_devices", "device_id", ["device_id", "device_type", "connection_status", "last_seen_at",
                                                     "manufacturer"]) for r in rows]
    held = "hems_gateway" in devices(state)
    note = None
    gateways = [r for r in rows if r.get("device_type") == "hems_gateway"]
    offline = [r for r in gateways if r.get("connection_status") != "online"]
    if offline:
        note = f"HEMS gateway {offline[0].get('connection_status')} (last seen {day(offline[0].get('last_seen_at'))})"
    elif rows and not gateways:
        note = "devices without a HEMS gateway"
    return ProductLine(held=held, opportunity=not held, items=items, note=note)


def build_products(state) -> Products:
    return Products(
        energy=_energy(state),
        autostrom=_autostrom(state),
        mobile=_mobile(state),
        shop=_shop(state),
        smart_living=_smart_living(state),
        internet=ProductLine(held=None, opportunity=False,
                             note="No ownership or availability data; P-IN-01 is not evaluated (not enough data)"),
    )
