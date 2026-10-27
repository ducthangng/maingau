"""FastAPI decision service. Run: uvicorn api.app:app --port 8000 (one worker: the logs are replayed per process).

The append-only JSONL uses {customer_id, entry} envelopes; each entry is a
DecisionLogEntry. This keeps customer routing out of the shared entry model.
Rule Center edits are a second append-only log (rule_versions.jsonl, docs/rule-center.md §6), the
service agents' reactions a third (service_feedback.jsonl, read by the feedback step), and campaign fast-forwards
a fourth (campaign_outcomes.jsonl: simulated outcomes, added to the history the engine learns from).
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.replay import replay_preview

from nba.contracts import (
    CustomerCard, DecisionLogEntry, DecisionRequest, FastForwardRequest, IndexRow, Journey, NO_ACTION, RuleChange, RuleCreate, RulesFile,
    ServiceFeedbackRow, Summary, TupleRef, tuple_id,
)
from nba.data import DEFAULT_WORKBOOK, REPO
from nba.engine.assemble import build_chosen, checklist_for, evaluate_candidates, valuation_scores, value_candidate
from nba.engine.config import MissingDataError
from nba.ai import feedback as ai_feedback
from nba.ai.llm import from_env as llm_from_env
from nba.ai.review import review as ai_review
from nba.engine.rule_audit import legacy_audit
from nba.engine.rule_registry import RuleEditError, custom_rule, next_custom_id, replay_ops, rules_file
from nba.engine.rulecenter import Evaluator
from nba.engine.runtime import Runtime, index_rows, summary
from nba.kg.journey import build_journey, lookups as journey_lookups
from nba.learn import outcomes as campaign_outcomes
from nba.learn.impact import feedback_impact, learning_impact
from nba.kg.rules import check_tuple, generate_candidates, is_profiled
from nba.kg.signals import extract_signals
from nba.kg.viz import DEMO as KB_CUSTOMERS, export as kb_export

try:  # POSIX file locks; on Windows the in-process RLock below is the guard (Q-KG-23)
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

CORS_ORIGINS = os.environ.get("MAINGAU_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
log = logging.getLogger(__name__)


@contextmanager
def locked(stream, exclusive: bool):
    if fcntl is not None:
        fcntl.flock(stream, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield stream
    finally:
        if fcntl is not None:
            fcntl.flock(stream, fcntl.LOCK_UN)


class JsonlStore:
    """Append-only JSON lines, fsync'ed, with a shared lock for reads and an exclusive one for writes.

    Each record is one complete line written at once. A line that cannot be read (a torn last line after a
    crash, a hand edit) is skipped and logged once; the next record still starts on a line of its own."""

    def __init__(self, path):
        self.path = Path(path)
        self._skipped: set[int] = set()

    def check(self, record) -> None:
        """Raise ValueError / KeyError / TypeError for a record that must be skipped."""
        if not isinstance(record, dict):
            raise TypeError("not a JSON object")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8", errors="replace") as stream, locked(stream, exclusive=False):
            for n, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    self.check(record)
                except (ValueError, KeyError, TypeError) as exc:  # pydantic's ValidationError is a ValueError
                    if n not in self._skipped:
                        self._skipped.add(n)
                        log.warning("%s line %d skipped: %s", self.path, n, str(exc).partition("\n")[0])
                    continue
                out.append(record)
        return out

    def add(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str) + "\n").encode("utf-8")
        with self.path.open("a+b") as stream, locked(stream, exclusive=True):
            if stream.seek(0, os.SEEK_END):
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"\n":
                    data = b"\n" + data  # after a torn last line: keep this record on a line of its own
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


class DecisionStore(JsonlStore):
    def __init__(self, directory):
        super().__init__(Path(directory) / "decision_log.jsonl")

    def check(self, record) -> None:
        super().check(record)
        if not isinstance(record["customer_id"], str):
            raise TypeError("customer_id is not text")
        DecisionLogEntry.model_validate(record["entry"])

    def entries(self, cid):
        return [DecisionLogEntry.model_validate(r["entry"]) for r in self.records() if r["customer_id"] == cid]

    def append(self, cid, entry):
        self.add({"customer_id": cid, "entry": entry.model_dump(mode="json")})


class ServiceFeedbackStore(JsonlStore):
    """service_feedback.jsonl: ServiceFeedbackRow per line (the service agents' reactions in Customer 360°)."""

    def check(self, record) -> None:
        ServiceFeedbackRow.model_validate(record)


def refused(rule_ids, reasons):
    raise HTTPException(status_code=409, detail={"rule_ids": sorted(set(rule_ids)), "reasons": reasons})


def checked_tuple(runtime, cid, ref):
    """Regenerate with KG's own gates for every human-selected tuple."""
    state, policy = runtime.states[cid], runtime.policy
    blockers = check_tuple(state, ref.offer_id, ref.channel, policy)
    if blockers:
        refused([b.rule_id for b in blockers], [b.reason for b in blockers])
    if not is_profiled(state, policy) and ref.tone != "sie":
        refused(["CONSENT-PROFILING"], ["Without profiling consent only the default Sie tone is allowed"])
    signals = extract_signals(state, policy)
    allowed, _ = generate_candidates(state, signals, policy, ref.tone)
    target = next((c for c in allowed if c.tuple_id == tuple_id(ref.offer_id, ref.channel, ref.tone)), None)
    if target is None:
        refused(["DATA-MISSING"], ["The KG did not evaluate this tuple: no eligible need path or generic channel"])
    try:
        target = value_candidate(target, state, runtime.cfg, policy=policy)
    except MissingDataError as exc:
        refused(["DATA-MISSING"], [str(exc)])
    if target.valuation.delta_clv <= 0:
        refused(["ECON-NONPOSITIVE"], [f"Expected ΔCLV €{target.valuation.delta_clv:.2f} ≤ 0"])
    if target.origin == "generic" and is_profiled(state, policy):
        _, evaluated, _ = evaluate_candidates(allowed, state, policy, runtime.cfg)
        if not any(c.tuple_id == target.tuple_id for c in evaluated):
            refused(["HOLDING-PRECONDITION"], ["Generic fallback is allowed only when no signal or service action has positive expected ΔCLV"])
    if target.action_type != "service":  # Rule Center tier 2: a blocked or held-back tuple cannot be approved now
        blocks, defers = Evaluator(state, policy, runtime.cfg, capacity=runtime.capacity_overflow().get(cid)).verdict(target)
        if blocks or defers:
            refused([rid for rid, _ in blocks] + [rid for rid, _, _ in defers],
                    [reason for _, reason in blocks] + [f"held back until {until:%Y-%m-%d %H:%M}: {reason}"
                                                        for _, until, reason in defers])
    return target


def create_app(*, workbook=DEFAULT_WORKBOOK, out_dir=REPO / "out", p_mode=None, runtime=None,
               kb_file=REPO / "web" / "public" / "data" / "kg_viz.json"):
    app = FastAPI(title="MAINGAU NBA", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["*"])
    app.state.runtime = runtime
    app.state.base = None  # runtime as loaded from the config files, before the logged Rule Center edits
    app.state.skipped = {}  # rule log position -> why that logged edit no longer applies
    store, rule_log, lock = DecisionStore(out_dir), JsonlStore(Path(out_dir) / "rule_versions.jsonl"), RLock()
    feedback_log = ServiceFeedbackStore(Path(out_dir) / "service_feedback.jsonl")
    memory_path = Path(out_dir) / "customer_memory.jsonl"  # feedback memory per customer (nba.ai.feedback)
    outcome_log = JsonlStore(Path(out_dir) / "campaign_outcomes.jsonl")  # one fast-forward per campaign

    @app.exception_handler(RuleEditError)
    async def refused_edit(request, exc: RuleEditError):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    def known_ids(rt):
        return frozenset([*rt.policy.compliance, *(rt.cfg.settings.get("business_rules") or {}), "B-02", "B-07"])

    def with_ops(base, records, new=()):
        """The base runtime with the logged Rule Center edits, then the `new` operations, replayed (config/nba.yaml
        + config/kg.yaml contact_cap). A logged edit that no longer applies is skipped; a refused new one raises
        RuleEditError. Returns (runtime, {log position: why it was skipped})."""
        skipped = {}
        known = known_ids(base)
        settings, cap = replay_ops(base.cfg.settings, base.policy.config.get("contact_cap", {}),
                                   [r.get("op") for r in records], known,
                                   on_error=lambda i, exc: skipped.setdefault(i, str(exc)))
        settings, cap = replay_ops(settings, cap, list(new), known)
        if len(skipped) == len(records) and not new:
            return base, skipped
        policy = replace(base.policy, config={**base.policy.config, "contact_cap": cap})
        rt = base.with_rules(settings={k: settings.get(k) for k in ("business_rules", "custom_rules")}, policy=policy)
        return rt, skipped

    def context():
        with lock:
            if app.state.base is None:  # state is set only after a complete replay
                base = app.state.runtime or Runtime.load(workbook, p_mode=p_mode)
                base = campaign_outcomes.with_outcomes(base, outcome_log.records())
                records = rule_log.records()
                rt, skipped = with_ops(base, records)
                campaign_outcomes.remember(outcome_log.records(), memory_path)
                for i, why in sorted(skipped.items()):
                    log.warning("%s: version %s skipped, it no longer applies: %s", rule_log.path,
                                records[i].get("version", "?"), why)
                app.state.runtime, app.state.skipped = rt.with_memory(memory_path), skipped
                app.state.base = base
            return app.state.runtime

    def customer(cid):
        rt = context()
        if cid not in rt.states:
            raise HTTPException(404, "Unknown customer")
        return rt

    def card_with_decisions(cid, entries=None):
        rt = customer(cid)
        card = rt.card(cid)
        entries = store.entries(cid) if entries is None else entries
        card.decision_log += entries
        # A Rule Center edit alone does not drop approvals: checked_tuple re-checks every rule below.
        now = {k: v for k, v in card.meta.versions.model_dump().items() if k != "rules"}
        current = [i for i, e in enumerate(entries) if e.state_revision == card.meta.state_revision
                   and {k: v for k, v in e.versions.items() if k != "rules"} == now]
        if current:
            last = entries[current[-1]]
            if last.action in {"approved", "overridden"} and last.to_tuple and last.to_tuple != NO_ACTION:
                oid, channel, tone = last.to_tuple.split("|")
                try:
                    target = checked_tuple(rt, cid, TupleRef(offer_id=oid, channel=channel, tone=tone))
                except HTTPException:
                    return card  # An old approval never reactivates a currently blocked tuple.
                card.chosen = build_chosen(target, rt.states[cid], rt.cfg, card.chosen.service_mode)
                if not any(c.tuple_id == target.tuple_id for c in card.candidates):
                    card.candidates.append(target)
                card.chosen.status = last.action
                card.explanation_path = target.path
                card.checklist = checklist_for(target, card.data_quality)
                card.alternatives = [a for a in card.alternatives if a.tuple_id != target.tuple_id]
            elif last.action == "rejected":
                # Only while the card still shows what was rejected (today's proposal, or a person's approval or
                # override of it): once customer memory changes the proposal, the new action shows as proposed.
                if last.from_tuple == card_with_decisions(cid, entries[:current[-1]]).chosen.tuple_id:
                    card.chosen.status = "rejected"
        return card

    @app.get("/api/customers", response_model=list[IndexRow])
    def customers(q: str | None = None, offer: str | None = None, channel: str | None = None,
                  archetype: str | None = None, urgency_tier: str | None = None, flag: str | None = None,
                  confidence: str | None = None, service_mode: bool | None = None, personalised: bool | None = None):
        rt = context()
        rows = index_rows(rt.cards(), rt.states)
        filters = {"chosen_offer": offer, "channel": channel, "archetype": archetype,
                   "urgency_tier": urgency_tier, "confidence": confidence,
                   "service_mode": service_mode, "personalised": personalised}
        return [r for r in rows if all(v is None or getattr(r, k) == v for k, v in filters.items())
                and (not flag or flag in r.flags)
                and (not q or q.casefold() in r.customer_id.casefold() or q.casefold() in (r.city or "").casefold())]

    @app.get("/api/customers/{customer_id}", response_model=CustomerCard)
    def get_customer(customer_id: str):
        return card_with_decisions(customer_id)

    @app.get("/api/customers/{customer_id}/journey", response_model=Journey)
    def get_journey(customer_id: str):
        """Customer 360° journey: what happened and how the customer reacted (nba.kg.journey)."""
        rt = customer(customer_id)
        return build_journey(rt.states[customer_id], **journey_lookups(rt.tables, rt.policy))

    @app.get("/api/summary", response_model=Summary)
    def get_summary():
        rt = context()
        return summary(rt.cards(), rt.cfg, next(iter(rt.states.values())).eval_time, rt.policy)

    @app.post("/api/replay")
    def preview_replay(until: datetime | None = None):
        """Replay preview only: returns re-decisions and revocations without changing API state or approvals."""
        with lock:
            try:
                return replay_preview(context(), until, card_provider=card_with_decisions)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.post("/api/customers/{customer_id}/decision", response_model=DecisionLogEntry)
    def decision(customer_id: str, request: DecisionRequest):
        if not request.user.strip():
            raise HTTPException(422, "user must not be empty")
        if request.action == "reject" and not (request.reason or "").strip():
            raise HTTPException(422, "A rejection requires a reason")
        if request.action == "override" and request.tuple is None:
            raise HTTPException(422, "An override requires a tuple")
        with lock:
            rt = customer(customer_id)
            card = card_with_decisions(customer_id)
            previous = card.chosen.tuple_id
            target = None
            if request.action == "override":
                target = checked_tuple(rt, customer_id, request.tuple)
            elif request.action == "approve":
                if previous == NO_ACTION:
                    refused(["ECON-NONPOSITIVE"], [card.chosen.reason_line])
                if request.tuple and tuple_id(request.tuple.offer_id, request.tuple.channel, request.tuple.tone) != previous:
                    checked_tuple(rt, customer_id, request.tuple)
                    refused(["HOLDING-PRECONDITION"], ["The proposal has changed; reload it or submit an explicit override"])
                oid, channel, tone = previous.split("|")
                target = checked_tuple(rt, customer_id, TupleRef(offer_id=oid, channel=channel, tone=tone))
            entry = DecisionLogEntry(
                ts=datetime.now(timezone.utc).isoformat(), actor=request.user.strip(),
                action={"approve": "approved", "override": "overridden", "reject": "rejected"}[request.action],
                tuple_id=target.tuple_id if target else previous,
                from_tuple=previous, to_tuple=target.tuple_id if target else previous,
                reason=request.reason, reason_code=request.reason_code, state_revision=rt.states[customer_id].revision,
                versions=card.meta.versions.model_dump(),
                rules_applied=sorted({c.rule_id for c in target.checks}) if target else [],
                scores=valuation_scores(target.valuation) if target else {},
            )
            store.append(customer_id, entry)
            return entry

    # ------------------------------------------------------------ Rule Center (docs/rule-center.md §6)

    def rules_view(rt) -> RulesFile:
        return rules_file(rt.cfg.settings, rt.policy, rt.tables, next(iter(rt.states.values())).eval_time.isoformat())

    def edit(op: dict, by: str, reason: str | None) -> RulesFile:
        if not by.strip():
            raise HTTPException(422, "by must not be empty")
        with lock:
            context()
            records = rule_log.records()
            updated, _ = with_ops(app.state.base, records, [op])  # validated before anything is logged
            version = updated.cfg.versions(updated.policy).rules
            rule_log.add({"version": len(records) + 1, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "by": by.strip(), "reason": reason, "op": op, "rule_set_version": version})
            app.state.runtime = updated.with_memory(memory_path)
            return rules_view(updated)

    @app.get("/api/rules", response_model=RulesFile)
    def get_rules():
        return rules_view(context())

    @app.put("/api/rules/{rule_id}", response_model=RulesFile)
    def change_rule(rule_id: str, change: RuleChange):
        return edit({"op": "update", "rule_id": rule_id, "active": change.active, "params": change.params},
                    change.by, change.reason)

    @app.post("/api/rules", response_model=RulesFile)
    def create_rule(body: RuleCreate):
        with lock:
            rt = context()
            rid = next_custom_id(rt.cfg.settings, [r.get("op") for r in rule_log.records()])
            rule = custom_rule(body, rid, rt.tables)
            return edit({"op": "create", "rule": rule}, body.by, None)

    @app.delete("/api/rules/{rule_id}", response_model=RulesFile)
    def delete_rule(rule_id: str, by: str, reason: str | None = None):
        return edit({"op": "delete", "rule_id": rule_id}, by, reason)

    @app.get("/api/rules/versions")
    def rule_versions():
        """The edit log; an edit that no longer applies (skipped at start) carries `skipped` with the reason."""
        context()
        return [{**r, "skipped": app.state.skipped[i]} if i in app.state.skipped else r
                for i, r in enumerate(rule_log.records())]

    @app.post("/api/rules/whatif")
    def what_if(changes: list[RuleChange | RuleCreate]):
        """Decide every customer under the current rules and under the proposed edits; nothing is saved."""
        from nba.engine.rule_whatif import what_if as compare

        with lock:
            rt = context()
            ops, history = [], [r.get("op") for r in rule_log.records()]
            for change in changes:
                if isinstance(change, RuleCreate):
                    rid = next_custom_id(rt.cfg.settings, history + ops)
                    ops.append({"op": "create", "rule": custom_rule(change, rid, rt.tables)})
                elif not change.rule_id:
                    raise HTTPException(422, "each change needs rule_id")
                else:
                    ops.append({"op": "update", "rule_id": change.rule_id, "active": change.active, "params": change.params})
            proposed, _ = with_ops(rt, [], ops)
            return compare(rt, proposed)

    # ------------------------------------------------------------ AI steps (nba/ai; any backend or none)

    @app.get("/api/ai/review")
    def review_proposals(ai: bool = True):
        """Clusters of proposed actions: who is ready for bulk approval and who needs an individual decision."""
        return ai_review(context(), llm_from_env() if ai else None)

    @app.post("/api/ai/feedback")
    def learn_from_feedback(ai: bool = True):
        """Turn new rejections / overrides (and service-agent feedback) into customer memory; the next decision uses it."""
        with lock:
            rt = context()
            rows = ai_feedback.agent_rows(rt.tables["service_nba_feedback"].to_dict("records"), feedback_log.records())
            items = ai_feedback.from_decisions(store.records()) + ai_feedback.from_agent_feedback(rows)
            result = ai_feedback.process(rt, items, memory_path, llm_from_env() if ai else None)
            app.state.runtime = rt.with_memory(memory_path)
            # What this step changed: the decisions of the customers it just remembered something about
            result["impact"] = feedback_impact(rt, app.state.runtime, [m["customer_id"] for m in result["added"]])
            return result

    @app.get("/api/learn/impact")
    def get_learning_impact():
        """What the feedback loop learned (k, look-alike lift, customer memory) and which decisions it changed."""
        with lock:
            rt = context()
            cached = getattr(app.state, "learn_impact", None)
            if cached is None or cached[0] is not rt:
                app.state.learn_impact = (rt, learning_impact(rt))
            return app.state.learn_impact[1]

    # ------------------------------------------------------------ Campaign fast-forward (nba/learn/outcomes.py)

    def stored_outcome(campaign_id):
        return next((r for r in outcome_log.records() if r.get("campaign") == campaign_id), None)

    @app.post("/api/campaigns/{campaign_id}/fast-forward")
    def fast_forward(campaign_id: str, body: FastForwardRequest):
        """Simulate the 14 days after the send: who of the contacted bought, and the actual ΔCLV. The control group
        gets no outcome. The outcomes join the history, so k and the look-alike model learn from them. Once per
        campaign: a second call returns the stored result."""
        if not body.user.strip():
            raise HTTPException(422, "user must not be empty")
        if not campaign_id.strip() or len(campaign_id) > 80:
            raise HTTPException(422, "campaign id must be 1–80 characters")
        if not body.members:
            raise HTTPException(422, "a campaign without members has nothing to fast-forward")
        with lock:
            rt = context()
            if (done := stored_outcome(campaign_id)) is not None:
                return {**done, "already": True}
            sent_at = next(iter(rt.states.values())).eval_time
            outcomes = campaign_outcomes.simulate(rt, campaign_id, [m.model_dump() for m in body.members], sent_at)
            record = {"campaign": campaign_id, "by": body.user.strip(),
                      "simulated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "sent_at": sent_at.isoformat(), "horizon_days": campaign_outcomes.HORIZON_DAYS,
                      "outcomes": outcomes, "totals": campaign_outcomes.totals(outcomes)}
            base = campaign_outcomes.with_outcomes(app.state.base, [record])
            updated, _ = with_ops(base, rule_log.records())
            record["learned"] = campaign_outcomes.learned(rt, updated, outcomes)
            # Memory first: it is idempotent and repaired on start, so a crash before the record is never half-applied.
            remembered = campaign_outcomes.remember([record], memory_path)
            outcome_log.add(record)
            app.state.base, app.state.runtime = base, updated.with_memory(memory_path)
            # The sent customers' next best action, now that their outcome is known
            record["impact"] = feedback_impact(rt, app.state.runtime, [m["customer_id"] for m in remembered])
            return {**record, "already": False}

    @app.get("/api/campaigns/{campaign_id}/outcomes")
    def campaign_outcome(campaign_id: str):
        """The stored fast-forward of a campaign (404 before the first one)."""
        if (done := stored_outcome(campaign_id)) is None:
            raise HTTPException(404, "This campaign has not been fast-forwarded")
        return done

    def kb_live(rebuild=False):
        with lock:
            rt = context()
            cached = getattr(app.state, "kb", None)
            if rebuild or cached is None or cached[0] is not rt:
                app.state.kb = (rt, kb_export(rt, [c for c in KB_CUSTOMERS if c in rt.states]))
            return app.state.kb[1]

    @app.get("/api/kb")
    def knowledge_base():
        """The Knowledge Base page (nba/kg/viz.py) from the live runtime: the demo customers' decision graphs include
        customer memory, campaign outcomes and Rule Center edits. Static mode reads web/public/data/kg_viz.json."""
        return kb_live()

    @app.post("/api/kb/generate")
    def generate_knowledge_base():
        """Rebuild the Knowledge Base from the live runtime and save it as the static file (kb_file), so static mode and
        a page that cannot reach GET /api/kb show the same graph. Written to a temporary file first, then renamed."""
        data = kb_live(rebuild=True)
        path = Path(kb_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
        return data

    @app.post("/api/customers/{customer_id}/service-feedback", response_model=ServiceFeedbackRow)
    def add_service_feedback(customer_id: str, row: ServiceFeedbackRow):
        """A service agent's reaction to a suggested offer (Customer 360°); the feedback step reads it."""
        rt = customer(customer_id)
        if row.customer_id != customer_id:
            raise HTTPException(422, f"customer_id {row.customer_id} in the body does not match the path ({customer_id})")
        if row.suggested_offer_id not in rt.policy.offers:
            raise HTTPException(422, f"Unknown offer {row.suggested_offer_id}")
        try:
            datetime.fromisoformat(row.shown_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(422, f"shown_at must be an ISO timestamp, got {row.shown_at!r}") from exc
        with lock:
            feedback_log.add(row.model_dump(mode="json"))
        return row

    @app.get("/api/customers/{customer_id}/service-feedback", response_model=list[ServiceFeedbackRow])
    def service_feedback(customer_id: str):
        """The reactions posted for this customer (the workbook's service_nba_feedback rows are not repeated)."""
        customer(customer_id)
        return [r for r in ai_feedback.agent_rows([], feedback_log.records()) if r["customer_id"] == customer_id]

    @app.get("/api/rules/audit")
    def rule_audit():
        """Legacy audit: past sends in nba_action_history that today's rules would have stopped."""
        return legacy_audit(context())

    return app


app = create_app()
