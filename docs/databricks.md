# Databricks and MCP: architecture and setup

This page covers four things:
1. How the system is built today.
2. How it would run on Databricks with MCP data access.
3. What is already connected.
4. How to connect your own workspace.

The connection is to **our own Databricks Free Edition workspace with the mock data**. It is not a MAINGAU system (README §11).

## 1. The system as built (27 Oct)

```text
data/ (workbook, event stream)
  └─ nba/data.py ─ load + type every sheet ── kg/data_contract.yaml check (nba/kg/intake.py)
       └─ nba/state.py ─ one CustomerState per customer at eval_time
            ├─ KG (kg/ontology.yaml, kg/policy.yaml, nba/kg/*)
            │    Signal → Need → Offer; hard rules (consent, exclusions, profiling, contact cap = Rule Center C-01…C-09);
            │    triage: archetype, urgency tier P1–P5, flags
            ├─ Engine (nba/engine/*)
            │    CLV/churn → p_accept (history + look-alike) → ΔCLV rank → business rules B-01…B-09, custom rules,
            │    customer memory (MEMORY), channel capacity → CustomerCard
            └─ Customer 360 (nba/profile/*, nba/kg/journey.py) → profile card + journey document
                 └─ nba/build.py → out/: index.json (worklist), customers/<id>.json, journey/<id>.json, summary, rules
                      ├─ static export → web/ on Vercel (decisions in the browser, exported as files)
                      └─ api/app.py (FastAPI): decisions re-check every rule, Rule Center edits and what-if,
                           AI review, AI feedback, event replay
Orchestration: Worklist → Overview (action ranking) → Groups: clusters of the same offer × channel × tone
               → AI review marks "needs review" (nba/ai/review.py) → a person approves the batch → hand-off file
Feedback: decision log + service feedback → customer memory (nba/ai/feedback.py);
          outcomes vs control group → nba/learn (traffic lights, fix cases, look-alike) → next run
```

What this means for Databricks:

| Finding | Consequence |
|---|---|
| Every module reads data through `load_workbook()` / `load_events()` in `nba/data.py` | The data source can be swapped in one place. This is how the connection works (§3) |
| The engine is a deterministic batch: same data and config give byte-identical JSON, and the KG is rebuilt on every run | It fits a scheduled Databricks Job unchanged. Byte-identical output is how we prove the Databricks path changes nothing |
| Orchestration state lives in local files (`decision_log.jsonl`, `rule_versions.jsonl`, `customer_memory.jsonl`, `out/learn/`) or in the browser (static demo) | This is the main gap for many users at once. In the target it becomes append-only Delta tables |
| The AI steps receive a card as JSON inside the prompt | In the target they fetch the same evidence through governed MCP tools, read-only |
| Events are replayed from a file | In the target an ingestion stream lands events and the replay runs per batch |

## 2. Target architecture on Databricks

| Layer | As built | On Databricks (target) |
|---|---|---|
| Sources | `data/*.xlsx`, `data/*.jsonl` | Source systems → Delta tables in Unity Catalog (`maingau_raw`); event stream via Auto Loader |
| Contract check | `scripts/validate_data.py` | First task of the Job; stops the run on ERROR |
| Decision engine | `python -m nba.build` | Lakeflow Job on serverless compute, same Python code, reads `maingau_raw` through `nba/lakehouse.py` |
| Results / Customer 360 | `out/*.json` | `maingau_nba` tables: `worklist`, `nba_options`, `nba_blocked`, `customer_cards`, `customer_journey` |
| Orchestration state | `decision_log.jsonl`, browser storage | Delta tables `decision_log`, `executions`, `rule_versions`, `customer_memory`, append-only and shared by every user |
| Serving | Vercel static site, local FastAPI | Databricks App (FastAPI + React) reading results and writing decisions |
| AI data access | Card JSON in the prompt | **Managed MCP**: Unity Catalog functions as tools (`customer_360`, `next_best_actions`, `why_blocked`, `action_group`), and Genie for questions in plain language |
| Feedback loop | `nba.learn` on files | Nightly task: decision log + new outcomes → p estimates, look-alike, fix cases → next run |
| Governance | README rules | Unity Catalog permissions, column masks (payment data, birth year), lineage, audit log |

**What MCP adds.** MCP is the AI's governed way into the data; it does not replace the engine. The AI calls a function such as `next_best_actions('MG-100068')` and receives only what that function returns. Unity Catalog decides who may call it, and every call is logged.

**Rules MCP does not change:**
- Decisions stay deterministic. The engine ranks by ΔCLV with no LLM at decision time (README §0).
- The tools are read-only.
- Approving an action still goes through the decision service, which re-checks every hard rule (`checked_tuple` in `api/app.py`).
- The AI never sends anything and never loosens a rule (§6.17).

## 3. What is connected now

| Piece | Status |
|---|---|
| Raw layer: the 23 sheets, `events_raw` and `_manifest` in `workspace.maingau_raw` | **Built:** `scripts/databricks_sync.py upload` |
| Engine reads from Databricks (`MAINGAU_DATA_SOURCE=databricks`) | **Built**, with fallback to `data/`. Live check: 1,505 files, 0 differences against the local build |
| **The engine as a Databricks Job** `maingau-nba-nightly`: `validate_data`, then `decide_and_publish`, on serverless compute | **Built:** `scripts/databricks_deploy.py job --run`. Unity Catalog lineage shows the job reading `maingau_raw` and writing `maingau_nba`. The 02:00 schedule starts paused |
| Results layer in `workspace.maingau_nba`: worklist, options, blocks, cards, journeys, customer memory, learning impact, run info, with column descriptions | **Built:** written by the job (or by `publish` after a local build) |
| **Decisions flow back:** `decision_log` and `service_feedback` are Delta record tables | **Built:** the API appends every approval, override, rejection and agent reaction, and the job turns them into customer memory on its next run. Publish never overwrites them |
| **Genie space** "MAINGAU Next Best Action" over the results | **Built:** `scripts/databricks_deploy.py genie`, with instructions, sample questions and example SQL |
| **The dashboard as a Databricks App** `maingau-nba` | **Built:** `scripts/databricks_deploy.py app`. It reads through the attached SQL warehouse as its own service principal, which gets Unity Catalog grants |
| SQL functions `customer_360`, `next_best_actions`, `why_blocked`, `action_group` | **Built** and callable in SQL |
| Managed MCP server over those functions | **Not available on Free Edition** (previews cannot be enabled; the server answers "not enabled"). Works unchanged on a paid workspace |
| Auto Loader for events, column masks | **Not built.** These are the target |

**How the source works:**
- Every cell is stored as the text pandas reads from the workbook, and a hidden `_row` column keeps the order. `nba/data.py` then parses Databricks data exactly as it parses the file.
- A full 750-customer build read through the Databricks path gave byte-identical output to the local build: 1,504 files, 0 differences (tested against an in-memory warehouse; `tests/test_lakehouse.py`).

**Fallback.** With `source: databricks`, any of these makes the whole run use `data/` and log one warning:
- no SDK or no credentials;
- the network or warehouse is down;
- a sheet is missing;
- a table's row count differs from the manifest (a partial upload).

The run never mixes the two sources. `nba.build` prints which source it read and writes it to `out/data_source.json`. The publish step copies it to `run_info`.

## 4. Connect your workspace

1. **Workspace and token.** Sign up for Databricks Free Edition. In the workspace, open your profile → **Settings → Developer → Access tokens** and generate a token.
2. **Credentials, in the git-ignored `.env`.** Copy `.env.example` to `.env` (the same file that holds the Hessian.AI key) and fill in:
   ```ini
   DATABRICKS_HOST=https://<your-workspace>.cloud.databricks.com
   DATABRICKS_TOKEN=<your token>
   MAINGAU_DATA_SOURCE=databricks   # optional: build and API read the workspace, data/ is the backup
   ```
   `nba/lakehouse.py` loads `.env`, and a variable already set in the shell wins. A profile in `~/.databrickscfg` also works. Never commit the token. Tests always read `data/` (`tests/conftest.py`).
3. **SDK.** Install it into the project environment: `.venv/Scripts/pip install databricks-sdk` (Windows) or `.venv/bin/pip install databricks-sdk`.
4. **Upload the mock data.** Run `python scripts/databricks_sync.py upload`. It:
   - creates `workspace.maingau_raw` and the volume `landing`;
   - stores the original files under `landing/files/`;
   - writes the 23 sheet tables, `events_raw` and, last, `_manifest`.
5. **Check.** Run `python scripts/databricks_sync.py check`. It shows the workspace, warehouse, row counts, and "identical to data/" (compared cell by cell).
6. **Build from Databricks.** Set `MAINGAU_DATA_SOURCE=databricks` (PowerShell: `$env:MAINGAU_DATA_SOURCE="databricks"`), then run `python -m nba.build --out out/`. The last line says `Data: databricks (...)`. To make it permanent, set `source: databricks` in `config/databricks.yaml` instead.
7. **Publish results and MCP tools.** Run `python scripts/databricks_sync.py publish`. It writes `workspace.maingau_nba.*` and the four functions. Then, in the SQL editor:
   ```sql
   SELECT * FROM workspace.maingau_nba.next_best_actions('MG-100068');
   ```
8. **MCP.** Run `python scripts/databricks_sync.py check --mcp`. It lists the tools at `https://<host>/api/2.0/mcp/functions/workspace/maingau_nba` and calls `customer_360` for MG-100068. Managed MCP is a preview, and **Free Edition cannot enable previews**: there the check reports "not enabled". On a paid workspace an admin switches on **Managed MCP Servers** under username → **Previews**.

Settings live in `config/databricks.yaml`: catalog, schemas, volume, warehouse and timeout. `MAINGAU_DATABRICKS_*` variables override them.

**Free Edition limits:**
- Non-commercial use only.
- A daily compute quota; when it is used up, the run falls back to `data/`.
- One small SQL warehouse, which the code picks automatically.

## 5. Run it on Databricks

| Command | What it does |
|---|---|
| `python scripts/databricks_deploy.py job --run` | Uploads the engine to `/Workspace/Users/<you>/maingau-nba`, creates or updates the job `maingau-nba-nightly`, runs it and waits (about 3–4 minutes) |
| `python scripts/databricks_deploy.py run` | Runs the job again |
| `python scripts/databricks_deploy.py genie [--ask "question"]` | Creates or updates the Genie space; `--ask` asks it a question and prints the SQL and the answer |
| `cd web && npm run build`, then `python scripts/databricks_deploy.py app` | Deploys the dashboard and API as the App `maingau-nba`. On Free Edition the App stops after 24 hours: start it again in **Compute → Apps** |
| `MAINGAU_DATA_SOURCE=databricks uvicorn api.app:app --port 8000` | The local API on Databricks data; approvals also go to `maingau_nba.decision_log` |

**How the job works** (`scripts/databricks_job.py`):
- Inside the job, SQL runs through the job's own Spark session (`nba.lakehouse.SparkWarehouse`). That is why lineage names the job.
- There is no fallback in the job. If the raw layer cannot be read, the run fails.
- **`validate_data`** runs the data contract; an ERROR stops the run.
- **`decide_and_publish`** does five things:
  1. reads `decision_log` and `service_feedback` from Delta;
  2. learns customer memory (code only, no AI);
  3. decides for all 750 customers;
  4. publishes the tables;
  5. re-applies the column descriptions.

## 6. Demo script (about 3 minutes)

1. **The data is in Databricks.** Open Catalog → `workspace.maingau_raw`: the 23 source tables, `events_raw` and `_manifest`. *"MAINGAU's customer data lives in Unity Catalog. Our engine reads it from there."*
2. **Databricks runs the engine.** Open Jobs & Pipelines → `maingau-nba-nightly` → **Run now**. Show the two tasks and the output of `decide_and_publish`:
   - feedback read from Delta;
   - 74 memory entries learned;
   - 750 customers decided in about 30 seconds.

   Then open `maingau_nba.worklist` → **Lineage**: the job reads `maingau_raw` and writes `maingau_nba`.
3. **The results, governed.** Open `maingau_nba.nba_options` → Sample data, and run `SELECT * FROM workspace.maingau_nba.next_best_actions('MG-100068')` in the SQL editor.
4. **Ask in plain language.** Open the Genie space "MAINGAU Next Best Action" and ask:
   - *"Which offers bring the most expected value in total?"*
   - *"Why is StromWärme blocked for so many customers?"*

   Genie shows its SQL. *"The AI reads only the tables Unity Catalog grants it."*
5. **The app runs on Databricks.** Open the App `maingau-nba` (Compute → Apps). Approve a group or one customer.
6. **Decisions flow back.** Run `SELECT * FROM workspace.maingau_nba.decision_log ORDER BY ts DESC`: the approval is there within seconds. *"The next nightly run learns from it."* Optionally reject one with "customer upset", then run the job again: that customer's proposal is held back.

Say: *"Shown on our own Databricks Free Edition workspace with the mock data; MAINGAU would point it at their master view."* Do not say it is integrated with MAINGAU's Databricks. Rehearse the Genie questions: it is an AI and can phrase SQL differently.
