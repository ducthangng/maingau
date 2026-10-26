import pytest

from nba.contracts import Candidate, PSource, Valuation
from nba.engine.assemble import evaluate_candidates
from nba.engine.config import load_config
from nba.engine.rank import rank
from nba.kg.rules import generate_candidates
from nba.kg.signals import extract_signals


def item(oid, delta, p=0.1, fee=0):
    v = Valuation(clv_now_shown=100, clv_now_model=100, clv_after_accept=120, clv_after_reject=100,
                  p_accept=p, p_source=PSource(mode='rate', level='global'), contact_cost=fee, delta_clv=delta, confidence='low')
    return Candidate(tuple_id=f'{oid}|email|sie', offer_id=oid, offer_name=oid, action_type='sales',
                     channel='email', tone='sie', valuation=v)


def test_economics_and_tie_breaks():
    chosen, ordered = rank([item('Z', 10), item('B', 10, .2, 0), item('A', 10, .2, 0),
                            item('C', 10, .2, 1), item('D', 0), item('E', -1)])
    assert [c.offer_id for c in ordered] == ['A', 'B', 'C', 'Z']
    assert chosen.rank == 1
    assert rank([item('Z', 0)]) == (None, [])


def test_need_first_arbitration_and_uplift_fallback(states, tables, policy):
    cfg, state = load_config(tables), states['MG-100023']
    candidates, _ = generate_candidates(state, extract_signals(state, policy), policy, 'sie')
    winner, ordered, _ = evaluate_candidates(candidates, state, policy, cfg)
    assert winner.offer_id == 'P-AS-01' and all(c.origin == 'signal' for c in ordered)
    winner, ordered, blocked = evaluate_candidates(candidates, state, policy, cfg.with_mode('uplift'))
    assert winner.origin == 'generic'
    assert any(b.offer_id == 'P-AS-01' and b.rule_id == 'ECON-NONPOSITIVE' for b in blocked)


def test_rank_refuses_unvalued_candidates():
    c = item('A', 2).model_copy(update={'valuation': None})
    with pytest.raises(ValueError, match='valuation'):
        rank([c])
