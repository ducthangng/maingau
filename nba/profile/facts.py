"""Helpers shared by the profile builders: value cleaning and Fact construction (README §5.3)."""

from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any

from nba.contracts import Fact

# Event-time columns used for Fact.updated_at when a sheet has no record_updated_at (README §5.3).
EVENT_TIME_COLUMNS = (
    "created_at", "started_at", "date", "decided_at", "order_created_at", "call_started_at",
    "activated_at", "last_seen_at", "start_date",
)


def clean(v: Any) -> Any:
    """None for NaN/NA; plain Python scalars for numpy values."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item") and not isinstance(v, (str, bytes, datetime, date)):
        try:
            return clean(v.item())
        except (TypeError, ValueError):
            return v
    try:
        if v != v:  # pd.NA / NaT
            return None
    except TypeError:
        return None
    return v


def iso(v: Any) -> str | None:
    """ISO date for midnight timestamps, ISO date-time otherwise."""
    v = clean(v)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == time(0) else v.isoformat(timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def day(v: Any) -> str | None:
    """ISO date only."""
    v = clean(v)
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return None if v is None else str(v)[:10]


def to_datetime(v: Any) -> datetime | None:
    """Parse the few timestamp columns load_workbook leaves as strings (e.g. portal session_start)."""
    v = clean(v)
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except ValueError:
        return None


def row_updated(row: dict | None, sheet: str) -> str | None:
    """Fact.updated_at for a row, following README §5.3."""
    if not row:
        return None
    if sheet == "customer_value":
        return iso(row.get("clv_calc_date"))
    if sheet == "consent_status":
        return iso(row.get("updated_at"))
    if row.get("record_updated_at") is not None:
        return iso(row["record_updated_at"])
    for col in EVENT_TIME_COLUMNS:
        if clean(row.get(col)) is not None:
            return iso(row[col])
    return None


def fact(v: Any, src: str, row: dict | None = None, sheet: str | None = None, row_key: str | None = None) -> Fact:
    """A displayed value with its source; updated_at comes from the row (README §5.3)."""
    v = clean(v)
    if isinstance(v, (datetime, date)):
        v = iso(v)
    sheet = sheet or src.split(".", 1)[0]
    return Fact(v=v, src=src, updated_at=row_updated(row, sheet), row_key=row_key)


def fact_dict(v: Any, src: str, row: dict | None = None, sheet: str | None = None, row_key: str | None = None) -> dict:
    """Fact as a plain dict, for ProductLine.items and trend payloads."""
    return fact(v, src, row, sheet, row_key).model_dump()
