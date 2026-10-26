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
| Q-KG-10 | Generic offers by phone/SMS: MG-100112's generic StromAktiv call is +€14.8 (rate) / +€2.6 (uplift), not negative as D1 assumed (README K11) | Outcome of MG-100112 and of every no-profiling customer whose only channel is a call | Team | answered | Team decided 26 Oct: allow; MG-100112 → generic StromAktiv by phone (README §6.12, §9, K11) |
| Q-KG-11 | Agent NBA: please (a) change the evidence example in `nba/contracts.py` Signal.evidence from `order:SO-1#2` to `order:SO-1` (Order IDs are order_id now), and (b) consider an optional `ConsentItem.doi_at` so the consent-proof drawer can show the real double opt-in date (KG currently puts it only in the channel reason text) | Contract comment is wrong; consent proof in the UI | Agent NBA | open | — |
| Q-KG-12 | Agent NBA: use `nba.kg.rules.check_tuple(state, offer_id, channel, policy)` for the override 409 and for `legacy_comparison.blocked_now_by`; do not re-implement gates | One source of truth for hard rules | Agent NBA | open | — |
| Q-KG-13 | Agent NBA: `rank()` (34a9f5c) drops ΔCLV ≤ 0 silently and ranks all origins together. README §6.12 needs (a) dropped tuples added to `blocked` as `ECON-NONPOSITIVE` and (b) the tiers: signal/service tuples first; generic tuples for profiled customers only when no signal/service tuple has ΔCLV > 0 (`generic.fallback_for_profiled`). Without (b), MG-100023 would get a generic StromWärme (about +€24) instead of P-AS-01 | Team test MG-100023 → P-AS-01; need-first ranking | Agent NBA | open | — |
| Q-KG-14 | Agent NBA: the export is 34 MB (`indent=2`) and still 23 MB compact, above the ~20 MB budget for `web/public/data` (README §13.2). Write compact JSON and trim per-candidate duplication: only the top 5 tuples per customer get the full `checks`/`path`, or drop channel duplicates of the same offer | Vercel static deploy and UI load time | Agent NBA | open | — |
| Q-KG-15 | Agent NBA: internal reason lines mix languages: the NO_ACTION and ECON-NONPOSITIVE reasons are German ("Keine zulässige Aktion…", "erwartete ΔCLV"), the rest is English. README §0: UI text may be English or German, customer content German. Pick one language for internal reasons, English recommended | Consistent UI and pitch | Agent NBA | open | — |
| Q-KG-16 | Agent NBA: K11 is decided. Make MG-100112 strict in `tests/test_acceptance.py` under both p modes (chosen `P-EN-01|outbound_call|sie`, `origin = generic`, content not personalised, S3 blocked by CONSENT-PROFILING), and close Q-NBA-11 in your log | README §9 strict list | Agent NBA | open | — |

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

