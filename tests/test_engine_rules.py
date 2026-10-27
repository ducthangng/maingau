"""Rule Center (docs/rule-center.md): tier 2 rules, DEFER_UNTIL, capacity, registry, audit, API and build."""
import json
from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from nba.contracts import NO_ACTION, CustomerCard, RulesFile
from nba.engine.config import load_config
from nba.engine.rule_audit import legacy_audit
from nba.engine.rule_registry import RuleEditError, apply_op, next_custom_id, rule_tree
from nba.engine.rulecenter import Evaluator, customer_matches, load_rules, offer_matches, plan_capacity
from nba.engine.runtime import Runtime
from nba.state import build_states


@pytest.fixture(scope="module")
def rt(tables, states, policy, pop):
    runtime = Runtime(tables, dict(states), pop, policy, load_config(tables))
    runtime.cards()
    return runtime


def card(rt, cid):
    return rt.card(cid)


def result(c, rule_id):
    return next(r for r in c.rules.results if r.rule_id == rule_id)


# ---------------------------------------------------------------- the spec's test customers (§8)


def test_frequency_rules_defer_email_and_other_channels_are_tried(rt):
    c = card(rt, "MG-100267")  # 9 e-mails in 90 days
    assert result(c, "B-01").result == "defer" and result(c, "B-01").measured["count"] == 9
    assert c.chosen.tuple_id.split("|")[1] not in {"email", "newsletter_email"} and not c.chosen.deferred_until
    assert "Email 9/5 (90 d)" in c.rules.counter_line
    waiting = card(rt, "MG-100026")  # only the newsletter is allowed, and it is over the limit
    assert waiting.chosen.deferred_until and waiting.chosen.send_at >= waiting.chosen.deferred_until
    assert waiting.chosen.reason_line.startswith("Held back until")
    assert next(k for k in waiting.checklist if k.item == "contact_cap").passed is False


def test_consent_cases(rt):
    assert card(rt, "MG-100023").chosen.tuple_id.startswith("P-AS-01|")  # newsletter yes, 1:1 e-mail no
    for cid in ("MG-100067", "MG-100102"):  # unsubscribed via NL-2613 late 09/2026
        assert result(card(rt, cid), "C-03").result == "block"
    c = card(rt, "MG-100001")  # portal/app consent but no app
    assert c.chosen.tuple_id.split("|")[1] == "portal_popup"
    assert any(b.rule_center_id == "C-01" and b.channel == "app_push" for b in c.blocked)


def test_b08_keeps_the_k11_call_and_drops_cheap_calls(rt):
    c = card(rt, "MG-100112")
    assert c.chosen.tuple_id == "P-EN-01|outbound_call|sie"  # €14.87 ≥ €10
    assert {b.offer_id for b in c.blocked if b.rule_center_id == "B-08"} == {"P-MO-01", "P-SL-01"}


def test_service_only_customers(rt):
    for cid, rc in (("MG-100096", "C-06"), ("MG-100186", "C-07")):
        c = card(rt, cid)
        assert c.chosen.tuple_id.startswith("P-SV-01|") and result(c, rc).result == "block"


def test_b05_pauses_an_offer_after_two_dismissals(tables, policy, rt):
    rule = next(r for r in rt.cfg.rules if r.id == "B-05")
    early = build_states(tables, datetime(2026, 9, 1, 12), customer_ids=["MG-100051"])["MG-100051"]
    n, last, until = Evaluator(early, policy, rt.cfg).offer_cooldown(rule, "P-EN-02")
    assert (n, last.date().isoformat(), until.date().isoformat()) == (2, "2026-07-25", "2026-09-23")
    assert Evaluator(rt.states["MG-100051"], policy, rt.cfg).offer_cooldown(rule, "P-EN-02")[2] is None  # ended 23.09


def test_contact_cap_defers_instead_of_dropping(rt):
    c = card(rt, "MG-100171")  # one NBA contact + an offer a service agent mentioned
    assert result(c, "B-02").result == "defer" and c.chosen.deferred_until == result(c, "B-02").until
    assert any(b.rule_id == "CONTACT-CAP" and b.offer_id == "*" and b.until for b in c.blocked)


# ---------------------------------------------------------------- what-if, capacity, registry


def test_what_if_b01_from_5_to_3(rt):
    from nba.engine.rule_whatif import what_if

    settings = rt.cfg.settings
    edited = dict(settings["business_rules"])
    edited["B-01"] = {**edited["B-01"], "max": 3}
    report = what_if(rt, rt.with_rules(settings={"business_rules": edited}))
    assert (report["before"]["customers_by_rule"]["B-01"], report["after"]["customers_by_rule"]["B-01"]) == (328, 492)
    assert report["changed"] > 0 and report["after"]["waiting"] >= report["before"]["waiting"]
    assert report["rule_set_version"]["before"] != report["rule_set_version"]["after"]


def test_capacity_switches_channel_or_waits(rt):
    calls = [c for c in rt.cards() if "|outbound_call|" in c.chosen.tuple_id and not c.chosen.deferred_until]
    assert len(calls) > 1
    overflow = plan_capacity(rt.cards(), {"outbound_call": 1})
    assert len(overflow) == len(calls) - 1
    edited = dict(rt.cfg.settings["business_rules"])
    edited["B-09"] = {**edited["B-09"], "per_week": {"outbound_call": 1}}
    small = rt.with_rules(settings={"business_rules": edited})
    after = {c.customer_id: c for c in small.cards()}
    moved = [cid for cid in overflow if after[cid].chosen.tuple_id != card(rt, cid).chosen.tuple_id
             or after[cid].chosen.deferred_until]
    assert moved == sorted(overflow) and all(result(after[cid], "B-09").result == "defer" for cid in overflow)


def test_registry_edits(rt, policy):
    settings, cap = rt.cfg.settings, policy.config["contact_cap"]
    for op, status in (({"op": "update", "rule_id": "C-01", "active": False}, 403),
                       ({"op": "update", "rule_id": "B-07", "active": False}, 403),
                       ({"op": "update", "rule_id": "B-02", "active": False}, 422),
                       ({"op": "update", "rule_id": "B-01", "params": {"max": 0}}, 422),
                       ({"op": "update", "rule_id": "B-99"}, 404),
                       ({"op": "delete", "rule_id": "B-03"}, 403)):
        with pytest.raises(RuleEditError) as err:
            apply_op(settings, cap, op, known_ids=frozenset(["B-03"]))
        assert err.value.status == status, op
    new, _ = apply_op(settings, cap, {"op": "update", "rule_id": "B-01", "params": {"max": 3}})
    assert next(r for r in load_rules(new) if r.id == "B-01").name == "Max 3 e-mails in 90 days"
    assert next_custom_id({"custom_rules": [{"id": "U-2"}]}, [{"op": "create", "rule": {"id": "U-5"}}]) == "U-6"
    tree = rule_tree(settings, policy)
    assert [n.id for n in tree if n.locked] == [f"C-0{i}" for i in range(1, 10)] + ["B-07"]


def test_custom_rule_tree_narrows_and_blocks(rt):
    rule = {"id": "U-1", "name": "No app: no mobile offers", "hard": True, "active": True,
            "condition": {"entity": "customer_master", "column": "app_installed", "op": "=", "value": False},
            "children": [{"id": "U-1.1", "active": True,
                          "condition": {"entity": "product_catalog", "column": "business_line", "op": "=", "value": "mobile"}}]}
    custom = rt.with_rules(settings={"custom_rules": [rule]})
    c = custom.card("MG-100001")
    assert any(b.rule_center_id == "U-1" and b.offer_id == "P-MO-01" for b in c.blocked)
    assert not any(x.offer_id == "P-MO-01" for x in c.candidates)
    off = [{**rule, "children": [{**rule["children"][0], "active": False}]}]  # without the sub-rule: all sales
    assert all(x.action_type == "service" for x in rt.with_rules(settings={"custom_rules": off}).card("MG-100001").candidates)


# ---------------------------------------------------------------- audit, API, build


def test_legacy_audit_reproduces_the_spec(rt):
    audit = legacy_audit(rt)
    assert audit["sends"] == 2022 and audit["by_rule"]["C-01"] == 829  # "about 830"
    assert audit["by_channel"]["app_push"]["C-01 (no app / portal)"] == 114


def test_api_rule_center(tmp_path, rt):
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    rules = RulesFile.model_validate(api.get("/api/rules").json())
    assert {e.id for e in rules.entities} >= {"customer_master", "consent_status", "product_catalog"}
    assert api.put("/api/rules/C-06", json={"by": "m", "active": False}).status_code == 403
    deferred = card(rt, "MG-100026")
    assert api.post("/api/customers/MG-100026/decision", json={"action": "approve", "user": "r"}).status_code == 409
    oid, ch, tone = deferred.chosen.tuple_id.split("|")
    assert oid and ch and tone
    override = api.post("/api/customers/MG-100112/decision", json={"action": "override", "user": "r",
                        "tuple": {"offer_id": "P-MO-01", "channel": "outbound_call", "tone": "sie"}})
    assert override.status_code == 409 and "B-08" in override.json()["detail"]["rule_ids"]
    body = {"by": "marketing", "hard": True, "condition": {"entity": "customer_master", "column": "app_installed",
            "op": "=", "value": False}}
    created = api.post("/api/rules", json=body).json()  # U-1..U-4 are the demo rules in config/nba.yaml
    assert any(n["id"] == "U-5" and n["tier"] == "hard" for n in created["rules"])
    assert api.delete("/api/rules/U-5", params={"by": "marketing"}).status_code == 200
    assert api.post("/api/rules", json=body).json()["rules"][-1]["id"] == "U-6"  # never reused
    versions = api.get("/api/rules/versions").json()
    assert [v["op"]["op"] for v in versions] == ["create", "delete", "create"] and all(v["by"] == "marketing" for v in versions)
    restarted = TestClient(create_app(runtime=Runtime(rt.tables, rt.states, rt.pop, rt.policy, load_config(rt.tables)),
                                      out_dir=tmp_path))
    assert [n["id"] for n in restarted.get("/api/rules").json()["rules"] if n["id"].startswith("U-")] == \
        ["U-1", "U-2", "U-3", "U-4", "U-6"]
    assert restarted.get("/api/customers/MG-100068").headers["content-type"].startswith("application/json")


# Demo rules in config/nba.yaml (docs/rule-center.md "Demo rules"): changed decisions when switched on, as documented
DEMO = {"U-1": (10, 40), "U-2": (8, 40), "U-3": (50, 120), "U-4": (8, 40)}


def _decision(row):
    return row["chosen_tuple"], (row.get("deferred_until") or "")[:10]


@pytest.mark.parametrize("rule_id", sorted(DEMO))
def test_demo_rules_switch_on_through_the_api(tmp_path, rt, rule_id):
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    rules = {n["id"]: n for n in api.get("/api/rules").json()["rules"]}
    assert rules[rule_id]["active"] is False  # off by default: the default decisions do not change
    before = {r["customer_id"]: _decision(r) for r in api.get("/api/customers").json()}
    whatif = api.post("/api/rules/whatif", json=[{"rule_id": rule_id, "active": True}])
    lo, hi = DEMO[rule_id]
    assert whatif.status_code == 200 and lo <= whatif.json()["changed"] <= hi, whatif.json()["changed"]
    on = api.put(f"/api/rules/{rule_id}", json={"active": True, "by": "Demo", "reason": "demo"})
    assert on.status_code == 200 and next(n for n in on.json()["rules"] if n["id"] == rule_id)["active"]
    changed = [r["customer_id"] for r in api.get("/api/customers").json() if _decision(r) != before[r["customer_id"]]]
    assert len(changed) == whatif.json()["changed"]
    for cid in changed:
        c = CustomerCard.model_validate(api.get(f"/api/customers/{cid}").json())
        assert any(r.rule_id == rule_id and r.result in {"block", "defer"} for r in c.rules.results), cid
        if rule_id != "U-3":  # U-3 holds back (DEFER_UNTIL); the others block tuples
            assert any(b.rule_center_id == rule_id for b in c.blocked), cid


def test_rule_edits_are_validated_before_they_are_logged(tmp_path, rt):
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    cond = {"entity": "customer_master", "column": "city", "op": "=", "value": "Köln"}
    made = api.post("/api/rules", json={"by": "m", "condition": cond, "effect": "DEFER_UNTIL"})
    assert made.status_code == 200
    rid = made.json()["rules"][-1]["id"]
    refused = [
        ("put", f"/api/rules/{rid}", {"by": "m", "params": {"days": "abc"}}, "days must be a whole number from 1 to 365"),
        ("put", f"/api/rules/{rid}", {"by": "m", "params": {"days": 0}}, "days must be"),
        ("put", f"/api/rules/{rid}", {"by": "m", "params": {"days": 400}}, "days must be"),
        ("put", f"/api/rules/{rid}", {"by": "m", "params": {"channels": ["fax"]}}, "channels must be marketing channels"),
        ("put", f"/api/rules/{rid}", {"by": "m", "params": {"name": 5}}, "name must be text"),
        ("put", "/api/rules/B-01", {"by": "m", "params": {"window_days": 400}}, "window_days must be"),
        ("put", "/api/rules/B-02", {"by": "m", "params": {"window_days": 400}}, "window_days must be"),
        ("post", "/api/rules", {"by": "m", "condition": {**cond, "entity": "customers"}}, "unknown entity"),
        ("post", "/api/rules", {"by": "m", "condition": {**cond, "column": "citty", "op": "!="}}, "has no column 'citty'"),
        ("post", "/api/rules", {"by": "m", "condition": {**cond, "value": None}}, "needs a value"),
        ("post", "/api/rules", {"by": "m", "condition": cond, "effect": "REQUIRE_APPROVAL"}, "not supported for custom rules"),
        ("post", "/api/rules", {"by": "m", "condition": cond, "effect": "CANCEL_PENDING"}, "not supported for custom rules"),
        ("post", "/api/rules", {"by": "m", "condition": {**cond, "op": ">=", "value": "many"}}, ">= needs a number"),
        ("post", "/api/rules", {"by": "m", "condition": {**cond, "op": "within_days", "value": 999}}, "within_days"),
        ("post", "/api/rules/whatif", [{"condition": {**cond, "column": "citty"}}], "has no column"),
        ("post", "/api/rules/whatif", [{"rule_id": rid, "params": {"days": "abc"}}], "days must be"),
    ]
    for method, path, body, text in refused:
        r = getattr(api, method)(path, json=body)
        assert r.status_code == 422 and text in r.json()["detail"], (path, body, r.json())
    assert len(api.get("/api/rules/versions").json()) == 1  # nothing refused reached the rule log
    assert api.put(f"/api/rules/{rid}", json={"by": "m", "params": {"days": 14}}).status_code == 200
    held = api.get("/api/customers/MG-100001").json()  # Köln: held back 14 days after the snapshot (30.09)
    assert held["chosen"]["deferred_until"] >= "2026-10-14"
    assert any(r["rule_id"] == rid and r["result"] == "defer" for r in held["rules"]["results"])


def test_a_missing_column_never_matches(rt):
    state = rt.states["MG-100001"]
    typo = {"entity": "customer_master", "column": "citty", "op": "!=", "value": "Köln"}
    assert not customer_matches(typo, state, state.eval_time)
    assert customer_matches({**typo, "column": "city", "value": "Berlin"}, state, state.eval_time)
    assert not offer_matches({**typo, "entity": "product_catalog"}, rt.cfg.offers["P-EN-01"])


def test_api_starts_with_a_damaged_rule_log(tmp_path, rt):
    ops = [{"op": "update", "rule_id": "U-2", "active": True}, {"op": "update", "rule_id": "U-99", "active": True},
           {"op": "update", "rule_id": "U-3", "params": {"days": "abc"}}]  # ok, unknown rule, bad value (older API)
    log = "".join(json.dumps({"version": i, "by": "Demo", "op": op}) + "\n" for i, op in enumerate(ops, 1))
    (tmp_path / "rule_versions.jsonl").write_text(log + '{"version": 4, "op": {"op": "upd', encoding="utf-8")  # torn
    (tmp_path / "decision_log.jsonl").write_text('{"customer_id": "MG-100068", "entry": {"ts": "2026', encoding="utf-8")
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    rules = {n["id"]: n for n in api.get("/api/rules").json()["rules"]}
    assert rules["U-2"]["active"] and not rules["U-3"]["active"]
    versions = api.get("/api/rules/versions").json()
    assert [(v["version"], "skipped" in v) for v in versions] == [(1, False), (2, True), (3, True)]
    assert "unknown rule U-99" in versions[1]["skipped"] and "days" in versions[2]["skipped"]
    logged = api.get("/api/customers/MG-100068").json()["decision_log"]
    assert [e["actor"] for e in logged] == ["engine"]  # the torn decision is skipped
    assert api.post("/api/customers/MG-100068/decision", json={"action": "reject", "user": "r", "reason": "x"}).status_code == 200
    assert api.put("/api/rules/U-2", json={"by": "Demo", "active": False}).status_code == 200
    assert [v["version"] for v in api.get("/api/rules/versions").json()] == [1, 2, 3, 4]  # on a line of its own
    restarted = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    assert not {n["id"]: n for n in restarted.get("/api/rules").json()["rules"]}["U-2"]["active"]
    assert len(restarted.get("/api/customers/MG-100068").json()["decision_log"]) == len(logged) + 1


def test_api_cors_preflight(tmp_path, rt):
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    pre = api.options("/api/rules", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"})
    assert pre.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_build_writes_rules_and_rule_log(tmp_path, rt):
    from nba.build import build

    build(rt, tmp_path, ["MG-100026", "MG-100112"], report=False)
    RulesFile.model_validate_json((tmp_path / "rules.json").read_text())
    log = [json.loads(x) for x in (tmp_path / "rule_log.jsonl").read_text().splitlines()]
    assert [r["customer_id"] for r in log] == ["MG-100026", "MG-100112"]
    assert log[0]["deferred_until"] and log[0]["rule_set_version"].startswith("rs-1:")
    assert {r["rule_id"] for r in log[1]["results"]} >= {"C-01", "B-01", "B-02", "B-08"}


def test_no_action_has_no_checklist(rt):
    for c in rt.cards():
        if c.chosen.tuple_id == NO_ACTION:
            assert c.checklist == []
            break
    else:
        pytest.fail("no NO_ACTION customer")


def test_bad_rules_stop_loading(tables):
    cfg = load_config(tables)
    bad = {**cfg.settings, "business_rules": {**cfg.settings["business_rules"],
                                               "B-04": {**cfg.settings["business_rules"]["B-04"], "channels": ["fax"]}}}
    with pytest.raises(ValueError):
        load_rules(bad)
    assert replace(cfg, _rules=None).rules  # the shipped config is valid


def test_marketer_rulebook_edits_business_rules(tables):
    from nba.rules.__main__ import base_sections, names_for
    from nba.rules.cards import compile_cards, render

    base = base_sections()
    names = names_for(base, tables)
    text = render(base, names, None, "x")
    assert '"E-mails per customer":' in text and "newsletters count: no" in text
    edited_text = text.replace('"E-mails per customer":\n    active: yes\n    at most: 5', '"E-mails per customer":\n    active: yes\n    at most: 3')
    assert edited_text != text
    edited, found, _ = compile_cards(edited_text, base, names)
    assert edited["nba"]["business_rules"]["B-01"]["max"] == 3
    assert [(c.card, c.field, c.before, c.after) for c in found] == [("E-mails per customer", "at most", 5, 3)]
