"""KG audit: invariants over all 750 customers (README §7.1 "Done when", §9), checked against the oracle."""

from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from kg_audit_oracle import (
    CHANNELS, FLAG_COUNTS, INCONSISTENT_TICKETS, RULE_IDS, SALES_TYPES, SIGNAL_COUNTS, ARCHETYPE_COUNTS,
    TIER_COUNTS, oracle,
)

from nba.kg.bundle import kg_bundle
from nba.kg.quality import data_quality

REPO = Path(__file__).resolve().parents[1]


def _marketing(cands):
    return [c for c in cands if c.origin != "service"]


def test_no_tuple_without_channel_consent_and_availability(kg_all):
    o = oracle()
    for cid, (_, cands, _, _) in kg_all.items():
        allowed = o.allowed_channels(cid)
        for c in cands:
            if c.origin == "service":
                assert c.channel == "service_agent" and c.offer_id == "P-SV-01", (cid, c.tuple_id)
            else:
                assert c.channel in CHANNELS and c.channel in allowed, (cid, c.tuple_id)


def test_no_sales_tuple_while_an_exclusion_is_active(kg_all):
    o = oracle()
    for cid, (_, cands, _, _) in kg_all.items():
        if o.exclusions(cid):
            assert not [c.tuple_id for c in cands if c.action_type in SALES_TYPES], cid


def test_no_signal_or_personalised_tuple_without_profiling(kg_all):
    o = oracle()
    for cid, (_, cands, _, _) in kg_all.items():
        if not o.profiled(cid):
            assert not [c.tuple_id for c in cands if c.origin == "signal" or c.personalised], cid
            assert all(c.tone == "sie" for c in cands), cid


def test_no_tuple_for_an_owned_product(kg_all):
    o = oracle()
    bad = [(cid, c.tuple_id) for cid, (_, cands, _, _) in kg_all.items() for c in cands if o.owns(cid, c.offer_id)]
    assert not bad, bad[:20]


def test_contact_cap_respected(kg_all):
    o = oracle()
    for cid, (_, cands, _, _) in kg_all.items():
        if o.capped(cid):
            assert not _marketing(cands), cid


def test_every_signal_blocked_item_and_reason_has_provenance(kg_all):
    for cid, (sig, cands, blocked, tri) in kg_all.items():
        assert all(s.src for s in sig), cid
        for b in blocked:
            assert b.rule_id in RULE_IDS and b.reason, (cid, b)
        for c in cands:
            assert all(ch.rule_id in RULE_IDS for ch in c.checks), (cid, c.tuple_id)
        assert tri.archetype.reason and tri.urgency_reasons, cid


def test_every_flag_has_a_src(kg_all):
    missing = collections.Counter(f.id for *_, t in kg_all.values() for f in t.flags if not f.src)
    assert not missing, dict(missing)


# ---------------------------------------------------------------- data quality (§6.9)


def test_snapshot_inconsistent_covers_tickets_and_late_cdrs(states):
    o = oracle()
    flagged = {cid for cid, s in states.items() if any(d.code == "SNAPSHOT-INCONSISTENT" for d in data_quality(s))}
    want = {c for c in o.customers if o.late_cdr(c) or o.odd_ticket(c)}
    assert flagged == want, (sorted(flagged - want), sorted(want - flagged))
    assert len(want) == FLAG_COUNTS["data_inconsistent"] == 71
    owners = {c for c in o.customers if o.odd_ticket(c)}
    assert {r["ticket_id"] for c in owners for r in o.tickets[c] if r["ticket_id"] in INCONSISTENT_TICKETS} == INCONSISTENT_TICKETS
    late_rows = sum(1 for c in o.customers for r in o.charges[c] if r.get("cdr_received_at") and o.late_cdr(c)
                    and r["cdr_received_at"] > "2026-09-30 23:59:59")
    assert late_rows == 79


def test_data_quality_flags_never_block(states, policy, kg_all):
    codes = {d.code for s in states.values() for d in data_quality(s)}
    assert codes and not codes & RULE_IDS
    for cid, (_, _, blocked, _) in kg_all.items():
        assert {b.rule_id for b in blocked} <= RULE_IDS


# ---------------------------------------------------------------- bundle contract and determinism


@pytest.fixture(scope="module")
def bundles(states, policy, pop):
    return {cid: kg_bundle(s, policy, pop) for cid, s in states.items()}


def _bundle_json(b) -> str:
    def dump(v):
        return [x.model_dump(mode="json") for x in v] if isinstance(v, list) else v.model_dump(mode="json")

    return json.dumps({k: dump(getattr(b, k)) for k in b.__dataclass_fields__}, sort_keys=True)


def test_kg_bundle_validates_against_contracts(bundles):
    from nba import contracts as C

    models = {"signals": C.Signal, "candidates": C.Candidate, "blocked": C.Blocked, "triage": C.Triage,
              "consent": C.ConsentItem, "channels": C.ChannelItem, "exclusions": C.ExclusionItem,
              "data_quality": C.DataQuality}
    for cid, b in bundles.items():
        for field, model in models.items():
            value = getattr(b, field)
            for item in value if isinstance(value, list) else [value]:
                model.model_validate(item.model_dump(mode="json"))
        assert all(c.valuation is None for c in b.candidates), cid


def test_kg_bundle_json_is_byte_identical_across_runs(states, policy, pop, bundles):
    from nba.kg.policy import load_policy

    policy2 = load_policy()
    diffs = [cid for cid, s in states.items() if _bundle_json(kg_bundle(s, policy2, pop)) != _bundle_json(bundles[cid])]
    assert not diffs, diffs[:10]


def test_kg_report_counts_equal_oracle(tmp_path, monkeypatch):
    path = REPO / "scripts" / "kg_report.py"
    if not path.exists():
        pytest.fail("scripts/kg_report.py missing")
    spec = importlib.util.spec_from_file_location("kg_report_audit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["kg_report.py"])
    mod.main()
    text = (tmp_path / "out" / "kg_report.md").read_text(encoding="utf-8")

    def row(key):
        line = next(ln for ln in text.splitlines() if ln.startswith(f"| {key} |"))
        return int(line.strip("| \n").split("|")[-1])

    for sid, n in SIGNAL_COUNTS.items():
        assert row(sid) == n == len(oracle().signal_sets[sid]), sid
    for a, n in ARCHETYPE_COUNTS.items():
        line = next(ln for ln in text.splitlines() if ln.startswith(f"| {a} |"))
        assert int(line.split("|")[3]) == n, a
    for t, n in TIER_COUNTS.items():
        assert row(t) == n, t
    for f, n in FLAG_COUNTS.items():
        assert row(f) == n, f
    assert "Outliers: 154." in text
