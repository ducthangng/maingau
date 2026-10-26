"""KG audit (stretch): event replay against the raw event stream (README §5.1, §6.14)."""

from __future__ import annotations

import copy
from datetime import datetime

import pytest

from kg_audit_oracle import SALES_TYPES, expected_events, raw_event_lines

from nba.data import load_events
from nba.kg.events import replay
from nba.kg.rules import active_exclusions, consents, generate_candidates, is_profiled
from nba.kg.segments import triage
from nba.kg.signals import extract_signals


def _parse(ev: dict) -> dict:
    """The raw JSONL line with the same field parsing as load_events, but without dedup."""
    out = copy.deepcopy(ev)
    for k in ("occurred_at", "ingested_at"):
        out[k] = datetime.fromisoformat(out[k])
    eff = (out.get("payload") or {}).get("effective_date")
    out["effective_date"] = datetime.fromisoformat(eff) if eff else None
    return out


@pytest.fixture(scope="module")
def events():
    return load_events()


@pytest.fixture(scope="module")
def full(states, policy, pop, events):
    return replay(states, events, policy, pop)


def _ev(cid, etype):
    return next(e for e in raw_event_lines() if e["customer_id"] == cid and e["event_type"] == etype)


def test_events_are_processed_in_ingest_order(full):
    assert [o.event_id for o in full.outcomes] == [eid for eid, _ in expected_events()]
    assert [o.ingested_at for o in full.outcomes] == sorted(o.ingested_at for o in full.outcomes)


def test_duplicate_lines_are_applied_once(states, policy, pop, full):
    lines = [_parse(e) for e in raw_event_lines()]
    assert len(lines) == 647
    lines.sort(key=lambda e: (e["ingested_at"], e["event_id"]))
    noisy = replay(states, lines, policy, pop)
    statuses = [o.status for o in noisy.outcomes]
    assert len(statuses) == 647
    dup_ids = [e["event_id"] for e in lines]
    assert len(dup_ids) - len(set(dup_ids)) == 12
    assert {c: s.revision for c, s in noisy.states.items()} == {c: s.revision for c, s in full.states.items()}


def test_mg_100003_consent_changes_take_effect(states, policy, full):
    assert is_profiled(states["MG-100003"], policy)
    s = full.states["MG-100003"]
    c = consents(s, policy)
    assert c["profiling_analytics"].effective_status == "withdrawn"
    assert c["newsletter_email"].effective_status == "withdrawn"
    cands, blocked = generate_candidates(s, extract_signals(s, policy), policy, "sie")
    assert not [x for x in cands if x.origin == "signal" or x.personalised or x.channel == "newsletter_email"]


def test_mg_100465_cancellation_adds_exclusion_and_removes_sales(states, policy, full):
    # Premise check: MG-100465 has no consented marketing channel at T0, so it never had a sales tuple to
    # remove (logged). The exclusion is therefore checked per sales offer with check_tuple instead.
    from nba.kg.rules import check_tuple

    before, s = states["MG-100465"], full.states["MG-100465"]
    sales = [o.id for o in policy.offers.values() if o.action_type in SALES_TYPES]
    assert not any(b.rule_id == "EXCL-CANCELLATION" for oid in sales for b in check_tuple(before, oid, "email", policy))
    assert all(any(b.rule_id == "EXCL-CANCELLATION" for b in check_tuple(s, oid, "email", policy)) for oid in sales)
    assert "EXCL-CANCELLATION" in dict(active_exclusions(s, policy))
    cands, blocked = generate_candidates(s, extract_signals(s, policy), policy, "sie")
    assert not [c for c in cands if c.action_type in SALES_TYPES]
    assert any(b.offer_id == "*" and b.rule_id == "EXCL-CANCELLATION" for b in blocked)
    ev = _ev("MG-100465", "contract_cancellation_received")
    row = next(r for r in s.rows["energy_contracts"] if r["status"] == "cancellation_pending")
    assert row["commodity"] == ev["payload"]["commodity"]
    assert row["cancellation_received_at"] == datetime.fromisoformat(ev["occurred_at"])


def test_mg_100125_gas_deregistration_uses_payload_effective_date(states, policy, full):
    assert "S1" not in {x.id for x in extract_signals(states["MG-100125"], policy)}
    ev = _ev("MG-100125", "gas_meter_deregistration_received")
    eff = datetime.fromisoformat(ev["payload"]["effective_date"])
    s = full.states["MG-100125"]
    s1 = next(x for x in extract_signals(s, policy) if x.id == "S1")
    gas = next(r for r in s.rows["energy_contracts"] if r["commodity"] == "gas")
    assert gas["meter_deregistration_effective"] == eff
    assert gas["status"] == "active" and s.eval_time < eff  # deferred until the effective date
    assert eff.date().isoformat() in s1.detail


def test_mg_100009_agent_feedback_is_recorded(states, policy, pop, full):
    ev = _ev("MG-100009", "agent_nba_feedback")
    s = full.states["MG-100009"]
    rows = [r for r in s.rows["service_nba_feedback"] if r.get("ticket_id") == ev["payload"]["ticket_id"]]
    assert len(rows) == 1
    r = rows[0]
    assert (r["agent_action"], r["dismiss_reason"], r["suggested_offer_id"]) == \
        (ev["payload"]["agent_action"], ev["payload"]["dismiss_reason"], ev["payload"]["suggested_offer_id"])
    assert "annoyed_before" in {f.id for f in triage(s, extract_signals(s, policy), policy, pop).flags}
