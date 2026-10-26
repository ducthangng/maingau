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
| Q-CARDS-11 | The bulk preview needs each customer's checklist result and contact cost, but `IndexRow` has neither (only `CustomerCard.checklist` and `valuation.contact_cost`). Default: on "Approve group" the UI loads `customers/<id>.json` for every selected row. Add `checklist_failed: list[ChecklistKey]` and `contact_cost` to `IndexRow`? | README §7.2: bulk approval refuses failing checklists; the preview shows Σ contact cost | Agent NBA | open | — |
| Q-CARDS-12 | Worklist numbers (CLV, churn, ΔCLV, p) have no `src` / `updated_at`, and refresh/latency (`sources`) exist only inside each card. Default: a fixed column → `table.column` map in the UI. Add `sources` and the value date to `summary.json`? | "Every number has a source tooltip" also applies to the worklist | Agent NBA (owns `Summary`) | open | — |
| Q-CARDS-13 | The static demo has no API to re-run the gates on an override. Default: only tuples present in `candidates` can be selected; anything else is refused, showing the matching `blocked` rule or "not evaluated by the engine" | An override must never select a blocked combination (README §6.10) | Agent KG (review) | decided-default | — |
| Q-CARDS-14 | The sensitivity hint (prompt §1.4 item 5) has no field in `CustomerCard`; Agent NBA's ±20% check only goes into `out/test_report.md` (README §7.3 M3). Default: hidden | Never show a number the engine did not produce | Agent NBA | decided-default | — |

## Session entries

### Session 1 · 2026-10-26 ≈15:20–15:35 Europe/Berlin · Claude Code (Opus 5.5) · branch main (no `feat/cards` yet) · commits none (log not committed yet)

**Goal:** onboarding before M0. Read the repo, the CARDS brief and all logs; check that the contracts the UI depends on are ready; list the gaps before scaffolding `web/`. No code written.

**Done:**
- Read README §0–§12, `prompts/agent-cards.md` in full, `PLAN_KG.md` §10 (Agent KG's review duties for CARDS), `prompts/agent-nba.md` §2.7–§2.8 (export and API), `nba/contracts.py`, `config/cards.yaml`, and the three logs (latest entry: Agent KG Session 1; NBA and CARDS empty).
- Repo state at start: `main` @ 72db44d, the only branch on origin. `web/`, `nba/profile/` and `tests/test_profile_*.py` do not exist yet. Agent KG's `kg/*.yaml` and `nba/kg/*.py` are untracked work in progress; not touched.
- Mapped the brief onto the contracts: worklist ← `IndexRow` + `Summary`; customer page ← `CustomerCard`; tooltips ← `Fact` + `CustomerCard.sources`; bulk execution ← `IndexRow.chosen_tuple`, `outlier`, `archetype`, `flags`. The gaps are Q-CARDS-11 to Q-CARDS-14.

**Verified:**
- `docs/schema/*.json` is in sync with `nba/contracts.py`: regenerated the 4 schemas with `model_json_schema()` into a scratch folder, `diff -rq` → no differences. `customer_card.schema.json` has 37 `"additionalProperties": false`, so mock JSON must not carry any extra key.
- Representative customers match prompt §4, checked with `load_workbook()` + `build_states()`:
  - MG-100325: Hamburg, since 2020-02-23, household 2, portal + app; margin 393.39, cost to serve 55, CLV 1440, churn 0.149; drivers "multi-product (4 lines); price guarantee ends <90d; HEMS user"; StromWärme 5,144 kWh `smart_meter_imsys` + feed-in, GasGarant `terminated_meter_deregistration`; devices heat_pump, hems_gateway, pv_inverter, smart_plug, wallbox (no home_battery); phone withdrawn, SMS not given.
  - MG-100001: Köln, born 1955, since 2013-11-22, household 2, portal yes, app no; StromAktiv 1,770 kWh conventional; margin 86.94, cost 19, CLV 261, churn 0.18 ("2 tickets in 12m"); phone and SMS withdrawn.
- All 13 test customers (README §9) exist in `build_states()`.
- Toolchain: node v23.1.0, npm 10.9.0; `.venv` has Python 3.12.

**Not done / carried over:** all of M0–M3: branch `feat/cards`, Vite scaffold, TypeScript types from `docs/schema/`, mock `web/public/data/` (~40 customers), worklist, customer page, bulk preview, `nba/profile/`.

**Contract changes:** none.

**Questions to consider:**
- Q-CARDS-11: the bulk preview needs checklist and contact cost per row; `IndexRow` has neither.
- Q-CARDS-12: worklist numbers have no `src` or refresh/latency for tooltips.
- Q-CARDS-13: overrides in the static demo cannot re-run the gates.
- Q-CARDS-14: there is no sensitivity field; the hint stays hidden.

**Issues / risks:**
- The TypeScript in prompt §3 is looser than the contracts: `TimelineItem.kind` is `string` (contract: 7 values), `ConsentItem.status` is `string` (contract: 3 values), and `decision_log` lacks `from_tuple`, `to_tuple`, `rules_applied` and `scores`. Generate the types from `docs/schema/`; keep the prompt only as reference.
- `IndexRow.chosen_offer` is required, but `delta_clv`, `p_accept` and `confidence` can be null (NO_ACTION rows). The worklist must show "no action" / "not enough data", never 0, and sorting and grouping must handle null.
- ΔCLV is computed on `clv_now_model`, not on the displayed `clv_eur` (README §6.5). The waterfall must start from `clv_now_model` and label `clv_now_shown` separately; otherwise a gap of up to 3.05 € appears. Show `delta_clv` as given; do not recompute it.
- `nba/contracts.py` still comments `Signal.id` as "S1".."S18", although S14–S18 were removed (README §6.3). Cosmetic; Agent NBA owns the file.
- MG-100325 carries the churn driver "price guarantee ends <90d", which the archetype draft omitted (K13). The mock card must show it.

**Handoff:**
- Agent NBA: Q-CARDS-11, Q-CARDS-12 and Q-CARDS-14 ask for optional fields in `IndexRow`, `Summary` and `CustomerCard`. Until they are answered, the UI uses the defaults in the table.
- Agent KG: please confirm the Q-CARDS-13 default (only engine-gated tuples are selectable in static mode) in your review.

**Next session starts with:** create `feat/cards` from `main`; scaffold `web/` (Vite + React + TypeScript + Tailwind + React Router, `vercel.json` with an SPA rewrite); generate `web/src/types/` from `docs/schema/*.json` with json-schema-to-typescript; then write mock `public/data/`, starting with MG-100325, MG-100001 and the 13 test customers, validated against the schema.
