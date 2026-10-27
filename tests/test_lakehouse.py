"""Databricks source and results layer (nba/lakehouse.py) against an in-memory fake warehouse.

The fake understands only the SQL nba.lakehouse writes: CREATE/DROP, CTAS from read_files over an
uploaded JSON-lines file, and SELECT ... ORDER BY. No network.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from nba import data, lakehouse as lh

REPO = Path(__file__).resolve().parents[1]
SETTINGS = lh.Settings(source="databricks", catalog="workspace", raw_schema="maingau_raw", out_schema="maingau_nba")


class FakeWarehouse:
    warehouse_id = "fake-wh"

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.tables: dict[str, tuple[list[str], list[dict]]] = {}
        self.functions: dict[str, str] = {}
        self.statements: list[str] = []

    def put(self, path, body):
        self.files[path] = body

    @staticmethod
    def _cols(text):
        return [c.strip().strip("`").split("` ")[0].strip("`") for c in text.split(", ")]

    @staticmethod
    def _text(v):
        if v is None or isinstance(v, str):
            return v
        return json.dumps(v) if isinstance(v, (list, dict, bool)) else str(v)

    def query(self, sql, params=None):
        self.statements.append(sql)
        if m := re.match(r"SHOW TABLES IN (\S+) LIKE '([^']+)'", sql):
            return ["tableName"], [[m[2]]] if f"{m[1]}.`{m[2]}`" in self.tables else []
        if m := re.match(r"CREATE TABLE IF NOT EXISTS (\S+) \((.+)\)$", sql):
            self.tables.setdefault(m[1], (self._cols(m[2]), []))
            return [], []
        if m := re.match(r"INSERT INTO (\S+) \((.+?)\) VALUES \((.+)\)$", sql):
            assert params is not None and "'" not in m[3]  # values only ever travel as parameters
            cols = self._cols(m[2])
            self.tables[m[1]][1].append(dict(zip(cols, (params[k.strip()[1:]] for k in m[3].split(", ")))))
            return [], []
        if m := re.match(r"CREATE OR REPLACE TABLE (\S+) COMMENT '(?:[^'\\]|\\.)*' AS SELECT (.+?) FROM read_files\('([^']+)'", sql):
            rows = [json.loads(line) for line in self.files[m[3]].decode("utf-8").splitlines()]
            self.tables[m[1]] = (self._cols(m[2]), rows)
        elif m := re.match(r"CREATE OR REPLACE TABLE (\S+) \((.+)\) COMMENT", sql):
            self.tables[m[1]] = (self._cols(m[2]), [])
        elif m := re.match(r"CREATE OR REPLACE FUNCTION (\S+?)\(", sql):
            self.functions[m[1]] = sql
        elif m := re.match(r"DROP TABLE IF EXISTS (\S+)", sql):
            self.tables.pop(m[1], None)
        elif m := re.match(r"SELECT (.+?) FROM (\S+) ORDER BY (\S+)$", sql):
            if m[2] not in self.tables:
                raise lh.LakehouseError(f"[TABLE_OR_VIEW_NOT_FOUND] {m[2]}")
            cols, order = self._cols(m[1]), m[3].strip("`")
            rows = sorted(self.tables[m[2]][1], key=lambda r: r[order])
            return cols, [[self._text(r.get(c)) for c in cols] for r in rows]
        elif not sql.startswith(("CREATE ", "ALTER TABLE ")):
            raise AssertionError(f"fake warehouse does not understand: {sql[:80]}")
        return [], []


@pytest.fixture(scope="module")
def uploaded():
    wh = FakeWarehouse()
    lh.upload_raw(wh, SETTINGS)
    return wh


@pytest.fixture
def use_databricks(monkeypatch, uploaded):
    """Point the loader at the fake warehouse; restores the per-process source decision afterwards."""
    monkeypatch.setattr(lh, "load_settings", lambda *a, **k: SETTINGS)
    monkeypatch.setattr(lh, "Warehouse", lambda s: uploaded)
    lh.reset()
    yield uploaded
    lh.reset()


@pytest.fixture(scope="module")
def local_tables():
    lh.reset()
    tables, events = data.load_workbook(use_cache=False), data.load_events()
    assert lh.status()["source"] == "local"
    lh.reset()
    return tables, events


def test_upload_writes_every_sheet_events_and_manifest_last(uploaded):
    raw = SETTINGS.raw
    sheets = lh.contract_sheets()
    assert {raw(t) for t in lh.safe_names(sheets)} <= set(uploaded.tables)
    assert uploaded.statements[-1].startswith(f"CREATE OR REPLACE TABLE {raw(lh.MANIFEST)}")
    assert any(s == f"DROP TABLE IF EXISTS {raw(lh.MANIFEST)}" for s in uploaded.statements[:5])
    manifest = uploaded.tables[raw(lh.MANIFEST)][1]
    assert [m["position"] for m in manifest] == list(range(24)) and manifest[-1]["kind"] == "events"
    counts = {m["table_name"]: m["n_rows"] for m in manifest}
    assert counts["customer_master"] == 750 and counts["consent_status"] == 4500 and counts[lh.EVENTS] == 647
    # Spark's read_files skips files whose name starts with "_" or ".": no table may come from such a file
    assert not [p for p in uploaded.files if p.rsplit("/", 1)[1][0] in "_."]
    # the original files land in the volume too
    assert {f"{SETTINGS.volume_dir}/files/{p.name}" for p in (data.DEFAULT_WORKBOOK, data.DEFAULT_EVENTS)} <= set(uploaded.files)


def test_raw_layer_reads_back_identical_to_the_workbook(uploaded):
    raw = lh.read_raw(uploaded, SETTINGS)
    local = pd.read_excel(data.DEFAULT_WORKBOOK, sheet_name=None, dtype=str)
    assert list(raw.sheets) == list(local)  # same sheet order
    for name, df in local.items():  # same headers (README's free-text header too), order, text and nulls
        pd.testing.assert_frame_equal(raw.sheets[name], df, obj=name)
    assert raw.event_lines == data.event_lines(data.DEFAULT_EVENTS)


def test_databricks_source_gives_the_same_tables_and_events(use_databricks, local_tables):
    tables, events = local_tables
    remote = data.load_workbook()
    assert lh.status()["source"] == "databricks" and "maingau_raw" in lh.status()["detail"]
    assert list(remote) == list(tables)
    for name in tables:
        pd.testing.assert_frame_equal(remote[name], tables[name], obj=name)
        assert remote[name].attrs["workbook"] == tables[name].attrs["workbook"]  # policy loader re-reads the same source
    assert data.load_events() == events
    assert set(data.read_raw_sheets()) == set(tables)


def test_each_caller_gets_its_own_copy(use_databricks):
    first = data.load_workbook()
    first["customer_master"].loc[0, "city"] = "changed"
    assert data.load_workbook()["customer_master"].loc[0, "city"] != "changed"


def test_an_explicit_other_workbook_is_read_from_its_file(use_databricks, tmp_path):
    copy = tmp_path / "other.xlsx"
    shutil.copyfile(data.DEFAULT_WORKBOOK, copy)
    use_databricks.statements.clear()
    assert len(data.load_workbook(copy, use_cache=False)["customer_master"]) == 750
    assert not use_databricks.statements


def test_unreachable_workspace_falls_back_to_the_local_files(monkeypatch, local_tables):
    def unreachable(s):
        raise ConnectionError("cannot reach https://example.cloud.databricks.com")

    monkeypatch.setattr(lh, "load_settings", lambda *a, **k: SETTINGS)
    monkeypatch.setattr(lh, "Warehouse", unreachable)
    lh.reset()
    try:
        tables = data.load_workbook()
        st = lh.status()
        assert st["source"] == "local" and "fallback" in st["detail"] and "cannot reach" in st["detail"]
        pd.testing.assert_frame_equal(tables["energy_contracts"], local_tables[0]["energy_contracts"])
        assert data.load_events() == local_tables[1]
    finally:
        lh.reset()


def test_partial_or_missing_raw_layer_falls_back(monkeypatch, uploaded):
    partial = FakeWarehouse()
    partial.tables = dict(uploaded.tables)
    cols, rows = partial.tables[SETTINGS.raw("consent_status")]
    partial.tables[SETTINGS.raw("consent_status")] = (cols, rows[:100])  # an upload that stopped half way
    empty = FakeWarehouse()
    for wh, expected in ((partial, "consent_status has 100 rows"), (empty, "run scripts/databricks_sync.py upload")):
        monkeypatch.setattr(lh, "load_settings", lambda *a, **k: SETTINGS)
        monkeypatch.setattr(lh, "Warehouse", lambda s, wh=wh: wh)
        lh.reset()
        assert lh.remote_raw() is None
        assert lh.status()["source"] == "local" and expected in lh.status()["detail"]
    lh.reset()


def test_local_source_never_connects(monkeypatch):
    monkeypatch.setattr(lh, "load_settings", lambda *a, **k: lh.Settings(source="local"))
    monkeypatch.setattr(lh, "Warehouse", lambda s: pytest.fail("connected although source is local"))
    lh.reset()
    assert lh.remote_raw() is None and lh.status()["detail"] == "config/databricks.yaml source: local"
    lh.reset()


def test_committed_config_reads_local_and_env_overrides(tmp_path):
    assert lh.load_settings(env={}).source == "local"  # tests and the static demo never need a workspace
    s = lh.load_settings(env={"MAINGAU_DATA_SOURCE": "databricks", "MAINGAU_DATABRICKS_CATALOG": "demo"})
    assert (s.source, s.catalog, s.raw("x")) == ("databricks", "demo", "`demo`.`maingau_raw`.`x`")
    with pytest.raises(ValueError):
        lh.load_settings(env={"MAINGAU_DATA_SOURCE": "s3"})
    bad = lh.load_settings(env={"MAINGAU_DATABRICKS_CATALOG": "x`; DROP TABLE y; --"})
    with pytest.raises(lh.LakehouseError):
        bad.raw("customer_master")


def test_no_credentials_in_the_config():
    text = (REPO / "config" / "databricks.yaml").read_text(encoding="utf-8")
    assert not re.search(r"dapi[0-9a-f]{8,}|token\s*:|password", text, re.I)
    assert ".databrickscfg" in (REPO / ".gitignore").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def build_dir(tmp_path_factory):
    """A small out/ directory in the build's format, taken from the exported UI data."""
    src, out = REPO / "web" / "public" / "data", tmp_path_factory.mktemp("out")
    ids = ["MG-100068", "MG-100096", "MG-100112"]
    index = [r for r in json.loads((src / "index.json").read_text(encoding="utf-8")) if r["customer_id"] in ids]
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
    for sub in ("customers", "journey"):
        (out / sub).mkdir()
        for cid in ids:
            shutil.copyfile(src / sub / f"{cid}.json", out / sub / f"{cid}.json")
    entry = {"ts": "2026-10-01T09:00:00", "actor": "Anna", "action": "approved", "tuple_id": "P-EN-03|email|sie"}
    (out / "decision_log.jsonl").write_text(json.dumps({"customer_id": "MG-100068", "entry": entry}) + "\n", encoding="utf-8")
    (out / "data_source.json").write_text(json.dumps({"source": "databricks", "detail": "test"}), encoding="utf-8")
    return out


def test_publish_writes_results_and_mcp_functions(build_dir):
    wh = FakeWarehouse()
    counts = lh.publish(wh, SETTINGS, build_dir)
    assert counts["worklist"] == counts["customer_cards"] == counts["customer_journey"] == 3
    assert counts["decision_log"] == 1 and counts["customer_memory"] == 0 and counts["run_info"] == 1
    out = SETTINGS.out
    _, options = wh.tables[out("nba_options")]
    _, worklist = wh.tables[out("worklist")]
    for row in worklist:  # exactly the proposal is marked chosen
        chosen = [o["tuple_id"] for o in options if o["customer_id"] == row["customer_id"] and o["chosen"]]
        assert chosen == ([] if row["chosen_tuple"] == "NO_ACTION" else [row["chosen_tuple"]])
    _, blocked = wh.tables[out("nba_blocked")]
    assert {b["rule_id"] for b in blocked if b["customer_id"] == "MG-100096"} >= {"EXCL-DUNNING"}
    assert wh.tables[out("run_info")][1][0]["data_source"] == "databricks"
    assert set(wh.functions) == {out(f) for f in ("customer_360", "next_best_actions", "why_blocked", "action_group")}
    for sql in wh.functions.values():  # every tool has a description and only reads the results layer
        assert " COMMENT '" in sql and "maingau_raw" not in sql
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE)\b", sql.split(" RETURN ", 1)[1])


def test_published_rows_match_their_column_types(build_dir):
    columns, rows, _ = lh.result_tables(build_dir)["worklist"]
    kinds = dict(columns)
    assert kinds["customer_id"] == "STRING" and kinds["flags"] == "ARRAY<STRING>" and kinds["urgency_score"] == "DOUBLE"
    for row in lh.conform(rows, columns):
        json.dumps(row, allow_nan=False)
        assert all(isinstance(x, str) for x in row["flags"])


def test_mcp_replies_as_json_or_server_sent_events():
    assert lh._rpc_result('{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}') == {"tools": []}
    sse = 'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"a__customer_360"}]}}\n\n'
    assert lh._rpc_result(sse)["tools"][0]["name"] == "a__customer_360"
    assert lh._rpc_result("") == {}
    with pytest.raises(lh.LakehouseError):
        lh._rpc_result('{"jsonrpc":"2.0","id":3,"error":{"code":-32601,"message":"no"}}')


def test_decision_log_is_a_record_table_that_publish_never_overwrites(build_dir):
    wh = FakeWarehouse()
    lh.publish(wh, SETTINGS, build_dir)
    first = list(wh.tables[SETTINGS.out("decision_log")][1])
    entry = {"ts": "2026-10-02T10:00:00", "actor": "Ben", "action": "rejected", "tuple_id": "P-EN-02|email|sie",
             "reason": "customer upset; it's not the time", "reason_code": "customer_upset"}
    lh.insert_row(wh, SETTINGS, "decision_log", lh.decision_row("MG-100096", entry))
    lh.publish(wh, SETTINGS, build_dir)  # a later build must keep what the API appended
    rows = wh.tables[SETTINGS.out("decision_log")][1]
    assert rows[: len(first)] == first and rows[-1]["customer_id"] == "MG-100096" and rows[-1]["actor"] == "Ben"
    decisions, service = lh.read_records(wh, SETTINGS)  # the nightly job's feedback, in the build's envelope shape
    assert decisions[-1] == {"customer_id": "MG-100096", "entry": entry} and service == []


def test_record_writes_only_when_this_process_reads_databricks(monkeypatch):
    monkeypatch.setattr(lh, "load_settings", lambda *a, **k: lh.Settings(source="local"))
    lh.reset()
    assert lh.record("decision_log", lh.decision_row("MG-100001", {"ts": "t"})) is False
    lh.reset()


def test_spark_backend_returns_text_like_the_sql_api(tmp_path):
    class Frame:
        columns = ["n", "flag", "x", "s", "none"]

        def collect(self):
            return [(3, True, 0.5, "a", None)]

    class Spark:
        def sql(self, statement, args=None):
            self.seen = (statement, args)
            return Frame()

    spark = Spark()
    wh = lh.SparkWarehouse(spark)
    assert wh.query("SELECT 1", {"p0": "v"}) == (Frame.columns, [["3", "true", "0.5", "a", None]])
    assert spark.seen == ("SELECT 1", {"p0": "v"})
    wh.put(str(tmp_path / "sub" / "t-x.jsonl"), b"{}\n")
    assert (tmp_path / "sub" / "t-x.jsonl").read_bytes() == b"{}\n"
