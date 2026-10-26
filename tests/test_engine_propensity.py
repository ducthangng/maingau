import pytest

from nba.engine.config import load_config
from nba.engine.propensity import HistoryIndex, p_accept


def observations(n, conversions=0, *, offer='P-AS-01', channel='email', tone='sie', control=False, status='delivered'):
    return [dict(offer_id=offer, channel=channel, tonality=tone, control_group=control,
                 delivery_status=status, converted_within_14d=i < conversions) for i in range(n)]


def test_real_history_and_generic_global_prior(tables):
    cfg = load_config(tables)
    index = HistoryIndex(cfg.history)
    assert index.treated[()] == [2022, 69]
    assert index.control[()] == [248, 5]
    assert index.treated[('P-AS-01',)] == [203, 0]
    for oid in ['P-AS-01', 'P-EN-03', 'P-MO-01']:
        p = p_accept(oid, 'email', 'du', index, cfg, generic=True)
        assert p.p_accept == pytest.approx(69 / 2022)
        assert p.source.level == 'global' and p.confidence == 'low'
        u = p_accept(oid, 'sms', 'sie', index, cfg.with_mode('uplift'), generic=True)
        assert u.p_accept == pytest.approx(69 / 2022 - 5 / 248)


def test_rate_shrinkage_and_raw_uplift_are_distinct(tables):
    cfg = load_config(tables)
    history = observations(40, 4) + observations(30, 1, control=True)
    rate = p_accept('P-AS-01', 'email', 'sie', history, cfg)
    assert rate.p_accept == pytest.approx((4 + 0.034 * 30) / 70)
    assert rate.source.level == 'offer_channel_tone' and rate.confidence == 'medium'
    uplift = p_accept('P-AS-01', 'email', 'sie', history, cfg.with_mode('uplift'))
    assert uplift.p_accept == pytest.approx(4 / 40 - 1 / 30)
    assert uplift.baseline_level == 'offer'


def test_backoff_and_confidence_boundaries(tables):
    cfg = load_config(tables)
    controls = observations(20, control=True)
    l2 = observations(29) + observations(1, tone='du') + controls
    assert p_accept('P-AS-01', 'email', 'sie', l2, cfg).source.level == 'offer_channel'
    l1 = observations(20) + observations(10, channel='sms') + controls
    assert p_accept('P-AS-01', 'email', 'sie', l1, cfg).source.level == 'offer'
    l0 = observations(29) + observations(50, offer='P-MO-01') + controls
    assert p_accept('P-AS-01', 'email', 'sie', l0, cfg).source.level == 'global'
    assert p_accept('P-AS-01', 'email', 'sie', observations(100) + controls, cfg).confidence == 'high'
    assert p_accept('P-AS-01', 'email', 'sie', observations(99) + controls, cfg).confidence == 'medium'


def test_failed_deliveries_are_excluded_and_service_is_an_assumption(tables):
    cfg = load_config(tables)
    history = observations(40, 4) + observations(100, 100, status='bounced') + observations(40, control=True)
    assert p_accept('P-AS-01', 'email', 'sie', history, cfg).source.n_treated == 40
    service = p_accept('P-SV-01', 'service_agent', 'sie', [], cfg)
    assert service.p_accept == 0.5 and service.source.mode == 'assumption' and service.confidence == 'low'
    assert p_accept('P-AS-01', 'email', 'sie', cfg.history, cfg.with_mode('uplift')).p_accept == 0
