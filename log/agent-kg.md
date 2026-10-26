# Agent KG: session log

Owner: **Agent KG** (README §7.1: data loading, ontology, KG, signals, rules, explanation paths). Only Agent KG writes in this file. Logging rules: README §12.

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
- <task> — files: `<path>`, functions: `<name>()`, tests: `<test file>`

**Verified:** commands actually run and their results (e.g. `pytest -q tests/test_kg_policy.py` → 12 passed; S1 count = 12).

**Not done / carried over:** what is unfinished and why.

**Contract changes:** changes to README §5/§6 made in this session (with PR/commit), or "none".

**Questions to consider:** new IDs added to the table below (Q-KG-xx), one line each.

**Issues / risks:** bugs, data quirks, blockers — with evidence (customer_id, row, count).

**Handoff:** what Agent CARDS / Agent NBA need to know or change.

**Next session starts with:** the first concrete step.
```

## Open questions and issues to consider

These are kept up to date and edited in place. Status values: `open`, `answered`, `decided-default`, `closed`.

| ID | Question / issue | Why it matters | Ask whom | Status | Answer / decision (date) |
|---|---|---|---|---|---|
| Q-KG-01 | Without `profiling_analytics`, may contract/device facts (holdings, devices) still select a marketing offer? Default: yes for `contract`/`device` signals, no for `behavioural` ones (README K3) | Decides the candidates for 289 customers and the outcome of test MG-100112 | MAINGAU mentor (Jan / Caro) | decided-default | — |
| Q-KG-02 | Does `autostrom_contracts.status = cancelled` block all sales, or only e-mobility offers? Default: all (K6) | 9 customers; changes their candidates | MAINGAU mentor | decided-default | — |
| Q-KG-03 | Is an unsubscribe found in `newsletter_performance` a withdrawal of `newsletter_email` only, or also of `marketing_email`? Default: newsletter only (K9) | Changes allowed channels for customers with `unsubscribed = 1` (58 rows) | MAINGAU mentor | decided-default | — |
| Q-KG-04 | Snapshot mode: are status columns authoritative ("provided"), or should we rebuild state as of the cutoff? Default: provided (K8) | 79 CDRs arrive after the cutoff; TK-200565 and TK-200640 are closed with a later `resolved_at` | Raphael (Data Architect) | decided-default | — |
| Q-KG-05 | Which definition counts as "Autostrom-only"? The spec says 150; the file gives 159 / 161 / 127 depending on the definition (K4) | Segment counts on the overview page and in the pitch | Team | open | — |
| Q-KG-06 | S4 (price guarantee < 90 days, active electricity) counts 116, while the churn driver "price guarantee ends <90d" appears for 145 customers. Reconcile: gas contracts? evaluation date? | P-EN-02 eligibility and its value (driver removal) | Agent KG (self), then NBA | open | — |
| Q-KG-07 | Event `ticket_updated` references `TK-open-complaint`, which is not in the snapshot. Treat it as an orphan with a conservative customer-level complaint flag? | Exclusion for MG-100004 during event replay (stretch) | Team | open | — |
| Q-KG-08 | P-EN-04 (GasAktiv) and P-IN-01 (Internet) are never generated (`DATA-MISSING`). Confirm this is acceptable for the hidden reference customers | Catalog coverage | MAINGAU mentor | decided-default | — |

## Session entries

No sessions yet. The first entry goes below this line.
