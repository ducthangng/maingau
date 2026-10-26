"""Load and validate the KG policy (kg/policy.yaml + config/kg.yaml). Owner: Agent KG."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from nba.contracts import ArchetypeId, ConsentType
from nba.data import load_workbook
from nba.kg import predicates as P

REPO = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO / "kg" / "policy.yaml"
CONFIG_PATH = REPO / "config" / "kg.yaml"
CONSENT_TYPES = set(ConsentType.__args__)
ARCHETYPE_IDS = set(ArchetypeId.__args__)


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


def load_policy(path: str | Path = POLICY_PATH, config_path: str | Path = CONFIG_PATH, catalog=None) -> Policy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) if config_path else {}
    if catalog is None:
        catalog = load_workbook()["product_catalog"]
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
    policy = Policy(
        version=raw["version"],
        needs=raw["needs"],
        signals={sid: SignalDef(id=sid, label=s["label"], predicate=s["predicate"], strength=s["strength"],
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
        config=config or {},
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
    if set(policy.archetypes) != ARCHETYPE_IDS:
        out.append(f"archetypes must be exactly {sorted(ARCHETYPE_IDS)}")
    for sid in policy.config.get("signals", {}).get("enabled", []):
        if sid not in policy.signals:
            out.append(f"config enables unknown signal {sid}")
    for oid in policy.config.get("generic", {}).get("offers", []):
        if oid not in policy.offers or not policy.offers[oid].generic:
            out.append(f"config lists {oid} as generic but policy does not allow it")
    return out
