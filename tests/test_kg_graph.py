"""Graph structure and provenance (README §6.11; review findings 26 Oct)."""

from nba.kg.graph import consent_id, customer_graph, export_graph, policy_graph
from nba.kg.signals import extract_signals


def test_policy_graph_has_six_consent_types_and_no_self_loops(policy):
    g = policy_graph(policy)
    assert sum(1 for _, d in g.nodes(data=True) if d["type"] == "ConsentType") == 6
    assert not [(u, v) for u, v in g.edges() if u == v]
    assert g.has_edge("channel:newsletter_email", consent_id("newsletter_email"))


def test_every_signal_evidence_ref_resolves(states, policy):
    for cid, s in states.items():
        sigs = extract_signals(s, policy)
        if not sigs:
            continue
        g = customer_graph(s, policy)
        for sig in sigs:
            node = f"{cid}:{sig.id}"
            targets = {v for _, v, d in g.out_edges(node, data=True) if d["type"] == "EVIDENCED_BY"}
            assert len(targets) == len(set(sig.evidence)), (cid, sig.id, sig.evidence)


def test_received_only_for_delivered_actions(states, policy):
    s = states["MG-100004"]
    g = customer_graph(s, policy)
    delivered = {r["action_id"] for r in s.rows["nba_action_history"] if r["delivery_status"] == "delivered"}
    received = {v for _, v, d in g.out_edges("MG-100004", data=True) if d["type"] == "RECEIVED"}
    assert received == delivered


def test_export_has_no_orphan_nodes(states, policy, kg_all, tmp_path):
    import json

    subset = {c: states[c] for c in ("MG-100068", "MG-100009", "MG-100112")}
    archetypes = {c: kg_all[c][3].archetype.id for c in subset}
    export_graph(subset, policy, tmp_path, archetypes)
    nodes = {json.loads(line)["id"] for line in (tmp_path / "kg_nodes.jsonl").open()}
    touched = set()
    for line in (tmp_path / "kg_edges.jsonl").open():
        e = json.loads(line)
        touched |= {e["src"], e["dst"]}
    assert touched <= nodes
    orphans = {n for n in nodes - touched}
    assert not orphans, sorted(orphans)[:10]
