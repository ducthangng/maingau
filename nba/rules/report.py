"""Render a rules diff for marketers: what you changed, what happens to customers, is it safe."""
from __future__ import annotations

import json

ICON = {"green": "🟢", "amber": "🟡", "red": "🔴", None: "—"}
WORD = {"green": "working", "amber": "not clear yet", "red": "not working", None: "—"}


def short(value, width=70) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    return text if len(text) <= width else text[: width - 1] + "…"


def verdict(changed, imp) -> tuple[str, list[str]]:
    notes = []
    if imp.errors:
        return "FAIL", imp.errors
    if imp.violations_after:
        notes.append(f"{len(imp.violations_after)} customer(s) would get a message that breaks a hard rule")
    if any(c["hard"] for c in changed):
        notes.append("a 🔒 hard rule was changed: the rule owner signs off with --sign-off NAME")
    if imp.reference_changed:
        notes.append("test customer(s) agreed with MAINGAU change: " + ", ".join(c["customer_id"] for c in imp.reference_changed))
    if imp.violations_after:
        return "FAIL", notes
    return ("REVIEW" if notes else "PASS"), notes


MEANING = {"PASS": "safe to apply", "REVIEW": "safe, but someone must look at the notes", "FAIL": "cannot be applied"}


def markdown(changed, imp, moved: bool, names) -> str:
    status, notes = verdict(changed, imp)
    lines = ["# What your rule change does", "", f"**Verdict: {status}** ({MEANING[status]})", ""]
    lines += [f"- {n}" for n in notes] + ([""] if notes else [])
    if moved:
        lines += ["⚠ Someone changed the rules after you opened `rules.yaml`. Run `python -m nba.rules reset` and redo "
                  "your change, or you may undo theirs.", ""]
    lines += [f"## 1. What you changed ({len(changed)})", "", "| | Rule | Before | After |", "|---|---|---|---|"]
    lines += [f"| {'🔒' if c['hard'] else ''} | {c['where']} | {short(c['before'])} | {short(c['after'])} |" for c in changed]
    if imp.errors:
        return "\n".join(lines + ["", "## Problem", "", *imp.errors]) + "\n"
    lines += ["", f"## 2. What happens to customers: {len(imp.changed)} of {imp.n_customers} get a different recommendation", "",
              f"Expected gain in customer value from all recommendations: {imp.sum_before:,.0f} € → {imp.sum_after:,.0f} € "
              f"({imp.sum_after - imp.sum_before:+,.0f} €). This is the engine's expectation, not a measured result.", ""]
    if imp.flows:
        lines += ["| Was recommended | Now recommended | Customers |", "|---|---|---|"]
        lines += [f"| {names.offer_or_none(a)} | {names.offer_or_none(b)} | {k} |"
                  for (a, b), k in sorted(imp.flows.items(), key=lambda kv: (-kv[1], kv[0]))]
        lines += ["", "| Offer | Recommended before | After | Change |", "|---|---|---|---|"]
        for offer in sorted(set(imp.chosen_before) | set(imp.chosen_after), key=names.offer_or_none):
            b, a = imp.chosen_before.get(offer, 0), imp.chosen_after.get(offer, 0)
            if a != b:
                lines.append(f"| {names.offer_or_none(offer)} | {b} | {a} | {a - b:+d} |")
        fmt = lambda v: "—" if v is None else f"{v:,.2f} €"
        lines += ["", "<details><summary>Every customer that changes (⭐ = agreed test customer)</summary>", "",
                  "| Customer | Before | After | Expected gain before → after |", "|---|---|---|---|"]
        for c in imp.changed:
            star = " ⭐" if c in imp.reference_changed else ""
            lines.append(f"| {c['customer_id']}{star} | {names.tuple(c['before'])} | {names.tuple(c['after'])} | "
                         f"{fmt(c['delta_before'])} → {fmt(c['delta_after'])} |")
        lines += ["", "</details>"]
    lines += ["", "## 3. Safety check (recomputed from the raw customer data)", ""]
    lines += (["✅ Every recommendation still respects consent, blocks (dunning, complaints, cancellations), profiling "
               "consent and the contact limit, and has a positive expected gain."] if not imp.violations_after
              else [f"❌ {v}" for v in imp.violations_after[:30]])
    b, a = imp.loop_counts
    lines += ["", "## 4. Feedback loop", ""]
    if imp.loop_changes:
        lines += ["| Offer | Before | After |", "|---|---|---|"]
        lines += [f"| {names.pattern(c['pattern'])} | {ICON[c['before']]} {WORD[c['before']]} | "
                  f"{ICON[c['after']]} {WORD[c['after']]} |" for c in imp.loop_changes]
    else:
        lines.append("No offer changes its 🟢 / 🟡 / 🔴 judgement.")
    lines += ["", "Next: `python -m nba.rules apply --by \"Your name\"` to make it the new rule, or "
              "`python -m nba.rules reset` to throw it away."]
    return "\n".join(lines) + "\n"


def terminal(changed, imp, moved: bool, names) -> str:
    status, notes = verdict(changed, imp)
    out = [f"You changed {len(changed)} rule(s):"]
    out += [f"  {'🔒 ' if c['hard'] else ''}{c['where']}: {short(c['before'], 40)} -> {short(c['after'], 40)}" for c in changed]
    if moved:
        out.append("  ! someone changed the rules after you opened rules.yaml: reset and redo before applying")
    if imp.errors:
        return "\n".join(out + [f"FAIL: {e}" for e in imp.errors])
    out.append(f"Customers: {len(imp.changed)} of {imp.n_customers} get a different recommendation; "
               f"expected gain {imp.sum_before:,.0f} € -> {imp.sum_after:,.0f} €")
    for (a, b), k in sorted(imp.flows.items(), key=lambda kv: (-kv[1], kv[0]))[:8]:
        out.append(f"  {k:4d} × {names.offer_or_none(a)} -> {names.offer_or_none(b)}")
    out.append("Safety check: " + ("OK" if not imp.violations_after else f"{len(imp.violations_after)} PROBLEM(S)"))
    out += [f"  {v}" for v in imp.violations_after[:5]]
    if imp.loop_changes:
        out.append("Feedback loop: " + "; ".join(f"{names.pattern(c['pattern'])} {WORD[c['before']]} -> {WORD[c['after']]}"
                                                 for c in imp.loop_changes[:4]))
    out.append(f"Verdict: {status} ({MEANING[status]})")
    out += [f"  - {n}" for n in notes]
    return "\n".join(out)
