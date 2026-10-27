"""Event replay: deep dive B, data freshness (README §7.1 step 5). Owner: Agent KG.

Online semantics:
- events are applied in `ingested_at` order (what the system could know at that moment);
  `occurred_at` updates the facts, and `effective_date` defers contract changes;
- every fact key has its own clock: an older event that arrives later never overwrites a newer fact;
- after each decision-relevant event the KG view of that customer is recomputed at the ingest time,
  and a pending card (offer, channel) is re-checked with `check_tuple`: revoked if a hard rule now
  blocks it. A deferred card already waits for a temporary block (contact cap) that frees up by its
  `deferred_until`, so that block does not revoke it. Cards already delivered in the past cannot be
  revoked — only pending ones.

Three freshness measures (from the audit): arrival-to-invalidation (processing at ingest),
decision-time known-state validity (pending cards re-checked at every transition) and retrospective
late-data exposure (`ingested_at − occurred_at` for events that revoke a card).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime

import pandas as pd

from nba.contracts import Blocked
from nba.kg.policy import Policy
from nba.kg.rules import active_exclusions, check_tuple
from nba.kg.segments import triage
from nba.kg.signals import extract_signals
from nba.state import CustomerState, _revision

# Event types that only feed engagement counters; they never change a decision fact.
INFORMATIONAL = {
    "portal_login", "page_viewed", "newsletter_opened", "charge_session_started", "meter_reading_submitted",
    "cart_abandoned", "hems_daily_summary", "mobile_data_threshold", "call_transcript_ready",
}


@dataclass(frozen=True)
class EventOutcome:
    event_id: str
    event_type: str
    customer_id: str
    occurred_at: datetime
    ingested_at: datetime
    status: str  # applied | stale | informational | orphan | unknown_customer | already_applied
    facts: tuple[str, ...] = ()
    note: str = ""

    @property
    def delay_hours(self) -> float:
        return round((self.ingested_at - self.occurred_at).total_seconds() / 3600, 2)


@dataclass(frozen=True)
class Transition:
    """KG effect of one applied event on one customer, evaluated at the event's ingest time."""

    outcome: EventOutcome
    signals_added: tuple[str, ...]
    signals_removed: tuple[str, ...]
    exclusions_added: tuple[str, ...]
    exclusions_removed: tuple[str, ...]
    tier_before: str
    tier_after: str
    profiled_before: bool
    profiled_after: bool
    flags_added: tuple[str, ...] = ()
    flags_removed: tuple[str, ...] = ()
    pending: str | None = None  # "<offer>|<channel>|<tone>" of the pending card, if any
    pending_status: str | None = None  # valid | revoked
    revoked_by: tuple[str, ...] = ()
    revoke_reasons: tuple[str, ...] = ()


@dataclass
class ReplayResult:
    states: dict[str, CustomerState]
    outcomes: list[EventOutcome] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    affected: set[str] = field(default_factory=set)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for o in self.outcomes:
            out[o.status] = out.get(o.status, 0) + 1
        return out


# ---------------------------------------------------------------- fact updates


class _Clocks:
    """Per-fact-key clocks: the occurred_at of the newest fact applied for each key."""

    def __init__(self):
        self._t: dict[tuple, datetime] = {}

    def newer(self, key: tuple, occurred: datetime, snapshot_time: datetime | None) -> bool:
        current = max([t for t in (self._t.get(key), snapshot_time) if t is not None], default=None)
        return current is None or occurred >= current

    def set(self, key: tuple, occurred: datetime) -> None:
        self._t[key] = occurred


def _active_contract(rows: list[dict], commodity: str | None = None) -> dict | None:
    for r in rows:
        if r.get("status") == "active" and (commodity is None or r.get("commodity") == commodity):
            return r
    return None


def apply_event(rows: dict[str, list[dict]], cid: str, ev: dict, clocks: _Clocks) -> tuple[str, list[str], str]:
    """Mutate `rows` (a private copy) for one event. Returns (status, facts changed, note)."""
    t, p, occ = ev["event_type"], ev.get("payload") or {}, ev["occurred_at"]
    if t in INFORMATIONAL:
        return "informational", [], "engagement only; no decision fact"

    if t == "consent_changed":
        ctype = p["consent_type"]
        row = next((r for r in rows["consent_status"] if r["consent_type"] == ctype), None)
        if row is None:
            row = {"customer_id": cid, "consent_type": ctype}
            rows["consent_status"].append(row)
        if not clocks.newer(("consent", ctype), occ, row.get("updated_at")):
            return "stale", [], f"{ctype}: snapshot or an earlier event is newer than {occ}"
        old = row.get("status")
        row.update(status=p["new_status"], updated_at=occ, source=p.get("source"))
        clocks.set(("consent", ctype), occ)
        return "applied", [f"consent_status.{ctype}: {old} → {p['new_status']}"], ""

    if t == "contract_cancellation_received":
        c = _active_contract(rows["energy_contracts"], p.get("commodity"))
        if c is None:
            return "orphan", [], f"no active {p.get('commodity')} contract to cancel"
        if not clocks.newer(("contract_status", c["contract_id"]), occ, c.get("record_updated_at")):
            return "stale", [], f"{c['contract_id']} has a newer record"
        c.update(status="cancellation_pending", cancellation_received_at=occ)
        clocks.set(("contract_status", c["contract_id"]), occ)
        return "applied", [f"energy_contracts.{c['contract_id']}.status: active → cancellation_pending"], ""

    if t == "dunning_level_changed":
        cands = [r for r in rows["energy_contracts"] if (r.get("dunning_level") or 0) == p.get("old_level")]
        c = cands[0] if cands else _active_contract(rows["energy_contracts"])
        if c is None:
            return "orphan", [], "no energy contract for the dunning change"
        if not clocks.newer(("dunning", c["contract_id"]), occ, c.get("record_updated_at")):
            return "stale", [], f"{c['contract_id']} has a newer dunning record"
        old = c.get("dunning_level")
        c["dunning_level"] = p["new_level"]
        clocks.set(("dunning", c["contract_id"]), occ)
        return "applied", [f"energy_contracts.{c['contract_id']}.dunning_level: {old} → {p['new_level']}"], ""

    if t == "gas_meter_deregistration_received":
        c = _active_contract(rows["energy_contracts"], "gas")
        if c is None:
            return "orphan", [], "no active gas contract"
        eff = ev.get("effective_date")
        c.update(meter_deregistered_at=occ, meter_deregistration_effective=eff)
        facts = [f"energy_contracts.{c['contract_id']}.meter_deregistered_at = {occ:%Y-%m-%d}"
                 + (f" (effective {eff:%Y-%m-%d})" if eff else "")]
        return "applied", facts, "gas stays active until the effective date"

    if t == "ticket_created":
        tid = p.get("ticket_id") or f"TK-{ev['event_id']}"
        rows["service_interactions"].append({
            "ticket_id": tid, "customer_id": cid, "created_at": occ, "channel": p.get("channel"),
            "category": p.get("category"), "message_text": p.get("message_text"), "status": "open",
            "resolved_at": None, "source_event": ev["event_id"],
        })
        return "applied", [f"service_interactions.{tid}: new open {p.get('category')} ticket"], ""

    if t == "ticket_updated":
        tid = p.get("ticket_id")
        row = next((r for r in rows["service_interactions"] if r.get("ticket_id") == tid), None)
        if row is None:
            # Unknown ticket ID: never merge into an arbitrary ticket. Keep a conservative open
            # placeholder with provenance so the exclusion applies (README §3, audit 5.8).
            rows["service_interactions"].append({
                "ticket_id": tid, "customer_id": cid, "created_at": occ, "category": "unknown",
                "status": p.get("status", "open"), "resolved_at": None, "orphan": True,
                "source_event": ev["event_id"], "message_text": p.get("note"),
            })
            return "orphan", [f"service_interactions.{tid}: placeholder ticket ({p.get('status')})"], \
                f"{tid} is not in the snapshot; kept as a conservative open ticket"
        if not clocks.newer(("ticket", tid), occ, row.get("resolved_at") or row.get("created_at")):
            return "stale", [], f"{tid} has a newer update"
        old = row.get("status")
        row["status"] = p.get("status", old)
        clocks.set(("ticket", tid), occ)
        return "applied", [f"service_interactions.{tid}.status: {old} → {row['status']}"], ""

    if t in ("charge_session_failed", "charge_session_completed"):
        contract = next((r for r in rows["autostrom_contracts"] if r.get("status") == "active"), None)
        status = "failed" if t == "charge_session_failed" else "completed"
        rows["charge_sessions"].append({
            "session_id": f"EV-{ev['event_id']}", "contract_id": contract.get("contract_id") if contract else None,
            "customer_id": cid, "started_at": occ, "ended_at": occ, "charge_type": p.get("charge_type"),
            "energy_kwh": p.get("energy_kwh"), "amount_eur": p.get("amount_eur"), "session_status": status,
            "failure_reason": p.get("failure_reason") or ("unknown" if status == "failed" else None),
            "cdr_source": "own_backend", "cdr_received_at": ev["ingested_at"], "location_id": p.get("location_id"),
        })
        return "applied", [f"charge_sessions: new {status} session"], ""

    if t == "order_placed":
        rows["shop_orders"].append({
            "order_id": f"EV-{ev['event_id']}", "customer_id": cid, "order_created_at": occ,
            "product_name": p.get("product_name"), "order_status": "placed", "is_guest": False,
        })
        return "applied", [f"shop_orders: {p.get('product_name')} placed (not yet owned)"], ""

    if t == "newsletter_clicked":
        sent = next((r.get("campaign_sent_at") for r in rows["newsletter_performance"]
                     if r.get("campaign_id") == p.get("campaign_id")), None)
        rows["newsletter_performance"].append({
            "campaign_id": p.get("campaign_id"), "customer_id": cid, "clicked_at": occ,
            "click_target": p.get("click_target"), "delivered": True, "campaign_sent_at": sent,
        })
        return "applied", [f"newsletter_performance: click on {p.get('click_target')}"], ""

    if t == "hems_device_offline":
        dev = next((d for d in rows["hems_devices"] if d.get("device_type") == p.get("device_type")), None)
        if dev is None:
            return "orphan", [], f"no {p.get('device_type')} device"
        dev.update(connection_status="offline", last_seen_at=occ)
        return "applied", [f"hems_devices.{dev['device_id']}: offline"], ""

    if t == "agent_nba_feedback":
        rows["service_nba_feedback"].append({
            "customer_id": cid, "ticket_id": p.get("ticket_id"), "shown_at": occ,
            "suggested_offer_id": p.get("suggested_offer_id"), "agent_action": p.get("agent_action"),
            "dismiss_reason": p.get("dismiss_reason"), "customer_reaction": None,
        })
        return "applied", [f"service_nba_feedback: {p.get('agent_action')} {p.get('suggested_offer_id')} ({p.get('dismiss_reason')})"], ""

    return "informational", [], f"unsupported event type {t}; logged only"


# ---------------------------------------------------------------- replay


def _kg_view(state: CustomerState, policy: Policy, pop: pd.DataFrame):
    sig = extract_signals(state, policy)
    from nba.kg.rules import is_profiled  # local import keeps the module graph simple
    return (sig, triage(state, sig, policy, pop), {r for r, _ in active_exclusions(state, policy)}, is_profiled(state, policy))


def _pending_card(entry) -> tuple[str | None, bool, datetime | None]:
    """tuple_id | (tuple_id, personalised) | (tuple_id, personalised, deferred_until) -> the three parts."""
    if not entry:
        return None, False, None
    if isinstance(entry, str):
        return entry, False, None
    tid, personalised, *rest = entry
    wait = rest[0] if rest else None
    return tid, bool(personalised), datetime.fromisoformat(wait) if isinstance(wait, str) else wait


def _waits_for(b: Blocked, deferred_until: datetime | None) -> bool:
    """The card already waits for this temporary block (contact cap): it frees up by `deferred_until`."""
    return deferred_until is not None and b.until is not None and datetime.fromisoformat(b.until) <= deferred_until


def replay(
    states: dict[str, CustomerState],
    events: list[dict],
    policy: Policy,
    pop: pd.DataFrame,
    until: datetime | None = None,
    pending: dict[str, str | tuple] | None = None,
) -> ReplayResult:
    """Apply events (already deduplicated and sorted by ingested_at) up to `until` (inclusive).

    `pending` maps customer_id -> tuple_id of a not-yet-sent card (e.g. Agent NBA's T0 decision),
    or -> (tuple_id, personalised[, deferred_until]). A personalised card is also revoked when profiling
    consent is gone, even if a generic version of the same offer and channel would still be allowed (D1).
    A deferred card is not revoked by a contact-cap block that frees up on or before its `deferred_until`
    (ISO string or datetime); a cap that frees later, or any other hard rule, still revokes it.
    The returned states have eval_time = `until` (or the last ingest time).
    """
    pending = dict(pending or {})
    clocks = _Clocks()
    work: dict[str, dict[str, list[dict]]] = {}
    applied_ids: dict[str, list[dict]] = {}
    result = ReplayResult(states={})
    last_t = None
    for ev in events:
        if until is not None and ev["ingested_at"] > until:
            break
        last_t = ev["ingested_at"]
        cid = ev.get("customer_id")
        base = states.get(cid)
        if base is None:
            result.outcomes.append(EventOutcome(ev["event_id"], ev["event_type"], cid or "", ev["occurred_at"],
                                                ev["ingested_at"], "unknown_customer", (), "customer not in snapshot"))
            continue
        if any(e["event_id"] == ev["event_id"] for e in applied_ids.get(cid, [])):
            result.outcomes.append(EventOutcome(ev["event_id"], ev["event_type"], cid, ev["occurred_at"],
                                                ev["ingested_at"], "already_applied"))
            continue
        before_state = _state_at(base, work.get(cid), applied_ids.get(cid, []), ev["ingested_at"])
        rows = work.setdefault(cid, copy.deepcopy(base.rows))
        status, facts, note = apply_event(rows, cid, ev, clocks)
        outcome = EventOutcome(ev["event_id"], ev["event_type"], cid, ev["occurred_at"], ev["ingested_at"],
                               status, tuple(facts), note)
        result.outcomes.append(outcome)
        if not facts:
            continue
        applied_ids.setdefault(cid, []).append(ev)
        result.affected.add(cid)
        after_state = _state_at(base, rows, applied_ids[cid], ev["ingested_at"])
        sig_b, tri_b, exc_b, prof_b = _kg_view(before_state, policy, pop)
        sig_a, tri_a, exc_a, prof_a = _kg_view(after_state, policy, pop)
        tr = dict(
            outcome=outcome,
            signals_added=tuple(sorted({s.id for s in sig_a} - {s.id for s in sig_b})),
            signals_removed=tuple(sorted({s.id for s in sig_b} - {s.id for s in sig_a})),
            exclusions_added=tuple(sorted(exc_a - exc_b)),
            exclusions_removed=tuple(sorted(exc_b - exc_a)),
            tier_before=tri_b.urgency_tier, tier_after=tri_a.urgency_tier,
            profiled_before=prof_b, profiled_after=prof_a,
            flags_added=tuple(sorted({f.id for f in tri_a.flags} - {f.id for f in tri_b.flags})),
            flags_removed=tuple(sorted({f.id for f in tri_b.flags} - {f.id for f in tri_a.flags})),
        )
        tid, personalised, deferred_until = _pending_card(pending.get(cid))
        if tid and tid != "NO_ACTION":
            offer, channel, _tone = tid.split("|")
            blockers = [(b.rule_id, b.reason) for b in check_tuple(after_state, offer, channel, policy)
                        if not _waits_for(b, deferred_until)]
            if personalised and not prof_a:
                blockers.append(("CONSENT-PROFILING", "personalised card, but profiling consent was withdrawn"))
            if blockers:
                tr.update(pending=tid, pending_status="revoked", revoked_by=tuple(r for r, _ in blockers),
                          revoke_reasons=tuple(m for _, m in blockers))
                pending.pop(cid)  # a revoked card stays revoked; the engine must re-decide
            else:
                tr.update(pending=tid, pending_status="valid")
        result.transitions.append(Transition(**tr))

    end = until or last_t
    for cid, base in states.items():
        result.states[cid] = _state_at(base, work.get(cid), applied_ids.get(cid, []), end) if end else base
    return result


def _state_at(base: CustomerState, rows: dict | None, applied: list[dict], t: datetime) -> CustomerState:
    """A CustomerState as known at time t: snapshot rows plus applied events, gas deregistration effective dates resolved."""
    if rows is None:
        return replace(base, eval_time=t) if t and t != base.eval_time else base
    snap = copy.deepcopy(rows)
    for c in snap["energy_contracts"]:
        eff = c.get("meter_deregistration_effective")
        if eff is not None and t >= eff and c.get("status") == "active":
            c["status"] = "terminated_meter_deregistration"
    return replace(base, eval_time=t, rows=snap, applied_events=list(applied),
                   snapshot_mode=base.snapshot_mode, revision=_revision(snap, applied))
