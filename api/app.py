"""FastAPI decision service. Run: uvicorn api.app:app --port 8000.

The append-only JSONL uses {customer_id, entry} envelopes; each entry is a
DecisionLogEntry. This keeps customer routing out of the shared entry model.
Rule Center edits are a second append-only log (rule_versions.jsonl, docs/rule-center.md §6).
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.replay import replay_preview

from nba.contracts import (
    CustomerCard, DecisionLogEntry, DecisionRequest, IndexRow, NO_ACTION, RuleChange, RuleCreate, RulesFile,
    Summary, TupleRef, tuple_id,
)
from nba.data import DEFAULT_WORKBOOK, REPO
from nba.engine.assemble import build_chosen, checklist_for, evaluate_candidates, valuation_scores, value_candidate
from nba.engine.config import MissingDataError
from nba.engine.rule_audit import legacy_audit
from nba.engine.rule_registry import (
    RuleEditError, custom_rule, entity_catalog, next_custom_id, replay_ops, rules_file,
)
from nba.engine.rulecenter import Evaluator
from nba.engine.runtime import Runtime, index_rows, summary
from nba.kg.rules import check_tuple, generate_candidates, is_profiled
from nba.kg.signals import extract_signals

try:  # POSIX file locks; on Windows the in-process RLock below is the guard (Q-KG-23)
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

CORS_ORIGINS = os.environ.get("MAINGAU_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")


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
    """Append-only JSON lines, fsync'ed, with a shared lock for reads and an exclusive one for writes."""

    def __init__(self, path):
        self.path = Path(path)

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as stream, locked(stream, exclusive=False):
            return [json.loads(line) for line in stream if line.strip()]

    def add(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str) + "\n"
        with self.path.open("a", encoding="utf-8") as stream, locked(stream, exclusive=True):
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())


class DecisionStore(JsonlStore):
    def __init__(self, directory):
        super().__init__(Path(directory) / "decision_log.jsonl")

    def entries(self, cid):
        return [DecisionLogEntry.model_validate(r["entry"]) for r in self.records() if r["customer_id"] == cid]

    def append(self, cid, entry):
        self.add({"customer_id": cid, "entry": entry.model_dump(mode="json")})


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


def create_app(*, workbook=DEFAULT_WORKBOOK, out_dir=REPO / "out", p_mode=None, runtime=None):
    app = FastAPI(title="MAINGAU NBA", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["*"])
    app.state.runtime = runtime
    app.state.base = None  # (runtime as loaded from the config files, rule edit count it reflects)
    store, rule_log, lock = DecisionStore(out_dir), JsonlStore(Path(out_dir) / "rule_versions.jsonl"), RLock()

    def known_ids(rt):
        return frozenset([*rt.policy.compliance, *(rt.cfg.settings.get("business_rules") or {}), "B-02", "B-07"])

    def with_ops(base, ops):
        """The base runtime with Rule Center edits replayed (config/nba.yaml + config/kg.yaml contact_cap)."""
        if not ops:
            return base
        settings, cap = replay_ops(base.cfg.settings, base.policy.config.get("contact_cap", {}),
                                   [o["op"] for o in ops], known_ids(base))
        policy = replace(base.policy, config={**base.policy.config, "contact_cap": cap})
        return base.with_rules(settings={k: settings.get(k) for k in ("business_rules", "custom_rules")}, policy=policy)

    def context():
        with lock:
            if app.state.base is None:
                base = app.state.runtime or Runtime.load(workbook, p_mode=p_mode)
                app.state.base = base
                app.state.runtime = with_ops(base, rule_log.records())
            return app.state.runtime

    def customer(cid):
        rt = context()
        if cid not in rt.states:
            raise HTTPException(404, "Unknown customer")
        return rt

    def card_with_decisions(cid):
        rt = customer(cid)
        card = rt.card(cid)
        entries = store.entries(cid)
        card.decision_log += entries
        current = [e for e in entries if e.state_revision == card.meta.state_revision
                   and e.versions == card.meta.versions.model_dump()]
        if current:
            last = current[-1]
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

    @app.get("/api/summary", response_model=Summary)
    def get_summary():
        rt = context()
        return summary(rt.cards(), rt.cfg, next(iter(rt.states.values())).eval_time)

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
                reason=request.reason, state_revision=rt.states[customer_id].revision,
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
            ops = rule_log.records()
            try:
                updated = with_ops(app.state.base, ops + [{"op": op}])
            except RuleEditError as exc:
                raise HTTPException(exc.status, str(exc)) from exc
            version = updated.cfg.versions(updated.policy).rules
            rule_log.add({"version": len(ops) + 1, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "by": by.strip(), "reason": reason, "op": op, "rule_set_version": version})
            app.state.runtime = updated
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
            rid = next_custom_id(rt.cfg.settings, [r["op"] for r in rule_log.records()])
            rule = custom_rule(body, rid, entity_catalog(rt.tables))
        return edit({"op": "create", "rule": rule}, body.by, None)

    @app.delete("/api/rules/{rule_id}", response_model=RulesFile)
    def delete_rule(rule_id: str, by: str, reason: str | None = None):
        return edit({"op": "delete", "rule_id": rule_id}, by, reason)

    @app.get("/api/rules/versions")
    def rule_versions():
        context()
        return rule_log.records()

    @app.post("/api/rules/whatif")
    def what_if(changes: list[RuleChange | RuleCreate]):
        """Decide every customer under the current rules and under the proposed edits; nothing is saved."""
        from nba.engine.rule_whatif import what_if as compare

        with lock:
            rt = context()
            ops, history = [], [r["op"] for r in rule_log.records()]
            for change in changes:
                if isinstance(change, RuleCreate):
                    rid = next_custom_id(rt.cfg.settings, history + ops)
                    ops.append({"op": "create", "rule": custom_rule(change, rid, entity_catalog(rt.tables))})
                elif not change.rule_id:
                    raise HTTPException(422, "each change needs rule_id")
                else:
                    ops.append({"op": "update", "rule_id": change.rule_id, "active": change.active, "params": change.params})
            try:
                proposed = with_ops(rt, [{"op": o} for o in ops])
            except RuleEditError as exc:
                raise HTTPException(exc.status, str(exc)) from exc
            return compare(rt, proposed)

    @app.get("/api/rules/audit")
    def rule_audit():
        """Legacy audit: past sends in nba_action_history that today's rules would have stopped."""
        return legacy_audit(context())

    return app


app = create_app()
