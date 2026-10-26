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
| Q-KG-06 | S4 (price guarantee < 90 days, active electricity) counts 116, while the churn driver "price guarantee ends <90d" appears for 145 customers. Reconcile: gas contracts? evaluation date? | P-EN-02 eligibility and its value (driver removal) | Agent KG (self), then NBA | answered | KG audit 26 Oct: S4 = 143 (README), driver = 145. The 2 extra customers are MG-100087 (guarantee on EN-500096 ends 2026-11-02, but the contract is `cancellation_pending`, and S4 needs `active`) and MG-100335 (EN-500409 active, ends 2026-12-29 = exactly 90 days; S4 uses `< 90`, the driver evidently `≤ 90`). The code matches README; no change needed |
| Q-KG-07 | Event `ticket_updated` references `TK-open-complaint`, which is not in the snapshot. Treat it as an orphan with a conservative customer-level complaint flag? | Exclusion for MG-100004 during event replay (stretch) | Team | answered | Orphan ticket kept as a conservative open placeholder with provenance (nba/kg/events.py, 26 Oct) |
| Q-KG-08 | P-EN-04 (GasAktiv) and P-IN-01 (Internet) are never generated (`DATA-MISSING`). Confirm this is acceptable for the hidden reference customers | Catalog coverage | MAINGAU mentor | decided-default | — |
| Q-KG-09 | The marketing archetype draft (5 profiles) does not match the data (README K13). Use the rule-based archetypes in README §6.13 | UI must not show wrong ranges | — | closed | Archetypes A0–A5 with verified counts (26 Oct) |
| Q-KG-10 | Generic offers by phone/SMS: MG-100112's generic StromAktiv call is +€14.8 (rate) / +€2.6 (uplift), not negative as D1 assumed (README K11) | Outcome of MG-100112 and of every no-profiling customer whose only channel is a call | Team | answered | Team decided 26 Oct: allow; MG-100112 → generic StromAktiv by phone (README §6.12, §9, K11) |
| Q-KG-11 | Agent NBA: please (a) change the evidence example in `nba/contracts.py` Signal.evidence from `order:SO-1#2` to `order:SO-1` (Order IDs are order_id now), and (b) consider an optional `ConsentItem.doi_at` so the consent-proof drawer can show the real double opt-in date (KG currently puts it only in the channel reason text) | Contract comment is wrong; consent proof in the UI | Agent NBA | open | — |
| Q-KG-12 | Agent NBA: use `nba.kg.rules.check_tuple(state, offer_id, channel, policy)` for the override 409 and for `legacy_comparison.blocked_now_by`; do not re-implement gates | One source of truth for hard rules | Agent NBA | open | — |
| Q-KG-13 | Agent NBA: `rank()` (34a9f5c) drops ΔCLV ≤ 0 silently and ranks all origins together. README §6.12 needs (a) dropped tuples added to `blocked` as `ECON-NONPOSITIVE` and (b) the tiers: signal/service tuples first; generic tuples for profiled customers only when no signal/service tuple has ΔCLV > 0 (`generic.fallback_for_profiled`). Without (b), MG-100023 would get a generic StromWärme (about +€24) instead of P-AS-01 | Team test MG-100023 → P-AS-01; need-first ranking | Agent NBA | open | — |
| Q-KG-14 | Agent NBA: the export is 34 MB (`indent=2`) and still 23 MB compact, above the ~20 MB budget for `web/public/data` (README §13.2). Write compact JSON and trim per-candidate duplication: only the top 5 tuples per customer get the full `checks`/`path`, or drop channel duplicates of the same offer | Vercel static deploy and UI load time | Agent NBA | closed | Resolved by Agent NBA in f8090e8 (reduced static export, ~19 MB) |
| Q-KG-15 | Agent NBA: internal reason lines mix languages: the NO_ACTION and ECON-NONPOSITIVE reasons are German ("Keine zulässige Aktion…", "erwartete ΔCLV"), the rest is English. README §0: UI text may be English or German, customer content German. Pick one language for internal reasons, English recommended | Consistent UI and pitch | Agent NBA | closed | Resolved by Agent NBA in f8090e8 (English internal texts) |
| Q-KG-16 | Agent NBA: K11 is decided. Make MG-100112 strict in `tests/test_acceptance.py` under both p modes (chosen `P-EN-01|outbound_call|sie`, `origin = generic`, content not personalised, S3 blocked by CONSENT-PROFILING), and close Q-NBA-11 in your log | README §9 strict list | Agent NBA | closed | Resolved by Agent NBA in f8090e8 (MG-100112 strict) |
| Q-KG-17 | Agent NBA (optional stretch): `POST /api/replay?until=` can call `nba.kg.events.replay(runtime.states, load_events(), policy, pop, until, pending=<chosen tuples>)` and then `assemble()` on the affected customers, as in `scripts/replay_demo.py` | Live deep-dive B demo in the API | Agent NBA | closed | Resolved by Agent NBA in f8090e8 (POST /api/replay, preview only) |
| Q-KG-18 | Agent CARDS (optional): show deep dive B in the UI from `out/replay/timeline.json` (copy into `web/public/data/replay/`): a "What changed since 30.09" panel with event, delay, KG effect and pending card status (REVOKED + rule). Demo customers MG-100125 (card revoked by a new ticket), MG-100465 (cancellation 16.9 h late → P1), MG-100009 (ticket + annoyed flag), MG-100003 (consent withdrawn) | Deep dive B is the challenge's chosen deep dive | Agent CARDS | open | — |
| Q-KG-19 | Agent NBA (API, from writing docs/api.md): (a) no CORS middleware, so a browser UI on another origin cannot call it; add `CORSMiddleware` for the Vite dev origin, or document the proxy (docs/api.md uses the proxy); (b) the routes have no `response_model`, so `docs/openapi.json` does not describe responses; (c) `NO_ACTION` cards report all 6 checklist items as failed, which the worklist shows as 6 failures; report an empty `checklist_failed` or a dedicated NO_ACTION state | UI integration | Agent NBA | closed | Done by Agent KG at the user's request (26 Oct): CORS (MAINGAU_CORS_ORIGINS), response models, NO_ACTION has an empty checklist |
| Q-KG-20 | README §6.1 puts a contact-cost column in `kg/policy.yaml` (owner Agent KG), but the policy has no cost; costs come from the workbook `value_assumptions` (read by Agent NBA) and match §6.7. Either add `contact_cost_eur` to the policy channels or change §6.1 to name `value_assumptions` as the source | One source of truth for contact cost (audit test `test_policy_channels_carry_contact_cost`) | Team (README owner) | answered | Decided 26 Oct: value_assumptions is the single source; README §6.1 updated; audit test now checks there is no duplicate |
| Q-KG-21 | README §6.4 says P-MO-01 requires an active energy contract, but P-MO-01 is generic-only and D1/§6.12 say a generic tuple only drops owned products. So the requirement never applies, and the policy leaves it out. Drop it from §6.4, or apply it to generic P-MO-01 too (it would remove P-MO-01 for Autostrom-only customers) | P-MO-01 audience; `check_tuple` overrides | Team | answered | Decided 26 Oct: P-MO-01 has no requirement (generic, D1); README §6.4 + audit oracle updated |
| Q-KG-22 | README §6.11 does not list the ontology's `Archetype` node and `INSTANCE_OF` / `IN_ARCHETYPE` edges, nor the `GENERIC_OFFER` edge used in generic explanation paths. Document them in §6.11 (and add `GENERIC_OFFER` to `kg/ontology.yaml`) or remove them | Ontology = README contract (audit tests `test_ontology_*`, `test_path_edges_are_ontology_edge_types`) | Agent KG | closed | README §6.11 + ontology document Archetype, INSTANCE_OF, IN_ARCHETYPE, GENERIC_OFFER (26 Oct) |
| Q-KG-23 | Agent NBA: on Windows with fresh installs, (a) `api/app.py` imports `fcntl` (POSIX only), so `tests/test_engine_api.py` cannot be collected; (b) `tests/test_engine_build.py::test_all_four_schema_files_match_the_models` fails with pydantic 2.14.1 (`requirements.txt` has `pydantic>=2.5`): pin pydantic or regenerate `docs/schema/` | Whole-suite `pytest -q` for every team member | Agent NBA | closed | Done by Agent KG at the user's request (26 Oct): fcntl optional (Windows), pydantic ~=2.14.1 |
| Q-KG-24 | Agent NBA (from the A–D review): (a) `nba/engine/runtime.py` should call `load_policy(tables=tables)` (KG now infers the workbook from the catalog, but explicit is safer) and send `--asof` through `nba.state.resolve_eval_time` (timezone offsets); (b) `content.py` / `assemble.py` hard-code `< 90` days for the P-EN-02 date and note: use the S4 hit (`P.price_guarantee_ending(state, policy.params)`) or `policy.params['price_guarantee_window_days']`; (c) optionally gate `nba.build` with `nba.kg.intake.validate_workbook` (exit on ERROR) | New snapshots and tunable thresholds (README §6.15) | Agent NBA | closed | Done by Agent KG at the user's request (26 Oct): load_policy(tables=…), --asof via resolve_eval_time, P-EN-02 window from policy.params, nba.build data gate (--skip-validation) |
| Q-KG-25 | Rule Center R1: do newsletters count toward B-02 (2 contacts / 30 days)? As in the spec: 336 of 549 marketing decisions deferred (204 until 03.10), including test customers MG-100023/100001/100267/100102/100051. Recommended: newsletters only in B-01, with a per-rule `sources` setting | docs/rule-center.md §9 | User / mentor | answered | User: build with defaults (26 Oct). R1 = newsletters only in B-01; switch: config/kg.yaml contact_cap.sources (+newsletter changes 328 decisions) |
| Q-KG-26 | Rule Center R2–R5: C-07 stricter scope (recommended: keep, same result today); B-05 test MG-100051 (block ended 23.09; test at 2026-09-01); who builds the page (`web/` = CARDS, busy); B-08 €10 drops 9 of 12 chosen calls | docs/rule-center.md §9 | User / mentor | answered | Defaults applied (26 Oct): C-07 stays stricter; B-05 tested at 01.09; page on temporary branch feat/rule-card; B-08 €10 |

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

### Session 2 · 2026-10-26 15:00–16:05 Europe/Berlin · Claude Code (Opus) · branch main → feat/kg · commits fbf9a54, 30dc4c9, (this commit)

**Goal:** implement the KG (PLAN_KG steps 2–7), review Agent CARDS' first questions, and write the git rules after a branch incident.

**Done:**
- `kg/ontology.yaml`, `kg/policy.yaml`, and `nba/kg/`: `policy`, `predicates`, `signals`, `rules`, `segments`, `paths`, `quality`, `graph`, plus an `events` stub.
- `scripts/kg_report.py`; 25 tests in `tests/test_kg_*.py` plus `tests/conftest.py`.
- Contracts: `IndexRow.contact_cost` and `checklist_failed`; `Summary.sources`, `column_src` and `value_date`. These answer Q-CARDS-11 and Q-CARDS-12, done on Agent NBA's behalf because NBA had not started.
- Agreed with Q-CARDS-13: in static mode, overrides are limited to tuples in `candidates`. Agreed with Q-CARDS-14: the sensitivity hint stays hidden.
- README §13 and prompt sections on git/commit rules; one worktree per agent.

**Verified:**
- `pytest -q`: 25 passed.
- Signal, archetype, tier and flag counts match README §6.3 and §6.13.
- `scripts/kg_report.py` runs all 750 customers in 0.48 s.
- Graph export: 10,781 nodes and 17,185 edges.

**Contract changes:** the `IndexRow` and `Summary` fields above; README §5.4 and `docs/schema/` regenerated (commit 30dc4c9).

**Issues / risks:**
- Agent CARDS switched the shared folder `MAINGAU` to `feat/cards`. My contract commit 30dc4c9 was created there.
- 30dc4c9 sat directly on `origin/main`, so it was fast-forwarded with `git push origin 30dc4c9:refs/heads/main` and `git branch -f main 30dc4c9`, without switching branches. Agent CARDS' untracked `web/` was not touched.
- I moved to the worktree `../MAINGAU-kg` on `feat/kg`. Agent NBA has `../MAINGAU-nba` on `feat/nba`.
- My commit fbf9a54 also contained Agent CARDS' uncommitted log entry, because of `git add -A` in the shared folder. Its content was kept unchanged. The new §13 forbids `git add -A`.

**Handoff:**
- All agents: read README §13 before the next commit.
- Agent NBA: contracts now include the worklist fields above.

**Next session starts with:** fix the findings of the independent KG review (running), then K11 once the team decides.

### Session 3 · 2026-10-26 16:10–17:10 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits ebf5ab0..(this commit)

**Goal:** fix the confirmed findings of the independent KG review. The review was a workflow of 4 reviewers plus 4 adversarial verifiers: 17 findings confirmed (11 distinct issues), 3 refuted.

**Done:**
- `nba/data.py`: the cache key now includes a parser fingerprint (sha256 of `data.py` + the pandas version), and the pickle is written atomically. A stale cache had served NaN and string numbers (high severity).
- `nba/kg/rules.py`:
  - EXCL-AUTOSTROM-CANCELLED stays active whatever the K6 scope; `blocks_offer()` applies the scope per offer, so `e_mobility` no longer leaks P-AS-01.
  - Per-channel `blocked` rows (`offer_id = "*"`, channel set, CONSENT-CHANNEL or CHANNEL-AVAILABLE).
  - HOLDING-PRECONDITION rows for owned generic offers.
  - S10 is reported as ignored without profiling consent.
  - The real double opt-in date appears in the newsletter reason.
  - New `check_tuple()` for overrides and the legacy comparison.
- `nba/kg/predicates.py`:
  - non-string `churn_drivers` is handled safely;
  - the S11 detail is now factual (MG-100087: "no active MAINGAU electricity contract (EN-500096 is cancellation_pending)").
- `nba/kg/graph.py`:
  - channel and consent-type nodes are namespaced (no ID collision, no self-loop);
  - Order nodes are keyed by `order_id`, so S3 evidence resolves;
  - S10 evidence gets a Campaign node;
  - HAS_SESSION edges are emitted;
  - control rows use HELD_OUT instead of RECEIVED;
  - the export links IN_ARCHETYPE and drops unused archetype nodes.
- `nba/kg/paths.py`: the P-SV-01 offer node has no invalid `product:service` `ui_ref`.
- Ontology, README §5.4, §5.6 and §6.11, and PLAN_KG synced. 12 new regression tests.

**Verified:**
- `pytest -q`: 37 passed.
- `scripts/kg_report.py --graph`: 10,784 nodes and 17,989 edges, 0 orphan nodes, 0 dangling edges; RECEIVED 2,022 (= delivered), HELD_OUT 248 (= control), IN_ARCHETYPE 750.
- Tuple counts unchanged (808 signal / 69 service / 6,343 generic): the fixes change reporting and the K6 alternative, not today's decisions.

**Refuted findings (kept as is):**
- The "no consented channel" row is not added when an exclusion is already active.
- No data-quality flag for the `TK-open-complaint` event at T0. It only matters during replay.
- `portal_sessions.session_start` and `mobile_contracts.min_term_end` stay strings, as README §5.1 specifies; consumers parse them.

**Contract changes:** none in `nba/contracts.py`. Requests to Agent NBA: Q-KG-11 and Q-KG-12.

**Issues / risks:** the shared folder `MAINGAU` still holds the stale pickle from 15:12. The new cache key ignores it automatically, so nothing needs deleting.

**Next session starts with:** event replay (deep dive B) in `nba/kg/events.py`, unless the team re-prioritises. Then review Agent NBA's and Agent CARDS' first deliveries.


### Session 4 · 2026-10-26 17:15–17:35 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 99242f4..(this commit)

**Goal:** speed up Agent CARDS and Agent NBA in parallel without touching their paths. The user asked for parallel help because CARDS is slow.

**Done:**
- First plan: take over `nba/profile/` from CARDS. Dropped it, because a directory listing (files not opened) of the CARDS folder showed CARDS had already written 13 files / about 925 lines there at 15:46–15:57, uncommitted. Ownership is unchanged.
- `nba/kg/bundle.py`: `kg_bundle()` returns every KG output for one customer in one call; also `source_info()` and `COLUMN_SRC` (answers Q-CARDS-12 on the data side).
- `scripts/export_preview.py`: real-data preview for the UI:
  - `index.json`: 750 `IndexRow`s with real triage, ranked P1→P5 by score; `chosen_offer` = "PENDING";
  - `summary.json`: counts, sources, `column_src`, `value_date`;
  - `kg/<id>.json`: the KG part of each card;
  - every object is pydantic-validated.
- README §5.6 and §8, plus both prompts, point to it.

**Verified:**
- `pytest -q`: 40 passed.
- Preview for 750 customers in 0.6 s: 20 MB in total (`index.json` 436 KB, about 25 KB per customer file).
- Top of the worklist: MG-100190, MG-100087, MG-100405 (P1, A4).

**Handoff:**
- Agent CARDS: run `scripts/export_preview.py --out web/public/data` after merging `origin/main`; mock only valuation, chosen and content.
- Agent NBA: use `kg_bundle()` and `check_tuple()` in `assemble` and the API.

**Next session starts with:** review `feat/nba` (pushed at 34a9f5c), then event replay.

### Session 5 · 2026-10-26 17:35–17:45 Europe/Berlin · Claude Code (Opus) · branch feat/kg · review only

**Goal:** review Agent NBA's first push (`origin/feat/nba` 34a9f5c), as the reviewer role in PLAN_KG §10.

**Done:**
- Ran the branch in a detached scratch worktree, outside `MAINGAU-nba`, and removed it afterwards.
- Read `value.py`, `propensity.py`, `rank.py`, `churn.py` and `config/nba.yaml` against README §6.5–§6.6.

**Verified:**
- `pytest -q` on 34a9f5c: 43 passed.
- Correct against the README:
  - model basis (`clv_now_model`);
  - one-off margin counted once;
  - P-EN-02 removes only the 0.10 driver;
  - P-SV-01 keeps 0.95 for cancellation pending and subtracts €15;
  - reject penalty only for open complaint or dunning;
  - backoff L3→L0 with `n_min` 30;
  - rate mode shrinks with 0.034·30 (raw 3.4% at L0);
  - uplift uses the offer's own control only when n ≥ 30;
  - confidence high/medium only at L3;
  - unknown churn drivers raise instead of guessing.

**Issues / risks:**
- Q-KG-13: tiers and `ECON-NONPOSITIVE` rows are missing (expected in `assemble`).
- The branch is based on 30dc4c9. It must merge `origin/main` (f23a28f) to get `kg_bundle`, `check_tuple`, the cache fix and the K6 fix.

**Next session starts with:** event replay (`nba/kg/events.py`, deep dive B).



### Session 6 · 2026-10-26 17:50–18:05 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 20f066f..(this commit)

**Goal:** review Agent NBA's delivery on main (ef82704) and report KG status.

**Done:**
- Fast-forwarded `feat/kg` to `origin/main` (ef82704).
- Ran `nba.build` for all 750 customers into the scratchpad, plus an independent checker (my own script, not NBA's tests).

**Verified:**
- `pytest -q` on main: 88 passed (KG 40 + NBA 48).
- `nba.build`: 750 cards in 2.3 s; two runs give identical hashes (deterministic); every card validates against `CustomerCard`.
- Independent checker over all 750 customers, 0 violations:
  - chosen ΔCLV > 0;
  - the chosen tuple is among the candidates and `check_tuple` returns [] for it;
  - no personalised tuple or content without profiling;
  - P-SV-01 content has no product words;
  - §6.12 tiers respected (no profiled customer gets a generic offer while a signal/service tuple has ΔCLV > 0).
- 238 ECON-NONPOSITIVE rows; 154 NO_ACTION.
- Chosen offers: P-MO-01 201, P-EN-01 152, P-SL-01 95, P-EN-02 60, P-SV-01 47, P-MO-03 16, P-SL-02 8, P-EN-03 6, P-AS-01 4, P-SL-03 4, P-EN-05 3. Σ expected ΔCLV €9,798 (model-based, mock).
- Test customers match README §9:
  - MG-100023 → P-AS-01 (+€7.12, p 1.6%);
  - MG-100009 / MG-100659 / MG-100096 / MG-100186 / MG-100004 → P-SV-01;
  - MG-100035 / MG-100087 → NO_ACTION;
  - MG-100012 → generic P-MO-01;
  - MG-100051 / MG-100060 → P-EN-03;
  - MG-100068 and MG-100325 → P-EN-02;
  - MG-100112 → generic P-EN-01 by phone (+€14.87, K11 still open).
- `out/test_report.md` covers both p modes.

**Issues / risks:**
- The profile is still a placeholder: tone is the default, the timeline and product items are empty. It is waiting for Agent CARDS' `nba/profile`, which is not pushed (no `feat/cards` on origin).
- Export size: Q-KG-14. Mixed-language reasons: Q-KG-15.

**Next session starts with:** event replay (deep dive B), then review `nba/profile` when CARDS pushes it.

### Session 7 · 2026-10-26 18:10–18:15 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits d1914ed..(this commit)

**Goal:** record the team decisions: K11 resolved, the Customer 360 UI proposal dropped.

**Done:**
- README §6.12, §9 (MG-100112 strict under both modes) and §10 K11 updated; `config/kg.yaml` comment updated.
- Q-KG-10 answered; Q-KG-16 opened for Agent NBA.
- The Customer 360 layout proposal (A/B/C) was dropped by the team. Agent CARDS keeps its own design per `prompts/agent-cards.md`.

**Verified:** `nba.build --customers MG-100112` gives `P-EN-01|outbound_call|sie` in both modes: rate +€14.87 at p 3.41%, uplift +€2.54 at p 1.40%. Not personalised; S3 blocked by CONSENT-PROFILING.

**Next session starts with:** event replay (deep dive B); review `nba/profile` and `web/` when Agent CARDS pushes.

### Session 8 · 2026-10-26 18:20–19:05 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 8ecc8ce..(this commit)

**Goal:** deep dive B, event replay (PLAN_KG step 9).

**Done:**
- `nba/kg/events.py`:
  - ingest-order replay;
  - per-fact-key clocks (consent, contract status, dunning, ticket), with `stale` for older facts;
  - `effective_date` for gas deregistration (S1 now; gas stays active until 31.10);
  - orphan ticket → conservative open placeholder with provenance;
  - informational events logged without fact changes; duplicates → `already_applied`;
  - snapshot states never mutated;
  - per-transition KG diff (signals, exclusions, tier, profiling, flags);
  - pending-card re-check with `check_tuple`, plus CONSENT-PROFILING for personalised cards.
- `nba/kg/predicates.py`: the S1 detail shows the effective date when it is in the future.
- `scripts/replay_demo.py`:
  - T0 cards from Agent NBA's engine → replay → re-decision with `assemble()`;
  - verdicts REVOKED / SUPERSEDED / UNCHANGED;
  - three freshness measures;
  - output in `out/replay_report.md` and `out/replay/timeline.json`.
- README §5.6, new §6.14, §7.1 and §8; PLAN_KG step 9.

**Verified:**
- `pytest -q`: 98 passed, with 10 new replay tests:
  - online order for MG-100003 (newsletter still granted at 10:14:07);
  - the late cancellation is only known after 02.10 02:11:06;
  - effective date (gas active on 03.10, terminated on 01.11);
  - the orphan ticket;
  - the MG-100009 story;
  - a stale event is ignored; a duplicate is applied once;
  - pending revocation.
- `scripts/replay_demo.py`: 635 events in 0.44 s (about 0.7 ms per event); 118 customers affected; 29 pending cards revoked (28 EXCL-OPEN-TICKET, 1 EXCL-CANCELLATION), 5 superseded, 84 unchanged.

**Demo stories:**
- MG-100125: T0 card Autostrom by newsletter is REVOKED at 01.10 11:31 by a new open ticket; S1 arrives 14.7 h late with effective date 31.10; the re-decision is NO_ACTION while the ticket is open.
- MG-100465: cancellation 16.9 h late → EXCL-CANCELLATION, P5 → P1 (no pending card at T0).
- MG-100009: 4th failed charge → ticket → "annoyed_before" flag; the service card stays valid.
- MG-100003: profiling and then newsletter withdrawn; the card stays valid because the T0 card was already generic (no signals).

**Issues / risks:**
- The NO_ACTION reason lines are German (Q-KG-15).
- MG-100003 is a weaker demo than planned, because its T0 card was already generic. MG-100125 is the strongest revocation story.

**Handoff:** Q-KG-17 (Agent NBA, optional API replay) and Q-KG-18 (Agent CARDS, optional "What changed" panel).

**Next session starts with:** review `nba/profile` and `web/` when Agent CARDS pushes; reconcile S4 143 vs 145 (Q-KG-06).

### Session 9 · 2026-10-26 19:20–19:40 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits e40c526..(this commit)

**Goal:** API documentation for the UI (user request).

**Done:**
- `docs/api.md`: modes (static vs API), run instructions, types, all 4 endpoints with query parameters, real request/response examples, decision semantics, the error and rule-ID table with UI labels, static-mode mapping, a TypeScript client and known limitations.
- `scripts/export_schema.py` now also writes `docs/openapi.json`. README tree updated.

**Verified:** every example in `docs/api.md` comes from real calls through FastAPI's TestClient against `create_app(out_dir=<scratch>)` on main e40c526, without touching the repo's `out/`:
- the worklist filters;
- the card for MG-100068;
- the summary;
- 404;
- approve and override (200);
- 409 for MG-100112 Autostrom by phone, MG-100068 by phone and approving MG-100035 (NO_ACTION);
- 422 for a reject without reason and for an invalid action.

Cold start 1.8 s; warm list call 0.75 s. `pytest -q`: 128 passed.

**Issues / risks:** Q-KG-19 (CORS, response models, NO_ACTION checklist). The UI code was not touched; Agent CARDS' folder is being edited by a team member.

## 2026-10-26 17:11 · KG audit session · test/kg-audit @ 6e46313

Claude Code (Opus) on Windows, in the user's checkout `E:\Projects\maingau`. On the user's request it worked on a new branch, `test/kg-audit`, created from `origin/main` 6e46313, instead of `../MAINGAU-kg` on `feat/kg`. `origin/feat/kg` and `origin/main` were both at 6e46313, so the audited code is the same. It used its own `.venv` (Python 3.12.7, pandas 3.1.0, pydantic 2.14.1), because the macOS venv path does not exist on this machine. No code under `nba/`, `kg/`, `config/`, `scripts/` or `README.md` was changed.

**Goal:** check that the ontology, KG, signals, gates and triage behave as README.md specifies; prove it with automated tests against an independent oracle; turn every gap into a next step.

**Done:**
- `tests/kg_audit_oracle.py`: an independent oracle. It reads the raw xlsx and JSONL with pandas and never imports `nba.kg`, `nba.data` or `nba.state`. It recomputes holdings, consent and channels, exclusions, contacts, S1–S13, the full §6.12 tuple set (offer, channel, origin), archetypes, tiers, urgency score, flags, Autostrom K4 counts and the Q-KG-06 gap.
- Tests per file (189 total):

  | File | Tests |
  |---|---|
  | `test_kg_audit_policy.py` | 46 |
  | `test_kg_audit_loading.py` | 13 |
  | `test_kg_audit_signals.py` | 34 |
  | `test_kg_audit_gates.py` | 21 |
  | `test_kg_audit_customers.py` | 28 (13 premise checks + 15 KG checks) |
  | `test_kg_audit_triage.py` | 19 |
  | `test_kg_audit_graph.py` | 10 |
  | `test_kg_audit_invariants.py` | 12 |
  | `test_kg_audit_events.py` | 6 (stretch; `events.py` exists) |

**Verified:** `.venv/Scripts/python -m pytest tests/ -q -rA --continue-on-collection-errors` → 294 passed, 12 failed, 1 collection error.
- **New audit tests:** 178 passed, 11 failed, 0 skipped.

  | File | Passed | Failed |
  |---|---|---|
  | policy | 41 | 5 |
  | loading | 13 | 0 |
  | signals | 33 | 1 |
  | gates | 19 | 2 |
  | customers | 28 | 0 |
  | triage | 19 | 0 |
  | graph | 8 | 2 |
  | invariants | 11 | 1 |
  | events | 6 | 0 |

- **Pre-existing, unchanged before/after:** 116 passed, 1 failed (`test_engine_build.py::test_all_four_schema_files_match_the_models`), 1 collection error (`test_engine_api.py`, `fcntl`). Both are Agent NBA paths (Q-KG-23). All existing `test_kg_*.py` tests pass.
- **What the oracle confirms, code = oracle = README:**
  - S1–S13 customer **sets** (not just counts) match for all 13 signals: 12/2/16/143/11/80/66/33/48/33/161/29/39. S2 = {MG-100009, MG-100659}.
  - The full allowed-tuple set (offer, channel, origin) matches for **all 750 customers**: service, signal and generic, including exclusions, contact cap, profiling (D1), holdings and K11 phone/SMS generics.
  - Per-offer gate order (exclusion → holding) matches for every profiled customer. Customer-wide `*` rows (exclusions, cap, blocked channels with the right rule) match for all 750. `channel_view` matches for all 750.
  - `check_tuple` returns `[]` for every generated tuple and the same rule for every blocked one.
  - Archetypes A4 75, A1 33, A3 201, A5 50, A2 342, A0 49; tiers P1 53, P2 62, P3 95, P4 261, P5 279 (per customer, not just counts).
  - All 9 flag sets match the README counts, including `no_profiling` 289 and `data_inconsistent` 71. 154 outliers; `top_clv` is never an outlier. p90 = 1,023 (index 675; numpy's linear p90 is 1,017.6, with the same 75 customers).
  - `urgency_score` equals the formula for all 750.
  - Loading: 23 sheets, 750 unique IDs, bool and naive-datetime typing, None for empty, 25 guests absent from states. 647 lines → 635 events, in exact oracle order. Revision stable.
  - `contacts(…, 30)` matches for all 750, and the window is half-open. `owns()` matches for 750 × 9 offers. Autostrom 159 / 161 / 127, with no literal 150 in the KG code.
  - Graph: only ontology types with valid endpoints; RECEIVED = delivered and HELD_OUT = control for all 750; deterministic.
  - Every explanation path alternates node/edge, has the §4.2 C3 shape (signal/service/generic), uses policy edges that exist, and has valid `ui_ref`s.
  - `kg_bundle` validates against `nba/contracts.py` for all 750 and is byte-identical across two runs. `scripts/kg_report.py` counts equal the oracle.
- **§9 test customers:** all 13 premises hold in the raw data, and all KG-level expectations pass (MG-100051, -060, -096, -186, -068, -023, -112, -009, -659, -035, -087, -004, -012; representatives MG-100325 A1, MG-100001 A2).
- **Events:** ingest order; 12 duplicate lines applied once (identical revisions with and without dedup); MG-100003 consents; MG-100465 EXCL-CANCELLATION; MG-100125 S1 with `payload.effective_date` 2026-10-31; MG-100009 feedback + `annoyed_before`.
- **Premise note:** MG-100465 has no consented marketing channel at T0, so it never had a sales tuple to remove. The test instead checks that `check_tuple` gains EXCL-CANCELLATION for every sales offer.
- **Q-KG-06:** the 2 customers with the driver but no S4 are MG-100087 (EN-500096 `cancellation_pending`, ends 2026-11-02, 33 days) and MG-100335 (EN-500409 active, ends 2026-12-29, exactly 90 days; S4 uses `< 90`). The code is correct; table row answered.

**Not done:**
- No stubs found, so nothing is skipped.
- Not tested against the oracle: FRESH-CDR / FRESH-HEMS / FRESH-VALUE (only SNAPSHOT-INCONSISTENT); `snapshot_mode = strict_asof` (raises NotImplementedError by design); `kg_bundle` on replayed states.
- `scripts/export_preview.py` is covered only by the existing test.
- Existing tests: `test_kg_rules.py::test_invariants_all_customers` and `test_kg_signals.py::test_signal_counts` overlap with the audit (the audit adds oracle set comparisons); none of them is wrong.

**Contract changes:** none. No field is missing from `nba/contracts.py` for these tests.

**Issues:**

- **I1** · **Test:** `tests/test_kg_audit_gates.py::test_non_granted_consent_is_not_allowed[unknown]`
  - **Type:** CODE BUG · **Priority:** MAJOR. It is in the consent area but fails closed: it raises, so no tuple is ever allowed. No snapshot row has another status today; an event or new source could.
  - **Evidence:** `nba/kg/rules.py::consents` copies any status into `ConsentItem(status=…)`. With `status = "unknown"`, pydantic raises `literal_error` (`ConsentStatus` = granted / not_given / withdrawn), so `channel_view` / `generate_candidates` crash instead of treating it as not allowed (README §6.1: "Unknown also counts as not allowed"). `None` and a missing row work (they map to `not_given`).
  - **Root cause:** no normalisation of out-of-enum statuses.
  - **Fix (next session):** in `nba/kg/rules.py::consents`, map any status not in {granted, not_given, withdrawn} to `not_given`, with `override_reason = "unknown status '<x>' treated as not allowed"`.
- **I2** · **Test:** `tests/test_kg_audit_gates.py::test_no_duplicate_blocked_rows_per_offer_and_rule`
  - **Type:** CODE BUG · **Priority:** MINOR
  - **Evidence:** MG-100325 has two `P-SL-01` HOLDING-PRECONDITION rows: one from the S1 signal path ("(from S1)") and one from the generic loop ("not offered").
  - **Root cause:** in `nba/kg/rules.py::generate_candidates`, the generic loop skips only offers in `signal_offers` (the allowed ones), not offers already blocked on the signal path.
  - **Fix (next session):** track `signal_blocked` offer IDs in the signal loop and skip them in the generic loop.
- **I3** · **Test:** `tests/test_kg_audit_signals.py::test_every_signal_has_a_date`
  - **Type:** CODE BUG · **Priority:** MINOR (provenance)
  - **Evidence:** every S6 (80), S7 (66), S8 (33) and S9 (48) signal has `date = None`; README §4.1 B4 says each signal has a date.
  - **Root cause:** in `nba/kg/predicates.py`, `household_exceeds_sims`, `pv_without_hems` (feed-in branch), `hems_battery_or_wallbox` and `smart_meter_flexible_load` pass `None` as the Hit date.
  - **Fix (next session):** use the evidencing row's date: the mobile/energy contract's `record_updated_at` (or `start_date`), and the latest `activated_at` of the cited devices for S8.
- **I4** · **Test:** `tests/test_kg_audit_invariants.py::test_every_flag_has_a_src`
  - **Type:** CODE BUG · **Priority:** MINOR
  - **Evidence:** `service_critical` (53) and `data_inconsistent` (71) flags have `src = None`.
  - **Fix (next session):** in `nba/kg/segments.py::triage`, set `service_critical.src` from the P1 driver (`energy_contracts.status` / `service_interactions.status` / `energy_contracts.dunning_level` / `charge_sessions.session_status`). Set `data_inconsistent.src` to `charge_sessions.cdr_received_at` or `service_interactions.resolved_at`.
- **I5** · **Test:** `tests/test_kg_audit_graph.py::test_path_edges_are_ontology_edge_types`
  - **Type:** CODE BUG · **Priority:** MINOR (explanation path)
  - **Evidence:** generic paths use edge type `GENERIC_OFFER` (`nba/kg/paths.py::explain`), which is not in `kg/ontology.yaml`.
  - **Fix (next session):** add `GENERIC_OFFER: {from: Customer, to: Offer, note: "non-personalised catalog offer (D1)"}` to `kg/ontology.yaml`, and to README §6.11 (Q-KG-22).
- **I6** · **Tests:** `tests/test_kg_audit_policy.py::test_policy_layer_has_no_orphan_nodes`, `tests/test_kg_audit_graph.py::test_no_orphan_nodes`
  - **Type:** CODE BUG · **Priority:** MINOR
  - **Evidence:** `policy_graph()` has 7 orphans: A0–A5 and `consent:profiling_analytics`. Every `customer_graph(state, policy, archetype)` keeps the 5 unused archetype nodes as orphans (e.g. MG-100001: A0, A1, A3, A4, A5). Only `export_graph` prunes them.
  - **Fix (next session):** in `nba/kg/graph.py`, add Archetype nodes only in `customer_graph` for the customer's own archetype. In `policy_graph`, add `REQUIRES` edges from every non-generic, non-service Offer to `consent:profiling_analytics` (D1), so the consent type is connected and the profiling rule is visible in the graph.
- **I7** · **Tests:** `tests/test_kg_audit_policy.py::test_ontology_node_types_match_readme`, `::test_ontology_edge_types_match_readme`
  - **Type:** README DISCREPANCY · **Priority:** MINOR
  - **Evidence:** the ontology has extra `Archetype` (node) and `INSTANCE_OF`, `IN_ARCHETYPE` (edges), which README §4.3 / §6.11 do not list. Code and ontology agree, so this is a README gap (Q-KG-22).
  - **Fix (next session):** document them in README §6.11 through the contract process, or drop them.
- **I8** · **Test:** `tests/test_kg_audit_policy.py::test_policy_channels_carry_contact_cost`
  - **Type:** README DISCREPANCY · **Priority:** MINOR
  - **Evidence:** README §6.1 lists contact cost per channel in `kg/policy.yaml`, but the policy has none. The workbook `value_assumptions` values match §6.7 (`test_workbook_contact_costs_match_readme` passes).
  - **Fix (next session):** decide Q-KG-20.
- **I9** · **Test:** `tests/test_kg_audit_policy.py::test_preconditions_match_readme_table[P-MO-01]`
  - **Type:** README DISCREPANCY · **Priority:** MINOR
  - **Evidence:** §6.4 says P-MO-01 requires an active energy contract; `kg/policy.yaml` has `requires: []`. P-MO-01 is generic-only, and D1 drops only owned products, so the requirement can never apply (Q-KG-21).
  - **Fix (next session):** after the team answers, either remove the requirement from §6.4, or add `has_active_energy` to `nba/kg/predicates.py` and to P-MO-01 `requires`, and apply it in `_holding_check` for generic offers too.

**New questions:** Q-KG-20 (contact cost source), Q-KG-21 (P-MO-01 requirement vs D1), Q-KG-22 (ontology extras in README) and Q-KG-23 (Agent NBA: Windows `fcntl`, pydantic pin). Q-KG-06 answered.

**Handoff / next step** (BLOCKER: none; MAJOR, then MINOR):
1. I1: normalise unknown consent statuses in `rules.consents` (MAJOR).
2. I2: deduplicate HOLDING-PRECONDITION rows between the signal and generic loops.
3. I3: dates for S6–S9.
4. I4: `src` for `service_critical` and `data_inconsistent`.
5. I5 + I6: ontology edge `GENERIC_OFFER`; no orphan archetype / profiling-consent nodes.
6. I7–I9: README §6.1 / §6.4 / §6.11 after the team answers Q-KG-20–22, then re-run `tests/test_kg_audit_*.py`. Every one of the 11 failures should then pass without editing the audit tests, except the ones the team resolves by changing the README.

**Next session starts with:** I1 in `nba/kg/rules.py::consents`, then `pytest tests/test_kg_audit_gates.py -q`.

### Session 10 · 2026-10-26 20:10–21:40 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 6e46313..(this commit)

**Goal:** new-data handling A–D (user request); merge and fix the teammate's KG audit (`test/kg-audit`); refresh the API docs for Agent NBA's delivery (Q-NBA-21). Agent CARDS' folder was not touched, as the user asked.

**Done:**
- **A–D** (README §6.15):
  - `kg/data_contract.yaml` + `nba/kg/intake.py` + `scripts/validate_data.py`;
  - 13 bounded thresholds in `kg/policy.yaml → parameters`, with labels templated from them;
  - `scripts/policy_diff.py` (customer, before, after only);
  - `eval_time: auto`.
- **Fixes from an adversarial review of A–D** (3 verifiers, 21 findings):
  - auto eval_time comes from the catalog's own workbook (`nba.data` stamps `attrs['workbook']`);
  - eval_time offsets and YAML dates are normalised;
  - the scripts use the configured eval_time;
  - S4 is capped at 90 days;
  - the validator catches empty rule cells, unreadable booleans, non-ISO dates, missing key columns and missing sheets (no crash), null `order_id` on guest rows and the extra date columns, and treats `category` / `response` as rule enums;
  - policy_diff fills the parameters of an older base, prints readable git errors, escapes Markdown pipes, labels each file, and overrides tone at runtime (Agent CARDS' cached policy; no CARDS file changed).
- **Merged `origin/test/kg-audit`** (Ho Anh Minh, 189 tests plus an oracle) and fixed all 9 issues:
  - I1: unknown consent status → `not_given` with a reason;
  - I2: no duplicate HOLDING rows from the signal and generic loops;
  - I3: dates for S6–S9;
  - I4: `src` on `service_critical` and `data_inconsistent`;
  - I5: `GENERIC_OFFER` in the ontology;
  - I6: no orphan policy nodes (archetype nodes per customer; personalised offers REQUIRE `consent:profiling_analytics`);
  - I7–I9: README §6.11 / §6.1 / §6.4 updated (Q-KG-20/21/22 decided), with the oracle constants and the contact-cost test aligned to the decisions.
- **Q-NBA-21:** `docs/api.md` updated for f8090e8 (`POST /api/replay`, English reasons, reduced static view, resolved and still-open questions); `docs/openapi.json` regenerated (now includes `/api/replay`).

**Verified:**
- `pytest -q tests/`: **351 passed** (the audit suite included).
- `validate_data.py` on the workbook: 0 errors, 7 warnings.
- `policy_diff.py`: 0 changes for the same policy; 2 changes for S2 at 4 failures, and 39 when S4 is also at 30 days.
- `/api/replay`: 126 / 508 / 1, 118 affected, 29 revocations (11 at 12:00 on 01.10).

**Questions:** Q-KG-20, 21 and 22 answered; Q-KG-24 opened for Agent NBA; Q-KG-19 and Q-KG-23 still open for Agent NBA.

**Next session starts with:** the Rule Center spec from the mentor (user, 26 Oct): plan the split. Agent NBA owns the tier-2 rule engine; KG aligns the tier-1 compliance gates (C-01…C-09) and the shared contact counter.

### Session 11 · 2026-10-26 21:40–22:30 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 092d493..(this commit)

**Goal:** sync with `main` (CARDS' new UI version + the audit PR #1), and turn the mentor's Rule Center spec into an English spec checked against the data (user: "these belong to NBA").

**Done:**
- Merged `origin/main` (beb92a7: CARDS `web/` changes + PR #1) into `feat/kg`. No conflicts; nothing of CARDS edited. 351 tests pass; `main` fast-forwarded to 092d493.
- `docs/rule-center.md`:
  - the spec in English;
  - each tier 1 rule mapped to the existing KG gate (all built; C-07 is stricter);
  - each tier 2 default checked against the workbook, with its impact on today's 750 decisions;
  - the shared contact counter, evaluation order, NBA's pieces, card fields;
  - the legacy audit and test cases, checked;
  - open decisions R1–R5.
- README §6.16 points to it.

**Verified against the data:**
- B-01 claims exact: 673 customers, median 4, 328 at ≥ 5.
- B-02 "p90 = 4" not reproduced (3 with all sources). The "4% → 1.2%" claim holds per customer over Jun–Sep, not per 30 days.
- B-03 and B-04 max of 2 in 90 days: confirmed.
- Legacy "~830" = 829 sends without channel consent at send time; 114 app pushes to customers without the app.
- Test customers: all tier 1 cases already pass. MG-100112's call is worth €14.87 (≥ €10, passes B-08). MG-100051's B-05 block ended 23.09, before the snapshot.

**Questions:** Q-KG-25 and Q-KG-26 (R1–R5) for the user and mentor.

**Next session starts with:** after R1–R5, build `nba/kg/contacts.py` (shared counter with per-rule `sources`), switch the old contact cap to it, and add the C-xx IDs to the tier 1 checks; then hand over to Agent NBA.

### Session 12 · 2026-10-26 18:00–19:40 Europe/Berlin · Claude Code (Opus) · branch feat/kg · commits 062196c..(this commit)

**Goal (user):** "thực hiện phần KG trước và phần Agent NBA": build the Rule Center (KG part, then Agent NBA's part) and close the NBA questions Q-KG-19/23/24. The Rule CARD page is on a separate temporary branch (`feat/rule-card`, b5228a9), not in Agent CARDS' folder.

**Done (KG):**
- `nba/kg/contacts.py`: one shared contact counter.
  - Sources: nba_history, newsletter, service_feedback (text booleans read correctly).
  - Dedupe by channel + time; window `(t − W, t]`; `free_from`.
  - `build_states` copies `newsletter_campaigns.sent_at` onto each newsletter row.
- The contact cap (B-02) uses the counter; `config/kg.yaml contact_cap.sources` = history + service feedback.
- `generate_candidates(apply_cap=False)` keeps capped tuples for deferral.
- `kg/policy.yaml compliance` C-01…C-09 (validated). Blocked rows carry `rule_center_id` (C-02 / C-03 per channel) and `until`.
- The audit oracle counts service-feedback mentions in the cap.

**Done (Agent NBA's part, at the user's request):**
- `config/nba.yaml business_rules` B-01, B-03…B-06, B-08, B-09; `nba/engine/rulecenter.py`:
  - per-tuple block or hold-back (DEFER_UNTIL);
  - waiting actions (`chosen.deferred_until`, send time after it);
  - B-09 capacity as a global pass in Runtime;
  - custom condition trees;
  - the rule report on every card.
- `rule_registry.py`: rule tree, Field / Operator catalog, append-only edits. Also `rule_whatif.py` and `rule_audit.py`.
- API: `/api/rules` (GET/PUT/POST/DELETE), whatif, versions, audit; approvals refuse held-back or tier 2 blocked tuples; CORS; response models; portable lock.
- Build: `rules.json` and `rule_log.jsonl`; data gate; export trimmed to 19.7 MB.
- Contracts:
  - new: `RuleReport`, `RuleResult`, `ContactCounter`, `RulesFile`, `RuleNode`, `RuleChange`, `RuleCreate`;
  - new fields: `deferred_until`, `Blocked.rule_center_id` / `until`, `Versions.rules`;
  - the `BUSINESS-RULE` rule ID.
- Schemas and OpenAPI regenerated.
- Integration fixes in Vinh's rulebook (`nba/rules/*`):
  - `eval_time: auto`;
  - check uses the same cap sources and accepts waiting actions;
  - the diff shows waiting dates;
  - new section "Pauses and limits per channel" and "newsletters count" (hard).

**Docs:** `docs/rule-center.md` (built, engine numbers), `docs/nba-guide.md` (how it works and how to run it), `docs/api.md` §3.6, README §5.4 / §6.7 / §6.16.

**Verified on the mock data:**
- B-01 basis 673 / median 4 / 328 (492 at 3) reproduced by the counter.
- Decisions: 519 act now, 146 waiting, 85 no action.
- Audit: C-01 829, app push without app 114.
- What-if B-01 5 → 3: 328 → 492 customers.
- Build: 750 cards in 5 s.
- API smoke test over uvicorn: all endpoints 200.
- Tests: full suite green before this commit; 17 new Rule Center tests and 8 KG counter tests.

**Open (adversarial review, 4 lenses + verification: 37 of 39 findings confirmed):** fixed before this goes to `main`.
- **High:**
  - a held-back P-EN-02 can be scheduled after its price guarantee ends;
  - custom-rule params (`days`, `channels`, `name`) and day windows have no type or upper-bound check, so a bad edit is logged and then every card returns 500;
  - a failed replay of `rule_versions.jsonl` at start-up silently serves the unedited rules.
- **Medium:**
  - the rule report says "defer" when a counter is at its limit but no tuple was held;
  - sub-rules on the same entity do not narrow the same row;
  - B-09 is a single pass;
  - B-09 ignores approved overrides;
  - two concurrent creates can get the same ID;
  - sub-rule effect / hard flag is shown but ignored;
  - conditions are not checked against the catalog;
  - children of built-in rules are independent rules;
  - REQUIRE_APPROVAL / CANCEL_PENDING are accepted but do nothing;
  - replay revokes waiting cards on CONTACT-CAP;
  - `policy_diff` ignores waiting;
  - the static `summary` / `n_blocked` are computed after trimming;
  - the audit uses Autostrom `cancelled_at` wrongly;
  - the §3 counts in `docs/rule-center.md` are inflated.
- **Low:**
  - B-05 has no lookback window (103 pairs vs the spec's 7);
  - `within_days` uses `abs`;
  - the NO_ACTION reason hides B-xx;
  - a torn JSONL line;
  - multi-worker replay;
  - the propensity version changes on rule edits;
  - CORS whitespace;
  - response models for replay / whatif / audit / versions;
  - a null condition value gives 500;
  - the audit C-07 ignores the tightening.
- **For Agent CARDS (`web/`, not touched):** regenerate `web/src/types/contracts.ts` (`npm run types`, add `RulesFile`); show "waits until" and disable one-click Approve when `deferred_until` is set (the API already refuses with 409).

**Delivered to `main` early at the user's request** ("đưa lên main sớm", 26 Oct), with the review findings above still open. All 412 tests pass on the merged tree.

**Next session starts with:** fixing the confirmed review findings (highest first) and delivering them to `main`; afterwards wire the Rule CARD page (`feat/rule-card`) to `/api/rules`.

### Session 13 · 2026-10-27 · Claude Code (Opus) · branch feat/kg

**Goal (user):** implement the whiteboard idea from 27 Oct: per offer × channel × tone, k = buys observed / buys predicted, p_new = p × k, so a channel that does worse than predicted loses to the next one.

**Done:**
- `nba/engine/propensity.py`: `calibration_factor` and a calibrated `p_accept`:
  - k is shrunk toward 1 by 5 pseudo-buys and kept within [0.2, 3];
  - k is not applied to catalog offers (D1), the service assumption or overrides.
- `PSource.k` added; the evidence line reads "calibrated ×k: n bought where the model expected m".
- `config/nba.yaml calibration` (validated); README §6.6 and `docs/nba-guide.md` updated; schemas regenerated.

**Verified:**
- 254 tuples calibrated (k 0.73–1.13); 12 decisions change.
- MG-100019 moves from newsletter €13.19 to app push €11.40, the whiteboard case.
- MG-100273's call falls under the B-08 €10 floor, so the customer gets no action.
- Tests: 4 new calibration tests. Two older tests were adjusted: the base-shrinkage test now runs without calibration, and the B-09 test uses a limit of 1, because only 2 calls are chosen now.

**Next:** "AI decides whether k applies to this customer's profile (clustering)" from the whiteboard. The look-alike lift (`nba.learn.lookalike`) is the closest existing piece.

