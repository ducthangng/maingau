"""Shared contact counter for every frequency rule (docs/rule-center.md §4). Owner: Agent KG.

One list of contact events per customer, merged from the sources below and de-duplicated by
channel + timestamp. Each rule picks its sources and channels; the window is (at - days, at].

  nba_history       nba_action_history, delivered and not control group, at decided_at
  newsletter        newsletter_performance, delivered, at newsletter_campaigns.sent_at (as newsletter_email)
  service_feedback  service_nba_feedback with offer_mentioned_to_customer, at shown_at (as a phone contact)

The engine's own decision log is not in the workbook; callers pass those events as `extra`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from nba.state import CustomerState

SOURCES = ("nba_history", "newsletter", "service_feedback")
EMAIL_CHANNELS = ("newsletter_email", "email")
PHONE_CHANNEL = "outbound_call"
SOURCE_SRC = {
    "nba_history": "nba_action_history.decided_at",
    "newsletter": "newsletter_campaigns.sent_at",
    "service_feedback": "service_nba_feedback.shown_at",
}


@dataclass(frozen=True)
class ContactEvent:
    ts: datetime
    channel: str
    source: str
    ref: str | None = None


def _yes(value) -> bool:
    """Booleans arrive as bool or as text (service_nba_feedback.offer_mentioned_to_customer is 'True'/'False')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, (int, float)):
        return value == 1
    return False


def check_sources(sources: Iterable[str]) -> tuple[str, ...]:
    sources = tuple(sources)
    unknown = sorted(set(sources) - set(SOURCES))
    if unknown:
        raise ValueError(f"unknown contact source(s) {unknown}; use {list(SOURCES)}")
    return sources


def contact_events(state: CustomerState, sources: Iterable[str] = SOURCES,
                   extra: Iterable[ContactEvent] = ()) -> list[ContactEvent]:
    """Every contact of this customer from `sources` (+ `extra`), oldest first, one per channel + time."""
    sources = check_sources(sources)
    found: dict[tuple[str, datetime], ContactEvent] = {}

    def add(ts, channel, source, ref):
        if ts is not None and channel:
            found.setdefault((channel, ts), ContactEvent(ts, channel, source, ref))

    if "nba_history" in sources:
        for r in state.rows["nba_action_history"]:
            if r.get("delivery_status") == "delivered" and not _yes(r.get("control_group")):
                add(r.get("decided_at"), r.get("channel"), "nba_history", r.get("action_id"))
    if "newsletter" in sources:
        for r in state.rows["newsletter_performance"]:
            if _yes(r.get("delivered")):
                add(r.get("campaign_sent_at"), "newsletter_email", "newsletter", r.get("campaign_id"))
    if "service_feedback" in sources:
        for r in state.rows["service_nba_feedback"]:
            if _yes(r.get("offer_mentioned_to_customer")):
                add(r.get("shown_at"), PHONE_CHANNEL, "service_feedback", r.get("feedback_id") or r.get("ticket_id"))
    for e in extra:
        add(e.ts, e.channel, e.source, e.ref)
    return sorted(found.values(), key=lambda e: (e.ts, e.channel, e.ref or ""))


def window(events: Iterable[ContactEvent], days: int, at: datetime,
           channels: Iterable[str] | None = None) -> list[ContactEvent]:
    """Events in (at - days, at], optionally only on `channels`. Later events are not counted yet."""
    start, wanted = at - timedelta(days=days), set(channels) if channels is not None else None
    return [e for e in events if start < e.ts <= at and (wanted is None or e.channel in wanted)]


def free_from(events: Iterable[ContactEvent], days: int, limit: int, at: datetime,
              channels: Iterable[str] | None = None) -> datetime | None:
    """Earliest time after `at` with fewer than `limit` events in the window; None if that holds at `at`."""
    if limit < 1:
        raise ValueError("a contact limit must be at least 1")
    inside = window(events, days, at, channels)
    if len(inside) < limit:
        return None
    # the window must lose len(inside) - limit + 1 events; the k-th oldest leaves at its time + days
    return inside[len(inside) - limit].ts + timedelta(days=days)


def source_text(sources: Iterable[str]) -> str:
    return "; ".join(SOURCE_SRC[s] for s in check_sources(sources))
