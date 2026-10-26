"""Seed data for the Rules card: web/public/data/rules.json.

- rules: the tier 1 compliance rules C-01..C-09 (locked = legally required; the card asks before one is
  unticked) and the tier 2 business rules B-01..B-09 with their defaults, as specified in
  docs/rule-center.md. Names are short on purpose; id, target and condition only show in the row
  tooltip. A rule gets a condition only when one column check states the whole rule.
- entities: one entry per related sheet, with the rule conditions ("operators") that its columns allow
  today. Operators are read from the workbook and kg/data_contract.yaml, never typed in by hand:
  boolean -> "is yes" / "is no"; enum (contract enums or text with <= 12 values) -> "is <value>";
  small integers (<= 6 values) -> ">= v"; dates -> "within 30 / 90 days". consent_status gets one
  operator per consent type x status first, then its other columns. Labels stay within 32 characters
  (they also become user rule names), dropping words when needed.
- Agent NBA will export the same shape later; keep it exact (web/src/lib/rules.ts reads it).

Run from the repo root: .venv/bin/python web/mock/build_rules.py
web/mock/build_mock.py wipes web/public/data, so run this again after it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from nba.data import BOOL_COLUMNS, load_workbook  # noqa: E402

OUT = REPO / "web" / "public" / "data" / "rules.json"
CONTRACT = REPO / "kg" / "data_contract.yaml"

# Field = related entity (sheet -> label), in the order the popup lists them.
ENTITIES: list[tuple[str, str]] = [
    ("customer_master", "Customer"),
    ("customer_value", "Customer value"),
    ("consent_status", "Consent"),
    ("energy_contracts", "Energy contract"),
    ("mobile_contracts", "Mobile contract"),
    ("autostrom_contracts", "Autostrom contract"),
    ("hems_devices", "HEMS device"),
    ("shop_orders", "Shop order"),
    ("service_interactions", "Service ticket"),
    ("charge_sessions", "Charging session"),
    ("nba_action_history", "Past action"),
    ("newsletter_performance", "Newsletter"),
    ("service_nba_feedback", "Agent feedback"),
    ("product_catalog", "Offer"),
]

# Columns that never make a rule condition: free text, names, prices as text, and bookkeeping.
FREE_TEXT = {
    "message_text", "call_note", "subject_line", "description", "value_note", "legal_basis",
    "typical_target_signal", "churn_drivers", "price_indicative_eur", "car_model",
    "resolution_code", "model_version",
}
METADATA = {"record_updated_at"}
DERIVED = {"is_guest"}  # added by nba.data for guest shop lines, not a workbook column

MAX_ENUM = 12  # text columns with more distinct values count as free text
MAX_INT = 6  # integer columns with more distinct values are measures, not levels
MAX_LABEL = 32  # a label is also the second half of a user rule name: "<Entity> · <label>"
WINDOWS = (30, 90)
DATE_SUFFIXES = ("_at", "_date", "_since", "_until")
TRUE_TEXT = {"true", "false"}
# Shorter words for the few names that would not fit MAX_LABEL otherwise (labels only; values stay as stored).
SHORT = {
    "portal_app_personalisation": "portal personalisation", "double_opt_in_confirmed": "opt-in confirmed",
    "newsletter_unsubscribe_link": "unsubscribe link", "terminated_meter_deregistration": "meter deregistered",
    "apple_mpp_prefetch": "apple mpp", "customer_already_has_product": "owns product",
    "price_guarantee_until": "price guarantee ends",
}

SEED_RULES: list[dict[str, Any]] = [
    # Tier 1 (docs/rule-center.md §2): legally required (locked); the card asks before one is switched off.
    {"id": "C-01", "name": "Channel needs consent", "target": "All channels"},
    {"id": "C-02", "name": "Newsletter needs double opt-in", "target": "Newsletter"},
    {"id": "C-03", "name": "Unsubscribe stops newsletter", "target": "Newsletter",
     "condition": ("newsletter_performance", "unsubscribed", "=", True)},
    {"id": "C-04", "name": "Withdrawn consent cancels pending", "target": "Pending actions"},
    {"id": "C-05", "name": "No profiling, no personalisation", "target": "Personalisation",
     "condition": ("consent_status", "status", "!=", "profiling_analytics:granted")},
    {"id": "C-06", "name": "Dunning: service only", "target": "All sales",
     "condition": ("energy_contracts", "dunning_level", ">=", 1)},
    {"id": "C-07", "name": "Open complaint: no sales", "target": "All sales",
     "condition": ("service_interactions", "status", "=", "open")},  # tightened: any open ticket (R2)
    {"id": "C-08", "name": "Cancellation: no sales", "target": "All sales"},  # energy or Autostrom: two checks
    {"id": "C-09", "name": "Payment data only to exclude", "target": "Payment data"},
    # Tier 2 (§3): marketing switches these on or off; defaults from the spec.
    {"id": "B-01", "name": "Max 5 e-mails in 90 days", "target": "E-mail, Newsletter"},
    {"id": "B-02", "name": "Max 2 contacts in 30 days", "target": "All channels"},
    {"id": "B-03", "name": "Max 1 call in 90 days", "target": "Phone call"},
    {"id": "B-04", "name": "Max 1 SMS in 90 days", "target": "SMS"},
    {"id": "B-05", "name": "Pause offer after 2 dismissals (60 days)", "target": "Offer"},  # count + window
    {"id": "B-06", "name": "No sales 14 days after a ticket", "target": "All customers",
     "condition": ("service_interactions", "resolved_at", "within_days", 14)},
    {"id": "B-07", "name": "Never offer what they own", "target": "All offers"},
    {"id": "B-08", "name": "Calls only if value ≥ 10 €", "target": "Phone call"},
    {"id": "B-09", "name": "Max 50 calls per week", "target": "Phone call"},
]


def words(s: str) -> str:
    return SHORT.get(s, s).replace("_", " ")


def date_words(col: str) -> str:
    """'resolved_at' -> 'resolved'; '_date', '_until', '_since' carry meaning and stay."""
    return words(col[:-3] if col.endswith("_at") else col)


def wordings(column: str, op: str, value: Any) -> list[str]:
    """Ways to say one condition, from full to terse."""
    if op == "within_days":
        col = date_words(column)
        return [f"{col} within {value} days", f"{col} in {value} days"]
    col = words(column)
    if op == "=" and isinstance(value, bool):
        yes = "yes" if value else "no"
        return [f"{col} is {yes}", f"{col}: {yes}"]
    if op == "=":
        v = words(str(value))
        return [f"{col} is {v}", f"{col} {v}", v]  # value only: the popup groups operators by column
    sign = {">=": "≥", "<=": "≤", "!=": "is not"}[op]
    return [f"{col} {sign} {value}"]


def labels(options: list[list[str]]) -> list[str]:
    """One wording for a whole column: the fullest that keeps every label within MAX_LABEL."""
    if not options:
        return []
    n = len(options[0])
    pick = next((i for i in range(n) if all(len(o[i]) <= MAX_LABEL for o in options)), n - 1)
    return [o[pick] for o in options]


def label(column: str, op: str, value: Any) -> str:
    return labels([wordings(column, op, value)])[0]


def consent_label(value: str, op: str = "=") -> str:
    ctype, status = value.split(":")
    return f"{words(ctype)} {'not ' if op == '!=' else ''}{words(status)}"


def operator(column: str, op: str, value: Any, text: str) -> dict[str, Any]:
    shown = json.dumps(value) if isinstance(value, bool) else value  # true / false, as JS prints them
    return {"id": f"{column}|{op}|{shown}", "column": column, "op": op, "value": value, "label": text}


def column_ops(col: str, op: str, values: list[Any], spoken: list[Any] | None = None) -> list[dict[str, Any]]:
    """Operators for one column. spoken: the values the labels name, when they differ from the stored ones."""
    texts = labels([wordings(col, op, v) for v in (spoken or values)])
    return [operator(col, op, v, t) for v, t in zip(values, texts)]


def is_date(sheet: str, col: str, extra_dates: set[str]) -> bool:
    return col.endswith(DATE_SUFFIXES) or f"{sheet}.{col}" in extra_dates


def column_operators(sheet: str, col: str, values: list[Any], enums: dict[str, list[str]],
                     extra_dates: set[str]) -> list[dict[str, Any]]:
    present = [v for v in values if v is not None]
    distinct = sorted({str(v) for v in present})
    if not present:
        return []
    if col in BOOL_COLUMNS or all(isinstance(v, bool) for v in present):
        return column_ops(col, "=", [True, False])
    if {s.lower() for s in distinct} <= TRUE_TEXT:
        # "True" / "False" kept as text by nba.data: match the stored text, label it yes / no.
        stored = sorted(distinct, key=lambda s: s.lower() != "true")
        return column_ops(col, "=", stored, [s.lower() == "true" for s in stored])
    if is_date(sheet, col, extra_dates):
        return [] if len(distinct) < 2 else column_ops(col, "within_days", list(WINDOWS))
    allowed = enums.get(f"{sheet}.{col}")
    if allowed is not None:
        return [] if len(allowed) < 2 else column_ops(col, "=", allowed)
    if all(isinstance(v, int) and not isinstance(v, bool) for v in present):
        levels = sorted({int(v) for v in present})
        return [] if len(levels) > MAX_INT else column_ops(col, ">=", levels[1:])
    if all(isinstance(v, str) for v in present) and 2 <= len(distinct) <= MAX_ENUM:
        return column_ops(col, "=", distinct)
    return []  # floats, high-cardinality text, single-valued columns


def entity_operators(sheet: str, df: Any, enums: dict[str, list[str]], extra_dates: set[str]) -> list[dict[str, Any]]:
    out = []
    skip = FREE_TEXT | METADATA | DERIVED
    if sheet == "consent_status":
        # One operator per consent type x status (one row per customer and type), then the other columns.
        for ctype in enums["consent_status.consent_type"]:
            for status in enums["consent_status.status"]:
                value = f"{ctype}:{status}"
                out.append(operator("status", "=", value, consent_label(value)))
        skip = skip | {"consent_type", "status"}
    for col in df.columns:
        if col.endswith("_id") or col in skip:
            continue
        out.extend(column_operators(sheet, col, df[col].tolist(), enums, extra_dates))
    return out


def condition(entity: str, column: str, op: str, value: Any) -> dict[str, Any]:
    text = consent_label(value, op) if entity == "consent_status" else label(column, op, value)
    return {"entity": entity, "column": column, "op": op, "value": value, "label": text}


def seed_rules() -> list[dict[str, Any]]:
    rules = []
    for r in SEED_RULES:
        hard = r["id"].startswith("C-")
        node: dict[str, Any] = {"id": r["id"], "name": r["name"], "tier": "hard" if hard else "custom", "active": True}
        if hard:
            node["locked"] = True
        node["target"] = r["target"]
        if "condition" in r:
            node["condition"] = condition(*r["condition"])
        node["children"] = []
        rules.append(node)
    return rules


def build() -> dict[str, Any]:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    enums = {**contract.get("enums_warning", {}), **contract.get("enums_error", {})}
    extra_dates = set(contract.get("extra_dates", []))
    tables = load_workbook(use_cache=False)
    entities = [{"id": sheet, "label": text, "operators": entity_operators(sheet, tables[sheet], enums, extra_dates)}
                for sheet, text in ENTITIES]
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules": seed_rules(),
        "entities": entities,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT, help="output file (default web/public/data/rules.json)")
    args = ap.parse_args()
    data = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts = ", ".join(f"{e['id']} {len(e['operators'])}" for e in data["entities"])
    print(f"wrote {len(data['rules'])} rules and {len(data['entities'])} entities to {args.out}")
    print(f"operators: {counts}")


if __name__ == "__main__":
    main()
