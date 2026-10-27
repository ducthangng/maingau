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
| Q-CARDS-18 | `nba/engine/runtime.py` passes `population(tables)` to `assemble` → `build_profile`. That frame lacks the profile features, so in the real export every card has 0 highlights and no same-combo percentile. Please use `pop = nba.profile.profile_population(states)`: it has every `population()` column, and KG's triage is identical with it (test in `tests/test_profile_card.py`) | Highlights A5 and the A2 percentile vanish from all 750 real cards (with the right frame, 321 customers get 1–3 highlights) | Agent NBA | open | — |

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

### Session 2b · 2026-10-26 16:40–16:55 Europe/Berlin · Claude Code (Opus 5.5) · branch feat/cards · commits 82f453b..(this commit)

**Goal:** deliver Session 2 to `main` (Agent KG's priority: NBA's assemble needs `nba/profile`) and check how NBA's new export uses it.

**Done:**
- Committed Session 2 as 82f453b (only my paths, 107 files; `git diff --cached` checked). Merged `origin/main` (NBA delivery ef82704, K11 decision 8ecc8ce) as dde01a2; no overlap with my paths.
- `git push -u origin feat/cards`, then `git push origin feat/cards:main` (fast-forward 8ecc8ce..dde01a2).
- `nba/profile/population.py`: `profile_population()` now also has every column of `nba.state.population()`, so NBA can use one frame everywhere (Q-CARDS-18). New test `test_profile_population_can_replace_state_population`.

**Verified:**
- After the merge: `.venv/bin/python -m pytest -q` → 117 passed, including NBA's engine and acceptance tests with `nba/profile` present. `npm run build` → OK.
- After the population change: `pytest -q` → 118 passed. KG triage is identical with both frames for all 750 customers. Highlights per customer: `population()` → 0 for all 750; `profile_population()` → 0: 429, 1: 243, 2: 72, 3: 6.

**Not done / carried over:** switching `web/public/data` to NBA's real export (`python -m nba.build --export web/public/data`): first decide the size (750 cards vs the ~20 MB limit in README §13.2) and wait for Q-CARDS-18 so the real cards carry highlights.

**Contract changes:** none.

**Questions to consider:** Q-CARDS-18 (Agent NBA: pass `profile_population(states)` as `pop`).

**Issues / risks:** none new.

**Handoff:** Agent NBA: Q-CARDS-18 is a one-line change in `nba/engine/runtime.py` (`population(tables)` → `profile_population(states)`).

**Next session starts with:** measure the size of NBA's export for 750 customers, then switch the UI data to it.

### Session 3 · 2026-10-27 ≈00:30–02:40 Europe/Berlin · Claude Code (Opus 5.5) + workflow `overview-review` (4 subagents) · branch feat/cards · commits 327670e, 2af2654, (this commit)

**Goal:** the two briefs `prompts/ui-customer360.md` (Customer 360° and the dashboard switch) and `prompts/ui-overview.md` (Overview page), with tests.

**Done:**
- Customer 360° (327670e):
  - The Orchestration | Customer 360° switch with customer-ID search (`components/service/ViewSwitch.tsx`).
  - `/service/:id` with a fixed strip and the Profile / Customer journey / Next best actions tabs (`pages/Service.tsx`, `components/service/*`).
  - Plain-language rule texts with no payment wording (`components/service/plain.ts`).
  - Mentioned / Interested / Declined rows in the `service_nba_feedback` shape (`lib/serviceFeedback.ts`).
- Tests (2af2654): vitest (`npm test`) with `plain.test.ts`, `serviceFeedback.test.ts`, and `customer360.test.tsx` (§4 acceptance plus a scan of all 750 customers for tier, flag, segment and payment wording).
- Overview (this commit):
  - `pages/Overview.tsx`, `components/overview/{model.ts, ActionTable.tsx, SegmentBreakdown.tsx, format.ts}`.
  - `/` is now the Overview and the Worklist is at `/worklist`. The nav reads Overview · Worklist · Groups. The three back links in `pages/Customer.tsx` go to `/worklist`.
  - The open action is kept in `?open=`. ↑/↓, Enter/Space and Esc work on rows; Esc returns focus to the row.
  - Segment rows link to `/worklist?offer=…&arch=…&pers=yes&queue=all`, or `pers=no` for Not personalised.
- Overview tests:
  - `model.test.ts` (14 tests, real `public/data`): every action matches `summary.chosen_by_offer`; totals 10 / 617 / +€7,302, 47 service, 86 NO_ACTION; the ranking table; reasons and labels with no code outside the tooltip; an older export reads "not enough data"; both percentage columns sum to 100 for every action; the StromGarant and StromAktiv splits; every segment link run through `matches()` gives the same count.
  - `overview.test.tsx` (7 tests): rendered text, tooltips, links and the empty-segment state.
- Independent review (workflow: 2 reviewers + 2 adversarial verifiers): 9 findings, 3 confirmed, all fixed. Fixed:
  - focus ring clipped by the card → drawn inward;
  - mobile ΔCLV bars of different widths → fixed track;
  - header total and service count without a source tooltip.
  The 6 refuted findings describe cases the engine cannot produce (null ΔCLV on a chosen action, personalised rows without a reason). One refuted keyboard detail (focus lost after Esc) was fixed anyway.

**Verified:**
- `npm test` → 69 passed (5 files). `npm run build` → OK.
- Browser on :5173 (static data):
  - At 1280 px no sideways scroll (document 1265 px); the nav reads Overview* · Worklist · Groups; 10 action rows; StromGarant shows 44 · 67% / +€552 · 54% etc.
  - StromAktiv → Not personalised opens the Worklist with exactly 79 rows and the ✕; Back restores `?open=P-EN-01`.
  - ↓ / Enter / Esc work.
  - At 375 px no sideways scroll; the reasons wrap under the offer name; the bars share one width (83 px).
- Customer 360° (Session 3, first part): the acceptance customers MG-100186, MG-100096, MG-100023, MG-100112 and MG-100026 checked in the browser. A mutation check showed that removing the payment sanitizer fails 3 tests and showing `payment_method` fails the 750-customer scan.

**Not done / carried over:**
- The Overview is not checked in API mode (no `uvicorn` running here).
- The 6 refuted review findings were left as is.

**Contract changes:** none.

**Questions to consider:** none new.

**Issues / risks:** the brief asked to change only the links in `Customer.tsx`. `ViewSwitch` still sends "Orchestration" to `/`, which is now the Overview, as the brief intends.

**Handoff:** marketers now land on the Overview; links that meant the Worklist must use `/worklist`.

**Next session starts with:** run the Overview against the live API (`uvicorn api.app:app`) and check the same acceptance numbers.

### Session 4 · 2026-10-27 ≈08:50–10:00 Europe/Berlin · Claude Code (Opus 5.5) + workflow `ui-polish-build` (4 subagents) · branch feat/cards · commits (this commit)

**Goal:** `prompts/ui-polish.md`: bring Customer 360° and the Overview to the Orchestration standard (borders, clipping, responsive). Style and layout only.

**Done:**
- `pages/Service.tsx` and new `components/service/ServiceColumn.tsx`:
  - Each column is an Orchestration card (`rounded-2xl border`, 11 px uppercase title) with an `@container` body.
  - From xl the body scrolls inside the card: `px-4 pb-4 pt-1.5` leaves room for rings and outlines, with `[scrollbar-gutter:stable]`.
  - A bottom fade (`mask-image`) shows while more content follows (`data-more`, scroll event + ResizeObserver).
  - The column height is measured: a ResizeObserver sets `--c360-h` from the grid's position, replacing the guessed `17rem`.
  - Breakpoints: one column below lg; at lg Profile and Next best actions side by side, with the journey full width below; from xl `minmax(17rem,1fr) minmax(17rem,1fr) minmax(24rem,1.6fr)`.
- Workflow builders (three in parallel, then one integration agent):
  - `ActionsTab.tsx`:
    - banner with `border` and LifeBuoy icon;
    - option rows with `border`; selected `ring-2 ring-inset`, emerald for #1 and accent otherwise;
    - offer and reason lines `line-clamp-2`; bar from `@sm:`;
    - `DecisionBox variant="inline"` inside a list card; "Not recommended" with `border` and wrapping.
  - `NbaPanel.tsx`: only the opt-in `variant` prop; the default (pop-up) renders the same markup, checked with renderToStaticMarkup for 750 customers and 732 state combinations.
  - `ProfileTab.tsx` and `JourneyTab.tsx`:
    - `ring-1` → `border`; lists with `divide-y`;
    - long values wrap or keep the full text in `title`;
    - product tiles in a shrinking 6-column grid; journey chips wrap.
  - `SegmentBreakdown.tsx`: `@container`; below `@lg` two lines per segment; from `@lg` today's grid.
  - `ActionTable.tsx`: offer names `line-clamp-2` instead of `truncate`.
- Inset focus outline: the global `:focus-visible` rule in `index.css` is unlayered and beats every layered utility. Only the important form `focus-visible:-outline-offset-2!` takes effect. Session 3's Overview row fix used the plain class and therefore never applied; it now uses `!`.

**Verified:**
- `npx tsc --noEmit` OK; `npm test` → 94 passed (8 files); `npm run build` OK.
- Acceptance in the browser at 375, 768, 1024, 1280, 1440 and 1920 px for MG-100096, MG-100023, MG-100186 and MG-100068, plus the Overview (P-EN-02 and P-EN-01 open). The checker ran in the page, measuring geometry; it is not committed. Results at every width:
  - page sideways scroll 0;
  - no clipped border or ring; no clipped focus outline (inset ones counted only in the `!` form);
  - no cut text without a `title`;
  - decision box `static`, `border-top 0`, no backdrop, buttons inside;
  - fade on while more content follows, off at the bottom.
  - Column widths: 343 (phone), 721 (768), 478/977/478 (1024), 331/331/530 (1280), 375/375/601 (1440), 508/508/815 (1920).
- Overview segments: at 375 px 5/5 and 2/2 rows on two lines with one-line names; from 640 px today's single-line grid.
- Orchestration unchanged: fingerprints of `/worklist`, `/customer/MG-100068` and `/groups` (every element's position, size, borders, shadow, outline, colours normalised to RGBA, font and padding) are identical before and after at all 6 widths (18/18). Two runs in a row showed the fingerprint is not noisy.

**Not done / carried over:**
- On a phone the sticky Customer 360° strip (`sticky top-14`, about 250 px tall) covers much of the screen. It is sticky on purpose (ui-customer360 §3.1 "always visible") and outside this brief; worth a team decision.
- Scroll events in the hidden browser pane arrive late, so the fade check fires the scroll event itself.

**Contract changes:** none.

**Questions to consider:** none new.

**Issues / risks:** `index.css` keeps its unlayered `:focus-visible`. Any future inset outline must use the `!` form, or the global rule should move into `@layer base` (that touches Orchestration, so it needs its own check).

**Handoff:** `DecisionBox` has `variant="inline"` for embedded use; the pop-up keeps the default.

**Next session starts with:** a team decision on the phone sticky strip; otherwise wait for the next brief.
