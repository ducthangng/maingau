"""Triage counts and representatives (README §6.13)."""

import collections


def test_archetype_and_tier_counts(kg_all):
    arch = collections.Counter(t.archetype.id for *_, t in kg_all.values())
    tiers = collections.Counter(t.urgency_tier for *_, t in kg_all.values())
    assert dict(arch) == {"A0": 49, "A1": 33, "A2": 342, "A3": 201, "A4": 75, "A5": 50}
    assert dict(tiers) == {"P1": 53, "P2": 62, "P3": 95, "P4": 261, "P5": 279}


def test_flags_and_outliers(kg_all):
    flags = collections.Counter(f.id for *_, t in kg_all.values() for f in t.flags)
    assert flags["service_critical"] == 53 and flags["no_profiling"] == 289 and flags["top_clv"] == 75
    assert sum(t.outlier for *_, t in kg_all.values()) == 154


def test_representatives(kg_all):
    assert kg_all["MG-100325"][3].archetype.id == "A1"
    assert kg_all["MG-100001"][3].archetype.id == "A2"


def test_every_customer_has_reasons(kg_all):
    for *_, t in kg_all.values():
        assert t.urgency_reasons and 0 <= t.urgency_score < 500
