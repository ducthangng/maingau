"""Real-data preview for the UI before valuation exists (Agent KG).

Writes, for all 750 customers (or --customers):
  <out>/index.json            IndexRow[] with real triage; valuation fields null, chosen_offer "PENDING"
  <out>/summary.json          Summary with archetype/tier/flag/signal counts, sources, column_src, value_date
  <out>/kg/<customer_id>.json KG part of a CustomerCard: triage, signals, candidates, blocked, consent,
                              channels, exclusions, data_quality (sources are in summary.json)
Every object is validated by the pydantic models in nba/contracts.py. Agent NBA's `nba.build --export`
replaces this with full CustomerCards.

Run: .venv/bin/python scripts/export_preview.py [--out out/preview] [--customers MG-100068,MG-100009]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.contracts import IndexRow, Summary  # noqa: E402
from nba.data import load_workbook  # noqa: E402
from nba.kg.bundle import COLUMN_SRC, kg_bundle, source_info  # noqa: E402
from nba.kg.policy import load_policy  # noqa: E402
from nba.state import build_states, population  # noqa: E402

PENDING = "PENDING"


def age_band(birth_year, eval_year: int) -> str | None:
    if not birth_year:
        return None
    lo = (eval_year - int(birth_year)) // 10 * 10
    return f"{lo}–{lo + 9}"


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "out" / "preview"))
    ap.add_argument("--customers", default="")
    args = ap.parse_args()
    t0 = time.time()
    tables = load_workbook()
    wanted = [c for c in args.customers.split(",") if c] or None
    policy = load_policy(tables=tables)
    states = build_states(tables, policy.config["eval_time"], snapshot_mode=policy.config["snapshot_mode"],
                          customer_ids=wanted)
    pop = population(tables)
    sources = source_info(tables)
    out = Path(args.out)
    (out / "kg").mkdir(parents=True, exist_ok=True)

    rows: list[IndexRow] = []
    counts = {k: collections.Counter() for k in ("signal", "archetype", "tier", "flag", "blocked")}
    eval_time = next(iter(states.values())).eval_time
    for cid in sorted(states):
        s = states[cid]
        b = kg_bundle(s, policy, pop)
        master, value = s.one("customer_master") or {}, s.one("customer_value") or {}
        service = [c for c in b.candidates if c.origin == "service"]
        rows.append(IndexRow(
            customer_id=cid,
            age_band=age_band(master.get("birth_year"), eval_time.year),
            city=master.get("city"),
            lines=value.get("active_business_lines"),
            clv_eur=value.get("clv_eur"),
            churn=value.get("churn_prob_12m"),
            archetype=b.triage.archetype.id,
            archetype_name=b.triage.archetype.name,
            urgency_tier=b.triage.urgency_tier,
            urgency_score=b.triage.urgency_score,
            top_reason=b.triage.urgency_reasons[0] if b.triage.urgency_reasons else None,
            flags=[f.id for f in b.triage.flags],
            outlier=b.triage.outlier,
            triggers=[x.id for x in b.signals],
            chosen_offer=PENDING,
            service_mode=bool(service) or any(e.active and e.rule_id == "EXCL-OPEN-TICKET" for e in b.exclusions),
            personalised=None,
            n_signals=len(b.signals),
            n_candidates=len(b.candidates),
            n_blocked=len(b.blocked),
            exclusions=[e.rule_id for e in b.exclusions if e.active],
        ))
        kg_part = {
            "customer_id": cid,
            "preview": "KG part only; valuation, chosen, content and profile come from Agent NBA / Agent CARDS",
            "eval_time": eval_time.isoformat(),
            "triage": b.triage.model_dump(),
            "signals": [x.model_dump() for x in b.signals],
            "candidates": [x.model_dump() for x in b.candidates],
            "blocked": [x.model_dump() for x in b.blocked],
            "consent": [x.model_dump() for x in b.consent],
            "channels": [x.model_dump() for x in b.channels],
            "exclusions": [x.model_dump() for x in b.exclusions],
            "data_quality": [x.model_dump() for x in b.data_quality],
        }
        (out / "kg" / f"{cid}.json").write_text(dump(kg_part) + "\n", encoding="utf-8")
        counts["signal"].update(x.id for x in b.signals)
        counts["archetype"][b.triage.archetype.id] += 1
        counts["tier"][b.triage.urgency_tier] += 1
        counts["flag"].update(f.id for f in b.triage.flags)
        counts["blocked"].update(x.rule_id for x in b.blocked)

    rows.sort(key=lambda r: (r.urgency_tier, -r.urgency_score, r.customer_id))
    calc = tables["customer_value"]["clv_calc_date"].dropna()
    summary = Summary(
        eval_time=eval_time.isoformat(),
        n_customers=len(rows),
        blocked_by_rule=dict(counts["blocked"]),
        signal_counts=dict(counts["signal"]),
        archetype_counts=dict(counts["archetype"]),
        urgency_counts=dict(counts["tier"]),
        flag_counts=dict(counts["flag"]),
        sources=sources,
        column_src=COLUMN_SRC,
        value_date=calc.max().date().isoformat() if len(calc) else None,
    )
    (out / "index.json").write_text(dump([r.model_dump() for r in rows]) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(dump(summary.model_dump()) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out} in {time.time() - t0:.1f} s (preview of {date.today()})")


if __name__ == "__main__":
    main()
