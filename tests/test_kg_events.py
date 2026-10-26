"""Event replay, deep dive B (README §7.1 step 5)."""

from datetime import datetime

import pytest

from nba.data import load_events
from nba.kg.events import replay
from nba.kg.rules import active_exclusions, consents, is_profiled
from nba.kg.segments import triage
from nba.kg.signals import extract_signals


@pytest.fixture(scope="module")
def events():
    return load_events()


@pytest.fixture(scope="module")
def full(states, policy, pop, events):
    return replay(states, events, policy, pop)


def test_full_stream_counts(full):
    assert full.counts() == {"applied": 126, "informational": 508, "orphan": 1}
    assert len(full.affected) == 118
    assert all(s.eval_time == datetime(2026, 10, 3, 19, 27, 39) for s in full.states.values())


def test_snapshot_states_are_not_mutated(states, full):
    assert not any(r["status"] == "cancellation_pending" for r in states["MG-100465"].rows["energy_contracts"])
    assert any(r["status"] == "cancellation_pending" for r in full.states["MG-100465"].rows["energy_contracts"])


def test_online_semantics_mg_100003(states, policy, pop, events):
    mid = replay(states, events, policy, pop, until=datetime(2026, 10, 1, 10, 14, 7))
    c = consents(mid.states["MG-100003"], policy)
    assert c["profiling_analytics"].effective_status == "withdrawn"
    assert c["newsletter_email"].effective_status == "granted"  # its event arrives at 10:14:11
    end = replay(states, events, policy, pop, until=datetime(2026, 10, 1, 10, 14, 11))
    assert consents(end.states["MG-100003"], policy)["newsletter_email"].effective_status == "withdrawn"


def test_late_cancellation_only_known_after_ingest(states, policy, pop, events):
    before = replay(states, events, policy, pop, until=datetime(2026, 10, 2, 2, 11, 5))
    after = replay(states, events, policy, pop, until=datetime(2026, 10, 2, 2, 11, 6))
    assert "EXCL-CANCELLATION" not in dict(active_exclusions(before.states["MG-100465"], policy))
    assert "EXCL-CANCELLATION" in dict(active_exclusions(after.states["MG-100465"], policy))
    tr = next(t for t in after.transitions if t.outcome.customer_id == "MG-100465")
    assert tr.outcome.delay_hours == pytest.approx(16.89, abs=0.01) and tr.tier_after == "P1"


def test_gas_deregistration_respects_effective_date(states, policy, pop, events, full):
    s = full.states["MG-100125"]
    gas = next(r for r in s.rows["energy_contracts"] if r["commodity"] == "gas")
    assert gas["status"] == "active"  # effective 2026-10-31 is after the stream
    s1 = next(x for x in extract_signals(s, policy) if x.id == "S1")
    assert "effective 2026-10-31" in s1.detail
    later = replay(states, events, policy, pop, until=datetime(2026, 11, 1))
    gas_later = next(r for r in later.states["MG-100125"].rows["energy_contracts"] if r["commodity"] == "gas")
    assert gas_later["status"] == "terminated_meter_deregistration"


def test_orphan_ticket_and_late_dunning_mg_100004(full):
    s = full.states["MG-100004"]
    orphan = next(r for r in s.rows["service_interactions"] if r["ticket_id"] == "TK-open-complaint")
    assert orphan["orphan"] and orphan["status"] == "open"
    assert max(r["dunning_level"] for r in s.rows["energy_contracts"]) == 3


def test_mg_100009_story(full, policy, pop):
    s = full.states["MG-100009"]
    assert "EXCL-OPEN-TICKET" in dict(active_exclusions(s, policy))
    flags = {f.id for f in triage(s, extract_signals(s, policy), policy, pop).flags}
    assert "annoyed_before" in flags
    assert "4 failed charging sessions" in next(x.detail for x in extract_signals(s, policy) if x.id == "S2")


def test_stale_event_is_ignored(states, policy, pop):
    stale = {"event_id": "TEST-STALE", "event_type": "consent_changed", "customer_id": "MG-100068",
             "occurred_at": datetime(2020, 1, 1), "ingested_at": datetime(2026, 10, 1, 8, 0),
             "payload": {"consent_type": "marketing_email", "new_status": "withdrawn", "source": "test"}}
    res = replay(states, [stale], policy, pop)
    assert res.outcomes[0].status == "stale" and not res.affected
    assert consents(res.states["MG-100068"], policy)["marketing_email"].effective_status == "granted"


def test_duplicate_event_is_applied_once(states, policy, pop):
    ev = {"event_id": "TEST-DUP", "event_type": "charge_session_failed", "customer_id": "MG-100009",
          "occurred_at": datetime(2026, 10, 1, 12, 0), "ingested_at": datetime(2026, 10, 1, 12, 1),
          "payload": {"charge_type": "AC"}}
    res = replay(states, [ev, dict(ev)], policy, pop)
    assert [o.status for o in res.outcomes] == ["applied", "already_applied"]
    assert sum(1 for r in res.states["MG-100009"].rows["charge_sessions"] if r["session_id"] == "EV-TEST-DUP") == 1


def test_pending_cards_are_revoked_by_hard_rules(states, policy, pop, events):
    pending = {
        "MG-100003": ("P-SL-01|portal_popup|sie", True),  # personalised card, profiling withdrawn at 10:14:05
        "MG-100125": "P-AS-01|newsletter_email|sie",  # open ticket at 11:31:20
    }
    res = replay(states, events, policy, pop, pending=pending)
    by = {t.outcome.customer_id: t for t in res.transitions if t.pending_status == "revoked"}
    assert by["MG-100003"].revoked_by == ("CONSENT-PROFILING",)
    assert by["MG-100003"].outcome.ingested_at == datetime(2026, 10, 1, 10, 14, 5)
    assert "EXCL-OPEN-TICKET" in by["MG-100125"].revoked_by
    assert not is_profiled(res.states["MG-100003"], policy)
