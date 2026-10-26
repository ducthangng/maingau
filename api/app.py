"""FastAPI decision service. Run: uvicorn api.app:app --port 8000.

The append-only JSONL uses {customer_id, entry} envelopes; each entry is a
DecisionLogEntry. This keeps customer routing out of the shared entry model.
"""
from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException

from nba.contracts import DecisionLogEntry, DecisionRequest, NO_ACTION, TupleRef, tuple_id
from nba.data import DEFAULT_WORKBOOK, REPO
from nba.engine.assemble import build_chosen, checklist_for, evaluate_candidates, valuation_scores, value_candidate
from nba.engine.config import MissingDataError
from nba.engine.runtime import Runtime, index_rows, summary
from nba.kg.rules import check_tuple, generate_candidates, is_profiled
from nba.kg.signals import extract_signals


class DecisionStore:
    def __init__(self, directory):
        self.path = Path(directory) / "decision_log.jsonl"

    def entries(self, cid):
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            try:
                records = [json.loads(line) for line in stream if line.strip()]
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
        return [DecisionLogEntry.model_validate(r["entry"]) for r in records if r["customer_id"] == cid]

    def append(self, cid, entry):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"customer_id": cid, "entry": entry.model_dump(mode="json")},
                          ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
        with self.path.open("a", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def refused(rule_ids, reasons):
    raise HTTPException(status_code=409, detail={"rule_ids": sorted(set(rule_ids)), "reasons": reasons})


def checked_tuple(runtime, cid, ref):
    """Regenerate with KG's own gates for every human-selected tuple."""
    state, policy = runtime.states[cid], runtime.policy
    blockers = check_tuple(state, ref.offer_id, ref.channel, policy)
    if blockers:
        refused([b.rule_id for b in blockers], [b.reason for b in blockers])
    if not is_profiled(state, policy) and ref.tone != "sie":
        refused(["CONSENT-PROFILING"], ["Ohne Profiling-Einwilligung ist nur die Standardanrede Sie zulässig"])
    signals = extract_signals(state, policy)
    allowed, _ = generate_candidates(state, signals, policy, ref.tone)
    target = next((c for c in allowed if c.tuple_id == tuple_id(ref.offer_id, ref.channel, ref.tone)), None)
    if target is None:
        refused(["DATA-MISSING"], ["Dieses Tupel wurde vom KG nicht ausgewertet; kein zulässiger Bedarfspfad oder generischer Kanal"])
    try:
        target = value_candidate(target, state, runtime.cfg)
    except MissingDataError as exc:
        refused(["DATA-MISSING"], [str(exc)])
    if target.valuation.delta_clv <= 0:
        refused(["ECON-NONPOSITIVE"], [f"Erwartete ΔCLV {target.valuation.delta_clv:.2f} € ≤ 0"])
    if target.origin == "generic" and is_profiled(state, policy):
        _, evaluated, _ = evaluate_candidates(allowed, state, policy, runtime.cfg)
        if not any(c.tuple_id == target.tuple_id for c in evaluated):
            refused(["HOLDING-PRECONDITION"], ["Ein generisches Angebot ist nur zulässig, wenn keine positive signalbasierte Aktion vorliegt"])
    return target


def create_app(*, workbook=DEFAULT_WORKBOOK, out_dir=REPO / "out", p_mode=None, runtime=None):
    app = FastAPI(title="MAINGAU NBA", version="0.1.0")
    app.state.runtime = runtime
    store, lock = DecisionStore(out_dir), RLock()

    def context():
        with lock:
            if app.state.runtime is None:
                app.state.runtime = Runtime.load(workbook, p_mode=p_mode)
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

    @app.get("/api/customers")
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

    @app.get("/api/customers/{customer_id}")
    def get_customer(customer_id: str):
        return card_with_decisions(customer_id)

    @app.get("/api/summary")
    def get_summary():
        rt = context()
        return summary(rt.cards(), rt.cfg, next(iter(rt.states.values())).eval_time)

    @app.post("/api/customers/{customer_id}/decision")
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
                    refused(["HOLDING-PRECONDITION"], ["Der Vorschlag hat sich geändert; bitte neu laden oder explizit überschreiben"])
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

    return app


app = create_app()
