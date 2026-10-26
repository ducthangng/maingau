"""Look-alike learning (nba/learn/lookalike.py): 🟢 offers learn who bought, similar customers move up or down."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from nba.engine.assemble import assemble
from nba.engine.propensity import Propensity, personalise
from nba.contracts import PSource
from nba.engine.runtime import Runtime
from nba.learn.lookalike import Lookalike, outcomes_by_offer, summary

SETTINGS = {"neighbours": 3, "prior_strength": 0, "max_ratio": 3.0}


def toy(profiled=("a", "b", "c", "d", "e", "f")) -> Lookalike:
    features = pd.DataFrame({"x": [0.0, 0.1, 0.2, 5.0, 5.1, 5.2], "y": [1.0, 1.0, None, 3.0, 3.0, 3.0]},
                            index=list("abcdef"))
    # a, b, c look alike and bought; d, e, f look alike and did not
    offers = {"O": {c: (c in "abc", 100.0 if c in "abc" else None, "sms") for c in "abcdef"}}
    return Lookalike(features, {"x": 1.0, "y": 1.0}, SETTINGS, offers, frozenset(profiled))


def test_customers_like_the_buyers_go_up_like_the_non_buyers_go_down():
    model = toy()
    up, down = model.score("a", "O", 0.1), model.score("d", "O", 0.1)
    assert up.lift > 1 > down.lift and up.p > 0.1 > down.p
    assert all(p.customer_id != "a" for p in up.peers)  # never their own peer
    assert [p.customer_id for p in up.peers][:2] == ["b", "c"]


def test_missing_values_are_left_out_not_filled():
    model = toy()
    assert model.similarity("a", "c") == model.similarity("c", "a") > model.similarity("a", "d")


def test_lift_is_capped():
    model = toy()
    model.settings = {**SETTINGS, "max_ratio": 1.2}
    assert model.score("a", "O", 0.1).lift == 1.2


def test_without_profiling_consent_no_score_and_not_a_peer():
    model = toy(profiled=("a", "b", "d", "e", "f"))
    assert model.score("c", "O", 0.1) is None
    assert "c" not in {p.customer_id for p in model.score("a", "O", 0.1).peers}


def test_only_positive_value_conversions_count_as_good():
    rows = [{"offer_id": "O", "customer_id": "a", "delivery_status": "delivered", "control_group": False,
             "converted_within_14d": True, "conversion_value_eur": 0.0, "decided_at": "1"},
            {"offer_id": "O", "customer_id": "b", "delivery_status": "delivered", "control_group": False,
             "converted_within_14d": True, "conversion_value_eur": 50.0, "decided_at": "2"},
            {"offer_id": "O", "customer_id": "c", "delivery_status": "delivered", "control_group": True,
             "converted_within_14d": True, "conversion_value_eur": 50.0, "decided_at": "3"}]
    assert outcomes_by_offer(rows, ["O"]) == {"O": {"a": (False, None, None), "b": (True, 50.0, None)}}


def test_reviewed_override_and_assumption_win():
    class Cfg:
        lookalike, p_mode = toy(), "rate"
    src = PSource(mode="assumption", level="assumption")
    override = Propensity(0.0, "low", src, 0.0, 0.0, "override:O:FIX-O")
    assert personalise(override, "O", "a", Cfg) == (override, None)
    rate = Propensity(0.1, "low", PSource(mode="rate", level="offer"), 0.1, 0.05, "offer")
    p, match = personalise(rate, "O", "a", Cfg)
    assert match and p.p_accept == match.p and p.baseline_level == "lookalike:offer"


@pytest.fixture(scope="module")
def runtime():
    return Runtime.load()


def test_runtime_learns_only_green_offers(runtime):
    model = runtime.cfg.lookalike
    assert sorted(model.offers) == ["P-MO-01", "P-SH-01"]  # P-AS-01 and P-EN-05 are red: they go to a fix case
    learned = summary(model)
    assert learned["offers"]["P-MO-01"]["buyers"] > 0 and learned["offers"]["P-MO-01"]["profile"]


def test_learning_moves_mg_100001_and_explains_it(runtime):
    card = runtime.card("MG-100001")
    unlearned = assemble(runtime.states["MG-100001"], runtime.pop, runtime.policy,
                         replace(runtime.cfg, lookalike=None, _versions=None))
    mobile = [c for c in card.candidates if c.offer_id == "P-MO-01" and c.valuation]
    assert mobile and all(any("Look-alike:" in w for w in c.why) for c in mobile)
    assert unlearned.chosen.tuple_id.startswith("P-MO-01") and not card.chosen.tuple_id.startswith("P-MO-01")


def test_similar_report_lists_peers_and_learning(runtime):
    from nba.learn.__main__ import _names
    from nba.learn.similar import report

    text = report(runtime, "MG-100001", _names(runtime), 5)
    assert "MG-100357" in text and "## What the engine learned for this customer" in text
    assert "Changed by the learning" in text
