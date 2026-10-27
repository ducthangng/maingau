"""Overview page fields (prompts/ui-overview.md §7): the signal and need behind each chosen action, and their labels."""
import pytest

from nba.engine.config import load_config
from nba.engine.runtime import Runtime, index_rows, summary


@pytest.fixture(scope="module")
def built(tables, states, policy, pop):
    rt = Runtime(tables, dict(states), pop, policy, load_config(tables))
    cards = rt.cards()
    return rt, index_rows(cards, rt.states), summary(cards, rt.cfg, next(iter(rt.states.values())).eval_time, rt.policy)


def test_reason_comes_from_the_chosen_path(built):
    rt, rows, _ = built
    actions = [r for r in rows if r.chosen_offer not in {"NO_ACTION", "P-SV-01"}]
    assert {(r.reason_signal, r.reason_need) for r in actions if r.chosen_offer == "P-EN-03"} == {("S1", "N-HEAT-PUMP")}
    assert all(r.reason_signal is None and r.reason_need is None for r in actions if r.personalised is False)
    assert all(r.reason_signal and r.reason_need for r in actions if r.personalised)
    for r in actions[:40]:  # the signal indicates the need, and the offer addresses it (kg/policy.yaml)
        if r.reason_signal:
            assert r.reason_need in rt.policy.signals[r.reason_signal].indicates
            assert r.reason_need in rt.policy.offers[r.chosen_offer].addresses
    assert all(r.reason_signal is None for r in rows if r.chosen_offer == "NO_ACTION")


def test_summary_labels(built):
    _, _, s = built
    assert s.signal_labels["S4"] == "Price guarantee ends within 90 days"
    assert s.signal_labels["S1"] == "Gas meter deregistered"
    assert s.need_labels["N-HEAT-PUMP"] == "Heat pump / electric heating"
    assert all("{" not in v for v in s.signal_labels.values())
