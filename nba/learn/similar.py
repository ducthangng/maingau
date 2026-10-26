"""Similar-customer report: who looks like this customer, what they were offered, what they bought,
and what the look-alike learning changes for this customer (python -m nba.learn similar MG-100001)."""
from __future__ import annotations

import math
from dataclasses import replace

from nba.engine.assemble import assemble
from nba.learn.lookalike import LABELS, Lookalike

CLOSE = 0.25  # |z difference| at or below which two customers count as "the same" on a feature


def _num(v, fmt="{:,.0f}"):
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else fmt.format(v)


def _shared(model: Lookalike, a: str, b: str) -> list[str]:
    za, zb = model._z.loc[a], model._z.loc[b]
    close = [(abs(za[c] - zb[c]), c) for c in model.weights if not (math.isnan(za[c]) or math.isnan(zb[c]))]
    return [LABELS[c] for d, c in sorted(close) if d <= CLOSE]


def _history(rows: list[dict], cid: str, names) -> list[str]:
    out = []
    for r in sorted((r for r in rows if r["customer_id"] == cid), key=lambda r: str(r["decided_at"])):
        if r.get("control_group"):
            what = "held back (control group)"
        elif r.get("delivery_status") != "delivered":
            what = f"not delivered ({r.get('delivery_status')})"
        elif r.get("converted_within_14d"):
            what = f"**bought** ({_num(r.get('conversion_value_eur'))} €)"
        else:
            what = str(r.get("response") or "no reaction")
        out.append(f"{str(r['decided_at'])[:10]} {names.offer_or_none(r['offer_id'])} by {r['channel']}: {what}")
    return out


def _profile_lines(f, cv: dict) -> list[str]:
    return [
        f"- **Demographics & tenure:** {_num(f['tenure_years'], '{:.1f}')} years as customer, age {_num(f['age'])}, "
        f"household of {_num(f['household_size'])}, {f['city']}",
        f"- **Products:** {_num(f['active_business_lines'])} active product line(s); electricity use "
        f"{_num(f['consumption_kwh'])} kWh/yr",
        f"- **Value & risk:** annual margin {_num(f['annual_margin_eur'], '{:,.2f}')} €, CLV {_num(f['clv_eur'])} €, "
        f"churn risk {_num(f['churn_prob_12m'], '{:.1%}')}" + (f" (driver: {cv['churn_drivers']})" if cv.get("churn_drivers") else ""),
        f"- **Digital & service:** {_num(f['portal_sessions_90d'])} portal sessions in 90 days "
        f"(about {_num(f['portal_minutes_avg'], '{:.1f}')} min each); {_num(f['tickets_12m'])} service ticket(s) in 12 months, "
        f"average rating {_num(f['csat_avg'], '{:.1f}')} / 5",
    ]


def report(runtime, cid: str, names, top: int = 5) -> str:
    model: Lookalike | None = runtime.cfg.lookalike
    if model is None:
        return "Look-alike learning is switched off (config/learn.yaml › lookalike › active).\n"
    if cid not in model.features.index:
        raise SystemExit(f"Unknown customer {cid}")
    if cid not in model.profiled:
        return (f"# Similar customers: {cid}\n\nNo profiling consent: this customer is not compared with others and "
                "the look-alike learning does not change their recommendation.\n")
    feats = model.features
    values = {r["customer_id"]: r for r in runtime.tables["customer_value"].to_dict("records")}
    history = [r for r in runtime.cfg.history]
    peers = model.nearest(cid, model.profiled, top)
    lines = [f"# Similar customers: {cid}", "", "## Target customer", "", *_profile_lines(feats.loc[cid], values.get(cid, {})), ""]

    lines += ["## Closest matches", ""]
    for i, (pid, sim) in enumerate(peers, 1):
        f = feats.loc[pid]
        lines += [f"### {i}. {pid} ({sim:.1%} similar)", "",
                  f"- **Same as the target:** {', '.join(_shared(model, cid, pid)) or 'nothing exactly; close on many features'}",
                  f"- {_num(f['tenure_years'], '{:.1f}')} years as customer · {f['city']} · age {_num(f['age'])} · "
                  f"margin {_num(f['annual_margin_eur'], '{:,.2f}')} € · CLV {_num(f['clv_eur'])} €"]
        past = _history(history, pid, names)
        lines += [f"- **What we offered them:** {'; '.join(past) if past else 'nothing yet'}", ""]

    cols = ["city", "age", "tenure_years", "household_size", "active_business_lines", "annual_margin_eur", "clv_eur",
            "churn_prob_12m", "portal_sessions_90d", "tickets_12m", "csat_avg"]
    heads = ["Customer", "Role", "Similarity", "City", "Age", "Tenure (yrs)", "Household", "Lines", "Margin €", "CLV €",
             "Churn", "Portal (90 d)", "Tickets (12 m)", "Rating"]
    fmts = {"age": "{:.0f}", "tenure_years": "{:.1f}", "household_size": "{:.0f}", "active_business_lines": "{:.0f}",
            "annual_margin_eur": "{:,.2f}", "clv_eur": "{:,.0f}", "churn_prob_12m": "{:.1%}", "portal_sessions_90d": "{:.0f}",
            "tickets_12m": "{:.0f}", "csat_avg": "{:.1f}"}
    lines += ["## Comparison", "", "| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    for role, pid, sim in [("Target", cid, None)] + [(f"Peer #{i}", p, s) for i, (p, s) in enumerate(peers, 1)]:
        f = feats.loc[pid]
        cells = [str(f[c]) if c == "city" else _num(f[c], fmts[c]) for c in cols]
        lines.append(f"| {pid} | {role} | {'—' if sim is None else f'{sim:.1%}'} | " + " | ".join(cells) + " |")

    lines += ["", "## What the engine learned for this customer", "",
              "Offers that work against their control group (🟢) learn who bought them. For each, the most similar "
              "customers who were sent it decide how this customer's chance moves.", ""]
    card = runtime.card(cid)
    for oid in sorted(model.offers):
        m = model.score(cid, oid, 1.0)
        if m is None:
            continue
        verdict = "more likely than average" if m.lift > 1.05 else "less likely than average" if m.lift < 0.95 else "about average"
        buyers = [f"{p.customer_id} ({p.similarity:.0%}, by {p.channel})" for p in m.peers if p.good]
        lines += [f"- **{names.offer_or_none(oid)}**: {m.n_good} of the {len(m.peers)} most similar recipients bought, "
                  f"vs {m.pool_rate:.1%} of all recipients → chance ×{m.lift:.2f} ({verdict})"
                  + (f"; buyers: {', '.join(buyers[:5])}" if buyers else "")]
        prof = model.profile(oid)[:3]
        if prof:
            lines.append("  - Buyers differ most in: " + "; ".join(
                f"{r['label']} {_num(r['buyers'], '{:,.2f}')} vs {_num(r['others'], '{:,.2f}')}" for r in prof))
    chosen = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
    lines += ["", f"**Recommendation now:** {names.tuple(card.chosen.tuple_id)}"
              + (f" (expected gain {chosen.valuation.delta_clv:,.2f} €)" if chosen else "")]
    look = next((w[w.index("Look-alike:"):] for w in (chosen.why if chosen else []) if "Look-alike:" in w), None)
    if look:
        lines.append(f"- {look}")
    unlearned = assemble(runtime.states[cid], runtime.pop, runtime.policy, replace(runtime.cfg, lookalike=None, _versions=None))
    if unlearned.chosen.tuple_id != card.chosen.tuple_id:
        lines.append(f"- Changed by the learning: without it the engine would recommend {names.tuple(unlearned.chosen.tuple_id)}")
    else:
        lines.append("- Same recommendation as without the learning")
    lines += ["", "_Similarity uses the snapshot at evaluation time on the columns in config/learn.yaml › lookalike › "
              "features; only customers with profiling consent are compared. It describes who bought, not why._"]
    return "\n".join(lines) + "\n"
