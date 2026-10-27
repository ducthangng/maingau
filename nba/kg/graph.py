"""Customer knowledge graph and export (README §6.11). Owner: Agent KG.

`customer_graph` builds a NetworkX MultiDiGraph with the policy layer and one customer's
instance layer. `export_graph` writes node/edge tables (JSONL) for all customers — the shape a
Delta table `kg_nodes` / `kg_edges` would have on Databricks.

Node IDs: policy nodes use their policy ID (S1, N-HEAT-PUMP, P-EN-03, EXCL-DUNNING, A2), except
channels and consent types, which share names and are namespaced (`channel:email`,
`consent:marketing_email`). Instance nodes use source IDs (contract_id, device_id, order_id,
ticket_id, session_id, action_id) or `<customer_id>:<rule|signal|consent>`; Feedback nodes use the
customer memory ID (`M-<customer_id>-<n>`, nba.ai.feedback).
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from nba.kg.policy import CONSENT_TYPES, Policy
from nba.kg.rules import active_exclusions, consents
from nba.kg.signals import extract_signals
from nba.state import CustomerState


def ch_id(channel: str) -> str:
    return f"channel:{channel}"


def consent_id(ctype: str) -> str:
    return f"consent:{ctype}"


def policy_graph(policy: Policy) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for nid, n in policy.needs.items():
        g.add_node(nid, type="Need", label=n["label_en"])
    for s in policy.signals.values():
        g.add_node(s.id, type="SignalType", label=s.label, strength=s.strength, purpose=s.purpose)
        for n in s.indicates:
            g.add_edge(s.id, n, type="INDICATES")
        for n in s.reinforces:
            g.add_edge(s.id, n, type="REINFORCES")
    for ctype in sorted(CONSENT_TYPES):
        g.add_node(consent_id(ctype), type="ConsentType", label=ctype)
    g.add_node(ch_id(policy.service_channel), type="Channel", label="service agent")
    for c in policy.channels.values():
        g.add_node(ch_id(c.id), type="Channel", label=c.id)
        g.add_edge(ch_id(c.id), consent_id(c.consent), type="REQUIRES")
    for o in policy.offers.values():
        g.add_node(o.id, type="Offer", label=o.name, action_type=o.action_type, generic=o.generic)
        for n in o.addresses:
            g.add_edge(n, o.id, type="ADDRESSED_BY")
        targets = [policy.service_channel] if o.action_type == "service" else list(policy.channels)
        for ch in targets:
            g.add_edge(o.id, ch_id(ch), type="DELIVERED_VIA")
    for o in policy.offers.values():  # D1: every need-based (personalised) offer requires profiling consent
        if o.action_type != "service" and not o.data_missing and o.addresses:
            g.add_edge(o.id, consent_id("profiling_analytics"), type="REQUIRES")
    for e in policy.exclusions.values():
        g.add_node(e.id, type="ExclusionRule", label=e.label)
        for o in policy.offers.values():
            if o.action_type in e.blocks:
                g.add_edge(e.id, o.id, type="BLOCKS")
    # Archetype nodes are added per customer (only the customer's own), so the policy layer has no orphans.
    return g


def customer_graph(state: CustomerState, policy: Policy, archetype: str | None = None,
                   memory: list[dict] | None = None) -> nx.MultiDiGraph:
    """`memory`: this customer's feedback memory (Runtime cfg.memory[customer_id]), added as Feedback nodes."""
    g = policy_graph(policy)
    cid = state.customer_id
    g.add_node(cid, type="Customer", label=cid)
    for sheet, kind in (("energy_contracts", "Energy"), ("mobile_contracts", "Mobile"), ("autostrom_contracts", "Autostrom")):
        for r in state.rows[sheet]:
            g.add_node(r["contract_id"], type="Contract", subtype=kind, status=r.get("status"))
            g.add_edge(cid, r["contract_id"], type="HOLDS")
    for r in state.rows["hems_devices"]:
        g.add_node(r["device_id"], type="Device", device_type=r.get("device_type"), status=r.get("connection_status"))
        g.add_edge(cid, r["device_id"], type="OWNS_DEVICE")
    for r in state.rows["shop_orders"]:
        g.add_node(r["order_id"], type="Order", product=r.get("product_name"), status=r.get("order_status"))
        g.add_edge(cid, r["order_id"], type="PLACED")
    for r in state.rows["service_interactions"]:
        g.add_node(r["ticket_id"], type="Ticket", category=r.get("category"), status=r.get("status"))
        g.add_edge(cid, r["ticket_id"], type="RAISED")
    for ctype, ci in consents(state, policy).items():
        nid = f"{cid}:{ctype}"
        g.add_node(nid, type="Consent", status=ci.effective_status)
        g.add_edge(cid, nid, type="HOLDS")
        g.add_edge(nid, consent_id(ctype), type="INSTANCE_OF")
    for r in state.rows["nba_action_history"]:
        g.add_node(r["action_id"], type="Action", offer=r.get("offer_id"), channel=r.get("channel"))
        if r.get("delivery_status") == "delivered":
            g.add_edge(cid, r["action_id"], type="RECEIVED")
            if r.get("response") in ("clicked", "viewed") or r.get("converted_within_14d"):
                g.add_edge(cid, r["action_id"], type="RESPONDED", response=r.get("response"))
        else:
            g.add_edge(cid, r["action_id"], type="HELD_OUT")  # control group: decided but not sent
    for rule_id, hit in active_exclusions(state, policy):
        nid = f"{cid}:{rule_id}"
        g.add_node(nid, type="Exclusion", detail=hit.detail)
        g.add_edge(nid, rule_id, type="INSTANCE_OF")
    sessions = {r["session_id"]: r for r in state.rows["charge_sessions"]}
    for s in extract_signals(state, policy):
        nid = f"{cid}:{s.id}"
        g.add_node(nid, type="Signal", detail=s.detail, date=s.date)
        g.add_edge(cid, nid, type="EMITTED")
        g.add_edge(nid, s.id, type="INSTANCE_OF")
        for n in s.needs:
            g.add_edge(nid, n, type="REINFORCES" if policy.signals[s.id].reinforces else "INDICATES")
        for ref in s.evidence:
            kind, target = ref.split(":", 1)
            if kind == "session":
                row = sessions.get(target, {})
                g.add_node(target, type="Session", status=row.get("session_status"), started_at=row.get("started_at"))
                if row.get("contract_id") and g.has_node(row["contract_id"]):
                    g.add_edge(row["contract_id"], target, type="HAS_SESSION")
            elif kind == "click":
                target = f"campaign:{target}"
                g.add_node(target, type="Campaign")
            g.add_edge(nid, target, type="EVIDENCED_BY")
    if archetype:
        g.add_node(archetype, type="Archetype", label=policy.archetypes.get(archetype, archetype))
        g.add_edge(cid, archetype, type="IN_ARCHETYPE")
    for m in memory or []:  # what a person said no to, remembered until a date (knowledge base for the engine)
        g.add_node(m["id"], type="Feedback", kind=m.get("kind"), reason_code=m.get("reason_code"),
                   since=m.get("since"), until=m.get("until"), source=m.get("source"), note=m.get("note"))
        g.add_edge(cid, m["id"], type="GAVE_FEEDBACK")
        if m.get("offer_id") in policy.offers:
            g.add_edge(m["id"], m["offer_id"], type="ABOUT")
        if m.get("channel") in policy.channels:
            g.add_edge(m["id"], ch_id(m["channel"]), type="ABOUT")
    return g


def export_graph(states: dict[str, CustomerState], policy: Policy, out_dir: str | Path,
                 archetypes: dict[str, str] | None = None, memory: dict[str, list[dict]] | None = None) -> tuple[int, int]:
    """Write kg_nodes.jsonl / kg_edges.jsonl: the policy layer once, then each customer's instance layer.

    Pass `archetypes` (customer_id -> A0..A5) to link customers to archetype nodes; an archetype node is
    written once, with the first customer in it, so the export has no orphans. Pass `memory` (Runtime
    cfg.memory) to add each customer's Feedback nodes.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = policy_graph(policy)
    policy_ids = set(base.nodes)
    n_nodes = n_edges = 0
    with (out / "kg_nodes.jsonl").open("w", encoding="utf-8") as fn, (out / "kg_edges.jsonl").open("w", encoding="utf-8") as fe:
        def write(g, nodes, edges):
            nonlocal n_nodes, n_edges
            for node in nodes:
                fn.write(json.dumps({"id": node, **g.nodes[node]}, default=str, sort_keys=True) + "\n")
                n_nodes += 1
            for u, v, attrs in edges:
                fe.write(json.dumps({"src": u, "dst": v, **attrs}, default=str, sort_keys=True) + "\n")
                n_edges += 1

        write(base, sorted(base.nodes), base.edges(data=True))
        seen: set[str] = set()
        for cid in sorted(states):
            g = customer_graph(states[cid], policy, (archetypes or {}).get(cid), (memory or {}).get(cid))
            instance = [n for n in g.nodes if n not in policy_ids and n not in seen]
            seen.update(instance)
            edges = [(u, v, a) for u, v, a in g.edges(data=True) if u not in policy_ids or v not in policy_ids]
            write(g, instance, edges)
    return n_nodes, n_edges
