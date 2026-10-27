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


MEMORY = [  # one entry per kind that the engine applies (nba.ai.feedback); pause_sales points at no offer or channel
    {"id": "M-MG-100068-1", "customer_id": "MG-100068", "kind": "pause_offer", "offer_id": "P-EN-02", "channel": None,
     "since": "2026-09-20T10:00:00", "until": "2026-12-19T10:00:00", "reason_code": "not_relevant", "source": "agent_feedback"},
    {"id": "M-MG-100068-2", "customer_id": "MG-100068", "kind": "block_channel", "offer_id": None, "channel": "email",
     "since": "2026-09-21T10:00:00", "until": "2026-12-20T10:00:00", "reason_code": "wrong_channel", "source": "decision_log"},
    {"id": "M-MG-100068-3", "customer_id": "MG-100068", "kind": "pause_sales", "offer_id": None, "channel": None,
     "since": "2026-09-22T10:00:00", "until": "2026-10-22T10:00:00", "reason_code": "customer_upset", "source": "decision_log"},
]


def test_customer_memory_becomes_feedback_nodes(states, policy, tmp_path):
    import json
    from pathlib import Path

    import yaml

    from nba.kg.graph import ch_id

    edge_types = yaml.safe_load((Path(__file__).parents[1] / "kg" / "ontology.yaml").read_text())["edge_types"]
    ids = {m["id"] for m in MEMORY}
    g = customer_graph(states["MG-100068"], policy, memory=MEMORY)
    assert {n for n, d in g.nodes(data=True) if d["type"] == "Feedback"} == ids
    assert {v for _, v, d in g.out_edges("MG-100068", data=True) if d["type"] == "GAVE_FEEDBACK"} == ids
    about = {(u, v) for u, v, d in g.edges(data=True) if d["type"] == "ABOUT"}
    assert about == {("M-MG-100068-1", "P-EN-02"), ("M-MG-100068-2", ch_id("email"))}
    for u, v, d in g.edges(data=True):  # endpoints as kg/ontology.yaml declares them
        if d["type"] in {"GAVE_FEEDBACK", "ABOUT"}:
            spec = {k: x if isinstance(x, list) else [x] for k, x in edge_types[d["type"]].items()}
            assert g.nodes[u]["type"] in spec["from"] and g.nodes[v]["type"] in spec["to"], (u, v)
    assert g.nodes["M-MG-100068-3"]["kind"] == "pause_sales" and g.nodes["M-MG-100068-3"]["until"] == "2026-10-22T10:00:00"
    assert not [n for n, d in customer_graph(states["MG-100068"], policy).nodes(data=True) if d["type"] == "Feedback"]
    export_graph({c: states[c] for c in ("MG-100068", "MG-100009")}, policy, tmp_path, memory={"MG-100068": MEMORY})
    nodes = [json.loads(line) for line in (tmp_path / "kg_nodes.jsonl").open()]
    edges = [json.loads(line) for line in (tmp_path / "kg_edges.jsonl").open()]
    assert {n["id"] for n in nodes if n["type"] == "Feedback"} == ids
    assert sum(e["type"] == "GAVE_FEEDBACK" for e in edges) == 3 and sum(e["type"] == "ABOUT" for e in edges) == 2
