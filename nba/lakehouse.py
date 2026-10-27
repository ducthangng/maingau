"""Databricks as the data source and the place results are published (README §6.18, docs/databricks.md).

Raw layer (`<catalog>.<raw_schema>`), written by `scripts/databricks_sync.py upload` from the local files:
- one table per workbook sheet, every cell as the text pandas reads from the workbook, so nba.data parses
  it exactly as it parses the file and the build output stays byte-identical;
- `events_raw`, one row per line of the event stream;
- `_manifest`, written last: original headers, row counts and the source file's sha256.
A hidden `_row` column keeps the source order.

Results layer (`<catalog>.<out_schema>`), written by `scripts/databricks_sync.py publish` after a build:
- the worklist, every option and block per customer;
- cards and journeys as JSON;
- the decision log and customer memory;
- SQL functions (customer_360, next_best_actions, why_blocked, action_group) that Databricks' managed MCP
  server offers an AI as read-only tools.

The source is config/databricks.yaml `source` (or MAINGAU_DATA_SOURCE): local | databricks. With
databricks, any failure (no SDK, no credentials, warehouse down, a missing or partial table) makes the whole
process use the local files, with a warning, so sources are never mixed. Credentials never live in the repo:
the Databricks SDK reads DATABRICKS_HOST / DATABRICKS_TOKEN (from the shell or the git-ignored .env) or a profile
in ~/.databrickscfg.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import re
import time
import urllib.request
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from nba.data import DEFAULT_EVENTS, DEFAULT_WORKBOOK, REPO, event_lines

log = logging.getLogger(__name__)

CONFIG_PATH = REPO / "config" / "databricks.yaml"
CONTRACT_PATH = REPO / "kg" / "data_contract.yaml"
ROW = "_row"  # source row order
MANIFEST = "_manifest"
EVENTS = "events_raw"
ENV = {
    "source": "MAINGAU_DATA_SOURCE", "profile": "MAINGAU_DATABRICKS_PROFILE",
    "warehouse_id": "MAINGAU_DATABRICKS_WAREHOUSE", "catalog": "MAINGAU_DATABRICKS_CATALOG",
    "raw_schema": "MAINGAU_DATABRICKS_RAW_SCHEMA", "out_schema": "MAINGAU_DATABRICKS_OUT_SCHEMA",
    "volume": "MAINGAU_DATABRICKS_VOLUME",
}
_PLAIN = re.compile(r"[A-Za-z0-9_]+")


class LakehouseError(RuntimeError):
    """Databricks could not serve the request; readers fall back to the local files."""


def q(name: str) -> str:
    """A quoted SQL identifier. Only plain names are allowed, so config values cannot inject SQL."""
    if not isinstance(name, str) or not _PLAIN.fullmatch(name):
        raise LakehouseError(f"not a plain identifier: {name!r}")
    return f"`{name}`"


def lit(text: str) -> str:
    """A SQL string literal (Databricks SQL uses backslash escapes)."""
    return "'" + str(text).replace("\\", "\\\\").replace("'", "\\'") + "'"


def safe_names(labels: Iterable[Any]) -> list[str]:
    """Unique lower-case Delta names for workbook headers or sheet names (the originals go in _manifest)."""
    out: list[str] = []
    for i, label in enumerate(labels, 1):
        name = re.sub(r"[^0-9a-z]+", "_", str(label).lower()).strip("_") or f"col_{i}"
        name = f"c_{name}" if name[0].isdigit() else name
        base, n = name, 2
        while name in out or name == ROW:
            name, n = f"{base}_{n}", n + 1
        out.append(name)
    return out


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Settings:
    source: str = "local"
    profile: str | None = None
    warehouse_id: str | None = None
    catalog: str = "workspace"
    raw_schema: str = "maingau_raw"
    out_schema: str = "maingau_nba"
    volume: str = "landing"
    timeout_s: int = 180

    def table(self, schema: str, name: str) -> str:
        return f"{q(self.catalog)}.{q(schema)}.{q(name)}"

    def raw(self, name: str) -> str:
        return self.table(self.raw_schema, name)

    def out(self, name: str) -> str:
        return self.table(self.out_schema, name)

    @property
    def volume_dir(self) -> str:
        for name in (self.catalog, self.raw_schema, self.volume):
            q(name)
        return f"/Volumes/{self.catalog}/{self.raw_schema}/{self.volume}"


def load_settings(path: str | Path = CONFIG_PATH, env: dict | None = None) -> Settings:
    """config/databricks.yaml, overridden by MAINGAU_DATABRICKS_* variables. Without an explicit `env`, the
    git-ignored .env is loaded first (like the AI steps), so DATABRICKS_HOST / DATABRICKS_TOKEN for the SDK and
    MAINGAU_DATA_SOURCE can live there; a variable already set in the shell wins."""
    if env is None:
        from nba.ai.llm import load_env_file

        load_env_file()
        env = os.environ
    data = (yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}) if Path(path).exists() else {}
    data.update({key: env[var] for key, var in ENV.items() if env.get(var)})
    known = {f.name for f in fields(Settings)}
    s = Settings(**{k: v for k, v in data.items() if k in known})
    if s.source not in ("local", "databricks"):
        raise ValueError(f"config/databricks.yaml source must be local or databricks, not {s.source!r}")
    return s


def workspace_client(s: Settings):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config

    # short HTTP retries: an unreachable workspace should fall back in about a minute, not five
    return WorkspaceClient(config=Config(profile=s.profile, http_timeout_seconds=30, retry_timeout_seconds=60))


class Warehouse:
    """SQL on a Databricks SQL warehouse (Statement Execution API) and file uploads to a volume (Files API)."""

    def __init__(self, s: Settings, client=None):
        self.client = client or workspace_client(s)
        self.timeout_s = int(s.timeout_s)
        self.warehouse_id = s.warehouse_id or self._first_warehouse()

    def _first_warehouse(self) -> str:
        warehouses = sorted(self.client.warehouses.list(), key=lambda w: (w.name or "", w.id))
        if not warehouses:
            raise LakehouseError("this workspace has no SQL warehouse")
        return warehouses[0].id

    def query(self, statement: str, params: dict[str, str | None] | None = None) -> tuple[list[str], list[list[str | None]]]:
        """Column names and rows; every value comes back as text or None (JSON_ARRAY format). `params` fill
        :name markers as STRING values."""
        from databricks.sdk.service.sql import (
            Disposition, ExecuteStatementRequestOnWaitTimeout, Format, StatementParameterListItem, StatementState,
        )

        api = self.client.statement_execution
        parameters = [StatementParameterListItem(name=k, value=v, type="STRING") for k, v in (params or {}).items()]
        resp = api.execute_statement(statement=statement, warehouse_id=self.warehouse_id, wait_timeout="30s",
                                     on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
                                     format=Format.JSON_ARRAY, disposition=Disposition.INLINE,
                                     parameters=parameters or None)
        deadline = time.monotonic() + self.timeout_s
        while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            if time.monotonic() > deadline:
                api.cancel_execution(resp.statement_id)
                raise LakehouseError(f"statement timed out after {self.timeout_s}s: {statement[:80]}")
            time.sleep(1)
            resp = api.get_statement(resp.statement_id)
        if resp.status.state != StatementState.SUCCEEDED:
            error = resp.status.error.message if resp.status.error else resp.status.state
            raise LakehouseError(f"{error} [{statement[:80]}]")
        schema = resp.manifest.schema if resp.manifest else None
        columns = [c.name for c in (schema.columns or [])] if schema else []
        rows, result = [], resp.result
        while result is not None:
            rows += result.data_array or []
            if result.next_chunk_index is None:
                break
            result = api.get_statement_result_chunk_n(resp.statement_id, result.next_chunk_index)
        return columns, rows

    def put(self, path: str, data: bytes) -> None:
        self.client.files.upload(path, io.BytesIO(data), overwrite=True)


def _spark_text(v) -> str | None:
    """A Spark value as the text the Statement Execution API returns."""
    if v is None or isinstance(v, str):
        return v
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


class SparkWarehouse:
    """The same two operations inside a Databricks job: SQL through the job's Spark session (so Unity Catalog
    lineage records the job as the reader of maingau_raw and the writer of maingau_nba), files through /Volumes."""

    warehouse_id = "job compute"

    def __init__(self, spark=None):
        if spark is None:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder.getOrCreate()
        self.spark = spark

    def query(self, statement: str, params: dict[str, str | None] | None = None) -> tuple[list[str], list[list[str | None]]]:
        df = self.spark.sql(statement, args=params) if params else self.spark.sql(statement)
        return list(df.columns), [[_spark_text(v) for v in row] for row in df.collect()]

    def put(self, path: str, data: bytes) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)


def on_databricks_compute() -> bool:
    """True inside a Databricks job or notebook (not in a Databricks App, which has no Spark)."""
    return bool(os.environ.get("DATABRICKS_RUNTIME_VERSION"))


def connect(s: Settings):
    """Spark inside a Databricks job, the SQL warehouse anywhere else (laptop, API, Databricks App)."""
    return SparkWarehouse() if on_databricks_compute() else Warehouse(s)


def write_table(wh, s: Settings, schema: str, table: str, columns: list[tuple[str, str]], rows: list[dict],
                comment: str) -> int:
    """(Re)create schema.table from rows via a JSON-lines file in the landing volume; returns the row count."""
    target = s.table(schema, table)
    spec = ", ".join(f"{q(c)} {t}" for c, t in columns)
    if not rows:
        wh.query(f"CREATE OR REPLACE TABLE {target} ({spec}) COMMENT {lit(comment)}")
        return 0
    # both names checked by s.table() above; "t-" because Spark skips files starting with "_" (e.g. _manifest)
    path = f"{s.volume_dir}/{schema}/t-{table}.jsonl"
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for r in rows)
    wh.put(path, body.encode("utf-8"))
    wh.query(f"CREATE OR REPLACE TABLE {target} COMMENT {lit(comment)} AS SELECT {', '.join(q(c) for c, _ in columns)} "
             f"FROM read_files({lit(path)}, format => 'json', schema => {lit(spec)})")
    return len(rows)


# --- raw layer -------------------------------------------------------------------------------------------

MANIFEST_COLUMNS = [
    ("position", "BIGINT"), ("kind", "STRING"), ("sheet", "STRING"), ("table_name", "STRING"),
    ("columns_json", "STRING"), ("delta_columns_json", "STRING"), ("n_rows", "BIGINT"),
    ("source_file", "STRING"), ("source_sha256", "STRING"), ("uploaded_at", "STRING"),
]


def upload_raw(wh, s: Settings, workbook: str | Path = DEFAULT_WORKBOOK, events: str | Path = DEFAULT_EVENTS) -> list[dict]:
    """Copy the workbook and the event stream into the raw layer; returns the manifest rows."""
    workbook, events = Path(workbook), Path(events)
    wh.query(f"CREATE SCHEMA IF NOT EXISTS {q(s.catalog)}.{q(s.raw_schema)}")
    wh.query(f"CREATE VOLUME IF NOT EXISTS {s.raw(s.volume)}")
    wh.query(f"DROP TABLE IF EXISTS {s.raw(MANIFEST)}")  # no manifest = no complete upload, until the end
    for path in (workbook, events):  # the original files as they landed
        wh.put(f"{s.volume_dir}/files/{path.name}", path.read_bytes())
    uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sheets = pd.read_excel(workbook, sheet_name=None, dtype=str)
    sha = file_sha256(workbook)
    manifest = []
    for position, ((sheet, df), table) in enumerate(zip(sheets.items(), safe_names(sheets))):
        cols = safe_names(df.columns)
        rows = [{ROW: i, **{c: None if pd.isna(v) else v for c, v in zip(cols, record)}}
                for i, record in enumerate(df.itertuples(index=False, name=None))]
        n = write_table(wh, s, s.raw_schema, table, [(ROW, "BIGINT")] + [(c, "STRING") for c in cols], rows,
                        f"Sheet {sheet} of {workbook.name}; every cell as text (scripts/databricks_sync.py)")
        manifest.append({"position": position, "kind": "sheet", "sheet": sheet, "table_name": table,
                         "columns_json": json.dumps([str(c) for c in df.columns], ensure_ascii=False),
                         "delta_columns_json": json.dumps(cols), "n_rows": n, "source_file": workbook.name,
                         "source_sha256": sha, "uploaded_at": uploaded_at})
    lines = event_lines(events)
    n = write_table(wh, s, s.raw_schema, EVENTS, [(ROW, "BIGINT"), ("line", "STRING")],
                    [{ROW: i, "line": line} for i, line in enumerate(lines, 1)],
                    f"{events.name}, one row per line as received (scripts/databricks_sync.py)")
    manifest.append({"position": len(sheets), "kind": "events", "sheet": None, "table_name": EVENTS,
                     "columns_json": '["line"]', "delta_columns_json": '["line"]', "n_rows": n,
                     "source_file": events.name, "source_sha256": file_sha256(events), "uploaded_at": uploaded_at})
    write_table(wh, s, s.raw_schema, MANIFEST, MANIFEST_COLUMNS, manifest,
                "What scripts/databricks_sync.py upload wrote; written last, so it marks a complete upload")
    return manifest


@dataclass
class RawData:
    sheets: dict[str, pd.DataFrame]  # every sheet as text, like pd.read_excel(dtype=str)
    event_lines: list[str]
    manifest: list[dict]
    detail: str
    parsed: dict | None = None  # nba.data's typed tables, filled once per process


def read_manifest(wh, s: Settings) -> list[dict]:
    names = [c for c, _ in MANIFEST_COLUMNS]
    _, rows = wh.query(f"SELECT {', '.join(map(q, names))} FROM {s.raw(MANIFEST)} ORDER BY {q('position')}")
    return [dict(zip(names, r)) for r in rows]


def contract_sheets(path: str | Path = CONTRACT_PATH) -> list[str]:
    return list(yaml.safe_load(Path(path).read_text(encoding="utf-8"))["sheets"])


def read_raw(wh, s: Settings) -> RawData:
    """The raw layer as text. Raises LakehouseError if it is missing, partial or incomplete."""
    try:
        manifest = read_manifest(wh, s)
    except LakehouseError as exc:
        raise LakehouseError(f"no complete raw layer in {s.catalog}.{s.raw_schema}; run scripts/databricks_sync.py "
                             f"upload ({exc})") from exc
    missing = sorted(set(contract_sheets()) - {m["sheet"] for m in manifest if m["kind"] == "sheet"})
    if missing:
        raise LakehouseError(f"the raw layer lacks sheets the data contract needs: {', '.join(missing)}")
    if not any(m["kind"] == "events" for m in manifest):
        raise LakehouseError(f"the raw layer has no {EVENTS} table")
    sheets, lines = {}, []
    for m in manifest:
        delta = json.loads(m["delta_columns_json"])
        _, rows = wh.query(f"SELECT {', '.join(map(q, delta))} FROM {s.raw(m['table_name'])} ORDER BY {q(ROW)}")
        if len(rows) != int(m["n_rows"]):
            raise LakehouseError(f"{m['table_name']} has {len(rows)} rows, the manifest says {m['n_rows']}")
        if m["kind"] == "events":
            lines = [r[0] or "" for r in rows]
        else:
            sheets[m["sheet"]] = pd.DataFrame(rows, columns=json.loads(m["columns_json"]), dtype=str)
    first = manifest[0]
    detail = (f"{s.catalog}.{s.raw_schema} via warehouse {getattr(wh, 'warehouse_id', '?')}; uploaded "
              f"{first['uploaded_at']} from {first['source_file']} sha256 {first['source_sha256'][:12]}")
    if DEFAULT_WORKBOOK.exists() and file_sha256(DEFAULT_WORKBOOK) != first["source_sha256"]:
        detail += "; differs from the local workbook"
    return RawData(sheets, lines, manifest, detail)


# --- which source this process uses ------------------------------------------------------------------------

_state: dict[str, Any] = {}


def _resolve() -> tuple[RawData | None, dict]:
    try:
        s = load_settings()
    except Exception as exc:
        log.warning("config/databricks.yaml unreadable, using the local files: %s", exc)
        return None, {"source": "local", "detail": f"config error: {exc}"}
    if s.source == "local":
        return None, {"source": "local", "detail": "config/databricks.yaml source: local"}
    try:
        wh = connect(s)
        _state["wh"], _state["settings"] = wh, s
        return (raw := read_raw(wh, s)), {"source": "databricks", "detail": raw.detail}
    except Exception as exc:  # anything at all (missing SDK, auth, network, tables): the local files are the backup
        reason = " ".join(str(exc).split())[:300] or type(exc).__name__
        log.warning("Databricks source unavailable, using the local files instead: %s", reason)
        return None, {"source": "local", "detail": f"fallback, Databricks unavailable: {reason}"}


def remote_raw() -> RawData | None:
    """The Databricks raw layer when config selects it and it can be read, else None (use the local files).
    Decided once per process."""
    if "raw" not in _state:
        _state["raw"], _state["status"] = _resolve()
    return _state["raw"]


def connection():
    """(warehouse, settings) this process reads Databricks with; only after remote_raw() succeeded."""
    if remote_raw() is None:
        raise LakehouseError(f"not connected to Databricks: {status()['detail']}")
    return _state["wh"], _state["settings"]


def status() -> dict:
    """{"source": "databricks" | "local", "detail": ...} for this process."""
    remote_raw()
    return dict(_state["status"])


def status_line() -> str:
    st = status()
    return f"{st['source']} ({st['detail']})"


def reset() -> None:
    _state.clear()


# --- results layer -----------------------------------------------------------------------------------------

OPTION_COLUMNS = [
    ("customer_id", "STRING"), ("rank", "BIGINT"), ("chosen", "BOOLEAN"), ("tuple_id", "STRING"),
    ("offer_id", "STRING"), ("offer_name", "STRING"), ("action_type", "STRING"), ("channel", "STRING"),
    ("tone", "STRING"), ("origin", "STRING"), ("personalised", "BOOLEAN"), ("need", "STRING"),
    ("signals", "ARRAY<STRING>"), ("delta_clv", "DOUBLE"), ("p_accept", "DOUBLE"), ("confidence", "STRING"),
    ("contact_cost", "DOUBLE"), ("clv_now_eur", "DOUBLE"), ("deferred_until", "STRING"),
    ("why", "ARRAY<STRING>"), ("notes", "ARRAY<STRING>"),
]
BLOCKED_COLUMNS = [
    ("customer_id", "STRING"), ("offer_id", "STRING"), ("channel", "STRING"), ("rule_id", "STRING"),
    ("rule_center_id", "STRING"), ("reason", "STRING"), ("until", "STRING"), ("counterfactual_delta_clv", "DOUBLE"),
]
CARD_COLUMNS = [("customer_id", "STRING"), ("eval_time", "STRING"), ("chosen_tuple", "STRING"), ("status", "STRING"),
                ("state_revision", "STRING"), ("card_json", "STRING")]
JOURNEY_COLUMNS = [("customer_id", "STRING"), ("journey_json", "STRING")]
DECISION_COLUMNS = [
    ("customer_id", "STRING"), ("ts", "STRING"), ("actor", "STRING"), ("action", "STRING"), ("tuple_id", "STRING"),
    ("from_tuple", "STRING"), ("to_tuple", "STRING"), ("reason", "STRING"), ("reason_code", "STRING"),
    ("entry_json", "STRING"),
]
MEMORY_COLUMNS = [("customer_id", "STRING"), ("entry_json", "STRING")]
SERVICE_FEEDBACK_COLUMNS = [("customer_id", "STRING"), ("feedback_id", "STRING"), ("shown_at", "STRING"),
                            ("agent_action", "STRING"), ("suggested_offer_id", "STRING"), ("row_json", "STRING")]
LEARN_IMPACT_COLUMNS = [("eval_time", "STRING"), ("learn_impact_json", "STRING")]
# Written by people through the API and read back by the nightly job: publish never replaces them.
RECORD_TABLES = {"decision_log": DECISION_COLUMNS, "service_feedback": SERVICE_FEEDBACK_COLUMNS}
RUN_COLUMNS = [("eval_time", "STRING"), ("n_customers", "BIGINT"), ("data_source", "STRING"),
               ("data_source_detail", "STRING"), ("published_at", "STRING"), ("versions_json", "STRING")]


def infer_columns(rows: list[dict], first: tuple[str, ...] = ("customer_id",)) -> list[tuple[str, str]]:
    kinds: dict[str, set[str]] = {}
    for row in rows:
        for key, v in row.items():
            seen = kinds.setdefault(key, set())
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            seen.add("BOOLEAN" if isinstance(v, bool) else "BIGINT" if isinstance(v, int)
                     else "DOUBLE" if isinstance(v, float) else "ARRAY<STRING>" if isinstance(v, list) else "STRING")
    def sql_type(seen):
        if seen and seen <= {"BIGINT", "DOUBLE"}:
            return "DOUBLE" if "DOUBLE" in seen else "BIGINT"
        return next(iter(seen)) if len(seen) == 1 else "STRING"
    order = [k for k in first if k in kinds] + sorted(k for k in kinds if k not in first)
    return [(k, sql_type(kinds[k])) for k in order]


def _text(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)


def conform(rows: list[dict], columns: list[tuple[str, str]]) -> list[dict]:
    """Values shaped like their column type: anything structured in a STRING column as JSON text."""
    out = []
    for row in rows:
        shaped = {}
        for col, kind in columns:
            v = row.get(col)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                v = None
            elif kind == "ARRAY<STRING>":
                v = [_text(x) for x in v]
            elif kind == "STRING":
                v = _text(v)
            shaped[col] = v
        out.append(shaped)
    return out


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def result_tables(out_dir: str | Path) -> dict[str, tuple[list[tuple[str, str]], list[dict], str]]:
    """The build output in out_dir as {table: (columns, rows, comment)}."""
    out = Path(out_dir)
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    options, blocked, cards = [], [], []
    for path in sorted((out / "customers").glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        cid, chosen, meta = card["customer_id"], card["chosen"], card["meta"]
        cards.append({"customer_id": cid, "eval_time": meta.get("eval_time"), "chosen_tuple": chosen["tuple_id"],
                      "status": chosen.get("status"), "state_revision": meta.get("state_revision"),
                      "card_json": json.dumps(card, ensure_ascii=False, sort_keys=True)})
        for c in card.get("candidates", []):
            v = c.get("valuation") or {}
            options.append({"customer_id": cid, "chosen": c["tuple_id"] == chosen["tuple_id"],
                            "clv_now_eur": v.get("clv_now_shown"),
                            **{k: c.get(k) for k in ("rank", "tuple_id", "offer_id", "offer_name", "action_type",
                                                     "channel", "tone", "origin", "personalised", "need",
                                                     "signals", "deferred_until", "why", "notes")},
                            **{k: v.get(k) for k in ("delta_clv", "p_accept", "confidence", "contact_cost")}})
        blocked += [{"customer_id": cid, **{k: b.get(k) for k, _ in BLOCKED_COLUMNS[1:]}} for b in card.get("blocked", [])]
    journeys = [{"customer_id": p.stem, "journey_json": p.read_text(encoding="utf-8").strip()}
                for p in sorted((out / "journey").glob("*.json"))]
    decisions = [{"customer_id": r["customer_id"], "entry_json": _text(r["entry"]),
                  **{k: r["entry"].get(k) for k, _ in DECISION_COLUMNS[1:-1]}} for r in _jsonl(out / "decision_log.jsonl")]
    memory = [{"customer_id": r.get("customer_id"), "entry_json": _text(r)} for r in _jsonl(out / "customer_memory.jsonl")]
    service = [service_feedback_row(r) for r in _jsonl(out / "service_feedback.jsonl")]
    impact_path = out / "learn_impact.json"
    impact = json.loads(impact_path.read_text(encoding="utf-8")) if impact_path.exists() else None
    source = json.loads((out / "data_source.json").read_text(encoding="utf-8")) if (out / "data_source.json").exists() else {}
    first = json.loads(cards[0]["card_json"]) if cards else {"meta": {}}
    run = [{"eval_time": first["meta"].get("eval_time"), "n_customers": len(cards),
            "data_source": source.get("source"), "data_source_detail": source.get("detail"),
            "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "versions_json": _text(first["meta"].get("versions", {}))}]
    worklist = infer_columns(index)
    return {
        "worklist": (worklist, index, "One row per customer: triage, chosen action, ΔCLV, flags (index.json)"),
        "nba_options": (OPTION_COLUMNS, options, "Every allowed, valued action per customer; chosen = the proposal"),
        "nba_blocked": (BLOCKED_COLUMNS, blocked, "Every action a hard rule or business rule blocked, with the reason"),
        "customer_cards": (CARD_COLUMNS, cards, "The full Customer Profile + Next Best Action card per customer (JSON)"),
        "customer_journey": (JOURNEY_COLUMNS, journeys, "The Customer 360 journey per customer (JSON)"),
        "decision_log": (DECISION_COLUMNS, decisions, "Approvals, overrides and rejections (append-only log of the API)"),
        "customer_memory": (MEMORY_COLUMNS, memory, "What people said no to, per customer (nba.ai feedback)"),
        "service_feedback": (SERVICE_FEEDBACK_COLUMNS, service, "Service agents' reactions to suggested offers (Customer 360)"),
        "learn_impact": (LEARN_IMPACT_COLUMNS,
                         [{"eval_time": first["meta"].get("eval_time"), "learn_impact_json": _text(impact)}] if impact is not None else [],
                         "What the feedback loop learned and which decisions it changed"),
        "run_info": (RUN_COLUMNS, run, "The build these tables come from"),
    }


# Column descriptions for people and for Genie (re-applied on every publish, because each run recreates the tables).
_OFFER = "offer ID, e.g. P-EN-03 (names in maingau_raw.product_catalog)"
COLUMN_COMMENTS = {
    "worklist": {
        "customer_id": "MAINGAU customer ID, e.g. MG-100068",
        "archetype": "segment A0-A5: A0 other, A1 smart eco-system adopter, A2 traditional energy loyalist, A3 EV driver, "
                     "A4 retention risk (do no harm), A5 growing connected household",
        "urgency_tier": "P1 most urgent ... P5 least urgent; sort by tier, then urgency_score descending",
        "urgency_score": "higher = more urgent within a tier",
        "top_reason": "the main reason this customer is on the worklist, with the signal or rule ID in brackets",
        "chosen_offer": f"proposed {_OFFER}; NO_ACTION = do not contact",
        "chosen_tuple": "proposed action as offer|channel|tone, e.g. P-EN-02|newsletter_email|sie",
        "channel": "channel of the proposed action: outbound_call (phone), sms, email, newsletter_email, app_push, "
                   "portal_popup, service_agent (handled by a service agent)",
        "tone": "du (informal) or sie (formal)",
        "delta_clv": "expected change of customer lifetime value in EUR if the action is sent, after contact cost",
        "p_accept": "probability that the customer accepts the offer, 0 to 1",
        "contact_cost": "cost of the contact in EUR",
        "clv_eur": "customer lifetime value today in EUR",
        "churn": "probability that the customer leaves within 12 months, 0 to 1",
        "flags": "warnings such as service_critical, negative_clv, contact_fatigue, top_clv",
        "outlier": "true if a flag marks a special case that needs a second look",
        "exclusions": "active exclusions that block every sales offer (dunning, cancellation, open ticket, ...)",
        "deferred_until": "set when the action has to wait (contact cap or a business rule) until this time",
    },
    "nba_options": {
        "rank": "1 = best allowed action for this customer, by expected delta_clv",
        "chosen": "true for the action proposed to the marketer",
        "offer_id": _OFFER,
        "delta_clv": "expected change of customer lifetime value in EUR, after contact cost",
        "p_accept": "probability that the customer accepts, 0 to 1",
        "why": "plain-language reasons this action fits",
        "notes": "caveats: low confidence, assumptions, data quality",
    },
    "nba_blocked": {
        "offer_id": _OFFER,
        "rule_id": "why it is blocked: CONSENT-CHANNEL / CONSENT-PROFILING missing consent, EXCL-* exclusion "
                   "(dunning, open ticket, cancellation), CONTACT-CAP too many contacts, HOLDING-PRECONDITION already "
                   "owns it or lacks a prerequisite, CHANNEL-AVAILABLE no address/app, ECON-NONPOSITIVE not worth it, "
                   "BUSINESS-RULE a Rule Center limit, DATA-MISSING not enough data",
        "reason": "the blocking reason in plain language",
    },
    "decision_log": {
        "action": "approved, overridden or rejected by a person",
        "actor": "who decided",
        "reason_code": "coded reason for a rejection or override (feeds the customer memory)",
    },
}


def _function(s: Settings, name: str, params: list[tuple[str, str, str]], returns: list[tuple[str, str]],
              comment: str, body: str) -> str:
    args = ", ".join(f"{q(p)} {t} COMMENT {lit(c)}" for p, t, c in params)
    spec = ", ".join(f"{q(c)} {t}" for c, t in returns)
    return (f"CREATE OR REPLACE FUNCTION {s.out(name)}({args}) RETURNS TABLE ({spec}) "
            f"COMMENT {lit(comment)} RETURN {body}")


def mcp_functions(s: Settings, worklist: list[tuple[str, str]]) -> dict[str, str]:
    """Read-only SQL functions over the results layer; the managed MCP server lists each one as a tool."""
    cid = [("customer_id", "STRING", "MAINGAU customer ID, e.g. MG-100068")]
    options = OPTION_COLUMNS[1:]
    blocked = BLOCKED_COLUMNS[1:]
    group = [c for c in worklist if c[0] in ("customer_id", "urgency_tier", "urgency_score", "archetype", "delta_clv",
                                             "p_accept", "confidence", "flags", "outlier", "checklist_failed")]
    cols = lambda spec: ", ".join(q(c) for c, _ in spec)  # noqa: E731
    return {
        "customer_360": _function(
            s, "customer_360", cid, worklist,
            "Customer 360 summary for one customer: archetype, urgency tier and reason, CLV, churn, flags, the "
            "proposed next best action with expected ΔCLV (EUR) and p_accept. Read-only; no payment data.",
            f"SELECT {cols(worklist)} FROM {s.out('worklist')} w WHERE w.customer_id = customer_360.customer_id"),
        "next_best_actions": _function(
            s, "next_best_actions", cid, options,
            "Every action that passed the hard rules for one customer, ranked by expected ΔCLV (EUR), with the "
            "signals and need behind it and the reasons it fits. chosen = the proposal a person approves.",
            f"SELECT {cols(options)} FROM {s.out('nba_options')} o WHERE o.customer_id = next_best_actions.customer_id "
            f"ORDER BY o.`chosen` DESC, o.`rank`"),
        "why_blocked": _function(
            s, "why_blocked", cid, blocked,
            "Actions blocked for one customer and why: rule ID (consent, exclusion, contact cap, business rule) "
            "and a plain-language reason. Hard rules are never overridden.",
            f"SELECT {cols(blocked)} FROM {s.out('nba_blocked')} b WHERE b.customer_id = why_blocked.customer_id"),
        "action_group": _function(
            s, "action_group", [("tuple_id", "STRING", "An action as offer|channel|tone, e.g. P-EN-02|email|sie")], group,
            "Customers whose proposed action is this offer|channel|tone tuple: the group a marketer approves in "
            "one batch, most urgent first, with flags that need a second look.",
            f"SELECT {cols(group)} FROM {s.out('worklist')} w WHERE w.chosen_tuple = action_group.tuple_id "
            f"ORDER BY w.`urgency_tier`, w.`urgency_score` DESC"),
    }


def publish(wh, s: Settings, out_dir: str | Path) -> dict[str, int]:
    """Write the build output in out_dir to the results layer and (re)create the MCP functions."""
    wh.query(f"CREATE SCHEMA IF NOT EXISTS {q(s.catalog)}.{q(s.out_schema)} "
             f"COMMENT {lit('MAINGAU Next Best Action results (scripts/databricks_sync.py publish)')}")
    wh.query(f"CREATE VOLUME IF NOT EXISTS {s.raw(s.volume)}")
    counts = {}
    tables = result_tables(out_dir)
    for table, (columns, rows, comment) in tables.items():
        if table in RECORD_TABLES and table_exists(wh, s, table):
            continue  # the API appends to it and the nightly job reads it back: never overwritten by a build
        counts[table] = write_table(wh, s, s.out_schema, table, columns, conform(rows, columns), comment)
        names = {c for c, _ in columns}
        for col, text in COLUMN_COMMENTS.get(table, {}).items():
            if col in names:
                wh.query(f"ALTER TABLE {s.out(table)} ALTER COLUMN {q(col)} COMMENT {lit(text)}")
    for sql in mcp_functions(s, tables["worklist"][0]).values():
        wh.query(sql)
    return counts


def table_exists(wh, s: Settings, table: str) -> bool:
    _, rows = wh.query(f"SHOW TABLES IN {q(s.catalog)}.{q(s.out_schema)} LIKE {lit(table)}")
    return bool(rows)


def decision_row(customer_id: str, entry: dict) -> dict:
    return {"customer_id": customer_id, "entry_json": _text(entry), **{k: entry.get(k) for k, _ in DECISION_COLUMNS[1:-1]}}


def service_feedback_row(row: dict) -> dict:
    return {"row_json": _text(row), **{k: row.get(k) for k, _ in SERVICE_FEEDBACK_COLUMNS[:-1]}}


def insert_row(wh, s: Settings, table: str, row: dict) -> None:
    """Append one row to a record table (created if missing); values travel as parameters, never as SQL text."""
    columns = RECORD_TABLES[table]
    spec = ", ".join(f"{q(c)} {t}" for c, t in columns)
    wh.query(f"CREATE TABLE IF NOT EXISTS {s.out(table)} ({spec})")
    shaped = conform([row], columns)[0]
    params = {f"p{i}": shaped[c] for i, (c, _) in enumerate(columns)}
    wh.query(f"INSERT INTO {s.out(table)} ({', '.join(q(c) for c, _ in columns)}) "
             f"VALUES ({', '.join(':' + k for k in params)})", params)


_writer = None


def record(table: str, row: dict) -> bool:
    """Append a row to decision_log / service_feedback in Databricks, in the background and in order, when this
    process reads its data from Databricks. Returns whether it was queued; a failure is logged, never raised
    (the local JSONL log stays the API's own record)."""
    global _writer
    if status()["source"] != "databricks":
        return False
    if _writer is None:
        from concurrent.futures import ThreadPoolExecutor

        _writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lakehouse-writer")

    def write():
        try:
            insert_row(_state["wh"], _state["settings"], table, row)
        except Exception as exc:  # the decision is already in the local log
            log.warning("could not write to %s in Databricks: %s", table, " ".join(str(exc).split())[:200])

    _writer.submit(write)
    return True


def read_records(wh, s: Settings) -> tuple[list[dict], list[dict]]:
    """decision_log as {customer_id, entry} envelopes and service_feedback rows, as the feedback step reads them."""
    found = {t: table_exists(wh, s, t) for t in RECORD_TABLES}
    decisions, service = [], []
    if found["decision_log"]:
        _, rows = wh.query(f"SELECT `customer_id`, `entry_json` FROM {s.out('decision_log')} ORDER BY `ts`")
        decisions = [{"customer_id": cid, "entry": json.loads(entry)} for cid, entry in rows if cid and entry]
    if found["service_feedback"]:
        _, rows = wh.query(f"SELECT `row_json` FROM {s.out('service_feedback')} ORDER BY `shown_at`")
        service = [json.loads(r[0]) for r in rows if r[0]]
    return decisions, service


# --- managed MCP ---------------------------------------------------------------------------------------------

def _rpc_result(text: str) -> dict:
    """The JSON-RPC result from a JSON or a server-sent-events reply."""
    if not text.strip():
        return {}
    payloads = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")] or [text]
    for payload in payloads:
        msg = json.loads(payload)
        if "error" in msg:
            raise LakehouseError(f"MCP error: {msg['error']}")
        if "result" in msg:
            return msg["result"]
    return {}


class MCPClient:
    """Databricks managed MCP server for the results layer's UC functions (Streamable HTTP, JSON-RPC)."""

    def __init__(self, s: Settings, client=None):
        self.client = client or workspace_client(s)
        self.url = f"{self.client.config.host.rstrip('/')}/api/2.0/mcp/functions/{s.catalog}/{s.out_schema}"
        self.session, self.next_id = None, 1
        self._call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "maingau-nba", "version": "0.1"}})
        self._call("notifications/initialized", None)

    def _call(self, method: str, params: dict | None) -> dict:
        body = {"jsonrpc": "2.0", "method": method}
        if not method.startswith("notifications/"):
            body["id"], self.next_id = self.next_id, self.next_id + 1
        if params is not None:
            body["params"] = params
        headers = {**self.client.config.authenticate(), "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.session = resp.headers.get("Mcp-Session-Id") or self.session
            return _rpc_result(resp.read().decode("utf-8"))

    def tools(self) -> list[dict]:
        return self._call("tools/list", {}).get("tools", [])

    def call(self, name: str, arguments: dict) -> dict:
        return self._call("tools/call", {"name": name, "arguments": arguments})
