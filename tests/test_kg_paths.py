"""Explanation paths (README §5.4)."""

import re

UI_REF = re.compile(r"^(header|value|product:\w+|consent:\w+|exclusion:[\w-]+|signal:S\d+|timeline:.+|trend:\w+)$")


def test_paths_are_well_formed(kg_all):
    for _, cands, _, _ in kg_all.values():
        for c in cands:
            kinds = [p.kind for p in c.path]
            assert kinds[0] == "node" and kinds[-1] == "node"
            assert all(a != b for a, b in zip(kinds, kinds[1:])), c.tuple_id
            for p in c.path:
                if p.ui_ref:
                    assert UI_REF.match(p.ui_ref), p.ui_ref


def test_signal_path_shape(kg_all):
    c = next(c for c in kg_all["MG-100023"][1] if c.offer_id == "P-AS-01")
    assert [p.type for p in c.path if p.kind == "node"] == ["Customer", "Signal", "Need", "Offer", "Channel", "Consent"]


def test_determinism(states, policy):
    from nba.kg.rules import generate_candidates
    from nba.kg.signals import extract_signals

    s = states["MG-100068"]
    a = [c.model_dump_json() for c in generate_candidates(s, extract_signals(s, policy), policy, "sie")[0]]
    b = [c.model_dump_json() for c in generate_candidates(s, extract_signals(s, policy), policy, "sie")[0]]
    assert a == b
