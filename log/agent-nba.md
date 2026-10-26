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
| Q-NBA-13 | `kg/policy.yaml` has `P-EN-03.requires: []`, while README §6.4 requires active electricity. Please reconcile in KG; NBA calls the KG gates rather than duplicating them | Prevents accepting a heat-pump offer without its documented holding requirement | Agent KG | open | Found 26 Oct; not changed in NBA-owned paths |

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
