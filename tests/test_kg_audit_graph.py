"""KG audit: customer graph and explanation paths (README §4.2 C3, §5.4, §6.11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from kg_audit_oracle import CONSENT_TYPES, PRODUCT_LINES, UI_REF_PREFIXES, oracle

from nba.kg.graph import customer_graph
from nba.kg.paths import explain

REPO = Path(__file__).resolve().parents[1]
ONTOLOGY = yaml.safe_load((REPO / "kg" / "ontology.yaml").read_text(encoding="utf-8"))
SAMPLE = ["MG-100068", "MG-100009", "MG-100112", "MG-100325", "MG-100096", "MG-100004", "MG-100023", "MG-100087"]


def _types(v) -> set[str]:
    return set(v) if isinstance(v, list) else {v}


@pytest.fixture(scope="module")
def graphs(states, policy, kg_all):
    return {c: customer_graph(states[c], policy, kg_all[c][3].archetype.id) for c in states}


def test_graph_uses_only_ontology_types(graphs):
    nodes, edges = set(ONTOLOGY["node_types"]), ONTOLOGY["edge_types"]
    bad = set()
    for cid, g in graphs.items():
        for n, d in g.nodes(data=True):
            if d.get("type") not in nodes:
                bad.add(("node", n, d.get("type")))
        for u, v, d in g.edges(data=True):
            spec = edges.get(d.get("type"))
            if spec is None:
                bad.add(("edge", d.get("type")))
                continue
            tu, tv = g.nodes[u].get("type"), g.nodes[v].get("type")
            if tu not in _types(spec["from"]) or tv not in _types(spec["to"]):
                bad.add(("endpoint", d["type"], tu, tv))
    assert not bad, sorted(bad, key=str)[:20]


def test_channel_and_consent_nodes_are_namespaced(graphs):
    g = graphs["MG-100068"]
    for n, d in g.nodes(data=True):
        if d["type"] == "Channel":
            assert n.startswith("channel:"), n
        if d["type"] == "ConsentType":
            assert n.startswith("consent:"), n
    assert {f"consent:{t}" for t in CONSENT_TYPES} <= set(g.nodes)


def test_received_only_for_delivered_and_held_out_for_control(graphs, states):
    for cid, g in graphs.items():
        rows = states[cid].rows["nba_action_history"]
        delivered = {r["action_id"] for r in rows if r["delivery_status"] == "delivered"}
        control = {r["action_id"] for r in rows if r["delivery_status"] != "delivered"}
        out = [(v, d["type"]) for _, v, d in g.out_edges(cid, data=True)]
        assert {v for v, t in out if t == "RECEIVED"} == delivered, cid
        assert {v for v, t in out if t == "HELD_OUT"} == control, cid
        assert not {v for v, t in out if t == "RESPONDED"} & control, cid


def test_no_orphan_nodes(graphs):
    orphans = {cid: sorted(n for n in g.nodes if g.degree(n) == 0) for cid, g in graphs.items()}
    orphans = {c: o for c, o in orphans.items() if o}
    assert not orphans, dict(list(orphans.items())[:3])


def test_graph_is_identical_across_two_builds(states, policy):
    def dump(g):
        nodes = sorted(json.dumps([n, d], default=str, sort_keys=True) for n, d in g.nodes(data=True))
        edges = sorted(json.dumps([u, v, d], default=str, sort_keys=True) for u, v, d in g.edges(data=True))
        return nodes, edges

    for cid in SAMPLE:
        assert dump(customer_graph(states[cid], policy)) == dump(customer_graph(states[cid], policy)), cid


# ---------------------------------------------------------------- explain()

SIGNAL_PATH = ["Customer", "EMITTED", "Signal", "INDICATES", "Need", "ADDRESSED_BY", "Offer", "DELIVERED_VIA",
               "Channel", "REQUIRES", "Consent"]
SERVICE_PATH = SIGNAL_PATH[:9]


def _shape(path):
    return [p.type for p in path]


def test_paths_alternate_and_follow_the_policy_shape(kg_all, states, policy):
    for cid, (sig, cands, _, _) in kg_all.items():
        for c in cands:
            path = explain(states[cid], c, policy, sig)
            assert [p.kind for p in path] == ["node", "edge"] * (len(path) // 2) + ["node"], (cid, c.tuple_id)
            assert path == c.path, (cid, c.tuple_id)
            if c.origin == "signal":
                assert _shape(path) == SIGNAL_PATH, (cid, c.tuple_id)
            elif c.origin == "service":
                assert _shape(path) == SERVICE_PATH and path[-1].id == "service_agent", (cid, c.tuple_id)
            else:
                assert _shape(path)[0] == "Customer" and _shape(path)[-5:] == SIGNAL_PATH[-5:], (cid, c.tuple_id)
            assert path[0].id == cid and [p.id for p in path if p.type == "Offer"] == [c.offer_id]


def test_path_edges_are_ontology_edge_types(kg_all):
    edges = set(ONTOLOGY["edge_types"])
    used = {p.type for _, cands, _, _ in kg_all.values() for c in cands for p in c.path if p.kind == "edge"}
    assert used <= edges, sorted(used - edges)


def test_path_policy_edges_exist_in_the_policy_graph(kg_all, policy):
    from nba.kg.graph import ch_id, consent_id, policy_graph

    g = policy_graph(policy)
    for cid, (_, cands, _, _) in kg_all.items():
        for c in cands:
            nodes = [p for p in c.path if p.kind == "node"]
            ids = {p.type: p.id for p in nodes}
            if "Need" in ids:
                assert g.has_edge(ids["Signal"], ids["Need"]) and g.has_edge(ids["Need"], ids["Offer"]), (cid, c.tuple_id)
            assert g.has_edge(ids["Offer"], ch_id(ids["Channel"])), (cid, c.tuple_id)
            if "Consent" in ids:
                assert g.has_edge(ch_id(ids["Channel"]), consent_id(ids["Consent"])), (cid, c.tuple_id)


def test_ui_refs_are_valid_and_point_to_customer_data(kg_all, states):
    o = oracle()
    bad = []
    for cid, (sig, cands, _, _) in kg_all.items():
        sig_ids = {s.id for s in sig}
        consent_types = {r["consent_type"] for r in states[cid].rows["consent_status"]}
        for c in cands:
            for p in c.path:
                ref = p.ui_ref
                if ref is None:
                    continue
                if ref in ("header", "value"):
                    ok = True
                elif ref.startswith("signal:"):
                    ok = ref[7:] in sig_ids
                elif ref.startswith("consent:"):
                    ok = ref[8:] in consent_types
                elif ref.startswith("product:"):
                    ok = ref[8:] in PRODUCT_LINES
                elif ref.startswith("exclusion:"):
                    ok = ref[10:] in o.exclusions(cid)
                else:
                    ok = ref.startswith(UI_REF_PREFIXES)
                if not ok:
                    bad.append((cid, c.tuple_id, ref))
    assert not bad, bad[:20]


def test_signal_and_consent_nodes_carry_ui_refs(kg_all):
    for cid, (_, cands, _, _) in kg_all.items():
        for c in cands:
            for p in c.path:
                if p.kind == "node" and p.type in ("Customer", "Signal", "Consent"):
                    assert p.ui_ref, (cid, c.tuple_id, p.type)
