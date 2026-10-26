"""KG audit: triage, archetypes, urgency and flags (README §6.13)."""

from __future__ import annotations

import ast
import collections
import re
from pathlib import Path

import pytest

from kg_audit_oracle import ARCHETYPE_COUNTS, FLAG_COUNTS, OUTLIER_COUNT, OUTLIER_FLAGS, TIER_COUNTS, oracle

REPO = Path(__file__).resolve().parents[1]
SEGMENTS = REPO / "nba" / "kg" / "segments.py"


def test_archetype_counts_match_readme_and_oracle(kg_all):
    got = collections.Counter(t.archetype.id for *_, t in kg_all.values())
    assert dict(got) == ARCHETYPE_COUNTS
    diffs = [(c, t.archetype.id, oracle().archetype(c)) for c, (*_, t) in kg_all.items() if t.archetype.id != oracle().archetype(c)]
    assert not diffs, diffs[:20]


def test_archetype_first_match_order(kg_all):
    """A customer that meets several rules gets the earliest one (A4 > A1 > A3 > A5 > A2 > A0)."""
    o = oracle()
    both = [c for c in o.customers if o.exclusions(c) and "hems_gateway" in o.device_types(c)]
    both += [c for c in o.customers if "hems_gateway" in o.device_types(c) and o.has_active_autostrom(c)
             and not o.exclusions(c) and o.churn(c) < 0.35]
    assert both
    for c in both:
        assert kg_all[c][3].archetype.id == o.archetype(c), c


def test_tier_counts_match_readme_and_oracle(kg_all):
    got = collections.Counter(t.urgency_tier for *_, t in kg_all.values())
    assert dict(got) == TIER_COUNTS
    diffs = [(c, t.urgency_tier, oracle().tier(c)) for c, (*_, t) in kg_all.items() if t.urgency_tier != oracle().tier(c)]
    assert not diffs, diffs[:20]


@pytest.mark.parametrize("flag", sorted(FLAG_COUNTS))
def test_flag_sets_match_oracle_and_readme_counts(kg_all, flag):
    got = {c for c, (*_, t) in kg_all.items() if any(f.id == flag for f in t.flags)}
    want = {c for c in oracle().customers if flag in oracle().flags(c)}
    assert got == want, f"{flag}: code-only {sorted(got - want)[:10]}, oracle-only {sorted(want - got)[:10]}"
    assert len(got) == FLAG_COUNTS[flag]


def test_outliers_and_top_clv_is_not_an_outlier(kg_all):
    assert sum(t.outlier for *_, t in kg_all.values()) == OUTLIER_COUNT
    for c, (*_, t) in kg_all.items():
        ids = {f.id for f in t.flags}
        assert t.outlier == bool(ids & OUTLIER_FLAGS), c
    vip_only = [c for c, (*_, t) in kg_all.items() if {f.id for f in t.flags} & (OUTLIER_FLAGS | {"top_clv"}) == {"top_clv"}]
    assert vip_only and not any(kg_all[c][3].outlier for c in vip_only)


def test_urgency_score_formula_for_every_customer(kg_all):
    bad = [(c, t.urgency_score, round(oracle().urgency_score(c), 2)) for c, (*_, t) in kg_all.items()
           if t.urgency_score != pytest.approx(oracle().urgency_score(c), abs=0.006)]
    assert not bad, bad[:20]


def test_every_customer_has_archetype_tier_and_flags_list(kg_all):
    assert len(kg_all) == 750
    for c, (*_, t) in kg_all.items():
        assert t.archetype.id and t.archetype.reason and t.urgency_tier and isinstance(t.flags, list), c
        assert t.urgency_reasons, c


def _function_source(name: str) -> str:
    tree = ast.parse(SEGMENTS.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SEGMENTS.read_text(encoding="utf-8"), fn)


@pytest.mark.parametrize("fn", ["_archetype", "triage"])
def test_archetype_and_tier_never_read_age_or_payment(fn):
    src = _function_source(fn)
    assert "birth_year" not in src and "payment_method" not in src


def test_dunning_used_only_in_exclusions_s13_tiers_and_a4():
    """dunning_level may appear only in the exclusion predicate, S13 (via the exclusion) and the tier rules."""
    allowed = {("predicates.py", "excl_dunning"), ("segments.py", "triage"), ("events.py", "apply_event"),
               ("rules.py", "policy_src")}  # policy_src only returns the "table.column" label
    hits = set()
    for path in sorted((REPO / "nba" / "kg").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and "dunning_level" in (ast.get_source_segment(text, node) or ""):
                inner = [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef) and n is not node
                         and "dunning_level" in (ast.get_source_segment(text, n) or "")]
                if not inner:
                    hits.add((path.name, node.name))
    assert hits <= allowed, sorted(hits - allowed)
    # S13 must reuse the exclusion predicate rather than read dunning directly
    pred = (REPO / "nba" / "kg" / "predicates.py").read_text(encoding="utf-8")
    s13 = re.search(r"def dunning_or_cancellation.*?(?=\n@|\Z)", pred, re.S).group(0)
    assert "excl_dunning" in s13 and "dunning_level" not in s13


def test_triage_reasons_carry_a_signal_or_rule_id(kg_all):
    tag = re.compile(r"\[(S\d+|EXCL-[A-Z-]+|[A-Z]+-[A-Z-]+)\]")
    missing = collections.Counter()
    for c, (*_, t) in kg_all.items():
        for r in t.urgency_reasons:
            if r != "no trigger" and not tag.search(r):
                missing[re.sub(r"[\d.]+", "#", r)] += 1
    assert not missing, missing.most_common(5)
