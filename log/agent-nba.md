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
| Q-NBA-09 | The need-first pitch statistic (6.8% vs 2.1% conversion with vs without the target signal, ≈ 2.3× within offers) is descriptive mock data. Re-check it once signals are implemented, and only pitch it with that label | Credibility with the jury | Agent NBA with Agent KG | open | — |
| Q-NBA-10 | Should the 333 legacy rows with `consent_checked = 0` be excluded when estimating p? (They are illegal contacts in the mock, but still real conversion observations) | Changes p for offers sent mostly by the legacy engine | Team | open | — |
| Q-NBA-11 | K11: allow generic offers by phone/SMS? MG-100112's generic StromAktiv call is +€14.8 (rate) / +€2.6 (uplift) | MG-100112 outcome | Team | open | — |
| Q-NBA-12 | K12: profiled customers fall back to generic offers only when no signal/service tuple has ΔCLV > 0 | Coverage vs need-first | Team | decided-default | Fallback on (`generic.fallback_for_profiled: true`) |
| Q-NBA-13 | `kg/policy.yaml` has `P-EN-03.requires: []`, while the earlier README §6.4 required active electricity | Reconcile the holding requirement without duplicating KG gates | Agent KG | closed | After merging 20f066f, README §6.4 also has no active-electricity requirement for P-EN-03; NBA follows the current policy |
| Q-NBA-14 | Answer Q-KG-11: correct Order evidence comments; add optional `ConsentItem.doi_at`? | Consent proof and a stable interface for CARDS | Agent KG / CARDS | decided-default | Comments corrected to `order:SO-1` and S1–S13. Defer the optional field: the KG channel reason already includes the actual DOI date; no schema change is needed for the current UI. Revisit if CARDS needs a structured date |
| Q-NBA-15 | Answer Q-KG-12: use public `check_tuple` in API and legacy comparison | One source of truth for gates | Agent KG | closed | Implemented after merging 20f066f; every legacy blocker includes the public check's IDs, and override 409 uses its IDs and reasons |
| Q-NBA-16 | Answer Q-KG-13: tiers and `ECON-NONPOSITIVE` evidence | Need-first arbitration and MG-100023 | Agent KG | closed | `evaluate_candidates()` evaluates signal/service first, enables generic fallback according to config, and records non-positive tuples with `counterfactual_delta_clv`; both-mode tests cover all 750 customers |

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
