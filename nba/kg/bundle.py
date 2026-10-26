"""Everything the KG knows about one customer, in one call (README §5.6). Owner: Agent KG.

Agent NBA's `assemble` calls `kg_bundle` once per customer instead of calling each KG function;
`scripts/export_preview.py` uses it to give Agent CARDS real worklist data before valuation exists.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from nba.contracts import (
    Blocked, Candidate, ChannelItem, ConsentItem, DataQuality, ExclusionItem, Signal, SourceInfo, Triage,
)
from nba.kg.policy import Policy
from nba.kg.quality import data_quality
from nba.kg.rules import channel_view, consent_view, exclusion_view, generate_candidates
from nba.kg.segments import triage
from nba.kg.signals import extract_signals
from nba.state import CustomerState

# IndexRow numbers -> "table.column", for worklist tooltips (Summary.column_src, Q-CARDS-12)
COLUMN_SRC = {
    "age_band": "customer_master.birth_year",
    "city": "customer_master.city",
    "lines": "customer_value.active_business_lines",
    "clv_eur": "customer_value.clv_eur",
    "churn": "customer_value.churn_prob_12m",
    "archetype": "nba.kg.segments (README §6.13)",
    "urgency_tier": "nba.kg.segments (README §6.13)",
    "triggers": "nba.kg.signals (README §6.3)",
    "delta_clv": "nba.engine.value (README §6.5)",
    "p_accept": "nba_action_history.converted_within_14d (README §6.6)",
    "contact_cost": "value_assumptions.contact_cost_*",
}


def source_info(tables: dict[str, pd.DataFrame]) -> dict[str, SourceInfo]:
    """refresh / typical_latency per source sheet, from the workbook's `sources` sheet."""
    return {r["sheet"]: SourceInfo(refresh=r.get("refresh"), latency=r.get("typical_latency"))
            for r in tables["sources"].to_dict("records")}


@dataclass(frozen=True)
class KGBundle:
    signals: list[Signal]
    candidates: list[Candidate]
    blocked: list[Blocked]
    triage: Triage
    consent: list[ConsentItem]
    channels: list[ChannelItem]
    exclusions: list[ExclusionItem]
    data_quality: list[DataQuality]


def kg_bundle(state: CustomerState, policy: Policy, pop: pd.DataFrame, tone: str = "sie") -> KGBundle:
    """Signals, gated candidates (valuation None), blocked rows, triage, views and data-quality flags."""
    signals = extract_signals(state, policy)
    candidates, blocked = generate_candidates(state, signals, policy, tone)
    return KGBundle(
        signals=signals,
        candidates=candidates,
        blocked=blocked,
        triage=triage(state, signals, policy, pop),
        consent=consent_view(state, policy),
        channels=channel_view(state, policy),
        exclusions=exclusion_view(state, policy),
        data_quality=data_quality(state),
    )
