import math

import pytest

from nba.engine.config import load_config
from nba.engine.impact import history_audit, impact_metrics, impact_report, need_first_metrics
from nba.engine.runtime import Runtime
from nba.profile import profile_population


@pytest.fixture(scope='module')
def impact_context(tables, states, policy):
    return Runtime(tables, states, profile_population(states), policy, load_config(tables))


def test_impact_totals_reconcile_and_legacy_cohorts_are_explicit(impact_context):
    rt = impact_context
    cards = rt.cards()
    metrics = impact_metrics(cards, rt.states)
    for key in ['by_offer', 'by_archetype']:
        assert sum(r['customers'] for r in metrics[key].values()) == 750
        assert math.fsum(r['sum_delta_clv'] for r in metrics[key].values()) == pytest.approx(metrics['sum_delta_clv'])
    assert metrics['by_offer']['NO_ACTION']['sum_delta_clv'] == 0
    legacy = metrics['legacy']
    assert legacy['latest_delivered'] < legacy['latest_proposals'] <= 750
    assert legacy['non_economic_blocked'] <= legacy['blocked'] <= legacy['latest_proposals']
    assert max(legacy['by_rule'].values()) <= legacy['blocked']
    assert legacy['comparisons']['all_latest']['customers'] + legacy['missing_valuation'] == legacy['latest_proposals']
    for row in legacy['comparisons'].values():
        assert row['difference'] == pytest.approx(row['our_sum'] - row['legacy_sum'])


def test_rechecked_need_first_statistic_uses_the_implemented_trigger_cohort(impact_context):
    rt = impact_context
    metric = need_first_metrics(rt.states, rt.policy, rt.cfg.history)
    assert (metric['with_conversions'], metric['with_n']) == (9, 82)
    assert (metric['without_conversions'], metric['without_n']) == (12, 930)
    assert metric['with_n'] + metric['without_n'] + metric['excluded_n'] == 2022
    assert metric['standardised_offers'] == 5
    assert set(metric['by_offer']).isdisjoint(metric['excluded_by_offer'])


def test_history_policy_keeps_all_observations_and_exposes_unchecked_cohort(impact_context):
    audit = history_audit(impact_context.cfg.history)
    assert audit['all'] == dict(treated_n=2022, treated_conversions=69, control_n=248, control_conversions=5)
    assert audit['unchecked']['treated_n'] == 297 and audit['unchecked']['treated_conversions'] == 10
    assert audit['unchecked']['control_n'] == 36
    for key in audit['all']:
        assert audit['checked'][key] + audit['unchecked'][key] == audit['all'][key]


def test_pitch_report_discloses_model_scope_and_does_not_reuse_the_old_statistic(impact_context):
    rt = impact_context
    report = impact_report(rt.cards(), rt.states, rt.pop, rt.policy, rt.cfg)
    assert 'model-based, mock data, not causal uplift' in report
    assert '## Mode: rate' in report and '## Mode: uplift' in report
    assert 'By archetype' in report and 'Latest legacy proposals' in report
    assert 'snapshot, not at send time' in report
    assert 'is not reproduced' in report and '38/558' in report
