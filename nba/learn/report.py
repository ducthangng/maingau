"""Markdown for the loop: one report, and one case file per red pattern with a brief for AI review."""
from __future__ import annotations

ICON = {"green": "🟢", "amber": "🟡", "red": "🔴"}


def _pct(v):
    return "—" if v is None else f"{v:+.1%}"


def report(found, cases, ledger_new, meta) -> str:
    lines = [
        "# Feedback loop report",
        "",
        f"Eval time {meta['eval_time']} · learn {meta['learn_version']} · p mode {meta['p_mode']} · "
        f"{meta['n_treated']} treated / {meta['n_control']} control rows.",
        "",
        "Each pattern is compared with its offer's control group (Beta posteriors, prior strength "
        f"{meta['prior_strength']}). 🟢 = works, recorded in the ledger · 🟡 = not clear yet, keep collecting · "
        "🔴 = fix case for a human with AI. Mock history: evidence for the loop, not a causal claim.",
        "",
        "| | Pattern | Sends | Conv | Control | Uplift (90%) | P(uplift > 0) | Why |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in found:
        r = p.result
        name = p.key if p.channel is None else f"&nbsp;&nbsp;↳ {p.channel}"
        lines.append(f"| {ICON[p.status]} | {name} | {r.treated.n} | {r.treated.conv} | {r.control.conv}/{r.control.n} | "
                     f"{_pct(r.uplift)} ({_pct(r.low)} … {_pct(r.high)}) | {r.p_positive:.0%} | {p.why} |")
    lines += ["", f"## Fix cases ({len(cases)})", ""]
    for c in cases:
        lines.append(f"- **{c.id}** · layer: {c.layer} · {c.finding}")
    lines += ["", f"## Recorded this run ({len(ledger_new)} new ledger entries)", ""]
    lines += [f"- {e['pattern']}: {e['why']}" for e in ledger_new] or ["- nothing new"]
    return "\n".join(lines) + "\n"


def case_markdown(case, meta) -> str:
    p = case.pattern
    lines = [
        f"# {case.id}: {p.key}",
        "",
        f"**Status:** 🔴 {p.why}  ",
        f"**Layer:** {case.layer}  ",
        f"**Finding:** {case.finding}",
        "",
        "## Evidence",
        "",
        "| Split | Subgroup | Sends | Conv | Uplift | P(uplift > 0) |",
        "|---|---|---|---|---|---|",
    ]
    for s in case.splits:
        for g in s.subgroups:
            r = g.result
            lines.append(f"| {s.dimension} (contrast {s.contrast:.2f}) | {g.label} | {r.treated.n} | {r.treated.conv} | "
                         f"{_pct(r.uplift)} | {r.p_positive:.0%} |")
    lines += [
        "",
        f"Control group for {p.offer_id}: {p.result.control.conv}/{p.result.control.n}. "
        "Target signals are taken at eval time, a proxy for the signal at the time of the send.",
        "",
        f"**Agent feedback (service pilot):** {case.harm['upset']}/{case.harm['n_feedback']} upset or annoyed"
        + (" ⚠ watch" if case.harm["watch"] else "") + "  ",
        f"**Reviewer decisions on this offer:** {case.human}",
        "",
        "## Options",
        "",
    ]
    for o in case.options:
        bt = case.backtests.get(o.id, {})
        lines += [f"### {o.id}. {o.title}", "", o.rationale, ""]
        if o.overrides:
            lines += ["Engine change (`config/nba.yaml` → `p_overrides`):", "", "```yaml"]
            lines += [f"\"{k}\": {{p: {v['p']}, basis: \"{v['basis']}\"}}" for k, v in sorted(o.overrides.items())]
            lines += ["```", ""]
        if o.needs_rewrite:
            lines += [f"Rewrite by a human with AI: `{o.needs_rewrite}`.", ""]
        if bt.get("applies"):
            lines += [f"Backtest: {bt['customers_valued']} customers value this offer; **{bt['decisions_changed']} decisions "
                      f"change**, {bt['values_changed']} only change value. Sum ΔCLV of changed customers "
                      f"{bt['sum_delta_clv_before']:.2f} € → {bt['sum_delta_clv_after']:.2f} €. {bt['note']}", ""]
            if bt["reference_changed"]:
                lines += [f"⚠ Changes README §9 reference customers: {', '.join(bt['reference_changed'])}. "
                          "Agree the new expectation with the team before approving.", ""]
            for ch in bt["changes"][:8]:
                lines.append(f"- {ch['customer_id']}: {ch['before']} ({ch['delta_clv_before']}) → {ch['after']} ({ch['delta_clv_after']})")
            if len(bt["changes"]) > 8:
                lines.append(f"- … {len(bt['changes']) - 8} more in the case JSON")
            lines.append("")
    lines += [
        "## Decide",
        "",
        f"`python -m nba.learn apply {case.id} --option <id> --reviewer <name>` writes the override with this case ID "
        "into `config/nba.yaml`. Every hard rule still runs before p is used. Options without an engine change are "
        "done as a reviewed edit of the named file.",
        "",
        "## Brief for AI review",
        "",
        "Paste this section and the evidence above into Claude (or open this file in Claude Code):",
        "",
        "> You are reviewing a fix case from the MAINGAU NBA feedback loop. Using only the evidence in this file:",
        "> 1. Is the diagnosed layer plausible? Name any other explanation the evidence supports (small n, proxy signal, "
        "contamination by newsletters sent to everyone).",
        "> 2. Recommend one option, or a better one, and say what result in the next cycle would prove it right or wrong.",
        "> 3. If the fix is a rewrite (KG mapping, template, tone), draft the exact YAML change.",
        "> Constraints: never loosen consent, exclusion, profiling or payment-data rules; customer content stays German "
        "with the right Du/Sie; no personalised prices or false urgency; a human approves every change.",
        "",
        f"_learn {meta['learn_version']} · eval {meta['eval_time']} · p mode {meta['p_mode']}_",
    ]
    return "\n".join(lines) + "\n"
