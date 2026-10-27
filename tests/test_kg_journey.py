"""Customer journey for the Customer 360° view (nba.kg.journey): the events the card timeline leaves out."""
import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from nba.kg.journey import build_journey, export_journey, lookups


@pytest.fixture(scope="module")
def journeys(tables, states, policy):
    lk = lookups(tables, policy)
    return {cid: build_journey(s, **lk) for cid, s in states.items()}


def test_every_event_type_and_window(journeys, states):
    types = set().union(*(j.counts for j in journeys.values()))
    assert types == {"contract", "milestone", "consent", "proposal", "ticket", "order", "newsletter",
                     "agent_suggestion", "charging", "portal"}
    for cid, j in list(journeys.items())[:50]:
        dates = [e.date for e in j.events]
        assert dates == sorted(dates, reverse=True) and sum(j.counts.values()) == len(j.events)
        now = states[cid].eval_time.date().isoformat()
        assert all(e.type == "milestone" for e in j.events if e.date > now)


def test_the_missing_fields_are_there(journeys):
    events = [e for j in journeys.values() for e in j.events]
    proposals = [e for e in events if e.type == "proposal"]
    assert proposals and all(e.facts["tone"] in {"du", "sie"} and "tone " in e.detail for e in proposals)
    assert any(e.facts.get("value_eur") and "€" in e.detail for e in events if e.type == "order")
    assert any(e.facts.get("resolution_code") and "resolution:" in e.detail for e in events if e.type == "ticket")
    letters = [e for e in events if e.type == "newsletter"]
    assert all(not e.title.startswith("Newsletter: NL-") for e in letters)  # subject from newsletter_campaigns
    assert {"bounced", "not opened"} <= {e.reaction for e in letters}
    assert any("clicked" in (e.reaction or "") for e in letters)
    assert any("bought within 7 days" in (e.reaction or "") for e in letters)
    assert sum(e.type == "agent_suggestion" for e in events) == 100
    portal = [e for e in events if e.type == "portal"]
    assert all(e.facts.get("pages") for e in portal) and any("offer banner shown" in e.detail for e in portal)


def test_apple_mail_preload_is_not_an_open(journeys):
    preloads = [e for j in journeys.values() for e in j.events
                if e.type == "newsletter" and e.facts.get("open_client") == "apple_mpp_prefetch" and not e.facts.get("clicked")]
    assert preloads and all(e.reaction.startswith("not opened") for e in preloads)


def test_charging_is_one_event_per_day(journeys, states):
    cid = next(c for c, j in journeys.items() if j.counts.get("charging"))
    charging = [e for e in journeys[cid].events if e.type == "charging"]
    assert len({e.date for e in charging}) == len(charging)
    assert sum(e.facts["sessions"] for e in charging) <= len(states[cid].rows["charge_sessions"])
    failed = [e for j in journeys.values() for e in j.events if e.type == "charging" and "failed" in e.flags]
    assert failed and all(e.facts.get("failed") or e.facts.get("aborted") for e in failed)


def test_no_payment_or_value_scores(journeys):
    text = json.dumps([j.model_dump(mode="json") for j in list(journeys.values())[:200]])
    assert "payment" not in text and "dunning" not in text and "clv" not in text.lower()


def test_static_export_is_lean(journeys):
    j = export_journey(journeys["MG-100023"])
    dumped = j.model_dump(mode="json")
    assert all("facts" not in e and "src" not in e for e in dumped["events"])
    assert all(e.facts for e in journeys["MG-100023"].events if e.type in {"newsletter", "portal"})


def test_api_journey(tmp_path, tables, states, policy, pop):
    from nba.engine.config import load_config
    from nba.engine.runtime import Runtime

    api = TestClient(create_app(runtime=Runtime(tables, dict(states), pop, policy, load_config(tables)), out_dir=tmp_path))
    r = api.get("/api/customers/MG-100023/journey")
    assert r.status_code == 200 and r.json()["customer_id"] == "MG-100023" and r.json()["events"]
    assert api.get("/api/customers/MG-999999/journey").status_code == 404
