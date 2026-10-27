"""Validate a workbook against kg/data_contract.yaml before the pipeline uses it (README §6.15). Owner: Agent KG.

The checks target the failure that hurts most: a value the rules do not know (a new status, consent
type, churn-driver label, an empty rule cell, unreadable boolean or non-ISO date) that would otherwise
be ignored silently. ERROR = stop; WARNING = report. A missing sheet or column is reported, never a crash.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from nba.data import BOOL_COLUMNS, DEFAULT_WORKBOOK, _is_date_column, load_workbook, read_raw_sheets
from nba.state import resolve_eval_time

REPO = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO / "kg" / "data_contract.yaml"
CONFIG_PATH = REPO / "config" / "kg.yaml"
IGNORED_COLUMNS = {"is_guest"}  # added by nba.data, not in the source
FREE_TEXT_SHEETS = {"README", "columns", "clv_method"}


@dataclass(frozen=True)
class Issue:
    level: str  # ERROR | WARNING
    code: str
    where: str  # "sheet" or "sheet.column"
    detail: str
    count: int = 0
    examples: tuple = field(default_factory=tuple)


def load_contract(path: str | Path = CONTRACT_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _examples(values, n=3) -> tuple:
    return tuple(str(v) for v in list(dict.fromkeys(values))[:n])


def _split(ref: str) -> tuple[str, str]:
    sheet, col = ref.split(".", 1)
    return sheet, col


def _required_columns(c: dict) -> set[tuple[str, str]]:
    """Columns the rules need, whatever the workbook's own `columns` sheet says."""
    req = {(s, k) for s, keys in c["primary_keys"].items() for k in keys}
    req |= {(s, "customer_id") for s in c["foreign_keys"]["customer_sheets"]}
    for key in ("enums_error", "ranges"):
        req |= {_split(ref) for ref in (c.get(key) or {})}
    req |= {("customer_value", "churn_drivers"), ("customer_value", "clv_calc_date")}
    return req


def validate_tables(tables: dict[str, pd.DataFrame], contract: dict | None = None,
                    raw: dict[str, pd.DataFrame] | None = None, eval_time: datetime | None = None) -> list[Issue]:
    c = contract or load_contract()
    out: list[Issue] = []

    def has(sheet: str, col: str | None = None) -> bool:
        return sheet in tables and (col is None or col in tables[sheet].columns)

    # 1. sheets and columns
    for sheet in c["sheets"]:
        if sheet not in tables:
            out.append(Issue("ERROR", "MISSING_SHEET", sheet, "sheet missing"))
    for sheet in sorted(set(tables) - set(c["sheets"])):
        out.append(Issue("WARNING", "EXTRA_SHEET", sheet, "sheet not in the data contract"))
    missing: set[tuple[str, str]] = {(s, col) for s, col in _required_columns(c) if s in tables and col not in tables[s].columns}
    declared: dict[str, set[str]] = {}
    if has("columns", "sheet") and has("columns", "column"):
        for r in tables["columns"].to_dict("records"):
            declared.setdefault(r["sheet"], set()).add(r["column"])
        for sheet, cols in declared.items():
            if sheet in tables:
                missing |= {(sheet, col) for col in cols - set(tables[sheet].columns)}
                extra = sorted(set(tables[sheet].columns) - IGNORED_COLUMNS - cols)
                if extra:
                    out.append(Issue("WARNING", "UNDOCUMENTED_COLUMNS", sheet,
                                     f"not described in `columns`: {', '.join(extra)}", len(extra), tuple(extra)))
    for sheet, col in sorted(missing):
        out.append(Issue("ERROR", "MISSING_COLUMN", f"{sheet}.{col}", "required column is missing"))

    # 2. primary keys (order_id is required on guest shop rows too)
    for sheet, keys in c["primary_keys"].items():
        if not all(has(sheet, k) for k in keys):
            continue
        sub = tables[sheet][keys]
        null = sub.isna().any(axis=1)
        if null.any():
            out.append(Issue("ERROR", "NULL_KEY", sheet, f"null in key {keys}", int(null.sum())))
        dup = sub[~null].duplicated(keep=False)
        if dup.any():
            rows = sub[~null][dup].astype(str).agg("|".join, axis=1)
            out.append(Issue("ERROR", "DUPLICATE_KEY", sheet, f"duplicate key {keys}", int(dup.sum()), _examples(rows)))

    # 3. foreign keys to customer_master
    known = set(tables["customer_master"]["customer_id"]) if has("customer_master", "customer_id") else set()
    for sheet in c["foreign_keys"]["customer_sheets"]:
        if not has(sheet, "customer_id"):
            continue
        ids = tables[sheet]["customer_id"]
        nulls = ids.isna()
        if nulls.any() and sheet not in c["foreign_keys"]["nullable"]:
            out.append(Issue("ERROR", "NULL_CUSTOMER", sheet, "customer_id missing", int(nulls.sum())))
        unknown = [v for v in ids[~nulls] if v not in known]
        if unknown:
            out.append(Issue("ERROR", "UNKNOWN_CUSTOMER", sheet, "customer_id not in customer_master",
                             len(unknown), _examples(unknown)))

    # 4. enums: unknown values; empty cells in rule columns unless nullable
    nullable = set(c.get("nullable") or [])
    for level, key in (("ERROR", "enums_error"), ("WARNING", "enums_warning")):
        for ref, allowed in (c.get(key) or {}).items():
            sheet, col = _split(ref)
            if not has(sheet, col):
                continue
            values = tables[sheet][col]
            allowed_s = {str(a) for a in allowed}
            bad = [v for v in values if v is not None and str(v) not in allowed_s]
            if bad:
                counts = Counter(str(v) for v in bad)
                out.append(Issue(level, "UNKNOWN_VALUE", ref, f"values not in the contract: {dict(counts)}",
                                 len(bad), tuple(counts)))
            empty = int(values.isna().sum())
            if level == "ERROR" and empty and ref not in nullable:
                out.append(Issue("ERROR", "NULL_VALUE", ref, "empty cell in a rule column", empty))

    # 5. churn-driver labels (the churn model removes drivers by label)
    pats = [re.compile(p) for p in c.get("churn_driver_patterns") or []]
    if has("customer_value", "churn_drivers") and pats:
        labels = [t.strip() for v in tables["customer_value"]["churn_drivers"] if isinstance(v, str)
                  for t in v.split(";") if t.strip()]
        bad = [t for t in labels if not any(p.match(t) for p in pats)]
        if bad:
            out.append(Issue("ERROR", "UNKNOWN_CHURN_DRIVER", "customer_value.churn_drivers",
                             f"unknown labels: {dict(Counter(bad))}", len(bad), _examples(bad)))

    # 6. numeric ranges
    for ref, (lo, hi) in (c.get("ranges") or {}).items():
        sheet, col = _split(ref)
        if not has(sheet, col):
            continue
        vals = [v for v in tables[sheet][col] if v is not None]
        not_num = [v for v in vals if not isinstance(v, (int, float)) or isinstance(v, bool)]
        out_of = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool) and not lo <= v <= hi]
        if not_num:
            out.append(Issue("ERROR", "NOT_A_NUMBER", ref, "non-numeric values", len(not_num), _examples(not_num)))
        if out_of:
            out.append(Issue("ERROR", "OUT_OF_RANGE", ref, f"outside [{lo}, {hi}]", len(out_of), _examples(out_of)))

    # 7. raw text checks: ISO dates, readable booleans (needs the raw sheets)
    extra_dates = {_split(ref) for ref in (c.get("extra_dates") or [])}
    if raw is not None:
        for sheet, rdf in raw.items():
            if sheet in FREE_TEXT_SHEETS or sheet not in tables:
                continue
            for col in rdf.columns:
                texts = [str(v).strip() for v in rdf[col] if isinstance(v, str) and v.strip()]
                if _is_date_column(col) or (sheet, col) in extra_dates:
                    non_iso = []
                    for v in texts:
                        try:
                            datetime.fromisoformat(v)
                        except ValueError:
                            non_iso.append(v)
                    if non_iso:
                        out.append(Issue("ERROR", "NON_ISO_DATE", f"{sheet}.{col}",
                                         "date text is not ISO 8601 (could be misread or dropped)", len(non_iso), _examples(non_iso)))
                elif col in BOOL_COLUMNS:
                    unreadable = [v for v in texts if v.lower() not in {"1", "0", "1.0", "0.0", "true", "false", "yes", "no", "y", "n"}]
                    if unreadable:
                        out.append(Issue("ERROR", "UNPARSEABLE_BOOL", f"{sheet}.{col}", "boolean text not understood",
                                         len(unreadable), _examples(unreadable)))

    # 8. timestamps after the evaluation time (snapshot consistency; README §3)
    try:
        t = eval_time or resolve_eval_time(tables, "auto")
    except (KeyError, ValueError) as exc:
        out.append(Issue("ERROR", "NO_EVAL_TIME", "customer_value.clv_calc_date", f"cannot resolve eval_time: {exc}"))
        return out
    for sheet, df in tables.items():
        for col in df.columns:
            if not _is_date_column(col) or col in ("price_guarantee_until",):
                continue  # future contract dates are expected
            later = [v for v in df[col] if isinstance(v, datetime) and v > t]
            if later:
                out.append(Issue("WARNING", "AFTER_EVAL_TIME", f"{sheet}.{col}", f"timestamps after eval_time {t:%Y-%m-%d %H:%M:%S}",
                                 len(later), _examples(sorted(later)[:3])))
    return out


def configured_eval_time(tables: dict[str, pd.DataFrame], config_path: str | Path = CONFIG_PATH) -> datetime:
    """eval_time exactly as the pipeline will use it (config/kg.yaml; "auto" resolves from the data)."""
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return resolve_eval_time(tables, cfg.get("eval_time", "auto"))


def validate_workbook(path: str | Path = DEFAULT_WORKBOOK, contract_path: str | Path = CONTRACT_PATH,
                      config_path: str | Path = CONFIG_PATH) -> list[Issue]:
    tables = load_workbook(path)
    raw = read_raw_sheets(path)  # Databricks when configured, like load_workbook
    try:
        t = configured_eval_time(tables, config_path)
    except (KeyError, ValueError):
        t = None  # reported by validate_tables as NO_EVAL_TIME
    return validate_tables(tables, load_contract(contract_path), raw, eval_time=t)
