"""KG audit: signals S1–S13 against the independent oracle and README §6.3."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from kg_audit_oracle import SIGNAL_COUNTS, SIGNAL_TABLE, oracle

from nba.kg.signals import extract_signals

SIGNALS = sorted(SIGNAL_TABLE, key=lambda s: int(s[1:]))


def _code_sets(kg_all) -> dict[str, set[str]]:
    out = {s: set() for s in SIGNALS}
    for cid, (sig, *_) in kg_all.items():
        for s in sig:
            out[s.id].add(cid)
    return out


@pytest.mark.parametrize("sid", SIGNALS)
def test_signal_customer_set_matches_oracle(kg_all, sid):
    got, want = _code_sets(kg_all)[sid], oracle().signal_sets[sid]
    assert got == want, f"{sid}: code-only {sorted(got - want)}, oracle-only {sorted(want - got)}"


@pytest.mark.parametrize("sid", SIGNALS)
def test_signal_count_matches_readme(kg_all, sid):
    assert len(_code_sets(kg_all)[sid]) == SIGNAL_COUNTS[sid]
    assert len(oracle().signal_sets[sid]) == SIGNAL_COUNTS[sid]


def test_s2_fires_for_exactly_the_two_spec_customers(kg_all):
    assert _code_sets(kg_all)["S2"] == {"MG-100009", "MG-100659"}


def test_s8_offers_follow_the_variant(kg_all):
    o = oracle()
    for cid, (sig, *_) in kg_all.items():
        for s in sig:
            if s.id == "S8":
                assert sorted(s.offers) == sorted(o.signal_offers(cid, "S8")), cid


def test_s10_uses_human_clicks_only(states, policy):
    """An apple_mpp_prefetch open (no click) never creates S10; a human click on the target does."""
    s = next(st for c, st in states.items() if c not in oracle().signal_sets["S10"])
    row = {"campaign_id": "NL-TEST", "customer_id": s.customer_id, "delivered": True,
           "opened_at": s.eval_time - timedelta(days=2), "open_client_class": "apple_mpp_prefetch",
           "clicked_at": None, "click_target": "heat_pump_article"}
    mpp = replace(s, rows=dict(s.rows, newsletter_performance=[row]))
    assert "S10" not in {x.id for x in extract_signals(mpp, policy)}
    human = replace(s, rows=dict(s.rows, newsletter_performance=[
        {**row, "open_client_class": "human", "clicked_at": s.eval_time - timedelta(days=2)}]))
    assert "S10" in {x.id for x in extract_signals(human, policy)}


def test_every_s10_source_row_is_a_human_click(kg_all, states):
    for cid, (sig, *_) in kg_all.items():
        if any(s.id == "S10" for s in sig):
            rows = [r for r in states[cid].rows["newsletter_performance"] if r.get("clicked_at")
                    and r.get("click_target") in ("heat_pump_article", "smart_living_landingpage")]
            assert rows and all(r.get("open_client_class") != "apple_mpp_prefetch" for r in rows), cid


def test_signal_metadata_matches_policy(kg_all, policy):
    for cid, (sig, *_) in kg_all.items():
        for s in sig:
            strength, purpose, _, _ = SIGNAL_TABLE[s.id]
            assert (s.strength, s.purpose) == (strength, purpose), (cid, s.id)
            assert s.label == policy.signals[s.id].label and s.src and "." in s.src, (cid, s.id)


def test_every_signal_has_a_date(kg_all):
    missing = sorted({s.id for sig, *_ in kg_all.values() for s in sig if not s.date})
    assert not missing, f"signals without a date (README §4.1 B4): {missing}"


def test_signal_evidence_points_to_real_rows(kg_all, states):
    keys = {"contract": [("energy_contracts", "contract_id"), ("mobile_contracts", "contract_id"),
                         ("autostrom_contracts", "contract_id")],
            "order": [("shop_orders", "order_id")], "ticket": [("service_interactions", "ticket_id")],
            "session": [("charge_sessions", "session_id")], "device": [("hems_devices", "device_id")],
            "click": [("newsletter_performance", "campaign_id")]}
    bad = []
    for cid, (sig, *_) in kg_all.items():
        rows = states[cid].rows
        for s in sig:
            assert s.evidence, (cid, s.id)
            for ref in s.evidence:
                kind, _, target = ref.partition(":")
                ok = kind in keys and any(r.get(col) == target for sheet, col in keys[kind] for r in rows[sheet])
                if not ok:
                    bad.append((cid, s.id, ref))
    assert not bad, bad[:20]


def test_q_kg_06_price_driver_without_s4(kg_all):
    """Documents the 2-customer gap behind Q-KG-06; the reasons go to the audit log."""
    gap = oracle().price_driver_without_s4()
    print("\nQ-KG-06:", gap)
    assert set(gap) == {"MG-100087", "MG-100335"}
    s4 = _code_sets(kg_all)["S4"]
    assert not set(gap) & s4
