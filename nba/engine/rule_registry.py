"""Rule Center registry (docs/rule-center.md §6). Owner: Agent NBA.

- the rule tree for the Rule Center card and GET /api/rules (also written to rules.json by nba.build);
- the Field / Operator catalog for the "Add rule" popup, built from the columns the workbook has today;
- edits as an append-only list of operations (update / create / delete), replayed over config/nba.yaml and
  config/kg.yaml contact_cap, so every version says who changed what and when.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from nba.contracts import Condition, Entity, OperatorOption, RuleNode, RulesFile
from nba.data import BOOL_COLUMNS, REPO, _is_date_column
from nba.engine.rulecenter import load_rules, rule_set_version
from nba.kg.contacts import check_sources

CONTRACT_PATH = REPO / "kg" / "data_contract.yaml"
ENTITIES = {
    "customer_master": "Customer", "customer_value": "Customer value", "consent_status": "Consent",
    "energy_contracts": "Energy contract", "mobile_contracts": "Mobile contract",
    "autostrom_contracts": "Autostrom contract", "hems_devices": "HEMS device", "shop_orders": "Shop order",
    "service_interactions": "Service ticket", "charge_sessions": "Charging session",
    "nba_action_history": "Past action", "newsletter_performance": "Newsletter",
    "service_nba_feedback": "Agent feedback", "product_catalog": "Offer",
}
FREE_TEXT = {"message_text", "call_note", "subject_line", "description", "value_note", "typical_target_signal",
             "churn_drivers", "product_name", "city", "content_variant", "transcript", "summary", "segment_rule"}
CHANNEL_NAMES = {"newsletter_email": "Newsletter", "email": "E-mail", "outbound_call": "Phone call", "sms": "SMS",
                 "portal_popup": "Portal pop-up", "app_push": "App push"}
B02, B07 = "B-02", "B-07"
LOCKED = {B07}  # enforced by the KG gate itself; it cannot be switched off here


class RuleEditError(ValueError):
    """A refused Rule Center edit; `status` is the HTTP code (403 locked, 404 unknown, 422 invalid)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- Field / Operator catalog


def _label(column: str) -> str:
    return column.replace("_", " ")


def _operators(sheet: str, df: pd.DataFrame, enums: dict[str, list]) -> list[OperatorOption]:
    out: list[OperatorOption] = []

    def add(column, op, value, label):
        out.append(OperatorOption(id=f"{column}|{op}|{value}", column=column, op=op, value=value, label=label))

    if sheet == "consent_status":  # one consent per type: "<type> <status>"
        for ctype in enums.get("consent_status.consent_type", []):
            for status in enums.get("consent_status.status", []):
                add("status", "=", f"{ctype}:{status}", f"{_label(ctype)} {status}")
        return out
    for col in df.columns:
        if col == "customer_id" or col.endswith("_id") or col in FREE_TEXT:
            continue
        values = [v for v in df[col].tolist() if v is not None and not (isinstance(v, float) and pd.isna(v))]
        if not values:
            continue
        key = f"{sheet}.{col}"
        if col in BOOL_COLUMNS or all(isinstance(v, bool) for v in values):
            add(col, "=", True, f"{_label(col)} is yes")
            add(col, "=", False, f"{_label(col)} is no")
        elif key in enums or (all(isinstance(v, str) for v in values) and len(set(values)) <= 12):
            for v in enums.get(key) or sorted(set(values)):
                add(col, "=", v, f"{_label(col)} is {_label(str(v))}")
        elif _is_date_column(col) or all(hasattr(v, "year") for v in values):
            for days in (30, 90):
                add(col, "within_days", days, f"{_label(col)} within {days} days")
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer() for v in values) \
                and len(set(values)) <= 6:
            for v in sorted(set(int(x) for x in values))[1:]:
                add(col, ">=", v, f"{_label(col)} ≥ {v}")
    return out


def entity_catalog(tables: dict[str, pd.DataFrame], contract_path: Path = CONTRACT_PATH) -> list[Entity]:
    contract = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8")) or {}
    enums = {**(contract.get("enums_warning") or {}), **(contract.get("enums_error") or {})}
    return [Entity(id=sheet, label=label, operators=_operators(sheet, tables[sheet], enums))
            for sheet, label in ENTITIES.items() if sheet in tables]


# ---------------------------------------------------------------- the rule tree


def _target(rule: dict) -> str:
    if rule.get("channels"):
        return ", ".join(CHANNEL_NAMES.get(c, c) for c in rule["channels"])
    for key in ("min_eur", "per_week"):
        if rule.get(key):
            return ", ".join(CHANNEL_NAMES.get(c, c) for c in rule[key])
    return {"offer_cooldown": "Offer", "post_ticket_cooldown": "All customers"}.get(rule.get("kind"), "All customers")


def _custom_node(r: dict) -> RuleNode:
    cond = r.get("condition")
    return RuleNode(id=r["id"], name=r.get("name") or r["id"], tier="hard" if r.get("hard") else "custom",
                    active=bool(r.get("active", True)), kind="condition", effect=r.get("effect") or "auto",
                    condition=Condition(**cond) if cond else None, children=[_custom_node(c) for c in r.get("children") or []])


def rule_tree(settings: dict, policy) -> list[RuleNode]:
    """Compliance (locked) and business rules, then the custom rules; a custom rule with `parent` set to a
    built-in rule is shown under it (it is still its own rule)."""
    nodes: dict[str, RuleNode] = {}
    for cid, c in sorted(policy.compliance.items()):
        nodes[cid] = RuleNode(id=cid, name=c["label"], tier="hard", locked=True, effect=c.get("effect"))
    cap = policy.config.get("contact_cap", {})
    business = {
        B02: RuleNode(id=B02, name=f"Max {cap.get('max_contacts', 2)} contacts in {cap.get('window_days', 30)} days",
                      tier="custom", target="All channels", kind="contact_cap", effect="DEFER_UNTIL",
                      params={k: cap[k] for k in ("max_contacts", "window_days", "sources") if k in cap}),
        B07: RuleNode(id=B07, name="Never offer what they own", tier="custom", locked=True, target="All offers",
                      kind="kg_gate", effect="BLOCK_OFFER"),
    }
    for rule in load_rules(settings):
        if rule.tier == "business":
            business[rule.id] = RuleNode(id=rule.id, name=rule.name, tier="custom", active=rule.active,
                                         target=_target({**rule.params, "kind": rule.kind}), kind=rule.kind,
                                         effect=rule.effect, params=dict(rule.params))
    nodes.update(dict(sorted(business.items())))
    roots: list[RuleNode] = []
    for r in settings.get("custom_rules") or []:
        node = _custom_node(r)
        parent = nodes.get(r.get("parent") or "")
        (parent.children if parent is not None else roots).append(node)
    return list(nodes.values()) + roots


def rules_file(settings: dict, policy, tables, eval_time: str) -> RulesFile:
    """rules.json for the static Rule Center page (deterministic: stamped with the snapshot time)."""
    return RulesFile(generated_at=eval_time, rule_set_version=rule_set_version(settings, policy),
                     rules=rule_tree(settings, policy), entities=entity_catalog(tables))


# ---------------------------------------------------------------- edits (append-only operations)


def _find(rules: list[dict], rule_id: str) -> tuple[list[dict], dict] | tuple[None, None]:
    for r in rules:
        if r.get("id") == rule_id:
            return rules, r
        found = _find(r.get("children") or [], rule_id)
        if found[1] is not None:
            return found
    return None, None


def custom_ids(settings: dict) -> list[str]:
    out = []

    def walk(rs):
        for r in rs:
            out.append(r["id"])
            walk(r.get("children") or [])
    walk(settings.get("custom_rules") or [])
    return out


def apply_op(settings: dict, cap: dict, op: dict, *, known_ids=frozenset()) -> tuple[dict, dict]:
    """One edit -> new (settings, contact_cap). Raises RuleEditError; never mutates its inputs."""
    settings, cap = copy.deepcopy(settings), copy.deepcopy(cap)
    kind, rid = op.get("op"), op.get("rule_id")
    if kind == "create":
        rule = copy.deepcopy(op["rule"])
        parent = rule.get("parent")
        if parent and parent.startswith("U-"):
            _, holder = _find(settings.get("custom_rules") or [], parent)
            if holder is None:
                raise RuleEditError(404, f"unknown rule {parent}")
            rule.pop("parent")
            holder.setdefault("children", []).append(rule)  # a sub-rule narrows its custom parent
        else:
            if parent and parent not in known_ids:
                raise RuleEditError(404, f"unknown rule {parent}")
            settings["custom_rules"] = list(settings.get("custom_rules") or []) + [rule]
    elif rid is None:
        raise RuleEditError(422, "rule_id is missing")
    elif rid.startswith("C-") or rid in LOCKED:
        raise RuleEditError(403, f"{rid} is always on: compliance rules and KG gates can only be tightened, "
                                 "by adding a hard rule")
    elif kind == "delete":
        holder, rule = _find(settings.get("custom_rules") or [], rid)
        if rule is None:
            raise RuleEditError(403 if rid in known_ids else 404, f"only rules added in the Rule Center can be removed ({rid})")
        holder.remove(rule)
    elif kind == "update" and rid == B02:
        if op.get("active") is False:
            raise RuleEditError(422, "B-02 cannot be switched off; raise its limit instead")
        unknown = set(op.get("params") or {}) - {"max_contacts", "window_days", "sources"}
        if unknown:
            raise RuleEditError(422, f"B-02 has no setting {sorted(unknown)}")
        cap.update(op.get("params") or {})
    elif kind == "update":
        business = settings.get("business_rules") or {}
        if rid in business:
            rule = business[rid] = dict(business[rid])
            unknown = set(op.get("params") or {}) - (set(rule) - {"name", "kind", "effect", "reason", "active"})
            if unknown:
                raise RuleEditError(422, f"{rid} has no setting {sorted(unknown)}")
        else:
            _, rule = _find(settings.get("custom_rules") or [], rid)
            if rule is None:
                raise RuleEditError(404, f"unknown rule {rid}")
            unknown = set(op.get("params") or {}) - {"name", "effect", "days", "channels"}
            if unknown:
                raise RuleEditError(422, f"{rid} has no setting {sorted(unknown)}")
        if op.get("active") is not None:
            rule["active"] = bool(op["active"])
        rule.update(op.get("params") or {})
    else:
        raise RuleEditError(422, f"unknown operation {kind!r}")
    try:
        load_rules(settings)
        check_sources(cap.get("sources") or ())
        for key in ("max_contacts", "window_days"):
            if isinstance(cap.get(key), bool) or not isinstance(cap.get(key), int) or cap[key] < 1:
                raise ValueError(f"contact_cap.{key} must be a whole number ≥ 1")
    except ValueError as exc:
        raise RuleEditError(422, str(exc)) from exc
    return settings, cap


def replay_ops(settings: dict, cap: dict, ops: list[dict], known_ids=frozenset()) -> tuple[dict, dict]:
    for op in ops:
        settings, cap = apply_op(settings, cap, op, known_ids=known_ids)
    return settings, cap


def next_custom_id(settings: dict, history: list[dict]) -> str:
    """U-<n>, never reused: above every custom ID in the config and in the edit history."""
    seen = custom_ids(settings) + [o["rule"]["id"] for o in history if o.get("op") == "create"]
    n = max([int(i.split("-", 1)[1]) for i in seen if i.startswith("U-") and i.split("-", 1)[1].isdigit()] + [0])
    return f"U-{n + 1}"


def custom_rule(body, rule_id: str, entities: list[Entity]) -> dict[str, Any]:
    """RuleCreate -> config dict (ids for sub-rules too); names default to "<entity> · <operator>"."""
    labels = {e.id: e.label for e in entities}
    ops = {(e.id, o.column, o.op, str(o.value)): o.label for e in entities for o in e.operators}
    counter = [0]

    def build(node, rid):
        cond = node.condition.model_dump(exclude_none=True)
        label = cond.get("label") or ops.get((cond["entity"], cond["column"], cond["op"], str(cond["value"])),
                                             f"{_label(cond['column'])} {cond['op']} {cond['value']}")
        cond["label"] = label
        out = {"id": rid, "name": node.name or f"{labels.get(cond['entity'], cond['entity'])} · {label}",
               "hard": body.hard, "active": node.active, "condition": cond, "children": []}
        if node.effect:
            out["effect"] = node.effect
        for child in node.children:
            counter[0] += 1
            out["children"].append(build(child, f"{rule_id}.{counter[0]}"))
        return out

    rule = build(body, rule_id)
    if body.parent:
        rule["parent"] = body.parent
    return rule
