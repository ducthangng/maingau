"""Customer knowledge graph and export (README §6.11). Owner: Agent KG.

`customer_graph` builds a NetworkX MultiDiGraph with the policy layer and one customer's
instance layer. `export_graph` writes node/edge tables (JSONL) for all customers — the shape a
Delta table `kg_nodes` / `kg_edges` would have on Databricks.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from nba.kg.policy import CONSENT_TYPES, Policy
from nba.kg.rules import active_exclusions, consents
from nba.kg.signals import extract_signals
from nba.state import CustomerState


def policy_graph(policy: Policy) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for nid, n in policy.needs.items():
        g.add_node(nid, type="Need", label=n["label_en"])
    for s in policy.signals.values():
        g.add_node(s.id, type="SignalType", label=s.label, strength=s.strength, purpose=s.purpose)
        for n in s.indicates:
            g.add_edge(s.id, n, type="INDICATES")
    for o in policy.offers.values():
        g.add_node(o.id, type="Offer", label=o.name, action_type=o.action_type, generic=o.generic)
        for n in o.addresses:
            g.add_edge(n, o.id, type="ADDRESSED_BY")
        if o.action_type == "service":
            g.add_edge(o.id, policy.service_channel, type="DELIVERED_VIA")
        else:
            for ch in policy.channels:
                g.add_edge(o.id, ch, type="DELIVERED_VIA")
    g.add_node(policy.service_channel, type="Channel", label="service agent")
    for ctype in sorted(CONSENT_TYPES):
        g.add_node(ctype, type="ConsentType", label=ctype)
    for c in policy.channels.values():
        g.add_node(c.id, type="Channel", label=c.id)
        g.add_edge(c.id, c.consent, type="REQUIRES")
    for e in policy.exclusions.values():
        g.add_node(e.id, type="ExclusionRule", label=e.label)
        for o in policy.offers.values():
            if o.action_type in e.blocks:
                g.add_edge(e.id, o.id, type="BLOCKS")
    for aid, name in policy.archetypes.items():
        g.add_node(aid, type="Archetype", label=name)
    return g


def customer_graph(state: CustomerState, policy: Policy, archetype: str | None = None) -> nx.MultiDiGraph:
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
    for i, r in enumerate(state.rows["shop_orders"]):
        oid = f"{r['order_id']}#{i}"
        g.add_node(oid, type="Order", product=r.get("product_name"), status=r.get("order_status"))
        g.add_edge(cid, oid, type="PLACED")
    for r in state.rows["service_interactions"]:
        g.add_node(r["ticket_id"], type="Ticket", category=r.get("category"), status=r.get("status"))
        g.add_edge(cid, r["ticket_id"], type="RAISED")
    for ctype, ci in consents(state, policy).items():
        nid = f"{cid}:{ctype}"
        g.add_node(nid, type="Consent", status=ci.effective_status)
        g.add_edge(cid, nid, type="HOLDS")
        g.add_edge(nid, ctype, type="INSTANCE_OF")
    for r in state.rows["nba_action_history"]:
        g.add_node(r["action_id"], type="Action", offer=r.get("offer_id"), channel=r.get("channel"))
        g.add_edge(cid, r["action_id"], type="RECEIVED")
        if r.get("response") in ("clicked", "viewed") or r.get("converted_within_14d"):
            g.add_edge(cid, r["action_id"], type="RESPONDED", response=r.get("response"))
    for rule_id, hit in active_exclusions(state, policy):
        nid = f"{cid}:{rule_id}"
        g.add_node(nid, type="Exclusion", detail=hit.detail)
        g.add_edge(nid, rule_id, type="INSTANCE_OF")
    for s in extract_signals(state, policy):
        nid = f"{cid}:{s.id}"
        g.add_node(nid, type="Signal", detail=s.detail, date=s.date)
        g.add_edge(cid, nid, type="EMITTED")
        g.add_edge(nid, s.id, type="INSTANCE_OF")
        for n in s.needs:
            g.add_edge(nid, n, type="INDICATES")
        for ref in s.evidence:
            target = ref.split(":", 1)[1]
            if ref.startswith("session:"):
                g.add_node(target, type="Session")
            if g.has_node(target):
                g.add_edge(nid, target, type="EVIDENCED_BY")
    if archetype:
        g.add_edge(cid, archetype, type="IN_ARCHETYPE")
    return g


def export_graph(states: dict[str, CustomerState], policy: Policy, out_dir: str | Path) -> tuple[int, int]:
    """Write kg_nodes.jsonl / kg_edges.jsonl: the policy layer once, then each customer's instance layer."""
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
        for cid in sorted(states):
            g = customer_graph(states[cid], policy)
            instance = [n for n in g.nodes if n not in policy_ids]
            edges = [(u, v, a) for u, v, a in g.edges(data=True) if u not in policy_ids or v not in policy_ids]
            write(g, instance, edges)
    return n_nodes, n_edges
