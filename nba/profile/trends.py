"""Mini-chart payloads (README §4.1 B2). Each trend states the real date range of its source.

Shapes (Trends values are free-form dicts in the contract; the UI relies on these keys):
- every trend: {"src": "<table>", "range": {"from": date, "to": date}, "notes": [str]}
- charging: months[{month, kwh, sessions, failed, ac_kwh, dc_kwh}], failures_by_reason{}, markers[{date, label}]
- portal: months[{month, sessions, offers, tariff_overview, consumption_chart}]
- newsletter: delivered, real_opens, prefetch_opens_excluded, clicks, clicks_by_target{}, unsubscribed, months[{month, opens, clicks}]
- service: quarters[{quarter, tickets}], open, repeat_contacts, latest_csat{v, date, ticket_id}|null, goodwill_eur
- mobile_usage: plan, data_volume_gb, avg_data_used_gb_3m, data_limit_reached_3m, usage_share
- hems: days_with_data, days_missing, self_consumption_rate_avg, grid_export_kwh, heat_pump_kwh, ev_charging_kwh, daily[]
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from nba.contracts import Trends
from nba.profile.facts import clean, day, to_datetime

PORTAL_PAGES = ("offers", "tariff_overview", "consumption_chart")


def _months(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= end[:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _range(ranges: dict, key: str) -> dict:
    lo, hi = ranges[key]
    return {"from": str(lo), "to": str(hi)}


def _num(v) -> float:
    return clean(v) or 0


def _charging(state, ranges: dict) -> dict | None:
    sessions = state.rows.get("charge_sessions", [])
    if not sessions and not state.rows.get("autostrom_contracts"):
        return None
    rng = _range(ranges, "charging")
    months = {m: {"month": m, "kwh": 0.0, "sessions": 0, "failed": 0, "ac_kwh": 0.0, "dc_kwh": 0.0}
              for m in _months(rng["from"], rng["to"])}
    reasons: Counter = Counter()
    for s in sessions:
        if not s.get("started_at"):
            continue
        row = months.get(s["started_at"].strftime("%Y-%m"))
        if row is None:
            continue
        row["sessions"] += 1
        if s.get("session_status") == "failed":
            row["failed"] += 1
            reasons[clean(s.get("failure_reason")) or "unknown"] += 1
        elif s.get("session_status") == "completed":
            kwh = _num(s.get("energy_kwh"))
            row["kwh"] += kwh
            row["ac_kwh" if s.get("charge_type") == "AC" else "dc_kwh"] += kwh
    for row in months.values():
        for k in ("kwh", "ac_kwh", "dc_kwh"):
            row[k] = round(row[k], 1)
    return {
        "src": "charge_sessions", "range": rng,
        "months": list(months.values()),
        "failures_by_reason": dict(sorted(reasons.items())),
        "markers": [{"date": "2026-07-01", "label": "AC price cut 0.62 → 0.52 €/kWh"}],
        "notes": ["Roaming CDRs can arrive up to 72 h late (charge_sessions.cdr_received_at)"],
    }


def _portal(state, ranges: dict) -> dict | None:
    cm = state.one("customer_master") or {}
    sessions = state.rows.get("portal_sessions", [])
    if not sessions and not cm.get("portal_account"):
        return None
    rng = _range(ranges, "portal")
    months = {m: {"month": m, "sessions": 0, **{p: 0 for p in PORTAL_PAGES}} for m in _months(rng["from"], rng["to"])}
    for s in sessions:
        t = to_datetime(s.get("session_start"))
        row = months.get(t.strftime("%Y-%m")) if t else None
        if row is None:
            continue
        row["sessions"] += 1
        pages = set(str(clean(s.get("pages_viewed")) or "").split("|"))
        for p in PORTAL_PAGES:
            row[p] += p in pages
    return {"src": "portal_sessions", "range": rng, "months": list(months.values()),
            "notes": ["Page views are counted per session from portal_sessions.pages_viewed"]}


def _newsletter(state, ranges: dict) -> dict | None:
    rows = state.rows.get("newsletter_performance", [])
    if not rows:
        return None
    rng = _range(ranges, "newsletter")
    months = {m: {"month": m, "opens": 0, "clicks": 0} for m in _months(rng["from"], rng["to"])}
    real_opens = prefetch = clicks = 0
    targets: Counter = Counter()
    for r in rows:
        opened = clean(r.get("opened_at"))
        if opened is not None:
            if clean(r.get("open_client_class")) == "apple_mpp_prefetch":
                prefetch += 1
            else:
                real_opens += 1
                if (row := months.get(opened.strftime("%Y-%m"))) is not None:
                    row["opens"] += 1
        clicked = clean(r.get("clicked_at"))
        if clicked is not None:
            clicks += 1
            targets[clean(r.get("click_target")) or "unknown"] += 1
            if (row := months.get(clicked.strftime("%Y-%m"))) is not None:
                row["clicks"] += 1
    return {
        "src": "newsletter_performance", "range": rng,
        "delivered": sum(1 for r in rows if r.get("delivered")),
        "real_opens": real_opens, "prefetch_opens_excluded": prefetch, "clicks": clicks,
        "clicks_by_target": dict(sorted(targets.items())),
        "unsubscribed": any(r.get("unsubscribed") for r in rows),
        "months": list(months.values()),
        "notes": ["Apple Mail privacy prefetch opens are excluded (open_client_class = apple_mpp_prefetch)"],
    }


def _quarter(d: datetime) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _service(state) -> dict:
    end = state.eval_time
    start = end - timedelta(days=365)
    tickets = sorted((r for r in state.rows.get("service_interactions", [])
                      if r.get("created_at") and start < r["created_at"] <= end), key=lambda r: r["created_at"])
    quarters, d = [], datetime(start.year, start.month, 1)
    while d <= end:
        if (q := _quarter(d)) not in quarters:
            quarters.append(q)
        d = datetime(d.year + (d.month == 12), d.month % 12 + 1, 1)
    counts = Counter(_quarter(r["created_at"]) for r in tickets)
    rated = [r for r in tickets if clean(r.get("csat_1to5")) is not None]
    latest = rated[-1] if rated else None
    return {
        "src": "service_interactions", "range": {"from": str((start + timedelta(days=1)).date()), "to": str(end.date())},
        "quarters": [{"quarter": q, "tickets": counts.get(q, 0)} for q in quarters],
        "open": sum(1 for r in tickets if r.get("status") == "open"),
        "repeat_contacts": sum(1 for r in tickets if clean(r.get("repeat_of_ticket_id"))),
        "latest_csat": {"v": clean(latest["csat_1to5"]), "date": day(latest["created_at"]),
                        "ticket_id": latest["ticket_id"]} if latest else None,
        "goodwill_eur": round(sum(_num(r.get("goodwill_eur")) for r in tickets), 2),
        "notes": [],
    }


def _mobile(state) -> dict | None:
    active = [r for r in state.rows.get("mobile_contracts", []) if r.get("status") == "active"]
    if not active:
        return None
    r = sorted(active, key=lambda r: r["contract_id"])[0]
    vol, used = clean(r.get("data_volume_gb")), clean(r.get("avg_data_used_gb_3m"))
    return {
        "src": "mobile_contracts", "range": None, "contract_id": r["contract_id"], "plan": clean(r.get("plan")),
        "data_volume_gb": vol, "avg_data_used_gb_3m": used,
        "data_limit_reached_3m": clean(r.get("data_limit_reached_3m")),
        "usage_share": round(used / vol, 3) if vol and used is not None else None,
        "notes": ["Only 3-month aggregates exist; no usage trend"],
    }


def _hems(state, ranges: dict) -> dict | None:
    rows = sorted(state.rows.get("hems_telemetry_daily", []), key=lambda r: r["date"])
    if not rows:
        return None
    rng = _range(ranges, "hems")
    n_days = (date.fromisoformat(rng["to"]) - date.fromisoformat(rng["from"])).days + 1
    rates = [clean(r.get("self_consumption_rate")) for r in rows if clean(r.get("self_consumption_rate")) is not None]
    return {
        "src": "hems_telemetry_daily", "range": rng,
        "days_with_data": len(rows), "days_missing": max(0, n_days - len(rows)),
        "self_consumption_rate_avg": round(sum(rates) / len(rates), 3) if rates else None,
        "grid_export_kwh": round(sum(_num(r.get("grid_export_kwh")) for r in rows), 1),
        "heat_pump_kwh": round(sum(_num(r.get("heat_pump_kwh")) for r in rows), 1),
        "ev_charging_kwh": round(sum(_num(r.get("ev_charging_kwh")) for r in rows), 1),
        "daily": [{"date": day(r["date"]),
                   **{k: clean(r.get(k)) for k in ("self_consumption_rate", "grid_export_kwh", "heat_pump_kwh",
                                                    "ev_charging_kwh")}} for r in rows],
        "notes": ["Missing days mean the device was offline"],
    }


def build_trends(state, ranges: dict) -> Trends:
    return Trends(
        charging=_charging(state, ranges),
        portal=_portal(state, ranges),
        newsletter=_newsletter(state, ranges),
        service=_service(state),
        mobile_usage=_mobile(state),
        hems=_hems(state, ranges),
    )
