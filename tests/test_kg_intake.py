"""Data-contract validation (README §6.15): clean data passes, injected anomalies are caught."""

import copy

import pandas as pd
import pytest

from nba.kg.intake import load_contract, validate_tables


@pytest.fixture(scope="module")
def contract():
    return load_contract()


def _errors(issues):
    return {(i.code, i.where) for i in issues if i.level == "ERROR"}


def _copy(tables):
    return {k: v.copy(deep=True) for k, v in tables.items()}


def test_current_workbook_has_no_errors(tables, contract):
    issues = validate_tables(tables, contract)
    assert not [i for i in issues if i.level == "ERROR"]
    later = {i.where: i.count for i in issues if i.code == "AFTER_EVAL_TIME"}
    assert later == {"charge_sessions.cdr_received_at": 79, "charge_sessions.ended_at": 15,
                     "service_interactions.resolved_at": 2}  # the known snapshot inconsistencies (README §3)


@pytest.mark.parametrize("sheet,col,value,code", [
    ("energy_contracts", "status", "cancelled", "UNKNOWN_VALUE"),         # would silently skip EXCL-CANCELLATION
    ("consent_status", "status", "pending", "UNKNOWN_VALUE"),
    ("consent_status", "consent_type", "whatsapp", "UNKNOWN_VALUE"),
    ("hems_devices", "device_type", "ev_charger", "UNKNOWN_VALUE"),
    ("customer_value", "churn_prob_12m", 1.5, "OUT_OF_RANGE"),
    ("energy_contracts", "dunning_level", "high", "NOT_A_NUMBER"),
])
def test_unknown_or_invalid_values_are_errors(tables, contract, sheet, col, value, code):
    t = _copy(tables)
    t[sheet].loc[t[sheet].index[0], col] = value
    assert (code, f"{sheet}.{col}") in _errors(validate_tables(t, contract))


def test_unknown_churn_driver_label(tables, contract):
    t = _copy(tables)
    t["customer_value"].loc[t["customer_value"].index[0], "churn_drivers"] = "smart meter fault"
    assert ("UNKNOWN_CHURN_DRIVER", "customer_value.churn_drivers") in _errors(validate_tables(t, contract))


def test_duplicate_key_unknown_customer_and_missing_column(tables, contract):
    t = _copy(tables)
    ec = t["energy_contracts"]
    ec.loc[ec.index[1], "contract_id"] = ec.loc[ec.index[0], "contract_id"]
    t["consent_status"].loc[t["consent_status"].index[0], "customer_id"] = "MG-999999"
    t["mobile_contracts"] = t["mobile_contracts"].drop(columns=["data_limit_reached_3m"])
    errs = _errors(validate_tables(t, contract))
    assert ("DUPLICATE_KEY", "energy_contracts") in errs
    assert ("UNKNOWN_CUSTOMER", "consent_status") in errs
    assert ("MISSING_COLUMN", "mobile_contracts.data_limit_reached_3m") in errs


def test_non_iso_date_is_an_error(tables, contract):
    t = _copy(tables)
    n = len(t["energy_contracts"])
    raw = {"energy_contracts": pd.DataFrame({"price_guarantee_until": ["31/12/2026", "03.04.2026"] + [None] * (n - 2)})}
    assert ("NON_ISO_DATE", "energy_contracts.price_guarantee_until") in _errors(validate_tables(t, contract, raw=raw))


def test_unreadable_boolean_is_an_error(tables, contract):
    t = _copy(tables)
    n = len(t["energy_contracts"])
    raw = {"energy_contracts": pd.DataFrame({"feed_in_meter": ["WAHR"] + ["false"] * (n - 1)})}
    assert ("UNPARSEABLE_BOOL", "energy_contracts.feed_in_meter") in _errors(validate_tables(t, contract, raw=raw))


def test_empty_rule_value_is_an_error_but_nullable_columns_pass(tables, contract):
    t = _copy(tables)
    t["energy_contracts"].loc[t["energy_contracts"].index[0], "status"] = None
    errs = _errors(validate_tables(t, contract))
    assert ("NULL_VALUE", "energy_contracts.status") in errs
    assert ("NULL_VALUE", "service_nba_feedback.customer_reaction") not in errs  # 66 legitimate empty cells


def test_rule_used_enums_are_errors(tables, contract):
    t = _copy(tables)
    t["service_interactions"].loc[t["service_interactions"].index[0], "category"] = "Complaint"
    assert ("UNKNOWN_VALUE", "service_interactions.category") in _errors(validate_tables(t, contract))


def test_missing_key_column_or_sheet_is_reported_not_crashing(tables, contract):
    t = _copy(tables)
    t["product_catalog"] = t["product_catalog"].drop(columns=["product_id"])
    del t["customer_value"]
    errs = _errors(validate_tables(t, contract))
    assert ("MISSING_COLUMN", "product_catalog.product_id") in errs
    assert ("MISSING_SHEET", "customer_value") in errs


def test_guest_order_without_order_id_is_flagged(tables, contract):
    t = _copy(tables)
    so = t["shop_orders"]
    guest = so.index[so["customer_id"].isna()][0]
    so.loc[guest, "order_id"] = None
    assert ("NULL_KEY", "shop_orders") in _errors(validate_tables(t, contract))
