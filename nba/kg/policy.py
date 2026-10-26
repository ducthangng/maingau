"""Load and validate the KG policy (kg/policy.yaml + config/kg.yaml). Owner: Agent KG."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from nba.contracts import ArchetypeId, ConsentType, RuleId
from nba.data import load_workbook
from nba.kg import predicates as P
from nba.kg.contacts import SOURCES as CONTACT_SOURCES
from nba.state import resolve_eval_time

REPO = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO / "kg" / "policy.yaml"
CONFIG_PATH = REPO / "config" / "kg.yaml"
CONSENT_TYPES = set(ConsentType.__args__)
ARCHETYPE_IDS = set(ArchetypeId.__args__)
RULE_IDS = set(RuleId.__args__)

# Every tunable threshold must be present; (min, max) bounds catch typos such as 0.35 → 35.
PARAMETER_BOUNDS = {
    "failed_charges_window_days": (1, 365), "failed_charges_min": (1, 100),
    # S4 cannot widen beyond 90 days: P-EN-02 requires the upstream churn driver "price guarantee ends <90d".
    "price_guarantee_window_days": (1, 90), "data_limit_min_months": (1, 3),
    "risk_churn_min": (0.0, 1.0), "p1_dunning_min": (1, 3), "p2_price_guarantee_days": (0, 730),
    "p3_dereg_recent_days": (1, 730), "top_clv_quantile": (0.5, 0.999), "fatigue_contacts_30d": (1, 30),
    "fatigue_ignored_90d": (1, 90), "roaming_late_hours": (1, 720), "value_stale_days": (1, 365),
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class SignalDef:
    id: str
    label: str
    predicate: str
    strength: str
    purpose: str
    indicates: tuple[str, ...] = ()
    reinforces: tuple[str, ...] = ()


@dataclass(frozen=True)
class OfferDef:
    id: str
    name: str
    business_line: str
    action_type: str
    addresses: tuple[str, ...]
    requires: tuple[str, ...]
    not_held: tuple[str, ...]
    generic: bool
    data_missing: str | None = None


@dataclass(frozen=True)
class ChannelDef:
    id: str
    consent: str
    needs_doi: bool = False
    requires_field: str | None = None


@dataclass(frozen=True)
class ExclusionDef:
    id: str
    label: str
    predicate: str
    blocks: tuple[str, ...]


@dataclass(frozen=True)
class Policy:
    version: str
    needs: dict[str, dict[str, str]]
    signals: dict[str, SignalDef]
    offers: dict[str, OfferDef]
    channels: dict[str, ChannelDef]
    service_channel: str
    exclusions: dict[str, ExclusionDef]
    archetypes: dict[str, str]
    config: dict[str, Any] = field(default_factory=dict)
    params: dict[str, float] = field(default_factory=dict)
    compliance: dict[str, dict[str, Any]] = field(default_factory=dict)  # Rule Center tier 1, C-01..C-09

    def offers_for_need(self, need: str) -> list[str]:
        return [o.id for o in self.offers.values() if need in o.addresses]

    @property
    def enabled_signals(self) -> list[SignalDef]:
        enabled = self.config.get("signals", {}).get("enabled") or list(self.signals)
        return [self.signals[s] for s in enabled]

    @property
    def generic_offers(self) -> list[OfferDef]:
        ids = self.config.get("generic", {}).get("offers") or [o.id for o in self.offers.values() if o.generic]
        return [self.offers[i] for i in ids]

    @property
    def contact_cap(self) -> tuple[int, int]:
        cap = self.config.get("contact_cap", {})
        return int(cap.get("max_contacts", 2)), int(cap.get("window_days", 30))

    @property
    def contact_cap_sources(self) -> tuple[str, ...]:
        """Which contacts count toward the cap (nba.kg.contacts.SOURCES); the history alone by default."""
        return tuple(self.config.get("contact_cap", {}).get("sources") or ("nba_history",))


def load_policy(path: str | Path = POLICY_PATH, config_path: str | Path = CONFIG_PATH, catalog=None,
                tables=None) -> Policy:
    """Parse and validate the policy. `config["eval_time"]` is always a concrete ISO time afterwards
    ("auto" is resolved from the data), so every consumer reads the same evaluation time."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = (yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) if config_path else {}) or {}
    if tables is None and (catalog is None or config.get("eval_time") in (None, "", "auto")):
        # Same workbook as the catalog the caller passed (nba.data stamps the source path on each table).
        source = getattr(catalog, "attrs", {}).get("workbook") if catalog is not None else None
        tables = load_workbook(source) if source else load_workbook()
    if catalog is None:
        catalog = tables["product_catalog"]
    if config.get("eval_time") in (None, "", "auto"):
        config["eval_time"] = resolve_eval_time(tables, "auto").isoformat()
        config["eval_time_source"] = "auto: end of latest customer_value.clv_calc_date"
    else:
        config["eval_time"] = resolve_eval_time(tables or {}, config["eval_time"]).isoformat()
    cat = {r["product_id"]: r for r in catalog.to_dict("records")}

    offers = {}
    for oid, o in raw["offers"].items():
        c = cat.get(oid, {})
        offers[oid] = OfferDef(
            id=oid, name=c.get("product_name", oid), business_line=c.get("business_line", ""),
            action_type=c.get("action_type", ""), addresses=tuple(o.get("addresses", [])),
            requires=tuple(o.get("requires", [])), not_held=tuple(o.get("not_held", [])),
            generic=bool(o.get("generic")), data_missing=o.get("data_missing"),
        )
    params = dict(raw.get("parameters") or {})
    try:  # labels may quote parameters, e.g. "≥ {failed_charges_min} failed charging sessions"
        labels = {sid: s["label"].format(**params) for sid, s in raw["signals"].items()}
    except (KeyError, IndexError, ValueError) as exc:
        raise PolicyError(f"kg/policy.yaml signal label refers to an unknown parameter: {exc}") from exc
    policy = Policy(
        version=raw["version"],
        needs=raw["needs"],
        signals={sid: SignalDef(id=sid, label=labels[sid], predicate=s["predicate"], strength=s["strength"],
                                purpose=s["purpose"], indicates=tuple(s.get("indicates", [])),
                                reinforces=tuple(s.get("reinforces", [])))
                 for sid, s in raw["signals"].items()},
        offers=offers,
        channels={cid: ChannelDef(id=cid, consent=c["consent"], needs_doi=bool(c.get("needs_doi")),
                                  requires_field=c.get("requires_field"))
                  for cid, c in raw["channels"].items()},
        service_channel=raw["service_channel"],
        exclusions={eid: ExclusionDef(id=eid, label=e["label"], predicate=e["predicate"], blocks=tuple(e["blocks"]))
                    for eid, e in raw["exclusions"].items()},
        archetypes={aid: a["name"] for aid, a in raw["archetypes"].items()},
        config=config,
        params=params,
        compliance={cid: dict(c) for cid, c in (raw.get("compliance") or {}).items()},
    )
    problems = validate(policy, set(cat))
    if problems:
        raise PolicyError("kg/policy.yaml is invalid:\n- " + "\n- ".join(problems))
    return policy


def validate(policy: Policy, catalog_ids: set[str]) -> list[str]:
    """Integrity rules from README §7.1; returns human-readable problems (empty = valid)."""
    out: list[str] = []
    if set(policy.offers) != catalog_ids:
        out.append(f"offers differ from product_catalog: missing {sorted(catalog_ids - set(policy.offers))}, "
                   f"unknown {sorted(set(policy.offers) - catalog_ids)}")
    for s in policy.signals.values():
        if s.predicate not in P.SIGNALS:
            out.append(f"{s.id}: predicate {s.predicate!r} not found")
        if not s.indicates and not s.reinforces:
            out.append(f"{s.id}: indicates no need")
        for n in s.indicates + s.reinforces:
            if n not in policy.needs:
                out.append(f"{s.id}: unknown need {n}")
    for n in policy.needs:
        if not policy.offers_for_need(n):
            out.append(f"{n}: no offer addresses this need")
        if not any(n in s.indicates for s in policy.signals.values()):
            out.append(f"{n}: no signal indicates this need")
    for o in policy.offers.values():
        for name in o.requires + o.not_held:
            if name not in P.HOLDINGS:
                out.append(f"{o.id}: holding predicate {name!r} not found")
        for n in o.addresses:
            if n not in policy.needs:
                out.append(f"{o.id}: unknown need {n}")
    for c in policy.channels.values():
        if c.consent not in CONSENT_TYPES:
            out.append(f"channel {c.id}: unknown consent {c.consent}")
    for e in policy.exclusions.values():
        if e.predicate not in P.EXCLUSIONS:
            out.append(f"{e.id}: predicate {e.predicate!r} not found")
    for name, (lo, hi) in PARAMETER_BOUNDS.items():
        v = policy.params.get(name)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            out.append(f"parameter {name} is missing or not a number")
        elif not lo <= v <= hi:
            out.append(f"parameter {name} = {v} outside [{lo}, {hi}]")
    for name in set(policy.params) - set(PARAMETER_BOUNDS):
        out.append(f"unknown parameter {name}")
    if set(policy.archetypes) != ARCHETYPE_IDS:
        out.append(f"archetypes must be exactly {sorted(ARCHETYPE_IDS)}")
    for sid in policy.config.get("signals", {}).get("enabled", []):
        if sid not in policy.signals:
            out.append(f"config enables unknown signal {sid}")
    for oid in policy.config.get("generic", {}).get("offers", []):
        if oid not in policy.offers or not policy.offers[oid].generic:
            out.append(f"config lists {oid} as generic but policy does not allow it")
    cap_max, window = policy.contact_cap
    if cap_max < 1 or window < 1:
        out.append("contact_cap: max_contacts and window_days must be at least 1")
    unknown = sorted(set(policy.contact_cap_sources) - set(CONTACT_SOURCES))
    if unknown:
        out.append(f"contact_cap: unknown source(s) {unknown}; use {list(CONTACT_SOURCES)}")
    if sorted(policy.compliance) != [f"C-0{i}" for i in range(1, 10)]:
        out.append("compliance must list exactly C-01 … C-09 (docs/rule-center.md §2)")
    for cid, c in policy.compliance.items():
        if not c.get("label") or not (c.get("kg_rules") or c.get("enforced_by")):
            out.append(f"compliance {cid}: needs a label and kg_rules or enforced_by")
        for rule in c.get("kg_rules") or []:
            if rule not in RULE_IDS:
                out.append(f"compliance {cid}: unknown KG rule {rule}")
    return out
