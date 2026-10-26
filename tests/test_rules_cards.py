"""Marketer rulebook (nba/rules/cards.py): plain cards in, the right rule-file settings out."""
from __future__ import annotations

import re
import shutil

import pytest

from nba.data import REPO, load_workbook
from nba.rules.book import SOURCES, apply, load_sources, plain
from nba.rules.cards import CardError, Names, compile_cards, render


@pytest.fixture(scope="module")
def base():
    return {n: plain(v) for n, v in load_sources().items()}


@pytest.fixture(scope="module")
def names(base):
    return Names(base, {r["product_id"]: r["product_name"] for r in load_workbook()["product_catalog"].to_dict("records")})


@pytest.fixture(scope="module")
def text(base, names):
    return render(base, names, None, "fp")


def set_field(text: str, card: str, field: str, value: str) -> str:
    i = text.index(f'"{card}":')
    j = text.index(f"    {field}:", i)
    return text[:j] + f"    {field}: {value}" + text[text.index("\n", j):]


def test_rendered_file_has_no_internal_ids(text):
    editable = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"\b(P-[A-Z]{2}-\d\d|S\d{1,2}|N-[A-Z-]+|MG-\d+)\b", editable)
    assert '"Wallbox bought, no Autostrom":' in text and '"MAINGAU Autostrom":' in text


def test_unchanged_file_compiles_to_the_same_rules(text, base, names):
    edited, found, fp = compile_cards(text, base, names)
    assert found == [] and edited == base and fp == "fp"


def test_card_edits_map_to_rule_settings(text, base, names):
    t = set_field(text, "More household members than SIMs", "active", "no")
    t = set_field(t, "MAINGAU Autostrom", "never by", '["sms", "Phone call"]')
    t = set_field(t, "StromGarant", "never in tone", "[Du]")
    t = set_field(t, "HEMS Starter-Set", "active", "no")
    t = set_field(t, "Judging an offer", "working when chance it helps is at least", '"85%"')
    t = set_field(t, "Marketing contact limit", "max contacts", "1")
    edited, found, _ = compile_cards(t, base, names, by="Tester")
    assert "S6" not in edited["kg"]["signals"]["enabled"] and "S5" in edited["kg"]["signals"]["enabled"]
    overrides = edited["nba"]["p_overrides"]
    assert set(overrides) == {"P-AS-01|sms", "P-AS-01|outbound_call", "P-EN-02|*|du", "P-SL-01"}
    assert all(o["p"] == 0.0 and o["approved_by"] == "Tester" for o in overrides.values())
    assert edited["learn"]["status"]["green_p_positive"] == 0.85
    assert edited["kg"]["contact_cap"]["max_contacts"] == 1
    hard = {c.where for c in found if c.hard}
    assert hard == {"Contact limits and blocks › Marketing contact limit › max contacts"}
    assert len(found) == 6


def test_turning_an_offer_back_on_removes_only_its_block(base, names):
    blocked = {**base, "nba": {**base["nba"], "p_overrides": {
        "P-AS-01": {"p": 0.0, "case": "RULEBOOK", "approved_by": "x"},
        "P-MO-01": {"p": 0.05, "case": "FIX-P-MO-01", "approved_by": "y"}}}}
    t = render(blocked, names, None, "fp")
    assert re.search(r'"MAINGAU Autostrom":\n    active: no', t)
    edited, found, _ = compile_cards(set_field(t, "MAINGAU Autostrom", "active", "yes"), blocked, names)
    assert set(edited["nba"]["p_overrides"]) == {"P-MO-01"}  # the reviewed take-up rate stays
    assert [c.after for c in found] == [True]


@pytest.mark.parametrize("card,field,value,message", [
    ("Marketing contact limit", "max contacts", "two", "whole number"),
    ("Rank offers by", "rank by", '"cheapest first"', "choose one of"),
    ("MAINGAU Autostrom", "never by", '["Fax"]', "unknown Fax"),
    ("Judging an offer", "working when chance it helps is at least", '"150%"', "between 0% and 100%"),
    ("StromAktiv", "active", "maybe", "yes or no"),
])
def test_bad_values_are_explained(text, base, names, card, field, value, message):
    with pytest.raises(CardError, match=message):
        compile_cards(set_field(text, card, field, value), base, names)


def test_renamed_card_is_refused(text, base, names):
    with pytest.raises(CardError, match="do not rename"):
        compile_cards(text.replace('"StromAktiv":', '"Strom Aktiv":'), base, names)


def test_apply_from_cards_writes_compact_lines(tmp_path, text, base, names):
    for rel in SOURCES.values():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, tmp_path / rel)
    edited, _, _ = compile_cards(set_field(text, "MAINGAU Autostrom", "never by", "[SMS]"), base, names, by="Tester")
    written = apply(tmp_path, edited)
    assert list(written) == ["config/nba.yaml"]
    added = (tmp_path / "config/nba.yaml").read_text(encoding="utf-8").splitlines()[-2:]
    assert added[0] == "p_overrides:" and added[1].startswith("  P-AS-01|sms: {p: 0.0, case: RULEBOOK")
