"""AI steps (nba/ai): cluster review before approval, feedback memory. A fake backend stands in for the AI."""
import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from nba.ai import feedback
from nba.ai.llm import LLM, from_env
from nba.ai.review import review
from nba.engine.config import load_config
from nba.engine.runtime import Runtime


class FakeLLM(LLM):
    name = "fake"

    def __init__(self, answer):
        super().__init__()
        self.answer, self.seen = answer, []

    def _complete(self, system, user, schema, effort):
        self.seen.append(json.loads(user))
        return json.dumps(self.answer(json.loads(user)) if callable(self.answer) else self.answer)


@pytest.fixture(scope="module")
def rt(tables, states, policy, pop):
    runtime = Runtime(tables, dict(states), pop, policy, load_config(tables))
    runtime.cards()
    return runtime


def test_no_backend_means_code_only(monkeypatch):
    monkeypatch.setenv("MAINGAU_LLM", "none")
    llm = from_env()
    assert llm.name == "none" and llm.structured("s", {}, {}) is None


def test_review_splits_clusters_and_keeps_hard_flags(rt):
    plain = review(rt)
    s = plain["summary"]
    assert s["proposals"] == s["ready"] + s["needs_review"] and s["clusters"] > 10
    hard = [c for c in plain["customers"].values() if c["hard"]]
    assert hard and all(c["status"] == "needs_review" for c in hard)
    soft_only = [cid for cid, c in plain["customers"].items() if c["soft"] and not c["hard"]]
    assert soft_only and all(plain["customers"][c]["status"] == "needs_review" for c in soft_only)  # no AI: be careful
    fake = FakeLLM(lambda p: {"verdict": "fits_cluster", "reason_code": "other", "note": "fine", "cited": ["S99", p["allowed_ids"][0]]})
    with_ai = review(rt, fake, ai_limit=1000)
    assert with_ai["ai"]["reviewed"] == len(hard) + len(soft_only)
    assert all(with_ai["customers"][c]["status"] == "needs_review" for c in [k for k, v in plain["customers"].items() if v["hard"]])
    assert all(with_ai["customers"][c]["status"] == "ready" for c in soft_only)  # the AI settles soft cases only
    assert all("S99" not in v["ai"]["cited"] for v in with_ai["customers"].values() if v["ai"])  # unknown IDs dropped
    first = fake.seen[0]
    assert {"cluster", "proposed", "flags", "signals", "rules", "allowed_ids"} <= set(first)


def test_invalid_ai_answers_are_ignored(rt):
    bad = FakeLLM({"verdict": "send_now", "reason_code": "nope", "note": "x", "cited": []})
    r = review(rt, bad, ai_limit=5)
    assert r["ai"]["reviewed"] == 0 and all(c["ai"] is None for c in r["customers"].values())


def test_feedback_becomes_customer_memory_and_changes_the_next_decision(rt, tmp_path):
    items = feedback.from_agent_feedback(rt.tables["service_nba_feedback"].to_dict("records"))
    assert len(items) == 74 and {i["reason_code"] for i in items} <= set(feedback.REASON_CODES)
    path = tmp_path / "customer_memory.jsonl"
    result = feedback.process(rt, items, path)
    assert len(result["added"]) == 74 and result["proposals"]
    assert feedback.process(rt, items, path)["added"] == []  # nothing is remembered twice
    mem = rt.with_memory(path)
    changed = [c for c in mem.cards() if c.chosen.tuple_id != rt.card(c.customer_id).chosen.tuple_id]
    assert changed and all(any(r.rule_id == "MEMORY" for r in c.rules.results) for c in changed)


def test_ai_can_make_memory_stricter_but_not_looser(rt, tmp_path):
    item = {"source": "decision_log", "ref": "x@1", "customer_id": "MG-100068", "at": "2026-10-27T10:00:00+00:00",
            "action": "rejected", "offer_id": "P-EN-02", "channel": "email", "reason": "she was furious on the phone",
            "reason_code": None}
    looser = FakeLLM({"reason_code": "customer_upset", "memory_kind": "note", "offer_id": "none", "channel": "none",
                      "days": 1, "note": "Upset customer.", "global_hint": ""})
    m = feedback.process(rt, [item], tmp_path / "a.jsonl", looser)["added"][0]
    assert m["kind"] == "pause_sales" and m["reason_code"] == "customer_upset" and m["by"] == "ai:fake"  # default kept
    stricter = FakeLLM({"reason_code": "not_relevant", "memory_kind": "pause_sales", "offer_id": "none", "channel": "none",
                        "days": 500, "note": "Stop all sales for now.", "global_hint": "StromGarant e-mails annoy upset customers"})
    out = feedback.process(rt, [{**item, "ref": "x@2"}], tmp_path / "b.jsonl", stricter)
    m = out["added"][0]
    assert m["kind"] == "pause_sales" and m["until"].startswith("2027-10-27")  # stricter kind, days capped at 365
    assert any(p.get("from") == "MG-100068" for p in out["proposals"])  # global ideas go to a person, not into rules


def test_api_feedback_loop(tmp_path, rt):
    api = TestClient(create_app(runtime=rt, out_dir=tmp_path))
    r = api.post("/api/customers/MG-100068/decision", json={"action": "reject", "user": "anna", "reason": "has it already",
                                                            "reason_code": "already_has_product"})
    assert r.status_code == 200 and r.json()["reason_code"] == "already_has_product"
    offer = r.json()["from_tuple"].split("|")[0]
    learned = api.post("/api/ai/feedback", params={"ai": False}).json()
    mine = [m for m in learned["added"] if m["customer_id"] == "MG-100068"]
    assert mine and mine[0]["kind"] == "pause_offer" and mine[0]["offer_id"] == offer
    card = api.get("/api/customers/MG-100068").json()
    assert not card["chosen"]["tuple_id"].startswith(offer + "|")
    assert any(r["rule_id"] == "MEMORY" for r in card["rules"]["results"])
    assert api.get("/api/ai/review", params={"ai": False}).json()["summary"]["proposals"] > 0
