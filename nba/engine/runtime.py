"""One shared in-memory context for CLI and local API."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from nba.contracts import IndexRow, NO_ACTION, Summary
from nba.data import DEFAULT_WORKBOOK, load_workbook
from nba.engine.assemble import assemble
from nba.engine.config import EngineConfig, load_config
from nba.kg.bundle import COLUMN_SRC
from nba.kg.policy import load_policy
from nba.state import build_states, population

COLUMN_SOURCES = {
    **COLUMN_SRC,
    "urgency_score": "customer_value.clv_eur; customer_value.churn_prob_12m; nba.kg.segments.triage",
    "delta_clv": "nba.engine.value.delta_clv", "p_accept": "nba_action_history.converted_within_14d",
    "contact_cost": "value_assumptions.contact_cost", "n_signals": "nba.kg.signals.extract_signals",
    "n_candidates": "nba.kg.rules.generate_candidates", "n_blocked": "nba.kg.rules.generate_candidates",
}


@dataclass
class Runtime:
    tables: dict
    states: dict
    pop: object
    policy: object
    cfg: EngineConfig
    _cards: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, workbook=DEFAULT_WORKBOOK, *, p_mode=None, eval_time=None):
        tables = load_workbook(workbook)
        policy = load_policy(catalog=tables["product_catalog"])
        t = eval_time or datetime.fromisoformat(policy.config["eval_time"])
        states = build_states(tables, t, snapshot_mode=policy.config["snapshot_mode"])
        cfg = load_config(tables, p_mode=p_mode)
        # A propensity estimate must never use action outcomes recorded after evaluation.
        cfg.history = [r for r in cfg.history if r.get("decided_at") and r["decided_at"] <= t]
        return cls(tables, states, population(tables), policy, cfg)

    def card(self, customer_id):
        state = self.states[customer_id]
        key = (customer_id, state.revision)
        if key not in self._cards:
            self._cards[key] = assemble(state, self.pop, self.policy, self.cfg)
        return self._cards[key].model_copy(deep=True)

    def cards(self, customer_ids=None):
        return [self.card(cid) for cid in sorted(self.states if customer_ids is None else customer_ids)]


def index_row(card, state) -> IndexRow:
    value, master = state.one("customer_value") or {}, state.one("customer_master") or {}
    selected = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
    v, tri = selected.valuation if selected else None, card.triage
    birth = master.get("birth_year")
    band_start = (state.eval_time.year - int(birth)) // 10 * 10 if birth is not None else None
    return IndexRow(
        customer_id=state.customer_id, age_band=f"{band_start}–{band_start + 9}" if band_start is not None else None,
        city=master.get("city"), lines=value.get("active_business_lines"), clv_eur=value.get("clv_eur"),
        churn=value.get("churn_prob_12m"), archetype=tri.archetype.id, archetype_name=tri.archetype.name,
        urgency_tier=tri.urgency_tier, urgency_score=tri.urgency_score,
        top_reason=tri.urgency_reasons[0] if tri.urgency_reasons else None,
        flags=[f.id for f in tri.flags], outlier=tri.outlier, triggers=[s.id for s in card.signals],
        chosen_offer=selected.offer_id if selected else NO_ACTION, chosen_tuple=card.chosen.tuple_id,
        channel=selected.channel if selected else None, tone=selected.tone if selected else None,
        delta_clv=v.delta_clv if v else None, p_accept=v.p_accept if v else None, contact_cost=v.contact_cost if v else None,
        confidence=v.confidence if v else None, service_mode=card.chosen.service_mode,
        personalised=selected.personalised if selected else None,
        checklist_failed=[c.item for c in card.checklist if not c.passed],
        n_signals=len(card.signals), n_candidates=len(card.candidates), n_blocked=len(card.blocked),
        exclusions=[e.rule_id for e in card.profile.exclusions if e.active],
    )


def index_rows(cards, states):
    return sorted((index_row(c, states[c.customer_id]) for c in cards),
                  key=lambda r: (r.urgency_tier, -r.urgency_score, r.customer_id))


def summary(cards, cfg, eval_time) -> Summary:
    chosen, blocked, no_action = defaultdict(list), Counter(), Counter()
    signal, archetype, urgency, flags = Counter(), Counter(), Counter(), Counter()
    for card in cards:
        selected = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
        if selected:
            chosen[selected.offer_id].append(selected.valuation.delta_clv)
        else:
            no_action[card.chosen.reason_line] += 1
        blocked.update(b.rule_id for b in card.blocked)
        signal.update(s.id for s in card.signals)
        archetype.update([card.triage.archetype.id])
        urgency.update([card.triage.urgency_tier])
        flags.update(f.id for f in card.triage.flags)
    return Summary(eval_time=eval_time.isoformat(), n_customers=len(cards),
                   chosen_by_offer={k: {"count": len(v), "sum_delta_clv": math.fsum(v)} for k, v in sorted(chosen.items())},
                   blocked_by_rule=dict(blocked), no_action_by_reason=dict(no_action), signal_counts=dict(signal),
                   archetype_counts=dict(archetype), urgency_counts=dict(urgency), flag_counts=dict(flags),
                   sources=cfg.sources, column_src=COLUMN_SOURCES, value_date=cfg.value_date)
