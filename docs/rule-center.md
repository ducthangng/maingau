# Rule Center: rules that block or limit actions

Status: **specified, not built** (26 Oct 2026). Source: the rule spec agreed with the mentor. This file translates that spec into English, checks every number in it against `maingau_nba_mockdata.xlsx` (evaluation time 2026-09-30 23:59:59), and maps each rule to the existing code.

**Owners:**
- **Agent NBA:** the tier 2 rule engine, DEFER, capacity, rule versions, what-if, legacy audit, rule log and API.
- **Agent KG:** the tier 1 gates (already built) and the shared contact counter.
- **Agent CARDS:** the Rule Center page and the card display, later. Their folder is being edited by a team member, so do not touch `web/` or `nba/profile/`.

Open decisions are listed in §9. Build nothing that depends on them until they are answered.

## 1. Purpose

Marketing sets rules that block or limit actions. Every rule is evaluated **before ranking**, on each offer × channel tuple, and changes each customer's NBA directly. The page should be minimal: one page that lists the rules, a form to edit them, and a what-if preview before saving.

## 2. Tier 1: compliance rules

Always on. They can never be switched off or loosened, only tightened.

| ID | Rule | Data | Effect | Already built as | State |
|---|---|---|---|---|---|
| C-01 | A channel needs its consent `granted` (map below) | `consent_status` | BLOCK_CHANNEL | `kg/policy.yaml → channels`, `nba/kg/rules.py` channel gate (`CONSENT-CHANNEL`) | done |
| C-02 | Newsletter also needs double opt-in | `double_opt_in_confirmed_at` not null | BLOCK_CHANNEL | `needs_doi: true` | done |
| C-03 | Unsubscribe counts as withdrawn at once, even if `consent_status` is not updated yet | `newsletter_performance.unsubscribed` | BLOCK_CHANNEL `newsletter_email` | `consents()` override | done |
| C-04 | Withdrawn consent stops everything at once, including actions approved but not sent | `consent_status.updated_at` + consent events | CANCEL_PENDING | `nba/kg/events.py` revokes pending cards on replay (29 at 30.09 → 01.10) | done for cards; NBA must also cancel approved-not-sent entries in its decision log |
| C-05 | No profiling consent → no behaviour or purchase signals | `profiling_analytics` | DOWNGRADE_TO_NON_PERSONALISED | D1 generic path | done |
| C-06 | Dunning ≥ 1 → no sales, service only | `energy_contracts.dunning_level` | BLOCK_ALL_SALES | `EXCL-DUNNING` | done |
| C-07 | Open complaint → no sales | `service_interactions` open + complaint | BLOCK_ALL_SALES | `EXCL-OPEN-TICKET` blocks on **any** open ticket (stricter) | see R2 |
| C-08 | Cancellation in progress → no sales | `energy_contracts.status = cancellation_pending`; `autostrom_contracts.status = cancelled` | BLOCK_ALL_SALES | `EXCL-CANCELLATION`, `EXCL-AUTOSTROM-CANCELLED` | done |
| C-09 | Payment data only as an exclusion | design rule | — | README §6.2 | done |

Channel → consent map (identical to README §6.1):

| Channel | Consent | Extra condition |
|---|---|---|
| `newsletter_email` | `newsletter_email` | DOI confirmed |
| `email` (1:1) | `marketing_email` | — |
| `outbound_call` | `marketing_phone` | — |
| `sms` | `marketing_sms` | — |
| `portal_popup` | `portal_app_personalisation` | `customer_master.portal_account = True` |
| `app_push` | `portal_app_personalisation` | `customer_master.app_installed = True` |

**What KG still does for tier 1:**
- give every tier 1 check its C-xx ID alongside the existing ID, so cards and logs can show C-xx without breaking current checks;
- expose the tier 1 list read-only for the Rule Center.

## 3. Tier 2: business rules

Marketing creates, edits and switches these rules on or off. Each has a default.

"Today" below means the 750 decisions the engine makes now: 549 marketing actions, 47 service actions and 154 NO_ACTION.

| ID | Rule | Default | Spec's claim, checked | Impact today if switched on | State |
|---|---|---|---|---|---|
| B-01 | Max N emails per customer in W days | N=5, W=90 | **Confirmed.** 673 customers got ≥ 1 email in 90 days, the median is 4, and 328 are at ≥ 5 when newsletters count | Email blocked for 328 customers, hitting 68 of today's 118 email/newsletter decisions | new |
| B-02 | Max N contacts per customer on all channels in W days | N=2, W=30 | **"p90 = 4" not reproduced.** p90 is 3 with all sources and 2 with NBA history only; the p90 of each customer's busiest 30 days is 5. **The "~4% → 1.2% above 4 actions" claim is reproduced, but per customer over Jun–Sep, not per 30 days:** 3.8–4.1% conversion per action for customers with 1–4 actions, 1.2% for those with 5–6 (420 actions) | Counting newsletters: **336 of 549** marketing decisions deferred, 204 of them until 03.10. NBA history only: 0 more than today | exists as `contact_cap` 2/30 in `config/kg.yaml`, NBA history only; see R1 |
| B-03 | Max 1 call per customer per 90 days | 1/90 | **Confirmed:** the history max is 2 in 90 days (5 customers) | 73 customers had a call in the last 90 days, hitting 1 of today's 12 chosen calls | new |
| B-04 | Max 1 SMS per customer per 90 days | 1/90 | **Confirmed:** the max is 2 in 90 days (5 customers) | 82 customers, hitting 1 of today's 6 chosen SMS | new |
| B-05 | The same offer dismissed or ignored ≥ 2 times → do not send it again for 60 days | 2, 60 days | MG-100051 × P-EN-02 is real, but both dismissals were on 24.07 and 25.07, so the block **ended 23.09**, before the snapshot | 7 customer × offer pairs blocked at 30.09 (141 pairs over all history) | new; see R3 |
| B-06 | No sales for X days after a ticket is resolved | X=14 | `service_interactions.resolved_at` | 41 customers, 24 with a marketing decision today | new |
| B-07 | Never offer what the customer already owns | on | contracts, `hems_devices`, `shop_orders` delivered | already applied | done in KG (holding preconditions; generic offers drop owned products, D1) |
| B-08 | Minimum ΔCLV per channel | call ≥ €10 | A call costs €6 (`value_assumptions`) | **9 of 12** chosen calls are below €10 (lowest €1.03). MG-100112's generic StromAktiv call is €14.87, so K11 stands | new |
| B-09 | Channel capacity | call: 50 per week | set by marketing | 12 calls chosen, so no effect on the snapshot | new |

**Rule record:**

```text
{ rule_id, name, tier (compliance|business), active,
  scope (all|channel|offer|business_line|segment),
  condition {source_table, field, operator, value, window_days},
  effect, params, valid_from, valid_to, version, created_by, reason_template }
```

Effects: `BLOCK_CHANNEL`, `BLOCK_OFFER`, `BLOCK_ALL_SALES`, `BLOCK_ALL_CONTACT`, `DEFER_UNTIL(date)`, `DOWNGRADE_TO_NON_PERSONALISED`, `REQUIRE_APPROVAL`, `CANCEL_PENDING`.

`reason_template` is the sentence shown on the card, for example `"Email blocked: {count}/{N} emails in {W} days (B-01)"`.

## 4. Shared contact counter (every frequency rule uses it)

The spec merges these sources and removes duplicates by customer + channel + timestamp:

| Source | Counted as | Timestamp |
|---|---|---|
| `nba_action_history`, delivered, not control group | its channel | `decided_at` (there is no `sent_at` column) |
| `newsletter_performance`, `delivered = True`, joined to `newsletter_campaigns` | email | `newsletter_campaigns.sent_at` |
| `service_nba_feedback`, `offer_mentioned_to_customer = True` | phone | `shown_at` |
| the engine's own decision log, approved and sent | its channel | send time |

Facts to respect:
- **The history has no 1:1 `email` rows.** Every "email" in it is `newsletter_email` (1,397 rows).
- **Window is `(t − W days, t]` on exact timestamps**, where t is the decision time (the snapshot, or the event time during replay). If the window starts at midnight of the first day instead, B-01 jumps from 328 to 449 customers, because campaign NL-2609 (02.07 09:00) falls just inside.
- Newsletters go out every 21 days, so with W=30 almost every subscriber always has 1–2 newsletters in the window (see R1).
- **Owner: Agent KG.** It provides one counter, `nba/kg/contacts.py`, that both the old contact cap and the new rules use, with a `sources` parameter per rule. Agent NBA must not build a second counter.

## 5. Evaluation order

| Step | Spec | Where |
|---|---|---|
| 1 | Tier 1 first, then tier 2. The strictest rule wins; tier 2 never overrides tier 1 | KG gates (`generate_candidates`) → NBA rule engine |
| 2 | Evaluate per offer × channel, not per customer | NBA. Tuples already exist |
| 3 | If the best channel is blocked, try the next allowed channel with its own ΔCLV (contact cost differs) | Already how ranking works: each channel is its own tuple |
| 4 | Blocked only for now (frequency or cooldown) → `DEFER_UNTIL` the earliest valid date | NBA, new. Proposal: choose the best tuple that is allowed **now**. If none is, choose the best deferred tuple with ΔCLV > 0, with status `deferred` and `send_at = defer_until` |
| 5 | Everything blocked or ΔCLV ≤ 0 → NO_ACTION with the list of reasons | Exists |
| 6 | Capacity (B-09) last, across all customers: sort by ΔCLV, and above capacity switch channel or wait | NBA, new (a global pass after per-customer ranking) |

## 6. What NBA builds

| Piece | Details |
|---|---|
| Rule store | `config/rules.yaml`: tier 2 records as in §3, plus the read-only tier 1 list from KG. `rule_set_version` = a version number plus a content hash |
| Engine | Evaluates tier 2 on each tuple after the KG gates, applies the effects, DEFER and capacity, and writes the measured values (e.g. `email_count_90d = 6`) |
| Contract | New card fields: per-rule checks (✓/✗, `rule_id`, reason text), blocked tuples with the rule, `deferred` status with a date, and a contact counter line: `Email 3/5 (90 d) · Total 1/2 (30 d) · Call 0/1 (90 d)`. Update README §5.4 in the same PR |
| Decision log | Each decision stores `rule_set_version`. C-04 cancels entries that were approved but not sent |
| API | `GET /api/rules`; `PUT /api/rules/{id}` (tier 2 only; loosening tier 1 is refused); `POST /api/rules/whatif`; `GET /api/rules/versions` (who changed what, when); `GET /api/rules/audit` |
| What-if | Before saving: customers affected, actions blocked by channel and offer, change in total ΔCLV, 10 example customers. Decide every customer twice, the way `scripts/policy_diff.py` does |
| Legacy audit | Run every rule over `nba_action_history`. Numbers in §8 |
| Log | Per customer and run: rules evaluated, result (pass / block / defer), measured value, `rule_set_version`, final action |
| Docs and static export | `docs/api.md` + `docs/openapi.json`; rules, counters and audit in the static export for Vercel |

## 7. Card display (data from NBA; Agent CARDS renders it later)

- A checklist row per relevant rule: ✓/✗, `rule_id`, and the `reason_template` sentence.
- A "Blocked" section listing each blocked offer × channel and the rule that blocks it.
- A "Deferred until {date}" status when the action is deferred.
- The contact counter line from §6.

## 8. Legacy audit and test cases, checked

**Legacy audit** over 2,022 delivered, non-control sends:

| Check | Sends |
|---|---|
| C-01: channel consent not granted **at send time** | **829**, the spec's "~830" (861 using the latest consent status, minus 32 consents withdrawn only after the send) |
| `app_push` to customers without the app | **114**, as in the spec |
| `portal_popup` to customers without a portal account | 44 |
| All tier 1 rules | 1,025 |
| All rules with the spec defaults | 1,674 |

`consent_status` holds only the latest status, so the audit is an approximation. Say so on the page.

**Test cases:**

| Customer | Spec expects | Data | Today |
|---|---|---|---|
| MG-100267 | ≥ 5 emails → email blocked (B-01), try another channel | 9 emails in 90 days (5 NBA newsletters + 4 campaigns) | Today: `P-MO-01 · portal_popup`. If B-02 counts newsletters (R1), it is deferred: 3 contacts in 30 days |
| MG-100026 | Same | 8 emails. Only `newsletter_email` is allowed (email withdrawn, the rest not given), so there is no other channel | NO_ACTION already (3 NBA contacts in 30 days) |
| MG-100023 | Newsletter yes, 1:1 email no | `newsletter_email` granted, `marketing_email` withdrawn | Today: `P-AS-01 · portal_popup`. Deferred if R1 = count newsletters |
| MG-100112 | Phone only, no profiling → non-personalised; call €6 → check B-08 | Generic StromAktiv call, ΔCLV €14.87 | Passes B-08 |
| MG-100067 | Newsletter unsubscribe/withdrawn late 09/2026 → blocked at once (C-03/C-04) | Withdrawn 26.09, unsubscribed via NL-2613 | NO_ACTION; newsletter blocked |
| MG-100102 | Same | Withdrawn 25.09, unsubscribed via NL-2613 | Newsletter blocked; `P-MO-01 · app_push` |
| MG-100001 | Portal/app consent but no app → no app_push, only portal_popup | `app_installed = False` | `P-MO-01 · portal_popup` |
| MG-100051 | P-EN-02 dismissed twice → blocked 60 days (B-05) | Dismissed 24.07 and 25.07, block until 23.09 | **Already expired at 30.09** (R3) |
| MG-100096 | Dunning ≥ 2 → service only (C-06) | Dunning level 3 | `P-SV-01` service |
| MG-100186 | Open complaint → service only (C-07) | TK-200745, open since 20.09 | `P-SV-01` service |
| B-01 5 → 3 | What-if shows more customers with email blocked | 328 → 492 customers; today's email decisions hit: 68 → 99 | — |

## 9. Open decisions

| # | Question | Options | Recommendation |
|---|---|---|---|
| R1 | Do newsletters count toward **B-02** (all channels, 2 in 30 days)? The spec's counter says yes for every frequency rule | (a) Yes, as in the spec: 336 of 549 marketing decisions deferred, including the test customers MG-100023, MG-100001, MG-100267, MG-100102, MG-100051. (b) Newsletters count only in B-01 | (b). A newsletter is a broadcast every 21 days, so with (a) a subscriber is almost never free for a 1:1 action. Either way, give each rule a `sources` setting so marketing can switch it |
| R2 | C-07: keep the stricter "any open ticket", or only complaints? | Tier 1 may be tightened, so stricter is allowed. All 29 open tickets in the snapshot are complaints, so the results are identical today | Keep stricter and label it C-07 (tightened) |
| R3 | B-05 test MG-100051 | (a) Test at eval_time 2026-09-01 (blocked until 23.09). (b) Expect "B-05 ended 23.09" at the snapshot | (a) for the test, plus (b) on the card |
| R4 | Who builds the Rule Center page? | `web/` belongs to Agent CARDS, which is being edited | NBA ships the API, docs and static data first. The page comes when CARDS is free, or when the team reassigns it |
| R5 | B-08 drops 9 of 12 chosen calls | Keep €10, or lower it | Keep €10 as in the spec. The what-if shows which customers change |
