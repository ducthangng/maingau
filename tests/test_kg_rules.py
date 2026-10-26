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
