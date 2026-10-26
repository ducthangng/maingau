# MAINGAU NBA API: reference for the UI

**Implementation and owner:** `api/app.py`, owned by Agent NBA. This document is maintained by Agent KG.

**Version:** API 0.1.0 at `main` e40c526, 26 Oct 2026. Every example below was produced by calling the running API on the mock data.

The UI can get the data in two ways. Both return **the same JSON shapes**, defined in [`nba/contracts.py`](../nba/contracts.py) and exported as JSON Schema in [`docs/schema/`](schema/):

| Mode | When | Read | Write decisions |
|---|---|---|---|
| **Static** | Vercel demo | `public/data/index.json`, `summary.json`, `customers/<id>.json` (written by `python -m nba.build --export web/public/data`) | Client-side only (no server) |
| **API** | Local / pilot | `GET /api/...` below | `POST /api/customers/{id}/decision`, persisted to `out/decision_log.jsonl` |

## 1. Running the API

```bash
.venv/bin/python -m uvicorn api.app:app --port 8000          # http://localhost:8000
```

- **Base URL:** `http://localhost:8000`. All routes start with `/api`.
- **Interactive docs:** `http://localhost:8000/docs` (Swagger UI) and `/openapi.json`. A static copy is in [`docs/openapi.json`](openapi.json).
- **Cold start:**
  - the first request loads the workbook and builds all 750 cards, which takes about 2 s;
  - later list calls take under 1 s;
  - cards are cached per customer state revision.
- **Auth:** none. The service is for local and pilot use only. It never sends anything to customers.
- **CORS:** not enabled. In development, proxy `/api` through Vite instead of calling port 8000 from the browser:

  ```ts
  // vite.config.ts
  export default defineConfig({ server: { proxy: { "/api": "http://localhost:8000" } } });
  ```

  Calling the API cross-origin, for example from a deployed site, needs CORS on the server first (open question Q-KG-19 for Agent NBA).
- **Probability mode:** `p_mode` comes from `config/nba.yaml` (`rate` by default). The mode used is recorded in every card's `meta.versions.propensity`.

## 2. Types

Generate TypeScript types from the JSON Schemas; they are the contract. The OpenAPI file does not describe response bodies yet (Q-KG-19).

```bash
npx json-schema-to-typescript docs/schema/customer_card.schema.json > src/types/customer_card.ts
npx json-schema-to-typescript docs/schema/index_row.schema.json     > src/types/index_row.ts
npx json-schema-to-typescript docs/schema/summary.schema.json       > src/types/summary.ts
npx json-schema-to-typescript docs/schema/decision_request.schema.json > src/types/decision_request.ts
```

**Contract conventions:**

| Concept | Format |
|---|---|
| Tuple ID | `"<offer_id>\|<channel>\|<tone>"`, e.g. `"P-EN-02\|newsletter_email\|sie"`. `"NO_ACTION"` means nothing qualifies |
| Channels | `newsletter_email`, `email`, `portal_popup`, `app_push`, `sms`, `outbound_call`, and `service_agent` (service only) |
| Fact | Every displayed number is a `Fact` `{v, src: "table.column", updated_at, row_key}`. The tooltip adds `sources[<table>]` (refresh, latency) from the card, or `summary.sources` in the worklist |
| `blocked[].offer_id = "*"` | The rule applies to every non-service offer. With `channel` set, that channel is blocked for every offer |
| Money and p | `delta_clv` and CLV values are euros on the model basis (README §6.5). `p_accept` is 0–1. The UI rounds for display |

## 3. Endpoints

### 3.1 `GET /api/customers`: worklist

Returns `IndexRow[]`, **already sorted**: `urgency_tier` ascending (P1 first), then `urgency_score` descending, then `customer_id`.

**Query parameters** (all optional, combined with AND):

| Parameter | Matches | Example |
|---|---|---|
| `q` | Substring of `customer_id` or `city`, case-insensitive | `q=darmstadt` |
| `offer` | `chosen_offer` (an offer ID or `NO_ACTION`) | `offer=P-EN-02` |
| `channel` | `channel` of the chosen tuple | `channel=newsletter_email` |
| `archetype` | `A0`–`A5` | `archetype=A4` |
| `urgency_tier` | `P1`–`P5` | `urgency_tier=P1` |
| `flag` | One flag in `flags` | `flag=service_critical` |
| `confidence` | `high` / `medium` / `low` | `confidence=low` |
| `service_mode` | `true` / `false` | `service_mode=true` |
| `personalised` | `true` / `false` | `personalised=false` |

Example: `GET /api/customers?q=darmstadt&offer=P-EN-02` returns 6 rows (`MG-100068`, `MG-100441`, …). `GET /api/customers?urgency_tier=P1` returns 53 rows. The first one:

```json
{
  "customer_id": "MG-100190", "age_band": "30–39", "city": "Hamburg", "lines": 1,
  "clv_eur": 310.0, "churn": 0.95,
  "archetype": "A4", "archetype_name": "Retention risk (do no harm)",
  "urgency_tier": "P1", "urgency_score": 429.45,
  "top_reason": "electricity cancellation received on 2026-08-21 [EXCL-CANCELLATION]",
  "flags": ["service_critical"], "outlier": true, "triggers": ["S13"],
  "chosen_offer": "NO_ACTION", "chosen_tuple": "NO_ACTION", "channel": null, "tone": null,
  "delta_clv": null, "p_accept": null, "contact_cost": null, "confidence": null,
  "checklist_failed": ["consent_for_channel", "profiling_consent", "no_exclusion", "not_owned", "contact_cap", "data_fresh"],
  "service_mode": true, "personalised": null,
  "n_signals": 1, "n_candidates": 0, "n_blocked": 8, "exclusions": ["EXCL-CANCELLATION"]
}
```

**UI notes:**
- **Bulk approval** groups rows by `chosen_tuple`. Exclude rows where `outlier` is true or `checklist_failed` is non-empty, unless the user confirms each one.
- **`NO_ACTION` rows** currently list all six items in `checklist_failed`, because no tuple was checked. Show "No action" instead of six failures (Q-KG-19).

### 3.2 `GET /api/customers/{customer_id}`: customer page

Returns one `CustomerCard`, including every decision already recorded for this customer (`decision_log`). Unknown ID: **404** `{"detail": "Unknown customer"}`.

**Top-level keys:** `schema_version`, `customer_id`, `meta`, `sources`, `triage`, `profile`, `timeline`, `signals`, `candidates`, `blocked`, `chosen`, `alternatives`, `legacy_comparison`, `explanation_path`, `checklist`, `data_quality`, `decision_log`.

`chosen` for MG-100068:

```json
{
  "tuple_id": "P-EN-02|newsletter_email|sie", "status": "proposed", "send_at": "2026-10-01T10:00:00",
  "reason_line": "electricity price guarantee ends on 2026-10-08 (in 8 days) [S4] → StromGarant via newsletter_email; ΔCLV +18.92 €, p 9.3% (medium)",
  "service_mode": false, "agent_script": null,
  "content": {
    "language": "de", "tone": "sie", "personalised": true, "template_id": "P-EN-02.sie.p",
    "subject": "Preisgarantie mit StromGarant",
    "body": "Ihre Preisgarantie endet am 08.10.2026. Mit StromGarant können Sie sich eine neue Preisgarantie sichern. Wir erklären Ihnen gern die Bedingungen."
  }
}
```

Each item of `candidates[]` carries what an NBA card needs:
- `origin`: `signal`, `service` or `generic`;
- `personalised`;
- `why[]` and `notes[]`;
- `checks[]`;
- `path[]`, the KG chain, with `ui_ref` jump targets;
- `valuation`:
  - `clv_now_shown`, `clv_now_model`;
  - `clv_after_accept`, `clv_after_reject`;
  - `p_accept` and `p_source`: `{mode, level, n_treated, conv_treated, n_control, conv_control, baseline_control}`;
  - `contact_cost`, `delta_clv`, `confidence`.

**Waterfall:** start from `clv_now_model`, not `clv_now_shown`. Starting from the displayed value would turn its rounding error (up to €3.05) into fake gain.

**After a decision**, the card reflects it:
- `chosen.status` becomes `approved`, `overridden` or `rejected`;
- an override replaces `chosen`, `explanation_path` and `checklist` with the overriding tuple.

An earlier approval **never revives a tuple that is blocked now**. If the customer's state changed (new `meta.state_revision`) or the policy/model versions changed, older decisions stay in `decision_log` but no longer drive `chosen`.

### 3.3 `GET /api/summary`: KPI strip and tooltips

Returns `Summary` for all customers. A subset:

```json
{
  "eval_time": "2026-09-30T23:59:59", "n_customers": 750, "value_date": "2026-09-30",
  "urgency_counts": {"P1": 53, "P2": 62, "P3": 95, "P4": 261, "P5": 279},
  "archetype_counts": {"A0": 49, "A1": 33, "A2": 342, "A3": 201, "A4": 75, "A5": 50},
  "chosen_by_offer": {"P-EN-02": {"count": 60, "sum_delta_clv": 995.61}},
  "sources": {"charge_sessions": {"refresh": "event-driven", "latency": "own stations minutes; roaming CDRs 1-72 h late"}},
  "column_src": {"clv_eur": "customer_value.clv_eur"}
}
```

Also present:
- `blocked_by_rule`, `no_action_by_reason`, `signal_counts`, `flag_counts`;
- `sources` for all 18 source tables, used for tooltips;
- `column_src` for every worklist column.

### 3.4 `POST /api/customers/{customer_id}/decision`: human in the loop

**Body** (`DecisionRequest`):

```json
{ "action": "approve | override | reject", "user": "caro", "reason": "optional text",
  "tuple": { "offer_id": "P-EN-03", "channel": "email", "tone": "sie" } }
```

| Action | Required | What happens |
|---|---|---|
| `approve` | `user` | Approves the current `chosen` tuple after re-checking every hard rule. Refused (409) when `chosen` is `NO_ACTION`. If you send `tuple` and it differs from the current proposal, the call is refused: reload or override |
| `override` | `user`, `tuple` | Re-runs the KG gates (`check_tuple`), requires the tuple to be one the engine evaluated with ΔCLV > 0, and respects the generic-fallback rule. Then records it |
| `reject` | `user`, `reason` | Records the rejection; `chosen.status` becomes `rejected` |

**Response 200** is the stored `DecisionLogEntry`. Real override of MG-100068 from StromGarant to StromWärme by email:

```json
{
  "ts": "2026-10-26T15:50:29.259604+00:00", "actor": "caro", "action": "overridden",
  "tuple_id": "P-EN-03|email|sie", "from_tuple": "P-EN-02|newsletter_email|sie", "to_tuple": "P-EN-03|email|sie",
  "reason": "heat pump campaign",
  "state_revision": "sha256:52de8395…", "versions": {"policy": "kg-0.1:4795e2c101e7", "value_model": "clv_simple_v1:2dbd595e1f64",
                                                  "propensity": "p-0.1:rate:fde3370da2b9", "templates": "t-0.1:bb86f2c3522f"},
  "rules_applied": ["CONSENT-CHANNEL", "CONSENT-PROFILING", "CONTACT-CAP", "EXCL-AUTOSTROM-CANCELLED", "EXCL-CANCELLATION",
                    "EXCL-DUNNING", "EXCL-OPEN-TICKET", "HOLDING-PRECONDITION"],
  "scores": {"clv_now_model": 604.88, "clv_after_accept": 1063.83, "p_accept": 0.0341, "contact_cost": 0.01, "delta_clv": 15.65,
             "n_treated": 2022, "conv_treated": 69, "n_control": 248, "conv_control": 5, "baseline_control": 0.0202}
}
```

**Refusals return 409** with the rule IDs that block the tuple. Show them; never let the user retry the same tuple.

```json
// override MG-100112 to Autostrom by phone (no profiling consent)
{ "detail": { "rule_ids": ["CONSENT-PROFILING"],
              "reasons": ["MAINGAU Autostrom is a personalised offer and the customer has no profiling consent"] } }

// override MG-100068 to StromWärme by phone
{ "detail": { "rule_ids": ["CONSENT-CHANNEL"], "reasons": ["marketing_phone withdrawn on 2023-03-09"] } }

// approve MG-100035, whose chosen is NO_ACTION
{ "detail": { "rule_ids": ["ECON-NONPOSITIVE"],
              "reasons": ["Keine zulässige Aktion mit positiver erwarteter ΔCLV. Gründe: CONSENT-CHANNEL, DATA-MISSING, ECON-NONPOSITIVE, EXCL-CANCELLATION"] } }
```

**Persistence:** entries are appended to `out/decision_log.jsonl` as `{"customer_id": …, "entry": DecisionLogEntry}`, with file locking. Nothing is ever sent.

## 4. Errors

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "Unknown customer"}` | `customer_id` not in the data |
| 409 | `{"detail": {"rule_ids": [...], "reasons": [...]}}` | A hard rule or economic rule refuses the decision |
| 422 | `{"detail": "user must not be empty"}` / `"A rejection requires a reason"` / `"An override requires a tuple"` | Missing required input |
| 422 | FastAPI validation list, e.g. `detail[0].type = "literal_error"`, `loc = ["body", "action"]` | Body does not match `DecisionRequest` (e.g. `"action": "send"`) |

**Rule IDs in 409 responses**, with suggested UI labels:

| Rule ID | Label |
|---|---|
| `CONSENT-CHANNEL` | No consent for this channel |
| `CHANNEL-AVAILABLE` | Channel not available (no portal account / app) |
| `CONSENT-PROFILING` | No profiling consent: only non-personalised offers, tone Sie |
| `EXCL-DUNNING`, `EXCL-CANCELLATION`, `EXCL-OPEN-TICKET`, `EXCL-AUTOSTROM-CANCELLED` | Sales blocked (dunning / cancellation / open ticket / Autostrom cancelled); service only |
| `HOLDING-PRECONDITION` | Customer already has it, a prerequisite is missing, or a generic offer is not allowed while a need-based offer exists |
| `CONTACT-CAP` | Contact limit reached (2 per 30 days) |
| `ECON-NONPOSITIVE` | Expected ΔCLV ≤ 0 |
| `DATA-MISSING` | Not enough data, or a combination the engine did not evaluate |

## 5. Static mode (Vercel)

| API call | Static file |
|---|---|
| `GET /api/customers` | `GET /data/index.json`, then filter and search on the client |
| `GET /api/customers/{id}` | `GET /data/customers/{id}.json` |
| `GET /api/summary` | `GET /data/summary.json` |
| `POST …/decision` | Not available; keep decisions client-side and only offer tuples present in `candidates` (Q-CARDS-13) |

A minimal client that works in both modes:

```ts
const BASE = import.meta.env.VITE_API_BASE ?? "";      // "" -> same origin (Vite proxy)
const STATIC = import.meta.env.VITE_STATIC === "1";      // Vercel demo

export async function getCustomer(id: string): Promise<CustomerCard> {
  const url = STATIC ? `/data/customers/${id}.json` : `${BASE}/api/customers/${id}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.status === 404 ? "Unknown customer" : `HTTP ${r.status}`);
  return r.json();
}

export async function decide(id: string, body: DecisionRequest): Promise<DecisionLogEntry> {
  const r = await fetch(`${BASE}/api/customers/${id}/decision`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (r.status === 409) {
    const { detail } = await r.json();                  // { rule_ids: string[], reasons: string[] }
    throw Object.assign(new Error(detail.reasons.join("; ")), { ruleIds: detail.rule_ids });
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
```

## 6. Known limitations (as of e40c526)

Each is tracked as a question for Agent NBA in `log/agent-kg.md`:

- No CORS middleware. Use the Vite proxy (Q-KG-19).
- The OpenAPI file has no response models. Use `docs/schema/` for types (Q-KG-19).
- `NO_ACTION` rows list all six checklist items as failed (Q-KG-19).
- Some reasons, `why` texts and 409 messages are German (Q-KG-15).
- The full export is about 41 MB (Q-KG-14).
- No replay endpoint yet. Deep dive B runs as `python scripts/replay_demo.py`; an API endpoint is optional (Q-KG-17).

Regenerate `docs/openapi.json` and the JSON Schemas with `.venv/bin/python scripts/export_schema.py` after any API or contract change.
