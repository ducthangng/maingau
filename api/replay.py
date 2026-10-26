"""Read-only deep-dive B preview, following scripts/replay_demo.py."""
from __future__ import annotations

from datetime import datetime

from nba.contracts import NO_ACTION
from nba.data import load_events
from nba.engine.assemble import assemble
from nba.kg.events import replay


def replay_preview(runtime, until: datetime | None = None, *, card_provider=None):
    if until is not None and until.tzinfo is not None:
        raise ValueError("Use timezone-naive timestamps from the mock event stream")
    if until is not None and until < max(state.eval_time for state in runtime.states.values()):
        raise ValueError("Replay cutoff must not precede the source snapshot")
    events = load_events()
    provider = card_provider or runtime.card
    customer_ids = sorted({e["customer_id"] for e in events if e.get("customer_id") in runtime.states})
    before = {cid: provider(cid) for cid in customer_ids}
    pending = {}
    for cid, card in before.items():
        if card.chosen.tuple_id == NO_ACTION or card.chosen.status == "rejected":
            continue
        selected = next(c for c in card.candidates if c.tuple_id == card.chosen.tuple_id)
        pending[cid] = (selected.tuple_id, selected.personalised)
    result = replay(runtime.states, events, runtime.policy, runtime.pop, until=until, pending=pending)
    cutoff = next(iter(result.states.values())).eval_time.isoformat()
    cards = []
    for cid in sorted(result.affected):
        card = assemble(result.states[cid], runtime.pop, runtime.policy, runtime.cfg)
        card.meta.events_applied_until = cutoff
        cards.append(card)
    transitions = []
    revoked = {}
    for transition in result.transitions:
        outcome = transition.outcome
        row = {"customer_id": outcome.customer_id, "event_id": outcome.event_id, "event_type": outcome.event_type,
               "occurred_at": outcome.occurred_at.isoformat(), "ingested_at": outcome.ingested_at.isoformat(),
               "delay_hours": outcome.delay_hours, "pending_tuple": transition.pending,
               "pending_status": transition.pending_status, "revoked_by": sorted(set(transition.revoked_by)),
               "reasons": list(transition.revoke_reasons), "signals_added": list(transition.signals_added),
               "signals_removed": list(transition.signals_removed)}
        transitions.append(row)
        if transition.pending_status == "revoked":
            revoked[outcome.customer_id] = row
    return {"preview_only": True, "eval_time": cutoff, "counts": dict(sorted(result.counts().items())),
            "affected": sorted(result.affected), "pending_revocations": revoked,
            "customers": cards, "transitions": transitions}
