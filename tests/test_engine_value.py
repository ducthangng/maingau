from dataclasses import replace

import pytest

from nba.contracts import Candidate, PSource
from nba.engine.clv import clv
from nba.engine.config import load_config, MissingDataError
from nba.engine.propensity import Propensity
from nba.engine.value import value


def candidate(oid, action_type='sales', channel='portal_popup'):
    return Candidate(tuple_id=f'{oid}|{channel}|sie', offer_id=oid, offer_name=oid,
                     action_type=action_type, channel=channel, tone='sie')


def sure():
    return Propensity(1, 'low', PSource(mode='assumption', level='assumption'), 1, 0, 'assumption')


def test_one_off_margin_is_added_once(states, tables):
    cfg = load_config(tables)
    result = value(candidate('P-SH-03', 'one_off'), states['MG-100112'], sure(), cfg)
    assert result.clv_after_accept - result.clv_now_model == pytest.approx(23)
    assert result.delta_clv == pytest.approx(23)


def test_retention_removes_driver_once(states, tables):
    cfg = load_config(tables)
    state = states['MG-100068']
    row = state.one('customer_value')
    result = value(candidate('P-EN-02', 'retention'), state, sure(), cfg)
    expected = clv(row['annual_margin_eur'], row['cost_to_serve_12m_eur'], row['churn_prob_12m'] - 0.1)
    assert result.clv_after_accept == pytest.approx(expected)
    assert result.clv_after_reject == result.clv_now_model


def test_service_value_and_cancellation_lock(states, tables):
    cfg = load_config(tables)
    p = replace(sure(), p_accept=0.5)
    fixed = value(candidate('P-SV-01', 'service', 'service_agent'), states['MG-100009'], p, cfg)
    row = states['MG-100009'].one('customer_value')
    assert fixed.clv_after_accept == pytest.approx(clv(row['annual_margin_eur'], row['cost_to_serve_12m_eur'], 0.2) - 15)
    cancelled = value(candidate('P-SV-01', 'service', 'service_agent'), states['MG-100035'], p, cfg)
    assert cancelled.delta_clv == pytest.approx(-7.5)


def test_reject_penalty_and_no_rounding_gain(states, tables):
    cfg = load_config(tables)
    blocked = value(candidate('P-EN-03'), states['MG-100096'], replace(sure(), p_accept=0), cfg)
    assert blocked.clv_after_reject < blocked.clv_now_model
    state = states['MG-100112']
    unchanged = value(candidate('P-EN-01'), state, replace(sure(), p_accept=0), cfg)
    assert unchanged.delta_clv == 0
    rows = {**state.rows, 'customer_value': [{**state.one('customer_value'), 'annual_margin_eur': None}]}
    with pytest.raises(MissingDataError, match='annual_margin_eur'):
        value(candidate('P-EN-01'), replace(state, rows=rows), sure(), cfg)


def test_call_cost_is_read_from_the_workbook(states, tables):
    cfg = load_config(tables)
    cfg.assumptions = {**cfg.assumptions, 'contact_cost_call_eur': 11}
    result = value(candidate('P-EN-01', channel='outbound_call'), states['MG-100112'], sure(), cfg)
    assert result.contact_cost == 11
