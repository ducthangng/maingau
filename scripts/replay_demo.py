"""Deep dive B demo: replay the 2026-10-01 event stream against the T0 decisions (Agent KG).

1. T0 decisions for every customer that receives events (Agent NBA's assemble on the snapshot).
2. Online replay in ingested_at order (nba.kg.events.replay); each T0 card is a pending card.
3. After the stream: re-decide with Agent NBA's assemble on the replayed state.
4. Classify every pending card: UNCHANGED, SUPERSEDED (still allowed, engine now prefers another
   action) or REVOKED (a hard rule now blocks it), and report the three freshness measures.

Writes out/replay_report.md and out/replay/timeline.json (per-customer transitions for the UI).
Run: .venv/bin/python scripts/replay_demo.py [--until 2026-10-03T19:27:39]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.contracts import NO_ACTION  # noqa: E402
from nba.data import load_events  # noqa: E402
from nba.engine.assemble import assemble  # noqa: E402  (Agent NBA, read-only use)
from nba.engine.runtime import Runtime  # noqa: E402
from nba.kg.events import replay  # noqa: E402

DEMO = ["MG-100003", "MG-100465", "MG-100125", "MG-100009", "MG-100004"]


def late_summary(res) -> str:
    """Late decision events by name; late charging records as a count with the maximum delay."""
    late = [o for o in res.outcomes if o.status in ("applied", "orphan") and o.delay_hours >= 1]
    charging = [o for o in late if o.event_type.startswith("charge_session")]
    other = [o for o in late if not o.event_type.startswith("charge_session")]
    parts = [f"{o.customer_id} {o.event_type.replace('_', ' ')} {o.delay_hours:.1f} h" for o in other]
    text = "Late decision events: " + (", ".join(parts) if parts else "none")
    if charging:
        text += f"; plus {len(charging)} late charging records (max {max(o.delay_hours for o in charging):.1f} h)"
    return text + "."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=datetime.fromisoformat, default=None)
    ap.add_argument("--export", type=Path, default=None, help="also write the changed customers for the UI (web/public/data/replay.json)")
    args = ap.parse_args()

    rt = Runtime.load()
    events = load_events()
    with_events = sorted({e["customer_id"] for e in events if e.get("customer_id") in rt.states})
    t0_cards = {cid: rt.card(cid) for cid in with_events}
    def personalised(card) -> bool:
        chosen = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
        return bool(chosen and chosen.personalised)

    # A deferred card carries its deferred_until: replay does not revoke it for the cap it already waits for.
    pending = {cid: (c.chosen.tuple_id, personalised(c), c.chosen.deferred_until)
               for cid, c in t0_cards.items() if c.chosen.tuple_id != NO_ACTION}

    start = time.perf_counter()
    res = replay(rt.states, events, rt.policy, rt.pop, until=args.until, pending=pending)
    replay_s = time.perf_counter() - start
    after_cards = {cid: assemble(res.states[cid], rt.pop, rt.policy, rt.cfg) for cid in sorted(res.affected)}

    revoked = {tr.outcome.customer_id: tr for tr in res.transitions if tr.pending_status == "revoked"}
    verdicts = {}
    for cid in sorted(res.affected):
        before, after = t0_cards[cid].chosen.tuple_id, after_cards[cid].chosen.tuple_id
        if cid in revoked:
            verdicts[cid] = "REVOKED"
        elif before == after:
            verdicts[cid] = "UNCHANGED"
        else:
            verdicts[cid] = "SUPERSEDED"
    counts = collections.Counter(verdicts.values())
    exposures = sorted(tr.outcome.delay_hours for tr in revoked.values())
    late = sorted(((tr.outcome.delay_hours, cid) for cid, tr in revoked.items() if tr.outcome.delay_hours >= 1), reverse=True)
    median = exposures[len(exposures) // 2] if exposures else 0.0

    lines = [
        "# Event replay report (deep dive B)",
        "",
        f"Snapshot {next(iter(rt.states.values())).eval_time} → replay of {len(events)} unique events, ingest order, up to "
        f"{next(iter(res.states.values())).eval_time}. Mock data; decisions by Agent NBA's engine on the replayed state.",
        "",
        "## Totals",
        "",
        f"- Events: {dict(res.counts())} (informational = engagement only).",
        f"- Customers whose decision facts changed: {len(res.affected)}; pending T0 cards among them: "
        f"{sum(1 for c in res.affected if c in pending)}.",
        f"- Decisions of these {len(res.affected)} customers: {counts.get('REVOKED', 0)} pending cards revoked by a hard rule, "
        f"{counts.get('SUPERSEDED', 0)} superseded, {counts.get('UNCHANGED', 0)} unchanged.",
        f"- Revoking rules: {dict(collections.Counter(r for tr in revoked.values() for r in tr.revoked_by))}.",
        "",
        "## Freshness measures",
        "",
        f"1. **Arrival-to-invalidation:** a pending card is re-checked when its event is ingested; the whole stream "
        f"replays in {replay_s:.2f} s ({1000 * replay_s / max(1, len(res.outcomes)):.2f} ms per event).",
        "2. **Decision-time known-state validity:** every pending card is re-checked after every decision-relevant event; "
        "no revoked card can be exported afterwards.",
        f"3. **Retrospective late-data exposure:** {len(exposures)} revoking events; delay between occurrence and ingestion "
        f"median {median:.1f} h, max {max(exposures, default=0):.1f} h"
        + (f"; late (≥ 1 h): {', '.join(f'{c} {h:.1f} h' for h, c in late)}" if late else "")
        + ". During that window the card looked valid on the known state; a card already sent cannot be recalled. "
        + late_summary(res),
        "",
        "## Demo customers",
        "",
    ]
    timeline = {}
    for cid in sorted(res.affected):
        trs = [t for t in res.transitions if t.outcome.customer_id == cid]
        timeline[cid] = {
            "t0_chosen": t0_cards[cid].chosen.tuple_id, "after_chosen": after_cards[cid].chosen.tuple_id,
            "verdict": verdicts[cid],
            "after_reason": after_cards[cid].chosen.reason_line,
            "transitions": [{
                "event_id": t.outcome.event_id, "event_type": t.outcome.event_type,
                "occurred_at": t.outcome.occurred_at.isoformat(), "ingested_at": t.outcome.ingested_at.isoformat(),
                "delay_hours": t.outcome.delay_hours, "status": t.outcome.status, "facts": list(t.outcome.facts),
                "signals_added": list(t.signals_added), "signals_removed": list(t.signals_removed),
                "exclusions_added": list(t.exclusions_added), "tier": [t.tier_before, t.tier_after],
                "profiled": [t.profiled_before, t.profiled_after], "flags_added": list(t.flags_added), "pending": t.pending,
                "pending_status": t.pending_status, "revoked_by": list(t.revoked_by),
            } for t in trs],
        }
    for cid in DEMO:
        if cid not in timeline:
            continue
        tl = timeline[cid]
        lines += [f"### {cid}: {tl['verdict']}", "",
                  f"T0 card `{tl['t0_chosen']}` → after the stream `{tl['after_chosen']}`.", "",
                  "| Ingested | Delay | Event | Facts | KG effect | Pending card |", "|---|---|---|---|---|---|"]
        for t in tl["transitions"]:
            effect = "; ".join(x for x in (
                f"+{','.join(t['signals_added'])}" if t["signals_added"] else "",
                f"+{','.join(t['exclusions_added'])}" if t["exclusions_added"] else "",
                f"tier {t['tier'][0]}→{t['tier'][1]}" if t["tier"][0] != t["tier"][1] else "",
                "profiling withdrawn" if t["profiled"] == [True, False] else "",
                f"flag +{','.join(t['flags_added'])}" if t["flags_added"] else "",
            ) if x) or "—"
            card = (f"REVOKED ({', '.join(t['revoked_by'])})" if t["pending_status"] == "revoked"
                    else t["pending_status"] or "—")
            lines.append(f"| {t['ingested_at'][5:16]} | {t['delay_hours']} h | {t['event_type']} | "
                         f"{'; '.join(t['facts'])} | {effect} | {card} |")
        lines += ["", f"Re-decision: {tl['after_reason']}", ""]
    out = REPO / "out"
    (out / "replay").mkdir(parents=True, exist_ok=True)
    (out / "replay_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "replay" / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                                  encoding="utf-8")
    print(f"replayed {len(res.outcomes)} events in {replay_s:.2f}s; affected {len(res.affected)}; verdicts {dict(counts)}")
    print("wrote out/replay_report.md and out/replay/timeline.json")
    if args.export:  # the Knowledge Base "Event replay" view: only customers whose pending card changed
        changed = {cid: {**tl, "transitions": [t for t in tl["transitions"] if t["status"] == "applied"]}
                   for cid, tl in timeline.items() if tl["verdict"] != "UNCHANGED"}
        args.export.write_text(json.dumps({"verdicts": dict(counts), "events": len(res.outcomes), "customers": changed},
                                          ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"wrote {args.export} ({len(changed)} customers)")


if __name__ == "__main__":
    main()
