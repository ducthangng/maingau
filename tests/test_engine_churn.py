from nba.engine.churn import churn_breakdown
from nba.engine.config import load_config


def test_reconstructs_snapshot_probabilities_exactly(states, tables):
    cfg = load_config(tables)
    results = [churn_breakdown(s, cfg) for s in states.values()]
    assert all(b.given == b.reconstructed for b in results)
    # 718 active customers, eight additional cancellation-pending customers, 24 without an active contract.
    assert sum(not b.used_given and not b.cancellation_pending for b in results) == 718
    assert sum(b.cancellation_pending for b in results) == 8
    assert sum(b.used_given for b in results) == 24


def test_service_and_cancellation_components(states, tables):
    cfg = load_config(tables)
    failed = churn_breakdown(states['MG-100009'], cfg)
    assert failed.base == 0.2
    assert round(failed.service_increment, 2) == 0.14
    assert churn_breakdown(states['MG-100035'], cfg).reconstructed == 0.95
