# Agent NBA: session log

Owner: **Agent NBA** (README §7.3: valuation, p_accept, ranking, German content, decision log, API, build). Only Agent NBA writes in this file. Logging rules: README §12.

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

**Verified:** commands actually run and their results (e.g. `pytest -q tests/test_engine_clv.py` → 750 customers within 3.05 €; `python -m nba.build` → 750 files in 41 s).

**Not done / carried over:** what is unfinished and why.

**Contract changes:** changes to README §5/§6 made in this session (with PR/commit), or "none".

**Questions to consider:** new IDs added to the table below (Q-NBA-xx), one line each.

**Issues / risks:** bugs, data quirks, test failures, blockers — with evidence (customer_id, numbers).

**Handoff:** what Agent KG / Agent CARDS need to know or change.

**Next session starts with:** the first concrete step.
```

## Open questions and issues to consider

These are kept up to date and edited in place. Status values: `open`, `answered`, `decided-default`, `closed`.

| ID | Question / issue | Why it matters | Ask whom | Status | Answer / decision (date) |
|---|---|---|---|---|---|
| Q-NBA-01 | p_accept definition: uplift (spec: treated − control) or shrunk treated rate? With uplift, P-AS-01 (0/203 treated, 0/21 control) has p = 0 and is always dropped (K1) | Team confirmed MG-100023 → P-AS-01; affects every ranking | Jan (PM B2C Energy), Caro | decided-default | `p_mode: rate`; uplift computed and reported as evidence (26 Oct) |
| Q-NBA-02 | Priors for the 8 offers with no history (P-EN-01, P-EN-03, P-EN-04, P-MO-03, P-SL-02, P-SL-03, P-SH-04, P-SV-01). Default: global uplift 1.4%; P-SV-01 `p_service_success = 0.5` (K2) | StromWärme tests (MG-100051 / MG-100060) and every service decision depend on it | MAINGAU mentor | decided-default | — |
| Q-NBA-03 | Contact cap N per 30 days. Default: 2 marketing contacts; service exempt (K5) | Checklist C5 and the candidates for frequently contacted customers | Caro (Marketing) | decided-default | — |
| Q-NBA-04 | New business line: use the catalog churn effect only, or also the multi-line factor 0.8 and +12 € cost per line? Default: catalog effect only (K7). For the same customer, double counting inflates ΔCLV by about 40% | Size of every cross-sell ΔCLV | MAINGAU mentor | decided-default | — |
| Q-NBA-05 | Retention content (P-EN-02) while `cancellation_pending`: blocked as sales content? Default: blocked (K10) | MG-100035 / MG-100087 outcome | MAINGAU mentor | decided-default | — |
| Q-NBA-06 | The given `clv_eur` differs from the formula by up to 3.05 € (median 0.27 €). Compute ΔCLV on the model basis, display `clv_eur` | Avoids fake gains from rounding | — | closed | Model basis for ΔCLV; log both (README §6.5) |
| Q-NBA-07 | Only 20 of the 50 offer × channel cells have n ≥ 30, and per-offer control groups are n = 19–32 with 0–1 conversions. Is the control baseline per offer or global? | Stability of p and of the "confidence" labels | Team | decided-default (global if n_control < 30) | — |
| Q-NBA-08 | MG-100060 can only be reached by `outbound_call` (6 €). Check that ΔCLV stays > 0 for P-EN-03 under both p modes; if not, report NO_ACTION with the reason | Spec test expects StromWärme | Agent NBA (self) | closed | Verified 26 Oct: P-EN-03 by call is +€19.5890 (rate), +€4.4707 (uplift), including the €6 cost |
| Q-NBA-09 | Re-check the earlier 6.8% vs 2.1%, roughly 2.3× need-first statistic using implemented signals | Credibility with the jury | Agent NBA with Agent KG | closed | 26 Oct: S1–S13 plus signal.offers give 9/82 (10.98%) vs 12/930 (1.29%) across five offers with implemented triggers; 1,010 other treated rows excluded. Common-offer-weight rates are 7.15% vs 1.40% (5.09×). This is a snapshot proxy, not at-send evidence or causal uplift; it does not reproduce the earlier classifier/cohort. See out/impact_report.md; do not reuse the older numbers as S1–S13 results |
| Q-NBA-10 | Should unchecked legacy observations be excluded when estimating p? | Calibration cohort, auditability and current eligibility must remain distinct | Agent NBA (decision requested by user) | closed | 26 Oct: retain all treated/control observations per §6.6, including 297 unchecked delivered rows (10 conversions) and 36 unchecked controls (0 conversions). The flag records whether the legacy engine checked consent, not current permission. The impact report exposes checked/unchecked cohorts; today's KG gates always apply. No silent filtering or ranking change |
| Q-NBA-11 | K11: allow generic offers by phone/SMS? MG-100112's generic StromAktiv call is +€14.87 (rate) / +€2.54 (uplift) | MG-100112 outcome | Team | closed | Decided by the team, 26 Oct (README §9/§10 at e40c526): all consented channels including phone/SMS; strict expected choice is P-EN-01/outbound_call/sie in both modes, generic and not personalised; S3 stays blocked by CONSENT-PROFILING |
| Q-NBA-12 | K12: profiled customers fall back to generic offers only when no signal/service tuple has ΔCLV > 0 | Coverage vs need-first | Team | decided-default | Fallback on (`generic.fallback_for_profiled: true`) |
| Q-NBA-13 | `kg/policy.yaml` has `P-EN-03.requires: []`, while the earlier README §6.4 required active electricity | Reconcile the holding requirement without duplicating KG gates | Agent KG | closed | After merging 20f066f, README §6.4 also has no active-electricity requirement for P-EN-03; NBA follows the current policy |
| Q-NBA-14 | Answer Q-KG-11: correct Order evidence comments; add optional `ConsentItem.doi_at`? | Consent proof and a stable interface for CARDS | Agent KG / CARDS | decided-default | Comments corrected to `order:SO-1` and S1–S13. Defer the optional field: the KG channel reason already includes the actual DOI date; no schema change is needed for the current UI. Revisit if CARDS needs a structured date |
| Q-NBA-15 | Answer Q-KG-12: use public `check_tuple` in API and legacy comparison | One source of truth for gates | Agent KG | closed | Implemented after merging 20f066f; every legacy blocker includes the public check's IDs, and override 409 uses its IDs and reasons |
| Q-NBA-16 | Answer Q-KG-13: tiers and `ECON-NONPOSITIVE` evidence | Need-first arbitration and MG-100023 | Agent KG | closed | `evaluate_candidates()` evaluates signal/service first, enables generic fallback according to config, and records non-positive tuples with `counterfactual_delta_clv`; both-mode tests cover all 750 customers |
| Q-NBA-17 | Answer Q-KG-14: reduce the static export to ≤20 MB | Static delivery size | Agent KG / CARDS | closed | Compact JSON and one best channel per offer; full checks/path only for the chosen offer and three alternatives. 752 JSON files total 18,827,005 bytes (rate), 18,803,600 (uplift), all schema-valid. Runtime/API retain all evaluated tuples; no web/public/data committed |
| Q-NBA-18 | Answer Q-KG-15: English internal decision reasons | Consistent worklist and pitch | Agent KG | closed | NBA-owned NO_ACTION, ECON-NONPOSITIVE, valuation evidence, alternatives, checklist and API refusal text are English. German templates and customer content remain German |
| Q-NBA-19 | Answer Q-KG-16: K11 strict in both probability modes | Confirm the agreed generic phone outcome | Agent KG | closed | Both-mode acceptance asserts chosen P-EN-01/outbound_call/sie, origin generic, content not personalised, and S3 blocked by CONSENT-PROFILING. Q-NBA-11 closed |
| Q-NBA-20 | Answer Q-KG-17: optional API replay | Deep-dive B demo | Agent KG / CARDS | closed | POST /api/replay?until= calls KG replay with current chosen tuples as pending, assembles affected cards and returns revocations/transitions. Explicit preview_only=true: no mutation of snapshot API state, approvals or audit log. Cutoff uses the mock stream's timezone-naive timestamps |
| Q-NBA-21 | Refresh KG-owned API docs after this delivery | docs/api.md and docs/openapi.json at 6e46313 describe the preceding API version | Agent KG | open | Live /openapi.json already includes replay; a verified scratch copy is in out/openapi.json. Please regenerate the tracked OpenAPI and update docs for the preview endpoint, English reasons, reduced static view and resolved Q-KG-14/15/16/17 |

## Session entries

### Session 1 · 2026-10-26, M1 checkpoint recorded 17:00 Europe/Berlin · Codex (GPT-6) · branch feat/nba · commits 955a1c3..(this commit)

**Goal:** implement the valuation foundation while KG and CARDS work in their own worktrees.

**Done:**
- Created the separate `MAINGAU-nba` worktree on `feat/nba`; pulled the current main and merged `origin/main` (955a1c3), including README §13. No files in another agent's worktree were edited.
- Added `nba/engine/config.py`, `clv.py`, `churn.py`, `propensity.py`, `value.py`, `rank.py`; numeric model parameters come from the workbook.
- Added `config/nba.yaml: rate_prior_mean: 0.034`, making the README §6.6 shrinkage prior explicit and editable. Generic probabilities use the exact global rate 69/2022; uplift uses the raw treated rate minus the documented control baseline.
- Added the CLV, churn, propensity and value test modules.

**Verified:**
- `python -m pytest -q -p no:cacheprovider tests/test_engine_clv.py tests/test_engine_churn.py tests/test_engine_propensity.py tests/test_engine_value.py` → 18 passed in 0.38 s.
- CLV across 750 customers: max absolute error €3.046117, median €0.271229.
- Churn matches all 750 supplied values: 718 active customers plus 8 cancellation-pending cases are reconstructed; 24 without an active contract retain the given value. This clarifies the README's 718 versus 24 counts.
- MG-100009 service value +€84.9798; MG-100035 service value −€7.50 because churn remains 0.95. MG-100060 P-EN-03 is positive in both modes (Q-NBA-08).
- Additional integration work remains uncommitted for M2/M3; its first full test run passed 66 tests, and final changes will be checked again before delivery.

**Not done / carried over:** assemble/export, German templates, API, full acceptance and sensitivity report are delivered in the next checkpoint. The real CARDS profile builder is not yet available.

**Contract changes:** none. Existing worklist fields from 30dc4c9 are consumed without schema changes.

**Questions to consider:** Q-NBA-08 closed; Q-NBA-13 asks KG to reconcile the P-EN-03 holding requirement. Q-NBA-09, Q-NBA-10 and K11 remain open; existing README defaults are retained.

**Issues / risks:** no delivery integrations. Existing mock history with `consent_checked = 0` remains in the propensity observations, following §6.6's treated definition; it is never used to permit a current contact.

**Handoff:** `load_config(tables)` provides `EngineConfig`; `p_accept()` returns `Propensity` including its `PSource`. No change is needed in KG or CARDS for the valuation modules.

**Next session starts with:** finish and verify M2/M3 integration, then export all 750 cards and deliver the branch.

### Session 2 · 2026-10-26 17:00–17:16 Europe/Berlin · Codex (GPT-6) · branch feat/nba · commits 34a9f5c..(this commit)

**Goal:** complete M2/M3: real KG integration, German content, build/export, API, acceptance and sensitivity report.

**Done:**
- Merged `origin/main` at 20f066f, including the parser cache fix, K6 scope fix, `kg_bundle`, `check_tuple`, `source_info` and `COLUMN_SRC`. Re-ran pytest before adapting the integration: 87 passed.
- `nba/engine/assemble.py`: calls `kg_bundle()` once per card; values and ranks the evaluated tier, records economic blocks, creates alternatives, legacy comparison, the six-item checklist, data-quality notes and the proposed audit entry.
- `nba/engine/profile_adapter.py`: imports CARDS' `build_profile`, `build_timeline` and `infer_tone` when available; otherwise emits valid placeholders with `PROFILE-PENDING`. No profiling consent always means default Sie and no tone inference.
- `nba/engine/content.py`, `schedule.py`, `templates/de/*.yaml`: all 18 offers have du/sie × personalised/generic variants. Retention dates are only injected for personalised content. P-SV-01 has an apology, next steps and an agent script, without products. Service has no marketing contact fee; the workbook's €15 resolution cost remains in its accept branch.
- `nba/build.py`, `runtime.py`, `report.py`: subset/full builds, `--out`, `--export`, `--p-mode`, `--asof`; all IndexRow worklist fields populated, source metadata copied through KG helpers, and a report for 13 reference customers under both probability modes with a 3×3 p/margin sensitivity grid.
- `api/app.py`: list/filter, customer, summary and decision endpoints. Approvals and overrides re-run KG checks; economic and tier checks also apply. Invalid overrides return 409 with rule IDs. An explicitly supplied approval tuple cannot silently change. Append-only JSONL records use `{customer_id, entry}`, with `entry` matching `DecisionLogEntry`.
- `nba/contracts.py`: comment corrections only (S1–S13, `order:SO-1`); regenerated all four schemas, with no schema differences.

**Verified:**
- `/Users/linhngo/Downloads/Work/Hackathon/MAINGAU/.venv/bin/python -B -m pytest -q -p no:cacheprovider` → **88 passed in 12.80 s** after the public KG integration. Includes strict/reference cases and consent, exclusions, profiling, ownership, contact-cap, positive-value and schema invariants across all 750 customers in both modes; also verifies a single `kg_bundle` call per assembled card.
- `python -m nba.build --out out/ --export out/static-data` → **750 customers in 2.53 s** (rate).
- `python -m nba.build --p-mode uplift --out out/uplift --no-report` → **750 customers in 2.27 s**.
- Fresh-runtime build tests produce byte-identical JSON. Separately reopened and validated all 750 CustomerCards, all 750 IndexRows and Summary; all 752 static-export files are byte-identical to their output counterparts.
- `out/test_report.md` exists (37,500 bytes), covers both modes and sensitivity. Rate: MG-100068 → P-EN-02/newsletter/Sie (+€18.9198), MG-100023 → P-AS-01/portal/Sie (+€7.1164), MG-100009 → P-SV-01 (+€84.9798). MG-100112 → generic P-EN-01/call (+€14.8703 rate / +€2.5398 uplift), following K11's current default.
- API tests cover real GET/filter/summary responses, approval/override/rejection persistence, consent withdrawal after a cached card, blocked sales/profiling/uneconomic overrides, tier restrictions and explicit-tuple approval conflicts.

**Not done / carried over:** CARDS' real profile/timeline/tone module is not yet on the merged main; placeholders are deliberately marked, and a test verifies automatic use of the public builders when available. Event replay/API revocation remains the optional KG stretch goal. No web code or `web/public/data` is committed; the generated export is kept in git-ignored `out/static-data`.

**Contract changes:** no JSON schema or public model-field changes. `ConsentItem.doi_at` is deferred as explained in Q-NBA-14; the actual DOI date is already present in the KG channel proof.

**Questions to consider:** Q-KG-11/12/13 answered in Q-NBA-14/15/16 above; Q-NBA-13 reconciled with the current README. Q-NBA-09 (historical signal/pitch comparison), Q-NBA-10 (legacy observations) and K11 still await team decisions; no default was changed.

**Issues / risks:** one dependency warning in the test environment: Starlette deprecates its installed httpx TestClient path. All tests pass; no dependency change was needed. Only the tested rules and the provided snapshot are covered by the invariant claims.

**Handoff:**
- Agent CARDS: merge main, then run `python -m nba.build --export web/public/data` in your own folder. `index.json` is an IndexRow array, `summary.json` contains source metadata, and `customers/<id>.json` is a CustomerCard. `chosen_tuple`, `p_accept`, `contact_cost`, `checklist_failed`, `sources`, `column_src` and `value_date` are populated. NO_ACTION keeps unavailable numeric scores null.
- Agent CARDS: export the three public builders from `nba.profile` (or the documented builder/tone/timeline modules). Restart the API/re-run the CLI after merging them; PROFILE-PENDING then disappears. The NBA layer retains KG's authoritative consent/channel/exclusion views.
- Agent KG: please review `evaluate_candidates`, the API's `checked_tuple`, and the two-mode reference report. `rank` intentionally sorts only its already-valued input; `evaluate_candidates` owns tier selection and the economic blocked rows.
- Delivery follows README §13: tested NBA-owned paths only, push `feat/nba`, then fast-forward main; no branch switches, force pushes or changes in other worktrees.

**Next session starts with:** merge CARDS' profile builder, re-run export/acceptance, then implement replay invalidation only when KG's events module is ready.

### Session 3 · 2026-10-26, checkpoint 18:13 Europe/Berlin · Codex (GPT-6) · branch feat/nba · commits e40c526/6e46313..(this commit)

**Goal:** complete the user's ordered P0/P1/P2 follow-up and optional replay preview, without editing another agent's paths.

**Done:**
- Fetched and merged main e40c526, then ran the unchanged suite: 128 passed. Later merged 6e46313 (KG-owned API docs and schema-export script), without editing those files.
- Q-KG-16: MG-100112 is strict in both modes: exact chosen tuple, generic origin, no personalised content, S3 explicitly blocked. Updated the reference-report expectation and closed K11/Q-NBA-11.
- Q-KG-14: `nba/engine/export.py` projects a compact static card. It retains the chosen tuple unchanged, the best ranked channel per other offer, all valuations and explicit nulls, and detailed checks/path for the chosen offer plus the first three distinct alternatives. Runtime/API still expose the full evaluated channel set. Static index counts match the projected card. Real export removes a stale mock manifest.
- Q-KG-15: translated NBA-owned internal reasons/evidence/checklist/API messages into English; German content templates and agent scripts remain unchanged.
- Q-CARDS-18: `Runtime.load()` now passes `profile_population(states)` to both KG and CARDS, so percentiles and highlights have the real population features. New acceptance tests require real timeline/products and text-based tone for MG-100325 and MG-100001; a broken profile import cannot pass silently.
- `nba/engine/impact.py` and default CLI reporting now write `out/impact_report.md` for both p modes: expected ΔCLV by offer/archetype, latest legacy proposal blockers, aligned expected-value comparisons, implemented-signal conversion cohorts and the checked/unchecked history audit.
- Q-NBA-09: recomputed the signal statistic with explicit offer support and snapshot-time limitations; the original 38/558 vs 27/1,280 statistic is not reproduced under S1–S13. No target predicate or historical signal state was invented.
- Q-NBA-10: retain checked and unchecked observations; expose the cohort comparison and keep current contact permission entirely in the KG gates. Added the decision as a config comment without changing model probabilities.
- Optional Q-KG-17: `api/replay.py` and POST `/api/replay?until=` return a read-only replay preview with fresh CustomerCards, event transitions and pending revocations. The snapshot and decision log are preserved. Invalid/offset-aware mock cutoffs are rejected rather than silently reinterpreted.

**Verified:**
- Full suite after the latest main merge: **137 passed in 28.02 s**; the existing Starlette/httpx deprecation warning remains the only warning.
- Strict acceptance was first checked separately: 2 passed under rate/uplift. Targeted export/acceptance/API checks: 20 passed; impact/export/acceptance checks: 17 passed; API including replay: 12 passed.
- `python -m nba.build --out out/ --export out/static-data` → **750 customers in 5.01 s**, including both-mode reference and impact reports. `--p-mode uplift --out out/uplift --export out/static-uplift --no-report` → **750 in 3.01 s**.
- Reopened and validated all 750 CustomerCards, 750 IndexRows and Summary in each export. Each mode contains 752 JSON files: **18,827,005 bytes rate / 18,803,600 bytes uplift**, below the decimal 20 MB target. Determinism tests compare bytes from two fresh runtimes, check null preservation and ensure projection leaves the chosen action and scores unchanged.
- Real profile highlights: 429 customers have 0, 243 have 1, 72 have 2 and 6 have 3. The representatives have populated products, non-empty timelines and tone method `text`.
- Impact report totals (model-based, mock data, not causal uplift): **€9,755.91 rate / €6,519.52 uplift** expected incremental ten-year CLV. Latest legacy proposals: 750, of which 658 delivered; 622 blocked in rate / 637 in uplift, with 621 non-economic gate blockers in either mode. Aligned comparisons exclude 73 missing legacy valuations instead of treating them as zero.
- Implemented signal comparison: 9/82 vs 12/930 among 1,012 treated observations; 1,010 observations without implemented offer triggers excluded. Standardised common-offer rates: 7.15% vs 1.40% (5.09×), descriptive and subject to snapshot timing leakage.
- API replay test: 118 customers affected; fresh cards and rule-based revocations returned; original state revisions and decision-log files unchanged. Live OpenAPI includes `/api/replay`; scratch copy verified in `out/openapi.json`.

**Contract changes:** none. Every static file remains valid against the existing models/schemas; no model fields were added or removed. Static candidates are a smaller view of the full runtime data.

**Not done / carried over:** production ingestion/persistent replay-state promotion is outside this preview endpoint. Q-KG-19 (CORS, response models, NO_ACTION checklist) was not part of this request. KG-owned static API docs need the Q-NBA-21 refresh after delivery.

**Questions to consider:** Q-KG-14/15/16/17 answered above; Q-NBA-09/10/11 closed. The earlier pitch statistic must not be presented as a result of the current implemented signals.

**Issues / risks:** need-first history comparison uses snapshot signal presence, not at-send facts; the report names that limitation and never calls the result causal uplift. Static mode keeps one channel per offer; use the API for all evaluated channel variants.

**Handoff:**
- Agent CARDS: merge main and run `python -m nba.build --export web/public/data` in your own folder. Export is below 20 MB, real profiles/highlights are included, and the mock manifest is removed automatically. No web/public/data changes are committed by NBA.
- Agent KG: review `out/impact_report.md` for the pitch and refresh the API docs/OpenAPI (Q-NBA-21). The preview endpoint follows replay_demo.py, exposes `preview_only`, and never changes active snapshot approvals.
- Reports and generated data remain in git-ignored `out/`; the report builder and its tests are committed so both reports reproduce from the same data/config.

**Next session starts with:** final UI integration using the reduced export and the updated API reference; further model/policy changes only after a team decision.

### Session 4 (by Agent KG for Agent NBA) · 2026-10-26 18:00–19:40 Europe/Berlin · Claude Code (Opus) · branch feat/kg

The user asked Agent KG to do Agent NBA's part of the Rule Center and the open NBA questions. Agent NBA: merge `main` once this lands, and read `docs/rule-center.md` §5–§6 and `docs/nba-guide.md`.

**Done:**
- Rule Center tier 2 (`config/nba.yaml business_rules`, `nba/engine/rulecenter.py`):
  - held-back actions (`chosen.deferred_until`);
  - B-09 capacity in `Runtime.capacity_overflow`;
  - custom rules;
  - the rule report.
- Registry, what-if, legacy audit and the API endpoints (`docs/api.md` §3.6).
- Q-KG-19: CORS, response models, NO_ACTION checklist.
- Q-KG-23: optional `fcntl`, pydantic `~=2.14.1`.
- Q-KG-24:
  - `load_policy(tables=…)`;
  - `--asof` through `resolve_eval_time`;
  - the P-EN-02 window from `policy.params`;
  - a data gate in `nba.build`.

**Contract changes** (README §5.4):
- `CustomerCard.rules` (`RuleReport`);
- `Chosen` / `Candidate` / `IndexRow.deferred_until`;
- `Blocked.rule_center_id` / `until`;
- `Versions.rules`;
- RuleId `BUSINESS-RULE`;
- new models `RulesFile`, `RuleNode`, `RuleChange`, `RuleCreate`, `ContactCounter`, `RuleResult`;
- new optional fields are omitted from JSON while unset;
- schemas in `docs/schema/` (+ `rules`, `rule_change`, `rule_create`).

**Behaviour changes to know:**
- `assemble` uses `kg_bundle(apply_cap=False)`: capped customers now get a waiting action instead of NO_ACTION.
- B-08 removes calls under €10 ΔCLV: MG-100112 has no action in uplift mode.
- Static export: waiting cards keep the action plus one fallback, and only tier 2 rule outcomes.
- Acceptance tests were updated accordingly.

