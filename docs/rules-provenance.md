# Rules: given by MAINGAU vs added by the team

**Given** means stated by MAINGAU in one of four places: the challenge slides (`Hackathon_slides_for_MAINGAU.pdf`), the MAINGAU product spec adopted in README §4, the mentor's Rule Center spec (README §6.16, `docs/rule-center.md`), or the workbook `data/maingau_nba_mockdata.xlsx` (sheets README, clv_method, value_assumptions, product_catalog, sources, columns). **Added** means the team chose it: config values, thresholds, formulas, defaults, tie-breaks, UI rules and AI steps.
Legend: **Given** = Part 1. **Detail** = detail on a given rule: MAINGAU gave the rule and the team chose the details. These rows are in Part 2 and say "MAINGAU: … Team: …". Every other Part 2 row is **Added**. Numbers are for evaluation time 2026-09-30 23:59:59 in rate mode.

---

## Part 1. Rules given by MAINGAU

### 1.1 Slides

**Goal and value**

| Rule | Numbers | Source |
|---|---|---|
| Build only the decision layer (offer, channel, tone, timing) on one mock dataset joined by `customer_id`. Do not build data pipelines | — | slide 5 |
| Recommend offer, channel and tone per customer. "Best" means the highest expected gain in CLV | — | slide 6 |
| Use cases the engine must catch: gas meter deregistered → heat-pump electricity; wallbox bought in the shop → Autostrom; heat-pump story clicked in newsletters → follow up; a loyal high-value customer must not get the same action, timing and tone as a new one | 3 newsletters in a row | slide 6 |
| Expected value of an action = p(accept) × (CLV after − CLV now) − contact cost | no reject branch on the slide (spec C4 and clv_method add it) | slide 7 |
| Raises CLV: cross-sell and upsell (bundled customers churn less), retention (a renewed price guarantee), solving a service case | — | slide 7 |
| Lowers CLV: service cases (handling cost and churn: open complaints, failed charging, dunning), a sales offer during an open service case, every contact's cost, fatigue from too many contacts | — | slide 7 |
| Reference example: an Autostrom driver with failed charging sessions. A home electricity offer scores negative, a proactive service fix scores positive, so the engine picks the fix | 3 failed sessions | slide 7 |
| CLV, margins, churn drivers and all parameters are precomputed (customer_value, value_assumptions). Use them and do not invent your own | — | slide 7 |

**Engine behaviour and pipeline**

| Rule | Numbers | Source |
|---|---|---|
| Decide: per customer, pick offer, channel and tone (Du/Sie), ranked by expected CLV gain, while respecting consent, exclusions and contact limits | — | slide 8 |
| Explain: a one-line reason that a marketer can see and change. Inputs, rules, scores and the chosen action are all logged | — | slide 8 |
| Learn: show how reactions improve the engine and how to prove that an action caused a result. A concept is enough. Use a control group and uplift | — | slide 8 |
| Reference pipeline: Trigger → Eligibility (consent, products held, exclusions, frequency) → Scoring (ΔCLV, can be negative) → Arbitration (rank by ΔCLV, drop negatives, respect fatigue and limits) → Channel & tone → Content → Delivery & log | 7 steps | slide 9 |
| Content may be generated (e.g. by an LLM), but only within approved templates | — | slide 9 |
| Channel/tone example: formal e-mails, never opens newsletters, logs into the portal weekly → portal pop-up, "Sie" | — | slide 9 |
| Day one: rules plus the precomputed CLV plus acceptance rates from the action history. ML is optional. Log every decision and keep a control group | — | slide 9 |

**Hard rules**

| Rule | Source |
|---|---|
| Consent is binding: no channel without its consent, and a withdrawal stops actions at once | slide 12 |
| Exclusions beat offers: dunning, open complaints or cancellations block sales content | slide 12 |
| Human in the loop: the engine proposes and marketing approves. No autonomous sending | slide 12 |
| Profiling needs consent: personalisation only for customers who agreed to profiling | slide 12 |
| No manipulation: no personalised prices, no fake urgency, no targeting of customers in hardship | slide 12 |
| Payment data only as an exclusion, never to score creditworthiness | slide 12 |
| Explainability: every decision is logged with its inputs, rules, scores and chosen action | slide 12 |
| Mock data only: no real customer data and no scraping of MAINGAU systems | slide 12 |
| Language: the pitch is in English and customer content is in German | slide 12 |
| EU AI Act applicability is checked before any production use | slide 12 (footer) |

**Deliverables and judging**

| Rule | Numbers | Source |
|---|---|---|
| Engine: offer, channel and tone per customer, with the expected CLV gain and a one-line reason. Runs on the mock data | — | slide 10 |
| Marketing dashboard: top NBAs across customers and segments. Marketing sets offers, priorities and contact limits, and approves content, channels and tone | — | slide 10 |
| Customer 360° for service: products, contracts, open cases, CLV at a glance, and the ranked NBAs, each with a reason | — | slide 10 |
| One slide on the target architecture: Databricks with MCP data access | — | slide 10 |
| Core deliverables: prototype, marketing dashboard, Customer 360°, architecture slide, pitch | 8 min + 4 min Q&A, in English | slide 11 |
| Pick one deep dive: A feedback loop & uplift, B data freshness & event replay, C content generation, D tone detection | — | slide 11 |
| Jury weighting | technical 25%, feasibility 25%, impact 25%, innovation 15%, pitch 10% | slide 11 |
| Hidden reference customers are checked for three things: the ΔCLV of the recommendations, zero consent or exclusion violations, and a clear reason for every decision | 0 violations | slide 11 |
| Mock data | 750 customers, 16 tables, 640 live events, 10% control group | slide 12 |
| Target: a clear, compliant recommendation for every customer that marketing can steer and that pays off in customer value | — | slide 13 |

### 1.2 MAINGAU product spec (README §4)

**Screen and left card (Customer Profile)**

| Rule | Source |
|---|---|
| One screen per customer with two cards side by side: Customer Profile on the left and Next Best Action on the right. The user should understand the customer in about 30 s. The spec left the user group open; "both, with a mode switch" was filled in by the team | README §4 Task |
| Every number has a tooltip with its `table.column`, its update time, and the refresh and latency from the `sources` sheet | README §4 Task |
| A1 header: customer_id, an age band from birth_year shown as "50–59", city, household_size, tenure from customer_since, and the digital level (portal_account, app_installed, preferred_contact_language) | §4.1 A1 |
| A1 tone, in priority order: (1) customer text, where "Hi", "danke dir" and "tschüss" mean Du and "Sehr geehrte" and "Mit freundlichen Grüßen" mean Sie; (2) newsletter clicks by `newsletter_campaigns.tonality`; (3) default Sie, labelled as the default. Always show the evidence, e.g. "Du – 2/2 messages use 'du', latest 2026-08-14" | §4.1 A1 |
| A2 value: clv_eur, annual_margin_eur, cost_to_serve_12m_eur, active_business_lines, churn_prob_12m with churn_drivers as tags, and clv_service_impact_eur shown as "Service issues are costing €X of CLV". Also the CLV percentile among all 750 customers and among customers with the same product combination | §4.1 A2 |
| A3 products as a grid where an empty cell is an opportunity (lightly tinted). Energy: price_guarantee_until as a countdown, meter_type, feed_in_meter, payment_method. Autostrom: kWh per month and the AC/DC ratio. Mobile: data volume vs usage, data_limit_reached_3m, sim_count vs household_size, min_term_end. Shop: only rows with a customer_id; returned or cancelled orders are not owned. Smart Living: warn if the gateway is offline. Internet: no ownership data, so it is only a potential offer | §4.1 A3 |
| A4 consent and exclusions are shown traffic-light style at the top and never hidden. All 6 consent types are shown with status, updated_at and source | §4.1 A4 |
| A4 channel → consent: newsletter_email → newsletter_email (double opt-in confirmed); email → marketing_email; outbound_call → marketing_phone; sms → marketing_sms; portal_popup / app_push → portal_app_personalisation plus a portal account / installed app. Any personalisation needs profiling_analytics | §4.1 A4 (map in §6.1) |
| A4 an unsubscribe in newsletter_performance counts as withdrawn, even if consent_status was not updated | §4.1 A4 |
| A4 active exclusions: dunning_level ≥ 1; status = cancellation_pending; any open service ticket (especially a complaint); autostrom_contracts.status = cancelled | §4.1 A4 |
| A5 two or three highlights, only things genuinely unusual compared with the population (e.g. "Top 10% CLV", "DC charging 3× the average"). Each names its column | §4.1 A5 |

**Timeline, trends, contact history**

| Rule | Source |
|---|---|
| B1 vertical timeline, newest first, covering the last 12 months plus future milestones (price_guarantee_until, min_term_end). It shows contract events, service tickets (repeats marked "repeat contact"), purchases, consent changes, and marketing sent (without control-group rows) | §4.1 B1 |
| B2 every trend states the real time range of its data. Charging (06–09/2026): failed sessions by reason, a marker for the AC price cut on 2026-07-01, and a note that roaming data can arrive up to 72 h late. Portal (07–09/2026). Newsletter (01–09/2026) without apple_mpp_prefetch opens. Service (12 months): tickets per quarter, latest CSAT, goodwill. Mobile: a usage/limit bar only. HEMS (09/2026), where missing days mean the device was offline. No CLV trend: it is a single snapshot, and the card must say so | §4.1 B2 |
| B3 contacts in the last 30 and 90 days (delivered), the response rate, and offers ignored repeatedly. Flag `consent_checked = 0` as "legacy engine sent without checking consent", and show service_nba_feedback | §4.1 B3 |
| B4 each signal has an id, description, date, source table, strength and the offers it triggers. Duplicate events (same event_id and timestamp) are removed before signals are built | §4.1 B4 |

**Signals S1–S11** (original spec B4, `docs/company-spec-vi.md` @065c318; README §6.3)

| Signal | Strength | Offers |
|---|---|---|
| S1 gas meter deregistered (energy_contracts) | strong | P-EN-03, P-SL-01 |
| S2 3 failed charging sessions in 30 days | strong | P-SV-01 |
| S3 bought a wallbox but has no Autostrom | strong | P-AS-01, P-SL-03 |
| S4 price guarantee ends within 90 days | strong | P-EN-02 |
| S5 data limit reached in ≥ 2 of 3 months | medium | P-MO-02 |
| S6 household_size > sim_count | weak | P-MO-03 |
| S7 feed_in_meter or pv_inverter, but no hems_gateway | medium | P-SL-01 |
| S8 HEMS + home_battery / HEMS + wallbox | medium | P-SL-02 / P-SL-03 |
| S9 smart meter + (HEMS, EV or heat pump) | medium | P-EN-05 |
| S10 real click on heat pump / PV / e-mobility content | weak | none: it only reinforces other signals |
| S11 Autostrom-only customer without an electricity contract | medium | P-EN-01 |

**Right card (Next Best Action)**

| Rule | Source |
|---|---|
| C1 top action: offer (product_id, product_name, action_type), channel, tone and a suggested send time, plus the expected ΔCLV (€) and a confidence label high / medium / low. Status goes proposed → approved / overridden, and nothing is sent automatically | §4.2 C1 |
| C2 a one-line reason in plain language that references signals, e.g. "Gas meter deregistered 8 weeks ago [S1] → … +€42 expected CLV" | §4.2 C2 |
| C3 reasoning chain as a KG path: Customer –EMITTED→ Signal –INDICATES→ Need –ADDRESSED_BY→ Offer –DELIVERED_VIA→ Channel –REQUIRES→ Consent. Clicking a node jumps to the matching row in the left card | §4.2 C3 |
| C5 checklist, each line ✓/✗ with its source: channel consent, profiling consent, no exclusion, product not owned yet, contact cap not exceeded (≤ N per 30 days; N not given), data fresh enough | §4.2 C5 |
| C6 two or three alternatives with ΔCLV and why they rank lower. Blocked actions, each with the rule that blocks it. A comparison with the latest rule_engine_v1 action ("The old system would send R-SHOP-GENERIC, ΔCLV €−0.4") | §4.2 C6 |
| C7 content preview in German with the correct Du/Sie: a subject plus 2–3 sentences. No personalised prices and no false urgency. A service fix gets an apology and resolution steps, with no sales content. Without profiling consent the content is generic and labelled "nicht personalisiert" | §4.2 C7 |
| C8 buttons: Approve, change channel, change tone, change offer, Reject (with a reason). The log holds inputs, rules applied, scores, the final decision, the reviewer and the time. Service-agent mode: an open ticket switches the card to "resolve first" (P-SV-01) with suggested phrases | §4.2 C8 |

**Valuation (C4)**

| Rule | Numbers | Source |
|---|---|---|
| ΔCLV = p_accept × (CLV_after_accept − CLV_now) + (1 − p_accept) × (CLV_after_reject − CLV_now) − contact_cost, with CLV_now = clv_eur | — | §4.2 C4 |
| Accept for sales/upsell: add annual_margin_if_bought_eur to the margin and churn_effect_if_bought to churn. Shop offers add the margin only once | — | §4.2 C4 |
| Accept for P-EN-02: remove the "price guarantee" churn driver. Accept for P-SV-01: remove the service churn drivers and subtract service_resolution_cost_eur | 0.10; 15 € | §4.2 C4 |
| Reject = CLV_now, except a sales contact during an open complaint or dunning, which adds churn | +0.05 | §4.2 C4 |
| p_accept = conversion rate by offer × channel × tone from nba_action_history, minus the control-group baseline (uplift). Always show n. If n < 30, label it "low confidence" and use the parent level (offer × channel) | n < 30 | §4.2 C4 |
| contact_cost per channel | email 0.01, sms 0.08, popup 0, call 6 € | §4.2 C4 |
| Show the valuation as a small table that a marketer can re-check | — | §4.2 C4 |

**Knowledge graph, mandatory rules, tests, output**

| Rule | Source |
|---|---|
| Nodes: Customer, Contract (Energy, Mobile, Autostrom), Device, Order, Ticket, Session, Signal, Need, Offer, Channel, Consent, Exclusion, Action. Edges: HOLDS, OWNS_DEVICE, PLACED, RAISED, EMITTED, INDICATES, ADDRESSED_BY, DELIVERED_VIA, REQUIRES, BLOCKS, RECEIVED, RESPONDED. The KG generates candidates from signals, applies BLOCKS/REQUIRES and produces the explanation path. Ranking is always by ΔCLV | §4.3 |
| Keep every hard rule from the brief. Apply rules **before** ranking. Drop every candidate with ΔCLV ≤ 0. Payment data is used only as an exclusion. If data is missing, show "not enough data" and do not guess | §4.4 |
| Test customers: MG-100051 and MG-100060 → P-EN-03. MG-100096 (dunning) → P-SV-01 with sales blocked. MG-100186 (open complaint) → service first. MG-100068 → two signals compete. MG-100023 and MG-100112 → P-AS-01 (the team changed MG-100112, see K11). MG-100009 and MG-100659 → P-SV-01. MG-100035 and MG-100087 (cancellation_pending) → no sales. MG-100004 and MG-100012 (no profiling) → non-personalised fallback | §4.5, §9 |
| Output: one JSON per customer `{profile, signals[], timeline[], candidates[], blocked[], chosen, explanation_path[], decision_log}`, and a UI rendered from it | §4.6 |

### 1.3 Mentor: Rule Center (README §6.16, `docs/rule-center.md`)

**Frame:** marketing sets rules that block or limit actions. Every rule is evaluated before ranking, on each offer × channel tuple. The page lists the rules, has a form to edit them and shows a what-if preview before saving (rule-center §1).

**Tier 1, compliance:** always on. These rules can never be switched off or loosened, only tightened (§2).

| ID | Rule | Effect |
|---|---|---|
| C-01 | A channel needs its consent granted. The portal pop-up needs a portal account and app push needs the app | BLOCK_CHANNEL |
| C-02 | The newsletter also needs double opt-in | BLOCK_CHANNEL |
| C-03 | An unsubscribe withdraws the newsletter at once | BLOCK_CHANNEL |
| C-04 | Withdrawn consent cancels actions that were approved but not yet sent | CANCEL_PENDING |
| C-05 | No profiling consent → no personalisation | DOWNGRADE_TO_NON_PERSONALISED |
| C-06 | Dunning ≥ 1 → service only | BLOCK_ALL_SALES |
| C-07 | Open complaint → no sales | BLOCK_ALL_SALES |
| C-08 | Cancellation in progress (cancellation_pending, or Autostrom cancelled) → no sales | BLOCK_ALL_SALES |
| C-09 | Payment data only to exclude | design rule |

**Tier 2, business rules:** marketing creates, edits and switches them. Each has a default (§3).

| ID | Rule | Default | Effect | Data check |
|---|---|---|---|---|
| B-01 | Max N e-mails in W days; newsletters count | 5 / 90 d | DEFER_UNTIL | confirmed (673 customers e-mailed, median 4, 328 at ≥ 5) |
| B-02 | Max N contacts in W days, all channels | 2 / 30 d | DEFER_UNTIL | "p90 = 4" not reproduced (3) |
| B-03 | Max calls; an agent's offer mention counts as a call | 1 / 90 d | DEFER_UNTIL | confirmed (history max 2) |
| B-04 | Max SMS | 1 / 90 d | DEFER_UNTIL | — |
| B-05 | Same offer dismissed or ignored ≥ 2 times → pause it 60 days after the last time | 2, 60 d | DEFER_UNTIL | MG-100051 pause ended 23.09, before the snapshot (R3) |
| B-06 | No sales for X days after a ticket is resolved | 14 d | DEFER_UNTIL | — |
| B-07 | Never offer what the customer owns (contracts, hems_devices, delivered shop orders) | on | BLOCK_OFFER | — |
| B-08 | Minimum ΔCLV per channel; a call costs €6 | call ≥ €10 | BLOCK_CHANNEL | — |
| B-09 | Channel capacity; above it, switch channel or wait | 50 calls/week | DEFER_UNTIL | — |

**Mechanics**

- The rule record has these fields: rule_id, name, tier, active, scope, condition {source_table, field, operator, value, window_days}, effect, params, valid_from/to, version, created_by, reason_template (§3).
- There are 8 effects: BLOCK_CHANNEL, BLOCK_OFFER, BLOCK_ALL_SALES, BLOCK_ALL_CONTACT, DEFER_UNTIL, DOWNGRADE_TO_NON_PERSONALISED, REQUIRE_APPROVAL, CANCEL_PENDING. The reason_template is the sentence shown on the card (§3).
- One shared contact counter merges four sources: delivered non-control nba_action_history, delivered newsletters, agent offer mentions (as phone) and the engine's own decision log. Duplicates are removed by customer + channel + timestamp (§4).
- Order: tier 1 runs first, then tier 2. The strictest rule wins, and tier 2 never overrides tier 1. Rules are evaluated per offer × channel, and if the best channel is blocked the next channel competes with its own ΔCLV. A temporary block becomes DEFER_UNTIL the earliest valid date. If everything is blocked or ΔCLV ≤ 0, the result is NO_ACTION with the reasons. Capacity (B-09) runs last, sorted by ΔCLV (§5).
- Legacy audit over the history: the mentor estimated about 830 sends without channel consent (the data has 829) and 114 app pushes to customers without the app (the data has 114) (§8).
- Card display: one checklist row per rule, a Blocked section, "Waiting until {date}", and the counter line "Email 3/5 (90 d) · Total 1/2 (30 d) · Call 0/1 (90 d)" (§7; the doc does not mark which parts are mentor and which are team).
- Mentor test cases: MG-100267/MG-100026 (B-01), MG-100023 (newsletter yes, 1:1 e-mail no), MG-100112 (phone only, no profiling, check B-08), MG-100067/MG-100102 (late withdrawal, C-03/C-04), MG-100001 (no app → portal pop-up only), MG-100051 (B-05), MG-100096 (C-06), MG-100186 (C-07), what-if B-01 5 → 3 (§8).

### 1.4 Workbook (`data/maingau_nba_mockdata.xlsx`)

**clv_method and README sheets**

| Rule | Source |
|---|---|
| CLV = Σ over t = 1..10 of (annual_margin − cost_to_serve) × (1 − churn)^(t−1) / 1.06^t | clv_method row 2 |
| Service cases reduce CLV twice: through cost_to_serve and through churn. clv_service_impact_eur is always ≤ 0 | clv_method rows 3–4 |
| dCLV formula with the reject branch (same as spec C4). For one-off shop products, add the margin once, not as an annuity. P-EN-02 removes the "price guarantee ends" driver. P-SV-01 removes the service drivers and subtracts service_resolution_cost_eur. A sales contact during an open complaint or dunning adds contact_during_service_case, which "makes such actions negative" | clv_method rows 5–9 |
| p_accept is "your model": start with rates from nba_action_history by offer × channel × tone and **compare** to the control group (the spec says "minus") | clv_method row 10 |
| Rank by dCLV. Hard rules (consent, exclusions) apply before ranking. All parameters are fictional and editable | clv_method rows 11–12 |
| All data is synthetic. Snapshot 2026-09-30 23:59; the event stream starts 2026-10-01. The data has deliberate traps: Apple MPP machine opens, late roaming CDRs, guest orders, consent withdrawn by unsubscribe, legacy actions that ignored consent, offline HEMS gateways, duplicate events. Du/Sie is not labelled and must be derived | README sheet rows 2–8 |

**value_assumptions** (all values given; slide 7 says use them)

| Group | Parameters |
|---|---|
| general | discount_rate 0.06, horizon_years 10 |
| margin | electricity_eur_per_kwh 0.022, heatpump_electricity_eur_per_kwh 0.015, gas_eur_per_kwh 0.005, energy_base_eur_per_year 48, mobile_share_of_fee 0.3, autostrom_eur_per_kwh 0.07 (Jun–Sep × 3), hems_eur_per_year 36, shop_share_of_net_sales 0.18 |
| cost_to_serve | base_per_business_line_eur 12, ticket_email_eur 4.5, ticket_chat_eur 3, ticket_phone_eur 7.5, ticket_portal_form_eur 2.5, complaint_multiplier 2.5, failed_charge_session_eur 1.5, goodwill_counts_as_cost 1, dunning_per_level_eur 15 |
| churn base | base_electricity 0.14, base_gas 0.12, base_mobile 0.18, base_autostrom 0.20, multi_line_factor 0.8 per extra line (min 0.5×) |
| churn drivers | price_guarantee_ends_90d +0.10, open_complaint +0.12, tickets_12m_ge2 +0.04, csat_le2 +0.05, dunning_ge2 +0.08, failed_charges_30d_ge3 +0.10, hems_user −0.04, cancellation_pending = 0.95 |
| action | contact_during_service_case +0.05, contact_cost_email_eur 0.01 (also newsletter), contact_cost_sms_eur 0.08, contact_cost_popup_eur 0 (portal/app pop-up), contact_cost_call_eur 6, service_resolution_cost_eur 15 |

**product_catalog** (18 offers: margin = annual_margin_if_bought_eur, churn = churn_effect_if_bought)

| Offer | Type | Margin € | Churn | Target given by MAINGAU |
|---|---|---|---|---|
| P-EN-01 StromAktiv | sales | 114 | −0.02 | customer without electricity contract |
| P-EN-02 StromGarant | retention | 0 | −0.10 | price guarantee ending; value = avoided churn |
| P-EN-03 StromWärme | sales | 140 | −0.02 | heat pump in household |
| P-EN-04 GasAktiv | sales | 111 | −0.02 | electricity customer with gas heating (unknown in data) |
| P-EN-05 Dynamischer Stromtarif | sales | 20 | −0.03 | smart meter required; smart meter + HEMS/EV/heat pump |
| P-MO-01 Mobil S/M/L | sales | 54 | −0.02 | energy customer without mobile |
| P-MO-02 Mobil Upgrade | upsell | 18 | −0.03 | data limit reached repeatedly |
| P-MO-03 Zusatz-SIM | upsell | 29 | −0.01 | household_size > 1 |
| P-IN-01 Internet | sales | 130 | −0.03 | customer without internet (no holdings in data) |
| P-SL-01 HEMS Starter-Set | sales | 36 | −0.04 | PV / heat pump / EV owner without HEMS |
| P-SL-02 HEMS Speicher-Optimierung | upsell | 36 | −0.01 | HEMS + battery |
| P-SL-03 Wallbox-Integration | upsell | 24 | −0.01 | HEMS + EV / wallbox |
| P-SH-01 Balkonkraftwerk 800 W | one_off | 90 | −0.01 | no PV, balcony (unknown) |
| P-SH-02 Wallbox 11 kW | one_off | 126 | −0.01 | EV driver (charging signals) |
| P-SH-03 Smarte Thermostate | one_off | 23 | 0 | gas heating |
| P-SH-04 Smart Plug 4er-Set | one_off | 9 | 0 | digital, low basket |
| P-AS-01 Autostrom | sales | 85 | −0.02 | EV driver without Autostrom (public charging only) |
| P-SV-01 Service-Only | service | 0 | — | open complaint, dunning, cancellation; removes service churn drivers, costs 15 € |

**sources and columns**

| Rule | Source |
|---|---|
| Consent is event-driven with < 1 min latency and is legally binding: withdrawn = stop immediately | sources (consent_status) |
| Freshness per source: e.g. customer_master CDC < 5 min, energy_contracts daily 02:00 (2–26 h), portal_sessions < 10 s, customer_value monthly (~1 month). Roaming CDRs arrive 1–72 h late. The AC price was cut from 0.62 to 0.52 €/kWh on 2026-07-01 | sources |
| Autostrom is public on-the-go charging only. The legacy actions (Jun–Sep 2026) include a 10% control group and did not all check consent. apple_mpp_prefetch opens are machine opens. HEMS telemetry covers September, and gaps mean the device was offline | sources |
| dunning_level: 0 = none, 1–3 = stage (exclusion signal). smart_meter_imsys is needed for the dynamic tariff. meter_deregistered_at is a strong signal of a new heating system | columns (energy_contracts) |
| control_group = held out, not sent (for uplift). converted_within_14d is the conversion. consent_checked records whether the legacy engine checked consent | columns (nba_action_history) |
| message_text is a tonality signal. repeat_of_ticket_id = the same category within 21 days. A null customer_id in shop_orders is a guest order. service_nba_feedback values: agent_action, dismiss_reason, customer_reaction | columns |

### 1.5 Where the given sources disagree with the data (README §10, rule-center §9)

- **K1:** under uplift, P-AS-01 gets p = 0 (0/203 treated, 0/21 control) and can never be chosen, although MG-100023 → P-AS-01 is a test case.
- **K2:** 8 offers have no history, and the spec's backoff stops at offer × channel.
- **K3:** the spec does not say how candidates are chosen without profiling consent (team decision D1).
- **K4:** the spec says 150 Autostrom-only customers and 15 tables. The data gives 159 / 161 / 127 customers depending on the definition, and 18 source sheets. The slides say 16 tables and 640 events; the data has 647 event lines (635 unique) and 248 control rows of 2,270.
- **K5:** the contact cap N is not given (the mentor later said 2 per 30 days).
- **K6:** the spec does not say whether a cancelled Autostrom contract blocks all sales or only e-mobility offers.
- **K7:** for a new business line, should the catalog churn effect, the multi-line factor 0.8 or the +12 € line cost apply?
- **K8:** the snapshot contains future facts (79 late CDRs, 2 tickets with a later resolved_at).
- **K9:** the scope of an unsubscribe (newsletter only, or marketing_email too?).
- **K10:** whether retention content is allowed during cancellation_pending.
- **K11:** D1 expected MG-100112 to get no action, but a generic StromAktiv call is positive (+€14.87 rate, +€2.54 uplift).
- **K12:** should profiled customers fall back to generic offers?
- **K13:** the marketing archetype draft does not match the data.
- **R1:** the mentor's counter counts newsletters for every frequency rule. **R3:** the mentor's B-05 test (MG-100051) had already expired at the snapshot. The B-02 "p90 = 4" claim was not reproduced.

---

## Part 2. Rules the team added (not in the slides or the spec)

### 2.1 Knowledge graph and signals

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail.** MAINGAU: snapshot at 2026-09-30 23:59. Team: the evaluation time is derived automatically as the end of the latest customer_value.clv_calc_date, unless an ISO time is set | eval_time: auto → 2026-09-30 23:59:59 | config/kg.yaml:3; nba/state.py:20-32 | README §6.15, §8 |
| Snapshot status columns are taken as authoritative. There is no strict as-of rebuild; facts after the cutoff are only flagged | snapshot_mode: provided | config/kg.yaml:4; nba/state.py:85-86 | K8 (Q-KG-04) |
| **Detail S1.** MAINGAU: gas meter deregistered → strong. Team: any gas contract with meter_deregistered_at, at any status and with no age limit; the latest row wins; the need is N-HEAT-PUMP; the event effective_date is shown | commodity = gas AND meter_deregistered_at set | kg/policy.yaml:40; nba/kg/predicates.py:89-101 | README §6.3 |
| **Detail S2.** MAINGAU: 3 failed in 30 days. Team: ≥ 3 sessions with session_status = failed ("aborted" does not count), started_at in (eval − 30 d, eval]; tunable within 1–100 sessions and 1–365 days | failed_charges_min 3; window 30 d | kg/policy.yaml:10-11,41; nba/kg/predicates.py:104-115 | README §6.3 |
| **Detail S3.** MAINGAU: wallbox bought, no Autostrom. Team: only a *delivered* order named exactly "Wallbox 11 kW"; "no Autostrom" means no *active* contract | — | kg/policy.yaml:42; nba/kg/predicates.py:118-128; nba/state.py:43-48 | README §6.3 |
| **Detail S4.** MAINGAU: guarantee ends within 90 days. Team: active contracts only, any commodity, 0 ≤ days < 90 (strict; the workbook driver seems to use ≤ 90: 143 vs 145 customers), nearest date first; the window can be tuned only within 1–90 because P-EN-02 relies on the "<90d" driver | price_guarantee_window_days 90, bounds [1, 90] | kg/policy.yaml:12,43; nba/kg/predicates.py:131-144; nba/kg/policy.py:27-28 | Q-KG-06; README §6.15 |
| **Detail S5.** MAINGAU: ≥ 2 of 3 months. Team: active mobile only; tunable within 1–3 | data_limit_min_months 2 | kg/policy.yaml:13,44; nba/kg/predicates.py:147-154 | README §6.3 |
| **Detail S6, S7.** Team: S6 checks only active mobile contracts; S7 reads feed_in_meter only from the active electricity contract | sim_count < household_size; (feed_in OR pv_inverter) AND no gateway | kg/policy.yaml:45-46; nba/kg/predicates.py:157-181 | README §6.3 |
| **Detail S8, S9.** Team: an active Autostrom contract counts as an EV/wallbox (S8 → P-SL-03, S9). S9 also needs active electricity, and tariff StromWärme counts as a heat pump | smart_meter_imsys AND (HEMS OR Autostrom OR heat_pump OR StromWärme) | kg/policy.yaml:47-48; nba/kg/predicates.py:184-219 | README §6.3 |
| **Detail S10.** MAINGAU: a real click on heat pump / PV / e-mobility content, weak; the slide's case is 3 clicks in a row. Team: targets narrowed to heat_pump_article and smart_living_landingpage (no e-mobility target); 1 click is enough; S10 triggers no follow-up action and does not change p | ≥ 1 click | kg/policy.yaml:49; nba/kg/predicates.py:222-231; nba/kg/signals.py:19 | README §6.3 |
| **Detail S11.** MAINGAU: an Autostrom-only customer. Team: active Autostrom and no *active* electricity contract (161 customers, not 150) | — | kg/policy.yaml:50; nba/kg/predicates.py:234-248 | K4 (Q-KG-05) |
| **Detail S12 (new signal).** MAINGAU: an open ticket → "resolve first" (C8). Team: made it signal S12, strength strong, for *any* open ticket; complaints are shown first, then the oldest | status = open | kg/policy.yaml:51; nba/kg/predicates.py:251-258 | README §6.3 |
| **Detail S13 (new signal).** MAINGAU: P-SV-01 targets dunning and cancellation. Team: signal S13, strength strong, routes dunning ≥ 1 or cancellation_pending to the service tuple | — | kg/policy.yaml:52; nba/kg/predicates.py:261-267 | README §6.3 |
| Signal purposes: service signals (S2, S12, S13) create only P-SV-01 tuples, and the other signals create marketing tuples. All 13 signals are switched on | purpose ∈ {contract, service, behavioural, device}; S1–S13 | kg/policy.yaml:40-52; config/kg.yaml:7; nba/kg/rules.py:288-305 | README §6.3 |
| **Detail.** MAINGAU: the Need node and the signal → offer pairs. Team: 11 need IDs with EN/DE labels; each need must have ≥ 1 signal and ≥ 1 offer | N-HEAT-PUMP … N-HOME-ELECTRICITY | kg/policy.yaml:24-35; nba/kg/policy.py:189-193 | README §6.4 |
| Offers without a signal are reached only through the generic path, never through invented signals. P-SH-02 Wallbox has no need and is not generic, so it is never proposed (the catalog targets "EV driver (charging signals)") | P-SH-02: addresses [], generic false | kg/policy.yaml:71 | README §6.3 |
| **Detail offer preconditions.** MAINGAU: catalog targets and B-07. Team: P-EN-01 is not offered to customers with active electricity. P-EN-02 needs active electricity and the "price guarantee ends <90d" driver (a gas guarantee does not qualify). P-EN-03 is not offered on tariff StromWärme. P-MO-01 is not offered with active mobile (the target "energy customer" is dropped). P-MO-02/03 need active mobile. P-SL-01 is not offered with a gateway. P-SL-02 needs a gateway + home battery. P-SL-03 needs a gateway + (wallbox or active Autostrom) | not_held / requires predicates | kg/policy.yaml:58-69; nba/kg/predicates.py:290-325 | README §6.4; Q-KG-21 |
| **Detail shop ownership.** MAINGAU: B-07, and returned/cancelled orders are not owned. Team: map of product names and devices: Balkonkraftwerk 800 W, pv_inverter or feed_in_meter → P-SH-01 owned; Wallbox 11 kW or a wallbox device → P-SH-02; Smarte Thermostate 3er → P-SH-03; Smart Plug 4er-Set or smart_plug → P-SH-04. P-SH-03 is generic for everyone, although its target is gas heating | SHOP_OWNERSHIP | kg/policy.yaml:70-73; nba/kg/predicates.py:328-350; nba/state.py:43-48 | README §6.4 |
| **Detail.** MAINGAU: show "not enough data" and do not guess. Team: P-EN-04 and P-IN-01 are never generated, and every card lists one DATA-MISSING blocked row for each | "Gas heating is not in the data"; "No internet availability or ownership data" | kg/policy.yaml:61,66; nba/kg/rules.py:267-269 | Q-KG-08 |
| P-SV-01 uses a dedicated channel, service_agent, and only that channel | service_channel: service_agent | kg/policy.yaml:75,85; nba/kg/rules.py:288-301,401-404 | README §6.1 |
| One marketing tuple is created per allowed marketing channel; every offer may use all 6 channels | offer × allowed channel | nba/kg/rules.py:255-256,338 | README §6.4 |
| Generic offers (offered without signals) | P-EN-01, P-MO-01, P-SL-01, P-SH-01, P-SH-03, P-SH-04 | config/kg.yaml:15; kg/policy.yaml:58-75 | D1 |
| A generic tuple only drops products the customer owns (not_held); no "requires" precondition applies | — | nba/kg/rules.py:207-222 | D1 |
| Generic offers may use every consented channel, including phone and SMS; the economics decide (e.g. MG-100112 → a generic StromAktiv call) | allowed_channels: all | config/kg.yaml:17; nba/kg/rules.py:354-356 | K11 (26 Oct) |
| Customers with profiling consent get generic tuples only as a fallback, when no signal or service tuple is allowed now with ΔCLV > 0. These tuples then use the inferred tone. A generic offer that already came from a signal is skipped | fallback_for_profiled: true | config/kg.yaml:16; nba/kg/rules.py:357-359; nba/engine/assemble.py:80-86 | K12 (Q-KG-13) |
| Candidates are listed service first, then signal, then generic, then by offer_id and channel (the ranking itself is by ΔCLV) | {service 0, signal 1, generic 2} | nba/kg/rules.py:380 | README §6.12 |
| Ontology extensions: nodes Archetype, Campaign, Feedback; edges HELD_OUT, INSTANCE_OF, REINFORCES, EVIDENCED_BY, HAS_SESSION, IN_ARCHETYPE, GENERIC_OFFER, GAVE_FEEDBACK, ABOUT | 9 extra edge types | kg/ontology.yaml:27-30,45-55 | Q-KG-22; README §6.11 |
| **Detail edges.** MAINGAU: the edge names. Team: RECEIVED only for delivered actions and HELD_OUT for control rows; RESPONDED only for a response of clicked or viewed, or converted_within_14d; REQUIRES profiling only for need-based non-service offers; BLOCKS from each exclusion to every offer whose action_type it blocks | — | nba/kg/graph.py:58-65,94-101 | README §6.11 |
| **Detail path.** MAINGAU: the C3 path shape. Team: only the first signal is drawn; a generic tuple uses GENERIC_OFFER in place of a signal; a service tuple ends at service_agent, with no consent node | 3 path shapes | nba/kg/paths.py:32-62 | README §5.4 |
| The policy file loads only if all of these hold: its offers equal product_catalog, every predicate exists, every signal points to a need, the generic lists agree, the cap is ≥ 1, compliance lists exactly C-01…C-09, and 13 parameters are within bounds (e.g. risk_churn_min 0–1, top_clv_quantile 0.5–0.999, roaming_late_hours 1–720) | validate(); PARAMETER_BOUNDS | nba/kg/policy.py:25-32,175-237 | README §6.15, §7.1 |

### 2.2 Triage and segments

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| Archetypes, first match wins: A4 "Retention risk (do no harm)" if any exclusion or churn ≥ 0.35; A1 "Smart eco-system adopter" if there is a hems_gateway; A3 "EV driver" if Autostrom is active; A5 "Growing connected household" if household_size > sim_count or data_limit_reached_3m ≥ 1 (first active mobile); A2 "Traditional energy loyalist" if the lines are only electricity and/or gas; otherwise A0. Age and payment data are never used | risk_churn_min 0.35 | kg/policy.yaml:14,108; nba/kg/segments.py:38-58 | K13; README §6.13 |
| Urgency tier P1 (act now, service): cancellation pending, open complaint, dunning ≥ 2, or S2 | p1_dunning_min 2 | kg/policy.yaml:15; nba/kg/segments.py:82-91 | README §6.13 |
| P2: any other open ticket, dunning = 1, price guarantee ends in ≤ 30 days, or churn ≥ 0.35 | p2_price_guarantee_days 30 | kg/policy.yaml:14,16; nba/kg/segments.py:92-102 | README §6.13 |
| P3: S4 (31–89 days), a gas meter deregistered in the last 90 days, or S5. P4: any other signal except S10. P5: no trigger | p3_dereg_recent_days 90 | kg/policy.yaml:17; nba/kg/segments.py:76-77,103-120 | README §6.13 |
| Urgency score | 100 × (5 − tier) + min(99, max(0, clv_eur) × churn_prob_12m / 10) | nba/kg/segments.py:20,121 | README §6.13 |
| Flags: service_critical (tier P1), no_marketing_channel, no_profiling, negative_clv (clv_eur < 0), top_clv (clv_eur ≥ sorted_clv[int(0.9 n)] = 1,023 €, a VIP badge) | top_clv_quantile 0.9 | kg/policy.yaml:18; nba/kg/segments.py:25-31,127-144 | README §6.13 |
| **Detail contact_fatigue.** MAINGAU: too many contacts cause fatigue. Team: the flag is set at ≥ 2 delivered contacts in 30 days, or ≥ 3 ignored/dismissed in 90 days, counted from nba_action_history only | fatigue_contacts_30d 2; fatigue_ignored_90d 3 | kg/policy.yaml:19-20; nba/kg/segments.py:145-149 | README §6.13 |
| **Detail annoyed_before, prefers_en.** MAINGAU: show annoyed feedback; content is in German. Team: annoyed_before = customer_reaction annoyed or dismiss_reason customer_upset; prefers_en = preferred_contact_language en (content stays German) | — | nba/kg/segments.py:150-157 | README §6.8, §6.13 |
| data_inconsistent: any CDR received after eval, or one of the hard-coded tickets | TK-200565, TK-200640 | nba/kg/segments.py:22,158-163 | K8 |
| An outlier (special need, never bulk-approved) has any of these flags: service_critical, no_marketing_channel, negative_clv, annoyed_before, prefers_en | 5 flags | nba/kg/segments.py:21,172 | README §6.13 |

### 2.3 Valuation and propensity

**Valuation**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail.** MAINGAU: CLV_now = clv_eur. Team: ΔCLV is computed against a recomputed CLV_now_model (from annual_margin, cost_to_serve, churn), so the rounding in clv_eur (up to 3.05 €) never shows up as a gain. clv_eur is still shown, and both values are logged | CLV(margin, cost, churn) | nba/engine/value.py:32,37,61 | README §6.5 |
| Every churn value fed into CLV is clamped (the workbook only says that a cancellation sets 0.95) | churn ∈ [0, 0.95] | nba/engine/value.py:34-36 | README §6.5 |
| **Detail.** MAINGAU: base churns, the 0.8 factor (min 0.5), drivers and 0.95, but not how they combine. Team's reconstruction: mean of the active bases × max(0.8^(lines−1), 0.5) + drivers; cancellation_pending counts as active; 3 decimals; no active line → the given churn. It is a check only, and valuation uses churn_prob_12m | exact for 718 customers | nba/engine/churn.py:49-70 | README §6.5 |
| Churn-driver labels are parsed: "N tickets in 12m" with N ≥ 2 counts once; "dunning level 2/3" → dunning_ge2; the multi-product and cancellation labels are not increments; an unknown label raises a not-enough-data error | — | nba/engine/churn.py:9-16,31-46 | README §6.5 |
| **Detail sales/upsell accept.** MAINGAU: the catalog margin and churn effect. Team: the 0.8 multi-line factor and the +12 €/line cost are *not* applied on top (to avoid double counting) | catalog effect only | nba/engine/value.py:47-50 | K7 |
| **Detail one-off accept.** MAINGAU: add the margin once. Team: added undiscounted at t = 0 | + annual_margin_if_bought_eur | nba/engine/value.py:49 | README §6.5 |
| **Detail P-EN-02 accept.** Team: churn − 0.10. The catalog −0.10 is not applied again and no margin is added. Without the driver the tuple becomes DATA-MISSING | churn − 0.10 | nba/engine/value.py:43-46 | README §6.5 |
| **Detail P-SV-01 accept.** Team: the service drivers are open_complaint, tickets_12m_ge2, csat_le2, dunning_ge2 and failed_charges_30d_ge3 (price guarantee and HEMS are excluded). With a pending cancellation churn stays 0.95, so the fix scores −15 € → NO_ACTION | resolution cost 15 € | nba/engine/churn.py:16; nba/engine/value.py:40-42 | README §6.5 |
| **Detail reject branch.** MAINGAU: +0.05 during an open complaint or dunning. Team: dunning means level ≥ 1 (the churn driver uses ≥ 2); a complaint means status open and category complaint; it applies to every non-service type, retention included | +0.05 | nba/engine/value.py:51-55 | README §6.5 |
| **Detail contact cost.** Team: app push uses the pop-up cost of 0 €. The new service_agent channel costs 0 €, and its resolution cost sits in the accept branch | 0 € | nba/engine/value.py:9-21 | README §6.7 |

**Propensity and confidence**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail p data.** MAINGAU: rates by offer × channel × tone vs control. Team: treated = control_group false and delivered; conversion = converted_within_14d; control is counted only at offer and global level; an agent "accepted" is not a conversion | — | nba/engine/propensity.py:24-39 | README §6.6 |
| Only history with decided_at ≤ eval_time is used for p, calibration and look-alike (no leak) | decided_at ≤ eval_time | nba/engine/runtime.py:48-49; nba/learn/evidence.py:41-42 | default, not confirmed |
| Legacy rows sent without a consent check stay in the p data as observations | 297 delivered + 36 control rows kept | config/nba.yaml:12; nba/engine/impact.py:180-187 | Q-NBA-10 |
| The default p is the shrunk treated rate, **not** the uplift that spec C4 asks for. Uplift is reported for comparison | p_mode: rate | config/nba.yaml:6; nba/engine/config.py:107-108 | K1 (MG-100023 → P-AS-01) |
| **Detail backoff.** MAINGAU: n < 30 → offer × channel. Team: continues on to offer, then global | n_min 30; L3 → L2 → L1 → L0 | config/nba.yaml:7; nba/engine/propensity.py:110-120 | K2 |
| Rate shrinkage at levels L3–L1. L0 is the raw global rate 69/2,022 ≈ 3.41%. The 0.034 is a fixed rounded constant | p = (conv + 0.034 × 30) / (n + 30) | config/nba.yaml:8-9; nba/engine/propensity.py:126-128 | K1 |
| **Detail uplift mode.** Team: p is floored at 0 and uses the unshrunk rate. The baseline is the offer's own control rate when it has ≥ 30 control rows, otherwise the global control rate 5/248 ≈ 2.0% | p = max(0, rate − baseline) | nba/engine/propensity.py:121-128 | README §6.6 |
| P-SV-01 has no history, so the team assumes a success probability. It is always labelled low confidence | p_service_success 0.5 | config/nba.yaml:10; nba/engine/propensity.py:102-104 | K2; default, not confirmed |
| **Detail confidence.** MAINGAU: labels high/medium/low, and n < 30 → low. Team: **high only at offer × channel × tone with n ≥ 100; medium only at that level with 30 ≤ n < 100**. Everything else is low: any backoff level, generic offers, the P-SV-01 assumption and overrides. A low label adds "Low confidence: parent-level rate or assumed success probability" | high_min_n 100; medium_min_n 30; level L3 only | config/nba.yaml:19-21; nba/engine/propensity.py:129-132; nba/engine/assemble.py:50-51 | README §6.6; default, not confirmed |
| Generic tuples use the global catalog average (3.4% rate, ~1.4% uplift) and are not calibrated; look-alike can still adjust them for profiled customers. The key generic_p_level is not read (the global level is hard-coded) | L0 | config/nba.yaml:11; nba/engine/propensity.py:76,111-120 | D1 |
| **Detail evidence line.** MAINGAU: show n. Team: the line shows conversions/n, level, mode, control counts and baseline. treated − control is labelled "descriptive difference, not causal uplift". k is shown only when abs(k − 1) ≥ 0.01 | — | nba/engine/assemble.py:33-48 | README §6.6 |
| Calibration: p is scaled by the engine's own track record for the same offer × channel × tone. Expected buys = sends × the rate-mode p of the chosen level. Skipped when there are no sends, and for generic offers, P-SV-01 and overrides. Rate mode: min(1, p × k); uplift mode: max(0, rate × k − baseline) | k = (observed + 5) / (expected + 5), within 0.2–3.0 | config/nba.yaml:14-17; nba/engine/propensity.py:51-90; nba/engine/config.py:117-121 | whiteboard 27 Oct; README §6.6 |
| A reviewer-approved p from a learning fix case replaces the estimate. Lookup order: offer·channel·tone → offer·any·tone → offer·channel → offer. The override needs p in [0,1], a case and approved_by. It is labelled low confidence, and calibration and look-alike do not apply to it | p_overrides (none configured) | nba/engine/propensity.py:42-48,94-101; nba/engine/config.py:123-127 | feedback loop (nba/learn) |

### 2.4 Ranking and timing

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| Tie-break for equal ΔCLV: higher p, then lower contact cost, then offer_id, then tuple_id | (−ΔCLV, −p, cost, offer_id, tuple_id) | nba/engine/rank.py:8-10 | default, not confirmed |
| **Detail.** MAINGAU: evaluate per offer × channel, and pick the tone. Team: tone is not a free choice; each customer gets one tone (the inferred one) for all tuples | — | nba/kg/rules.py:338-341; nba/engine/assemble.py:62-100 | default, not confirmed |
| **Detail.** Mentor: DEFER_UNTIL the earliest valid date. Team: a tuple allowed now always wins over a waiting one, even a generic tuple over a held signal tuple. Only when nothing is allowed now is the best waiting tuple chosen. Profiled customers prefer waiting signal tuples over waiting generic ones | act now first | nba/engine/assemble.py:79-99 | K12; rule-center §5 |
| **Detail send time.** MAINGAU: "suggested send time". Team: the next weekday after eval. E-mail/newsletter 10:00, SMS 18:00, call 10:00 (window 10:00–16:00). Pop-up/push at the "next login". Service "immediately, with the open ticket". A deferred action gets the first slot at or after deferred_until | email_hour 10; sms_hour 18; call_window 10:00-16:00 | config/nba.yaml:23-26; nba/engine/schedule.py:5-16 | README §6.7 |
| P-EN-02 card note: "Contact before the price guarantee expires on {date}". Content starts with "Ihre/Deine Preisgarantie endet am dd.mm.yyyy" (earliest date) | — | nba/engine/assemble.py:55-58; nba/engine/content.py:36-40 | README §6.7 |
| **Detail reason line.** MAINGAU: a one-line reason with signals. Team wording: "{first signal reason} → {offer} via {channel}; ΔCLV +x €, p y% (confidence)", prefixed with "Held back until …" when the action waits. NO_ACTION reads "No eligible action with positive expected ΔCLV. Reasons: {rule ids}" | — | nba/engine/assemble.py:175-181,212-218 | default, not confirmed |
| **Detail alternatives.** MAINGAU: two or three. Team: up to three (ranks 2–4), each with "Lower expected ΔCLV by €x" or a tie-break note | — | nba/engine/assemble.py:219-223; nba/engine/export.py:41-46 | default, not confirmed |
| **Detail service mode.** MAINGAU: an open ticket triggers it. Team: S2 (failed charging) and S13 (dunning/cancellation) trigger it too | S2, S12, S13 | nba/engine/assemble.py:207-210 | README §6.3 |
| **Detail checklist.** MAINGAU: the six checks. Team: no checklist for NO_ACTION; a deferred action fails contact_cap; any data-quality warning fails data_fresh; service is marked exempt | — | nba/engine/assemble.py:146-167 | Q-KG-19 |
| **Detail legacy comparison.** MAINGAU: the latest rule_id. Team: the latest row with decided_at ≤ eval (ties by action_id), valued with today's model and tone Sie if missing; R-SHOP-GENERIC is valued as a generic offer; tagged ECON-NONPOSITIVE / DATA-MISSING / CONSENT-PROFILING when these apply | — | nba/engine/assemble.py:103-132 | default, not confirmed |
| **Detail tone cues.** MAINGAU: Hi, danke dir, tschüss / Sehr geehrte, Mit freundlichen Grüßen. Team adds: hey, du, dir, dein…, lg (weight 1) and viele grüße (0.5) for Du; Ihnen and capitalised Ihr/Ihre mid-sentence for Sie | cue lists, weights | nba/profile/tone.py:13-35 | README §6.8 |
| **Detail tone method.** Team: only customer-written text counts (message_text, and transcript lines starting "Kunde:"). Each message is labelled by its du vs sie score, and the majority of messages decides; a tie goes to the newsletter step. The newsletter step decides only with ≥ 2 clicks on du/sie campaigns and a winning share of ≥ 2/3 | min_newsletter_clicks 2; share ≥ 2/3 | config/cards.yaml:10-11; nba/profile/tone.py:47-113 | README §6.8 |

### 2.5 Rules and contact limits

**Compliance (tier 1) as built**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| C-01: an unknown or missing consent status counts as not_given (fail closed) | unknown → not_given | nba/kg/rules.py:86-91 | README §6.1 |
| **Detail C-03.** MAINGAU: an unsubscribe = withdrawn. Team: it withdraws newsletter_email only (not marketing_email); an unsubscribe on any date counts; it overrides only a stored "granted" | unsubscribe_withdraws: [newsletter_email] | config/kg.yaml:22-23; nba/kg/rules.py:82-94,134 | K9 (Q-KG-03) |
| **Detail C-04.** MAINGAU: a withdrawal cancels approved-but-unsent actions. Team: the card shows "n/a". The rule is enforced only in event replay: after each event the pending card is re-checked against the KG gates and the cap (not the tier-2 rules) and revoked if blocked. A personalised card is revoked when profiling consent goes. A cap block that frees by deferred_until does not revoke. A revoked card stays revoked, and a sent card cannot be recalled | CANCEL_PENDING via replay | nba/kg/events.py:265-267,324-343; nba/engine/rulecenter.py:443-444 | rule-center §2 |
| **Detail C-05 (D1).** MAINGAU: no personalisation without profiling consent. Team: contract and device facts also count as personalisation, so every marketing signal (S1, S3–S11) is blocked as CONSENT-PROFILING. Only generic and service tuples remain, the tone is fixed to Sie, and an override to Du is refused with 409 | profiling_off: marketing_path generic, tone sie | config/kg.yaml:9-12; nba/kg/rules.py:251-253,303-313,411-415; api/app.py:145-146 | D1 (26 Oct); K3; Q-KG-01 |
| **Detail exclusion scope (C-06/07/08).** MAINGAU: block "sales content". Team: blocks action types sales, upsell, **retention** (P-EN-02) and one_off; never service | blocks [sales, upsell, retention, one_off] | kg/policy.yaml:89-92; nba/kg/rules.py:171-178 | K10 |
| **Detail C-07.** Mentor: an open complaint. Spec A4: any open ticket. Team: any open ticket (tightened) | status = open, any category | kg/policy.yaml:91,103; nba/kg/predicates.py:376-378 | R2 |
| **Detail C-08.** Team: a cancelled Autostrom contract blocks all sales, not only e-mobility, with no limit on how long ago it was cancelled | autostrom_cancelled_scope: all_sales | config/kg.yaml:19-20; nba/kg/rules.py:171-178 | K6 (Q-KG-02) |
| **Detail C-09.** Team: a design rule only, with no runtime check. Dunning is read only by EXCL-DUNNING and by S13, a team trigger that routes to service | effect NONE | kg/policy.yaml:105 | README §6.2 |
| **Detail mapping.** Team: C-01 → CONSENT-CHANNEL + CHANNEL-AVAILABLE; C-02/C-03 → CONSENT-CHANNEL; C-04 → replay; C-05 → CONSENT-PROFILING; C-06 → EXCL-DUNNING; C-07 → EXCL-OPEN-TICKET; C-08 → EXCL-CANCELLATION + EXCL-AUTOSTROM-CANCELLED; CONTACT-CAP = B-02; HOLDING-PRECONDITION = B-07 | — | kg/policy.yaml:96-105; nba/kg/policy.py:229-236; nba/kg/rules.py:28 | rule-center §2 |
| **Detail tier lock.** Mentor: tier 1 can only be tightened. Team: edits to any C-xx or to B-07 are refused (403). Tightening is done with a custom rule marked "hard", but that flag is display-only, so the rule can still be switched off or deleted | 403 | nba/engine/rule_registry.py:36,191-193; nba/engine/rulecenter.py:46 | rule-center §2 |
| Service tuples (P-SV-01 via service_agent) are never blocked by exclusions, marketing consent, the contact cap or any tier-2 rule | service exempt | nba/kg/rules.py:288-301; nba/engine/rulecenter.py:373 | K5 "marketing only"; rule-center §5 |
| A customer with no consented marketing channel gets one blocked row: "only service contact is possible" | — | nba/kg/rules.py:280-282 | default, not confirmed |

**Contact limits and tier 2 as built**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail B-02 cap.** Spec: N not given. Mentor: 2 per 30 days, all channels, newsletters count. Team: newsletters do **not** count (they count only in B-01); service contacts do not count; the window is (t − 30 d, t]; capped tuples wait (DEFER_UNTIL) instead of being dropped | max_contacts 2; window_days 30; sources [nba_history, service_feedback] | config/kg.yaml:25-28; nba/kg/rules.py:50-69; nba/engine/rulecenter.py:306-309 | K5; R1 (Q-KG-25) |
| B-02 fallback when config omits it: 2 / 30 days, nba_history only. B-02 cannot be switched off (422: raise the limit instead), and its window is ≤ 365 days | — | nba/kg/policy.py:107-114; nba/engine/rule_registry.py:199-205,228-232 | default, not confirmed |
| **Detail shared counter.** Mentor: it merges four sources, including the engine's own log. Team: the decision-log source exists but is not wired in, so engine actions approved in the demo are not counted. Duplicates are removed by channel + timestamp, and each rule picks its own sources | 3 sources wired | nba/kg/contacts.py:21-82 | rule-center §4 |
| **Detail window.** Mentor: DEFER_UNTIL the earliest valid date. Team: exact timestamps in (t − W, t]. The earliest free time = the time of the (count − limit + 1)-th oldest contact + W | free_from = inside[n − limit].ts + W | nba/kg/contacts.py:85-101 | rule-center §4 (counting from midnight would move B-01 hits from 328 to 449) |
| **Detail B-01 / B-04 sources.** Team: B-01 counts the channels newsletter_email + email from history + newsletters; B-04 counts history only | 5 / 90 d; 1 / 90 d | config/nba.yaml:35-37,41-43 | rule-center §4 |
| **Detail B-05.** Team: counted per customer × offer across channels, with no look-back limit. The timestamp is response_at, or decided_at if missing. Only responses ≤ eval count, and control rows are not filtered out | min_responses 2; cooldown 60 d | config/nba.yaml:44-46; nba/engine/rulecenter.py:280-288 | R3 |
| **Detail B-06.** Team: applies to every non-service type (retention and upsell included); only the latest resolved ticket counts; a resolved_at after eval is ignored | cooldown 14 d | config/nba.yaml:47-48; nba/engine/rulecenter.py:290-297 | K8 |
| **Detail B-07.** Mentor: on by default. Team: locked (cannot be switched off, 403), applied as the KG holding gate before valuation | LOCKED | nba/kg/rules.py:28,207-222; nba/engine/rule_registry.py:35-36,125-126 | default, not confirmed |
| **Detail B-09.** Team: ISO week of the chosen action's deferred_until, send_at or eval. The highest ΔCLV keeps its slot, with ties by customer_id. Overflow customers are re-decided with calls held until next Monday 00:00, so they switch channel or wait. The pass runs once. If several caps name one channel, the smallest applies | per_week outbound_call 50 | config/nba.yaml:51-52; nba/engine/rulecenter.py:490-530; nba/engine/runtime.py:62-76 | rule-center §5 |
| **Detail order.** Mentor: tier 1, then tier 2, before ranking. Team: tier 1 and B-07 drop tuples before valuation; tier 2 and memory run after valuation (B-08 needs ΔCLV); service and ΔCLV ≤ 0 tuples skip tier 2 | gates → value → tier 2 → rank | nba/engine/assemble.py:62-99,188-195; nba/engine/rulecenter.py:366-376 | rule-center §5 |
| **Detail block vs defer.** Mentor: the strictest rule wins. Team: any block drops the tuple. A tuple held only by defers waits until the **latest** of the holding rules' dates | until = max(defer dates) | nba/engine/rulecenter.py:376-406 | default, not confirmed |
| A P-EN-02 tuple held until on or after the guarantee end date is blocked, not deferred, because the contact would come too late | until ≥ guarantee end → block | nba/engine/rulecenter.py:371,384-397; nba/engine/content.py:18-26 | rule-center §5 step 3 |
| **Detail rule report.** Mentor: a checklist row per rule and the counter line. Team: a rule reports block/defer only if it actually stopped a tuple; otherwise it reports pass ("limit reached; nothing held"), or off when inactive. SMS was added to the counter line: "Email 3/5 (90 d) · Total 1/2 (30 d) · Call 0/1 (90 d) · SMS 0/1 (90 d)" | COUNTER_LABELS | nba/engine/rulecenter.py:29,427-484 | default, not confirmed |

**Rule Center mechanics**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| Custom conditions: entity, column, one value, and an operator. >= and <= need a number; within_days needs 1–365 days on a date column | =, !=, >=, <=, within_days | nba/engine/rulecenter.py:26,64-74; nba/engine/rule_registry.py:274-283 | rule-center §6 |
| Bounds: every day setting is 1–365; max, min_responses and per_week are ≥ 1; min_eur is ≥ 0; only the 6 marketing channels; B-05 responses come from {dismissed, ignored, viewed, clicked}. A bad rule fails on load (ValueError) or on edit (422) | MAX_DAYS 365 | nba/engine/rulecenter.py:25-28,57-117 | default, not confirmed |
| **Detail effects.** Mentor: 8 effects. Team: REQUIRE_APPROVAL and CANCEL_PENDING are refused for custom rules | 6 effects allowed | nba/engine/rulecenter.py:22-24,127-128 | default, not confirmed |
| Effect semantics: "auto" means BLOCK_OFFER for a condition on product_catalog, else BLOCK_ALL_SALES. BLOCK_CHANNEL without a list blocks all 6 channels. DEFER_UNTIL waits eval + days (default 7). DOWNGRADE blocks personalised tuples. BLOCK_ALL_CONTACT applies to marketing tuples only | DEFER default 7 d | nba/engine/rulecenter.py:223-226,341-354 | default, not confirmed |
| Matching: a condition matches if any row matches. A missing column never matches, and null matches only "!=". within_days is abs(value − eval) ≤ N, so past and future dates both count. A consent condition is written "type:status". Active sub-rules narrow the parent (AND) | — | nba/engine/rulecenter.py:166-220 | rule-center §6 |
| The "Add rule" field catalog has 14 entities, with no ID or free-text columns. Enums, or text with ≤ 12 distinct values, get "is v". Dates get "within 30 / 90 days". Integers with ≤ 6 distinct values get "≥ v" | — | nba/engine/rule_registry.py:23-32,54-92 | default, not confirmed |
| **Detail edits.** Mentor: the rule record. Team: only custom rules can be deleted. Business-rule edits may change parameters only. Custom-rule edits may change name, effect, days and channels. Every edit needs "by". U-n IDs are never reused | 403 / 404 / 422 | nba/engine/rule_registry.py:172-259; api/app.py:333-335 | default, not confirmed |
| **Detail what-if.** Mentor: a preview before saving. Team: every customer is decided under the current and the proposed rules, and nothing is saved. A decision counts as changed if its tuple or waiting date differs. The preview shows 10 examples by largest abs ΔCLV change, plus totals | examples 10 | nba/engine/rule_whatif.py:47-59; api/app.py:374-393 | default, not confirmed |
| **Detail versioning.** Mentor: the rule record has a version. Team: the version is "rs-1:" + the first 12 hex of a SHA-256 over all rules. Each edit is appended to out/rule_versions.jsonl and replayed at API start; an edit that no longer applies is skipped with a warning | rs-1:&lt;sha256[:12]&gt; | nba/engine/rulecenter.py:156-160; api/app.py:189-215,333-344 | rule-center §6 |
| An approval stays valid while the state_revision and the policy, value_model, propensity and templates versions match. The rules version is ignored, and the approval is re-checked instead. B-02 edits, kg/policy.yaml parameters, p_overrides or a look-alike refit drop approvals. rule-center §6 says otherwise | — | api/app.py:224-240; nba/engine/config.py:46,90-100 | code comment api/app.py:229 (doc conflict) |
| Demo rules shipped switched off: U-1 no StromAktiv in Köln; U-2 no e-mail/newsletter after a complaint; U-3 hold sales 30 days for movers; U-4 no push/SMS/call for birth_year ≤ 1959 | active: false | config/nba.yaml:53-68; tests/test_engine_rules.py:232 | rule-center §10 |
| **Detail legacy audit.** Mentor: audit the history. Team: each delivered non-control send is checked at decided_at (own send excluded) against C-01/02/03/06/07/08, B-02 and the frequency/cooldown rules. Consent uses the latest status (an approximation). The audit's C-07 counts complaints only. B-07/B-08/B-09 are not audited | 829 / 114 | nba/engine/rule_audit.py:14-106 | rule-center §8 |

### 2.6 Learning and memory

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail evidence.** Slides: control group + uplift. Team: treated sends vs the offer-level control group as baseline for every subgroup (channel, tone, content) | — | nba/learn/evidence.py:39-68 | default, not confirmed |
| Bayesian uplift: Beta posteriors with prior strength 30 toward the global treated and control rates. 90% interval ± 1.645 sd. P(uplift > 0) on a 100,000-point grid | prior_strength 30 | config/learn.yaml:7; nba/learn/stats.py:10,13-74 | default, not confirmed |
| Traffic light per offer and per offer × channel, checked in this order: < 30 treated → amber; ≥ 100 sends with 0 conversions → red; P ≤ 0.15 → red; P ≥ 0.90 → green; otherwise amber | min_treated 30; red 0.15; green 0.90; red_zero_response_n 100 | config/learn.yaml:7-14; nba/learn/health.py:26-50 | default, not confirmed |
| Green patterns are appended to ledger.jsonl as evidence, never as rules, with no duplicates | — | nba/learn/health.py:53-56; nba/learn/__main__.py:41-48 | default, not confirmed |
| Fix cases: one per red offer (an offer × channel only if its offer is not red). Splits: target_signal, channel, tone, content_variant. A subgroup is usable with ≥ 5 treated. A split explains the failure if the spread of P is ≥ 0.30 | min_subgroup 5; min_contrast 0.30 | config/learn.yaml:19-21; nba/learn/diagnose.py:87-116,172-176 | default, not confirmed |
| Fix options: S (p = 0), K (keep and measure), and A depending on the layer: p from signal-matched sends, signal-only, p = 0 for subgroups with P < 0.5, or a template rewrite | losers: P < 0.5 | nba/learn/diagnose.py:99-169 | default, not confirmed |
| **Detail backtest.** MAINGAU: the test customers. Team: re-run every customer whose card valued the offer, count the changed decisions, and flag changes to the 12 reference customers | 12 customers | config/learn.yaml:30; nba/learn/backtest.py:15-45 | default, not confirmed |
| Apply: the CLI writes p into config/nba.yaml p_overrides with case, option, approved_by and approved_at, and logs to fix_log.jsonl. Hard rules still run before p | p ∈ [0,1] | nba/learn/__main__.py:75-99; nba/engine/config.py:123-127 | default, not confirmed |
| Harm watch: an offer with ≥ 10 agent-feedback rows and ≥ 35% upset/annoyed is flagged "watch" (as evidence only) | min_feedback 10; watch_rate 0.35 | config/learn.yaml:24-26; nba/learn/evidence.py:73-79 | default, not confirmed |
| Look-alike scope: only green offers, and only customers with profiling consent (both when scored and as peers). Not used for assumptions or overrides. Applied after calibration. Refit on every load | lookalike.active true | config/learn.yaml:32-38; nba/learn/lookalike.py:131-136,176-200; nba/engine/propensity.py:138-150 | config/learn.yaml comment |
| Look-alike formula: take the 25 nearest recipients (own send excluded, ties by customer_id). peer_rate = (Σ sim × good + 10 × pool_rate) / (Σ sim + 10); lift = min(peer_rate / pool_rate, 3.0) with no lower bound; p = min(1, p × lift). A good outcome is a treated delivered send with converted_within_14d and conversion_value_eur > 0 | neighbours 25; prior_strength 10; max_ratio 3.0 | config/learn.yaml:39-41; nba/learn/lookalike.py:123-173; nba/engine/propensity.py:145-149 | default, not confirmed |
| Similarity = exp(−d²/2), where d² is the mean squared robust z-difference (median, IQR/1.349) over 12 features: age, household, tenure, lines, margin, CLV, churn, portal sessions, minutes per session, tickets, CSAT, kWh. Missing values are skipped. The summary counts lift > 1.2 as "more likely" and < 0.8 as "less likely" | 12 features, weight 1 | config/learn.yaml:42-54; nba/learn/lookalike.py:38-58,99-129,215-220 | default, not confirmed |
| **Detail learning impact.** MAINGAU: the ΔCLV formula. Team: three runs (baseline with k = 1, no look-alike and no memory; + evidence; + memory) and attribution of the changes to each; p is shown as rate × k × lift; the k table shows the top 15 by abs(ln k), plus 60 examples | 3 runs | nba/learn/impact.py:8-10,26-34,61-149 | default, not confirmed |
| Customer memory reason codes (8) and memory kinds by strictness: pause_sales > block_channel > pause_offer > review > note. An unknown code becomes "other" | 8 codes, 5 kinds | nba/ai/feedback.py:24-26,205-206 | README §6.17 |
| Default memory per reason: already_has_product → pause offer 365 days; customer_upset → pause sales 30; no_time / wrong_timing → pause offer 14; not_relevant → pause offer 90; wrong_channel → block channel 90; data_wrong → review 30; other → note 30 | DEFAULT table | nba/ai/feedback.py:24-29 | README §6.17 |
| **Detail agent feedback.** Workbook: agent_action, dismiss_reason, customer_reaction. Team: only dismissed, annoyed or declined rows become memory. annoyed → customer_upset; a decline without a reason → not_relevant. Agent memory has no channel, so block_channel becomes pause_offer. Rows are merged once per feedback_id | — | nba/ai/feedback.py:30-31,138-166,227-228 | default, not confirmed |
| **Detail decision log.** MAINGAU: Reject with a reason. Team: rejected or overridden proposals (not NO_ACTION) become memory for the proposed offer + channel with the reviewer's code. No code means "other", a note with no effect | — | nba/ai/feedback.py:122-135; api/app.py:296-299 | README §6.17 |
| Memory lasts from the feedback time for N days. It is active while until > eval, with duplicates removed by source_ref. pause_sales, pause_offer and block_channel act as a DEFER_UNTIL hold named MEMORY, so block_channel waits rather than blocks. review and note have no engine effect. Service and ΔCLV ≤ 0 tuples are exempt | until = since + days | nba/ai/feedback.py:114-116,172-178,198-204; nba/engine/rulecenter.py:261-262,335-338 | README §6.17 |
| Proposals for everyone: when ≥ 3 feedback items share an offer and reason, a suggestion is raised to review the targeting or add a rule. Only a person applies it, through the Rule Center | n ≥ 3 | nba/ai/feedback.py:237-246 | README §6.17 |

### 2.7 AI steps

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| AI review clusters: act-now proposals grouped by chosen tuple + archetype. NO_ACTION, deferred and service actions are skipped. Clusters are ordered by size, then key | — | nba/ai/review.py:82-98 | README §6.17 |
| Hard review reasons, which the AI can never clear: flags service_critical, negative_clv, data_inconsistent or annoyed_before; an A4 customer with a sales/upsell/one_off proposal (retention not included); any memory of kind review (no date check); a ΔCLV or p robust z ≥ 3.5 | HARD_Z 3.5 | nba/ai/review.py:18,23,109-127 | README §6.17 |
| Soft reasons: contact_fatigue (B-01/B-02 already apply), calibration k < 0.85, z ≥ 2.5, and churn outliers. z = abs(x − median) / (1.4826 × MAD), computed in clusters of ≥ 5 with MAD > 0 | LOW_K 0.85; SOFT_Z 2.5; MIN_CLUSTER 5 | nba/ai/review.py:19,24,47-52,118-127 | default, not confirmed |
| **Detail AI pass.** Slides: the engine proposes and humans approve. Team: flagged customers go by ΔCLV, with at most 80 calls at low effort. Unknown codes and uncited IDs are dropped. Notes are ≤ 400 chars, at most 2 English sentences. The AI never proposes sending or argues against compliance, and its verdict counts only without a hard reason | ai_limit 80 | nba/ai/review.py:20-44,82,134-151 | default, not confirmed |
| In feedback, a person's reason code always wins, and the AI only classifies free text without a valid code | — | nba/ai/feedback.py:205,214 | README §6.17 |
| The AI may only make memory stricter: its kind is used only if stricter, and days = max(default, AI days clamped to 1–365). Note ≤ 400 chars, hint ≤ 300 chars. At most 60 calls at medium effort | ai_limit 60 | nba/ai/feedback.py:194-225 | README §6.17 "never loosens a rule" |
| **Detail QA invariants.** Slides: the hard rules and zero violations. Team: 8 oracles on every card: valid schema; the chosen action is a candidate; nothing sent; ΔCLV > 0 unless service; no sales (retention and one_off included) under an exclusion; a consented, unblocked channel; personalised only with profiling consent | 8 checks | nba/ai/qa.py:36,104-137 | qa.py docstring |
| **Detail QA event effects.** Team: a ticket, dunning ≥ 1 or cancellation event → the matching EXCL rule is active, there are no sales, and a pending sales card is revoked; a withdrawn consent is not used; a profiling withdrawal removes personalisation; ≥ 3 failed charges → S2; a deregistration → S1 | — | nba/ai/qa.py:37-38,140-171 | default, not confirmed |
| QA scenarios: one seed per event type at eval + 1 h, ingested 30 s later, with fixed defaults (complaint by phone, dunning 2, 3 failed AC charges an hour apart, deregistration effective +30 days). The AI tester writes ≤ 8 scenarios over a 24-customer pool, and the AI judge reviews ≤ 20 results; neither changes pass/fail | n 8; pool 24; judge 20 | nba/ai/qa.py:39,56-84,199-403; nba/ai/__main__.py:29 | default, not confirmed |
| Workflow test: 6 customers through the API (every third rejected without a backend). QA runs in out/ai_qa, never in the real decision log, and passes only with 0 failures | n_workflow 6 | nba/ai/qa.py:425-487; nba/ai/__main__.py:34-42 | default, not confirmed |
| LLM backend, auto order: Hessian.AI (if HAI_API_KEY is set) → Claude → local Ollama (if it answers within 2 s) → none, in which case the code's result stands. .env.example sets hessian | MAINGAU_LLM=auto | nba/ai/llm.py:203-232; .env.example:4 | README §6.17 |
| Hessian: vllm/Kolibri-1 (alternative GLM-Flash), timeout 120 s, temperature 0, max_tokens 8192, 3 attempts on 429/5xx (waits 2 s, 4 s), output format fallback json_schema → json_object → prompt. Claude: claude-opus-5-5, max_tokens 16000. Ollama: qwen2.5:7b-instruct. A backend that fails once is off for the rest of the run. .env sets only variables that are not already set | — | nba/ai/llm.py:27-55,72-168,188-200 | default, not confirmed |

### 2.8 UI and workflow

**Profile card (details on spec A1–B3)**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail A1.** Team: the age band is the decade of (eval year − birth_year); tenure = days / 365.25, 1 decimal | — | nba/profile/header.py:9-21 | default, not confirmed |
| **Detail A2.** MAINGAU: two percentiles. Team: percentile = share with a strictly lower clv_eur; "same product combination" = the same set of active lines; shown only with ≥ 5 peers | min peers 5 | nba/profile/value.py:37-67; nba/profile/population.py:17-20 | default, not confirmed |
| **Detail A5.** MAINGAU: 2–3 genuinely unusual highlights. Team: ≤ 3, rarest first, only if ≤ 10% of customers share it. Candidates: top 10% CLV, CLV < 0, service impact ≥ p90, DC share ≥ **2×** the mean (the spec example says 3×), ≥ 3 failed charges, PV without HEMS, data limit 3/3, tenure ≥ p90, portal sessions ≥ p90 | max 3; rarity_max_share 0.10 | config/cards.yaml:5-7; nba/profile/highlights.py:26-69; nba/profile/population.py:23-66 | default, not confirmed |
| **Detail A3.** Team: energy is held if active or cancellation_pending, and the countdown is shown for active contracts only. Autostrom kWh/month and DC share are computed over completed sessions. Shop shows the 5 newest orders. Internet is held = None and not tinted as an opportunity | shop limit 5 | nba/profile/products.py:16-105 | default, not confirmed |
| **Detail B1/B2.** Team: the timeline covers 365 days (12 × 30.44), with future dates only for active milestones. Exact trend ranges: charging 06-01–09-30, portal 07-02–09-30, newsletter 01-15–09-24, HEMS 09-01–09-30. kWh counts completed sessions only. Service window 365 days. Mobile usage_share = avg_data_used_gb_3m / data_volume_gb | timeline_months 12 | config/cards.yaml:3,13-17; nba/profile/timeline.py:13-45; nba/profile/trends.py:42-171 | README §3 |
| **Detail B3.** Team: windows are (eval − N, eval]; response rate = (clicked or converted) / delivered, where viewed does not count; "repeatedly ignored" means ≥ 2 | ≥ 2 ignored | nba/profile/fatigue.py:14-31; nba/state.py:173-180 | default, not confirmed |
| **Detail Customer 360° journey.** Team: a separate journey document covering 12 months plus milestones, one charging event per day, and facts only (no CLV, scores or payment method) | months 12 | nba/kg/journey.py:45-211 | default, not confirmed |

**Bulk approval and holdout**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| Bulk approval groups customers by identical chosen tuple. NO_ACTION rows are only counted. Groups are sorted by Σ ΔCLV, then by size | group key = chosen tuple | web/src/components/groups/model.ts:48-70 | prompts/agent-cards.md §1.2 |
| **Detail.** MAINGAU: service first, and no sales during a service case. Team: service rows (service mode or P-SV-01) are never bulk-approved; they are listed as "handle individually" and sorted by urgency_score | — | web/src/components/groups/model.ts:24-26,67-68; web/src/components/groups/ServiceList.tsx:8-21 | prompts/agent-cards.md §1.3 |
| Gate "blocked" (do no harm; cannot be ticked): archetype A4 or flag service_critical | — | web/src/components/groups/model.ts:118-123,147 | prompts/agent-cards.md §1.4 |
| **Detail gate "review"** (must be ticked explicitly). Team: an outlier flag; any failed checklist item; a missing ΔCLV or p ("No valuation"); a latest decision that was a rejection or an override to another tuple; low confidence when "Exclude low confidence" is on (off by default). Precedence: blocked > review > ready. Customers already approved are skipped | excludeLow default false | web/src/components/groups/model.ts:91-147,219-221; web/src/components/groups/PreviewSheet.tsx:70,230-235 | Q-CARDS-11 |
| **Detail preview totals.** Team: Σ ΔCLV, Σ p (expected conversions) and Σ contact cost over the contacted customers included. The total is null ("not enough data") if no row has a value | — | web/src/components/groups/model.ts:29-39; web/src/components/groups/PreviewSheet.tsx:134-139 | prompts/agent-cards.md §1.2 |
| "Approve everything" campaign: approves only customers gated "ready" in every shown group (low confidence is not excluded). It needs a name and ≥ 1 customer. The campaign is stored as CMP-{epoch ms}, with the default name "{action} · {segment} · {date}" and the filter offer/arch/pers from the URL | — | web/src/components/groups/model.ts:176-273; web/src/components/groups/CampaignDialog.tsx:100-136; web/src/lib/campaigns.ts:6-24; web/src/pages/Groups.tsx:93 | prompts/ui-overview.md §5 |
| **Detail holdout.** Slides: keep a control group (the history has 10%). Team: 10% by default for new bulk approvals. Membership = FNV-1a hash of customer_id mod 100 < pct (the same customers every time). The preview switch is on by default, and the campaign dialog allows 0–50% in steps of 5. Holdout rows are recorded but never posted or exported. Σ ΔCLV counts contacted customers only | HOLDOUT_PCT 10 | web/src/components/groups/model.ts:11,163-165,263-269; web/src/lib/decisions.ts:153-157,218-226; web/src/components/groups/CampaignDialog.tsx:17,44,189-197 | prompts/agent-cards.md §1.2 |

**Decisions**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail states.** MAINGAU: proposed → approved / overridden. Team: adds "rejected". Nothing is ever sent | approved, overridden, rejected | web/src/lib/decisions.ts:5-11 | README §6.10 |
| **Detail reject reason.** MAINGAU: Reject with a reason. Team: one of 8 codes (4 from dismiss_reason, plus wrong_channel, wrong_timing, data_wrong, other). The API refuses a rejection without a reason (422) | 8 codes | web/src/lib/decisions.ts:17-32; web/src/components/nba/DecisionBar.tsx:224-230; api/app.py:296-297 | reason feeds memory |
| **Detail override.** Team: an override needs a preset reason ("Other" also needs a note), and the presets map to codes. Only tuples the engine evaluated can be selected | — | web/src/components/customer/NbaPanel.tsx:356-375; web/src/components/nba/DecisionBar.tsx:8-10 | Q-CARDS-13 |
| **Detail API re-check.** MAINGAU: rules before ranking, and drop ΔCLV ≤ 0. Team: a human-selected tuple is refused (409 with rule IDs) if it fails a KG gate, uses Du without profiling, was not evaluated, has ΔCLV ≤ 0, is a generic fallback while a signal or service action is positive, or is blocked or held by tier 2, the cap or memory. Approving a proposal that has changed, or a NO_ACTION, is refused. Refused decisions are removed locally | 409 | api/app.py:135-170,306-313; web/src/lib/decisions.ts:126-166 | README §6.10 |
| A waiting action fails the contact_cap checklist item, so bulk approval leaves it out | — | nba/engine/assemble.py:131-138 | rule-center §5 |
| **Detail decision log.** Team: append-only in browser storage; the latest decision per customer wins, and a reviewer can undo one. The hand-off CSV holds the latest approved or overridden decisions outside the holdout, with fixed columns. The reviewer is the fixed name "demo-marketer" | maingau.decisions.v1 | web/src/lib/decisions.ts:8,168-228; web/src/components/groups/DecisionLog.tsx:8-13 | Q-CARDS-10 |
| **Detail UI locks.** Slides: marketing sets offers and limits. Team: block a channel, block an offer, or pause until a date, for one customer, an archetype or everyone. Locks only grey options out and never re-rank | 3 kinds × 3 scopes | web/src/lib/hardRules.ts:1-11,74-89; web/src/components/service/ActionsTab.tsx:146-148 | default, not confirmed |

**Worklist, Overview, Customer 360°, colours**

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| Worklist: sorted by tier P1–P5, then urgency_score. Queues: To review, Decided, Do not contact, All. Saved views: Act now (P1), Retention this month (P-EN-02 or P2), Upsell, Outliers | — | web/src/components/worklist/model.ts:10-56,175-218 | Q-CARDS-08 |
| **Detail Overview.** Slides: top NBAs across customers and segments. Team: NO_ACTION is left out; P-SV-01 gets a separate service line; actions are ranked by Σ ΔCLV, then customers, then offer ID; a missing ΔCLV adds 0, but a "valued" count is kept | — | web/src/components/overview/model.ts:100-163,218 | prompts/ui-overview.md §3 |
| Overview reasons: grouped by signal + need, "no-profiling" or "unknown"; the top 2 per action, then "+N other reasons". The text is "{signal} → {need}" only if every label exists, otherwise "not enough data". Codes appear only in the tooltip | top 2 | web/src/components/overview/model.ts:85-128,183-198; web/src/components/overview/ActionTable.tsx:31-52 | prompts/ui-overview.md §3, §4 |
| Overview segments: A0–A5 plus NP (not personalised, any archetype). Percentages use the largest remainder so they sum to 100. Links go to Groups with arch + pers=yes or pers=no. Money is shown in whole euros | 7 segments | web/src/components/overview/model.ts:14-26,64-94,139-151,202-216; web/src/components/overview/format.ts:3-7 | prompts/ui-overview.md §5 |
| **Detail Customer 360° wording.** Slides: payment data only as an exclusion. Team: any text matching dunning/payment/Mahn/Zahlung/Inkasso becomes "account status …". Payment method, dunning, tier, flags, archetype, highlights, fatigue and data quality are hidden. Engine codes (rule IDs, offer IDs, "ΔCLV", "Held back") are stripped or replaced | PAYMENT regex | web/src/components/service/plain.ts:38-79,104-115,131-132,154-179; web/src/components/service/ProfileTab.tsx:12-13 | prompts/ui-customer360.md §3.2 |
| **Detail Customer 360° blocked rows.** MAINGAU: list blocked actions with their rule. Team: one plain sentence per rule (e.g. C-07 "No sales offers while a ticket is open", B-08 "Not worth a phone call") in a fixed order. The no-offer reason priority is: exclusion → no marketing consent → contact limit → "not worth making" | — | web/src/components/service/plain.ts:93-227 | prompts/ui-customer360.md §3.4 |
| **Detail Customer 360° service.** MAINGAU: resolve first. Team: service actions are listed first while a ticket is open, with the banner "Resolve the service issue first." Waiting actions show "possible from {date}". The journey has filter chips (0-count chips hidden). Reaction buttons map to service_nba_feedback fields (the helper is not used yet) | — | web/src/components/service/plain.ts:55-57,81-89; web/src/components/service/ActionsTab.tsx:41-43,131-160; web/src/components/service/ServiceStrip.tsx:25-40; web/src/components/service/JourneyTab.tsx:50-98; web/src/lib/serviceFeedback.ts:62-91 | prompts/ui-customer360.md §3.1, §3.4 |
| Colours: MAINGAU blue #034c99 is the single accent. Yellow #f3bf00 is only for the #1 badge and the nav underline. No green or amber: states use the accent or a neutral surface with an icon. Red is only for danger (reject, blocked, negative ΔCLV, P1, withdrawn, offline, high churn). Customer 360° uses no warning colours | — | web/src/index.css:14-24; prompts/ui-colors.md:3-37 | prompts/ui-colors.md |
| Visual thresholds: tier chips go from P1 red to P5 grey, and only P1 rows are tinted. The churn meter is red at ≥ 0.5 and dark grey at ≥ 0.25. Confidence is 1/2/3 bars. A value bar is red when negative, with a 3% minimum width. Text contrast is ≥ 6.16:1 | 0.25 / 0.5 | web/src/components/Chips.tsx:5-11; web/src/components/viz.tsx:101-137; web/src/components/worklist/WorklistTable.tsx:18-20; prompts/ui-colors.md:39-50 | default, not confirmed |

### 2.9 Data and export

| Rule | Value / formula | Where | Why |
|---|---|---|---|
| **Detail event dedup.** MAINGAU: remove duplicates (same event_id + timestamp). Team: the first one seen wins, and events are applied in ingested_at order, then by event_id | key (event_id, occurred_at) | nba/data.py:183-204 | README §6.14 |
| Each fact keeps its own clock: consent per type, contract status, dunning and ticket status. An event older than that clock is "stale" and changes nothing | occurred ≥ clock | nba/kg/events.py:94-105,127-150,188-189 | README §6.14 |
| 9 informational event types never change a decision fact (portal_login, page_viewed, newsletter_opened, …). Unsupported types are only logged | INFORMATIONAL set | nba/kg/events.py:34-37,238 | README §6.14 |
| **Detail event mapping.** MAINGAU: a gas deregistration is a strong signal. Team: it sets meter_deregistered_at = occurred_at, which fires S1 at once, and the contract stays active until payload.effective_date. Other mappings: a cancellation → cancellation_pending; dunning_level_changed updates the contract whose level equals old_level; a ticket_updated for an unknown ID becomes an open placeholder ticket (never merged); charge events add an own_backend session; order_placed = "placed" (not owned); a click can fire S10; device offline | — | nba/kg/events.py:134-228,352-360 | Q-KG-07; README §6.14 |
| **Detail data contract.** Workbook: guest orders have a null customer_id, and dunning_level is 0–3. Team: all 23 sheets must exist, with unique non-null keys. customer_id must exist in customer_master (null only in shop_orders). Enums the rules use are checked (ERROR; display enums are a WARNING). Churn labels must match 9 patterns. Numeric ranges are checked (churn 0–1, dunning 0–3, …), as are ISO dates and boolean text. A date after eval is a WARNING (except price_guarantee_until) | ERROR stops the pipeline | kg/data_contract.yaml:7-102; nba/kg/intake.py:70-196 | README §6.15 |
| **Detail freshness.** MAINGAU: the checklist line "data fresh enough". Team: freshness and quality flags are warnings only and never block a decision | level warn / info | nba/kg/quality.py:1 | README §6.9 |
| **Detail freshness flags.** MAINGAU: roaming CDRs arrive up to 72 h late; gaps mean offline; customer_value is monthly. Team: FRESH-CDR = a roaming session started in the last 72 h (per customer); FRESH-HEMS = gateway not online, or < 30 September days with telemetry; FRESH-VALUE = clv_calc_date > 31 days old; SNAPSHOT-INCONSISTENT (info) = CDRs received after eval, and tickets TK-200565 / TK-200640 | roaming_late_hours 72; value_stale_days 31 | kg/policy.yaml:21-22; nba/kg/quality.py:10-47 | README §6.9; K8 |
| **Detail static export.** MAINGAU: alternatives and blocked actions. Team: per offer only the best channel is kept; the top 4 keep full checks and path; a waiting customer keeps 2 candidates; 3 alternatives; only block/defer/off rule results; one "waits until" row per offer × channel. The API keeps everything | top 4 | nba/engine/export.py:7-47; nba/contracts.py:66-70 | size budget |
| Static export budget (750 cards + journeys + index + summary + rules) | ≤ 30,000,000 bytes | tests/test_engine_build.py:31-34 | README §13.2 |
| The test report re-ranks the 13 reference customers in both modes with p and margin × 0.8 / 1.0 / 1.2 | sensitivity_pct 20 | config/nba.yaml:28; nba/engine/report.py:24,49-59 | default, not confirmed |
| Impact totals count NO_ACTION as 0 € and are labelled "model-based, mock data, not causal uplift" | — | nba/engine/impact.py:11-17 | default, not confirmed |

---

## Part 3. Open: team choices to confirm with MAINGAU

These are ordered by how much they move the numbers shown in the demo.

| # | Team choice | Current value | Effect in the demo | Question to ask |
|---|---|---|---|---|
| 1 | p from the shrunk treated rate, not uplift (K1) | `p_mode: rate` | Every p and ΔCLV. Under uplift P-AS-01 has p = 0, so MG-100023 could never get Autostrom | Spec C4 says "minus the control baseline". Is ranking on the treated rate, with uplift shown as evidence, acceptable? |
| 2 | Contact cap B-02 without newsletters (R1) | 2 per 30 days; newsletters and service not counted | Counting newsletters changes 332 decisions: act now 518 → 240, ΔCLV now €8,898 → €5,562 | Do newsletters count toward the 2-per-30-days cap? |
| 3 | Shrinkage prior | prior mean 0.034, strength 30 pseudo-sends | Pulls every small offer × channel × tone group toward 3.4% | Which prior and strength, or none? |
| 4 | P-SV-01 success probability (K2) | `p_service_success: 0.5` | Sets the ΔCLV of every service fix, so it decides when service beats sales | What success rate does a proactive service fix have? |
| 5 | Confidence labels | high = n ≥ 100, medium = 30–99, both only at offer × channel × tone; everything else low | The label on every card and the "Exclude low confidence" filter | Is n ≥ 100 right for "high"? Should a backed-off p ever be medium? |
| 6 | Backoff to offer and global; generic offers at the catalog average (K2, D1) | global 3.4% rate (1.4% uplift) | p for the 8 offers without history and for every generic offer (e.g. MG-100112) | What p should offers with no history get? |
| 7 | Calibration and look-alike adjust p | k = (obs + 5)/(exp + 5) in 0.2–3.0; lift ≤ 3.0 (25 neighbours, prior 10) | Can scale p from 0.2× up to 3× (calibration) and up to 3× (look-alike) | May p use the engine's own track record and similar customers, or show base rates only? |
| 8 | B-08 call floor (mentor default, kept R5) | €10 | Drops low-value calls; under uplift MG-100112 loses its call | Keep €10? |
| 9 | Multi-line effect for a new line not applied (K7) | catalog churn_effect only | ΔCLV of every cross-sell offer | Is the bundle effect already in churn_effect_if_bought? |
| 10 | Cancellation handling (K10) | churn stays 0.95, so the P-SV-01 fix = −15 €; retention blocked | Customers in cancellation get NO_ACTION | Should a retention or service contact be possible during cancellation_pending? |
| 11 | Generic path without profiling consent (D1, K11) | contract data removes owned products; generic offers by any channel, incl. phone | MG-100112 → generic StromAktiv call; MG-100004 / MG-100012 | Is filtering owned products with contract data allowed without profiling consent? Are generic calls OK? |
| 12 | Holdout for new approvals | 10%, fixed hash per customer | Σ ΔCLV excludes held-out customers | Is 10% right? Should it be set per campaign? |
| 13 | Exclusion scopes (K6, K9) | a cancelled Autostrom contract blocks all sales; an unsubscribe withdraws the newsletter only | Which customers get any sales offer at all, and by e-mail | Only e-mobility for K6? Should an unsubscribe also withdraw marketing_email? |
