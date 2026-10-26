"""Foundation checks for data loading, customer state and the shared contracts (Agent KG)."""

from __future__ import annotations

import json
from datetime import datetime

from nba.contracts import CustomerCard, IndexRow
from nba.data import load_events
from nba.state import active_lines, contacts, owns


def test_workbook_shape(tables):
    assert len(tables) == 23
    assert len(tables["customer_master"]) == 750
    assert int(tables["shop_orders"]["is_guest"].sum()) == 25
    row = tables["nba_action_history"].iloc[0].to_dict()
    assert isinstance(row["decided_at"], datetime)
    assert isinstance(row["control_group"], bool)


def test_events_dedup_and_order():
    events = load_events()
    assert len(events) == 635
    assert events == sorted(events, key=lambda e: (e["ingested_at"], e["event_id"]))


def test_states_and_holdings(states):
    assert len(states) == 750
    s = states["MG-100023"]
    assert active_lines(s) == {"electricity"}
    assert owns(s, "P-SH-02") and not owns(s, "P-AS-01")
    assert owns(states["MG-100009"], "P-AS-01")
    assert all(r["delivery_status"] == "delivered" for r in contacts(s, 90))


def test_schema_files_match_contracts():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "docs" / "schema"
    for name, model in {"customer_card": CustomerCard, "index_row": IndexRow}.items():
        on_disk = json.loads((root / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert on_disk == model.model_json_schema(), f"run scripts/export_schema.py ({name})"


def test_cache_key_includes_parser_fingerprint():
    from nba.data import DEFAULT_WORKBOOK, _cache_key

    key = _cache_key(DEFAULT_WORKBOOK)
    assert key.startswith("workbook-") and len(key.split("-")) == 4


def test_no_nan_in_typed_tables(tables):
    import math

    for name, df in tables.items():
        for col in df.columns:
            assert not any(isinstance(v, float) and math.isnan(v) for v in df[col]), (name, col)
