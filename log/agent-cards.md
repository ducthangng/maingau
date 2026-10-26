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
| Q-CARDS-11 | The bulk preview needs each customer's checklist result and contact cost, but `IndexRow` has neither (only `CustomerCard.checklist` and `valuation.contact_cost`). Default: on "Approve group" the UI loads `customers/<id>.json` for every selected row. Add `checklist_failed: list[ChecklistKey]` and `contact_cost` to `IndexRow`? | README §7.2: bulk approval refuses failing checklists; the preview shows Σ contact cost | Agent NBA | answered | Added `IndexRow.contact_cost` and `checklist_failed` (commit 30dc4c9, by Agent KG for NBA, 26 Oct). The Groups screen uses them |
| Q-CARDS-12 | Worklist numbers (CLV, churn, ΔCLV, p) have no `src` / `updated_at`, and refresh/latency (`sources`) exist only inside each card. Default: a fixed column → `table.column` map in the UI. Add `sources` and the value date to `summary.json`? | "Every number has a source tooltip" also applies to the worklist | Agent NBA (owns `Summary`) | answered | Added `Summary.sources`, `column_src` and `value_date` (commit 30dc4c9, 26 Oct). The worklist and Groups tooltips use them |
| Q-CARDS-13 | The static demo has no API to re-run the gates on an override. Default: only tuples present in `candidates` can be selected; anything else is refused, showing the matching `blocked` rule or "not evaluated by the engine" | An override must never select a blocked combination (README §6.10) | Agent KG (review) | answered | Confirmed by Agent KG (26 Oct): static overrides only to tuples in `candidates` |
| Q-CARDS-14 | The sensitivity hint (prompt §1.4 item 5) has no field in `CustomerCard`; Agent NBA's ±20% check only goes into `out/test_report.md` (README §7.3 M3). Default: hidden | Never show a number the engine did not produce | Agent NBA | answered | Confirmed by Agent KG (26 Oct): stays hidden |
| Q-CARDS-15 | `load_workbook` leaves `portal_sessions.session_start`, `mobile_contracts.min_term_end` and `portal_sessions.offer_banner_shown` as strings (their names do not match the date/bool rules). `nba/profile` parses the two dates itself (`facts.to_datetime`). Add `_start`/`_end` to the date suffixes and `offer_banner_shown` to the bool columns? | Every agent that reads these columns must otherwise parse them again | Agent KG | open | — |
| Q-CARDS-16 | `customer_value.clv_service_impact_eur` is always ≤ 0 in the data (a cost, e.g. −286). Spec A2 says "Service issues are costing €X"; the card shows it when the value is < 0, as €|X| | The banner would never show with an "if > 0" rule | Team | decided-default | — |
| Q-CARDS-17 | KG explanation paths for P-SV-01 point to `ui_ref = product:service`, but the product grid has no service cell. Default: the left card anchors `product:service` on the service trend block | Path chips must always land somewhere | Agent KG | decided-default | — |

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

### Session 2 · 2026-10-26 15:40–16:40 Europe/Berlin · Claude Code (Opus 5.5) + workflow `cards-demo-build` (10 subagents) · branch feat/cards · commits 20f066f..(this commit)

**Goal:** M0 plus a first clickable demo ("simple demo first"): branch, Vite scaffold, TypeScript types from `docs/schema/`, data for about 40 customers, worklist → customer page → bulk approval with holdout → export.

**Done:**
- `web/` scaffold: Vite 6, React 18, TypeScript (strict), Tailwind v4 via `@tailwindcss/vite` with the CSS-first theme in `src/index.css`, React Router, and `vercel.json` with an SPA rewrite that excludes `/data` and `/assets`.
  - `npm run types` (`web/scripts/gen-types.mjs`) generates `src/types/contracts.ts` from `docs/schema/*.json` and maps pydantic `Any` to `unknown`.
  - `npm run check:data` (`web/scripts/check-data.mjs`) validates `public/data` against `docs/schema/` with ajv.
- Shared UI foundation: `src/lib/data.ts` (cached loaders), `src/lib/format.ts` ("not enough data", € formats), `src/lib/decisions.ts` (localStorage decision log `maingau.decisions.v1`, CSV/JSON export, deterministic holdout by FNV-1a hash), `src/components/{Layout,Source,Chips}.tsx`, `src/pages/Customer.tsx`, and `src/types/trends.ts`.
  - The source tooltip on every number shows `table.column`, the update time, and refresh/latency taken from `sources`.
  - A MOCK DATA badge shows while `manifest.json` says `source: mock`.
- Screens, built by the workflow (4 parallel builders, then integrate, 2 reviewers with adversarial verify, then fix):
  - Worklist (`pages/Worklist.tsx`, `components/worklist/`): KPI strip, search, 8 filters, 5 saved views, group-by, outlier bar and badge, keyboard ↑/↓/Enter and `/`, URL-kept filters.
  - Groups (`pages/Groups.tsx`, `components/groups/`): groups by `chosen_tuple`, a preview sheet with Ready / Needs a second look / Do no harm (A4 or service_critical rows cannot be ticked), a 10% holdout, "Approve N for hand-off" (never "send"), a decision log, CSV/JSON export and reset.
  - Left card (`components/profile/`): header with Du/Sie evidence, triage banner, consent and exclusion traffic lights, value and risk, 6-cell product grid, highlights, signal chips, timeline, recharts trends with the "no CLV trend" note, and fatigue. `data-ui-ref` jump targets are on all of these.
  - Right card (`components/nba/`): reason line, top action with a ΔCLV waterfall on `clv_now_model`, a p / 1 − p bar with evidence, notes, checklist, a German preview with a "nicht personalisiert" badge, clickable path chips, and Approve / Override… (only `candidates` tuples) / Reject (reason required). Then alternatives, blocked actions, legacy comparison, data quality and the audit log, plus service mode "Resolve first" with the agent script.
- `nba/profile/` v0, built on the real snapshot: `infer_tone` (§6.8), `build_profile`, `build_timeline` and `profile_population`. Consent, channels and exclusions come from Agent KG's views (`nba.kg.rules`), so no rule is re-implemented. `config/cards.yaml` gained `trend_ranges`.
- `web/mock/build_mock.py` writes `web/public/data` for 40 customers: 2 representative customers, 13 test customers and 25 picked to cover archetypes, tiers, flags, rules and checklist failures.
  - Real parts: `nba.profile` plus `nba.kg.bundle.kg_bundle()` + `source_info()` + `COLUMN_SRC`.
  - Mock parts (labelled in `manifest.json`): p_accept (rate mode), ΔCLV, ranking, chosen, alternatives, German copy and the legacy ΔCLV.
  - It refuses to overwrite a folder that is not mock data (`--force` overrides; `--out` writes elsewhere).
- My own fixes after the workflow:
  - No sideways scroll at 375 px (Layout wraps; the Customer grid uses `minmax(0,1fr)`).
  - "← Worklist" and Esc go back in history, so worklist filters survive.
  - Money is formatted in English (`€1,440`, `+€18.93`) to match the reason lines.
  - The blocked list puts the most telling rules first (exclusions, CONSENT-PROFILING, …, DATA-MISSING).
- `tests/test_profile_card.py` (29 tests): all 750 profiles validate and the timeline is sorted newest first; facts of MG-100325 and MG-100001; complete left cards for the 13 test customers; tone rules on synthetic states (Kunde-only lines, sentence-start "Ihr", ≥ 2 newsletter clicks, profiling off → default Sie).

**Verified:**
- `.venv/bin/python -m pytest -q` → 69 passed (KG 40 + profile 29).
- `npm run check:data` → 40 index rows, 40 cards, 0 failures. `npm run build` → OK. The only warning is the >500 kB chunk, mostly recharts.
- `build_mock.py` run twice gives identical output; the guard exits 1 on a non-mock folder.
- Test customer outcomes in the mock:
  - MG-100009, MG-100659, MG-100096, MG-100186, MG-100004 → P-SV-01 (service mode).
  - MG-100035, MG-100087 → NO_ACTION.
  - MG-100023 → P-AS-01.
  - MG-100112 → generic P-EN-01 by phone, +€14.87 (= K11).
  - MG-100051, MG-100060 → P-EN-03 (MG-100060 by phone).
  - MG-100012 → generic P-MO-01.
  - MG-100068 → P-EN-02, ahead of P-EN-03 / P-SL-01 / P-AS-01.
- Browser (Vite dev server on :5173), no console errors:
  - Worklist and MG-100068 at 1280 px with no sideways scroll; the Consent path chip scrolls to and flashes `consent:newsletter_email`; Approve writes `MG-100068 approved P-EN-02|newsletter_email|sie ΔCLV 18.93`.
  - MG-100009 shows "Resolve first" with the German agent script; MG-100035 shows "No action" with the reason.
  - MG-100112 shows "nicht personalisiert", default Sie, and "S3 ignored … no profiling consent" at the top of the blocked list.
  - The P-MO-01 portal group preview shows 5 ready, 2 for a second look, the holdout switch and "Approve 5 for hand-off".
  - At 375 px the worklist and MG-100325 have no sideways scroll.
  - Test decisions were removed from localStorage afterwards.
- Workflow review: 17 findings, 12 confirmed by the verifiers, all 12 fixed. Fixed:
  - prior reject/override pre-ticked in the group preview;
  - Esc while typing a reason;
  - HEMS null shown as 0 kWh;
  - negative `guarantee_days_left`;
  - former Autostrom shown as an opportunity;
  - Marketing toggle stuck in service mode;
  - missing tooltips on waterfall and audit numbers;
  - service rows without p;
  - unclear "No open service issue" for cancellation customers.

**Not done / carried over:**
- Switching to `python -m nba.build --export web/public/data` once Agent NBA delivers it.
- Vercel deploy.
- Hallway test for 30-second readability (Q-CARDS-07).
- Code-splitting recharts.
- Virtualised table for 750 rows (a plain table is fine for 40).
- Real-data worklist for all 750 via `scripts/export_preview.py` (the demo uses the 40 mock customers).

**Contract changes:** none by me. Contracts changed by Agent KG for Q-CARDS-11/12 (30dc4c9).

**Questions to consider:** Q-CARDS-15 (unparsed workbook columns), Q-CARDS-16 (sign of `clv_service_impact_eur`), Q-CARDS-17 (`product:service` jump target).

**Issues / risks:**
- **Branch incident, my cause.** At session start I ran `git checkout -b feat/cards` in the shared folder `MAINGAU`. Agent KG was still committing there, so `fbf9a54` and `30dc4c9` were created on `feat/cards`; KG moved `main` to 30dc4c9 without force. KG's `git add -A` also swept my Session 1 log entry into `fbf9a54` (content unchanged). README §13 now gives every agent its own folder. I only ran `git merge --ff-only origin/main` here since.
- A stale `out/.cache` workbook pickle (built by an older `data.py`) gave NaN strings in numeric columns, so 515 of 750 profiles failed. I deleted the git-ignored pickle and it was rebuilt; KG has since keyed the cache on the code too (99242f4).
- The workflow subagents ran their own Vite servers (:5191, :5197) during checks; none are left running.

**Handoff:**
- Agent NBA:
  - `from nba.profile import build_profile, build_timeline, infer_tone, profile_population`; pass `pop = profile_population(states)` (a superset of `nba.state.population` columns) to `build_profile`.
  - `infer_tone(state)` loads the policy and campaign tonality once.
  - Trend payload keys are documented in `nba/profile/trends.py` and `web/src/types/trends.ts`.
  - Export with plain `model_dump(mode="json")` (no `exclude_none`) so the UI keeps explicit nulls.
- Agent KG: Q-CARDS-15 and Q-CARDS-17.
- Everyone:
  - The UI reads `web/public/data/{index,summary}.json`, `customers/<id>.json` and the optional `manifest.json`. A real export must not contain `manifest.json`, so the MOCK DATA badge disappears.
  - Run `npm run check:data` after any export.

**Next session starts with:** merge `origin/main`; if Agent NBA's export is there, run `python -m nba.build --export web/public/data`, delete `manifest.json`, run `npm run check:data`, and check the 13 test customers in the browser.
