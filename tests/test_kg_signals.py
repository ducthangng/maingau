"""Signal counts and test-customer signals (README §6.3, §9)."""

import collections

EXPECTED_COUNTS = {"S1": 12, "S2": 2, "S3": 16, "S4": 143, "S5": 11, "S6": 80, "S7": 66, "S8": 33,
                   "S9": 48, "S10": 33, "S11": 161, "S12": 29, "S13": 39}


def test_signal_counts(kg_all):
    counts = collections.Counter(s.id for sig, *_ in kg_all.values() for s in sig)
    assert dict(counts) == EXPECTED_COUNTS


def test_s2_fires_for_the_spec_customers(kg_all):
    assert sorted(c for c, (sig, *_) in kg_all.items() if any(s.id == "S2" for s in sig)) == ["MG-100009", "MG-100659"]


def test_test_customer_signals(kg_all):
    ids = lambda c: {s.id for s in kg_all[c][0]}
    assert {"S1"} <= ids("MG-100051") and {"S1"} <= ids("MG-100060")
    assert {"S1", "S13"} <= ids("MG-100096")
    assert {"S1", "S12"} <= ids("MG-100186")
    assert {"S1", "S3", "S4"} <= ids("MG-100068")
    assert "S3" in ids("MG-100023") and "S3" in ids("MG-100112")
    assert "S2" in ids("MG-100009") and "S2" in ids("MG-100659")
    assert "S13" in ids("MG-100035") and "S13" in ids("MG-100087")
    assert {"S12", "S13"} <= ids("MG-100004")


def test_signals_carry_evidence_and_offers(kg_all):
    for sig, *_ in kg_all.values():
        for s in sig:
            assert s.detail and s.src
            assert s.offers or s.id == "S10"
