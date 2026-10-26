"""Rulebook (nba/rules): one file in, edits found and classified, written back minimally, impact checked."""
from __future__ import annotations

import shutil

import pytest
from ruamel.yaml import YAML

from nba.data import REPO
from nba.rules.book import SOURCES, all_changes, apply, export, load_sources, merge_text, plain
from nba.rules.impact import impact


@pytest.fixture()
def root(tmp_path):
    for rel in SOURCES.values():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, tmp_path / rel)
    export(tmp_path)
    return tmp_path


def edit(root, *path_value):
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    book = root / "rules.yaml"
    data = y.load(book.read_text(encoding="utf-8"))
    for path, value in path_value:
        node = data
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    with book.open("w", encoding="utf-8") as f:
        y.dump(data, f)


def test_export_holds_every_rule_file_and_has_no_edits(root):
    text = (root / "rules.yaml").read_text(encoding="utf-8")
    for name, rel in SOURCES.items():
        assert f"\n{name}:" in text and str(rel) in text
    assert all_changes(root) == ([], False)


def test_edits_are_found_and_hard_rules_flagged(root):
    edit(root, (("kg", "contact_cap", "max_contacts"), 3), (("learn", "status", "green_p_positive"), 0.85),
         (("policy", "signals", "S6", "strength"), "medium"))
    found, moved = all_changes(root)
    by_where = {c.where: c for c in found}
    assert not moved and len(found) == 3
    assert by_where["config/kg.yaml › contact_cap › max_contacts"].hard
    assert not by_where["config/learn.yaml › status › green_p_positive"].hard
    assert by_where["kg/policy.yaml › signals › S6 › strength"].before == "weak"


def test_apply_changes_only_the_edited_lines(root):
    before = (root / "kg/policy.yaml").read_text(encoding="utf-8").splitlines()
    edit(root, (("policy", "signals", "S6", "strength"), "medium"))
    written = apply(root)
    after = (root / "kg/policy.yaml").read_text(encoding="utf-8").splitlines()
    assert list(written) == ["kg/policy.yaml"]
    diff = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and len(diff) == 1 and "strength: medium" in diff[0][1]
    assert (root / "config/kg.yaml").read_bytes() == (REPO / "config/kg.yaml").read_bytes()


def test_source_moved_after_export_is_detected(root):
    path = root / "config/nba.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n# someone else's edit\n", encoding="utf-8")
    assert all_changes(root)[1] is True


def test_merge_text_keeps_alignment():
    original = "a:  {x: 1,   y: 2}\nb:  {x: 3,   y: 4}\n"
    assert merge_text(original, "a: {x: 1, y: 2}\nb: {x: 3, y: 5}\n") == "a:  {x: 1,   y: 2}\nb: {x: 3, y: 5}\n"


IDS = ["MG-100006", "MG-100020", "MG-100023", "MG-100053", "MG-100096", "MG-100112"]


def test_loosened_cap_is_caught_and_tightened_cap_passes():
    base = {n: plain(v) for n, v in load_sources().items()}
    loose = {**base, "kg": {**base["kg"], "contact_cap": {**base["kg"]["contact_cap"], "max_contacts": 3}}}
    caught = impact(base, loose, customer_ids=IDS)
    assert any("contact cap" in v for v in caught.violations_after)
    signed = impact(base, loose, customer_ids=IDS, hold_to_edited=True)
    assert not signed.violations_after  # held to the signed-off rule, still no violation
    tight = {**base, "kg": {**base["kg"], "contact_cap": {**base["kg"]["contact_cap"], "max_contacts": 1}}}
    assert not impact(base, tight, customer_ids=IDS).violations_after


def test_broken_edit_is_reported_not_raised():
    base = {n: plain(v) for n, v in load_sources().items()}
    broken = {**base, "policy": {**base["policy"], "signals": {**base["policy"]["signals"],
                                                                "S6": {**base["policy"]["signals"]["S6"], "indicates": ["N-NOPE"]}}}}
    result = impact(base, broken, customer_ids=IDS)
    assert result.errors and "do not load" in result.errors[0]
