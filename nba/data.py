"""Load the mock workbook and the event stream (README §5.1).

Owner: Agent KG. Other agents import `load_workbook` / `load_events` and never
re-implement parsing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = REPO / "data" / "maingau_nba_mockdata.xlsx"
DEFAULT_EVENTS = REPO / "data" / "event_stream_2026-10-01.jsonl"
CACHE_DIR = REPO / "out" / ".cache"

# Free-text sheets are kept as strings; every other sheet gets typed values.
FREE_TEXT_SHEETS = {"README", "columns", "clv_method"}

BOOL_COLUMNS = {
    "portal_account", "app_installed", "feed_in_meter", "control_group", "converted_within_14d",
    "consent_checked", "unsubscribed", "esim", "app_user", "first_contact_resolution",
    "delivered", "bounced", "converted_within_7d",
}
# Identifier-like columns stay strings even if they look numeric.
STRING_COLUMNS = {"postal_code_prefix"}
DATE_SUFFIXES = ("_at", "_date", "_since", "_until")
_TRUE = {"1", "true", "yes", "y"}
_FALSE = {"0", "false", "no", "n"}


def _is_date_column(col: str) -> bool:
    return col == "date" or col.endswith(DATE_SUFFIXES)


def _is_null(v: Any) -> bool:
    return (v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v))
            or (isinstance(v, str) and not v.strip()))


def _to_bool(v: Any) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in _TRUE or s == "1.0":
        return True
    if s in _FALSE or s == "0.0":
        return False
    return None


def _to_datetime(v: Any) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.fromisoformat(str(v).strip())
    except ValueError:
        ts = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(ts) else ts.to_pydatetime()


def _is_number(v: Any) -> bool:
    try:
        float(str(v).strip())
        return True
    except ValueError:
        return False


def _to_number(v: Any) -> int | float | None:
    if v is None:
        return None
    s = str(v).strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else float(s)


def _clean_sheet(name: str, df: pd.DataFrame) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for col in df.columns:
        values = [None if _is_null(v) else v for v in df[col].tolist()]
        typed = name not in FREE_TEXT_SHEETS and col not in STRING_COLUMNS and not col.endswith("_id")
        if typed and col in BOOL_COLUMNS:
            values = [_to_bool(v) for v in values]
        elif typed and _is_date_column(col):
            values = [_to_datetime(v) for v in values]
        elif typed and any(v is not None for v in values) and all(_is_number(v) for v in values if v is not None):
            values = [_to_number(v) for v in values]
        # An explicit object Series stops pandas from re-inferring Timestamp/NaT/NaN.
        cols[col] = pd.Series(values, index=df.index, dtype=object)
    out = pd.DataFrame(cols)
    if name == "shop_orders":
        out["is_guest"] = out["customer_id"].isna()
    return out


def _stamp(tables: dict[str, pd.DataFrame], path: Path) -> dict[str, pd.DataFrame]:
    """Record the source workbook on every table, so e.g. the policy loader can resolve eval_time
    from the same workbook when it only receives the product catalog."""
    for df in tables.values():
        df.attrs["workbook"] = str(Path(path).resolve())
    return tables


def _cache_key(path: Path) -> str:
    """Workbook identity plus a parser fingerprint, so a changed parser never reads an old pickle."""
    st = path.stat()
    parser = hashlib.sha256(Path(__file__).read_bytes() + pd.__version__.encode()).hexdigest()[:12]
    return f"workbook-{st.st_mtime_ns}-{st.st_size}-{parser}.pkl"


def load_workbook(path: str | Path = DEFAULT_WORKBOOK, use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Every sheet as a DataFrame of Python values (None, bool, int/float, datetime, str).

    Raw rows are kept; guest shop lines get is_guest = True. Parsed tables are cached in
    out/.cache, keyed by the workbook's mtime and size and a fingerprint of this parser.
    """
    path = Path(path)
    cache = CACHE_DIR / _cache_key(path)
    if use_cache and cache.exists():
        with cache.open("rb") as fh:
            return _stamp(pickle.load(fh), path)
    raw = pd.read_excel(path, sheet_name=None, dtype=str)
    tables = _stamp({name: _clean_sheet(name, df) for name, df in raw.items()}, path)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(f".{os.getpid()}.tmp")
        with tmp.open("wb") as fh:
            pickle.dump(tables, fh)
        tmp.replace(cache)  # atomic: readers never see a half-written pickle
    return tables


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)


def load_events(path: str | Path = DEFAULT_EVENTS) -> list[dict]:
    """Events deduplicated by (event_id, occurred_at), first seen wins, sorted by ingested_at."""
    seen: set[tuple[str, str]] = set()
    events: list[dict] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            ev = json.loads(line)
            key = (ev["event_id"], ev.get("occurred_at"))
            if key in seen:
                log.info("duplicate event dropped: %s (line %d)", ev["event_id"], line_no)
                continue
            seen.add(key)
            ev["occurred_at"] = _parse_ts(ev.get("occurred_at"))
            ev["ingested_at"] = _parse_ts(ev.get("ingested_at"))
            payload = ev.get("payload") or {}
            ev["effective_date"] = _parse_ts(payload.get("effective_date")) if payload.get("effective_date") else None
            events.append(ev)
    events.sort(key=lambda e: (e["ingested_at"] or datetime.min, e["event_id"]))
    return events
