"""Freshness and data-quality flags (README §6.9). Owner: Agent KG. Flags never block a decision."""

from __future__ import annotations

from datetime import timedelta

from nba.contracts import DataQuality
from nba.state import CustomerState

INCONSISTENT_TICKETS = {"TK-200565", "TK-200640"}


def data_quality(state: CustomerState, params: dict | None = None) -> list[DataQuality]:
    """Flags per README §6.9; thresholds from kg/policy.yaml `parameters` (defaults 72 h / 31 days)."""
    prm = params or {}
    hours, stale_days = prm.get("roaming_late_hours", 72), prm.get("value_stale_days", 31)
    out: list[DataQuality] = []
    t = state.eval_time
    roaming_recent = [r for r in state.rows["charge_sessions"]
                      if r.get("cdr_source") == "roaming_hub" and r.get("started_at") and t - timedelta(hours=hours) < r["started_at"] <= t]
    if roaming_recent:
        out.append(DataQuality(code="FRESH-CDR", level="warn",
                               detail=f"{len(roaming_recent)} roaming session(s) in the last {hours} h; roaming CDRs can arrive up to {hours} h late"))
    gateways = [d for d in state.rows["hems_devices"] if d.get("device_type") == "hems_gateway"]
    if gateways:
        offline = [d for d in gateways if d.get("connection_status") != "online"]
        days = {r["date"].date() for r in state.rows["hems_telemetry_daily"] if r.get("date")}
        missing = 30 - len(days)
        if offline or missing > 0:
            parts = []
            if offline:
                parts.append(f"gateway {offline[0].get('connection_status')}")
            if missing > 0:
                parts.append(f"{missing} of 30 September days without telemetry")
            out.append(DataQuality(code="FRESH-HEMS", level="warn", detail="; ".join(parts)))
    value = state.one("customer_value") or {}
    calc = value.get("clv_calc_date")
    if calc and (t - calc).days > stale_days:
        out.append(DataQuality(code="FRESH-VALUE", level="warn", detail=f"customer_value calculated on {calc.date()}"))
    late = [r for r in state.rows["charge_sessions"] if r.get("cdr_received_at") and r["cdr_received_at"] > t]
    if late:
        out.append(DataQuality(code="SNAPSHOT-INCONSISTENT", level="info",
                               detail=f"{len(late)} charging record(s) received after the snapshot cutoff"))
    odd = [r["ticket_id"] for r in state.rows["service_interactions"] if r.get("ticket_id") in INCONSISTENT_TICKETS]
    if odd:
        out.append(DataQuality(code="SNAPSHOT-INCONSISTENT", level="info",
                               detail=f"ticket {odd[0]} is closed but resolved after the snapshot cutoff"))
    return out
