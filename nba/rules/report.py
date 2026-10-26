"""Render a rules diff: the edits, their effect on decisions and on the feedback loop, and a verdict."""
from __future__ import annotations

import json

ICON = {"green": "🟢", "amber": "🟡", "red": "🔴", None: "—"}


def short(value, width=70) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    return text if len(text) <= width else text[: width - 1] + "…"


def verdict(found, imp) -> tuple[str, list[str]]:
    notes = []
    if imp.errors:
        return "FAIL", imp.errors
    if imp.violations_after:
        notes.append(f"{len(imp.violations_after)} hard-rule violation(s) after the edit")
    if any(c.hard for c in found):
        notes.append("hard rule edited: the rule owner signs off with --sign-off NAME (consent / exclusion / contact cap)")
    if imp.reference_changed:
        notes.append("README §9 reference customer(s) change: " + ", ".join(c["customer_id"] for c in imp.reference_changed))
    if imp.violations_after:
        return "FAIL", notes
    return ("REVIEW" if notes else "PASS"), notes


def markdown(found, imp, moved: bool) -> str:
    status, notes = verdict(found, imp)
    lines = ["# Rules diff", "", f"**Verdict: {status}**" + ("" if not notes else " · " + " · ".join(notes)), ""]
    if moved:
        lines += ["⚠ The source files changed after `rules.yaml` was exported. Re-export, or your copy may undo "
                  "someone else's change.", ""]
    lines += [f"## 1. What you changed ({len(found)})", "", "| | Where | Before | After |", "|---|---|---|---|"]
    for c in found:
        flag = "🔒 HARD" if c.hard else c.kind
        lines.append(f"| {flag} | `{c.where}` | `{short(c.before)}` | `{short(c.after)}` |")
    if imp.errors:
        return "\n".join(lines + ["", "## Error", "", *imp.errors]) + "\n"
    n = len(imp.changed)
    lines += ["", f"## 2. Decisions: {n} of {imp.n_customers} customers change", "",
              f"Expected ΔCLV of the chosen actions: {imp.sum_before:,.2f} € → {imp.sum_after:,.2f} € "
              f"({imp.sum_after - imp.sum_before:+,.2f} €). Expectations under each rule set, not measured results.", ""]
    if imp.flows:
        lines += ["| From (chosen offer) | To | Customers |", "|---|---|---|"]
        lines += [f"| {a} | {b} | {k} |" for (a, b), k in sorted(imp.flows.items(), key=lambda kv: (-kv[1], kv[0]))]
        lines += ["", "| Offer | Chosen before | After | Δ |", "|---|---|---|---|"]
        for offer in sorted(set(imp.chosen_before) | set(imp.chosen_after)):
            b, a = imp.chosen_before.get(offer, 0), imp.chosen_after.get(offer, 0)
            if a != b:
                lines.append(f"| {offer} | {b} | {a} | {a - b:+d} |")
        lines += ["", "<details><summary>Every changed customer</summary>", "",
                  "| Customer | Before | After | ΔCLV before → after | New reason |", "|---|---|---|---|---|"]
        fmt = lambda v: "—" if v is None else f"{v:.2f}"
        for c in imp.changed:
            ref = " ⭐" if c in imp.reference_changed else ""
            lines.append(f"| {c['customer_id']}{ref} | {c['before']} | {c['after']} | {fmt(c['delta_before'])} → "
                         f"{fmt(c['delta_after'])} | {short(c['reason_after'], 110)} |")
        lines += ["", "</details>"]
    lines += ["", "## 3. Hard rules after the edit (independent check from the raw tables)", ""]
    lines += (["✅ No consent, exclusion, profiling, contact-cap or ΔCLV violation."] if not imp.violations_after
              else [f"❌ {v}" for v in imp.violations_after[:30]])
    b, a = imp.loop_counts
    lines += ["", "## 4. Feedback loop", "", f"Traffic light before {b} → after {a}.", ""]
    if imp.loop_changes:
        lines += ["| Pattern | Before | After | Why now |", "|---|---|---|---|"]
        lines += [f"| {c['pattern']} | {ICON[c['before']]} | {ICON[c['after']]} | {c['why']} |" for c in imp.loop_changes]
    else:
        lines.append("No pattern changes colour.")
    lines += ["", "Next: `python -m nba.rules apply` writes the edits into the source files; "
              "`python -m nba.rules reset` throws them away."]
    return "\n".join(lines) + "\n"


def terminal(found, imp, moved: bool) -> str:
    status, notes = verdict(found, imp)
    out = [f"{len(found)} rule edit(s):"]
    out += [f"  {'HARD ' if c.hard else ''}{c.where}: {short(c.before, 50)} -> {short(c.after, 50)}" for c in found]
    if moved:
        out.append("  ! source files changed after export: re-export before applying")
    if imp.errors:
        return "\n".join(out + [f"FAIL: {e}" for e in imp.errors])
    out.append(f"Decisions: {len(imp.changed)}/{imp.n_customers} change; ΔCLV {imp.sum_before:,.2f} -> {imp.sum_after:,.2f} €")
    for (a, b), k in sorted(imp.flows.items(), key=lambda kv: (-kv[1], kv[0]))[:8]:
        out.append(f"  {k:4d} × {a} -> {b}")
    out.append(f"Hard rules: {'OK' if not imp.violations_after else f'{len(imp.violations_after)} VIOLATION(S)'}")
    out += [f"  {v}" for v in imp.violations_after[:5]]
    out.append(f"Feedback loop: {len(imp.loop_changes)} pattern(s) change colour")
    out.append(f"Verdict: {status}" + ("" if not notes else " (" + "; ".join(notes) + ")"))
    return "\n".join(out)
