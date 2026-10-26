"""Event replay (README §7.1 step 5, deep dive B stretch). Owner: Agent KG.

Planned: dedup (nba.data.load_events), apply events in ingested_at order with per-fact-key
updates (consent, dunning, cancellation, tickets, gas deregistration with effective_date,
failed charges, data threshold, orders, clicks), log unsupported types, and return the
affected customer IDs so Agent NBA can rebuild their cards. Not implemented yet.
"""

from __future__ import annotations


def replay(states, events, until=None):
    raise NotImplementedError("event replay is the KG stretch goal (PLAN_KG.md step 9)")
