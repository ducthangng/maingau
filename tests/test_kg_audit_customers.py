"""KG audit: the README §9 test customers at KG level (signals, allowed tuples, blocked reasons; not `chosen`).

Each customer's verified facts are first re-checked in the raw workbook (premise tests), so a failing
KG assertion can never be caused by a wrong premise.
"""

from __future__ import annotations

import pytest

from kg_audit_oracle import SALES_TYPES, oracle, raw


def _rows(sheet, cid):
    return [r for r in raw()[sheet].to_dict("records") if r.get("customer_id") == cid]


def _consent(cid):
    return {r["consent_type"]: r["status"] for r in _rows("consent_status", cid)}


def _gas_dereg(cid):
    return sorted(r["meter_deregistered_at"][:10] for r in _rows("energy_contracts", cid)
                  if r["commodity"] == "gas" and r.get("meter_deregistered_at"))


def _sig(kg_all, cid):
    return {s.id for s in kg_all[cid][0]}


def _cands(kg_all, cid):
    return kg_all[cid][1]


def _blocked(kg_all, cid):
    return kg_all[cid][2]


# ---------------------------------------------------------------- premises (README §9 "verified facts")

PREMISES = {
    "MG-100051": lambda: _gas_dereg("MG-100051") == ["2026-09-13"] and _consent("MG-100051")["marketing_email"] == "withdrawn"
    and _consent("MG-100051")["profiling_analytics"] == "granted"
    and all(_consent("MG-100051")[t] == "granted" for t in ("newsletter_email", "marketing_phone", "portal_app_personalisation"))
    and any(r["tariff"] == "StromAktiv" and r["status"] == "active" and r["meter_type"] == "smart_meter_imsys"
            for r in _rows("energy_contracts", "MG-100051")),
    "MG-100060": lambda: _gas_dereg("MG-100060") == ["2026-08-29"]
    and {t for t, s in _consent("MG-100060").items() if s == "granted" and t != "profiling_analytics"} == {"marketing_phone"}
    and _consent("MG-100060")["newsletter_email"] == "withdrawn",
    "MG-100096": lambda: max(int(r["dunning_level"]) for r in _rows("energy_contracts", "MG-100096")) == 3
    and _gas_dereg("MG-100096") == ["2026-07-24"] and float(_rows("customer_value", "MG-100096")[0]["churn_prob_12m"]) == 0.36,
    "MG-100186": lambda: any(r["ticket_id"] == "TK-200745" and r["status"] == "open" and r["category"] == "complaint"
                             and r["created_at"].startswith("2026-09-20") for r in _rows("service_interactions", "MG-100186"))
    and _gas_dereg("MG-100186") == ["2026-09-12"],
    "MG-100068": lambda: _gas_dereg("MG-100068") == ["2026-09-10"]
    and any(r["product_name"] == "Wallbox 11 kW" and r["order_status"] == "delivered" and r["order_created_at"].startswith("2025-12-28")
            for r in _rows("shop_orders", "MG-100068"))
    and not _rows("autostrom_contracts", "MG-100068")
    and any(r["price_guarantee_until"] and r["price_guarantee_until"].startswith("2026-10-08") for r in _rows("energy_contracts", "MG-100068"))
    and all(_consent("MG-100068")[t] == "granted" for t in ("profiling_analytics", "newsletter_email", "marketing_email", "portal_app_personalisation")),
    "MG-100023": lambda: any(r["product_name"] == "Wallbox 11 kW" and r["order_status"] == "delivered"
                             and r["order_created_at"].startswith("2025-08-14") for r in _rows("shop_orders", "MG-100023"))
    and all(_consent("MG-100023")[t] == "granted" for t in ("profiling_analytics", "newsletter_email", "portal_app_personalisation"))
    and _consent("MG-100023")["marketing_email"] == "withdrawn" and not oracle().exclusions("MG-100023"),
    "MG-100112": lambda: any(r["product_name"] == "Wallbox 11 kW" and r["order_created_at"].startswith("2024-10-25")
                             for r in _rows("shop_orders", "MG-100112"))
    and {r["commodity"] for r in _rows("energy_contracts", "MG-100112")} == {"gas"}
    and _consent("MG-100112")["profiling_analytics"] != "granted"
    and {t for t, s in _consent("MG-100112").items() if s == "granted"} == {"marketing_phone"},
    "MG-100009": lambda: len(oracle().failed_charges_30d("MG-100009")) == 3
    and {t for t, s in _consent("MG-100009").items() if s == "granted"} == {"portal_app_personalisation", "profiling_analytics"},
    "MG-100659": lambda: len(oracle().failed_charges_30d("MG-100659")) == 3
    and "low CSAT" in (_rows("customer_value", "MG-100659")[0]["churn_drivers"] or ""),
    "MG-100035": lambda: any(r["status"] == "cancellation_pending" and r["commodity"] == "electricity"
                             and r["cancellation_received_at"].startswith("2026-09-04") for r in _rows("energy_contracts", "MG-100035"))
    and float(_rows("customer_value", "MG-100035")[0]["churn_prob_12m"]) == 0.95,
    "MG-100087": lambda: any(r["status"] == "cancellation_pending" and r["cancellation_received_at"].startswith("2026-09-22")
                             for r in _rows("energy_contracts", "MG-100087"))
    and any(r["status"] == "active" for r in _rows("autostrom_contracts", "MG-100087")),
    "MG-100004": lambda: _consent("MG-100004")["profiling_analytics"] != "granted"
    and any(r["ticket_id"] == "TK-200772" and r["status"] == "open" and r["category"] == "complaint"
            for r in _rows("service_interactions", "MG-100004"))
    and max(int(r["dunning_level"]) for r in _rows("energy_contracts", "MG-100004")) == 2,
    "MG-100012": lambda: _consent("MG-100012")["profiling_analytics"] != "granted"
    and {r["tariff"] for r in _rows("energy_contracts", "MG-100012")} >= {"StromGarant"}
    and {r["commodity"] for r in _rows("energy_contracts", "MG-100012")} == {"electricity", "gas"}
    and all(_consent("MG-100012")[t] == "granted" for t in ("newsletter_email", "marketing_phone", "portal_app_personalisation")),
}


@pytest.mark.parametrize("cid", sorted(PREMISES))
def test_premise_holds_in_raw_data(cid):
    assert PREMISES[cid](), f"README §9 verified facts do not hold for {cid}"


# ---------------------------------------------------------------- KG-level expectations


def test_mg_100051(kg_all):
    assert "S1" in _sig(kg_all, "MG-100051")
    cands = _cands(kg_all, "MG-100051")
    assert any(c.offer_id == "P-EN-03" and c.origin == "signal" for c in cands)
    assert not any(c.channel == "email" for c in cands)
    assert any(b.offer_id == "*" and b.channel == "email" and b.rule_id == "CONSENT-CHANNEL" and "marketing_email" in b.reason
               for b in _blocked(kg_all, "MG-100051"))


def test_mg_100060_only_outbound_call(kg_all):
    assert "S1" in _sig(kg_all, "MG-100060")
    en03 = {c.channel for c in _cands(kg_all, "MG-100060") if c.offer_id == "P-EN-03"}
    assert en03 == {"outbound_call"}
    assert {c.channel for c in _cands(kg_all, "MG-100060") if c.origin != "service"} == {"outbound_call"}


def test_mg_100096_dunning_blocks_sales_service_allowed(kg_all):
    cands, blocked = _cands(kg_all, "MG-100096"), _blocked(kg_all, "MG-100096")
    assert {"S1", "S13"} <= _sig(kg_all, "MG-100096")
    assert not [c for c in cands if c.action_type in SALES_TYPES]
    assert any(b.offer_id == "*" and b.rule_id == "EXCL-DUNNING" for b in blocked)
    assert any(b.offer_id == "P-EN-03" and b.rule_id == "EXCL-DUNNING" for b in blocked)
    svc = [c for c in cands if c.offer_id == "P-SV-01"]
    assert len(svc) == 1 and svc[0].channel == "service_agent" and "S13" in svc[0].signals


def test_mg_100186_open_complaint(kg_all):
    s12 = next(s for s in kg_all["MG-100186"][0] if s.id == "S12")
    assert "ticket:TK-200745" in s12.evidence
    cands = _cands(kg_all, "MG-100186")
    assert {c.offer_id for c in cands} == {"P-SV-01"} and cands[0].channel == "service_agent"
    assert any(b.offer_id == "*" and b.rule_id == "EXCL-OPEN-TICKET" for b in _blocked(kg_all, "MG-100186"))


def test_mg_100068_competing_offers(kg_all):
    assert {"S1", "S3", "S4"} <= _sig(kg_all, "MG-100068")
    offers = {c.offer_id for c in _cands(kg_all, "MG-100068")}
    assert {"P-EN-03", "P-AS-01", "P-EN-02", "P-SL-01"} <= offers


def test_mg_100023_s3_is_the_only_signal_source(kg_all):
    sig_cands = [c for c in _cands(kg_all, "MG-100023") if c.origin == "signal"]
    assert sig_cands and {s for c in sig_cands for s in c.signals} == {"S3"}
    assert any(c.offer_id == "P-AS-01" for c in sig_cands)


def test_mg_100112_no_profiling_generic_call(kg_all):
    blocked = _blocked(kg_all, "MG-100112")
    assert any(b.rule_id == "CONSENT-PROFILING" and b.reason.startswith("S3 ") for b in blocked)
    cands = {c.tuple_id: c for c in _cands(kg_all, "MG-100112")}
    c = cands["P-EN-01|outbound_call|sie"]
    assert c.origin == "generic" and not c.personalised
    assert not any(x.personalised or x.origin == "signal" for x in cands.values())


@pytest.mark.parametrize("cid", ["MG-100009", "MG-100659"])
def test_failed_charging_service_tuple(kg_all, cid):
    assert "S2" in _sig(kg_all, cid)
    svc = [c for c in _cands(kg_all, cid) if c.offer_id == "P-SV-01"]
    assert len(svc) == 1 and svc[0].channel == "service_agent" and "S2" in svc[0].signals


@pytest.mark.parametrize("cid", ["MG-100035", "MG-100087"])
def test_cancellation_pending_no_sales(kg_all, cid):
    assert not [c for c in _cands(kg_all, cid) if c.action_type in SALES_TYPES]
    assert any(b.offer_id == "*" and b.rule_id == "EXCL-CANCELLATION" for b in _blocked(kg_all, cid))


def test_mg_100004_service_only(kg_all):
    cands = _cands(kg_all, "MG-100004")
    assert [c.offer_id for c in cands] == ["P-SV-01"]
    assert cands[0].channel == "service_agent" and not cands[0].personalised and cands[0].tone == "sie"
    assert {"S12", "S13"} <= set(cands[0].signals)


def test_mg_100012_generic_only(kg_all):
    cands = _cands(kg_all, "MG-100012")
    assert cands and all(c.origin == "generic" and not c.personalised and c.tone == "sie" for c in cands)


@pytest.mark.parametrize("cid,arch", [("MG-100325", "A1"), ("MG-100001", "A2")])
def test_representatives(kg_all, cid, arch):
    assert kg_all[cid][3].archetype.id == arch == oracle().archetype(cid)
