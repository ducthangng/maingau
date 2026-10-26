"""Shared data contracts for the per-customer JSON (README §5.4 and §5.5).

Owner: Agent NBA. Agents KG and CARDS import these models and never edit them.
Changing a model means changing README §5.4/§5.5 in the same PR and telling the
other agents (log it in log/agent-nba.md under "Contract changes").

Every model forbids unknown keys, so a typo in a producer fails loudly.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
NO_ACTION = "NO_ACTION"

Channel = Literal[
    "newsletter_email", "email", "portal_popup", "app_push", "sms", "outbound_call", "service_agent"
]
ConsentType = Literal[
    "newsletter_email",
    "marketing_email",
    "marketing_phone",
    "marketing_sms",
    "portal_app_personalisation",
    "profiling_analytics",
]
ConsentStatus = Literal["granted", "not_given", "withdrawn"]
ToneValue = Literal["du", "sie"]
ActionType = Literal["sales", "upsell", "retention", "one_off", "service"]
Strength = Literal["strong", "medium", "weak"]
Purpose = Literal["contract", "device", "behavioural", "service"]
DecisionStatus = Literal["proposed", "approved", "overridden", "rejected", "revoked"]
Confidence = Literal["high", "medium", "low"]
RuleId = Literal[
    "CONSENT-CHANNEL",
    "CONSENT-PROFILING",
    "CHANNEL-AVAILABLE",
    "EXCL-DUNNING",
    "EXCL-CANCELLATION",
    "EXCL-OPEN-TICKET",
    "EXCL-AUTOSTROM-CANCELLED",
    "HOLDING-PRECONDITION",
    "CONTACT-CAP",
    "ECON-NONPOSITIVE",
    "DATA-MISSING",
    "BUSINESS-RULE",  # a Rule Center tier 2 rule; the B-xx / custom ID is in rule_center_id
]
# p_accept backoff levels (README §6.6): L3 offer_channel_tone, L2 offer_channel, L1 offer, L0 global.
PLevel = Literal["offer_channel_tone", "offer_channel", "offer", "global", "assumption"]
ChecklistKey = Literal[
    "consent_for_channel", "profiling_consent", "no_exclusion", "not_owned", "contact_cap", "data_fresh"
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _unset(v) -> bool:
    return v is None or v == {} or v == 0


# Rule Center fields (docs/rule-center.md) are left out of the JSON while unset, so the static export
# stays within its size budget; consumers read a missing key as null.
def omit_unset():
    return Field(default=None, exclude_if=_unset)


# ---------------------------------------------------------------- provenance (§5.3)


class Fact(Model):
    """One displayed value plus where it came from; the UI builds the tooltip from it."""

    v: Any = None
    src: str  # "table.column"
    updated_at: Optional[str] = None
    row_key: Optional[str] = None


class SourceInfo(Model):
    refresh: Optional[str] = None
    latency: Optional[str] = None


# ---------------------------------------------------------------- meta


class Versions(Model):
    policy: str
    value_model: str
    propensity: str
    templates: str
    rules: Optional[str] = None  # rule_set_version of the Rule Center (docs/rule-center.md §6)


class Meta(Model):
    eval_time: str
    snapshot_mode: Literal["provided", "strict_asof"] = "provided"
    events_applied_until: Optional[str] = None
    mode_default: Literal["marketing", "service"] = "marketing"
    versions: Versions
    state_revision: str


# ---------------------------------------------------------------- left card: profile (§4.1 A1–A5, B2–B3)


class Tone(Model):
    value: ToneValue
    method: Literal["text", "newsletter", "default"]
    evidence: str
    refs: list[str] = Field(default_factory=list)


class Header(Model):
    age_band: Fact
    city: Fact
    household_size: Fact
    tenure_years: Fact
    digital: dict[str, Fact]  # keys: portal_account, app_installed, language
    tone: Tone


class ChurnDriver(Model):
    label: str
    delta: Optional[float] = None


class Percentiles(Model):
    clv_all: Optional[float] = None
    clv_same_combo: Optional[float] = None
    combo: Optional[str] = None


class ValueRisk(Model):
    clv_eur: Fact
    annual_margin_eur: Fact
    cost_to_serve_12m_eur: Fact
    active_business_lines: Fact
    churn_prob_12m: Fact
    churn_drivers: list[ChurnDriver] = Field(default_factory=list)
    clv_service_impact_eur: Fact
    percentiles: Percentiles = Field(default_factory=Percentiles)


class ProductLine(Model):
    held: Optional[bool] = None  # None = no ownership data (internet)
    opportunity: bool = False
    items: list[dict[str, Any]] = Field(default_factory=list)  # values are Fact-shaped dicts
    note: Optional[str] = None


class Products(Model):
    energy: ProductLine
    autostrom: ProductLine
    mobile: ProductLine
    shop: ProductLine
    smart_living: ProductLine
    internet: ProductLine


class ConsentItem(Model):
    type: ConsentType
    status: ConsentStatus
    effective_status: ConsentStatus
    doi: Optional[bool] = None
    updated_at: Optional[str] = None
    source: Optional[str] = None
    override_reason: Optional[str] = None


class ChannelItem(Model):
    channel: Channel
    allowed: bool
    requires: list[ConsentType] = Field(default_factory=list)
    reason: str


class ExclusionItem(Model):
    rule_id: RuleId
    active: bool
    detail: Optional[str] = None
    src: str


class Highlight(Model):
    text: str
    basis: list[str]
    rarity: Optional[str] = None


class Trends(Model):
    charging: Optional[dict[str, Any]] = None
    portal: Optional[dict[str, Any]] = None
    newsletter: Optional[dict[str, Any]] = None
    service: Optional[dict[str, Any]] = None
    mobile_usage: Optional[dict[str, Any]] = None
    hems: Optional[dict[str, Any]] = None
    clv_note: str = "customer_value is a single snapshot; no CLV trend"


class Fatigue(Model):
    contacts_30d: int = 0
    contacts_90d: int = 0
    response_rate: Optional[float] = None
    repeatedly_ignored: list[str] = Field(default_factory=list)
    legacy_no_consent_check: int = 0
    agent_feedback: list[dict[str, Any]] = Field(default_factory=list)


class Profile(Model):
    header: Header
    value_risk: ValueRisk
    products: Products
    consent: list[ConsentItem]
    channels: list[ChannelItem]
    exclusions: list[ExclusionItem]
    highlights: list[Highlight] = Field(default_factory=list)
    trends: Trends = Field(default_factory=Trends)
    fatigue: Fatigue = Field(default_factory=Fatigue)


class TimelineItem(Model):
    id: str
    date: str
    future: bool = False
    kind: Literal["contract", "milestone", "service", "order", "consent", "marketing", "event"]
    line: Optional[str] = None
    title: str
    detail: Optional[str] = None
    src: str
    ref: Optional[str] = None
    flags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- KG outputs (§6.3, §6.11)


class Signal(Model):
    id: str  # "S1".."S13"
    label: str
    date: Optional[str] = None
    strength: Strength
    purpose: Purpose
    src: str
    evidence: list[str] = Field(default_factory=list)  # refs like "contract:EC-1", "order:SO-1"
    needs: list[str] = Field(default_factory=list)
    offers: list[str] = Field(default_factory=list)
    detail: Optional[str] = None


class PathStep(Model):
    kind: Literal["node", "edge"]
    type: str  # node: Customer/Signal/Need/Offer/Channel/Consent/...; edge: EMITTED/INDICATES/...
    id: Optional[str] = None
    label: Optional[str] = None
    ui_ref: Optional[str] = None  # header | value | product:<line> | consent:<type> | exclusion:<rule_id> | signal:<Sx> | timeline:<id> | trend:<name>


class Check(Model):
    rule_id: RuleId
    passed: bool
    detail: Optional[str] = None
    src: Optional[str] = None


class Blocked(Model):
    offer_id: str
    channel: Optional[Channel] = None
    rule_id: RuleId
    reason: str
    src: Optional[str] = None
    counterfactual_delta_clv: Optional[float] = None  # set by NBA for the "why blocked" view
    rule_center_id: Optional[str] = omit_unset()  # C-xx / B-xx
    until: Optional[str] = omit_unset()  # set when the block is temporary (DEFER_UNTIL): earliest allowed time


ArchetypeId = Literal["A1", "A2", "A3", "A4", "A5", "A0"]
UrgencyTier = Literal["P1", "P2", "P3", "P4", "P5"]
FlagId = Literal[
    "service_critical", "no_marketing_channel", "no_profiling", "negative_clv", "top_clv",
    "contact_fatigue", "annoyed_before", "prefers_en", "data_inconsistent",
]


class Archetype(Model):
    """Rule-based segment (README §6.13); never ML clustering, never payment data or age."""

    id: ArchetypeId
    name: str
    reason: str  # which facts put the customer here


class Flag(Model):
    id: FlagId
    label: str
    detail: Optional[str] = None
    src: Optional[str] = None


class Triage(Model):
    """Why this customer is near the top of the worklist (README §6.13). Computed by Agent KG."""

    archetype: Archetype
    urgency_tier: UrgencyTier
    urgency_score: float  # higher = more urgent; sort key inside a tier
    urgency_reasons: list[str] = Field(default_factory=list)
    deadline: Optional[str] = None  # e.g. price_guarantee_until when it drives urgency
    flags: list[Flag] = Field(default_factory=list)
    outlier: bool = False  # True if any flag marks a special need


# ---------------------------------------------------------------- NBA outputs (§6.5–§6.10)


class PSource(Model):
    mode: Literal["uplift", "rate", "assumption"]
    level: PLevel
    n_treated: int = 0
    conv_treated: int = 0
    n_control: int = 0
    conv_control: int = 0
    baseline_control: Optional[float] = None


class Valuation(Model):
    clv_now_shown: float  # customer_value.clv_eur
    clv_now_model: float  # clv() on the same inputs; ΔCLV uses this basis
    clv_after_accept: float
    clv_after_reject: float
    p_accept: float
    p_source: PSource
    contact_cost: float
    delta_clv: float
    confidence: Confidence


class Candidate(Model):
    tuple_id: str  # "<offer_id>|<channel>|<tone>"
    offer_id: str
    offer_name: str
    action_type: ActionType
    channel: Channel
    tone: ToneValue
    origin: Literal["signal", "service", "generic"] = "signal"  # generic = non-personalised catalog offer (D1)
    personalised: bool = True
    need: Optional[str] = None
    signals: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    valuation: Optional[Valuation] = None  # None until Agent NBA values it
    rank: Optional[int] = None
    deferred_until: Optional[str] = omit_unset()  # set when a temporary rule (frequency / cooldown / capacity) holds it back
    why: list[str] = Field(default_factory=list)  # plain-language reasons this fits (KG path facts + NBA evidence)
    notes: list[str] = Field(default_factory=list)  # caveats: low confidence, assumptions, data-quality flags
    path: list[PathStep] = Field(default_factory=list)


class Content(Model):
    language: Literal["de"] = "de"
    tone: ToneValue
    personalised: bool
    template_id: str
    subject: str
    body: str


class Chosen(Model):
    tuple_id: str  # NO_ACTION when nothing qualifies
    status: DecisionStatus = "proposed"
    send_at: Optional[str] = None
    deferred_until: Optional[str] = omit_unset()  # DEFER_UNTIL: every eligible tuple is held back until this time
    reason_line: str
    service_mode: bool = False
    agent_script: Optional[str] = None
    content: Optional[Content] = None


class Alternative(Model):
    tuple_id: str
    delta_clv: float
    why_lower: str


class LegacyComparison(Model):
    rule_id: Optional[str] = None
    offer_id: Optional[str] = None
    channel: Optional[str] = None
    decided_at: Optional[str] = None
    delta_clv_our_model: Optional[float] = None
    blocked_now_by: list[str] = Field(default_factory=list)


class ChecklistItem(Model):
    item: ChecklistKey
    passed: bool
    detail: Optional[str] = None
    src: Optional[str] = None


RuleTier = Literal["compliance", "business", "custom"]
RuleResultValue = Literal["pass", "block", "defer", "off", "n/a"]


class RuleResult(Model):
    """One Rule Center rule for one customer and run (docs/rule-center.md §4, §6)."""

    rule_id: str  # C-01..C-09, B-01..B-09, U-<n>
    tier: RuleTier
    name: str
    result: RuleResultValue
    detail: Optional[str] = omit_unset()  # the reason_template sentence shown on the card
    measured: dict[str, Any] = Field(default_factory=dict, exclude_if=_unset)  # e.g. {"count": 6, "limit": 5, "window_days": 90}
    until: Optional[str] = omit_unset()  # earliest allowed time for "defer"
    tuples: int = Field(default=0, exclude_if=_unset)  # offer × channel tuples it blocked or deferred


class ContactCounter(Model):
    rule_id: str
    label: str  # "Email", "Total", "Call", "SMS"
    count: int
    limit: int
    window_days: int


class RuleReport(Model):
    rule_set_version: str
    results: list[RuleResult] = Field(default_factory=list)
    counters: list[ContactCounter] = Field(default_factory=list)
    counter_line: str = ""  # "Email 3/5 (90 d) · Total 1/2 (30 d) · Call 0/1 (90 d)"


class DataQuality(Model):
    code: str  # FRESH-CDR | FRESH-HEMS | FRESH-VALUE | SNAPSHOT-INCONSISTENT | ...
    level: Literal["info", "warn"]
    detail: str


class DecisionLogEntry(Model):
    ts: str
    actor: str  # "engine" or a user name
    action: DecisionStatus
    tuple_id: Optional[str] = None
    from_tuple: Optional[str] = None
    to_tuple: Optional[str] = None
    reason: Optional[str] = None
    state_revision: Optional[str] = None
    versions: dict[str, str] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)


class CustomerCard(Model):
    schema_version: str = SCHEMA_VERSION
    customer_id: str
    meta: Meta
    sources: dict[str, SourceInfo] = Field(default_factory=dict)
    triage: Triage
    profile: Profile
    timeline: list[TimelineItem] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    blocked: list[Blocked] = Field(default_factory=list)
    chosen: Chosen
    alternatives: list[Alternative] = Field(default_factory=list)
    legacy_comparison: Optional[LegacyComparison] = None
    explanation_path: list[PathStep] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    data_quality: list[DataQuality] = Field(default_factory=list)
    decision_log: list[DecisionLogEntry] = Field(default_factory=list)
    rules: Optional[RuleReport] = None  # Rule Center: every rule's result for this customer


# ---------------------------------------------------------------- overview + API


class IndexRow(Model):
    customer_id: str
    age_band: Optional[str] = None
    city: Optional[str] = None
    lines: Optional[int] = None
    clv_eur: Optional[float] = None
    churn: Optional[float] = None
    archetype: ArchetypeId = "A0"
    archetype_name: Optional[str] = None
    urgency_tier: UrgencyTier = "P5"
    urgency_score: float = 0.0
    top_reason: Optional[str] = None  # first urgency reason, shown in the worklist
    flags: list[FlagId] = Field(default_factory=list)
    outlier: bool = False
    triggers: list[str] = Field(default_factory=list)  # signal IDs
    chosen_offer: str
    chosen_tuple: Optional[str] = None  # group key for bulk execution
    channel: Optional[str] = None
    tone: Optional[ToneValue] = None
    delta_clv: Optional[float] = None
    p_accept: Optional[float] = None
    contact_cost: Optional[float] = None
    confidence: Optional[Confidence] = None
    checklist_failed: list[ChecklistKey] = Field(default_factory=list)  # bulk approval refuses these rows
    deferred_until: Optional[str] = omit_unset()  # chosen action held back by a temporary rule until this time
    service_mode: bool = False
    personalised: Optional[bool] = None
    n_signals: int = 0
    n_candidates: int = 0
    n_blocked: int = 0
    exclusions: list[str] = Field(default_factory=list)


class Summary(Model):
    eval_time: str
    n_customers: int
    chosen_by_offer: dict[str, dict[str, float]] = Field(default_factory=dict)  # offer -> {"count", "sum_delta_clv"}
    blocked_by_rule: dict[str, int] = Field(default_factory=dict)
    no_action_by_reason: dict[str, int] = Field(default_factory=dict)
    signal_counts: dict[str, int] = Field(default_factory=dict)
    archetype_counts: dict[str, int] = Field(default_factory=dict)
    urgency_counts: dict[str, int] = Field(default_factory=dict)
    flag_counts: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, SourceInfo] = Field(default_factory=dict)  # refresh/latency per table, for worklist tooltips
    column_src: dict[str, str] = Field(default_factory=dict)  # IndexRow field -> "table.column"
    value_date: Optional[str] = None  # customer_value.clv_calc_date


class TupleRef(Model):
    offer_id: str
    channel: Channel
    tone: ToneValue


class DecisionRequest(Model):
    action: Literal["approve", "override", "reject"]
    user: str
    reason: Optional[str] = None
    tuple: Optional[TupleRef] = None  # required for "override"


# ---------------------------------------------------------------- Rule Center (docs/rule-center.md §6)

ConditionOp = Literal["=", "!=", ">=", "<=", "within_days"]


class Condition(Model):
    entity: str  # sheet name, e.g. energy_contracts; product_catalog = the offer itself
    column: str
    op: ConditionOp
    value: Any  # consent_status uses "<consent_type>:<status>"
    label: Optional[str] = None


class RuleNode(Model):
    """One rule in the Rule Center tree; also the shape of web/public/data/rules.json."""

    id: str  # C-01.., B-01.., U-<n>
    name: str
    tier: Literal["hard", "custom"]  # the card section: hard rules (C-xx, user hard rules) or customized
    active: bool = True
    locked: bool = False  # C-01..C-09: always on (tier 1 can only be tightened)
    target: Optional[str] = None
    kind: Optional[str] = None  # engine kind (channel_frequency, ..., condition); None for KG gates
    effect: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    condition: Optional[Condition] = None
    children: list[RuleNode] = Field(default_factory=list)


class OperatorOption(Model):
    id: str  # "<column>|<op>|<value>"
    column: str
    op: ConditionOp
    value: Any
    label: str


class Entity(Model):
    id: str
    label: str
    operators: list[OperatorOption] = Field(default_factory=list)


class RulesFile(Model):
    version: int = 1
    generated_at: str
    rule_set_version: str
    rules: list[RuleNode]
    entities: list[Entity] = Field(default_factory=list)


class RuleChange(Model):
    """PUT /api/rules/{id}: switch a rule or change its numbers (rule_id comes from the path; what-if needs it)."""

    rule_id: Optional[str] = None
    by: str = ""
    reason: Optional[str] = None
    active: Optional[bool] = None
    params: dict[str, Any] = Field(default_factory=dict)


class RuleCreate(Model):
    """POST /api/rules: a customized or hard rule from the Rule Center popup (sub-rules narrow the parent)."""

    by: str = ""
    name: Optional[str] = None
    hard: bool = False
    active: bool = True
    condition: Condition
    effect: Optional[str] = None  # default: block the matching offers, or all sales of matching customers
    children: list[RuleCreate] = Field(default_factory=list)
    parent: Optional[str] = None  # add as a sub-rule of an existing custom rule


def tuple_id(offer_id: str, channel: str, tone: str) -> str:
    return f"{offer_id}|{channel}|{tone}"
