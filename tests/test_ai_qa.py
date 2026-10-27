"""AI test harness (nba/ai/qa.py): AI tester, marketer and judge on the real pipeline; code oracles decide.

A fake backend stands in for the AI here. The live run against a real backend is opt-in:
MAINGAU_AI_QA=1 MAINGAU_LLM=claude|ollama pytest -m ai_live
"""
import json
import os

import pytest

from nba.ai import qa
from nba.ai.llm import LLM, from_env
from nba.engine.config import load_config
from nba.engine.runtime import Runtime


class FakeLLM(LLM):
    """Answers by role (tester, judge, marketer) and records what it was shown."""

    name = "fake"

    def __init__(self, tester=None, judge=None, marketer=None):
        super().__init__()
        self.answers = {"test scenarios": tester, "review one test": judge, "careful CRM marketer": marketer}
        self.seen = []

    def _complete(self, system, user, schema, effort):
        role = next(k for k in self.answers if k in system)
        self.seen.append((role, json.loads(user)))
        answer = self.answers[role]
        answer = answer(json.loads(user)) if callable(answer) else answer
        return None if answer is None else json.dumps(answer)


def scenario(cid, event_type, **kw):
    base = {"customer_id": cid, "event_type": event_type, "consent_type": "none", "new_status": "none",
            "ticket_category": "none", "ticket_channel": "none", "commodity": "none", "new_level": 0, "count": 1,
            "product_name": "none", "story": "test", "expect_no_sales": False, "expect_rule": "none", "expect_signal": "none"}
    return base | kw


@pytest.fixture(scope="module")
def rt(tables, states, policy, pop):
    return Runtime(tables, dict(states), pop, policy, load_config(tables))


@pytest.fixture(scope="module")
def seeds(rt):
    return [qa.run_scenario(rt, sc) for sc in qa.seed_scenarios(rt)]


def test_seed_scenarios_cover_every_event_type_and_pass(seeds):
    assert {r["scenario"]["event_type"] for r in seeds} == set(qa.EVENT_TYPES)
    assert len({r["scenario"]["customer_id"] for r in seeds}) == len(seeds)  # a different customer each time
    failed = {r["scenario"]["id"]: [x for x in r["checks"] if not x["ok"]] for r in seeds if not r["passed"]}
    assert failed == {}
    by_id = {r["scenario"]["id"]: r for r in seeds}
    for sid in ("seed-ticket", "seed-dunning", "seed-cancellation"):  # a hard rule stops sales and revokes the pending card
        names = {x["check"] for x in by_id[sid]["checks"]}
        assert "no_sales_after_exclusion" in names and "pending_sales_card_revoked" in names
        assert by_id[sid]["after"]["action_type"] not in qa.SALES
    assert "withdrawn_consent_not_used" in {x["check"] for x in by_id["seed-consent"]["checks"]}
    assert "no_personalisation_without_profiling" in {x["check"] for x in by_id["seed-profiling"]["checks"]}
    assert "S2" in by_id["seed-charging"]["after"]["signals"] and "S1" in by_id["seed-gas"]["after"]["signals"]


def test_oracles_catch_a_broken_decision(rt, seeds):
    """Mutation test: the oracles fail when the engine's output breaks a hard rule."""
    ok = rt.card(next(r["scenario"]["customer_id"] for r in seeds if r["scenario"]["id"] == "seed-order"))
    assert all(x["ok"] for x in qa.invariants(ok, rt.policy))
    broken = ok.model_copy(deep=True)
    broken.profile.exclusions[0].active = True  # an exclusion is active but a sales offer is still chosen
    broken.chosen.status = "approved"  # and it looks sent without a person
    failed = {x["check"] for x in qa.invariants(broken, rt.policy) if not x["ok"]}
    assert {"exclusion_means_no_sales", "nothing_sent_without_approval"} <= failed
    offer, channel, _ = ok.chosen.tuple_id.split("|")
    for ch in broken.profile.channels:
        ch.allowed = ch.allowed and ch.channel != channel  # the chosen channel lost its consent
    assert "channel_has_consent" in {x["check"] for x in qa.invariants(broken, rt.policy) if not x["ok"]}


def test_ai_tester_scenarios_are_validated_and_run(rt):
    pool = qa._pool(rt, 24)
    cid = pool[0]
    fake = FakeLLM(tester={"scenarios": [
        scenario(cid, "ticket_created", ticket_category="billing", ticket_channel="chat", expect_no_sales=True,
                 expect_rule="EXCL-OPEN-TICKET"),
        scenario("MG-999999", "ticket_created"),  # not in the pool
        scenario(cid, "consent_changed"),  # no consent type
        scenario(cid, "dunning_level_changed", new_level=9, expect_signal="S2"),  # level capped; a wrong expectation
    ]})
    out, notes = qa.ai_scenarios(rt, fake, n=8)
    assert [s.event_type for s in out] == ["ticket_created", "dunning_level_changed"] and len(notes) == 2
    assert out[1].params["new_level"] == 3 and all(s.source == "ai:fake" for s in out)
    role, shown = fake.seen[0]
    assert role == "test scenarios" and {c["customer_id"] for c in shown["customers"]} == set(pool)
    results = [qa.run_scenario(rt, s) for s in out]
    assert results[0]["passed"] and not results[0]["mismatch"]
    assert results[1]["passed"] and results[1]["mismatch"] == ["tester expected signal S2"]  # a finding, not a failure


def test_judge_cannot_clear_a_failure_and_cites_only_evidence(seeds):
    results = json.loads(json.dumps(seeds[:3]))
    results[0]["checks"].append({"check": "made_up_failure", "ok": False, "detail": "test"})
    results[0]["passed"] = False
    fake = FakeLLM(judge={"verdict": "explainable", "reason_code": "ok", "note": "fine", "cited": ["S99", "EXCL-OPEN-TICKET"]})
    assert qa.judge(results, fake, limit=10) == 3
    assert results[0]["passed"] is False and results[0]["judge"]["verdict"] == "explainable"
    assert all("S99" not in r["judge"]["cited"] for r in results)
    assert fake.seen[0][1]["checks"] == [{"check": "made_up_failure", "ok": False, "detail": "test"}]  # failures first


def test_workflow_through_the_api_with_an_ai_marketer(rt, tmp_path):
    fake = FakeLLM(marketer=lambda pack: {"action": "reject" if pack["delta_clv_eur"] < 15 else "approve",
                                          "reason_code": "not_relevant", "reason": "value too small for this customer"},
                   judge=None)
    flow = qa.workflow(rt, fake, tmp_path, n=5)
    assert flow["passed"], [x for x in flow["checks"] if not x["ok"]]
    assert {d["by"] for d in flow["decisions"]} == {"ai:fake"} and any(d["action"] == "reject" for d in flow["decisions"])
    names = {x["check"].split(":")[0] for x in flow["checks"]}
    assert {"summary_matches_index", "overview_reason_for_personalised", "rejected_offer_not_proposed_again",
            "memory_rule_applied", "journey_newest_first", "review_keeps_hard_flags_with_a_person"} <= names


def test_run_writes_the_report_without_a_backend(rt, tmp_path):
    report = qa.run(rt, LLM(), tmp_path, n_workflow=3)
    s = report["summary"]
    assert report["backend"] == "none" and s["ai"] == 0 and s["failed"] == 0 and s["workflow_passed"]
    assert (tmp_path / "report.json").exists() and "AI QA report" in (tmp_path / "report.md").read_text()


@pytest.mark.ai_live
@pytest.mark.skipif(os.environ.get("MAINGAU_AI_QA") != "1", reason="live AI run is opt-in: MAINGAU_AI_QA=1")
def test_live_ai_qa(rt, tmp_path):
    llm = from_env()
    if not llm.enabled or llm.name == "none":
        pytest.skip("no AI backend configured (MAINGAU_LLM)")
    report = qa.run(rt, llm, tmp_path, n_ai=6, n_workflow=4, judge_limit=10)
    s = report["summary"]
    assert s["ai"] > 0, report["notes"]
    assert s["failed"] == 0, [r["checks"] for r in report["scenarios"] if not r["passed"]]
    assert s["workflow_passed"]
