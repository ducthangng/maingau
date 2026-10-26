"""Calibration factor k = buys observed / buys expected per offer × channel × tone (whiteboard 27 Oct)."""
import pytest

from nba.engine.config import load_config
from nba.engine.propensity import calibration_factor, p_accept
from nba.engine.runtime import Runtime


def test_factor_matches_the_whiteboard_and_is_shrunk():
    assert calibration_factor(3, 10, {"prior_buys": 0}) == pytest.approx(0.3)  # 10 expected, 3 bought
    assert calibration_factor(3, 10, {}) == pytest.approx(8 / 15)  # pulled toward 1 by 5 pseudo-buys
    assert calibration_factor(0, 0, {}) == 1.0  # no evidence, no change
    assert calibration_factor(0, 100, {"prior_buys": 0}) == 0.2 and calibration_factor(50, 1, {}) == 3.0  # capped


def test_p_is_scaled_by_k_only_where_it_should_be(tables):
    cfg = load_config(tables)
    off = cfg.with_settings(calibration={**cfg.settings["calibration"], "active": False})
    on = p_accept("P-EN-02", "newsletter_email", "du", cfg.history, cfg)
    base = p_accept("P-EN-02", "newsletter_email", "du", off.history, off)
    assert on.k is not None and on.p_accept == pytest.approx(base.p_accept * on.k)
    assert on.source.k == pytest.approx(on.k, abs=1e-4) and on.k_expected > 0
    assert p_accept("P-MO-01", "portal_popup", "sie", cfg.history, cfg, generic=True).k is None  # D1 catalog average
    assert p_accept("P-SV-01", "service_agent", "sie", cfg.history, cfg).k is None  # assumption


def test_a_worse_than_expected_channel_loses_to_the_next_one(tables, states, policy, pop):
    rt = Runtime(tables, dict(states), pop, policy, load_config(tables))
    off = rt.with_rules(settings={"calibration": {**rt.cfg.settings["calibration"], "active": False}})
    before, after = off.card("MG-100019"), rt.card("MG-100019")
    assert before.chosen.tuple_id == "P-EN-02|newsletter_email|du" and after.chosen.tuple_id == "P-EN-02|app_push|du"
    old = next(c for c in after.candidates if c.tuple_id == before.chosen.tuple_id)
    new = next(c for c in after.candidates if c.tuple_id == after.chosen.tuple_id)
    assert old.valuation.p_source.k < 1 and new.valuation.delta_clv > old.valuation.delta_clv
    assert "calibrated ×" in " ".join(old.why)


def test_load_config_validates_calibration(tables, tmp_path):
    import yaml

    from nba.data import REPO

    settings = yaml.safe_load((REPO / "config" / "nba.yaml").read_text(encoding="utf-8"))
    settings["calibration"] = {"active": True, "min_k": 2.0, "max_k": 3.0}
    bad = tmp_path / "nba.yaml"
    bad.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(tables, bad)
