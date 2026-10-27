# MAINGAU Next Best Action: what it does and how to run it

For team members who demo, develop or pitch the engine. Details:
- [README.md](../README.md): the build brief;
- [docs/api.md](api.md): the API;
- [docs/rule-center.md](rule-center.md): the rules.

All numbers below come from the mock workbook `data/maingau_nba_mockdata.xlsx` (750 customers, snapshot 2026-09-30 23:59:59, rate mode). They were produced by the commands in §6.

## 1. What it does

For every customer, the engine:
- reads the data;
- finds what the customer needs now;
- drops every action that a rule forbids;
- values each remaining offer × channel by its expected gain in customer lifetime value (ΔCLV);
- proposes the best one, with a German message, a send time and a full explanation.

A marketer approves, changes or rejects the proposal. **Nothing is sent automatically.**

## 2. How one decision is made

| Step | What happens | Example: MG-100023 |
|---|---|---|
| 1. Load | Read the workbook and check it against `kg/data_contract.yaml`. Build one state per customer at the evaluation time (the end of the latest `clv_calc_date`) | snapshot 30.09.2026 23:59:59 |
| 2. Signal → need → offer | 13 signals (S1–S13) read the data. The knowledge graph maps each signal to a need and each need to offers (`kg/policy.yaml`) | **S3**: bought a Wallbox on 14.08.2025 but has no Autostrom → need *EV charging* → **P-AS-01 MAINGAU Autostrom** |
| 3. Hard rules (tier 1) | Consent per channel, double opt-in, unsubscribe, profiling consent, dunning, cancellation, open ticket, never offer what they own | e-mail consent withdrawn and no app → both channels dropped |
| 4. Value each offer × channel | p = chance to buy, from past conversions, then calibrated by k = buys observed / buys expected for that offer × channel × tone. CLV now, if they buy, and if they do not (10 years, 6% discount, churn model) | portal pop-up: p 1.6%; CLV €577 now, €1,017 if they buy, €577 if not; contact cost €0 |
| 5. Expected gain | **ΔCLV = p·(CLV if bought − CLV now) + (1 − p)·(CLV if not − CLV now) − contact cost** | 0.016 × (1,017 − 577) − 0 ≈ **+€7.12** |
| 6. Business rules (tier 2) | Frequency limits, cooldowns, minimum value per channel, call capacity. A rule **blocks** a tuple, or **holds it back** until the earliest allowed day | newsletter held back: 6 of max 5 e-mails in 90 days (B-01) |
| 7. Choose | The best ΔCLV allowed **now**. If none, the best held-back one with its waiting date. If nothing has ΔCLV > 0: no action | **P-AS-01 · portal pop-up · Sie**, at the next login |
| 8. Output | German message from an approved template; send time; explanation path; six-point checklist; rule report; decision log | template `P-AS-01.sie.p`, "Unterwegs laden mit MAINGAU Autostrom"; checklist 6/6 |
| 9. Across customers | B-09 caps calls per week; the lowest-value calls switch channel or wait | no effect today (5 calls) |

**Rules that always apply:**
- payment data (dunning) is used only to block sales;
- without profiling consent only non-personalised catalog offers in the formal "Sie" are used;
- service problems get a service action first (P-SV-01), never a sales message.

## 3. Rules (Rule Center)

| Tier | Rules | Where | Can marketing change it? |
|---|---|---|---|
| 1, compliance | C-01…C-09: consent, double opt-in, unsubscribe, withdrawn consent, profiling, dunning, complaint, cancellation, payment data | `kg/policy.yaml → compliance` | No; it can only add stricter rules |
| 2, business | B-01 e-mails, B-02 contacts, B-03 calls, B-04 SMS, B-05 dismissals, B-06 after a ticket, B-07 owned products, B-08 minimum value of a call, B-09 calls per week | `config/nba.yaml`, B-02 in `config/kg.yaml` | Yes: switch on/off and change numbers |
| Custom | Rules added in the Rule Center (Field + Operator + hard/customized + active), with sub-rules | `config/nba.yaml → custom_rules` or the API | Yes |

Every customer card says which rule passed, blocked or held back, with a counter line such as `Email 6/5 (90 d) · Total 1/2 (30 d) · Call 0/1 (90 d) · SMS 0/1 (90 d)`.

## 4. What comes out

| Output | Content |
|---|---|
| `out/customers/<id>.json` | One `CustomerCard` per customer (profile, signals, candidates, blocked, chosen, checklist, rules, decision log) |
| `out/index.json`, `out/summary.json` | Worklist rows and totals |
| `out/rules.json` | The rule tree and the Field / Operator options for the Rule Center page |
| `out/rule_log.jsonl` | Per customer: every rule's result and the final action |
| `out/test_report.md`, `out/impact_report.md` | Reference customers and expected impact (unless `--no-report`) |
| API | The same JSON, plus decisions, rule edits, what-if, legacy audit and replay (§6.4) |

## 5. Results on the mock data

| Measure | Value |
|---|---|
| Build | 750 customers in about 5 s |
| Data check | 0 errors, 7 warnings |
| Decisions | **519 act now** (total ΔCLV €8,897), **146 waiting** for a rule (ΔCLV €1,706), **85 no action** |
| Legacy audit | of 2,022 past sends, 829 went out without channel consent and 114 were app pushes to customers without the app |
| What-if, B-01 from 5 to 3 e-mails | customers with e-mail paused 328 → 492; 90 decisions change |
| Event replay (01.10 stream) | 118 customers re-decided; 33 pending cards revoked (32 by a new open ticket, 1 by a cancellation) |

## 6. How to run

### 6.1 Setup (once)

```bash
git clone https://github.com/ducthangng/maingau && cd maingau
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python 3.12; pydantic is pinned to 2.14.x
cd web && npm ci && cd ..                                           # Node 18+ (only for the UI)
```

The workbook and the event stream are already in `data/`. The first load parses the workbook once and caches it.

### 6.2 Check the data

```bash
.venv/bin/python scripts/validate_data.py                  # report: out/data_validation.md; exit 1 on ERROR
.venv/bin/python scripts/validate_data.py --workbook new.xlsx
```

### 6.3 Build every decision

```bash
.venv/bin/python -m nba.build --out out/                                 # all 750 customers + reports
.venv/bin/python -m nba.build --out out/ --export web/public/data        # also replace the UI's mock data
.venv/bin/python -m nba.build --customers MG-100023,MG-100112 --no-report  # a few customers, fast
.venv/bin/python -m nba.build --out out/ --learn                         # learn customer memory from feedback first
```

**Options:**

| Option | Effect |
|---|---|
| `--p-mode uplift` | Value with the extra buyers caused (control group) instead of the plain buy rate |
| `--asof 2026-10-02T12:00:00` | Another evaluation time |
| `--workbook path.xlsx` | Another workbook |
| `--skip-validation` | Build even if the data check finds errors |
| `--memory path.jsonl` | Customer memory to apply (default `out/customer_memory.jsonl`, used only if the file exists) |
| `--no-memory` | Ignore the customer memory |
| `--learn` | First turn new feedback into memory, code only (no AI): the workbook's `service_nba_feedback`, plus `decision_log.jsonl` and `service_feedback.jsonl` next to the memory file when they exist |

The build stops with a message if the data check finds an error. The static export stays under 30 MB.

**Customer memory:** what people said no to is remembered per customer (`nba.ai.feedback`) and held back by rule `MEMORY` until its date. The build prints how many memory entries it used. `--learn` adds each feedback item only once, so a fresh clone builds the same memory and the same export every time. On the mock data it learns 74 entries (58 active at the evaluation time) and changes 14 decisions: 3 get another action and 11 wait until a later date.

### 6.4 Run the API

```bash
.venv/bin/uvicorn api.app:app --port 8000      # interactive docs: http://localhost:8000/docs
```

The first request loads the data (about 3 s).

**Read:**

```bash
curl -s localhost:8000/api/customers/MG-100023 | jq '.chosen, .rules.counter_line'
curl -s 'localhost:8000/api/customers?offer=P-SV-01' | jq length
curl -s localhost:8000/api/summary | jq .chosen_by_offer
```

**Decide (human in the loop):**

```bash
curl -s -X POST localhost:8000/api/customers/MG-100068/decision -H 'Content-Type: application/json' \
     -d '{"action": "approve", "user": "Anna"}'
```

A refusal returns 409 with the rule that blocks the action.

**Rules:**

```bash
curl -s localhost:8000/api/rules | jq '.rules[] | {id, name, active}'
curl -s -X POST localhost:8000/api/rules/whatif -H 'Content-Type: application/json' \
     -d '[{"rule_id": "B-01", "params": {"max": 3}}]' | jq '{changed, before: .before.act_now, after: .after.act_now}'
curl -s -X PUT localhost:8000/api/rules/B-01 -H 'Content-Type: application/json' \
     -d '{"by": "Anna", "reason": "fewer e-mails", "params": {"max": 3}}'
curl -s localhost:8000/api/rules/audit | jq '.by_rule'
```

**Replay the event stream** (preview only):

```bash
curl -s -X POST 'localhost:8000/api/replay?until=2026-10-01T12:00:00' | jq '.affected | length'
```

**What the API writes:**
- decisions go to `out/decision_log.jsonl`, rule edits to `out/rule_versions.jsonl`;
- both are append-only, and rule edits are replayed when the API starts;
- delete `out/rule_versions.jsonl` to go back to the rules in the config files.

**Calling it from the browser:** the API allows calls from `http://localhost:5173` (the Vite dev server). Set `MAINGAU_CORS_ORIGINS` for other origins.

### 6.5 Run the UI

```bash
.venv/bin/uvicorn api.app:app --port 8000      # terminal 1: the API (§6.4)
cd web && npm run dev                          # terminal 2: http://localhost:5173: Worklist, Groups
```

- **Live API** (badge top right): with the API running, the UI reads `/api/*` through the Vite proxy (`MAINGAU_API` changes the target, `VITE_API_BASE` calls another origin directly). Every approve, override and reject is posted to `POST /api/customers/{id}/decision`; a refusal (409) is shown with its rule IDs and the decision is not kept.
- **Static** (badge): without the API, or with `VITE_STATIC=1` (Vercel), the UI reads the JSON in `web/public/data` and decisions stay in the browser. Run §6.3 with `--export web/public/data` after any engine change so the static demo shows the engine's current decisions.
- The **Rule Center card** (`/rules`) is on the temporary branch `feat/rule-card`: `git switch feat/rule-card` in your own folder, or open a separate worktree (README §13).
- Ticks and added rules are kept in the browser until the page is wired to `/api/rules`.

### 6.6 Other tools

| Command | What it does |
|---|---|
| `.venv/bin/python scripts/replay_demo.py` | Event replay report (`out/replay_report.md`) |
| `.venv/bin/python -m nba.rules export` → edit `rules.yaml` → `diff` → `apply --by "Name"` | Change rules as plain-language cards; `diff` shows who changes and checks the hard rules |
| `.venv/bin/python scripts/policy_diff.py` | Which customers change decision after an edit to `kg/policy.yaml` |
| `.venv/bin/python scripts/export_kg_viz.py` | Graph data for the decision-graph viewer: the ontology, the policy layer and eight demo customers' decision paths (`out/kg_viz.json`) |
| `.venv/bin/python -m nba.learn run` | Feedback loop: which offers work, compared with the control group |
| `.venv/bin/python -m pytest -q tests/` | All tests (about 90 s), including the reference customers in both p modes |
| `.venv/bin/python -m nba.ai qa [--no-ai] [--scenarios 8]` | AI tests of the whole workflow (§6.8); report in `out/ai_qa/report.md`; exit code 1 if a check fails |

### 6.8 AI tests of the whole workflow

`nba/ai/qa.py` puts three AI roles on the real pipeline. Code checks decide what passes, and the AI can never clear a failed check.

| Role | What it does | Without an AI backend |
|---|---|---|
| Tester | Writes scenarios: one change to one customer, as events of the real event stream (ticket, dunning, cancellation, consent, charging failures, gas meter, order). It can only use IDs and values from the ontology and the data. Code applies the events (`nba.kg.events.replay`) and decides the customer again | 8 seed scenarios, one per event type, each on a different customer |
| Marketer | Approves or rejects proposals through the API. Code then runs the feedback step and checks that a rejected offer does not come back | Fixed policy: every third proposal is rejected |
| Judge | Reads each before/after pair, marks it explainable or suspicious, and cites IDs from the evidence | Skipped |

**Checks (code):**
- **Every card:** the schema is valid; the chosen action is a candidate; nothing is sent without approval; the value is positive (or it is a service action); an active exclusion means no sales; the channel has consent; personalised offers need profiling consent.
- **Each event's effect:**
  - a ticket, dunning or cancellation activates its exclusion, stops sales and revokes a pending sales card;
  - a withdrawn consent is no longer used;
  - three failed charges raise S2, a gas meter deregistration raises S1.
- **The workflow through the API:**
  - the summary matches the index;
  - Overview reasons exist for personalised actions;
  - decisions are accepted;
  - rejected offers are not proposed again (rule MEMORY);
  - the journey is newest first;
  - the cluster review never marks a hard flag ready.

A tester expectation that does not come true is a **finding** for a person, not a failure. Tests: `tests/test_ai_qa.py`, with a fake backend and a mutation test showing the checks catch a broken decision. To run against a real backend: `MAINGAU_AI_QA=1 MAINGAU_LLM=claude .venv/bin/python -m pytest -m ai_live` (opt-in, because it costs API calls).

### 6.7 Common problems

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: ruamel` | `.venv/bin/pip install -r requirements.txt` |
| `data contract error(s)` when building | Read `out/data_validation.md`; fix the workbook or use `--skip-validation` |
| The UI shows "MOCK DATA" | Run §6.3 with `--export web/public/data` |
| An approval returns 409 "held back until …" | The action waits for a rule (e.g. B-01); approve after that date or choose another tuple |
| The rules look different after restarting the API | Edits in `out/rule_versions.jsonl` are replayed; delete the file to reset |

## 7. Limitations

- **Mock data:** the numbers show the method, not real results.
- **p is descriptive:** it is an observed conversion rate (backed off to coarser levels, adjusted by similar customers), not a causal uplift. `--p-mode uplift` uses the control group.
- **Latest state only:** `consent_status`, dunning and app/portal flags hold the latest state, so the legacy audit is an estimate.
