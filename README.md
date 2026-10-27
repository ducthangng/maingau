# MAINGAU Next Best Action: build brief for AI coding agents

Futury Build Days, 26–27 Oct 2026. This file is the single source of truth for the build.

**To see how the engine decides and how to run it** (build, API, UI, rules, tests), read [docs/nba-guide.md](docs/nba-guide.md).

- **Requirements:** §4 is the spec agreed with MAINGAU, adopted in full (English translation of the consulted spec).
- **Gaps and conflicts:** where the spec is silent, or conflicts with the data, this file sets the default (§6, §10). Do not invent other behaviour.
- **Other files:** `Hackathon_slides_for_MAINGAU.pdf` is the original challenge brief; `references/` holds German background slides on grid fees. Both are read-only context. If anything else disagrees with this README, this README wins.
- **Repo visibility:** this repo is public (team decision, 26 Oct 2026). The workbook, event stream and challenge slides are MAINGAU mock/challenge material. Never commit real customer data, credentials or API keys.

## 0. Read this first (all agents)

Three agents build in parallel:

| Agent | Builds | Task section |
|---|---|---|
| **Agent KG** (Claude, main session; also reviews the other two) | Ontology, knowledge graph, data loading, signals, rules, generic candidates, triage (archetypes, urgency, flags), explanation paths | §7.1, [PLAN_KG.md](PLAN_KG.md) |
| **Agent CARDS** | Marketing orchestration dashboard: urgency worklist, customer profile, ranked NBAs, bulk execution (React + TypeScript + Tailwind, static on Vercel); Python profile builder | §7.2, [prompts/agent-cards.md](prompts/agent-cards.md) |
| **Agent NBA** | CLV/ΔCLV valuation, p_accept, ranking, why/notes, German content, decision log, build and export CLI, local API | §7.3, [prompts/agent-nba.md](prompts/agent-nba.md) |

Every agent reads §0–§6, its own task in §7, then §8–§10.

**Working rules:**

1. Write only inside the paths your agent owns (§2).
2. Shared contracts (§5) change only through a PR that also edits this README, and the other agents must be told.
3. Start from stubs. Every public function in §5.6 returns fixture data in the first hour, so nobody waits on anyone (§8).
4. Log every session in your own file under `log/` (§12): what you did, what you verified, open questions and issues. Read all three logs at the start of each session.
5. Follow the git rules in §13: your own folder and branch, stage only your own paths, never switch branches or force-push.

**Never:**

- send anything to customers (no SMTP, SMS, telephony or push integration);
- scrape MAINGAU systems;
- use payment data for anything except exclusion;
- let a ranking, a weight or a human override bypass a hard rule;
- guess missing data. Show "not enough data" / "Nicht genug Daten" instead.

**Conventions:**

- Customer-facing content is German. UI labels may be English or German. The pitch is English.
- Python 3.11. Output must be deterministic: the same data and config give byte-identical JSON (sorted keys, no unseeded randomness).

## 1. The product in one paragraph

For each customer, a screen shows two cards side by side.

- **Left card, Customer Profile:** "who is this customer" and "how are they changing".
- **Right card, Next Best Action:** "what should we do" and "why".

Users are marketing staff and service agents. There is a mode switch (§4, C8). A user must understand the customer in about 30 seconds.

Every number on a card has a tooltip showing:
- `table.column`;
- the update time;
- the refresh and latency of that source, taken from the sheet `sources`.

**How the engine decides:**
1. Work out what the customer actually needs: **Signal → Need → Offer**, using the KG.
2. Apply the hard rules.
3. Rank the remaining actions by expected **ΔCLV** following the workbook's `clv_method`.
4. A human approves. Nothing is sent automatically.

The entry point is a **worklist ranked by urgency** (§6.13). A marketer opens one customer, or selects a group of customers that share the same recommended action and approves them together; every customer in the group still passes every hard rule individually.

**Why need-first.** In the mock history, offers sent to customers who had the catalog's own target signal converted at **38/558 = 6.8%**. Offers sent to customers without it converted at **27/1,280 = 2.1%**. Compared within each offer, that is about 2.3 times higher. 70% of the legacy engine's sends had no such signal. This is a descriptive statistic from mock data, not causal uplift; always label it that way.

## 2. Repository layout and ownership

```text
.
├── README.md                    # this file; editing it = changing a contract
├── Hackathon_slides_for_MAINGAU.pdf   # challenge brief, read-only
├── docs/schema/                 # JSON Schemas generated from nba/contracts.py (scripts/export_schema.py)
├── docs/api.md                  # API reference for the UI (endpoints, errors, static mode)
├── docs/openapi.json            # OpenAPI of api/app.py (scripts/export_schema.py)
├── prompts/                     # kickoff prompts for the AI agents (agent-cards.md, agent-nba.md)
├── PLAN_KG.md                   # Agent KG's detailed build plan
├── references/                  # background material, read-only
├── log/                         # one session log per agent (§12)
│   ├── agent-kg.md              # Agent KG
│   ├── agent-cards.md           # Agent CARDS
│   └── agent-nba.md             # Agent NBA
├── data/                        # read-only inputs
│   ├── maingau_nba_mockdata.xlsx
│   └── event_stream_2026-10-01.jsonl
├── config/
│   ├── kg.yaml                  # Agent KG
│   ├── databricks.yaml          # data source: local | databricks; catalog and schemas (§6.18), no secrets
│   ├── cards.yaml               # Agent CARDS
│   └── nba.yaml                 # Agent NBA
├── kg/                          # Agent KG
│   ├── ontology.yaml            # node/edge types (§6.11)
│   └── policy.yaml              # signals, needs, offers, channels, exclusions (§6.1–§6.4)
├── nba/
│   ├── contracts.py             # Agent NBA writes it from §5; others import, never edit
│   ├── data.py                  # Agent KG: workbook + event loading (§5.1)
│   ├── lakehouse.py             # Databricks source (with fallback to data/) and results layer (§6.18)
│   ├── state.py                 # Agent KG: CustomerState, contact counting (§5.2)
│   ├── kg/                      # Agent KG: policy, predicates, signals, rules, segments, graph, paths, events
│   ├── profile/                 # Agent CARDS: header, tone, value, products, consent,
│   │                            #   highlights, timeline, trends, fatigue
│   ├── engine/                  # Agent NBA: clv.py, churn.py, propensity.py, value.py,
│   │                            #   rank.py, content.py, assemble.py
│   └── build.py                 # Agent NBA: CLI
├── templates/de/                # Agent NBA: German content templates (YAML)
├── api/app.py                   # Agent NBA: FastAPI
├── web/                         # Agent CARDS: React + TypeScript + Tailwind (Vite), static, deployable on Vercel
│   └── public/data/             # exported JSON the UI reads: index.json, summary.json, customers/<id>.json
├── scripts/                     # Agent KG: export_schema.py, kg_report.py
├── tests/
│   ├── test_kg_*.py             # Agent KG
│   ├── test_profile_*.py        # Agent CARDS
│   ├── test_engine_*.py         # Agent NBA
│   └── test_acceptance.py       # Agent NBA owns; §9
├── requirements.txt             # Agent NBA
└── out/                         # generated; git-ignored except out/samples/
```

**Default stack:**

| Layer | Choice |
|---|---|
| Data, KG, engine | Python with pandas, openpyxl, networkx, PyYAML, pydantic v2 |
| API | FastAPI + uvicorn, local and pilot use only |
| Tests | pytest |
| UI | React + TypeScript + Tailwind CSS (Vite), static build deployed on Vercel; Recharts for mini charts |

The UI is a static site. `python -m nba.build --export web/public/data` writes the JSON it reads. In the deployed demo, approvals are kept in the browser (localStorage) and can be exported as CSV/JSON; the FastAPI decision endpoint is the local and pilot path. The JSON contract is the same in both.

## 3. Data facts (verified 26 Oct 2026 against the files)

| Item | Verified value |
|---|---|
| Customers | 750, all B2C. `customer_id` is unique in `customer_master` and `customer_value` |
| Workbook | 23 sheets. `sources` lists 18 source sheets; the spec and the workbook README say "15 source tables". Reference sheets: `README`, `columns`, `clv_method`, `value_assumptions`, `product_catalog` |
| Snapshot | 2026-09-30 23:59:59. `customer_value.clv_calc_date` = 2026-09-30 for all rows; `model_version` = `clv_simple_v1` |
| Event stream | 647 lines; 635 unique `event_id` (12 duplicates, identical payloads). Fields: `event_id, event_type, source_system, customer_id, occurred_at, ingested_at, payload`. 21 event types. Last ingest 2026-10-03 19:27:39; max delay 47.26 h; 100 `occurred_at` reversals in ingestion order |
| Autostrom | 238 contracts: 229 active, 9 cancelled. The spec says "150 Autostrom-only". The file gives 159 customers with Autostrom and no energy contract, 161 with active Autostrom and no active electricity, 127 with Autostrom and neither energy nor mobile. **Compute it; never hard-code 150** |
| Energy | 718 contracts: active 698, `terminated_meter_deregistration` 12, `cancellation_pending` 8. Tariffs: StromAktiv, StromGarant, StromKomfort, StromWärme, GasAktiv, GasGarant |
| Consent | 6 types × 750 = 4,500 rows. Statuses: `granted`, `not_given`, `withdrawn`. `profiling_analytics` granted: 461. `newsletter_email` granted: 442, all with `double_opt_in_confirmed_at` set |
| NBA history | 2,270 rows, 2026-06-01 → 2026-09-27. Treated (delivered): 2,022; control (`delivery_status = not_sent_control`): 248. Conversions: 69/2,022 (3.4%) treated vs 5/248 (2.0%) control. Channels: `newsletter_email` 1,397, `portal_popup` 423, `app_push` 213, `sms` 126, `outbound_call` 111. Tone: `sie` 1,698, `du` 572. `rule_id`: R-SEASONAL, R-SHOP-GENERIC, R-CROSS-ENERGY-MOBILE, R-PV-HEMS, R-RETENTION-60D. `consent_checked = 0` in 333 rows |
| History gaps | 8 offers were never sent: P-EN-01, P-EN-03, P-EN-04, P-MO-03, P-SL-02, P-SL-03, P-SH-04, P-SV-01. P-AS-01: 0 conversions in 203 sends |
| Newsletter | 13 campaigns, 2026-01-15 → 09-24, all sent to "all newsletter subscribers"; tonality `du` 7, `sie` 6. 6,161 performance rows. `open_client_class`: `apple_mpp_prefetch` 1,589, `human` 1,457, empty for the rest. `unsubscribed = 1` in 58 rows. Click targets: shop, mobile, energy, smart_living and service landing pages, plus `heat_pump_article` |
| Portal | 5,416 sessions, 2026-07-02 → 09-30. `pages_viewed` is pipe-separated: dashboard, charging_history, invoice, consumption_chart, installment, tariff_overview, contact_form, meter_reading, offers, moving, contract_details, mobile_usage, hems_dashboard |
| Charging | 5,696 sessions, 2026-06-01 → 09-30. `cdr_source`: `roaming_hub` 4,821, `own_backend` 875. `failure_reason`: vehicle_communication, auth_rejected, connector_error, station_offline. Average AC price 0.62 €/kWh in June, 0.52 from July. 79 CDRs have `cdr_received_at` after the snapshot |
| Service | 788 tickets, 2025-10-01 → 2026-09-29; 29 open. Categories: complaint, billing, tariff, moving, autostrom, meter, mobile, meter_deregistration, hems. 229 call transcripts: German, `speech_to_text_pilot`, customer lines start with `Kunde:` |
| Shop | 446 order lines: delivered 411, returned 27, cancelled 8. 25 lines have an empty `customer_id` (guest orders); ignore them in profiles |
| HEMS | Devices: hems_gateway 35, pv_inverter 35, wallbox 29, home_battery 18, smart_plug 17, heat_pump 11. Telemetry: 1,036 daily rows for 35 customers, September 2026 only |
| Mobile | 131 contracts; usage only as 3-month aggregates |
| Language | `preferred_contact_language`: `de` 743, `en` 7. Content stays German |
| CLV | The `clv_method` formula reproduces `clv_eur`: median absolute error 0.27 €, max 3.05 € |
| Churn | `churn_prob_12m` is reproduced exactly for all 718 customers with at least one active line (§6.5) |

**Snapshot inconsistencies.** Do not silently fix these; show them in `data_quality`:
- 79 CDRs received after the cutoff.
- Tickets TK-200565 and TK-200640 have `status = closed` but a `resolved_at` after the cutoff.
- The event `ticket_updated` references `TK-open-complaint`, which does not exist in the snapshot.

Default `snapshot_mode = "provided"`: status columns are authoritative (§10, K8).

## 4. Product spec (agreed with MAINGAU, adopted in full)

The bracketed § references are pointers to this README. Everything else is the spec.

**Context.** A Next Best Action prototype for MAINGAU Energie on `maingau_nba_mockdata.xlsx`: 750 customers joined by `customer_id`. Snapshot 2026-09-30 23:59; the event stream starts 2026-10-01. Reference sheets: `sources` (sources and latency), `columns` (column descriptions), `clv_method` and `value_assumptions` (how an action is valued), `product_catalog` (18 offers).

**Task.** One screen per customer with two cards side by side, as described in §1. Users: marketing and service agents (default: both, with a mode switch). They must understand the customer in about 30 seconds. Every number has a tooltip with `table.column` and update time, plus refresh and latency from `sources`.

### 4.1 Left card: Customer Profile

#### A. Who the customer is

**A1. Header**
- `customer_id`; age band derived from `customer_master.birth_year`, shown as "50–59"; `city`; `household_size`.
- Tenure from `customer_master.customer_since`.
- Digital level: `portal_account`, `app_installed`, `preferred_contact_language`.
- Form of address (Du/Sie), inferred in this priority order (§6.8):
  1. `service_interactions.message_text` and `call_transcripts.transcript`. Cues: "Hi", "danke dir", "tschüss" → Du; "Sehr geehrte", "Mit freundlichen Grüßen" → Sie.
  2. `newsletter_performance`: whether the customer clicked, by `newsletter_campaigns.tonality`.
  3. No signal → default Sie, clearly labelled as the default.
- Always show the evidence, for example "Du – 2/2 messages use 'du', latest 2026-08-14".

**A2. Value and risk** (`customer_value`)
- `clv_eur`, `annual_margin_eur`, `cost_to_serve_12m_eur`, `active_business_lines`.
- `churn_prob_12m` with `churn_drivers` shown as tags.
- `clv_service_impact_eur`, shown as "Service issues are costing €X of CLV".
- Percentile among all 750 customers, and among customers with the same product combination.

**A3. Products held across the business lines.** Shown as a grid; an empty cell is an opportunity and is lightly tinted.
- **Energy** (`energy_contracts`): commodity, tariff, status, `annual_consumption_kwh`, `price_guarantee_until` (countdown in days), `meter_type` (`smart_meter_imsys`?), `feed_in_meter` (customer has PV), `payment_method`.
- **Autostrom** (`autostrom_contracts` + `charge_sessions`): status, `car_brand`/`car_model`, `battery_kwh`, `charge_cards`, `app_user`; kWh per month; AC/DC ratio.
- **Mobile** (`mobile_contracts`): plan, `data_volume_gb` vs `avg_data_used_gb_3m`, `data_limit_reached_3m`, `sim_count` vs `household_size`, `min_term_end`.
- **Shop** (`shop_orders`, only rows with a `customer_id`): recent orders, `product_category`, `order_status`. Returned and cancelled orders do not count as owned.
- **Smart Living** (`hems_devices`): list of `device_type` with `connection_status`; warn if the gateway is offline.
- **Internet:** no ownership data exists; it is only a potential offer.

**A4. Consent and exclusions.** Traffic-light style, at the top of the card, never hidden.
- All 6 consent types from `consent_status`, each with status, `updated_at` and `source`: `newsletter_email`, `marketing_email`, `marketing_phone`, `marketing_sms`, `portal_app_personalisation`, `profiling_analytics`.
- Channel → consent map: §6.1.
- A customer who unsubscribed in `newsletter_performance` counts as withdrawn, even if `consent_status` was not updated.
- Active exclusions (§6.2):
  - `energy_contracts.dunning_level ≥ 1`;
  - `status = cancellation_pending`;
  - any `service_interactions` row with `status = open`, especially `category = complaint`;
  - `autostrom_contracts.status = cancelled`.

**A5. Two or three highlights.** Only things that are genuinely unusual compared with the population, for example "Top 10% CLV", "DC charging 3× the average", "Has PV but no HEMS", "Hit the data limit 3 of 3 months". Each highlight names the column it is based on.

#### B. How the customer is changing

**B1. Event timeline.** Vertical, newest first. Covers the last 12 months plus future milestones.
- Contracts: `start_date`, `cancellation_received_at`, `meter_deregistered_at`, Autostrom `cancelled_at`.
- Upcoming milestones: `price_guarantee_until`, mobile `min_term_end`.
- Service: `service_interactions.created_at`, category, status, `csat_1to5`; `repeat_of_ticket_id` is marked as "repeat contact".
- Purchases: `shop_orders.order_created_at`, `product_name`, `order_status`.
- Consent: `consent_status.updated_at` when the status changed.
- Marketing sent: `nba_action_history` (offer, channel, response), excluding control-group rows.
- Each row has an icon for its business line and a tag for its data source.

**B2. Trends.** Mini charts, each stating the real time range of its data.
- **Charging** (`charge_sessions`, 06–09/2026): kWh per month; failed sessions by `failure_reason`. Mark the AC price cut on 2026-07-01. Note "roaming data can arrive up to 72 h late" (`cdr_received_at`).
- **Portal/app** (`portal_sessions`, 07–09/2026): sessions per month; views of `offers`, `tariff_overview` and `consumption_chart`, split out of `pages_viewed`.
- **Newsletter** (`newsletter_performance`, 01–09/2026): real opens and clicks, excluding `open_client_class = apple_mpp_prefetch`; `click_target` by topic.
- **Service** (12 months): tickets per quarter, latest CSAT, total `goodwill_eur`.
- **Mobile:** only 3-month aggregates exist. Show a usage/limit bar, not a trend.
- **HEMS** (`hems_telemetry_daily`, 09/2026 only): `self_consumption_rate`, `grid_export_kwh`, `heat_pump_kwh`, `ev_charging_kwh`. Missing days mean the device was offline.
- **No CLV trend.** `customer_value` is a single snapshot; say so on the card.

**B3. Contact history and fatigue**
- Contacts in the last 30 and 90 days (`nba_action_history`, `delivery_status = delivered`), response rate, and offers ignored repeatedly.
- Flag legacy actions with `consent_checked = 0`: "legacy engine sent without checking consent".
- If present: `service_nba_feedback` (`agent_action`, `customer_reaction = annoyed`).

**B4. Signals: the bridge to the right card.** Each signal has an id, description, date, source table, strength (strong / medium / weak) and the offers it triggers. Full definitions are in §6.3. Duplicate events (same `event_id` and timestamp) are removed before signals are built.

### 4.2 Right card: Next Best Action

**C1. Top action**
- Offer (`product_id` + `product_name`, `action_type`), channel, tone (Du/Sie), suggested send time.
- Expected ΔCLV (€) and confidence (high / medium / low).
- Status: proposed → approved / overridden. Nothing is sent automatically.

**C2. One-line reason** in plain language, referencing signals. Example only: "Gas meter deregistered 8 weeks ago [S1] → heat pump likely installed → StromWärme via email, +€42 expected CLV".

**C3. Reasoning chain.** A drill-down showing the path through the KG, for example:

`Customer –EMITTED→ Signal S1 –INDICATES→ Need "heat pump" –ADDRESSED_BY→ P-EN-03 –DELIVERED_VIA→ marketing_email –REQUIRES→ Consent(marketing_email = granted ✓)`

Clicking a node jumps to the matching row in the left card.

**C4. Valuation**, following `clv_method` with parameters from `value_assumptions` (details in §6.5–§6.7):

`ΔCLV = p_accept × (CLV_after_accept − CLV_now) + (1 − p_accept) × (CLV_after_reject − CLV_now) − contact_cost`

- `CLV_now = customer_value.clv_eur`.
- `CLV_after_accept`: add `annual_margin_if_bought_eur`; churn + `churn_effect_if_bought`. Shop offers add the margin only once. P-EN-02: remove the churn driver "price guarantee". P-SV-01: remove the service-related churn drivers and subtract `service_resolution_cost_eur`.
- `CLV_after_reject = CLV_now`, **except** a sales contact while the customer has an open complaint or dunning: churn + `contact_during_service_case` (0.05).
- `p_accept`: conversion rate by offer × channel × tone from `nba_action_history`, minus the control-group baseline (uplift). Always show the sample size n. If n < 30, label it "low confidence" and use the parent level (offer × channel).
- `contact_cost`: email 0.01, sms 0.08, popup 0, call 6 €.
- Shown as a small table so a marketer can re-check the calculation.

**C5. Checklist.** Each line is ✓ or ✗, with its source:
- consent for the channel;
- profiling consent;
- no exclusion;
- customer does not own the product yet;
- contact cap not exceeded (≤ N per 30 days);
- data fresh enough (e.g. flagged if roaming CDRs may still be arriving).

**C6. Alternatives**
- Two or three fallback actions with ΔCLV and why they rank lower.
- Blocked actions, each with the rule that blocks it, e.g. "P-MO-01 blocked: marketing_phone withdrawn 2025-03-02" or "All sales offers blocked: dunning_level = 2".
- Comparison with `rule_engine_v1`, using the latest `rule_id` in `nba_action_history`, e.g. "The old system would send R-SHOP-GENERIC, ΔCLV €−0.4".

**C7. Content preview** in German with the correct Du/Sie.
- A subject plus 2–3 sentences.
- No personalised prices and no false urgency.
- Service fix: apology and resolution steps, no sales content.
- No profiling consent: generic content, clearly labelled "nicht personalisiert".

**C8. Human in the loop**
- Buttons: Approve / change channel / change tone / change offer / Reject (with a reason).
- Log: inputs, rules applied, scores, final decision, reviewer, time.
- Service-agent mode: if the customer has an open ticket, the card switches to "resolve first" (P-SV-01) with suggested phrases for the agent.

### 4.3 Ontology and knowledge graph

- **Nodes:** Customer, Contract (Energy | Mobile | Autostrom), Device, Order, Ticket, Session, Signal, Need, Offer (from `product_catalog`), Channel, Consent, Exclusion, Action (history).
- **Edges:** HOLDS, OWNS_DEVICE, PLACED, RAISED, EMITTED, INDICATES, ADDRESSED_BY, DELIVERED_VIA, REQUIRES, BLOCKS, RECEIVED, RESPONDED.
- **Role of the KG:** generate candidate offers from signals, apply the rules (BLOCKS / REQUIRES) and produce the explanation path. **Ranking is always by ΔCLV.**

### 4.4 Mandatory rules

Keep every hard rule from the challenge brief:
- consent per channel;
- profiling consent required for personalisation;
- exclusions block sales content;
- payment data only as exclusion;
- human approval, no autonomous sending;
- German customer content.

Add these:
- Apply rules **before** ranking.
- Drop every candidate with ΔCLV ≤ 0.
- Payment data is used only as an exclusion.
- If data is missing, show "not enough data"; do not guess.

### 4.5 Test customers

Listed in §9 with the verified facts behind each one.

### 4.6 Output

For each customer, one JSON document `{profile, signals[], timeline[], candidates[], blocked[], chosen, explanation_path[], decision_log}`, and a UI rendered from that JSON. The full contract is in §5.4.

## 5. Shared contracts

### 5.1 Loading and parsing (`nba/data.py`, owner: Agent KG)

```python
def load_workbook(path: str) -> dict[str, pd.DataFrame]: ...
def load_events(path: str) -> list[dict]: ...
```

**`load_workbook`**
- Reads every sheet with `dtype=str` and turns empty strings into `None`.
- Parses columns ending in `_at`, `_date`, `_since`, `_until`, and `date` into timezone-naive `datetime`.
- Parses `0`/`1` flag columns into `bool`: `portal_account`, `app_installed`, `feed_in_meter`, `control_group`, `converted_within_14d`, `consent_checked`, `unsubscribed`, `esim`, `app_user`, `first_contact_resolution`, `delivered`, `bounced`.
- Parses numeric columns with `pd.to_numeric(errors="coerce")`.
- Keeps every raw row. Guest shop rows (empty `customer_id`) stay in the table but get `is_guest = True`.

**`load_events`**
- Parses the JSONL.
- Drops duplicates by `(event_id, occurred_at)`; the first one seen wins, and each dropped line is logged.
- Sorts by `ingested_at`, then `event_id`.
- Keeps `occurred_at`, `ingested_at` and, where the payload has one, `effective_date`.

Until Agent KG's version lands, other agents may use this reference version:

```python
import pandas as pd

def load_workbook(path):
    raw = pd.read_excel(path, sheet_name=None, dtype=str)
    return {name: df.where(df.notna() & (df != ""), None) for name, df in raw.items()}
```

### 5.2 Customer state (`nba/state.py`, owner: Agent KG)

```python
@dataclass(frozen=True)
class CustomerState:
    customer_id: str
    eval_time: datetime                    # default 2026-09-30T23:59:59
    snapshot_mode: str                     # "provided" | "strict_asof"
    rows: dict[str, list[dict]]            # every row per sheet for this customer, e.g. rows["energy_contracts"]
    applied_events: list[dict]             # events applied after the snapshot (empty at T0)
    revision: str                          # sha256 of the sorted rows + applied event ids

def build_states(tables, eval_time, events=None, snapshot_mode="provided") -> dict[str, CustomerState]: ...
def population(tables) -> pd.DataFrame     # one row per customer; columns for percentiles and highlights
def contacts(state, days: int) -> list[dict]
    # delivered, non-control nba_action_history rows with decided_at in (eval_time - days, eval_time]
```

Holdings helpers live in `nba/state.py` so that every agent uses the same definition. "Owned" means active contracts, `delivered` shop orders and existing devices.

```python
def active_lines(state) -> set[str]: ...    # {"electricity", "gas", "mobile", "autostrom", "smart_living"}
def owns(state, product_id: str) -> bool: ...
```

### 5.3 Provenance for tooltips

Every number or status shown on a card is a `Fact`:

```json
{"v": 605.12, "src": "customer_value.clv_eur", "updated_at": "2026-09-30", "row_key": "MG-100068"}
```

How to fill `updated_at`:
- use `record_updated_at` where the sheet has it (`customer_master`, `energy_contracts`, `mobile_contracts`, `autostrom_contracts`, `shop_orders`);
- use `consent_status.updated_at` for consents;
- use `customer_value.clv_calc_date` for value fields;
- otherwise use the row's own event time (`created_at`, `started_at`, `date`, `decided_at`).

Refresh and latency are not repeated in every fact. The card JSON carries them once, in `sources`, keyed by table, copied from the sheet `sources`. The UI joins them for the tooltip.

### 5.4 The `CustomerCard` JSON (one file per customer: `out/customers/<customer_id>.json`)

The values below are illustrative, **not expected results**. `nba/contracts.py` holds pydantic models that mirror this exactly. Top-level keys follow the spec; the extra keys are `meta`, `sources`, `alternatives`, `legacy_comparison`, `checklist`, `data_quality` and `rules`.

**Rule Center fields (26 Oct; docs/rule-center.md §6):**
- `rules`: the `RuleReport`, with `rule_set_version`, `results[]` (`rule_id`, `tier`, `name`, `result` = pass | block | defer | off | n/a, `detail`, `measured`, `until`, `tuples`), `counters[]` and `counter_line`;
- `chosen.deferred_until`, `candidates[].deferred_until` and `IndexRow.deferred_until` for held-back actions;
- `blocked[].rule_center_id` (C-xx / B-xx / U-xx) and `blocked[].until`;
- `meta.versions.rules` (the `rule_set_version`);
- the rule ID `BUSINESS-RULE` for tier 2 blocks.

The new optional fields are left out of the JSON while unset. A NO_ACTION card has an empty `checklist` (Q-KG-19).

```json
{
  "schema_version": "1.0",
  "customer_id": "MG-100068",
  "meta": {
    "eval_time": "2026-09-30T23:59:59",
    "snapshot_mode": "provided",
    "events_applied_until": null,
    "mode_default": "marketing",
    "versions": {"policy": "kg-0.1", "value_model": "clv_simple_v1", "propensity": "p-0.1", "templates": "t-0.1"},
    "state_revision": "sha256:…"
  },
  "sources": {"customer_value": {"refresh": "monthly + on major events", "latency": "~1 month"}},
  "triage": {
    "archetype": {"id": "A2", "name": "Traditional energy loyalist", "reason": "only energy contracts (electricity)"},
    "urgency_tier": "P3", "urgency_score": 212.3,
    "urgency_reasons": ["price guarantee ends in 8 days (2026-10-08) [S4]", "gas meter deregistered 20 days ago [S1]"],
    "deadline": "2026-10-08",
    "flags": [{"id": "top_clv", "label": "Top 10% CLV", "detail": "clv_eur 1,120 ≥ p90 1,023", "src": "customer_value.clv_eur"}],
    "outlier": false
  },
  "profile": {
    "header": {
      "age_band": {"v": "50–59", "src": "customer_master.birth_year", "updated_at": "…"},
      "city": {}, "household_size": {}, "tenure_years": {},
      "digital": {"portal_account": {}, "app_installed": {}, "language": {}},
      "tone": {"value": "sie", "method": "text|newsletter|default", "evidence": "Sie – 3/3 messages use 'Sehr geehrte', latest 2026-08-14", "refs": ["ticket:TK-200123"]}
    },
    "value_risk": {
      "clv_eur": {}, "annual_margin_eur": {}, "cost_to_serve_12m_eur": {}, "active_business_lines": {},
      "churn_prob_12m": {},
      "churn_drivers": [{"label": "price guarantee ends <90d", "delta": 0.10}],
      "clv_service_impact_eur": {},
      "percentiles": {"clv_all": 81, "clv_same_combo": 64, "combo": "energy"}
    },
    "products": {
      "energy": {"held": true, "items": []},
      "autostrom": {"held": false, "opportunity": true},
      "mobile": {"held": false, "opportunity": true},
      "shop": {"held": true, "items": []},
      "smart_living": {"held": false, "opportunity": true},
      "internet": {"held": null, "note": "no ownership data in mock"}
    },
    "consent": [{"type": "newsletter_email", "status": "granted", "effective_status": "granted", "doi": true, "updated_at": "…", "source": "…", "override_reason": null}],
    "channels": [{"channel": "newsletter_email", "allowed": true, "requires": ["newsletter_email"], "reason": "granted + DOI"}],
    "exclusions": [{"rule_id": "EXCL-DUNNING", "active": false, "detail": null, "src": "energy_contracts.dunning_level"}],
    "highlights": [{"text": "Has PV but no HEMS", "basis": ["energy_contracts.feed_in_meter", "hems_devices.device_type"], "rarity": "9% of customers"}],
    "trends": {"charging": null, "portal": {}, "newsletter": {}, "service": {}, "mobile_usage": null, "hems": null, "clv_note": "customer_value is a single snapshot; no CLV trend"},
    "fatigue": {"contacts_30d": 1, "contacts_90d": 3, "response_rate": 0.33, "repeatedly_ignored": ["P-SH-01"], "legacy_no_consent_check": 1, "agent_feedback": []}
  },
  "timeline": [
    {"id": "tl-001", "date": "2026-10-08", "future": true, "kind": "milestone", "line": "energy", "title": "Price guarantee ends", "src": "energy_contracts.price_guarantee_until", "ref": "contract:EC-…", "flags": []}
  ],
  "signals": [
    {"id": "S1", "label": "Gas meter deregistered", "date": "2026-09-10", "strength": "strong", "purpose": "contract",
     "src": "energy_contracts.meter_deregistered_at", "evidence": ["contract:EC-…"], "needs": ["N-HEAT-PUMP"], "offers": ["P-EN-03", "P-SL-01"]}
  ],
  "candidates": [
    {"tuple_id": "P-EN-03|newsletter_email|sie", "offer_id": "P-EN-03", "offer_name": "StromWärme", "action_type": "sales",
     "channel": "newsletter_email", "tone": "sie", "origin": "signal", "personalised": true, "need": "N-HEAT-PUMP", "signals": ["S1"],
     "checks": [{"rule_id": "CONSENT-CHANNEL", "passed": true, "detail": "newsletter_email granted, DOI 2021-…", "src": "consent_status"}],
     "valuation": {"clv_now_shown": 605.12, "clv_now_model": 605.40, "clv_after_accept": 0.0, "clv_after_reject": 605.40,
                   "p_accept": 0.014, "p_source": {"mode": "uplift", "level": "global", "n_treated": 2022, "conv_treated": 69, "n_control": 248, "conv_control": 5},
                   "contact_cost": 0.01, "delta_clv": 0.0, "confidence": "low"},
     "rank": 1,
     "why": ["Gas meter deregistered on 2026-09-10 [S1] → heat pump likely", "Newsletter consent granted with double opt-in"],
     "notes": ["No sales history for P-EN-03: p is the catalog average (low confidence)"],
     "path": []}
  ],
  "blocked": [{"offer_id": "P-MO-01", "channel": "outbound_call", "rule_id": "CONSENT-CHANNEL", "reason": "marketing_phone withdrawn 2025-03-02", "src": "consent_status"}],
  "chosen": {
    "tuple_id": "P-EN-03|newsletter_email|sie", "status": "proposed", "send_at": "2026-10-01T10:00:00",
    "reason_line": "Gas meter deregistered 3 weeks ago [S1] → likely heat pump → StromWärme via newsletter, +€X expected CLV",
    "service_mode": false, "agent_script": null,
    "content": {"language": "de", "tone": "sie", "personalised": true, "template_id": "P-EN-03.sie.p", "subject": "…", "body": "…"}
  },
  "alternatives": [{"tuple_id": "P-EN-02|newsletter_email|sie", "delta_clv": 0.0, "why_lower": "lower expected ΔCLV (−€Y)"}],
  "legacy_comparison": {"rule_id": "R-SHOP-GENERIC", "offer_id": "P-SH-01", "channel": "newsletter_email", "decided_at": "…", "delta_clv_our_model": -0.4, "blocked_now_by": []},
  "explanation_path": [
    {"kind": "node", "type": "Customer", "id": "MG-100068", "ui_ref": "header"},
    {"kind": "edge", "type": "EMITTED"},
    {"kind": "node", "type": "Signal", "id": "S1", "ui_ref": "signal:S1"},
    {"kind": "edge", "type": "INDICATES"},
    {"kind": "node", "type": "Need", "id": "N-HEAT-PUMP"},
    {"kind": "edge", "type": "ADDRESSED_BY"},
    {"kind": "node", "type": "Offer", "id": "P-EN-03"},
    {"kind": "edge", "type": "DELIVERED_VIA"},
    {"kind": "node", "type": "Channel", "id": "newsletter_email"},
    {"kind": "edge", "type": "REQUIRES"},
    {"kind": "node", "type": "Consent", "id": "newsletter_email", "label": "granted (DOI) ✓", "ui_ref": "consent:newsletter_email"}
  ],
  "checklist": [{"item": "consent_for_channel", "passed": true, "detail": "…", "src": "consent_status"}],
  "data_quality": [{"code": "FRESH-CDR", "level": "warn", "detail": "roaming CDRs for the last 72 h may be incomplete"}],
  "decision_log": [{"ts": "…", "actor": "engine", "action": "proposed", "tuple_id": "…", "reason": null, "state_revision": "…", "versions": {}}]
}
```

**`ui_ref` values.** The UI uses these to jump from a path node to the left card:
- `header`, `value`
- `product:<line>`
- `consent:<type>`
- `exclusion:<rule_id>`
- `signal:<Sx>`
- `timeline:<id>`
- `trend:<name>`

**`chosen` when nothing qualifies.** `chosen.tuple_id = "NO_ACTION"`, and `reason_line` explains why: everything blocked, or no candidate with ΔCLV > 0.

**`blocked` rows with `offer_id = "*"`** apply to every non-service offer of the customer: an active exclusion, the contact cap, or no consented marketing channel. With `channel` set, the row means that channel is blocked for every offer (e.g. "outbound call not allowed for any offer: marketing_phone withdrawn on 2023-03-09").

**`out/index.json`** has one row per customer for the overview page:

```json
{"customer_id": "…", "age_band": "…", "city": "…", "lines": 1, "clv_eur": 0, "churn": 0,
 "archetype": "A2", "archetype_name": "Traditional energy loyalist",
 "urgency_tier": "P3", "urgency_score": 212.3, "top_reason": "price guarantee ends in 8 days [S4]",
 "flags": ["top_clv"], "outlier": false, "triggers": ["S1", "S4"],
 "chosen_offer": "P-EN-03", "chosen_tuple": "P-EN-03|newsletter_email|sie", "channel": "newsletter_email", "tone": "sie",
 "delta_clv": 0, "p_accept": 0.034, "contact_cost": 0.01, "confidence": "low", "checklist_failed": [],
 "service_mode": false, "personalised": true,
 "n_signals": 2, "n_candidates": 5, "n_blocked": 4, "exclusions": []}
```

**`out/summary.json`** holds the aggregates:
- chosen offers: count and ΣΔCLV;
- blocked tuples by `rule_id`;
- customers with NO_ACTION, by reason;
- signal counts;
- archetype, urgency-tier and flag counts;
- `sources` (refresh/latency per table), `column_src` (each `IndexRow` number → `table.column`) and `value_date`, so worklist numbers get tooltips too.

### 5.5 IDs and enums

| Name | Values |
|---|---|
| Channels | `newsletter_email`, `email`, `portal_popup`, `app_push`, `sms`, `outbound_call`, and `service_agent` (service actions only) |
| Consent types | `newsletter_email`, `marketing_email`, `marketing_phone`, `marketing_sms`, `portal_app_personalisation`, `profiling_analytics` |
| Tone | `du`, `sie` |
| Action types | `sales`, `upsell`, `retention`, `one_off`, `service` (from `product_catalog.action_type`) |
| Signal strength | `strong`, `medium`, `weak` |
| Signal purpose | `contract`, `device`, `behavioural`, `service` (§6.3; drives the profiling rule) |
| Decision status | `proposed`, `approved`, `overridden`, `rejected` (+ `revoked` for event replay, stretch goal) |
| Confidence | `high`, `medium`, `low` (§6.6) |
| Candidate origin | `signal` (personalised, from S1–S11), `service` (P-SV-01 from S2/S12/S13), `generic` (non-personalised catalog offer, §6.12) |
| Archetypes | `A1` Smart eco-system adopter, `A2` Traditional energy loyalist, `A3` EV driver, `A4` Retention risk (do no harm), `A5` Growing connected household, `A0` Other (§6.13) |
| Urgency tiers | `P1` act now (service), `P2` high, `P3` time-bound opportunity, `P4` opportunity, `P5` no trigger (§6.13) |
| Flags | `service_critical`, `no_marketing_channel`, `no_profiling`, `negative_clv`, `top_clv`, `contact_fatigue`, `annoyed_before`, `prefers_en`, `data_inconsistent` (§6.13) |
| Rule IDs | `CONSENT-CHANNEL`, `CONSENT-PROFILING`, `CHANNEL-AVAILABLE`, `EXCL-DUNNING`, `EXCL-CANCELLATION`, `EXCL-OPEN-TICKET`, `EXCL-AUTOSTROM-CANCELLED`, `HOLDING-PRECONDITION`, `CONTACT-CAP`, `ECON-NONPOSITIVE`, `DATA-MISSING` |

### 5.6 Module interfaces (stubs must exist by M0, §8)

```python
# Agent KG — nba/kg/*.py
def load_policy(path="kg/policy.yaml") -> Policy
def extract_signals(state, policy) -> list[Signal]
def generate_candidates(state, signals, policy, tone: str) -> tuple[list[Candidate], list[Blocked]]
    # builds (offer, channel, tone) tuples and applies every gate in §6.2-6.4 + contact cap;
    # returns candidates WITHOUT valuation and blocked items with rule_id
def explain(state, candidate, policy) -> list[PathStep]
def customer_graph(state, policy) -> networkx.MultiDiGraph
def triage(state, signals, policy, pop) -> Triage                  # archetype, urgency, flags (§6.13)
def consent_view(state, policy) -> list[ConsentItem]               # profile.consent (CARDS reuses it)
def channel_view(state, policy) -> list[ChannelItem]               # profile.channels (CARDS reuses it)
def exclusion_view(state, policy) -> list[ExclusionItem]           # profile.exclusions (CARDS reuses it)
def data_quality(state) -> list[DataQuality]                       # §6.9; NBA adds it to the checklist
def check_tuple(state, offer_id, channel, policy) -> list[Blocked] # hard-rule blockers of one tuple; [] = allowed
                                                                   # (override 409, legacy_comparison.blocked_now_by)
def kg_bundle(state, policy, pop, tone) -> KGBundle                # all of the above for one customer (nba/kg/bundle.py)
def replay(states, events, policy, pop, until=None, pending=None) -> ReplayResult
                                                                   # deep dive B (nba/kg/events.py, §6.14)
def source_info(tables) -> dict[str, SourceInfo]                   # CustomerCard.sources / Summary.sources

# Agent CARDS — nba/profile/*.py
def infer_tone(state) -> Tone             # value + method + evidence; NBA imports this
def build_profile(state, pop) -> Profile  # header, value_risk, products, consent, channels, exclusions,
                                          # highlights, trends, fatigue
def build_timeline(state) -> list[TimelineItem]

# Agent NBA — nba/engine/*.py
def churn_breakdown(state) -> ChurnBreakdown        # §6.5
def clv(margin, cost, churn, r=0.06, years=10) -> float
def p_accept(offer_id, channel, tone, history, cfg) -> Propensity
def value(candidate, state, propensity, cfg) -> Valuation
def rank(candidates) -> tuple[Candidate | None, list[Candidate]]   # drops ΔCLV ≤ 0 into blocked (ECON-NONPOSITIVE)
def render_content(chosen, tone, personalised: bool) -> Content
def assemble(state, pop, policy, cfg) -> CustomerCard
```

## 6. Business logic reference

### 6.1 Channel → consent map (owner: Agent KG, in `kg/policy.yaml`)

| Channel | Required consent | Extra condition | Contact cost € (from `value_assumptions`) |
|---|---|---|---|
| `newsletter_email` | `newsletter_email = granted` and `double_opt_in_confirmed_at` set | No `unsubscribed = 1` row in `newsletter_performance` (otherwise `effective_status = withdrawn`) | 0.01 |
| `email` | `marketing_email = granted` | — | 0.01 |
| `outbound_call` | `marketing_phone = granted` | — | 6.00 |
| `sms` | `marketing_sms = granted` | — | 0.08 |
| `portal_popup` | `portal_app_personalisation = granted` | `customer_master.portal_account = 1` | 0 |
| `app_push` | `portal_app_personalisation = granted` | `customer_master.app_installed = 1` | 0 |
| `service_agent` | none for service content; **never carries sales content** | Only for P-SV-01 | 0 (the 15 € resolution cost is in the accept branch) |
| Any personalised content | `profiling_analytics = granted` | Otherwise generic content and only non-behavioural signals (§6.3) | — |

Contact costs have **one source**: the workbook sheet `value_assumptions` (`contact_cost_*_eur`), read by Agent NBA. They are not duplicated in `kg/policy.yaml` (Q-KG-20, decided 26 Oct).

`not_given` and `withdrawn` are both treated as not allowed. Unknown also counts as not allowed.

### 6.2 Exclusions (owner: Agent KG)

| Rule | Predicate | Blocks |
|---|---|---|
| `EXCL-DUNNING` | Any `energy_contracts.dunning_level ≥ 1` | `sales`, `upsell`, `retention`, `one_off` |
| `EXCL-CANCELLATION` | Any `energy_contracts.status = cancellation_pending` | Same |
| `EXCL-OPEN-TICKET` | Any `service_interactions.status = open` (complaint is shown as the strongest) | Same |
| `EXCL-AUTOSTROM-CANCELLED` | Any `autostrom_contracts.status = cancelled` | Same (scope is open question K6) |

Exclusions never block `service` (P-SV-01). Dunning data is payment data: use it only to exclude and to route to service (S13). Never use it as a feature or in content.

### 6.3 Signals (owner: Agent KG)

S1–S11 come from the spec. S12 and S13 are the service triggers that spec C8 and the test customers require. Offers that no signal points to are reached only through the **generic path** (§6.12), never through invented signals.

The evaluation date is `eval_time.date()`. "Active" means `status = active`. "Owned" uses `owns()` (§5.2).

| ID | Exact definition | Strength | Purpose | Need | Offers |
|---|---|---|---|---|---|
| S1 | Energy contract with `commodity = gas` and `meter_deregistered_at` set (date = `meter_deregistered_at`). Event `gas_meter_deregistration_received` → use `payload.effective_date` as the effective date | strong | contract | N-HEAT-PUMP | P-EN-03, P-SL-01 |
| S2 | ≥ 3 `charge_sessions` with `session_status = failed` and `started_at` in (eval − 30 d, eval] | strong | service | N-SERVICE-FIX | P-SV-01 |
| S3 | Delivered shop order `product_name = "Wallbox 11 kW"` and no active Autostrom | strong | behavioural | N-EV-CHARGING | P-AS-01, P-SL-03 |
| S4 | Active energy contract with 0 ≤ (`price_guarantee_until` − eval date) < 90 days | strong | contract | N-PRICE-SECURITY | P-EN-02 |
| S5 | Active mobile with `data_limit_reached_3m ≥ 2` | medium | behavioural | N-MORE-DATA | P-MO-02 |
| S6 | Active mobile and `household_size > sim_count` | weak | contract | N-EXTRA-SIM | P-MO-03 |
| S7 | (`feed_in_meter = 1` on active electricity, or device `pv_inverter`) and no `hems_gateway` | medium | device | N-ENERGY-MANAGEMENT | P-SL-01 |
| S8 | `hems_gateway` + `home_battery` → P-SL-02. `hems_gateway` + (`wallbox` device or active Autostrom) → P-SL-03 | medium | device | N-STORAGE-OPT / N-WALLBOX-INTEGRATION | P-SL-02 / P-SL-03 |
| S9 | Active electricity with `meter_type = smart_meter_imsys` and (`hems_gateway` or active Autostrom or `heat_pump` device or tariff StromWärme) | medium | device | N-DYNAMIC-TARIFF | P-EN-05 |
| S10 | Human click (`clicked_at` set) on `heat_pump_article` or `smart_living_landingpage`, or event `newsletter_clicked` with these targets | weak | behavioural | Reinforces N-HEAT-PUMP / N-ENERGY-MANAGEMENT | None on its own; evidence only, does not change p |
| S11 | Active Autostrom and no active electricity contract | medium | contract | N-HOME-ELECTRICITY | P-EN-01 |
| S12 | Any ticket with `status = open` (strongest for `category = complaint`) | strong | service | N-SERVICE-FIX | P-SV-01 |
| S13 | Active `EXCL-DUNNING` or `EXCL-CANCELLATION` | strong | service | N-SERVICE-FIX | P-SV-01 |

**Not generated:**
- P-EN-04 GasAktiv: gas heating is unknown in the data.
- P-IN-01 Internet: no availability or ownership data exists.

List both once per customer in `blocked` with `DATA-MISSING`, reason "not enough data".

**Profiling rule (decision D1, team, 26 Oct 2026).** If `profiling_analytics ≠ granted`, only non-personalised logic is allowed:
- **No signal is used for marketing.** Every marketing signal (S1, S3–S11) is listed in `blocked` with `CONSENT-PROFILING`, e.g. "S3 wallbox purchase ignored: no profiling consent".
- **Marketing candidates come only from the generic path** (§6.12): catalog offers valued with the catalog-wide average p. Products the customer already owns are removed, because that check uses contract data only.
- Content is generic (`personalised = false`, labelled "nicht personalisiert"); tone is the default Sie.
- **Service** actions (S2, S12, S13 → P-SV-01) are unaffected.

**Signal counts** at eval 2026-09-30, produced by `nba/kg` and checked by `tests/test_kg_signals.py`:

| Signal | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | S13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Customers | 12 | 2 | 16 | 143 | 11 | 80 | 66 | 33 | 48 | 33 | 161 | 29 | 39 |

- S2 fires for exactly MG-100009 and MG-100659.
- S4 counts any active energy contract. The churn driver "price guarantee ends <90d" appears for 145 customers; the 2-customer gap is open question Q-KG-06.

### 6.4 Needs and offer preconditions (owner: Agent KG)

**Needs** (each has `label_en` and `label_de`):

| Need | Meaning |
|---|---|
| N-HEAT-PUMP | Heat pump / electric heating |
| N-SERVICE-FIX | Problem to resolve |
| N-EV-CHARGING | Charging contract for an EV |
| N-PRICE-SECURITY | Price certainty |
| N-MORE-DATA | More mobile data |
| N-EXTRA-SIM | Extra SIM for the household |
| N-ENERGY-MANAGEMENT | Use own PV energy |
| N-STORAGE-OPT | Optimise the home battery |
| N-WALLBOX-INTEGRATION | Smart charging at home |
| N-DYNAMIC-TARIFF | Benefit from flexible prices |
| N-HOME-ELECTRICITY | Home electricity for an EV driver |

**Preconditions.** These are REQUIRES / NOT-HELD edges, checked by `HOLDING-PRECONDITION`.

| Offer | Requires | Must not hold |
|---|---|---|
| P-EN-01 StromAktiv | — | Active electricity |
| P-EN-02 StromGarant | Active electricity; the churn driver "price guarantee ends <90d" is present | — |
| P-EN-03 StromWärme | — | Tariff StromWärme |
| P-EN-05 Dynamischer Stromtarif | Active electricity with `smart_meter_imsys` | — |
| P-MO-01 Mobil S/M/L | — (generic offer: only owned products are removed, D1; Q-KG-21) | Active mobile |
| P-MO-02 Mobil Upgrade | Active mobile | — |
| P-MO-03 Zusatz-SIM | Active mobile | — |
| P-SL-01 HEMS Starter-Set | — | `hems_gateway` |
| P-SL-02 HEMS Speicher-Optimierung | `hems_gateway` + `home_battery` | — |
| P-SL-03 Wallbox-Integration | `hems_gateway` + (wallbox device or active Autostrom) | — |
| P-SH-01 Balkonkraftwerk | — | Delivered Balkonkraftwerk / PV |
| P-SH-02 Wallbox 11 kW | — | Wallbox device or delivered Wallbox |
| P-SH-03 Smarte Thermostate | — | Delivered thermostats |
| P-SH-04 Smart Plug 4er-Set | — | Smart plug device or delivered order |
| P-AS-01 Autostrom | — | Active Autostrom |
| P-SV-01 Service | S2, S12 or S13 present | — |

**Default channels** for marketing offers: every channel in §6.1 except `service_agent`. P-SV-01 uses only `service_agent`.

**Generic offers** (`config/kg.yaml: generic.offers`): P-EN-01, P-MO-01, P-SL-01, P-SH-01, P-SH-03, P-SH-04. These are offers whose eligibility can be checked from contract data alone. Need-specific offers (P-EN-03 heat pump, P-EN-05 smart meter + device, P-AS-01 and P-SH-02 EV, P-SL-02/03 HEMS upsells, P-MO-02 usage, P-MO-03 household, P-EN-02 retention timing) are never offered generically. P-EN-04 and P-IN-01 stay `DATA-MISSING`. A generic tuple only drops products the customer already owns (the "must not hold" column); no other precondition applies (D1).

### 6.5 CLV and churn model (owner: Agent NBA)

**CLV formula** (`clv_method`, `value_assumptions`):

```text
CLV(margin, cost, churn) = Σ_{t=1..10} (margin − cost) · (1 − churn)^(t−1) / 1.06^t
margin = customer_value.annual_margin_eur
cost   = customer_value.cost_to_serve_12m_eur
```

**Churn reconstruction.** Verified exact for all 718 customers with an active line.

```text
churn = mean(base churn of active contracts) × max(0.8^(active_business_lines − 1), 0.5)
        + Σ driver increments
```

- **Base churn per contract:** electricity 0.14, gas 0.12, mobile 0.18, Autostrom 0.20. Energy contracts with status `active` or `cancellation_pending` count as active.
- **`active_business_lines`** comes from `customer_value`. Energy counts as one line; HEMS (smart_living) counts as a line.
- **Driver increments** (from `churn_drivers`), added *after* the multi-line factor:

  | Driver | Increment |
  |---|---|
  | price guarantee ends <90d | +0.10 |
  | open complaint | +0.12 |
  | "N tickets in 12m" (N ≥ 2) | +0.04, once |
  | low CSAT | +0.05 |
  | dunning level ≥ 2 | +0.08 |
  | 3 failed charges in 30d | +0.10 |
  | HEMS user | −0.04 |

  "multi-product (k lines)" is a label, not an increment.
- **Special cases:** cancellation pending → churn = 0.95. 24 customers have no active line; use `churn_prob_12m` as given.

**Valuation per tuple** (spec C4; the defaults close gaps the spec leaves open):

| Branch / offer type | Rule |
|---|---|
| Basis | `CLV_now_model = CLV(margin, cost, churn_prob_12m)`. Compute every ΔCLV on this model basis, so the rounding in the given `clv_eur` (up to 3.05 €) never shows up as gain. Display `clv_eur` as `CLV_now`; log both |
| Sales / upsell accept | `CLV(margin + annual_margin_if_bought, cost, clamp(churn + churn_effect_if_bought))`. Do not also apply the multi-line factor or a +12 € line cost; that would double-count (K7) |
| One-off shop accept | `CLV(margin, cost, clamp(churn + churn_effect_if_bought)) + annual_margin_if_bought`, with the margin added once |
| P-EN-02 accept | churn − 0.10 (the price-guarantee driver). Do not apply the catalog −0.10 as well |
| P-SV-01 accept | churn − Σ service increments present (open complaint, tickets, low CSAT, failed charges, dunning), then − 15 € (`service_resolution_cost_eur`). Cancellation pending stays at 0.95 |
| Reject | `CLV_now_model`, except a sales tuple while an open complaint or dunning ≥ 1 exists: churn + 0.05. This only affects valuations of blocked tuples and the legacy comparison, because exclusions already block such tuples |
| Clamp | churn ∈ [0, 0.95]; full precision internally; round to 2 decimals only for display |

Log every component of a valuation, not only the final number.

### 6.6 p_accept (owner: Agent NBA)

**Data:**
- *Treated* = `control_group = 0` and `delivery_status = delivered`.
- *Control* = `control_group = 1`.
- *Conversion* = `converted_within_14d = 1`. `agent_action = accepted` is not a conversion.

**Backoff levels:**

| Level | Grouping |
|---|---|
| L3 | offer × channel × tone |
| L2 | offer × channel |
| L1 | offer |
| L0 | global |

Use the first level where `n_treated ≥ 30`. L1 and L0 are an extension, because the spec stops at L2 and 8 offers have no history at all.

**Mode `rate`** (default since 26 Oct, K1):
- `p = (conv + 0.034·30) / (n + 30)`, i.e. the treated conversion rate shrunk toward the global 3.4% with pseudo-count 30.
- Why it is the default: the team confirmed MG-100023 as the P-AS-01 test case. Under `uplift`, P-AS-01 (0/203 treated, 0/21 control) always gets p = 0 and could never be recommended.
- The uplift against control is still computed and shown next to p as evidence ("vs control: 0/21, not significant").

**Mode `uplift`** (spec wording, kept for comparison and reported in `out/test_report.md`):
- `p = max(0, rate_treated − baseline_control)`.
- `baseline_control` is the offer's own control rate if that offer has `n_control ≥ 30`, otherwise the global control rate 5/248 = 2.0%.
- The L0 prior is 69/2,022 − 5/248 = 1.4%.

**Generic offers** (§6.12) always use L0, the catalog-wide average: 69/2,022 = 3.4% in `rate` mode, 1.4% in `uplift` mode. That is what "non-personalised, based on the catalog average" means (D1).

**P-SV-01** has no history. It uses `p_service_success = 0.5`, an editable assumption labelled low confidence (K2).

**Confidence:**

| Label | Rule |
|---|---|
| high | L3 with n ≥ 100 |
| medium | L3 with 30 ≤ n < 100 |
| low | Anything else, including any n < 30 (spec) |

Always show n, the conversions, the level, the mode and the control baseline in the valuation table.

**Offer-level reference** (treated vs control). Use it to sanity-check your output:

| Offer | Treated | Control | Uplift with own control | Uplift with global 2.0% |
|---|---|---|---|---|
| P-AS-01 | 0/203 | 0/21 | 0.000 | −0.020 |
| P-EN-02 | 16/209 | 1/19 | 0.024 | 0.056 |
| P-EN-05 | 1/218 | 1/22 | −0.041 | −0.016 |
| P-IN-01 | 4/184 | 1/24 | −0.020 | 0.002 |
| P-MO-01 | 22/213 | 0/24 | 0.103 | 0.083 |
| P-MO-02 | 1/191 | 0/20 | 0.005 | −0.015 |
| P-SH-01 | 7/204 | 0/30 | 0.034 | 0.014 |
| P-SH-02 | 4/198 | 1/28 | −0.016 | 0.000 |
| P-SH-03 | 11/211 | 1/28 | 0.016 | 0.032 |
| P-SL-01 | 3/191 | 0/32 | 0.016 | −0.004 |

Only 20 of the 50 offer × channel cells have n ≥ 30.

**Product catalog values** (`product_catalog`):

| Offer | Line | Type | Margin € | Churn effect |
|---|---|---|---|---|
| P-EN-01 | energy | sales | 114 | −0.02 |
| P-EN-02 | energy | retention | 0 | −0.10 |
| P-EN-03 | energy | sales | 140 | −0.02 |
| P-EN-04 | energy | sales | 111 | −0.02 |
| P-EN-05 | energy | sales | 20 | −0.03 |
| P-MO-01 | mobile | sales | 54 | −0.02 |
| P-MO-02 | mobile | upsell | 18 | −0.03 |
| P-MO-03 | mobile | upsell | 29 | −0.01 |
| P-IN-01 | internet | sales | 130 | −0.03 |
| P-SL-01 | smart_living | sales | 36 | −0.04 |
| P-SL-02 | smart_living | upsell | 36 | −0.01 |
| P-SL-03 | smart_living | upsell | 24 | −0.01 |
| P-SH-01 | shop | one_off | 90 | −0.01 |
| P-SH-02 | shop | one_off | 126 | −0.01 |
| P-SH-03 | shop | one_off | 23 | 0 |
| P-SH-04 | shop | one_off | 9 | 0 |
| P-AS-01 | e_mobility | sales | 85 | −0.02 |
| P-SV-01 | service | service | 0 | removes service drivers |

**Calibration (team decision, 27 Oct).** After the estimate above, p is scaled by the engine's own track record for the same offer × channel × tone (the action type follows from the offer):
- k = (buys observed + 5) / (buys the model expected + 5), kept within [0.2, 3]; p_new = p × k (uplift mode: the rate is scaled, then the control baseline is subtracted);
- the 5 pseudo-buys keep k near 1 when a group has little evidence; with plenty of evidence k approaches the plain ratio (3 bought where 10 were expected: 0.3);
- not applied to catalog offers (D1 keeps the catalog average), the service assumption or reviewed overrides;
- settings in `config/nba.yaml → calibration`; `Valuation.p_source.k` and the evidence line show it.

On the mock data 254 candidate tuples are calibrated (k 0.73–1.13) and 12 decisions change. Example: MG-100019 moves from StromGarant by newsletter (ΔCLV €13.19) to StromGarant by app push (€11.40).

### 6.7 Contact cost, contact cap and send time (owner: Agent NBA; cap computed by Agent KG)

**Contact cost:**

| Channel | € |
|---|---|
| `newsletter_email`, `email` | 0.01 |
| `sms` | 0.08 |
| `portal_popup`, `app_push`, `service_agent` | 0 |
| `outbound_call` | 6 |

**Contact cap (Rule Center B-02).** `N = 2` marketing contacts per rolling 30 days, `(t − 30 d, t]`, counted by the shared counter `nba.kg.contacts`:
- sources are set in `config/kg.yaml contact_cap.sources`: delivered NBA history plus offers a service agent mentioned; newsletters count only in B-01 (R1);
- service actions are exempt;
- a capped customer's tuples are **held back** until the cap frees up (DEFER_UNTIL), not dropped (docs/rule-center.md §5).

**Suggested send time:**

| Channel | Rule |
|---|---|
| Email and newsletter | Next weekday 10:00 after `eval_time` |
| `sms` | Next weekday 18:00 |
| `outbound_call` | Next weekday 10:00–16:00 |
| `portal_popup`, `app_push` | "next login" |
| `service_agent` | "immediately, with the open ticket" |

For P-EN-02 also show "send before `price_guarantee_until`".

### 6.8 Tone inference (owner: Agent CARDS; Agent NBA imports `infer_tone`)

1. **Customer-side text only.** Use `service_interactions.message_text` and the `Kunde:` lines of `call_transcripts.transcript`.
   - Du cues (case-insensitive, word boundaries): `hi`, `hey`, `danke dir`, `tschüss`, `\bdu\b`, `\bdir\b`, `\bdein\w*`, `lg`, `viele grüße` (weak).
   - Sie cues: `sehr geehrte`, `mit freundlichen grüßen`, `\bIhnen\b`, `\bIhr(e|en|em|er)?\b` (capitalised mid-sentence).
   - Decide by majority over messages. Evidence format: "Du – 2/2 messages use 'du', latest 2026-08-14".
2. If there is no text signal: use newsletter clicks by campaign `tonality`, and only with ≥ 2 human clicks and a clear majority. Note that every campaign went to all subscribers, so this is weak evidence.
3. Otherwise default to `sie`, labelled "default".
4. If `profiling_analytics ≠ granted`: tone is always the default `sie` (K3).
5. The 7 customers with `preferred_contact_language = en` still get German content; show the note "prefers EN; content stays DE per challenge rules".

### 6.9 Freshness and data quality (owner: Agent KG computes, Agent NBA puts it in the checklist)

These are flags shown as ⚠ in the checklist. **They never block.**

| Code | Condition |
|---|---|
| `FRESH-CDR` | The tuple depends on `charge_sessions` and the customer has roaming sessions in the last 72 h before `eval_time` |
| `FRESH-HEMS` | The gateway `connection_status` is not online, or September telemetry has missing days |
| `FRESH-VALUE` | `clv_calc_date` is more than 31 days before `eval_time` |
| `SNAPSHOT-INCONSISTENT` | The customer is affected by one of the inconsistencies listed in §3 |

### 6.10 Decision states and log (owner: Agent NBA)

- **States:** `proposed` → `approved` | `overridden` | `rejected`.
- **Overrides re-run every gate** for the new tuple. A blocked override is refused (API returns 409 with the rule IDs).
- **Log entry fields:** `ts`, `actor` (engine or user name), `action`, `from_tuple`, `to_tuple`, `reason`, `state_revision`, `versions`, `rules_applied`, `scores`.
- Logs are append-only, in `out/decision_log.jsonl`.

### 6.11 Ontology (owner: Agent KG, `kg/ontology.yaml`)

- **Customer instance layer.** Built per customer from tables:

  | Node | ID |
  |---|---|
  | Customer | `customer_id` |
  | Contract (subtype Energy / Mobile / Autostrom) | `contract_id` |
  | Device | `device_id` |
  | Order | `order_id` (unique per order line) |
  | Ticket | `ticket_id` |
  | Session | `session_id` |
  | Consent | `customer_id` + type |
  | Exclusion | instance per active rule |
  | Action | history `action_id` |
  | Signal | `customer_id` + Sx |

- **Policy layer.** Static YAML: Need, Offer, Channel, ConsentType, ExclusionRule, SignalType, Archetype (A0–A5; a node is added per customer for that customer's archetype).
- **Edges (spec):**

  | Edge | From → To |
  |---|---|
  | HOLDS | Customer → Contract; Customer → Consent |
  | OWNS_DEVICE | Customer → Device |
  | PLACED | Customer → Order |
  | RAISED | Customer → Ticket |
  | EMITTED | Customer → Signal |
  | INDICATES | Signal → Need |
  | ADDRESSED_BY | Need → Offer |
  | DELIVERED_VIA | Offer → Channel |
  | REQUIRES | Channel → Consent; Offer → precondition |
  | BLOCKS | Exclusion → Offer, by action type |
  | RECEIVED | Customer → Action (delivered only; control rows use HELD_OUT) |
  | RESPONDED | Customer → Action, with property `response` |

- **Extension edges and nodes:**
  - `EVIDENCED_BY`: Signal → Contract / Order / Ticket / Session / Device / Campaign (S10 clicks).
  - `HAS_SESSION`: Contract → Session.
  - `HELD_OUT`: Customer → Action for control-group rows that were never sent.
  - `REINFORCES`: S10 → Need (evidence only, no tuple).
  - `INSTANCE_OF`: Signal / Exclusion / Consent instance → SignalType / ExclusionRule / ConsentType.
  - `IN_ARCHETYPE`: Customer → Archetype.
  - `GENERIC_OFFER`: Customer → Offer in the explanation path of a generic (non-personalised) tuple (D1).
  - `REQUIRES` also links every need-based offer to `consent:profiling_analytics` (D1), so the profiling rule is visible in the graph.
  - Channel and consent-type nodes are namespaced in the graph (`channel:email`, `consent:marketing_email`) because they share names.
  - `Feedback` node, `GAVE_FEEDBACK`: Customer → Feedback, `ABOUT`: Feedback → Offer / Channel. Customer memory written by the feedback loop (§6.17): what a person said no to, remembered for that customer until a date.
- **Division of labour:** rules are declared in YAML and evaluated by named Python predicates. Scoring lives in code. Customer data stays in tables; the graph is built per customer on demand, so there is no graph database.

### 6.12 Candidate tiers and arbitration (owner: Agent KG builds tiers, Agent NBA ranks)

Rules are applied before any ranking. Then:

1. **Signal and service tuples.** For customers with profiling consent: tuples from S1–S13. For customers without it: only service tuples (S2, S12, S13 → P-SV-01).
2. **Generic tuples** (non-personalised, `origin = generic`):
   - without profiling consent: always evaluated, next to the service tuples;
   - with profiling consent: evaluated only when no signal or service tuple has ΔCLV > 0 (`generic.fallback_for_profiled`, K12). This keeps need-first ranking: a real need signal is never outbid by a generic push.
3. Rank by ΔCLV inside the evaluated set; drop ΔCLV ≤ 0 (`ECON-NONPOSITIVE`). If nothing remains, the decision is `NO_ACTION` with the reason.

**Generic channels (decided, K11, 26 Oct):** every consented and available channel, including phone and SMS (`generic.allowed_channels: all`); the economics decide. With the only channel being a 6 € call, a generic offer can still be positive. For MG-100112, StromAktiv by phone breaks even at p ≈ 0.98%, so at the catalog average it is +€14.87 (`rate`) or +€2.54 (`uplift`), and the decision is a generic StromAktiv call.

### 6.13 Triage: archetypes, urgency and flags (owner: Agent KG, `nba/kg/segments.py`)

**Archetypes** are rule-based, first match wins. They never use age or payment data except the exclusion flags themselves. Counts at eval 2026-09-30:

| ID | Name | Rule | Count | CLV median | Churn median |
|---|---|---|---|---|---|
| A4 | Retention risk (do no harm) | Any active exclusion (§6.2) or `churn_prob_12m ≥ 0.35` | 75 | 322 | 0.28 |
| A1 | Smart eco-system adopter | `hems_gateway` device | 33 | 932 | 0.07 |
| A3 | EV driver | Active Autostrom | 201 | 517 | 0.20 |
| A5 | Growing connected household | Active mobile and (`household_size > sim_count` or `data_limit_reached_3m ≥ 1`) | 50 | 660 | 0.14 |
| A2 | Traditional energy loyalist | Only energy contracts (electricity and/or gas) | 342 | 498 | 0.17 |
| A0 | Other | Everything else | 49 | 256 | 0.22 |

Representative customers: MG-100325 (A1) and MG-100001 (A2).

**Urgency tiers**, first match wins. The urgency score orders the worklist inside a tier:

| Tier | Meaning | Rule | Count |
|---|---|---|---|
| P1 | Act now (service) | `cancellation_pending`, open complaint, `dunning_level ≥ 2`, or S2 | 53 |
| P2 | High | Any other open ticket, `dunning_level = 1`, price guarantee ends in ≤ 30 days, or churn ≥ 0.35 | 62 |
| P3 | Time-bound opportunity | Price guarantee ends in 31–89 days, gas meter deregistered within 90 days, or S5 | 95 |
| P4 | Opportunity | Any other signal (except S10) | 261 |
| P5 | No trigger | — | 279 |

`urgency_score = 100 × (5 − tier number) + min(99, max(0, clv_eur) × churn_prob_12m / 10)`. In words: the tier first, then the CLV at risk. `urgency_reasons` lists the facts in plain language, each with its signal or rule ID. `deadline` is set when a date drives the tier.

**Flags** (shown as badges):

| Flag | Rule | Count |
|---|---|---|
| `service_critical` | Tier P1 | 53 |
| `no_marketing_channel` | No consented and available marketing channel | 51 |
| `no_profiling` | `profiling_analytics ≠ granted` | 289 |
| `negative_clv` | `clv_eur < 0` | 31 |
| `top_clv` | `clv_eur ≥ p90` (1,023 €) | 75 |
| `contact_fatigue` | ≥ 2 contacts in 30 days or ≥ 3 ignored/dismissed in 90 days | 188 |
| `annoyed_before` | `service_nba_feedback` with `customer_reaction = annoyed` or `dismiss_reason = customer_upset` | 32 |
| `prefers_en` | `preferred_contact_language = en` | 7 |
| `data_inconsistent` | Late CDRs after the cutoff, or TK-200565 / TK-200640 | 71 |

**Outlier** ("special need") = any of `service_critical`, `no_marketing_channel`, `negative_clv`, `annoyed_before`, `prefers_en` (154 customers). These customers need individual handling and are never bulk-approved without a second look. `top_clv` is a VIP badge, not an outlier.

Counts are from Agent KG's check script; `scripts/kg_report.py` reproduces them.

### 6.14 Event replay: deep dive B (owner: Agent KG, `nba/kg/events.py`)

- **Online order:** events (deduplicated) are applied in `ingested_at` order. At any moment the engine only knows what has arrived. `occurred_at` updates the fact; `effective_date` defers a contract change (a gas meter deregistration creates S1 at once, but the gas contract stays active until the effective date).
- **Per-fact-key clocks:** consent per type, contract status, dunning and ticket status each keep their own clock. An older event that arrives later is `stale` and never overwrites a newer fact.
- **Unknown IDs:** a ticket update for an ID missing from the snapshot (`TK-open-complaint`) becomes a conservative open placeholder ticket with provenance. It is never merged into another ticket.
- **Pending cards:** after each decision-relevant event, every pending card (offer, channel) is re-checked with `check_tuple`. A personalised card is also revoked when profiling consent is gone. A revoked card can no longer be exported, and the engine re-decides. A card already sent cannot be recalled.
- **Three freshness measures:**
  - arrival-to-invalidation: re-check at ingest, about 0.7 ms per event;
  - decision-time known-state validity: every transition is re-checked;
  - retrospective late-data exposure: `ingested_at − occurred_at` of revoking events.
- **Result on the stream:**
  - 635 events: 126 applied, 508 informational, 1 orphan. Decision facts changed for 118 customers.
  - Of those 118 customers (92 with a pending T0 card): 29 cards revoked (28 by a new open ticket, 1 by a late cancellation), 5 decisions superseded, 84 unchanged.
  - Late decision events: MG-100465 cancellation 16.9 h, MG-100510 cancellation 9.9 h, MG-100125 gas deregistration 14.7 h, MG-100004 dunning 25.5 h.
  - Report: `python scripts/replay_demo.py` → `out/replay_report.md`, `out/replay/timeline.json`.

### 6.15 New data and policy changes (owner: Agent KG)

The KG is **not a stored graph**. Customer nodes and edges are rebuilt from the tables on every run, so new data needs no "KG update". Only the policy (business rules) is edited by people.

| What changes | What happens | Who acts |
|---|---|---|
| New snapshot, same schema | Run the steps below. New customers, contracts and consents flow in automatically; triage, p and percentiles are recomputed; decisions approved on an older state stop applying (`state_revision`) | Pipeline |
| New events | `nba.kg.events.replay` updates only affected customers and revokes pending cards (§6.14) | Pipeline |
| New product in `product_catalog` | Loading the policy fails until `kg/policy.yaml` has the offer (needs, preconditions, generic flag); Agent NBA adds a German template. Margins and churn effects are read from the catalog | People |
| New threshold (e.g. S4 window) | Edit `parameters` in `kg/policy.yaml`, then run the policy diff | Marketing / Agent KG |
| New signal, need, exclusion or channel | Edit `kg/policy.yaml` + a predicate in `nba/kg/predicates.py` + a test | Agent KG |
| New value in a rule column (e.g. contract status `cancelled`) | `validate_data.py` stops the pipeline (ERROR) until `kg/data_contract.yaml` and the rules handle it | Agent KG |

**Steps for a new snapshot:**

```bash
.venv/bin/python scripts/validate_data.py --workbook <new.xlsx>   # 1. stop on ERROR (exit code 1)
# 2. eval_time: config/kg.yaml `eval_time: auto` = end of the latest customer_value.clv_calc_date
#    (or set an ISO time, or `python -m nba.build --asof ...`)
.venv/bin/python -m nba.build --out out/ --export web/public/data # 3. rebuild every customer
.venv/bin/python scripts/replay_demo.py                          # 4. apply the event stream (deep dive B)
```

**Changing the policy:**

- Thresholds live in `kg/policy.yaml → parameters` (13 values, validated with bounds).
- Edit, then run `.venv/bin/python scripts/policy_diff.py`. It decides every customer under the committed policy (`HEAD`) and under the edited one, and lists **only the customers whose decision changes**: customer, before, after.
- Example: S2 at 4 failures and an S4 window of 30 days changes 39 of 750 decisions.
- Any change also changes the policy fingerprint in `meta.versions.policy`, so approvals made under the old policy stop applying.
- The contact cap and the generic-offer switches stay in `config/kg.yaml`.

**Data contract** (`kg/data_contract.yaml`):
- sheets, primary keys, customer foreign keys;
- allowed values (ERROR for values the rules use, WARNING for display values);
- churn-driver label patterns and numeric ranges;
- date parsing.

On the current workbook it reports 0 errors and 7 warnings, including the known snapshot inconsistencies of §3.

### 6.16 Rule Center (mentor spec, 26 Oct; built; owner: Agent NBA, with Agent KG)

Marketing sets rules that block or limit actions before ranking. The rules come in two tiers:
- **Tier 1 (C-01…C-09):** compliance rules that can only be tightened. They are the KG gates, listed in `kg/policy.yaml → compliance`.
- **Tier 2:** business rules. B-01, B-03…B-06, B-08 and B-09 are in `config/nba.yaml → business_rules`, B-02 is the contact cap and B-07 the holdings gate. Rules marketing adds are in `custom_rules`.

They are checked per offer × channel after valuation:
- a **blocked** tuple is dropped;
- a **held-back** tuple waits; the card shows `chosen.deferred_until`.

Every card carries `rules` (per-rule result and the contact counter line). Edits go through the API (`docs/api.md` §3.6) or the rulebook (`python -m nba.rules`). The full spec, data checks, numbers and the defaults for R1–R5 are in **`docs/rule-center.md`**. There is one contact counter, `nba/kg/contacts.py`; do not build a second one.

### 6.17 AI steps: cluster review and feedback memory (27 Oct; `nba/ai/`)

The AI is not trained or fine-tuned. Each call gets a system prompt, the customer's evidence from the knowledge graph (card JSON) and an output schema built from the ontology. What the system learns is stored as data: customer memory, the calibration factor k and rules. The AI never sends anything and never loosens a rule. Without an AI backend the code result stands.

The backend is configured by `MAINGAU_LLM` (auto | claude | ollama | none; `nba/ai/llm.py`).

**Review before approval** (`python -m nba.ai review`, `GET /api/ai/review`):
- Act-now proposals are grouped into clusters: the same offer × channel × tone in the same segment.
- Code marks a customer `needs_review` for:
  - warning flags: service critical, negative CLV, inconsistent data, annoyed before;
  - the "do no harm" segment with a sales offer;
  - customer memory flagged for review;
  - a value or chance far outside the cluster (robust z ≥ 3.5).
- Soft cases go to the AI: contact fatigue, churn outliers, borderline outliers, low k. The AI explains each one; for soft cases its verdict decides. Hard cases always stay with a person. Cited IDs must exist in the evidence.

**Feedback memory** (`python -m nba.ai feedback`, `POST /api/ai/feedback`):
- Rejections and overrides from the decision log (with `reason_code`) and dismissed or declined offers in `service_nba_feedback` become memory for that customer (`out/customer_memory.jsonl`, `Feedback` nodes).
- What each reason does:

  | Reason | Memory |
  |---|---|
  | already has product | pause the offer 365 days |
  | customer upset | pause sales 30 days |
  | no time / wrong timing | pause the offer 14 days |
  | not relevant | pause the offer 90 days |
  | wrong channel | block the channel 90 days |
  | data wrong | review |

- The engine applies active memory as rule `MEMORY` (holds tuples back until its date).
- The AI classifies free-text reasons, writes the note, may make the memory stricter (never looser), and suggests changes for everyone. Only a person can apply those, through the Rule Center what-if.

**On the mock data:** 467 act-now proposals in 88 clusters. 74 agent-feedback items become memory and change 14 decisions.

### 6.18 Databricks source and results layer (27 Oct; `nba/lakehouse.py`)

The connection is to our own Databricks Free Edition workspace loaded with the mock data, not to a MAINGAU system. Architecture, target and setup: **[docs/databricks.md](docs/databricks.md)**.

- **Raw layer:** `scripts/databricks_sync.py upload` writes `<catalog>.maingau_raw`:
  - the 23 sheets, every cell as text, with `_row` for order;
  - `events_raw`, one row per line;
  - `_manifest`, written last.
- **Source:** `config/databricks.yaml → source` (or `MAINGAU_DATA_SOURCE`) is `local` (default) or `databricks`.
  - With `databricks`, `load_workbook()` / `load_events()` read the raw layer, and `nba/data.py` parses it exactly like the file. The output is byte-identical (1,504 files, 0 differences).
  - Any failure uses `data/` for the whole run, with one warning. Sources are never mixed.
  - `nba.build` prints the source and writes `out/data_source.json`.
- **Results layer:** `scripts/databricks_sync.py publish` writes `<catalog>.maingau_nba`:
  - tables: `worklist`, `nba_options`, `nba_blocked`, `customer_cards`, `customer_journey`, `decision_log`, `customer_memory`, `run_info`;
  - four read-only SQL functions that the managed MCP server lists as tools: `customer_360`, `next_best_actions`, `why_blocked`, `action_group`.
- **Credentials:** `DATABRICKS_HOST` / `DATABRICKS_TOKEN` or `~/.databrickscfg`, never in the repo.

## 7. Tasks: three agents in parallel

### 7.1 Agent KG: ontology, knowledge graph, signals, rules and triage

**Owner:** Claude (main session), who also reviews the work of Agent CARDS and Agent NBA against this README. Detailed plan: [PLAN_KG.md](PLAN_KG.md).

**Goal:** for any customer, return:
- the signals;
- the allowed (offer, channel, tone) tuples: signal, service and generic (§6.12);
- the blocked items with reasons;
- the triage: archetype, urgency and flags (§6.13);
- an explanation path for each tuple.

All of it is driven by `kg/policy.yaml`.

**Owns:**
- `kg/`, `config/kg.yaml`
- `nba/data.py`, `nba/state.py`, `nba/kg/`
- `scripts/`, `docs/schema/`
- `tests/test_kg_*.py`

**Delivers, in order:**
1. *(done 26 Oct)* `nba/data.py`, `nba/state.py`, and the first version of `nba/contracts.py`, now handed to Agent NBA.
2. `kg/ontology.yaml` and `kg/policy.yaml` covering §6.1–§6.4, §6.11 and §6.12.
3. `extract_signals` (S1–S13); the gates (exclusions → holding preconditions → profiling purpose → channel consent and availability → contact cap); generic tuples; `triage`; `explain` with `ui_ref`; `customer_graph`; data-quality flags (§6.9).
4. `scripts/export_schema.py` → `docs/schema/*.json`, which Agent CARDS turns into TypeScript types. `scripts/kg_report.py` → `out/kg_report.md` with signal, archetype, tier and flag counts.
5. *(done 26 Oct, deep dive B)* `nba/kg/events.py` + `scripts/replay_demo.py` (§6.14):
   - ingest-order replay with per-key clocks, effective dates and orphan handling;
   - pending-card revocation and the three freshness measures;
   - demo customers: MG-100003, MG-100465, MG-100125, MG-100009 and MG-100004.

**Done when:**
- Policy integrity tests pass:
  - every offer ID exists in `product_catalog`;
  - every signal except S10 indicates at least one need, and every need is addressed by at least one offer;
  - every channel maps to exactly one consent type;
  - every predicate name resolves to a Python function;
  - there are no orphan nodes.
- No tuple ever violates §6.1, §6.2 or the profiling rule across all 750 customers (an invariant test).
- The signal counts (§6.3) and triage counts (§6.13) are reproduced, or the differences are explained in `log/agent-kg.md`.
- The spec's signal examples reproduce for the test customers in §9.

**Don't:**
- compute ΔCLV;
- rank;
- write UI code;
- treat a missing internet holding as evidence.

### 7.2 Agent CARDS: marketing orchestration dashboard and customer profile

**The full brief is in [prompts/agent-cards.md](prompts/agent-cards.md).** In short:

- **Worklist:** a Notion-like table of all customers, ranked by urgency tier and score (§6.13), with archetype, top reason, recommended action, ΔCLV, confidence and flags. Outliers are visually distinct.
- **Execution:** act on one customer, or select a group that shares the same recommended tuple and approve it in one go. Outliers and customers with warnings need an explicit second look.
- **Customer page:** the left card is the profile (§4.1 A1–A5, B1–B4). The right card holds the ranked NBAs (§4.2 C1–C8). Each NBA shows:
  - why it fits;
  - the CLV gain if it succeeds;
  - the success and failure probability, and why;
  - the notes.
  Every number has a source tooltip.
- **Stack:** React + TypeScript + Tailwind (Vite). It is a static site deployable on Vercel and reads `web/public/data/` (mock data first, then the export from `nba.build`). Decisions are kept in localStorage and can be exported.
- **Backend part:** `nba/profile/` builds the left-card JSON (A1–A5, B1–B3, tone §6.8) from `CustomerState`.

**Owns:**
- `nba/profile/`, `config/cards.yaml`
- `web/`
- `tests/test_profile_*.py`

**Done when:**
- All 13 test customers and both representative customers (MG-100325, MG-100001) render without errors.
- Every number has a tooltip showing `src`, `updated_at`, refresh and latency.
- Missing data shows "not enough data".
- Bulk approval refuses customers whose own checklist fails.
- `npm run build` succeeds and the site works when deployed as static files.

**Don't:**
- re-implement valuation, ranking, rules or triage in the frontend; render what the JSON says;
- draw a CLV trend;
- show the archetype draft's ranges as facts (K13).

### 7.3 Agent NBA: valuation, ranking, content, decisions, API and build

**Goal:** for every customer, value each allowed tuple by ΔCLV, pick the best (or NO_ACTION), explain it, render German content, log decisions, and serve everything through the API and the CLI.

**Owns:**
- `nba/contracts.py`, `nba/engine/`, `nba/build.py`
- `templates/de/`, `api/`, `config/nba.yaml`
- `requirements.txt`, `.gitignore`
- `tests/test_engine_*.py`, `tests/test_acceptance.py`

**Steps:**

- **M0:**
  - `nba/contracts.py` and `requirements.txt` exist. Agent KG wrote the first versions on 26 Oct; you own them from now on.
  - Stub `assemble` so it returns a valid `CustomerCard` for MG-100068.
- **M1:**
  - Implement `clv` and `churn_breakdown`. Tests: CLV matches `clv_eur` within 3.05 € for every customer (median ≈ 0.27 €); churn matches `churn_prob_12m` exactly for the 718 customers.
  - Implement `p_accept` in both modes (default `rate`, §6.6), with reports; generic tuples use the catalog-wide average.
  - Implement `value` per §6.5 and `rank`: drop ΔCLV ≤ 0 into `blocked` as `ECON-NONPOSITIVE`; ties broken by higher p, then lower contact cost, then `offer_id`.
- **M2:**
  - Write `assemble`, combining KG (signals, tuples, blocked, triage, paths) + profile + valuation.
    - Apply the tier logic of §6.12.
    - Fill each candidate's `why` (KG facts + evidence for p) and `notes` (assumptions, low confidence, data quality).
    - Generate the reason line from the actual components and signal IDs.
    - Alternatives with `why_lower`.
    - Legacy comparison: the latest `nba_action_history` row, valued with our model, plus the rules that would block it now.
    - Checklist.
  - Write `templates/de/<offer>.yaml` with du/sie × personalised/generic variants and P-SV-01 apology variants with no sales content.
  - Write `build.py`, producing `out/customers/*.json`, `out/index.json` and `out/summary.json`; `--export web/public/data` copies them for the static UI.
  - Local API endpoints:
    - `GET /api/customers` (filters)
    - `GET /api/customers/{id}`
    - `POST /api/customers/{id}/decision`
    - `GET /api/summary`
- **M3:**
  - `out/test_report.md`: for each test customer, chosen vs expected, under both p modes.
  - Sensitivity check: ±20% on p and on margins for the chosen action.
  - (Stretch) `POST /api/replay` together with Agent KG's events module.

**Content rules:**
- German.
- Subject plus 2–3 sentences.
- No personalised prices.
- No false urgency: no "nur heute", "letzte Chance", or countdown timers.
- Facts allowed only when personalised. Example: *"Ihre Preisgarantie endet am 08.10.2026."*
- Service: apology plus next step, no product mention.
- Generic variant when profiling is not granted.
- No LLM is needed for the MVP. If one is used later, only to polish templates offline, never at decision time.

**Done when:**
- `python -m nba.build` runs for all 750 customers in under 60 s and is deterministic.
- All invariants in §9 hold.
- The test report exists.
- `--export web/public/data` produces files that validate against `docs/schema/`.

**Don't:**
- re-implement signals or rules (call Agent KG's functions);
- turn ΔCLV into a weighted "priority" and still call it euros;
- auto-send anything.

## 8. Integration plan

| Milestone | Target | Integration check |
|---|---|---|
| M0 | First ~45 min | `contracts.py`, `data.py`, `state.py` merged (done); every stub merged; `pytest -q` green; UI renders mock data that validates against `docs/schema/` |
| M1 | ~+3 h | Vertical slice: MG-100068 end to end with real signals, tuples, valuation and both cards |
| M2 | ~+6 h | All 750 customers; the 13 test customers in the report; decisions logged through the API |
| M3 | Remaining time | Overview page, test report, polish, demo script; stretch: event replay and revocation |

**Branches and folders:** `feat/kg` in `../MAINGAU-kg`, `feat/cards` in `MAINGAU`, `feat/nba` in `../MAINGAU-nba`. Deliver small, tested commits to `main` often; contracts first. Full rules: §13.

**Commands:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m nba.build --asof 2026-09-30T23:59:59 --out out/          # all customers
python -m nba.build --customers MG-100068,MG-100009 --out out/    # subset
python -m nba.build --out out/ --export web/public/data            # refresh the UI data
python scripts/export_preview.py --out web/public/data             # KG-only preview until nba.build exists
python scripts/replay_demo.py                                      # deep dive B: out/replay_report.md, out/replay/timeline.json
python scripts/validate_data.py --workbook <xlsx>                  # data contract check before a build (exit 1 on ERROR)
python scripts/policy_diff.py [--base <git ref>]                   # customers whose decision changes with the edited policy
python scripts/databricks_sync.py upload|check [--mcp]|publish       # Databricks raw layer, check, results + MCP tools (§6.18)
MAINGAU_DATA_SOURCE=databricks python -m nba.build --out out/       # build from Databricks; falls back to data/
pytest -q
uvicorn api.app:app --reload --port 8000
cd web && npm install && npm run dev
```

**Config files:** p mode, contact cap, `p_service_success`, generic offers and channels, the Autostrom-cancelled scope and the unsubscribe scope all live in `config/*.yaml`. Rule thresholds live in `kg/policy.yaml → parameters`. All of them are written into `meta.versions`; `eval_time: auto` resolves from the data (§6.15).

## 9. Acceptance tests

Customer facts below were verified in the workbook on 26 Oct. "Spec expects" is quoted from §4.

| Customer | Spec expects | Verified facts | Notes for the test |
|---|---|---|---|
| MG-100051 | StromWärme (P-EN-03) | Gas deregistered 2026-09-13; StromAktiv active with smart meter; profiling granted; `marketing_email` withdrawn; newsletter, phone and portal granted | `email` not allowed. P-EN-03 has no history → L0 prior, low confidence |
| MG-100060 | StromWärme | Gas deregistered 2026-08-29; electricity + Mobil L; **only `marketing_phone` granted** (newsletter withdrawn, portal and email not given) | Only `outbound_call` at 6 €; check that ΔCLV > 0 |
| MG-100096 | P-SV-01, sales blocked | `dunning_level = 3`; gas deregistered 2026-07-24; churn 0.36 | `EXCL-DUNNING` blocks every sales tuple, including P-EN-03 |
| MG-100186 | Service first | Open complaint TK-200745 (2026-09-20); gas deregistered 2026-09-12 | Service mode, P-SV-01 |
| MG-100068 | Two signals compete; check the ranking | Gas deregistered 2026-09-10; Wallbox delivered 2025-12-28; no Autostrom; **price guarantee ends 2026-10-08** (S4 too); profiling, newsletter, email and portal granted | P-EN-03, P-AS-01, P-EN-02 and P-SL-01 compete. Report the ranking with components |
| MG-100023 | P-AS-01 (team-confirmed test case) | Wallbox delivered 2025-08-14; StromAktiv; profiling, newsletter and portal granted; `marketing_email` withdrawn; no exclusion | Needs `p_mode: rate` (K1). S3 is the only signal tuple, so generic offers are not evaluated |
| MG-100112 | **Changed (D1 + K11):** "wallbox signal ignored because there is no profiling consent → non-personalised logic → generic StromAktiv by phone" | Wallbox delivered 2024-10-25; gas only; **profiling not granted**; only `marketing_phone` granted | Strict: S3 blocked by `CONSENT-PROFILING`; no personalised tuple; chosen `P-EN-01|outbound_call|sie`, `origin = generic`, content "nicht personalisiert" (+€14.87 rate / +€2.54 uplift) |
| MG-100009 | P-SV-01 | Autostrom only; 3 failed sessions in Sep 2026; only `portal_app_personalisation` and profiling granted | S2 strong; service mode |
| MG-100659 | P-SV-01 | Autostrom; 3 failed sessions in Sep 2026; low CSAT | S2 strong |
| MG-100035 | No sales offer | Electricity `cancellation_pending` (received 2026-09-04); churn 0.95 | P-SV-01 cannot lower 0.95, so NO_ACTION is acceptable; no sales tuple allowed |
| MG-100087 | No sales offer | `cancellation_pending` (received 2026-09-22); Autostrom active | Same |
| MG-100004 | Non-personalised fallback; open complaint | Profiling not granted; open complaint TK-200772; `dunning_level = 2` | Service first; generic content; tone Sie by default |
| MG-100012 | Non-personalised fallback | Profiling not granted; StromGarant + gas; newsletter, phone and portal granted | Generic path only (e.g. P-MO-01 at the catalog average); content "nicht personalisiert"; tone Sie |

**Strict tests** (must pass under both p modes): MG-100096, MG-100186, MG-100009, MG-100659, MG-100035, MG-100087, MG-100004, MG-100012, MG-100112.

**Strict under the default `rate` mode:** MG-100023 → P-AS-01.

**Report tests** (assert the signal fires and the expected offer appears in `candidates` or `blocked` with a reason; write chosen vs expected to `out/test_report.md`): MG-100051, MG-100060, MG-100068.

**Invariants for all 750 customers:**
- No candidate or chosen tuple without the channel consent and channel availability.
- No sales, upsell, retention or one-off tuple while an exclusion is active.
- No personalised content, no signal-based marketing tuple and no inferred tone when profiling is not granted.
- Every customer has a triage (archetype, urgency tier, flags).
- No chosen tuple with ΔCLV ≤ 0. NO_ACTION always has a reason.
- No offer chosen that the customer already owns.
- The contact cap is respected.
- Every displayed number has `src`.
- Re-running `nba.build` gives identical output.
- "0 violations" may only be claimed for these tested rules, this snapshot mode and these customers.

## 10. Known conflicts between the spec and the data, and the defaults chosen

| ID | Conflict | Default in code | Ask |
|---|---|---|---|
| K1 | Uplift p for P-AS-01 is 0 (0/203 treated, 0/21 control), so it is always dropped. The team confirmed MG-100023 → P-AS-01 | **`p_mode: rate`** (shrunk treated rate); uplift is shown as evidence and reported | Jan / Caro: confirm rate-based ranking |
| K2 | 8 offers have no history (P-EN-01, P-EN-03, P-EN-04, P-MO-03, P-SL-02, P-SL-03, P-SH-04, P-SV-01); the spec's backoff stops at offer × channel | Back off to offer, then global (3.4% rate / 1.4% uplift); P-SV-01 uses `p_service_success = 0.5` | Which priors and service success rate? |
| K3 | Personalisation without profiling consent | **Decided (D1, 26 Oct):** no signal for marketing; generic catalog offers at the catalog average; owned products removed with contract data; Sie; "nicht personalisiert" | — |
| K4 | The spec says 150 Autostrom-only customers and 15 tables | Computed: 159 / 161 / 127 depending on the definition; 18 sources | Which definition? |
| K5 | Contact cap N is not given | N = 2 per 30 days, marketing only | Confirm N |
| K6 | Scope of the `autostrom_contracts.status = cancelled` exclusion | Blocks all sales (spec wording) | All sales, or only e-mobility offers? |
| K7 | A new business line: catalog churn effect vs the multi-line factor 0.8 vs +12 €/line cost | Catalog effect only (spec C4) | Is the bundle effect already in the catalog? |
| K8 | Snapshot has future facts (79 late CDRs; 2 tickets closed with later `resolved_at`) | `snapshot_mode: provided`; flag `SNAPSHOT-INCONSISTENT` | Authoritative snapshot, or strict as-of? |
| K9 | Scope of an unsubscribe found in `newsletter_performance` | Withdraws `newsletter_email` only | Also `marketing_email`? |
| K10 | Retention content during `cancellation_pending` | Blocked, because retention counts as sales content | Confirm |
| K11 | D1 expected MG-100112 → no action because "a 6 € call at p 1–3% is negative". With the catalog values, generic StromAktiv by phone breaks even at p ≈ 0.98% and is +€14.87 (rate) / +€2.54 (uplift) | **Decided (team, 26 Oct):** generic offers may use phone/SMS; economics decide → MG-100112 gets a generic StromAktiv call | — |
| K12 | Should customers with profiling consent fall back to generic offers when no signal tuple is positive? | Yes, only as fallback (`generic.fallback_for_profiled: true`) | Team |
| K13 | The marketing archetype draft (five profiles) has numbers that do not match the data: MG-100325 cost to serve is 55 € (not 7 €) and it has the driver "price guarantee ends <90d"; P-SL-02 needs a home battery, which MG-100325 lacks; profile 4 churn median is 0.30 (not 40–95%) and CLV median 320 € (not < 100 €); there is no "cancellation page" in `portal_sessions`; profile 5 has 6 customers with data-limit hits and Mobil S/M plans | §6.13 uses rule-based archetypes with verified counts; the UI shows engine values, never the draft's ranges | — |

## 11. Out of scope

- Real sending and live MAINGAU systems.
- A production Databricks deployment: the Job schedule, Databricks App, Auto Loader, decisions written to Delta, and permissions. The architecture slide describes this target.
- What exists is a connection to our own Free Edition workspace with the mock data (§6.18). It is not a MAINGAU integration, and the slide must not claim one.
- Online learning or reinforcement learning. Learning is presented as a concept: a holdout design and Bayesian updates of p with versioning.
- A graph database, embeddings or an LLM reasoner. The KG is small and lives in YAML + NetworkX.
- Personalised prices, and causal uplift claims based on the mock history.

## 12. Session logs (`log/`)

Each agent owns one file and writes only there: `log/agent-kg.md`, `log/agent-cards.md`, `log/agent-nba.md`.

- **Start of a session:** `git pull`, then read the open-questions table and the latest entry of all three logs.
- **End of a session** (before the last push):
  - append one entry using the template at the top of your file: goal, what was done, what was verified, what was not done, contract changes, new questions, issues, handoff, next step;
  - update your open-questions table;
  - commit the log together with the session's code.
- **Append-only:** correct an earlier mistake in a new entry, never by rewriting it.
- **Answered questions:** when a mentor or the team answers one, write the answer and the date in the table. If the answer changes a default in §10, update §10 in the same PR.
- **Cross-agent questions:** a question for another agent goes in your own table, with "Ask whom" set to that agent. The other agent answers it in its next entry.
- **No sensitive content:** never put secrets, tokens or real customer data in a log.

## 13. Git and commit rules (all agents)

**Why:** on 26 Oct two agents shared one checkout. One of them switched branches, and another agent's commit landed on the wrong branch. These rules keep three agents from overwriting each other.

### 13.1 One folder and one branch per agent

| Agent | Folder (git worktree) | Branch |
|---|---|---|
| Agent KG (Claude) | `../MAINGAU-kg` | `feat/kg` |
| Agent CARDS | `MAINGAU` (the original folder) | `feat/cards` |
| Agent NBA | `../MAINGAU-nba` | `feat/nba` |

- **Work only in your own folder.** Never open, edit, build or run git commands in another agent's folder.
- **Never switch branches in your folder** (no `git checkout <other branch>` or `git switch`). Your folder stays on your branch for the whole hackathon.
- **To create a missing worktree**, run this from any folder: `git worktree add ../MAINGAU-<agent> -b feat/<agent> origin/main`. A separate `git clone` also works.
- **Python:** the virtualenv lives in the original folder. From your own folder, run `/Users/linhngo/Downloads/Work/Hackathon/MAINGAU/.venv/bin/python -m pytest -q`, or create your own `.venv` (it is git-ignored).
- **Before every git command**, run `git status -sb` and check that the folder and branch are yours. If they are not, stop.

### 13.2 What you may commit

- **Stage only paths you own (§2) plus your own log file.** Use `git add <your paths> log/agent-<you>.md`. **Never** use `git add -A`, `git add .` or `git commit -a`.
- **Before every commit**, run `git diff --cached --stat`; it must list only your paths. Unstage anything else with `git restore --staged <file>`.
- **Shared contracts** (`nba/contracts.py`, README §5) are changed only by their owner, Agent NBA. Whoever changes them also runs `scripts/export_schema.py` and commits `docs/schema/` in the same commit. Other agents ask for changes in their log and do not edit the files.
- **Never commit:**
  - `.venv/`, `node_modules/`, `web/dist/`;
  - `out/` (except `out/samples/`), `out/.cache`;
  - secrets or tokens;
  - real customer data.

  `web/public/data/` (mock data or the `nba.build` export) is allowed; keep it under 30 MB (cards, Customer 360° journeys, index, summary, rules). Regenerating it from `main` with `python -m nba.build --export web/public/data` is allowed and keeps the static demo in line with the API.
- **Commit small and often.** Message format: `<area>: <what changed> (<why>)`, plus a short body. Commit the session's log entry together with the code.

### 13.3 Syncing and delivering to `main`

- **Pick up others' work:** `git fetch origin`, then `git merge origin/main` into your own branch. Rebase only your own branch, only in your own folder, and never after you pushed it for others.
- **Conflicts:** resolve conflicts in your own paths. If a conflict touches another agent's path, stop and write it in your log (Ask whom: that agent).
- **Before delivering**, run the checks:
  - Python: `.venv/bin/python -m pytest -q`;
  - web: `npm run build`.
- **Deliver:**
  1. Push your branch: `git push -u origin feat/<agent>`.
  2. Then either open a PR to `main`, or fast-forward: `git push origin feat/<agent>:main`. The fast-forward only works when your branch contains the current `origin/main`.
- **Never** use `--force` on `main` or on another agent's branch. Never `git reset --hard`, `git clean`, or delete branches or worktrees that are not yours.
- **Do not use bare `git stash`;** the stash stack is shared between worktrees. Use a temporary WIP commit on your branch instead.

### 13.4 When something goes wrong

If a commit lands on the wrong branch, files are staged by mistake, or a push is rejected:
1. Stop; do not force anything.
2. Write what happened in your log (`Issues / risks`) with the commands you ran.
3. Ask Agent KG (Claude) in the open-questions table. Agent KG repairs shared history.
