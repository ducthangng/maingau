"""Independent hard-rule check on finished cards, rebuilt from the raw tables (not from nba.kg.rules).

It is deliberately small and separate from the engine: it answers "did the chosen action break a
hard rule?" from consent_status, customer_master, energy_contracts, service_interactions,
autostrom_contracts, newsletter_performance and nba_action_history directly.
"""
from __future__ import annotations

import pandas as pd


def as_bool(series: pd.Series) -> pd.Series:
    return series.map(lambda v: str(v).strip().lower() in {"1", "true", "yes"})


def raw_rules(x: dict, channels: dict, eval_time, cap: tuple[int, int], cap_sources=("nba_history",)) -> dict:
    """Per customer: allowed marketing channels, active exclusion, profiling, contact cap reached.

    `channels` is the channel -> consent map the check holds the engine to (the committed one, so an
    edit to that map is checked against the rule it replaces). `cap` is (max contacts, window days);
    `cap_sources` are config/kg.yaml contact_cap.sources (`service_feedback` adds offers a service agent
    mentioned). `capped` maps each capped customer to the time the cap frees up."""
    consent = x["consent_status"]
    granted = consent[consent["status"] == "granted"]
    by_type = {t: set(g["customer_id"]) for t, g in granted.groupby("consent_type")}
    doi = set(granted[(granted["consent_type"] == "newsletter_email") & granted["double_opt_in_confirmed_at"].notna()]["customer_id"])
    perf = x["newsletter_performance"]
    unsub = set(perf[as_bool(perf["unsubscribed"])]["customer_id"])
    master = x["customer_master"].set_index("customer_id")
    energy, tickets, autostrom = x["energy_contracts"], x["service_interactions"], x["autostrom_contracts"]
    excluded = (set(energy[energy["dunning_level"].fillna(0) >= 1]["customer_id"])
                | set(energy[energy["status"] == "cancellation_pending"]["customer_id"])
                | set(tickets[tickets["status"] == "open"]["customer_id"])
                | set(autostrom[autostrom["status"] == "cancelled"]["customer_id"]))
    h = x["nba_action_history"].copy()
    h["decided_at"] = pd.to_datetime(h["decided_at"])
    t = pd.Timestamp(eval_time)
    window = h[(h["delivery_status"] == "delivered") & ~as_bool(h["control_group"])
               & (h["decided_at"] > t - pd.Timedelta(days=cap[1])) & (h["decided_at"] <= t)]
    contacts = window[["customer_id", "channel", "decided_at"]].rename(columns={"decided_at": "ts"})
    if "service_feedback" in cap_sources:
        fb = x["service_nba_feedback"].copy()
        fb["ts"] = pd.to_datetime(fb["shown_at"])
        fb = fb[as_bool(fb["offer_mentioned_to_customer"]) & (fb["ts"] > t - pd.Timedelta(days=cap[1])) & (fb["ts"] <= t)]
        contacts = pd.concat([contacts, fb.assign(channel="outbound_call")[["customer_id", "channel", "ts"]]])
    contacts = contacts.drop_duplicates()
    capped = {}
    for cid, g in contacts.groupby("customer_id"):
        times = sorted(g["ts"])
        if len(times) >= cap[0]:  # frees up when the oldest surplus contact leaves the window
            capped[cid] = times[len(times) - cap[0]] + pd.Timedelta(days=cap[1])
    allowed: dict[str, set[str]] = {}
    for cid in master.index:
        ok = set()
        for ch, spec in channels.items():
            if cid not in by_type.get(spec["consent"], set()):
                continue
            if ch == "newsletter_email" and (cid not in doi or cid in unsub):
                continue
            if spec.get("requires_field") and not as_bool(pd.Series([master.at[cid, spec["requires_field"]]])).iloc[0]:
                continue
            ok.add(ch)
        allowed[cid] = ok
    return {"allowed": allowed, "excluded": excluded, "profiled": by_type.get("profiling_analytics", set()),
            "capped": capped}


def violations(cards, rules) -> list[str]:
    out = []
    for card in cards:
        cid, chosen = card.customer_id, card.chosen.tuple_id
        if chosen == "NO_ACTION":
            continue
        c = next(x for x in card.candidates if x.tuple_id == chosen)
        if c.action_type == "service":
            continue
        if c.channel not in rules["allowed"][cid]:
            out.append(f"{cid} {chosen}: no consent/availability for {c.channel}")
        if cid in rules["excluded"]:
            out.append(f"{cid} {chosen}: sales action during an exclusion")
        if (c.personalised or c.tone == "du") and cid not in rules["profiled"]:
            out.append(f"{cid} {chosen}: personalised without profiling consent")
        free_at = rules.get("capped", {}).get(cid) if isinstance(rules.get("capped"), dict) else None
        waits = card.chosen.deferred_until and free_at is not None and pd.Timestamp(card.chosen.deferred_until) >= free_at
        if cid in rules.get("capped", set()) and not waits:  # a deferred action may go out once the cap frees up
            out.append(f"{cid} {chosen}: contact cap reached")
        if c.valuation.delta_clv <= 0:
            out.append(f"{cid} {chosen}: ΔCLV {c.valuation.delta_clv:.2f} ≤ 0")
    return out
