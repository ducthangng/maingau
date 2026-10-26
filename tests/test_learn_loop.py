"""Feedback loop (nba/learn): posteriors, traffic light, diagnosis, approved overrides and their limits."""
from __future__ import annotations

import json
import shutil

import pytest
import yaml

from nba.data import REPO
from nba.engine.assemble import assemble
from nba.engine.config import load_config
from nba.engine.propensity import p_accept
from nba.engine.runtime import Runtime
from nba.learn.__main__ import apply, run
from nba.learn.backtest import with_overrides
from nba.learn.diagnose import cases
from nba.learn.evidence import Evidence, load_settings
from nba.learn.health import AMBER, GREEN, RED, classify, patterns
from nba.learn.stats import Arm, prob_greater, uplift


@pytest.fixture(scope="module")
def runtime():
    return Runtime.load()


@pytest.fixture(scope="module")
def evidence(runtime):
    return Evidence.from_runtime(runtime)


@pytest.fixture(scope="module")
def found(evidence):
    return {p.key: p for p in patterns(evidence)}


def test_prob_greater_is_symmetric_and_ordered():
    same = prob_greater(Arm(100, 5, 0.03, 30), Arm(100, 5, 0.03, 30))
    assert same == pytest.approx(0.5, abs=0.01)
    assert prob_greater(Arm(200, 20, 0.03, 30), Arm(200, 2, 0.03, 30)) > 0.99
    assert prob_greater(Arm(200, 2, 0.03, 30), Arm(200, 20, 0.03, 30)) < 0.01


def test_prior_shape_below_one_does_not_break_the_grid():
    # control prior 0.02 × 30 = 0.6 < 1: density is infinite at 0 but the probability must stay sane
    p = prob_greater(Arm(203, 0, 0.034, 30), Arm(21, 0, 0.02, 30))
    assert 0.2 < p < 0.5


def test_classify_thresholds():
    settings = load_settings()
    assert classify(uplift(Arm(10, 5, 0.03, 30), Arm(20, 0, 0.02, 30)), settings)[0] == AMBER  # too few sends
    assert classify(uplift(Arm(150, 0, 0.03, 30), Arm(20, 0, 0.02, 30)), settings)[0] == RED  # zero response
    assert classify(uplift(Arm(200, 25, 0.03, 30), Arm(25, 0, 0.02, 30)), settings)[0] == GREEN


def test_mock_history_traffic_light(found):
    assert found["P-MO-01"].status == GREEN
    assert found["P-AS-01"].status == RED and found["P-AS-01"].result.treated.conv == 0
    assert found["P-EN-05"].status == RED
    assert found["P-EN-02"].status == AMBER  # 16/209 vs 1/19 is promising but not yet clear


def test_red_offers_are_diagnosed_as_targeting(evidence, found, runtime):
    by_id = {c.id: c for c in cases(evidence, list(found.values()), runtime.policy, "rate")}
    assert set(by_id) == {"FIX-P-AS-01", "FIX-P-EN-05"}
    case = by_id["FIX-P-AS-01"]
    assert case.layer.startswith("targeting")
    option = next(o for o in case.options if o.id == "A")
    assert set(option.overrides) == {"P-AS-01"}
    assert option.overrides["P-AS-01"]["n_treated"] == 5  # only the signal-matched sends
    assert any(o.id == "S" and o.overrides["P-AS-01"]["p"] == 0.0 for o in case.options)


def test_override_is_used_and_most_specific_wins(runtime):
    cfg = with_overrides(runtime.cfg, {
        "P-MO-01": {"p": 0.2, "case": "FIX-T", "approved_by": "test"},
        "P-MO-01|sms": {"p": 0.05, "case": "FIX-T", "approved_by": "test"},
    })
    assert p_accept("P-MO-01", "sms", "sie", cfg.history, cfg).p_accept == 0.05
    email = p_accept("P-MO-01", "email", "sie", cfg.history, cfg)
    assert email.p_accept == 0.2 and email.source.mode == "assumption" and email.confidence == "low"
    assert p_accept("P-MO-02", "email", "sie", cfg.history, cfg).source.mode == runtime.cfg.p_mode


def test_override_never_unblocks_a_hard_rule(runtime):
    # MG-100096: dunning level 3 blocks every sales tuple; p = 1 for StromWärme must not bring it back
    cfg = with_overrides(runtime.cfg, {"P-EN-03": {"p": 1.0, "case": "FIX-T", "approved_by": "test"}})
    card = assemble(runtime.states["MG-100096"], runtime.pop, runtime.policy, cfg)
    assert all(c.offer_id != "P-EN-03" for c in card.candidates)
    assert card.chosen.tuple_id.startswith("P-SV-01") or card.chosen.tuple_id == "NO_ACTION"


def test_config_rejects_unreviewed_override(runtime, tmp_path):
    settings = yaml.safe_load((REPO / "config" / "nba.yaml").read_text(encoding="utf-8"))
    settings["p_overrides"] = {"P-AS-01": {"p": 0.1, "case": "FIX-P-AS-01"}}
    path = tmp_path / "nba.yaml"
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")
    with pytest.raises(ValueError, match="approved_by"):
        load_config(runtime.tables, path)


def test_run_is_deterministic_and_apply_writes_a_reviewed_override(runtime, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    run(runtime, a, with_backtest=False)
    run(runtime, b, with_backtest=False)
    assert (a / "health.json").read_bytes() == (b / "health.json").read_bytes()
    _, _, again = run(runtime, a, with_backtest=False)
    assert again == []  # the ledger records the same evidence only once

    config = tmp_path / "nba.yaml"
    shutil.copyfile(REPO / "config" / "nba.yaml", config)
    record = apply(a, "FIX-P-AS-01", "A", "tester", config_path=config)
    assert record["overrides"] == ["P-AS-01"]
    cfg = load_config(runtime.tables, config)
    entry = cfg.settings["p_overrides"]["P-AS-01"]
    assert entry["case"] == "FIX-P-AS-01" and entry["approved_by"] == "tester" and entry["n_treated"] == 5
    apply(a, "FIX-P-AS-01", "S", "tester", config_path=config)  # a later decision replaces the earlier one
    cfg = load_config(runtime.tables, config)
    assert cfg.settings["p_overrides"]["P-AS-01"]["p"] == 0.0
    log = [json.loads(line) for line in (a / "fix_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["option"] for r in log] == ["A", "S"]

    card = assemble(runtime.states["MG-100023"], runtime.pop, runtime.policy, cfg)
    assert not any(c.offer_id == "P-AS-01" for c in card.candidates)
