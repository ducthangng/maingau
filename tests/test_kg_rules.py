"""Gate invariants over all customers and the spec's test customers (README §6.1–§6.4, §6.12, §9)."""

from nba.kg.rules import _channels, active_exclusions, consents, is_profiled
from nba.state import contacts, owns


def test_invariants_all_customers(states, policy, kg_all):
    cap_max, window = policy.contact_cap
    for cid, (sig, cands, blocked, tri) in kg_all.items():
        s = states[cid]
        chans = _channels(s, policy, consents(s, policy))
        excluded = bool(active_exclusions(s, policy))
        profiled = is_profiled(s, policy)
        capped = len(contacts(s, window)) >= cap_max
        for c in cands:
            if c.origin == "service":
                assert c.offer_id == "P-SV-01" and c.channel == "service_agent" and not c.personalised
                continue
            assert chans[c.channel].allowed, (cid, c.tuple_id)
            assert not excluded, (cid, c.tuple_id)
            assert not capped, (cid, c.tuple_id)
            assert not owns(s, c.offer_id), (cid, c.tuple_id)
            if c.origin == "signal":
                assert profiled and c.personalised and c.signals
            else:
                assert not c.personalised and c.offer_id in {o.id for o in policy.generic_offers}
            if not profiled:
                assert c.tone == "sie"
            assert c.path and c.path[-1].type == "Consent"  # service tuples are skipped above
        assert len({c.tuple_id for c in cands}) == len(cands), cid


def _tuples(kg_all, cid):
    return kg_all[cid][1]


def _blocked(kg_all, cid):
    return kg_all[cid][2]


def test_mg_100112_consent_story(kg_all):
    cands = _tuples(kg_all, "MG-100112")
    assert all(c.origin == "generic" and c.channel == "outbound_call" for c in cands)
    assert any(b.offer_id == "P-AS-01" and b.rule_id == "CONSENT-PROFILING" for b in _blocked(kg_all, "MG-100112"))


def test_mg_100023_has_autostrom_signal_tuple(kg_all):
    assert any(c.offer_id == "P-AS-01" and c.origin == "signal" for c in _tuples(kg_all, "MG-100023"))


def test_service_only_customers(kg_all):
    for cid in ("MG-100096", "MG-100186", "MG-100035", "MG-100087", "MG-100004"):
        assert {c.offer_id for c in _tuples(kg_all, cid)} == {"P-SV-01"}, cid


def test_failed_charging_customers_get_service_tuple(kg_all):
    for cid in ("MG-100009", "MG-100659"):
        assert any(c.origin == "service" for c in _tuples(kg_all, cid)), cid


def test_no_profiling_means_generic_only(kg_all):
    assert {c.origin for c in _tuples(kg_all, "MG-100012")} == {"generic"}


def test_mg_100068_competing_offers(kg_all):
    offers = {c.offer_id for c in _tuples(kg_all, "MG-100068") if c.origin == "signal"}
    assert offers == {"P-EN-03", "P-SL-01", "P-AS-01", "P-EN-02"}
    assert any(b.offer_id == "P-SL-03" and b.rule_id == "HOLDING-PRECONDITION" for b in _blocked(kg_all, "MG-100068"))


# ---- review findings (26 Oct)

def test_channel_blocks_are_reported_with_channel(kg_all):
    rows = [b for b in _blocked(kg_all, "MG-100068") if b.offer_id == "*" and b.channel]
    assert {b.channel for b in rows} >= {"outbound_call", "sms"}
    assert all(b.rule_id in ("CONSENT-CHANNEL", "CHANNEL-AVAILABLE") for b in rows)
    assert any(b.channel == "app_push" and b.rule_id == "CHANNEL-AVAILABLE" for b in rows)  # portal yes, app no


def test_s10_is_reported_as_ignored_without_profiling(kg_all, states, policy):
    for cid, (sig, _, blocked, _) in kg_all.items():
        if "S10" in {s.id for s in sig} and not is_profiled(states[cid], policy):
            assert any(b.rule_id == "CONSENT-PROFILING" and b.reason.startswith("S10") for b in blocked), cid


def test_owned_generic_offers_are_reported(kg_all):
    assert any(b.offer_id == "P-SH-02" or (b.offer_id == "P-EN-01" and b.rule_id == "HOLDING-PRECONDITION")
               for b in _blocked(kg_all, "MG-100068"))


def test_s11_detail_is_factual(kg_all):
    s11 = next(s for s in kg_all["MG-100087"][0] if s.id == "S11")
    assert "cancellation_pending" in s11.detail and "elsewhere" not in s11.detail


def test_autostrom_cancelled_scope_switch(states, tables):
    from dataclasses import replace

    from nba.kg.policy import load_policy
    from nba.kg.rules import active_exclusions, blocks_offer, generate_candidates
    from nba.kg.signals import extract_signals

    base = load_policy(catalog=tables["product_catalog"])
    scoped = replace(base, config={**base.config, "exclusions": {"autostrom_cancelled_scope": "e_mobility"}})
    cancelled = [c for c, s in states.items() if any(r["status"] == "cancelled" for r in s.rows["autostrom_contracts"])]
    assert cancelled
    for cid in cancelled:
        s = states[cid]
        assert "EXCL-AUTOSTROM-CANCELLED" in dict(active_exclusions(s, scoped))  # never disappears
        cands, _ = generate_candidates(s, extract_signals(s, scoped), scoped, "sie")
        assert not any(c.offer_id == "P-AS-01" for c in cands), cid
    assert blocks_offer("EXCL-AUTOSTROM-CANCELLED", base.offers["P-MO-01"], base)
    assert not blocks_offer("EXCL-AUTOSTROM-CANCELLED", base.offers["P-MO-01"], scoped)
    assert blocks_offer("EXCL-AUTOSTROM-CANCELLED", base.offers["P-AS-01"], scoped)


def test_check_tuple(states, policy, kg_all):
    from nba.kg.rules import check_tuple

    assert {b.rule_id for b in check_tuple(states["MG-100096"], "P-EN-03", "email", policy)} >= {"EXCL-DUNNING"}
    rules_112 = {b.rule_id for b in check_tuple(states["MG-100112"], "P-AS-01", "outbound_call", policy)}
    assert "CONSENT-PROFILING" in rules_112
    assert {b.rule_id for b in check_tuple(states["MG-100068"], "P-EN-03", "outbound_call", policy)} == {"CONSENT-CHANNEL"}
    assert check_tuple(states["MG-100009"], "P-SV-01", "service_agent", policy) == []
    # every generated candidate passes its own check
    for cid in ("MG-100068", "MG-100023", "MG-100012", "MG-100325"):
        for c in kg_all[cid][1]:
            assert check_tuple(states[cid], c.offer_id, c.channel, policy) == [], (cid, c.tuple_id)
