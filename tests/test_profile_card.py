"""Left card: profile builder and timeline on the real snapshot (README §4.1, §5.6)."""

from __future__ import annotations

from datetime import datetime

import pytest

from nba.contracts import Profile
from nba.profile import build_profile, build_timeline, infer_tone, profile_population
from nba.state import CustomerState

TEST_CUSTOMERS = ["MG-100051", "MG-100060", "MG-100096", "MG-100186", "MG-100068", "MG-100023", "MG-100112",
                  "MG-100009", "MG-100659", "MG-100035", "MG-100087", "MG-100004", "MG-100012"]


@pytest.fixture(scope="session")
def ppop(states):
    return profile_population(states)


@pytest.fixture(scope="session")
def profiles(states, ppop):
    return {cid: build_profile(s, ppop) for cid, s in states.items()}


def test_every_customer_builds_a_valid_profile(states, profiles):
    assert len(profiles) == 750
    for cid, p in profiles.items():
        Profile.model_validate(p.model_dump())  # extra="forbid" catches stray keys
        items = build_timeline(states[cid])
        assert len({i.id for i in items}) == len(items)
        assert [i.date for i in items] == sorted((i.date for i in items), reverse=True)


def test_profile_is_deterministic(states, ppop):
    s = states["MG-100068"]
    assert build_profile(s, ppop).model_dump_json() == build_profile(s, ppop).model_dump_json()


def test_representative_mg_100325(profiles):
    p = profiles["MG-100325"]
    assert p.header.city.v == "Hamburg"
    assert p.header.household_size.v == 2
    assert p.header.age_band.v == "40–49"
    assert p.value_risk.clv_eur.v == 1440
    assert p.value_risk.cost_to_serve_12m_eur.v == 55
    assert p.value_risk.clv_eur.src == "customer_value.clv_eur"
    assert p.value_risk.clv_eur.updated_at == "2026-09-30"
    assert {d.label for d in p.value_risk.churn_drivers} >= {"price guarantee ends <90d", "HEMS user"}
    devices = {i["device_type"]["v"] for i in p.products.smart_living.items}
    assert "home_battery" not in devices and "hems_gateway" in devices
    assert p.products.energy.held and p.products.mobile.held and p.products.autostrom.held
    assert p.products.internet.held is None
    status = {c.type: c.effective_status for c in p.consent}
    assert status["marketing_phone"] == "withdrawn" and status["marketing_sms"] == "not_given"


def test_representative_mg_100001(profiles):
    p = profiles["MG-100001"]
    assert p.header.age_band.v == "70–79"
    assert p.header.city.v == "Köln"
    assert p.value_risk.clv_eur.v == 261
    assert not p.products.mobile.held and p.products.mobile.opportunity
    assert p.header.tone.value == "sie" and p.header.tone.method == "text"


@pytest.mark.parametrize("cid", TEST_CUSTOMERS)
def test_test_customers_have_complete_left_cards(cid, profiles, states):
    p = profiles[cid]
    assert len(p.consent) == 6
    assert {e.rule_id for e in p.exclusions} == {"EXCL-DUNNING", "EXCL-CANCELLATION", "EXCL-OPEN-TICKET",
                                                 "EXCL-AUTOSTROM-CANCELLED"}
    assert p.trends.clv_note
    assert len(p.highlights) <= 3
    assert build_timeline(states[cid])


@pytest.mark.parametrize("cid", ["MG-100112", "MG-100012", "MG-100004"])
def test_no_profiling_means_default_sie(cid, profiles):
    tone = profiles[cid].header.tone
    assert (tone.value, tone.method) == ("sie", "default")


def test_open_complaint_and_dunning_exclusions(profiles):
    active = {e.rule_id for e in profiles["MG-100004"].exclusions if e.active}
    assert {"EXCL-OPEN-TICKET", "EXCL-DUNNING"} <= active
    assert any(e.active for e in profiles["MG-100035"].exclusions if e.rule_id == "EXCL-CANCELLATION")


def test_charging_trend_counts_failed_sessions(profiles):
    charging = profiles["MG-100009"].trends.charging
    september = next(m for m in charging["months"] if m["month"] == "2026-09")
    assert september["failed"] == 3
    assert charging["range"] == {"from": "2026-06-01", "to": "2026-09-30"}


def test_future_price_guarantee_is_on_the_timeline(states):
    items = build_timeline(states["MG-100068"])
    assert any(i.future and i.kind == "milestone" and i.date == "2026-10-08" for i in items)


def test_highlights_are_rare(profiles):
    for p in profiles.values():
        for h in p.highlights:
            assert h.rarity and h.basis
            assert h.rarity.startswith("<1%") or int(h.rarity.split("%")[0]) <= 10


# ---------------------------------------------------------------- tone inference on synthetic states (§6.8)


def _state(messages=(), transcripts=(), profiling="granted", clicks=()) -> CustomerState:
    rows = {
        "consent_status": [{"consent_type": "profiling_analytics", "status": profiling, "updated_at": None}],
        "newsletter_performance": [{"campaign_id": c, "clicked_at": datetime(2026, 5, 1)} for c in clicks],
        "service_interactions": [
            {"ticket_id": f"TK-{i}", "created_at": datetime(2026, 8, i + 1), "message_text": m} for i, m in enumerate(messages)
        ],
        "call_transcripts": [
            {"transcript_id": f"CT-{i}", "call_started_at": datetime(2026, 9, i + 1), "transcript": t}
            for i, t in enumerate(transcripts)
        ],
    }
    return CustomerState("MG-TEST", datetime(2026, 9, 30, 23, 59, 59), "provided", rows)


def test_tone_du_from_customer_text():
    tone = infer_tone(_state(["Hi, danke dir für die schnelle Hilfe!", "Hey, kannst du mir helfen?"]), campaign_tonality={})
    assert (tone.value, tone.method) == ("du", "text")
    assert tone.evidence.startswith("Du – 2/2 messages")


def test_tone_ignores_agent_lines_in_transcripts():
    transcript = "Agent: Wie kann ich Ihnen helfen? Sehr geehrte Kundin.\nKunde: Hi, ich hab eine Frage zu meinem Tarif."
    tone = infer_tone(_state(transcripts=[transcript]), campaign_tonality={})
    assert (tone.value, tone.method) == ("du", "text")


def test_tone_ihr_at_sentence_start_is_not_a_sie_cue():
    tone = infer_tone(_state(["Ihr habt mir eine Rechnung geschickt."]), campaign_tonality={})
    assert tone.method == "default"


def test_tone_newsletter_needs_two_clicks_and_a_clear_majority():
    tonality = {"NL-1": "du", "NL-2": "du", "NL-3": "sie"}
    assert infer_tone(_state(clicks=["NL-1"]), campaign_tonality=tonality).method == "default"
    tone = infer_tone(_state(clicks=["NL-1", "NL-2", "NL-3"]), campaign_tonality=tonality)
    assert (tone.value, tone.method) == ("du", "newsletter")


def test_tone_without_profiling_is_default_sie():
    tone = infer_tone(_state(["Hi, danke dir!"], profiling="withdrawn"), campaign_tonality={})
    assert (tone.value, tone.method) == ("sie", "default")
