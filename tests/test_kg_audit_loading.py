"""KG audit: data loading and customer state (README §3, §5.1, §5.2, K4)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from kg_audit_oracle import NOT_HELD, expected_events, oracle, raw, raw_event_lines

from nba.data import load_events
from nba.state import build_states, contacts, owns

REPO = Path(__file__).resolve().parents[1]
FLAG_COLUMNS = {"portal_account", "app_installed", "feed_in_meter", "control_group", "converted_within_14d",
                "consent_checked", "unsubscribed", "esim", "app_user", "first_contact_resolution", "delivered", "bounced"}
FREE_TEXT = {"README", "columns", "clv_method"}


def _date_column(col: str) -> bool:
    return col == "date" or col.endswith(("_at", "_date", "_since", "_until"))


def test_sheet_count_and_unique_customers(tables):
    assert len(tables) == 23 and set(tables) == set(raw())
    for sheet in ("customer_master", "customer_value"):
        ids = tables[sheet]["customer_id"]
        assert len(ids) == 750 and ids.nunique() == 750, sheet
    assert set(tables["customer_master"]["customer_id"]) == set(tables["customer_value"]["customer_id"])


def test_every_raw_row_is_kept(tables):
    for name, df in raw().items():
        assert len(tables[name]) == len(df), name


def test_flag_columns_are_bool(tables):
    seen = set()
    for name, df in tables.items():
        for col in FLAG_COLUMNS & set(df.columns):
            seen.add(col)
            bad = {type(v).__name__ for v in df[col] if v is not None and not isinstance(v, bool)}
            assert not bad, (name, col, bad)
    assert seen == FLAG_COLUMNS


def test_date_columns_are_timezone_naive_datetimes(tables):
    for name, df in tables.items():
        if name in FREE_TEXT:
            continue
        for col in df.columns:
            if not _date_column(col) or col.endswith("_id"):
                continue
            for v in df[col]:
                if v is not None:
                    assert isinstance(v, datetime) and v.tzinfo is None, (name, col, v)


def test_empty_strings_become_none(tables):
    for name, df in tables.items():
        for col in df.columns:
            assert not any(isinstance(v, str) and not v.strip() for v in df[col]), (name, col)
    # an empty cell in the raw sheet is None after loading
    so = tables["shop_orders"]
    assert so["customer_id"].isna().sum() == raw()["shop_orders"]["customer_id"].isna().sum() == 25


def test_guest_orders_flagged_and_absent_from_states(tables, states):
    so = tables["shop_orders"]
    guests = so[so["is_guest"]]
    assert len(guests) == 25 and guests["customer_id"].isna().all()
    assert so.loc[~so["is_guest"], "customer_id"].notna().all()
    guest_ids = set(guests["order_id"])
    in_states = {r["order_id"] for s in states.values() for r in s.rows["shop_orders"]}
    assert not guest_ids & in_states
    assert len(in_states) == len(so) - 25


def test_load_events_dedups_and_sorts():
    lines = raw_event_lines()
    assert len(lines) == 647
    events = load_events()
    assert len(events) == 635
    assert [(e["event_id"], e["ingested_at"].strftime("%Y-%m-%d %H:%M:%S")) for e in events] == expected_events()
    assert len({(e["event_id"], e["occurred_at"]) for e in events}) == 635
    for e in events:
        assert isinstance(e["occurred_at"], datetime) and isinstance(e["ingested_at"], datetime)
        assert e["ingested_at"].tzinfo is None
        eff = (e.get("payload") or {}).get("effective_date")
        assert (e["effective_date"] is not None) == bool(eff), e["event_id"]


def test_build_states_shape_and_stable_revision(tables, states):
    assert len(states) == 750
    again = build_states(tables)
    assert {c: s.revision for c, s in states.items()} == {c: s.revision for c, s in again.items()}
    assert len({s.revision for s in states.values()}) == 750
    s = states["MG-100068"]
    assert s.eval_time == datetime(2026, 9, 30, 23, 59, 59) and s.snapshot_mode == "provided" and s.applied_events == []
    for sheet, rows in s.rows.items():
        assert all(r["customer_id"] == "MG-100068" for r in rows), sheet


def test_contacts_30d_match_oracle_for_every_customer(states):
    o = oracle()
    diffs = {}
    for cid, s in states.items():
        got = {r["action_id"] for r in contacts(s, 30)}
        want = o.contacts(cid, 30)
        if got != want:
            diffs[cid] = (sorted(got - want), sorted(want - got))
    assert not diffs, dict(list(diffs.items())[:10])


def test_contacts_window_is_half_open(states):
    """(eval - days, eval]: a contact exactly `days` ago is out, one at eval_time is in."""
    from dataclasses import replace
    from datetime import timedelta

    s = states["MG-100068"]
    base = {"customer_id": s.customer_id, "delivery_status": "delivered", "control_group": False}
    rows = dict(s.rows, nba_action_history=[
        {**base, "action_id": "edge-out", "decided_at": s.eval_time - timedelta(days=30)},
        {**base, "action_id": "edge-in", "decided_at": s.eval_time},
        {**base, "action_id": "future", "decided_at": s.eval_time + timedelta(seconds=1)},
        {**base, "action_id": "control", "decided_at": s.eval_time, "control_group": True},
        {**base, "action_id": "not-sent", "decided_at": s.eval_time, "delivery_status": "not_sent_control"},
    ])
    assert [r["action_id"] for r in contacts(replace(s, rows=rows), 30)] == ["edge-in"]


def test_owns_matches_oracle_for_all_customers_and_offers(states):
    o = oracle()
    diffs = []
    for cid, s in states.items():
        for offer in NOT_HELD:
            if owns(s, offer) != o.owns(cid, offer):
                diffs.append((cid, offer, owns(s, offer), o.owns(cid, offer)))
    assert not diffs, diffs[:20]


def test_returned_and_cancelled_orders_do_not_count(states):
    o = oracle()
    checked = 0
    for cid, s in states.items():
        statuses = {r["product_name"]: set() for r in s.rows["shop_orders"]}
        for r in s.rows["shop_orders"]:
            statuses[r["product_name"]].add(r["order_status"])
        if statuses.get("Wallbox 11 kW") and "delivered" not in statuses["Wallbox 11 kW"] \
                and "wallbox" not in o.device_types(cid):
            assert not owns(s, "P-SH-02"), cid
            checked += 1
    assert checked >= 1


def test_autostrom_count_is_computed_not_hard_coded():
    assert oracle().autostrom_counts() == (159, 161, 127)  # README §3 / K4
    code = [REPO / "nba" / "data.py", REPO / "nba" / "state.py", *sorted((REPO / "nba" / "kg").glob("*.py"))]
    hits = [f"{p.name}:{i}" for p in code for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"\b150\b", line) and not line.lstrip().startswith("#")]
    assert not hits, hits
