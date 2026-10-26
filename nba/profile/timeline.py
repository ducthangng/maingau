"""Event timeline (README §4.1 B1): last 12 months plus future milestones, newest first."""

from __future__ import annotations

from datetime import timedelta

from nba.contracts import TimelineItem
from nba.profile.facts import clean, day, to_datetime

CONSENT_LABELS = {"granted": "granted", "not_given": "not given", "withdrawn": "withdrawn"}


def build_timeline(state, months: int = 12) -> list[TimelineItem]:
    eval_time = state.eval_time
    start = eval_time - timedelta(days=round(months * 30.44))
    raw: list[dict] = []

    def add(when, kind, line, title, src, ref=None, detail=None, flags=None, future_ok=False):
        when = to_datetime(when)  # mobile min_term_end is not parsed by load_workbook
        if when is None:
            return
        future = when > eval_time
        if future and not future_ok:
            return
        if not future and when <= start:
            return
        raw.append({"date": day(when), "future": future, "kind": kind, "line": line, "title": title,
                    "detail": detail, "src": src, "ref": ref, "flags": flags or []})

    for r in state.rows.get("energy_contracts", []):
        ref, tariff = f"contract:{r['contract_id']}", r.get("tariff")
        add(r.get("start_date"), "contract", "energy", f"{tariff} started", "energy_contracts.start_date", ref)
        add(r.get("cancellation_received_at"), "contract", "energy", f"{tariff}: cancellation received",
            "energy_contracts.cancellation_received_at", ref, flags=["cancellation"])
        add(r.get("meter_deregistered_at"), "contract", "energy", f"{tariff}: gas meter deregistered",
            "energy_contracts.meter_deregistered_at", ref)
        if r.get("status") == "active":
            add(r.get("price_guarantee_until"), "milestone", "energy", f"{tariff}: price guarantee ends",
                "energy_contracts.price_guarantee_until", ref, future_ok=True)
    for r in state.rows.get("mobile_contracts", []):
        ref = f"contract:{r['contract_id']}"
        add(r.get("start_date"), "contract", "mobile", f"{r.get('plan')} started", "mobile_contracts.start_date", ref)
        if r.get("status") == "active":
            add(r.get("min_term_end"), "milestone", "mobile", f"{r.get('plan')}: minimum term ends",
                "mobile_contracts.min_term_end", ref, future_ok=True)
    for r in state.rows.get("autostrom_contracts", []):
        ref = f"contract:{r['contract_id']}"
        add(r.get("start_date"), "contract", "autostrom", "Autostrom started", "autostrom_contracts.start_date", ref)
        add(r.get("cancelled_at"), "contract", "autostrom", "Autostrom cancelled", "autostrom_contracts.cancelled_at",
            ref, flags=["cancellation"])
    for r in state.rows.get("service_interactions", []):
        flags = []
        if clean(r.get("repeat_of_ticket_id")):
            flags.append("repeat contact")
        if r.get("status") == "open":
            flags.append("open")
        csat = clean(r.get("csat_1to5"))
        detail = f"{r.get('channel')} · {r.get('status')}" + (f" · CSAT {csat}" if csat is not None else "")
        add(r.get("created_at"), "service", "service", f"Ticket: {r.get('category')}", "service_interactions.created_at",
            f"ticket:{r['ticket_id']}", detail, flags)
    for r in state.rows.get("shop_orders", []):
        add(r.get("order_created_at"), "order", "shop", str(r.get("product_name")), "shop_orders.order_created_at",
            f"order:{r['order_id']}", r.get("order_status"),
            [] if r.get("order_status") == "delivered" else [str(r.get("order_status"))])
    for r in state.rows.get("consent_status", []):
        status = CONSENT_LABELS.get(r.get("status"), r.get("status"))
        add(r.get("updated_at"), "consent", None, f"Consent {r['consent_type']}: {status}", "consent_status.updated_at",
            f"consent:{r['consent_type']}", clean(r.get("source")))
    for r in state.rows.get("nba_action_history", []):
        if r.get("control_group"):
            continue
        flags = [] if r.get("consent_checked") is not False else ["legacy engine sent without checking consent"]
        add(r.get("decided_at"), "marketing", "marketing", f"Offer {r.get('offer_id')} via {r.get('channel')}",
            "nba_action_history.decided_at", f"action:{r['action_id']}",
            f"{r.get('rule_id')} · {r.get('response')}" + (" · converted" if r.get("converted_within_14d") else ""),
            flags)

    raw.sort(key=lambda x: (x["date"], x["kind"], x["title"], x["ref"] or ""), reverse=True)
    return [TimelineItem(id=f"tl-{i:03d}", **x) for i, x in enumerate(raw, start=1)]
