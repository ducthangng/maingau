"""nba.build reads the customer memory (--memory, --no-memory) and can learn it first (--learn)."""
import json

from nba.build import build, main
from nba.engine.runtime import Runtime

IDS = ["MG-100005", "MG-100023", "MG-100112"]
PAUSE = {"id": "M-MG-100023-1", "customer_id": "MG-100023", "kind": "pause_offer", "offer_id": "P-AS-01", "channel": None,
         "since": "2026-09-29T10:00:00", "until": "2027-09-29T10:00:00", "reason_code": "already_has_product",
         "source": "agent_feedback", "source_ref": "SF-test-1", "note": "dismissed: customer_already_has_product", "by": "rule"}


def _files(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def _card(out, cid):
    return json.loads((out / "customers" / f"{cid}.json").read_text())


def _run(*args):  # the data contract check has its own tests
    main(["--customers", ",".join(IDS), "--no-report", "--skip-validation", *map(str, args)])


def test_memory_file_changes_the_remembered_customer_only(tmp_path, capsys):
    memory = tmp_path / "customer_memory.jsonl"
    memory.write_text(json.dumps(PAUSE) + "\n{torn line\n")
    _run("--out", tmp_path / "before", "--no-memory")
    _run("--out", tmp_path / "after", "--memory", memory)
    out = capsys.readouterr().out.splitlines()
    assert "memory=none;" in out[0] and f"memory=1 entries (1 active) from {memory};" in out[1]
    before, after = _card(tmp_path / "before", "MG-100023"), _card(tmp_path / "after", "MG-100023")
    assert before["chosen"]["tuple_id"] == "P-AS-01|portal_popup|sie"
    assert after["chosen"]["tuple_id"] != before["chosen"]["tuple_id"]
    assert [r["result"] for r in after["rules"]["results"] if r["rule_id"] == "MEMORY"] == ["defer"]
    assert not any(r["rule_id"] == "MEMORY" for r in before["rules"]["results"])
    for cid in ("MG-100005", "MG-100112"):  # memory is per customer
        assert _card(tmp_path / "before", cid) == _card(tmp_path / "after", cid)


def test_no_memory_file_or_no_memory_flag_is_todays_build(tmp_path):
    build(Runtime.load(), tmp_path / "today", IDS, report=False)
    memory = tmp_path / "customer_memory.jsonl"
    memory.write_text(json.dumps(PAUSE) + "\n")
    _run("--out", tmp_path / "missing", "--memory", tmp_path / "none.jsonl")
    _run("--out", tmp_path / "ignored", "--memory", memory, "--no-memory")
    today = _files(tmp_path / "today")
    assert _files(tmp_path / "missing") == today == _files(tmp_path / "ignored")


def test_learn_twice_is_byte_identical_and_remembers_each_item_once(tmp_path, capsys):
    folder = tmp_path / "state"
    folder.mkdir()
    memory = folder / "customer_memory.jsonl"
    (folder / "decision_log.jsonl").write_text(json.dumps(
        {"customer_id": "MG-100112", "entry": {"ts": "2026-09-29T09:00:00+00:00", "action": "rejected", "actor": "anna",
                                               "from_tuple": "P-EN-01|outbound_call|sie", "reason_code": "wrong_channel",
                                               "reason": "prefers letters"}}) + "\n")
    (folder / "service_feedback.jsonl").write_text("{not json\n" + json.dumps(
        {"feedback_id": "SF-1", "customer_id": "MG-100023", "shown_at": "2026-09-29T10:00:00", "channel": "phone",
         "suggested_offer_id": "P-AS-01", "agent_action": "dismissed", "dismiss_reason": "customer_already_has_product",
         "offer_mentioned_to_customer": True, "customer_reaction": None, "converted_within_14d": None}) + "\n")
    _run("--out", tmp_path / "base", "--no-memory")
    _run("--out", tmp_path / "first", "--memory", memory, "--learn")
    lines = memory.read_text().splitlines()
    _run("--out", tmp_path / "second", "--memory", memory, "--learn")
    out = capsys.readouterr().out.splitlines()
    assert out[1].startswith("Learned 76 new memory entries from 76 feedback items")  # 74 workbook + 1 log + 1 service
    assert out[3].startswith("Learned 0 new memory entries") and "memory=76 entries (" in out[4]
    assert memory.read_text().splitlines() == lines and len({json.loads(x)["source_ref"] for x in lines}) == 76
    assert _files(tmp_path / "first") == _files(tmp_path / "second")
    mine = {json.loads(x)["customer_id"]: json.loads(x) for x in lines if json.loads(x)["source"] == "decision_log"}
    assert mine["MG-100112"]["kind"] == "block_channel" and mine["MG-100112"]["channel"] == "outbound_call"
    for cid, was in (("MG-100005", "P-MO-03|app_push|du"), ("MG-100023", "P-AS-01|portal_popup|sie"),
                     ("MG-100112", "P-EN-01|outbound_call|sie")):
        base, card = _card(tmp_path / "base", cid), _card(tmp_path / "first", cid)
        assert base["chosen"]["tuple_id"] == was and card["chosen"] != base["chosen"], cid
        assert any(r["rule_id"] == "MEMORY" for r in card["rules"]["results"]), cid


def test_shipped_build_is_identical_across_two_loads(tmp_path):
    for name in ("a", "b"):
        build(Runtime.load(), tmp_path / name, report=False)
    a, b = _files(tmp_path / "a"), _files(tmp_path / "b")
    assert a["index.json"] == b["index.json"] and a["summary.json"] == b["summary.json"]
    assert a == b
