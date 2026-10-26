"""KG audit: ontology and policy integrity (README §4.3, §6.1–§6.4, §6.11, §7.1 "Done when")."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kg_audit_oracle import (
    CHANNELS, CONTACT_COST, DATA_MISSING_OFFERS, EDGE_TYPES, EXCLUSIONS, GENERIC_OFFERS, NEEDS, NODE_TYPES,
    NOT_HELD, REQUIRES, RULE_IDS, SALES_TYPES, SIGNAL_TABLE, oracle, raw,
)

REPO = Path(__file__).resolve().parents[1]
ONTOLOGY = yaml.safe_load((REPO / "kg" / "ontology.yaml").read_text(encoding="utf-8"))
POLICY_RAW = yaml.safe_load((REPO / "kg" / "policy.yaml").read_text(encoding="utf-8"))
CONFIG = yaml.safe_load((REPO / "config" / "kg.yaml").read_text(encoding="utf-8"))

# README §6.4 preconditions -> the policy's predicate names that implement them
REQUIRES_PREDICATES = {
    "active_electricity": "has_active_electricity", "price_guarantee_driver": "has_price_guarantee_driver",
    "smart_meter_on_active_electricity": "has_smart_meter", "active_mobile": "has_active_mobile",
    "hems_gateway": "has_hems_gateway", "home_battery": "has_home_battery",
    "wallbox_or_active_autostrom": "has_wallbox_or_ev", "active_energy": "has_active_energy",
}
NOT_HELD_PREDICATES = {
    "active_electricity": "has_active_electricity", "tariff_stromwaerme": "has_tariff_stromwaerme",
    "active_mobile": "has_active_mobile", "hems_gateway": "has_hems_gateway",
    "balkonkraftwerk_or_pv": "owns_pv_or_balkonkraftwerk", "wallbox_device_or_delivered": "owns_wallbox",
    "delivered_thermostats": "owns_thermostats", "smart_plug_device_or_delivered": "owns_smart_plug",
    "active_autostrom": "has_active_autostrom",
}


def test_yaml_files_load_and_load_policy_works(policy):
    assert ONTOLOGY["node_types"] and ONTOLOGY["edge_types"]
    assert POLICY_RAW["version"] == policy.version == CONFIG["policy_version"]
    assert policy.signals and policy.offers and policy.channels and policy.exclusions


def test_ontology_node_types_match_readme():
    got = set(ONTOLOGY["node_types"])
    assert got == NODE_TYPES, f"missing {sorted(NODE_TYPES - got)}, extra {sorted(got - NODE_TYPES)}"


def test_ontology_edge_types_match_readme():
    got = set(ONTOLOGY["edge_types"])
    assert got == EDGE_TYPES, f"missing {sorted(EDGE_TYPES - got)}, extra {sorted(got - EDGE_TYPES)}"


def test_every_policy_offer_is_in_the_catalog_and_all_18_are_covered(policy):
    catalog = set(oracle().catalog)
    assert len(catalog) == 18
    assert set(policy.offers) == catalog
    for o in policy.offers.values():
        row = oracle().catalog[o.id]
        assert (o.name, o.action_type, o.business_line) == (row["product_name"], row["action_type"], row["business_line"])


def test_every_signal_except_s10_indicates_a_need(policy):
    for s in policy.signals.values():
        if s.id == "S10":
            assert not s.indicates and set(s.reinforces) == {"N-HEAT-PUMP", "N-ENERGY-MANAGEMENT"}
        else:
            assert s.indicates and not s.reinforces, s.id


def test_s10_produces_no_tuple(kg_all):
    for cid, (sig, cands, _, _) in kg_all.items():
        s10 = [s for s in sig if s.id == "S10"]
        if s10:
            assert s10[0].offers == []
            assert not any(c.signals == ["S10"] for c in cands), cid


def test_every_need_is_addressed_and_labelled(policy):
    assert set(policy.needs) == set(NEEDS)
    for n, labels in policy.needs.items():
        assert policy.offers_for_need(n), n
        assert labels.get("label_en") and labels.get("label_de"), n


@pytest.mark.parametrize("sid", sorted(SIGNAL_TABLE, key=lambda s: int(s[1:])))
def test_signal_table_matches_readme(policy, sid):
    strength, purpose, needs, offers = SIGNAL_TABLE[sid]
    s = policy.signals[sid]
    assert (s.strength, s.purpose) == (strength, purpose)
    assert set(s.indicates or s.reinforces) == set(needs)
    derived = sorted({o for n in s.indicates for o in policy.offers_for_need(n)})
    assert derived == sorted(offers)


def test_channel_consent_map_and_availability_fields(policy):
    assert set(policy.channels) == set(CHANNELS)
    for ch, (consent, field) in CHANNELS.items():
        c = policy.channels[ch]
        assert c.consent == consent and c.requires_field == field, ch
        assert c.needs_doi == (ch == "newsletter_email"), ch


def test_service_agent_needs_no_consent_and_only_carries_p_sv_01(policy):
    assert policy.service_channel == "service_agent" and "service_agent" not in policy.channels
    service = [o.id for o in policy.offers.values() if o.action_type == "service"]
    assert service == ["P-SV-01"]
    from nba.kg.graph import policy_graph

    g = policy_graph(policy)
    carried = {u for u, v, d in g.edges(data=True) if d["type"] == "DELIVERED_VIA" and v == "channel:service_agent"}
    assert carried == {"P-SV-01"}


def test_workbook_contact_costs_match_readme():
    va = {r["parameter"]: float(r["value"]) for r in raw()["value_assumptions"].to_dict("records")}
    by_param = {"newsletter_email": "contact_cost_email_eur", "email": "contact_cost_email_eur",
                "sms": "contact_cost_sms_eur", "portal_popup": "contact_cost_popup_eur",
                "app_push": "contact_cost_popup_eur", "outbound_call": "contact_cost_call_eur"}
    for ch, param in by_param.items():
        assert va[param] == pytest.approx(CONTACT_COST[ch]), ch
    assert va["service_resolution_cost_eur"] == 15


def test_policy_channels_carry_contact_cost():
    """README §6.1 puts the contact cost column in kg/policy.yaml (owner Agent KG)."""
    chans = POLICY_RAW["channels"]
    missing = sorted(ch for ch in CHANNELS if "contact_cost_eur" not in (chans.get(ch) or {}))
    assert not missing, f"kg/policy.yaml channels without contact_cost_eur: {missing}"
    for ch in CHANNELS:
        assert chans[ch]["contact_cost_eur"] == pytest.approx(CONTACT_COST[ch]), ch


def test_exclusions_match_readme(policy):
    assert list(policy.exclusions) == EXCLUSIONS
    for e in policy.exclusions.values():
        assert set(e.blocks) == SALES_TYPES, e.id
        assert "service" not in e.blocks


@pytest.mark.parametrize("offer", sorted(set(REQUIRES) | set(NOT_HELD) | {"P-SV-01"}))
def test_preconditions_match_readme_table(policy, offer):
    o = policy.offers[offer]
    assert set(o.requires) == {REQUIRES_PREDICATES[k] for k in REQUIRES.get(offer, [])}, f"{offer} requires"
    assert set(o.not_held) == {NOT_HELD_PREDICATES[k] for k in NOT_HELD.get(offer, [])}, f"{offer} not_held"


def test_generic_offers_are_exactly_the_readme_list(policy):
    assert CONFIG["generic"]["offers"] == GENERIC_OFFERS
    assert [o.id for o in policy.generic_offers] == GENERIC_OFFERS
    assert {o.id for o in policy.offers.values() if o.generic} == set(GENERIC_OFFERS)


def test_data_missing_offers_are_never_generated(policy, kg_all):
    assert {o.id for o in policy.offers.values() if o.data_missing} == DATA_MISSING_OFFERS
    for cid, (_, cands, blocked, _) in kg_all.items():
        assert not {c.offer_id for c in cands} & DATA_MISSING_OFFERS, cid
        dm = sorted(b.offer_id for b in blocked if b.rule_id == "DATA-MISSING")
        assert dm == sorted(DATA_MISSING_OFFERS), cid  # once per customer
        assert all("not enough data" in b.reason for b in blocked if b.rule_id == "DATA-MISSING")


def test_every_predicate_name_resolves_to_a_function(policy):
    from nba.kg import predicates as P

    names = [(P.SIGNALS, s.predicate) for s in policy.signals.values()]
    names += [(P.HOLDINGS, n) for o in policy.offers.values() for n in o.requires + o.not_held]
    names += [(P.EXCLUSIONS, e.predicate) for e in policy.exclusions.values()]
    for registry, name in names:
        assert name in registry and callable(registry[name]), name
        assert getattr(P, name) is registry[name], name


def test_policy_layer_has_no_orphan_nodes(policy):
    from nba.kg.graph import policy_graph

    g = policy_graph(policy)
    orphans = sorted(n for n in g.nodes if g.degree(n) == 0)
    assert not orphans, orphans


def test_all_rule_ids_used_are_in_the_enum(policy, kg_all):
    import re

    src = (REPO / "nba" / "kg" / "rules.py").read_text(encoding="utf-8")
    used = set(re.findall(r'rule_id\s*=\s*"([A-Z-]+)"', src)) | set(policy.exclusions)
    assert used <= RULE_IDS, sorted(used - RULE_IDS)
    seen = {b.rule_id for _, _, blocked, _ in kg_all.values() for b in blocked}
    seen |= {ch.rule_id for _, cands, _, _ in kg_all.values() for c in cands for ch in c.checks}
    assert seen <= RULE_IDS, sorted(seen - RULE_IDS)
