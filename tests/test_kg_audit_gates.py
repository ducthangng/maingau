"""KG audit: candidates, blocked rows and the gate order (README §6.1–§6.4, §6.12, §7.1, D1, K11)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from kg_audit_oracle import CHANNELS, EXCLUSIONS, GENERIC_OFFERS, MARKETING_SIGNALS, SERVICE_SIGNALS, oracle

from nba.kg.rules import channel_view, check_tuple, generate_candidates
from nba.kg.signals import extract_signals

PER_OFFER_RULES = {"HOLDING-PRECONDITION", "CONSENT-PROFILING", *EXCLUSIONS}


def _gen(state, policy):
    return generate_candidates(state, extract_signals(state, policy), policy, "sie")


def test_allowed_tuples_match_oracle_for_every_customer(kg_all):
    """Full §6.12 tuple set (offer, channel, origin) recomputed from the README for all 750 customers."""
    o = oracle()
    diffs = {}
    for cid, (_, cands, _, _) in kg_all.items():
        got = {(c.offer_id, c.channel, c.origin) for c in cands}
        want = o.expected_tuples(cid)
        if got != want:
            diffs[cid] = {"code_only": sorted(got - want), "oracle_only": sorted(want - got)}
    assert not diffs, f"{len(diffs)} customers differ, e.g. {dict(list(diffs.items())[:5])}"


def test_gate_order_on_per_offer_blocks(kg_all, policy):
    """Profiled customers: exclusions → holding preconditions; the blocked row carries the first failing gate."""
    o = oracle()
    diffs = []
    for cid, (sig, cands, blocked, _) in kg_all.items():
        if not o.profiled(cid):
            continue
        excl = o.exclusions(cid)
        sigs = {s.id for s in sig} & (MARKETING_SIGNALS - {"S10"})
        offers = {x for s in sigs for x in o.signal_offers(cid, s)}
        for offer in sorted(offers):
            rows = list(dict.fromkeys(b.rule_id for b in blocked if b.offer_id == offer and b.rule_id in PER_OFFER_RULES))
            if excl:
                want = [excl[0]]
            elif not o.requirements_met(cid, offer) or o.owns(cid, offer):
                want = ["HOLDING-PRECONDITION"]
            else:
                want = []
            if rows != want:
                diffs.append((cid, offer, rows, want))
    assert not diffs, diffs[:20]


def test_no_duplicate_blocked_rows_per_offer_and_rule(kg_all):
    import collections

    dups = []
    for cid, (_, _, blocked, _) in kg_all.items():
        n = collections.Counter((b.offer_id, b.channel, b.rule_id) for b in blocked if b.rule_id != "CONSENT-PROFILING")
        dups += [(cid, *k, v) for k, v in n.items() if v > 1]
    assert not dups, dups[:20]


def test_customer_wide_rows_for_exclusions_cap_and_channels(kg_all):
    o = oracle()
    for cid, (_, _, blocked, _) in kg_all.items():
        star = [b for b in blocked if b.offer_id == "*"]
        assert sorted(b.rule_id for b in star if b.rule_id.startswith("EXCL-")) == sorted(o.exclusions(cid)), cid
        assert any(b.rule_id == "CONTACT-CAP" for b in star) == o.capped(cid), cid
        chans = o.channels(cid)
        got = {b.channel: b.rule_id for b in star if b.channel}
        assert got == {ch: rule for ch, (ok, rule) in chans.items() if not ok}, cid


def test_channel_view_matches_oracle(states, policy):
    o = oracle()
    diffs = []
    for cid, s in states.items():
        view = {c.channel: c.allowed for c in channel_view(s, policy)}
        want = {ch: ok for ch, (ok, _) in o.channels(cid).items()} | {"service_agent": True}
        if view != want:
            diffs.append((cid, {k: (view.get(k), want.get(k)) for k in want if view.get(k) != want.get(k)}))
    assert not diffs, diffs[:20]


# ---- channel availability, unit level (§6.1)


def _with_consent(state, ctype, **changes):
    rows = [dict(r, **changes) if r["consent_type"] == ctype else r for r in state.rows["consent_status"]]
    return replace(state, rows=dict(state.rows, consent_status=rows))


def _allowed(state, policy) -> dict[str, bool]:
    return {c.channel: c.allowed for c in channel_view(state, policy)}


def test_newsletter_needs_granted_doi_and_no_unsubscribe(states, policy):
    s = states["MG-100068"]
    assert _allowed(s, policy)["newsletter_email"]
    assert not _allowed(_with_consent(s, "newsletter_email", double_opt_in_confirmed_at=None), policy)["newsletter_email"]
    unsub = dict(s.rows["newsletter_performance"][0] if s.rows["newsletter_performance"] else
                 {"campaign_id": "NL-TEST", "customer_id": s.customer_id}, unsubscribed=True)
    s2 = replace(s, rows=dict(s.rows, newsletter_performance=s.rows["newsletter_performance"] + [unsub]))
    assert not _allowed(s2, policy)["newsletter_email"]
    assert _allowed(s2, policy)["email"] == _allowed(s, policy)["email"]  # K9: newsletter only


@pytest.mark.parametrize("status", ["not_given", "withdrawn", None, "unknown"])
def test_non_granted_consent_is_not_allowed(states, policy, status):
    s = states["MG-100068"]
    assert _allowed(s, policy)["email"]
    assert not _allowed(_with_consent(s, "marketing_email", status=status), policy)["email"]


def test_missing_consent_row_counts_as_not_allowed(states, policy):
    s = states["MG-100068"]
    rows = [r for r in s.rows["consent_status"] if r["consent_type"] != "marketing_email"]
    assert not _allowed(replace(s, rows=dict(s.rows, consent_status=rows)), policy)["email"]


@pytest.mark.parametrize("channel,field", [("portal_popup", "portal_account"), ("app_push", "app_installed")])
def test_portal_and_app_need_the_master_flag(states, policy, channel, field):
    o = oracle()
    cid = next(c for c in o.customers if o.consent(c)["portal_app_personalisation"]["effective"] == "granted"
               and o.master[c][field] in ("True", "1"))
    s = states[cid]
    assert _allowed(s, policy)[channel]
    master = [dict(r, **{field: False}) for r in s.rows["customer_master"]]
    off = replace(s, rows=dict(s.rows, customer_master=master))
    assert not _allowed(off, policy)[channel]
    blocked = {b.channel: b.rule_id for b in _gen(off, policy)[1] if b.offer_id == "*" and b.channel}
    assert blocked[channel] == "CHANNEL-AVAILABLE"


# ---- profiling (D1)


def test_without_profiling_marketing_signals_are_blocked_and_tuples_are_generic(kg_all):
    o = oracle()
    checked = 0
    for cid, (sig, cands, blocked, _) in kg_all.items():
        if o.profiled(cid):
            continue
        checked += 1
        prof_rows = [b for b in blocked if b.rule_id == "CONSENT-PROFILING"]
        for s in sig:
            if s.id in MARKETING_SIGNALS:
                assert any(b.reason.startswith(f"{s.id} ") for b in prof_rows), (cid, s.id)
        for c in cands:
            if c.origin == "service":
                continue
            assert c.origin == "generic" and not c.personalised and c.tone == "sie", (cid, c.tuple_id)
        service_expected = bool({s.id for s in sig} & SERVICE_SIGNALS)
        assert any(c.origin == "service" for c in cands) == service_expected, cid
    assert checked == 289


def test_generic_tuples_use_every_allowed_channel_and_drop_only_owned(kg_all):
    o = oracle()
    for cid, (_, cands, blocked, _) in kg_all.items():
        if o.exclusions(cid) or o.capped(cid):
            continue
        by_offer: dict[str, set[str]] = {}
        for c in cands:
            if c.origin == "generic":
                by_offer.setdefault(c.offer_id, set()).add(c.channel)
        for offer, chans in by_offer.items():
            assert chans == o.allowed_channels(cid), (cid, offer)
            assert not o.owns(cid, offer)


def test_generic_includes_phone_and_sms_k11(kg_all):
    channels = {c.channel for _, cands, _, _ in kg_all.values() for c in cands if c.origin == "generic"}
    assert {"outbound_call", "sms"} <= channels


# ---- contact cap (§6.7)


def _with_contacts(state, n):
    extra = [{"action_id": f"CAP-{i}", "customer_id": state.customer_id, "decided_at": state.eval_time - timedelta(days=i + 1),
              "delivery_status": "delivered", "control_group": False, "offer_id": "P-SH-01", "channel": "email",
              "response": "ignored"} for i in range(n)]
    return replace(state, rows=dict(state.rows, nba_action_history=extra))


def test_contact_cap_blocks_marketing_at_two_and_spares_service(states, policy):
    s = states["MG-100068"]
    one = _gen(_with_contacts(s, 1), policy)
    assert any(c.origin != "service" for c in one[0])
    assert not any(b.rule_id == "CONTACT-CAP" for b in one[1])
    two_c, two_b = _gen(_with_contacts(s, 2), policy)
    assert [c for c in two_c if c.origin != "service"] == []
    cap = [b for b in two_b if b.rule_id == "CONTACT-CAP"]
    assert len(cap) == 1 and cap[0].offer_id == "*"
    svc = _gen(_with_contacts(states["MG-100009"], 5), policy)[0]
    assert any(c.offer_id == "P-SV-01" for c in svc)


def test_capped_customers_in_data_have_no_marketing_tuple(kg_all):
    o = oracle()
    capped = [c for c in o.customers if o.capped(c)]
    assert capped
    for cid in capped:
        assert all(c.origin == "service" for c in kg_all[cid][1]), cid


# ---- check_tuple and tuple ids


def test_check_tuple_is_empty_for_every_allowed_tuple(states, policy, kg_all):
    bad = [(cid, c.tuple_id, [b.rule_id for b in check_tuple(states[cid], c.offer_id, c.channel, policy)])
           for cid, (_, cands, _, _) in kg_all.items() for c in cands
           if check_tuple(states[cid], c.offer_id, c.channel, policy)]
    assert not bad, bad[:20]


def test_check_tuple_reports_the_same_blockers(states, policy, kg_all):
    """For every per-offer blocked row (offer not generated on any channel), check_tuple names the same rule."""
    diffs = []
    for cid, (_, cands, blocked, _) in kg_all.items():
        generated = {c.offer_id for c in cands}
        for b in blocked:
            if b.offer_id == "*" or b.rule_id == "DATA-MISSING" or b.offer_id in generated:
                continue
            if b.rule_id == "CONSENT-PROFILING" and b.offer_id in GENERIC_OFFERS:
                continue  # "signal ignored" row; the generic version of the offer stays allowed (D1)
            for ch in CHANNELS:
                rules = {x.rule_id for x in check_tuple(states[cid], b.offer_id, ch, policy)}
                if b.rule_id not in rules:
                    diffs.append((cid, b.offer_id, ch, b.rule_id, sorted(rules)))
        for b in blocked:
            if b.offer_id == "*" and b.channel:
                for oid in generated - {"P-SV-01"}:
                    rules = {x.rule_id for x in check_tuple(states[cid], oid, b.channel, policy)}
                    if b.rule_id not in rules:
                        diffs.append((cid, oid, b.channel, b.rule_id, sorted(rules)))
    assert not diffs, diffs[:20]


def test_tuple_ids_follow_offer_channel_tone(kg_all):
    for cid, (_, cands, _, _) in kg_all.items():
        for c in cands:
            assert c.tuple_id == f"{c.offer_id}|{c.channel}|{c.tone}", (cid, c.tuple_id)
            assert c.tone in ("du", "sie")
