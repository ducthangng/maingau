"""Shared contact counter, contact cap sources and Rule Center IDs (docs/rule-center.md §2, §4)."""

import statistics
from dataclasses import replace
from datetime import datetime, timedelta

from nba.kg.contacts import EMAIL_CHANNELS, ContactEvent, contact_events, free_from, window
from nba.kg.policy import validate
from nba.kg.rules import check_tuple, contact_cap_status, generate_candidates, rule_center_ids
from nba.kg.signals import extract_signals

EMAIL_SOURCES = ("nba_history", "newsletter")


def _with_cap(policy, **cap):
    return replace(policy, config={**policy.config, "contact_cap": {**policy.config["contact_cap"], **cap}})


def test_email_counts_reproduce_the_spec_numbers(states):
    t = next(iter(states.values())).eval_time
    counts = [len(window(contact_events(s, EMAIL_SOURCES), 90, t, EMAIL_CHANNELS)) for s in states.values()]
    emailed = [n for n in counts if n]
    assert len(emailed) == 673 and statistics.median(emailed) == 4  # B-01 basis in the mentor spec
    assert sum(n >= 5 for n in emailed) == 328 and sum(n >= 3 for n in emailed) == 492


def test_window_is_exact_and_newsletters_use_the_campaign_time(states):
    s = states["MG-100267"]
    rows = [r for r in s.rows["newsletter_performance"] if r["campaign_id"] == "NL-2609"]
    assert rows and rows[0]["campaign_sent_at"] == datetime(2026, 7, 2, 9, 0)
    events = contact_events(s, EMAIL_SOURCES)
    inside = window(events, 90, s.eval_time, EMAIL_CHANNELS)
    assert len(inside) == 9 and all(e.ref != "NL-2609" for e in inside)  # 02.07 09:00 is just outside (t − 90 d)


def test_events_are_deduplicated_and_text_booleans_are_read(states):
    s = states["MG-100026"]
    events = contact_events(s)
    assert len({(e.channel, e.ts) for e in events}) == len(events)
    mentioned = [r for st in states.values() for r in st.rows["service_nba_feedback"]]
    assert {type(r["offer_mentioned_to_customer"]) for r in mentioned} == {str}  # 'True' / 'False' text
    n = sum(1 for st in states.values() for e in contact_events(st, ("service_feedback",)))
    assert n == sum(1 for r in mentioned if r["offer_mentioned_to_customer"] == "True") == 34
    extra = ContactEvent(events[-1].ts, events[-1].channel, "decision_log", "dup")
    assert len(contact_events(s, extra=[extra])) == len(events)


def test_free_from_is_when_the_oldest_contacts_leave_the_window():
    t = datetime(2026, 9, 30, 23, 59, 59)
    events = [ContactEvent(t - timedelta(days=d), "email", "nba_history", str(d)) for d in (80, 50, 10)]
    assert free_from(events, 90, 5, t) is None
    assert free_from(events, 90, 3, t) == events[0].ts + timedelta(days=90)
    assert free_from(events, 90, 2, t) == events[1].ts + timedelta(days=90)


def test_cap_sources_are_configurable(states, policy):
    s = states["MG-100171"]
    assert contact_cap_status(s, policy).hit  # service agent mentioned an offer + one NBA contact
    assert not contact_cap_status(s, _with_cap(policy, sources=["nba_history"])).hit
    with_news = _with_cap(policy, sources=["nba_history", "service_feedback", "newsletter"])
    capped = sum(contact_cap_status(st, with_news).hit for st in states.values())
    assert capped > sum(contact_cap_status(st, policy).hit for st in states.values())
    ids = set()
    assert any("unknown source" in p for p in validate(_with_cap(policy, sources=["sms_log"]), ids))
    assert any("at least 1" in p for p in validate(_with_cap(policy, max_contacts=0), ids))


def test_capped_tuples_are_kept_for_deferral_when_asked(states, policy):
    s = states["MG-100026"]
    signals = extract_signals(s, policy)
    gated, blocked = generate_candidates(s, signals, policy)
    kept, _ = generate_candidates(s, signals, policy, apply_cap=False)
    cap = next(b for b in blocked if b.rule_id == "CONTACT-CAP")
    assert cap.rule_center_id == "B-02" and cap.until and not any(c.action_type != "service" for c in gated)
    assert kept and all(not k.passed for c in kept for k in c.checks if k.rule_id == "CONTACT-CAP")


def test_rule_center_ids_on_blocked_rows(states, policy):
    assert sorted(policy.compliance) == [f"C-0{i}" for i in range(1, 10)]
    ids = rule_center_ids(policy)
    assert ids["EXCL-DUNNING"] == "C-06" and ids["HOLDING-PRECONDITION"] == "B-07" and ids["CONTACT-CAP"] == "B-02"
    cases = {
        ("MG-100001", "P-MO-01", "app_push"): ("CHANNEL-AVAILABLE", "C-01"),
        ("MG-100067", "P-EN-03", "newsletter_email"): ("CONSENT-CHANNEL", "C-03"),
        ("MG-100096", "P-EN-03", "email"): ("EXCL-DUNNING", "C-06"),
        ("MG-100186", "P-MO-01", "email"): ("EXCL-OPEN-TICKET", "C-07"),
        ("MG-100112", "P-AS-01", "outbound_call"): ("CONSENT-PROFILING", "C-05"),
    }
    for (cid, offer, channel), expected in cases.items():
        assert expected in {(b.rule_id, b.rule_center_id) for b in check_tuple(states[cid], offer, channel, policy)}, cid
    for cid in ("MG-100068", "MG-100023", "MG-100096"):
        _, blocked = generate_candidates(states[cid], extract_signals(states[cid], policy), policy)
        assert all(b.rule_center_id for b in blocked if b.rule_id != "DATA-MISSING"), cid


def test_compliance_block_is_validated(policy):
    broken = replace(policy, compliance={k: v for k, v in policy.compliance.items() if k != "C-09"})
    assert any("C-01 … C-09" in p for p in validate(broken, set()))
    typo = replace(policy, compliance={**policy.compliance, "C-06": {"label": "x", "kg_rules": ["EXCL-DUNING"]}})
    assert any("unknown KG rule" in p for p in validate(typo, set()))
