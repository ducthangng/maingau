"""Read-only source audit, not a test of an implemented NBA engine.

Uses openpyxl for extraction only; never modifies the provided workbook/JSONL.
Run with Python providing openpyxl. Writes audit-results.json beside this script.
"""

from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "MAINGAU"
CUTOFF = datetime(2026, 9, 30, 23, 59, 59)


def stamp(value):
    return datetime.fromisoformat(str(value))


def clv(margin, serve_cost, churn):
    return sum((margin - serve_cost) * (1 - churn) ** (t - 1) / 1.06 ** t
               for t in range(1, 11))


workbook = openpyxl.load_workbook(BASE / "data/maingau_nba_mockdata.xlsx",
                                read_only=True, data_only=True)
tables = {}
for sheet in workbook:
    rows = iter(sheet.values)
    headers = next(rows)
    tables[sheet.title] = [dict(zip(headers, row)) for row in rows if any(v is not None for v in row)]
workbook.close()

events = [json.loads(line) for line in (BASE / "data/event_stream_2026-10-01.jsonl").read_text().splitlines()
          if line.strip()]
unique = {}
duplicate_conflicts = []
for event in events:
    event_id = event["event_id"]
    if event_id in unique and unique[event_id] != event:
        duplicate_conflicts.append(event_id)
    unique.setdefault(event_id, event)
event_rows = list(unique.values())

history = tables["nba_action_history"]
delivered = [r for r in history if r["delivery_status"] == "delivered" and not r["control_group"]]
control = [r for r in history if r["control_group"]]
consents = {(r["customer_id"], r["consent_type"]): r for r in tables["consent_status"]}
channel_consent = {
    "newsletter_email": "newsletter_email", "outbound_call": "marketing_phone",
    "sms": "marketing_sms", "portal_popup": "portal_app_personalisation",
    "app_push": "portal_app_personalisation",
}
withdrawn_before = []
for action in delivered:
    consent = consents[(action["customer_id"], channel_consent[action["channel"]])]
    if consent["status"] == "withdrawn" and stamp(consent["updated_at"]) < stamp(action["decided_at"]):
        withdrawn_before.append(action)

campaigns = {r["campaign_id"]: r for r in tables["newsletter_campaigns"]}
unsubscribe_proxy_actions = []
for action in delivered:
    if action["channel"] != "newsletter_email":
        continue
    if any(r["customer_id"] == action["customer_id"] and r["unsubscribed"]
           and stamp(campaigns[r["campaign_id"]]["sent_at"]) < stamp(action["decided_at"])
           for r in tables["newsletter_performance"]):
        unsubscribe_proxy_actions.append(action)

dunning = {r["customer_id"] for r in tables["energy_contracts"] if r["dunning_level"] >= 1}
open_complaints = {r["customer_id"] for r in tables["service_interactions"]
                   if r["category"] == "complaint" and r["status"] != "closed"}
cancellations = {r["customer_id"] for r in tables["energy_contracts"]
                 if r["cancellation_received_at"] or r["status"] == "cancellation_pending"}
strict_open_complaints = {r["customer_id"] for r in tables["service_interactions"]
                          if r["category"] == "complaint" and stamp(r["created_at"]) <= CUTOFF
                          and (not r["resolved_at"] or stamp(r["resolved_at"]) > CUTOFF)}

active_auto = {r["customer_id"]: r for r in tables["autostrom_contracts"] if r["status"] == "active"}
auto_actions = [r for r in delivered if r["offer_id"] == "P-AS-01"]
auto_held_at_decision = [r for r in auto_actions if r["customer_id"] in active_auto
                        and stamp(active_auto[r["customer_id"]]["start_date"]) <= stamp(r["decided_at"])]
energy_customers = {r["customer_id"] for r in tables["energy_contracts"] if r["status"] == "active"}
mobile_customers = {r["customer_id"] for r in tables["mobile_contracts"] if r["status"] == "active"}
hems_customers = {r["customer_id"] for r in tables["hems_devices"]}
late_cdrs = [r for r in tables["charge_sessions"] if stamp(r["cdr_received_at"]) > CUTOFF]
future_resolutions = [r for r in tables["service_interactions"]
                      if r["resolved_at"] and stamp(r["resolved_at"]) > CUTOFF]
values = tables["customer_value"]
errors = [abs(clv(r["annual_margin_eur"], r["cost_to_serve_12m_eur"], r["churn_prob_12m"])
              - r["clv_eur"]) for r in values]
mg9 = next(r for r in values if r["customer_id"] == "MG-100009")
mg9_before = clv(mg9["annual_margin_eur"], mg9["cost_to_serve_12m_eur"], mg9["churn_prob_12m"])
mg9_after = clv(mg9["annual_margin_eur"] + 114, mg9["cost_to_serve_12m_eur"],
               mg9["churn_prob_12m"] - .02)

paths = [BASE / "MAINGAU-pipeline-va-diem-khac-biet.md", BASE / "Hackathon_slides_for_MAINGAU.pdf",
         BASE / "data/maingau_nba_mockdata.xlsx", BASE / "data/event_stream_2026-10-01.jsonl"]
results = {
    "method": "Source counts and reconstructed formula diagnostics; not product implementation tests",
    "snapshot_cutoff_assumption": CUTOFF.isoformat(),
    "files": [{"path": str(p.relative_to(ROOT)), "sha256": sha256(p.read_bytes()).hexdigest()} for p in paths],
    "sheet_rows_excluding_header": {key: len(value) for key, value in tables.items()},
    "sheet_count": len(tables), "source_registry_rows": len(tables["sources"]),
    "event_stream": {
        "raw": len(events), "unique": len(event_rows), "duplicates": len(events) - len(event_rows),
        "conflicting_duplicate_ids": duplicate_conflicts,
        "unique_event_type_counts": dict(Counter(e["event_type"] for e in event_rows)),
        "adjacent_occurred_at_backsteps_in_ingestion_order": sum(stamp(b["occurred_at"]) < stamp(a["occurred_at"])
                                                                  for a, b in zip(event_rows, event_rows[1:])),
        "ingested_at_backsteps": sum(stamp(b["ingested_at"]) < stamp(a["ingested_at"])
                                     for a, b in zip(event_rows, event_rows[1:])),
        "max_arrival_delay_hours": max((stamp(e["ingested_at"]) - stamp(e["occurred_at"])).total_seconds()
                                       for e in event_rows) / 3600,
        "last_ingested_at": max(e["ingested_at"] for e in event_rows),
    },
    "history": {
        "total": len(history), "delivered_noncontrol": len(delivered), "control_rows": len(control),
        "delivered_conversions": sum(bool(r["converted_within_14d"]) for r in delivered),
        "control_conversions": sum(bool(r["converted_within_14d"]) for r in control),
        "customers_appearing_in_both_treatment_and_control": len({r["customer_id"] for r in delivered}
                                                                & {r["customer_id"] for r in control}),
        "immature_14d_labels_at_snapshot": sum(stamp(r["decided_at"]) + timedelta(days=14) > CUTOFF for r in history),
        "offers_without_history": [r["product_id"] for r in tables["product_catalog"]
                                   if r["product_id"] not in {a["offer_id"] for a in history}],
    },
    "historical_diagnostics": {
        "assumed_channel_consent_mapping": channel_consent,
        "delivered_after_last_recorded_withdrawal": len(withdrawn_before),
        "withdrawal_counts_by_channel": dict(Counter(r["channel"] for r in withdrawn_before)),
        "newsletter_actions_after_campaign_sent_with_unsubscribe_flag": len(unsubscribe_proxy_actions),
        "unsubscribe_timestamp_missing": "No unsubscribe_at column; 70 is a send-time proxy, not confirmed post-unsubscribe count",
        "actions_to_customers_dunning_at_snapshot": sum(r["customer_id"] in dunning for r in delivered),
        "dunning_history_missing": "No dunning_since timestamp; snapshot dunning is not historical dunning at action time",
        "autostrom_delivered": len(auto_actions),
        "autostrom_delivered_to_active_holders_at_snapshot": sum(r["customer_id"] in active_auto for r in auto_actions),
        "autostrom_active_contract_start_not_after_action": len(auto_held_at_decision),
    },
    "snapshot_diagnostics": {
        "dunning_customers": len(dunning), "open_complaint_customers_by_status": len(open_complaints),
        "cancellation_customers": len(cancellations), "blocked_union_by_status": len(dunning | open_complaints | cancellations),
        "open_complaint_customers_reconstructed_at_cutoff": len(strict_open_complaints),
        "active_autostrom_only_excluding_active_energy_mobile_and_any_HEMS": len(set(active_auto) - energy_customers - mobile_customers - hems_customers),
        "cdr_received_after_snapshot": len(late_cdrs),
        "cdr_customers_received_after_snapshot": len({r["customer_id"] for r in late_cdrs}),
        "sessions_ended_after_snapshot": sum(stamp(r["ended_at"]) > CUTOFF for r in tables["charge_sessions"]),
        "resolved_after_snapshot": [{k: r[k] for k in ["ticket_id", "customer_id", "category", "status", "resolved_at"]}
                                     for r in future_resolutions],
        "guest_order_lines": sum(r["customer_id"] is None for r in tables["shop_orders"]),
    },
    "source_counts": {
        "machine_opens": sum(r["opened_at"] is not None and r["open_client_class"] == "apple_mpp_prefetch" for r in tables["newsletter_performance"]),
        "human_opens": sum(r["opened_at"] is not None and r["open_client_class"] == "human" for r in tables["newsletter_performance"]),
        "nonempty_service_message_rows": sum(bool(r["message_text"]) for r in tables["service_interactions"]),
        "distinct_nonempty_service_texts_including_English": len({r["message_text"] for r in tables["service_interactions"] if r["message_text"]}),
        "feedback_action_counts": dict(Counter(r["agent_action"] for r in tables["service_nba_feedback"])),
        "feedback_dismiss_reasons": dict(Counter(r["dismiss_reason"] for r in tables["service_nba_feedback"] if r["dismiss_reason"])),
    },
    "clv_reconstruction": {"median_absolute_error_eur": median(errors), "max_absolute_error_eur": max(errors),
                           "rows_with_error_above_1eur": sum(e > 1 for e in errors)},
    "MG100009_formula_diagnostic": {
        "assumptions": "Catalog P-EN-01 additive margin/churn; p_accept=0.034 illustrative; no contact cost; no open complaint/dunning rejection penalty",
        "model_clv_before": mg9_before, "model_clv_after_accept": mg9_after,
        "gain_if_accepted": mg9_after - mg9_before,
        "illustrative_expected_gain": .034 * (mg9_after - mg9_before),
        "meaning": "Positive under these assumptions; an open service issue does not algebraically force all sales scores negative",
    },
    "scenario_events": [e for e in event_rows if e["customer_id"] in ["MG-100003", "MG-100004", "MG-100005", "MG-100009", "MG-100125"]
                        and e["event_type"] not in ["portal_login", "page_viewed", "charge_session_started"]],
}

assert results["event_stream"]["unique"] == 635
assert results["historical_diagnostics"]["delivered_after_last_recorded_withdrawal"] == 334
assert results["snapshot_diagnostics"]["cdr_received_after_snapshot"] == 79
destination = Path(__file__).with_name("audit-results.json")
destination.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n")
print(json.dumps({"output": str(destination.relative_to(ROOT)),
                  "checks": "source diagnostics complete; no source files edited",
                  "events": results["event_stream"], "clv": results["clv_reconstruction"]},
                 ensure_ascii=False, indent=2))
