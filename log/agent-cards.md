# Agent CARDS: session log

Owner: **Agent CARDS** (README §7.2: Customer Profile, the UI for both cards, overview page). Only Agent CARDS writes in this file. Logging rules: README §12.

**At the start of a session:**
- `git pull`.
- Read the open-questions table below.
- Read the latest entry in all three files in `log/`.

**At the end of a session**, before the last push:
- Append one entry using the template.
- Update the table.
- Commit the log together with the session's code.

Entries are append-only. Correct a mistake in a new entry; never rewrite old ones.

## Entry template

```markdown
### Session <n> · <YYYY-MM-DD HH:MM–HH:MM> Europe/Berlin · <tool + model> · branch <name> · commits <sha>..<sha>

**Goal:** what this session set out to do (milestone M0–M3).

**Done:**
- <task> — files: `<path>`, components/functions: `<name>`, tests: `<test file>`

**Verified:** commands actually run and their results (e.g. `pytest -q tests/test_profile_tone.py` → 9 passed; screens checked for MG-100068, MG-100009 at 1280 px).

**Not done / carried over:** what is unfinished and why.

**Contract changes:** changes to README §5/§6 made in this session (with PR/commit), or "none".

**Questions to consider:** new IDs added to the table below (Q-CARDS-xx), one line each.

**Issues / risks:** bugs, data quirks, UX problems, blockers — with evidence (customer_id, screenshot path).

**Handoff:** what Agent KG / Agent NBA need to know or change.

**Next session starts with:** the first concrete step.
```

## Open questions and issues to consider

These are kept up to date and edited in place. Status values: `open`, `answered`, `decided-default`, `closed`.

| ID | Question / issue | Why it matters | Ask whom | Status | Answer / decision (date) |
|---|---|---|---|---|---|
| Q-CARDS-01 | Who is the primary user: marketing, service agent or both? | Layout and the default view of the right card | Caro (Marketing), Felix (Digital Channels) | answered | Marketing orchestration dashboard (worklist + bulk execution) with a Service mode switch; service mode is automatic when a ticket is open (26 Oct, prompts/agent-cards.md) |
| Q-CARDS-02 | Without profiling consent, may tone still be inferred from the customer's own messages? | Tone shown for 289 customers | Team | answered | No: D1 (26 Oct) → Sie by default, labelled "default" |
| Q-CARDS-03 | Newsletter tonality is weak evidence: all 13 campaigns went to all subscribers (du 7, sie 6). Keep it as tone priority 2 only with at least 2 human clicks and a clear majority? | Wrong Du/Sie is visible to the customer | Team | decided-default | — |
| Q-CARDS-04 | The spec says portal pages "offers / tariff / consumption". The data names are `offers`, `tariff_overview`, `consumption_chart`. Use the data names | Correct counts in the portal trend | — | closed | Use the data names (README §3) |
| Q-CARDS-05 | 7 customers prefer English (`preferred_contact_language = en`). Content stays German per the challenge. Show the note "prefers EN" on the card? | Transparency for the agent | MAINGAU mentor | decided-default | — |
| Q-CARDS-06 | Highlight thresholds: rarity ≤ 10% or percentile ≥ 90 / ≤ 10. Is "same product combination" the right peer group for percentiles? | Highlights must be genuinely unusual | Team | open | — |
| Q-CARDS-07 | 30-second readability: at most 12 numbers visible before any drill-down. Validate with someone who did not build it | Main UX acceptance criterion | Team (hallway test) | open | — |
| Q-CARDS-08 | Which KPIs go at the top of the worklist? | Jury deliverable | Caro (Marketing) | decided-default | Customers to act on, Σ expected ΔCLV of the view, outliers, blocked by rules (prompts/agent-cards.md §1.1) |
| Q-CARDS-09 | The archetype draft's numbers do not match the data (README K13) | Wrong facts on screen | — | closed | Show only engine values; archetype rules and counts in README §6.13 |
| Q-CARDS-10 | Deployment: static Vercel site reading `web/public/data/`; decisions in localStorage + export | Demo without a backend | — | closed | Decided 26 Oct |

## Session entries

No sessions yet. The first entry goes below this line.
