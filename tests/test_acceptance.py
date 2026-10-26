"""README §9: strict cases, report cases and all-customer invariants under both modes."""
import pytest

from nba.contracts import CustomerCard, NO_ACTION
from nba.engine.assemble import assemble
from nba.engine.config import load_config
from nba.kg.rules import _channels, active_exclusions, check_tuple, consents, is_profiled
from nba.state import contacts, owns


@pytest.fixture(scope='module', params=['rate', 'uplift'])
def cards(request, states, tables, policy, pop):
    cfg = load_config(tables, p_mode=request.param)
    return request.param, {cid: assemble(s, pop, policy, cfg) for cid, s in states.items()}


@pytest.mark.acceptance
def test_strict_reference_customers(cards):
    mode, all_cards = cards
    for cid in ['MG-100096', 'MG-100186', 'MG-100009', 'MG-100659', 'MG-100004']:
        card = all_cards[cid]
        selected = next(c for c in card.candidates if c.tuple_id == card.chosen.tuple_id)
        assert selected.offer_id == 'P-SV-01', (mode, cid)
        assert card.chosen.service_mode and card.chosen.agent_script
    for cid in ['MG-100035', 'MG-100087']:
        card = all_cards[cid]
        assert card.chosen.tuple_id == NO_ACTION and card.chosen.reason_line
        assert not any(c.action_type != 'service' for c in card.candidates)
    if mode == 'rate':
        assert all_cards['MG-100023'].chosen.tuple_id.startswith('P-AS-01|')
    for cid in ['MG-100004', 'MG-100012', 'MG-100112']:
        card = all_cards[cid]
        assert card.profile.header.tone.value == 'sie' and card.profile.header.tone.method == 'default'
        assert all(not c.personalised and c.origin != 'signal' for c in card.candidates)
        assert card.chosen.content and not card.chosen.content.personalised
    assert any(b.rule_id == 'CONSENT-PROFILING' and b.offer_id == 'P-AS-01' for b in all_cards['MG-100112'].blocked)


@pytest.mark.acceptance
def test_report_cases_keep_signal_evidence(cards):
    _, all_cards = cards
    for cid in ['MG-100051', 'MG-100060', 'MG-100068']:
        card = all_cards[cid]
        assert 'S1' in {s.id for s in card.signals}
        assert 'P-EN-03' in {c.offer_id for c in card.candidates} | {b.offer_id for b in card.blocked}
    assert {c.offer_id for c in all_cards['MG-100112'].candidates} == ({'P-EN-01', 'P-MO-01', 'P-SL-01'} if cards[0] == 'rate' else {'P-EN-01'})


@pytest.mark.acceptance
def test_all_750_invariants(cards, states, policy):
    mode, all_cards = cards
    assert len(all_cards) == 750
    for cid, card in all_cards.items():
        state = states[cid]
        CustomerCard.model_validate_json(card.model_dump_json())
        channels = _channels(state, policy, consents(state, policy))
        profiled, excluded = is_profiled(state, policy), bool(active_exclusions(state, policy))
        assert card.triage.archetype.id and card.triage.urgency_reasons
        assert len(card.checklist) == 6
        assert all(f.src for f in [card.profile.header.age_band, card.profile.header.city,
                                  card.profile.value_risk.clv_eur, card.profile.value_risk.churn_prob_12m])
        for c in card.candidates:
            assert not check_tuple(state, c.offer_id, c.channel, policy), (mode, cid, c.tuple_id)
            assert c.valuation.delta_clv > 0, (mode, cid, c.tuple_id)
            assert not owns(state, c.offer_id)
            if c.action_type != 'service':
                assert channels[c.channel].allowed and not excluded
                assert len(contacts(state, 30)) < policy.contact_cap[0]
            if not profiled:
                assert not c.personalised and c.origin != 'signal' and c.tone == 'sie'
        if card.chosen.tuple_id == NO_ACTION:
            assert card.chosen.reason_line
        else:
            assert any(c.tuple_id == card.chosen.tuple_id for c in card.candidates)
            assert card.chosen.content.language == 'de'
            if not profiled:
                assert not card.chosen.content.personalised and card.chosen.content.tone == 'sie'
        if card.legacy_comparison:
            legacy = card.legacy_comparison
            expected = {b.rule_id for b in check_tuple(state, legacy.offer_id, legacy.channel, policy)}
            assert expected <= set(legacy.blocked_now_by), (mode, cid)


def test_determinism_for_real_competing_signals(states, tables, policy, pop):
    cfg = load_config(tables)
    a = assemble(states['MG-100068'], pop, policy, cfg).model_dump_json()
    b = assemble(states['MG-100068'], pop, policy, cfg).model_dump_json()
    assert a == b
