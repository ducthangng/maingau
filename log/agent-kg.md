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
| Q-KG-01 | Without `profiling_analytics`, may contract/device facts still select a marketing offer? | Decides the candidates for 289 customers and the outcome of test MG-100112 | Team / MAINGAU | answered | D1 (26 Oct): no signal is used for marketing; only generic catalog offers at the catalog-average p; owned products removed with contract data (README §6.3, §6.12) |
| Q-KG-02 | Does `autostrom_contracts.status = cancelled` block all sales, or only e-mobility offers? Default: all (K6) | 9 customers; changes their candidates | MAINGAU mentor | decided-default | — |
| Q-KG-03 | Is an unsubscribe found in `newsletter_performance` a withdrawal of `newsletter_email` only, or also of `marketing_email`? Default: newsletter only (K9) | Changes allowed channels for customers with `unsubscribed = 1` (58 rows) | MAINGAU mentor | decided-default | — |
| Q-KG-04 | Snapshot mode: are status columns authoritative ("provided"), or should we rebuild state as of the cutoff? Default: provided (K8) | 79 CDRs arrive after the cutoff; TK-200565 and TK-200640 are closed with a later `resolved_at` | Raphael (Data Architect) | decided-default | — |
| Q-KG-05 | Which definition counts as "Autostrom-only"? The spec says 150; the file gives 159 / 161 / 127 depending on the definition (K4) | Segment counts on the overview page and in the pitch | Team | open | — |
| Q-KG-06 | S4 (price guarantee < 90 days, active electricity) counts 116, while the churn driver "price guarantee ends <90d" appears for 145 customers. Reconcile: gas contracts? evaluation date? | P-EN-02 eligibility and its value (driver removal) | Agent KG (self), then NBA | open | — |
| Q-KG-07 | Event `ticket_updated` references `TK-open-complaint`, which is not in the snapshot. Treat it as an orphan with a conservative customer-level complaint flag? | Exclusion for MG-100004 during event replay (stretch) | Team | open | — |
| Q-KG-08 | P-EN-04 (GasAktiv) and P-IN-01 (Internet) are never generated (`DATA-MISSING`). Confirm this is acceptable for the hidden reference customers | Catalog coverage | MAINGAU mentor | decided-default | — |
| Q-KG-09 | The marketing archetype draft (5 profiles) does not match the data (README K13). Use the rule-based archetypes in README §6.13 | UI must not show wrong ranges | — | closed | Archetypes A0–A5 with verified counts (26 Oct) |
| Q-KG-10 | Generic offers by phone/SMS: MG-100112's generic StromAktiv call is +€14.8 (rate) / +€2.6 (uplift), not negative as D1 assumed (README K11) | Outcome of MG-100112 and of every no-profiling customer whose only channel is a call | Team | open | — |

## Session entries

### Session 1 · 2026-10-26 13:45–16:30 Europe/Berlin · Claude Code (Opus) · branch main · commits f9b26eb..(this push)

**Goal:** set up the repo for three parallel agents, verify the spec against the data, write the KG plan and the prompts for Agents CARDS and NBA (M0).

**Done:**
- `nba/data.py`: `load_workbook()` (typed values; out/.cache pickle) and `load_events()` (dedup by event_id + occurred_at; sorted by ingested_at).
- `nba/state.py`: `CustomerState`, `build_states()`, `active_lines()`, `owns()`, `contacts()`, `population()`.
- `nba/contracts.py` v1 (handed to Agent NBA), now with `Triage`, `Archetype`, `Flag`, `Candidate.origin/personalised/why/notes` and new `IndexRow` fields.
- `config/kg.yaml`, `config/nba.yaml`, `config/cards.yaml`, `requirements.txt`, `pyproject.toml`, `Makefile`.
- README: decision D1 (no profiling → generic path only), `p_mode: rate` (K1), S14–S18 removed, §6.12 tiers, §6.13 triage, §7 tasks, §9 test changes for MG-100023/MG-100112, K11–K13.
- `PLAN_KG.md` rewritten to match the README; `prompts/agent-cards.md` and `prompts/agent-nba.md` written.

**Verified:**
- `load_workbook()`: 23 sheets in ~2 s uncached; typed values (bool/int/float/datetime/None); 25 guest shop rows flagged.
- `load_events()`: 635 unique events, last ingest 2026-10-03 19:27:39.
- `build_states()`: 750 customers in 0.65 s.
- Churn reconstruction exact for 718/718 customers (formula in README §6.5).
- Archetype draft checked against the data (README K13).
- Triage prototype: archetypes A2 342 / A3 201 / A4 75 / A5 50 / A1 33 / A0 49; tiers P1 53 / P2 62 / P3 95 / P4 234 / P5 306.
- Generic-offer economics for MG-100112, MG-100023 and MG-100012 (K11).

**Not done / carried over:** `kg/ontology.yaml`, `kg/policy.yaml`, `nba/kg/*` and the KG tests (PLAN_KG steps 2–7).

**Contract changes:** `nba/contracts.py` v1 created; README §5.4–§5.5 updated in the same commit.

**Questions to consider:** Q-KG-09 (closed), Q-KG-10 (open, K11).

**Issues / risks:**
- pandas 3 keeps NaN in object columns, so `data.py` normalises nulls explicitly; do not replace it with `df.where(...)`.
- The system Python's pandas lives in the user site-packages, which a plain venv cannot see.

**Handoff:**
- Agent NBA: contracts are yours from now; use a KG stub until `nba/kg` lands.
- Agent CARDS: use `docs/schema/*.json` for TypeScript types; mock data must follow README §6.13 counts, not the archetype draft.

**Next session starts with:** PLAN_KG step 2, `kg/ontology.yaml` + `kg/policy.yaml` + `nba/kg/policy.py` with integrity tests.
