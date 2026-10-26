import statistics

import pytest

from nba.engine.clv import clv


def test_reproduces_all_750_supplied_values(tables):
    errors = [abs(clv(r['annual_margin_eur'], r['cost_to_serve_12m_eur'], r['churn_prob_12m']) - r['clv_eur'])
              for r in tables['customer_value'].to_dict('records')]
    assert len(errors) == 750
    assert max(errors) <= 3.05
    assert statistics.median(errors) == pytest.approx(0.271229, abs=0.000001)


def test_closed_form_and_negative_net_margin():
    q = 0.8 / 1.06
    expected = 100 / 1.06 * (1 - q ** 10) / (1 - q)
    assert clv(120, 20, 0.2) == pytest.approx(expected)
    assert clv(20, 120, 0.2) == pytest.approx(-expected)
    assert clv(120, 20, 1) == pytest.approx(100 / 1.06)


@pytest.mark.parametrize('kwargs', [{'churn': -0.1}, {'churn': 1.1}, {'churn': float('nan')}, {'churn': 0.2, 'r': -1}, {'churn': 0.2, 'years': 0}])
def test_invalid_clv_inputs(kwargs):
    with pytest.raises(ValueError):
        clv(100, 10, **kwargs)
