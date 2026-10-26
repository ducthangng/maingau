"""Tunable parameters (B), policy diff (C) and automatic eval_time (D) — README §6.15."""

import collections
import importlib.util
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from nba.kg.policy import PolicyError, load_policy, validate
from nba.kg.signals import extract_signals
from nba.state import build_states, resolve_eval_time

REPO = Path(__file__).resolve().parents[1]


def _with(policy, **params):
    return replace(policy, params={**policy.params, **params})


# ---- D: eval_time

def test_eval_time_auto_is_end_of_snapshot_day(policy, tables):
    assert policy.config["eval_time"] == "2026-09-30T23:59:59"
    assert resolve_eval_time(tables, "auto") == datetime(2026, 9, 30, 23, 59, 59)
    assert resolve_eval_time(tables, "2026-10-02T12:00:00") == datetime(2026, 10, 2, 12)
    assert next(iter(build_states(tables, customer_ids=["MG-100068"]).values())).eval_time == datetime(2026, 9, 30, 23, 59, 59)


def test_eval_time_cannot_be_guessed_without_value_dates(tables):
    t = dict(tables)
    t["customer_value"] = tables["customer_value"].assign(clv_calc_date=None)
    with pytest.raises(ValueError):
        resolve_eval_time(t, "auto")


# ---- B: parameters

def test_parameters_are_validated(policy, tables):
    ids = set(tables["product_catalog"]["product_id"])
    assert validate(policy, ids) == []
    missing = replace(policy, params={k: v for k, v in policy.params.items() if k != "failed_charges_min"})
    assert any("failed_charges_min" in p for p in validate(missing, ids))
    assert any("risk_churn_min" in p for p in validate(_with(policy, risk_churn_min=35), ids))
    assert any("unknown parameter" in p for p in validate(_with(policy, typo_window=3), ids))


def test_invalid_parameter_stops_loading(tmp_path):
    text = (REPO / "kg" / "policy.yaml").read_text(encoding="utf-8").replace("risk_churn_min: 0.35", "risk_churn_min: 35")
    bad = tmp_path / "policy.yaml"
    bad.write_text(text, encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_parameters_drive_the_signals(states, policy):
    def count(p, sid):
        return sum(1 for s in states.values() if sid in {x.id for x in extract_signals(s, p)})

    assert count(policy, "S2") == 2 and count(_with(policy, failed_charges_min=4), "S2") == 0
    assert count(_with(policy, price_guarantee_window_days=30), "S4") < count(policy, "S4") == 143
    assert count(_with(policy, data_limit_min_months=3), "S5") < count(policy, "S5") == 11


def test_parameters_drive_triage(states, policy, pop):
    from nba.kg.segments import triage

    def tiers(p):
        return collections.Counter(triage(s, extract_signals(s, p), p, pop).urgency_tier for s in states.values())

    assert tiers(policy)["P1"] == 53
    assert tiers(_with(policy, p1_dunning_min=3))["P1"] < 53  # dunning level 2 moves down to P2


# ---- C: policy diff

def _policy_diff():
    spec = importlib.util.spec_from_file_location("policy_diff", REPO / "scripts" / "policy_diff.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_policy_diff_lists_only_changed_customers(policy, tables):
    pd_ = _policy_diff()
    ids = ["MG-100009", "MG-100659", "MG-100068", "MG-100023"]
    assert pd_.diff_decisions(policy, policy, tables, customer_ids=ids) == []
    changed = pd_.diff_decisions(policy, _with(policy, failed_charges_min=4), tables, customer_ids=ids)
    who = {c for c, _, _ in changed}
    assert {"MG-100009", "MG-100659"} <= who and "MG-100068" not in who
    assert all(len(row) == 3 and row[1] != row[2] for row in changed)  # customer, before, after; no reasons


# ---- review fixes

def test_eval_time_offsets_and_dates_are_normalised(tables):
    from datetime import date

    assert resolve_eval_time(tables, "2026-09-30T21:59:59Z") == datetime(2026, 9, 30, 21, 59, 59)
    assert resolve_eval_time(tables, "2026-09-30T23:59:59+02:00").tzinfo is None
    assert resolve_eval_time(tables, date(2026, 9, 30)) == datetime(2026, 9, 30, 23, 59, 59)


def test_auto_eval_time_follows_the_catalog_workbook(tables):
    assert tables["product_catalog"].attrs["workbook"].endswith("maingau_nba_mockdata.xlsx")
    p = load_policy(catalog=tables["product_catalog"])
    assert p.config["eval_time"] == "2026-09-30T23:59:59"


def test_labels_follow_parameters_and_s4_cannot_widen(policy, tables):
    ids = set(tables["product_catalog"]["product_id"])
    assert policy.signals["S2"].label == "≥ 3 failed charging sessions in 30 days"
    assert any("price_guarantee_window_days" in p for p in validate(_with(policy, price_guarantee_window_days=120), ids))

