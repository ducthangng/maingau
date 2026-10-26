"""What an edit to rules.yaml does: decisions before vs after for every customer, the feedback-loop
traffic light before vs after, and the independent hard-rule check on the edited engine."""
from __future__ import annotations

import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from nba.contracts import NO_ACTION
from nba.data import DEFAULT_WORKBOOK, load_workbook
from nba.engine.config import load_config
from nba.engine.runtime import Runtime
from nba.kg.policy import load_policy
from nba.learn.evidence import Evidence
from nba.learn.health import patterns
from nba.learn.lookalike import attach
from nba.profile import profile_population
from nba.rules.book import SOURCES
from nba.rules.check import raw_rules, violations
from nba.state import build_states


def runtime_from(sections: dict[str, dict], tables) -> Runtime:
    """The same steps as Runtime.load, with the rule files taken from `sections`."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = {}
        for name, rel in SOURCES.items():
            paths[name] = Path(tmp) / rel.name
            paths[name].write_text(yaml.safe_dump(sections[name], allow_unicode=True, sort_keys=False), encoding="utf-8")
        policy = load_policy(paths["policy"], paths["kg"], catalog=tables["product_catalog"])
        cfg = load_config(tables, paths["nba"])
    t = datetime.fromisoformat(policy.config["eval_time"])
    states = build_states(tables, t, snapshot_mode=policy.config["snapshot_mode"])
    cfg.history = [r for r in cfg.history if r.get("decided_at") and r["decided_at"] <= t]
    return attach(Runtime(tables, states, profile_population(states), policy, cfg), sections["learn"])


def offer_of(tuple_id: str) -> str:
    return tuple_id.split("|")[0] if tuple_id != NO_ACTION else NO_ACTION


def chosen_value(card) -> float | None:
    c = next((x for x in card.candidates if x.tuple_id == card.chosen.tuple_id), None)
    return c.valuation.delta_clv if c else None


@dataclass
class Impact:
    n_customers: int
    changed: list[dict]
    flows: Counter
    sum_before: float
    sum_after: float
    chosen_before: Counter
    chosen_after: Counter
    reference_changed: list[dict]
    violations_after: list[str]
    loop_changes: list[dict]
    loop_counts: tuple[dict, dict]
    errors: list[str] = field(default_factory=list)


def impact(base_sections: dict, edited_sections: dict, *, customer_ids=None, workbook=DEFAULT_WORKBOOK,
           hold_to_edited: bool = False) -> Impact:
    """`hold_to_edited`: check hard rules against the edited channel map and contact cap (after a named
    sign-off) instead of the committed ones."""
    tables = load_workbook(workbook)
    before_rt = runtime_from(base_sections, tables)
    try:
        after_rt = runtime_from(edited_sections, tables)
    except (ValueError, KeyError, TypeError) as exc:  # PolicyError is a ValueError
        return Impact(0, [], Counter(), 0, 0, Counter(), Counter(), [], [], [], ({}, {}),
                      errors=[f"The edited rules do not load: {exc}"])
    ids = sorted(customer_ids or before_rt.states)
    before, after = before_rt.cards(ids), after_rt.cards(ids)
    reference = set(edited_sections["learn"].get("reference_customers") or [])
    changed, flows = [], Counter()
    for b, a in zip(before, after):
        if b.chosen.tuple_id != a.chosen.tuple_id:
            row = {"customer_id": b.customer_id, "before": b.chosen.tuple_id, "after": a.chosen.tuple_id,
                   "delta_before": chosen_value(b), "delta_after": chosen_value(a), "reason_after": a.chosen.reason_line}
            changed.append(row)
            flows[(offer_of(row["before"]), offer_of(row["after"]))] += 1
    total = lambda cards: round(sum(chosen_value(c) or 0.0 for c in cards), 2)
    # held to the committed channel map and contact cap unless a hard-rule edit was signed off
    held = edited_sections if hold_to_edited else base_sections
    base_policy, base_kg = held["policy"], held["kg"]
    cap = (int(base_kg["contact_cap"]["max_contacts"]), int(base_kg["contact_cap"]["window_days"]))
    rules = raw_rules(tables, base_policy["channels"], datetime.fromisoformat(base_kg["eval_time"]), cap)
    loop_before = {p.key: p for p in patterns(Evidence.from_runtime(before_rt, base_sections["learn"]))}
    loop_after = {p.key: p for p in patterns(Evidence.from_runtime(after_rt, edited_sections["learn"]))}
    loop_changes = [{"pattern": k, "before": loop_before[k].status if k in loop_before else None,
                     "after": loop_after[k].status if k in loop_after else None,
                     "why": loop_after[k].why if k in loop_after else ""}
                    for k in sorted(set(loop_before) | set(loop_after))
                    if (loop_before.get(k) and loop_before[k].status) != (loop_after.get(k) and loop_after[k].status)]
    count = lambda found: dict(Counter(p.status for p in found.values()))
    return Impact(
        n_customers=len(ids), changed=changed, flows=flows, sum_before=total(before), sum_after=total(after),
        chosen_before=Counter(offer_of(c.chosen.tuple_id) for c in before),
        chosen_after=Counter(offer_of(c.chosen.tuple_id) for c in after),
        reference_changed=[c for c in changed if c["customer_id"] in reference],
        violations_after=violations(after, rules), loop_changes=loop_changes,
        loop_counts=(count(loop_before), count(loop_after)),
    )
