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
from nba.engine.rulecenter import capacity_limits, plan_capacity
from nba.kg.bundle import COLUMN_SRC
from nba.kg.policy import load_policy
from nba.state import build_states, resolve_eval_time
from nba.profile import profile_population

COLUMN_SOURCES = {
    **COLUMN_SRC,
    "urgency_score": "customer_value.clv_eur; customer_value.churn_prob_12m; nba.kg.segments.triage",
    "delta_clv": "nba.engine.value.delta_clv", "p_accept": "nba_action_history.converted_within_14d",
    "contact_cost": "value_assumptions.contact_cost", "n_signals": "nba.kg.signals.extract_signals",
    "n_candidates": "nba.kg.rules.generate_candidates", "n_blocked": "nba.kg.rules.generate_candidates",
    "reason_signal": "chosen action path: Signal (nba.kg.rules)", "reason_need": "chosen action path: Need (kg/policy.yaml)",
}


@dataclass
class Runtime:
    tables: dict
    states: dict
    pop: object
    policy: object
    cfg: EngineConfig
    _cards: dict = field(default_factory=dict, repr=False)
    _base: dict = field(default_factory=dict, repr=False)  # cards before the B-09 capacity pass
    _overflow: dict | None = field(default=None, repr=False)

    @classmethod
    def load(cls, workbook=DEFAULT_WORKBOOK, *, p_mode=None, eval_time=None, memory_path=None):
        tables = load_workbook(workbook)
        policy = load_policy(catalog=tables["product_catalog"], tables=tables)
        # --asof: offsets and plain dates are normalised like config/kg.yaml eval_time (README §6.15)
        t = resolve_eval_time(tables, eval_time) if eval_time else datetime.fromisoformat(policy.config["eval_time"])
        states = build_states(tables, t, snapshot_mode=policy.config["snapshot_mode"])
        cfg = load_config(tables, p_mode=p_mode)
        # A propensity estimate must never use action outcomes recorded after evaluation.
        cfg.history = [r for r in cfg.history if r.get("decided_at") and r["decided_at"] <= t]
        from nba.learn.evidence import load_settings
        from nba.learn.lookalike import attach
        rt = attach(cls(tables, states, profile_population(states), policy, cfg), load_settings())
        return rt.with_memory(memory_path) if memory_path else rt

    def _base_card(self, customer_id):
        state = self.states[customer_id]
        key = (customer_id, state.revision)
        if key not in self._base:
            self._base[key] = assemble(state, self.pop, self.policy, self.cfg)
        return self._base[key]

    def capacity_overflow(self) -> dict:
        """B-09: customers whose chosen action overflows a channel's weekly capacity -> {channel: wait until}.
        Needs every customer's decision once; with no active capacity rule it costs nothing."""
        if self._overflow is None:
            limits = capacity_limits(self.cfg.rules)
            self._overflow = plan_capacity([self._base_card(cid) for cid in sorted(self.states)], limits) if limits else {}
        return self._overflow

    def card(self, customer_id):
        state = self.states[customer_id]
        key = (customer_id, state.revision)
        if key not in self._cards:
            wait = self.capacity_overflow().get(customer_id)
            self._cards[key] = (assemble(state, self.pop, self.policy, self.cfg, capacity=wait) if wait
                                else self._base_card(customer_id))
        return self._cards[key].model_copy(deep=True)

    def with_memory(self, memory) -> Runtime:
        """A copy that applies customer memory (a path to customer_memory.jsonl or a loaded dict)."""
        from dataclasses import replace

        from nba.ai.feedback import load_memory

        mem = load_memory(memory) if not isinstance(memory, dict) else memory
        if not mem and not self.cfg.memory:
            return self
        return Runtime(self.tables, self.states, self.pop, self.policy, replace(self.cfg, memory=mem))

    def with_rules(self, *, settings=None, policy=None) -> Runtime:
        """A copy with edited Rule Center settings (config/nba.yaml) and/or KG policy (contact cap); caches reset."""
        cfg = self.cfg.with_settings(**settings) if settings else self.cfg
        return Runtime(self.tables, self.states, self.pop, policy or self.policy, cfg)

    def cards(self, customer_ids=None):
        return [self.card(cid) for cid in sorted(self.states if customer_ids is None else customer_ids)]


def index_row(card, state) -> IndexRow:
    value, master = state.one("customer_value") or {}, state.one("customer_master") or {}
    selected = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
    v, tri = selected.valuation if selected else None, card.triage
    path = selected.path if selected else []
    reason = {t: next((p.id for p in path if p.kind == "node" and p.type == t), None) for t in ("Signal", "Need")}
    birth = master.get("birth_year")
    band_start = (state.eval_time.year - int(birth)) // 10 * 10 if birth is not None else None
    return IndexRow(
        customer_id=state.customer_id, age_band=f"{band_start}–{band_start + 9}" if band_start is not None else None,
        city=master.get("city"), lines=value.get("active_business_lines"), clv_eur=value.get("clv_eur"),
        churn=value.get("churn_prob_12m"), archetype=tri.archetype.id, archetype_name=tri.archetype.name,
        urgency_tier=tri.urgency_tier, urgency_score=tri.urgency_score,
        top_reason=tri.urgency_reasons[0] if tri.urgency_reasons else None,
        flags=[f.id for f in tri.flags], outlier=tri.outlier, triggers=[s.id for s in card.signals],
        reason_signal=reason["Signal"], reason_need=reason["Need"],
        chosen_offer=selected.offer_id if selected else NO_ACTION, chosen_tuple=card.chosen.tuple_id,
        channel=selected.channel if selected else None, tone=selected.tone if selected else None,
        delta_clv=v.delta_clv if v else None, p_accept=v.p_accept if v else None, contact_cost=v.contact_cost if v else None,
        confidence=v.confidence if v else None, service_mode=card.chosen.service_mode,
        personalised=selected.personalised if selected else None,
        checklist_failed=[c.item for c in card.checklist if not c.passed], deferred_until=card.chosen.deferred_until,
        n_signals=len(card.signals), n_candidates=len(card.candidates), n_blocked=len(card.blocked),
        exclusions=[e.rule_id for e in card.profile.exclusions if e.active],
    )


def index_rows(cards, states):
    return sorted((index_row(c, states[c.customer_id]) for c in cards),
                  key=lambda r: (r.urgency_tier, -r.urgency_score, r.customer_id))


def summary(cards, cfg, eval_time, policy=None) -> Summary:
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
                   sources=cfg.sources, column_src=COLUMN_SOURCES, value_date=cfg.value_date,
                   signal_labels={sid: s.label for sid, s in policy.signals.items()} if policy else {},
                   need_labels={nid: n.get("label_en", nid) for nid, n in policy.needs.items()} if policy else {})
