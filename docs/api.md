# MAINGAU NBA API: reference for the UI

**Implementation and owner:** `api/app.py`, owned by Agent NBA. This document is maintained by Agent KG.

**Version:** API 0.2.0, 26 Oct 2026. Changes since 0.1.0:
- the Rule Center endpoints (§3.6; docs/rule-center.md);
- held-back actions: `chosen.deferred_until` and `card.rules`;
- CORS;
- response models in `docs/openapi.json`;
- an empty checklist for NO_ACTION;
- a portable file lock.

Earlier (Q-NBA-21): the replay preview endpoint, English reasons and the reduced static export.

Every example below was produced by calling the running API on the mock data.

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
- **One worker:** run a single API process for the demo (no `--workers N`). Each process replays `out/rule_versions.jsonl` once at start and keeps the rules in memory, so a second worker would not see the first one's Rule Center edits until it restarts.
- **Logs in `out/`:** `decision_log.jsonl`, `rule_versions.jsonl`, `service_feedback.jsonl`, `customer_memory.jsonl`. Each record is one complete line, written at once and fsync'ed. A line that cannot be read (a torn last line after a crash, a hand edit) is skipped with a warning in the server log; the next record still starts on a new line.
- **Interactive docs:** `http://localhost:8000/docs` (Swagger UI) and `/openapi.json`. A static copy, including `/api/replay`, is in [`docs/openapi.json`](openapi.json).
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
  "flags": ["service_critical"], "outlier": true, "triggers": ["S13"], "reason_signal": null, "reason_need": null,
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
- **`reason_signal` / `reason_need`** are the Signal and Need on the chosen action's path (e.g. `"S11"`, `"N-HOME-ELECTRICITY"`), for the Overview page (`prompts/ui-overview.md`). They are `null` for general offers (no profiling consent) and for `NO_ACTION`. Labels are in `Summary.signal_labels` / `need_labels`.

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

`why` and `notes` are English (internal text). Customer-facing `chosen.content` stays German. Example from MG-100068:
- `why`: `"electricity price guarantee ends on 2026-10-08 (in 8 days) [S4]"`, `"Observed conversions 11/99, level offer_channel_tone, mode rate; control group 1/19, baseline used 2.02% (global); descriptive difference 9.09%, not causal uplift"`;
- `notes`: `"Contact before the price guarantee expires on 2026-10-08; check the proposed date"`.

**Waterfall:** start from `clv_now_model`, not `clv_now_shown`. Starting from the displayed value would turn its rounding error (up to €3.05) into fake gain.

**After a decision**, the card reflects it:
- `chosen.status` becomes `approved`, `overridden` or `rejected`. `rejected` shows only while the card would still show the rejected tuple (the proposal, or a person's approval or override of it): once customer memory (`POST /api/ai/feedback`) changes the proposal, the new one shows as `proposed`;
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
- `signal_labels` (e.g. `"S4": "Price guarantee ends within 90 days"`, parameters filled in) and `need_labels` (e.g. `"N-HEAT-PUMP": "Heat pump / electric heating"`), from `kg/policy.yaml`;
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
              "reasons": ["No eligible action with positive expected ΔCLV. Reasons: CONSENT-CHANNEL, DATA-MISSING, ECON-NONPOSITIVE, EXCL-CANCELLATION"] } }

// approve with a tuple that is no longer the current proposal
{ "detail": { "rule_ids": ["HOLDING-PRECONDITION"],
              "reasons": ["The proposal has changed; reload it or submit an explicit override"] } }
```

Other English refusal texts:
- `"Without profiling consent only the default Sie tone is allowed"`;
- `"The KG did not evaluate this tuple: no eligible need path or generic channel"`;
- `"Expected ΔCLV €… ≤ 0"`;
- `"Generic fallback is allowed only when no signal or service action has positive expected ΔCLV"`.

**Persistence:** entries are appended to `out/decision_log.jsonl` as `{"customer_id": …, "entry": DecisionLogEntry}`, with file locking. Nothing is ever sent.

### 3.5 `POST /api/replay`: deep-dive B preview (read-only)

This replays the 2026-10-01 event stream (README §6.14) against the current decisions and returns what would change.
- It **never** changes API state, cards or approvals (`preview_only: true`).
- Every chosen tuple that is not `NO_ACTION` or rejected is treated as a pending card.

**Query parameter:**

| Parameter | Meaning |
|---|---|
| `until` (optional) | Timezone-naive ISO time; events ingested up to and including it are applied. Default: the whole stream, up to 2026-10-03 19:27:39 |

**Response:**

| Field | Content |
|---|---|
| `preview_only` | Always `true` |
| `eval_time` | The cutoff used |
| `counts` | Events by status: `applied`, `informational`, `orphan`, `stale`, … |
| `affected` | Customer IDs whose decision facts changed |
| `pending_revocations` | `{customer_id: transition}` for cards revoked by a hard rule |
| `transitions[]` | One row per decision-relevant event: `customer_id`, `event_id`, `event_type`, `occurred_at`, `ingested_at`, `delay_hours`, `pending_tuple`, `pending_status` (`valid` / `revoked`), `revoked_by`, `reasons`, `signals_added`, `signals_removed` |
| `customers[]` | The re-decided `CustomerCard` of every affected customer, with `meta.events_applied_until` set |

**Results on the mock stream:**
- Full stream: about 3.6 s and 3.6 MB.
  - Counts: `{"applied": 126, "informational": 508, "orphan": 1}`.
  - 118 affected customers, 29 pending revocations, 127 transitions.
- With `until=2026-10-01T12:00:00`: 28 affected, 11 revocations.

The revocation for MG-100125:

```json
{ "customer_id": "MG-100125", "event_type": "ticket_created",
  "occurred_at": "2026-10-01T11:31:02", "ingested_at": "2026-10-01T11:31:20", "delay_hours": 0.01,
  "pending_tuple": "P-AS-01|newsletter_email|sie", "pending_status": "revoked", "revoked_by": ["EXCL-OPEN-TICKET"],
  "reasons": ["MAINGAU Autostrom blocked: open meter_deregistration ticket TK-201001 since 2026-10-01"],
  "signals_added": ["S12"], "signals_removed": [] }
```

**Errors (422):**

| Input | Message |
|---|---|
| A timezone offset | `"Use timezone-naive timestamps from the mock event stream"` |
| A cutoff before the snapshot | `"Replay cutoff must not precede the source snapshot"` |
| Not a date | FastAPI validation error, `loc = ["query", "until"]` |

The same analysis is available offline as `python scripts/replay_demo.py` (`out/replay_report.md`, `out/replay/timeline.json`). That is the source for a static demo.

### 3.6 Rule Center: `/api/rules`

Rules that block or limit actions (docs/rule-center.md). Every edit is appended to `out/rule_versions.jsonl` (version, time, `by`, `reason`, operation, `rule_set_version`) and replayed when the API starts. A decision stores `versions.rules`, so approvals made under older rules stop applying.

**Rule log robustness:**
- an edit is validated in full before it is logged; a refused edit (403 / 404 / 422) leaves the log unchanged;
- at start the log is replayed onto a copy of the rules, and the API switches to them only when the replay is complete;
- a logged edit that no longer applies (an unknown rule, a value an older API accepted) is skipped with a warning in the server log, and `GET /api/rules/versions` shows it with `"skipped": "<reason>"`; the other edits still apply;
- a torn line is skipped (see §1).

Demo rules U-1…U-4 (switched off) are in `config/nba.yaml`; how to switch them on: docs/rule-center.md §10.

| Method and path | Body / query | Returns |
|---|---|---|
| `GET /api/rules` | — | `RulesFile` (`docs/schema/rules.schema.json`): `rule_set_version`, `rules` (tree: C-xx locked, B-xx, U-xx with `children`), `entities` (Field / Operator catalog from the workbook columns) |
| `PUT /api/rules/{id}` | `RuleChange`: `{"by": "Name", "reason": "...", "active": false, "params": {"max": 3}}` | the new `RulesFile` |
| `POST /api/rules` | `RuleCreate`: `{"by", "hard", "active", "condition": {"entity", "column", "op", "value"}, "effect"?, "children": [...], "parent"?}` | the new `RulesFile`; IDs `U-<n>` are never reused (the first new one is U-5, after the demo rules), sub-rules `U-<n>.<k>`. Set `days` / `channels` afterwards with `PUT` |
| `DELETE /api/rules/{id}?by=Name&reason=...` | — | the new `RulesFile`. Only rules added here can be removed |
| `POST /api/rules/whatif` | a list of `RuleChange` (with `rule_id`) and `RuleCreate`. Nothing is saved | `customers`, `changed`, `examples` (10), `rule_set_version` before/after, `before` / `after` totals: act now, waiting, no action, ΔCLV, held tuples by channel / offer, customers per rule |
| `GET /api/rules/versions` | — | the edit log |
| `GET /api/rules/audit` | — | legacy audit over `nba_action_history`: `sends`, `would_be_stopped`, `by_rule`, `by_channel`, `examples`, `notes` |

**Examples on the mock data:**
- What-if `[{"rule_id": "B-01", "params": {"max": 3}}]`: B-01 customers 328 → 492, 90 decisions change, ΔCLV now €8,897 → €8,617 (about 6 s for 2 × 750 decisions).
- Hard rule *Customer · app installed is no* with sub-rule *Offer · business line is mobile*: blocks P-MO-01 for MG-100001 (`blocked[].rule_center_id = "U-5"`).
- What-if `[{"rule_id": "U-1", "active": true}]` (demo rule: no StromAktiv in Köln): 19 decisions change.
- Audit: 2,022 sends, 1,496 would be stopped, C-01 829, app push without app 114.

**Refusals:**

| Status | When |
|---|---|
| 403 | Switching off or loosening a compliance rule (C-xx) or B-07; deleting a built-in rule |
| 404 | Unknown rule or parent |
| 422 | Invalid value (e.g. `max: 0`, an unknown channel or source), switching off B-02 (raise its limit instead), an empty `by`, or a custom rule the engine cannot apply (below) |

422 messages for custom rules (`{"detail": "<message>"}`, also from `POST /api/rules/whatif`):

| Input | Message (excerpt) |
|---|---|
| `"entity": "customers"` | `unknown entity 'customers'; use one of [...]` |
| `"column": "citty"` | `customer_master has no column 'citty'` |
| `"value": null` | `the condition on customer_master.city needs a value` |
| `"op": ">=", "value": "many"` | `>= needs a number, got 'many'` |
| `"op": "within_days", "value": 999` | `within_days: value must be a whole number from 1 to 365` |
| `"effect": "REQUIRE_APPROVAL"` or `"CANCEL_PENDING"` | `effect 'REQUIRE_APPROVAL' is not supported for custom rules; use one of [...]` |
| `PUT` `"params": {"days": "abc"}` (or 0, 400) | `days must be a whole number from 1 to 365 (got 'abc')` |
| `PUT` `"params": {"channels": ["fax"]}` | `channels must be marketing channels [...]` |
| `PUT` `"params": {"name": 5}` | `name must be text` |
| `PUT /api/rules/B-01` `"params": {"window_days": 400}` | `window_days must be a whole number from 1 to 365 (got 400)`; the same bound for `cooldown_days` and B-02 |

Rule validation messages start with `config/nba.yaml has invalid rule(s):` and name the rule, e.g. `custom_rules.U-5: days must be …`.

**Approvals and held-back actions:**
- `approve` / `override` also check tier 2 rules.
- A tuple blocked by B-08 or a custom rule, or held back (B-01…B-06, B-09, B-02), returns **409** with the rule IDs (e.g. `["B-08"]`) and reasons like `"held back until 2026-12-02 09:00: E-mail paused: 8/5 e-mails in 90 days"`.
- A held-back card shows `chosen.deferred_until`, `send_at` after it, the reason starting "Held back until …" and a failed `contact_cap` checklist item.

**CORS:** the API allows `http://localhost:5173` and `http://127.0.0.1:5173`. Set `MAINGAU_CORS_ORIGINS` (comma-separated) for others.

### 3.7 `GET /api/customers/{customer_id}/journey`: Customer 360° journey

What happened to one customer and how they reacted, newest first (`nba/kg/journey.py`, schema `docs/schema/journey.schema.json`). A separate document next to the card: the card and its `timeline` stay as they are. Plain facts only: no CLV, scores, warnings or payment data. Last 12 months plus future contract milestones.

```json
{"customer_id": "MG-100023", "eval_time": "2026-09-30T23:59:59", "months": 12,
 "counts": {"consent": 3, "milestone": 1, "newsletter": 13, "portal": 16, "proposal": 3},
 "events": [
  {"id": "jr-001", "date": "2026-09-29", "type": "portal", "title": "Portal visit",
   "detail": "dashboard, consumption chart, contact form · 1 min 57 s", "ref": "portal:36c4b507-dc3e",
   "src": "portal_sessions.session_start", "facts": {"client": "web", "pages": ["dashboard", "consumption_chart", "contact_form"], "duration_s": 117}},
  {"id": "jr-006", "date": "2026-09-07", "type": "proposal", "title": "Offer HEMS Starter-Set via newsletter email",
   "detail": "tone Sie · delivered", "reaction": "no reaction", "ref": "action:NBA-400064",
   "src": "nba_action_history.decided_at", "facts": {"offer_id": "P-SL-01", "channel": "newsletter_email", "tone": "sie", "response": "ignored"}}
 ]}
```

| `type` | One event per | `detail` | `reaction` |
|---|---|---|---|
| `newsletter` | delivery (`newsletter_performance` + `newsletter_campaigns`) | topic, tone | bounced / not opened / opened · clicked *target* · bought within 7 days · unsubscribed. An Apple Mail preload (`apple_mpp_prefetch`) is not an open |
| `proposal` | legacy engine action (`nba_action_history`, control group left out) | **tone** (Du / Sie), delivery | no reaction / viewed / clicked / dismissed · bought within 14 days |
| `agent_suggestion` | offer shown to a service agent (`service_nba_feedback`) | channel, agent accepted / dismissed (reason) | customer reaction, or "not mentioned to the customer" |
| `ticket` | ticket (`service_interactions`) | channel, status, **resolution** | CSAT |
| `order` | shop order | status, **value**, quantity (never the payment method) | — |
| `charging` | **day** with charging sessions | completed / failed / aborted, kWh, failure reasons | — |
| `portal` | portal or app visit | **pages viewed**, duration, "offer banner shown" | — |
| `contract`, `milestone`, `consent` | as in the card timeline | | |

- `flags`: `open`, `repeat contact`, `cancellation`, `returned`, `cancelled`, `bounced`, `unsubscribed`, `failed`.
- `facts`: the raw values behind the text (API only). A missing key means no / none.
- Unset fields (`detail`, `reaction`, `flags`, `future`, …) are left out of the JSON.
- 404 for an unknown customer.

### 3.8 `/api/customers/{customer_id}/service-feedback`: service agents' reactions

A service agent's reaction to a suggested offer in Customer 360° (`web/src/lib/serviceFeedback.ts`). The body is one `ServiceFeedbackRow` (`nba/contracts.py`), the shape of the workbook's `service_nba_feedback`. Rows are appended to `out/service_feedback.jsonl`. Nothing is sent to the customer.

| Method | Body | Returns |
|---|---|---|
| `POST` | `ServiceFeedbackRow` | the stored row |
| `GET` | — | the rows posted for this customer, once per `feedback_id` (the workbook's rows are not repeated) |

```json
{"feedback_id": "SF-1761557400000", "ticket_id": null, "customer_id": "MG-100068", "shown_at": "2026-10-27T09:30:00.000Z",
 "channel": "phone", "suggestion_source": "nba_engine", "suggested_offer_id": "P-EN-02", "agent_id": "anna",
 "agent_action": "accepted", "dismiss_reason": null, "offer_mentioned_to_customer": true,
 "customer_reaction": "declined", "converted_within_14d": null}
```

| Field | Values |
|---|---|
| `channel` | `phone`, `chat` |
| `agent_action` | `accepted`, `dismissed` |
| `dismiss_reason` | `customer_already_has_product`, `customer_upset`, `no_time`, `not_relevant`, `null` |
| `customer_reaction` | `interested`, `declined`, `annoyed`, `null` |
| `shown_at` | ISO timestamp |

- **404** `Unknown customer`.
- **422** when the body's `customer_id` differs from the path, for an unknown `suggested_offer_id`, a `shown_at` that is not an ISO timestamp, or a value outside the lists above.
- **Feedback step:** `POST /api/ai/feedback` and `python -m nba.ai feedback` read the workbook's `service_nba_feedback` plus these rows (once per `feedback_id`). A dismissed or declined offer becomes customer memory for that customer, e.g. *declined* → pause that offer for 90 days, *annoyed* or *customer upset* → pause all sales for 30 days. The next decision uses it (rule ID `MEMORY`).

## 4. Errors

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "Unknown customer"}` | `customer_id` not in the data |
| 409 | `{"detail": {"rule_ids": [...], "reasons": [...]}}` | A hard rule or economic rule refuses the decision |
| 422 | `{"detail": "user must not be empty"}` / `"A rejection requires a reason"` / `"An override requires a tuple"` | Missing required input |
| 422 | FastAPI validation list, e.g. `detail[0].type = "literal_error"`, `loc = ["body", "action"]` | Body does not match `DecisionRequest` (e.g. `"action": "send"`) |
| 422 | `{"detail": "Use timezone-naive timestamps …"}` / `"Replay cutoff must not precede the source snapshot"` | Invalid `until` for `/api/replay` |
| 422 | `{"detail": "unknown entity …"}`, `"… has no column …"`, `"… days must be a whole number from 1 to 365 …"`, … | A Rule Center edit the engine cannot apply (§3.6); nothing is logged |
| 422 | `{"detail": "customer_id MG-… in the body does not match the path (MG-…)"}` / `"Unknown offer …"` / `"shown_at must be an ISO timestamp, …"` | Invalid service feedback (§3.8) |

**Rule IDs in 409 responses**, with suggested UI labels:

| Rule ID | Label |
|---|---|
| `CONSENT-CHANNEL` | No consent for this channel |
| `CHANNEL-AVAILABLE` | Channel not available (no portal account / app) |
| `CONSENT-PROFILING` | No profiling consent: only non-personalised offers, tone Sie |
| `EXCL-DUNNING`, `EXCL-CANCELLATION`, `EXCL-OPEN-TICKET`, `EXCL-AUTOSTROM-CANCELLED` | Sales blocked (dunning / cancellation / open ticket / Autostrom cancelled); service only |
| `HOLDING-PRECONDITION` | Customer already has it, a prerequisite is missing, or a generic offer is not allowed while a need-based offer exists |
| `CONTACT-CAP` | Contact limit reached (B-02: 2 per 30 days); the action waits until it frees up |
| `B-01` … `B-09`, `U-<n>` | A Rule Center rule blocks or holds back this tuple (§3.6) |
| `ECON-NONPOSITIVE` | Expected ΔCLV ≤ 0 |
| `DATA-MISSING` | Not enough data, or a combination the engine did not evaluate |

## 5. Static mode (Vercel)

| API call | Static file |
|---|---|
| `GET /api/customers` | `GET /data/index.json`, then filter and search on the client |
| `GET /api/customers/{id}` | `GET /data/customers/{id}.json` |
| `GET /api/summary` | `GET /data/summary.json` |
| `GET /api/customers/{id}/journey` | `GET /data/journey/{id}.json` (without `src` and `facts`) |
| `POST …/decision` | Not available; keep decisions client-side and only offer tuples present in `candidates` (Q-CARDS-13) |
| `POST /api/replay` | Not available; use `out/replay/timeline.json` from `scripts/replay_demo.py` |

**The static cards are a reduced view** (`nba/engine/export.py`, Q-KG-14). The API keeps every tuple.

| Part | Static card |
|---|---|
| `candidates` | **One per offer**: the chosen tuple for the chosen offer, otherwise the best channel. Re-ranked 1…n |
| `checks` and `path` | Full for the chosen tuple and the next three; empty (`[]`) for the rest |
| `alternatives` | Recomputed from the three tuples after the chosen one, with `why_lower` such as `"Lower expected ΔCLV by €3.26"` |
| `chosen` | Identical to the API |
| `blocked`, `signals`, `profile` | Identical to the API |
| JSON format | Compact |

**Static export size:** `customers/` is about 19.2 MB, `index.json` about 0.5 MB and `rules.json` (the Rule Center tree and the Field / Operator catalog) about 41 KB; `journey/` (Customer 360°) is about 3.8 MB. The whole export stays under 30 MB (about 24 MB now). Regenerate it from `main` whenever the engine changes: `python -m nba.build --export web/public/data`.

**Rule Center data in static mode:**
- each card keeps only tier 2 outcomes in `rules.results` (block / defer / off), plus `counter_line`;
- a waiting card keeps the planned action and one fallback;
- `blocked` keeps one "possible from" row per offer × channel, as in the API (e.g. MG-100023: Autostrom by newsletter, possible from 5 Nov 2026);
- the API keeps everything.

A real export removes `manifest.json`, the mock-data marker. MG-100068, for example, has 12 tuples in the API but 4 candidates in the static file.

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

## 6. Known limitations

**Resolved on 26 Oct (Rule Center delivery):**
- Q-KG-19: CORS; response models; NO_ACTION has an empty `checklist` and `checklist_failed`.
- Q-KG-23: the file lock works without `fcntl` (Windows); pydantic is pinned to `~=2.14.1`.
- Q-KG-24: `eval_time` and `--asof` are resolved by `nba.state.resolve_eval_time`; the P-EN-02 window comes from `policy.params`; `nba.build` refuses a workbook with data-contract errors (`--skip-validation` overrides).

**Notes:**
- B-09 capacity needs every customer's decision. The first single-card request computes them once (about 3 s).
- What-if decides every customer twice (about 6 s).

**Resolved in f8090e8:**
- Q-KG-14: reduced static export.
- Q-KG-15: English internal texts.
- Q-KG-16: MG-100112 strict test.
- Q-KG-17: `/api/replay`.

Regenerate `docs/openapi.json` and the JSON Schemas with `.venv/bin/python scripts/export_schema.py` after any API or contract change.
