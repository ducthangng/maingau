# Rule Center: rules that block or limit actions

**Status: built (26 Oct 2026).** The engine, the API, the rule versions, the what-if, the legacy audit and the rule log are in `main`. Source: the rule spec agreed with the mentor. This file translates it, records how it was built, and gives the numbers from the engine on `maingau_nba_mockdata.xlsx` (evaluation time 2026-09-30 23:59:59, rate mode).

**Owners:**
- **Agent KG:** tier 1 (C-01…C-09), B-02 (contact cap), B-07 (holdings) and the shared contact counter `nba/kg/contacts.py`.
- **Agent NBA:** tier 2 (B-01, B-03…B-06, B-08, B-09), custom rules, DEFER_UNTIL, capacity, rule versions, what-if, audit, rule log, API.
- **Rule Center page:** a temporary UI branch, `feat/rule-card`, not Agent CARDS' folder.

The defaults for the open decisions R1–R5 are in §9; each one can be switched with one setting.

## 1. Purpose

Marketing sets rules that block or limit actions. Every rule is evaluated **before ranking**, on each offer × channel tuple, and changes each customer's NBA directly.

## 2. Tier 1: compliance rules (always on, can only be tightened)

Defined in `kg/policy.yaml → compliance`, enforced by the KG gates. Every blocked row carries `rule_center_id` (C-xx).

| ID | Rule | Effect | KG check | Customers blocked today |
|---|---|---|---|---|
| C-01 | A channel needs its consent `granted`; portal needs a portal account, app push the app | BLOCK_CHANNEL | `CONSENT-CHANNEL`, `CHANNEL-AVAILABLE` | most customers lack at least one channel |
| C-02 | Newsletter needs double opt-in | BLOCK_CHANNEL | `CONSENT-CHANNEL` | |
| C-03 | Unsubscribe withdraws the newsletter at once | BLOCK_CHANNEL | `CONSENT-CHANNEL` (`newsletter_performance.unsubscribed`) | e.g. MG-100067, MG-100102 |
| C-04 | Withdrawn consent cancels actions approved but not sent | CANCEL_PENDING | `nba.kg.events` replay revokes pending cards | 29 revocations on the event stream |
| C-05 | No profiling consent: no personalisation | DOWNGRADE_TO_NON_PERSONALISED | `CONSENT-PROFILING` (D1 generic path) | |
| C-06 | Dunning ≥ 1: service only | BLOCK_ALL_SALES | `EXCL-DUNNING` | MG-100096 |
| C-07 | Open complaint: no sales. **Tightened:** any open ticket (R2) | BLOCK_ALL_SALES | `EXCL-OPEN-TICKET` | MG-100186 |
| C-08 | Cancellation in progress: no sales | BLOCK_ALL_SALES | `EXCL-CANCELLATION`, `EXCL-AUTOSTROM-CANCELLED` | |
| C-09 | Payment data only to exclude | — | design rule (README §6.2) | |

The API refuses to switch off or loosen a C-xx rule (403). Tightening means adding a **hard rule** (§6).

## 3. Tier 2: business rules

Defined in `config/nba.yaml → business_rules`; B-02 is `config/kg.yaml → contact_cap`. Service actions are exempt from every tier 2 rule.

"Customers" below is how many of the 750 have the rule blocking or holding back at least one tuple today. A counter at its limit counts only when the rule held a tuple: otherwise the rule report says `pass`, "limit reached; nothing held" (e.g. 328 customers are at the B-01 limit, 285 have an e-mail tuple held).

| ID | Rule (default) | Effect | Customers | Spec's claim, checked |
|---|---|---|---|---|
| B-01 | Max 5 e-mails in 90 days; newsletters count | DEFER_UNTIL | 285 | **Confirmed:** 673 customers e-mailed, median 4, 328 at ≥ 5 |
| B-02 | Max 2 contacts in 30 days, all channels | DEFER_UNTIL | 80 | "p90 = 4" **not reproduced** (3 with every source). "4% → 1.2% above 4 actions" holds **per customer over Jun–Sep** (3.8–4.1% vs 1.2%), not per 30 days |
| B-03 | Max 1 call in 90 days (a service agent's offer mention counts as a call) | DEFER_UNTIL | 2 | **Confirmed:** max 2 in 90 days in the history |
| B-04 | Max 1 SMS in 90 days | DEFER_UNTIL | 8 | **Confirmed** |
| B-05 | Same offer dismissed or ignored ≥ 2 times: pause it 60 days after the last one | DEFER_UNTIL | 22 | MG-100051 × P-EN-02: dismissed 24.07 and 25.07, paused until 23.09, so **already over** at the snapshot (R3) |
| B-06 | No sales for 14 days after a ticket is resolved | DEFER_UNTIL | 33 | |
| B-07 | Never offer what they own | BLOCK_OFFER (KG gate) | 552 | |
| B-08 | A call only if ΔCLV ≥ €10 (a call costs €6) | BLOCK_CHANNEL | 99 | MG-100112's StromAktiv call is €14.87, so K11 stands in rate mode. Under uplift it is €2.54 and is blocked |
| B-09 | Max 50 calls per week | DEFER_UNTIL (switch channel or wait) | 0 | 3 calls are chosen today (2 now, 1 waiting) |

**Decisions today: before → after the Rule Center**

| Outcome | Before | After |
|---|---|---|
| Act now | 596 | **518** (ΔCLV €8,898) |
| Waiting | — | **146** (ΔCLV €1,666) |
| No action | 154 | **86** |

Among the 146 waiting customers, a tuple is held by B-01 in 103 cases, B-02 in 79, B-06 in 32, B-05 in 11, B-04 in 3 and B-03 in 1 (a customer can hit several). The most common dates are 21.10 (24) and 11.11 (13).

A price-guarantee offer (P-EN-02) never waits until the day its guarantee ends or later: that hold becomes a block naming the rule ("Price guarantee ends … before contact is allowed …") and the next action wins (6 decisions change today, e.g. MG-100140 and MG-100271).

## 4. Shared contact counter (`nba/kg/contacts.py`)

All frequency rules use one counter. It merges these sources and removes duplicates by channel + timestamp:

| Source | Counted as | Timestamp |
|---|---|---|
| `nba_history`: `nba_action_history`, delivered, not control | its channel | `decided_at` |
| `newsletter`: `newsletter_performance`, delivered | `newsletter_email` | `newsletter_campaigns.sent_at`, copied onto each row as `campaign_sent_at` |
| `service_feedback`: `service_nba_feedback` with `offer_mentioned_to_customer` (stored as text `'True'`) | `outbound_call` | `shown_at` |
| decision log | its channel | passed in by the caller as `extra` |

- The window is `(t − W days, t]` on exact timestamps. Counting from midnight of the first day would move the customers at the B-01 limit from 328 to 449.
- Each rule chooses its sources: B-01 uses history + newsletter; B-02 history + service feedback (R1); B-03 history + service feedback; B-04 history only.

## 5. Evaluation order (as built)

| Step | What happens | Code |
|---|---|---|
| 1 | Tier 1 and B-07 drop tuples. A capped customer keeps their tuples, marked with a failed CONTACT-CAP check | `kg_bundle(apply_cap=False)` |
| 2 | Every tuple is valued | `value_candidate` |
| 3 | Tier 2 per tuple: **block** (B-08, custom) drops it; **hold** (B-01…B-06, B-09, B-02) gives it `deferred_until` = the latest of its earliest allowed times; a P-EN-02 tuple held until the day its price guarantee ends, or later, is blocked by the holding rule instead. Tuples with ΔCLV ≤ 0 are left to the economics row | `nba/engine/rulecenter.py` |
| 4 | The best tuple allowed **now** wins, so a blocked channel falls back to the next one with its own contact cost. If none is allowed now, the best held-back tuple is chosen: `chosen.deferred_until` is set, `send_at` comes after it, and the reason starts "Held back until …". Signal tuples come before generic ones (K12) | `evaluate_candidates` |
| 5 | Nothing allowed or waiting with ΔCLV > 0: NO_ACTION with the list of reasons | `assemble` |
| 6 | B-09 runs last, across all customers. Per channel and ISO week, the highest ΔCLV keeps its slot; the overflow is re-decided with that channel held until next Monday (switch channel or wait) | `Runtime.capacity_overflow` |

A waiting action fails the checklist item `contact_cap`, so bulk approval leaves it out. The API refuses to approve it (409) until its time.

## 6. What was built

| Piece | Where |
|---|---|
| Business rules, custom rules, `rule_set_version` | `config/nba.yaml` (`business_rules`, `custom_rules`, `rule_set_version`) |
| Engine, rule report, capacity | `nba/engine/rulecenter.py` |
| Rule tree, Field / Operator catalog, edit operations | `nba/engine/rule_registry.py` |
| What-if | `nba/engine/rule_whatif.py` |
| Legacy audit | `nba/engine/rule_audit.py` |
| Card fields | `CustomerCard.rules`: per-rule result, counters, `counter_line`, e.g. `Email 9/5 (90 d) · Total 1/2 (30 d) · Call 1/1 (90 d) · SMS 0/1 (90 d)`. Also `chosen.deferred_until`, `candidate.deferred_until`, `IndexRow.deferred_until`, `Blocked.rule_center_id` / `until`, `meta.versions.rules` |
| API | `GET /api/rules`, `PUT /api/rules/{id}`, `POST /api/rules`, `DELETE /api/rules/{id}`, `POST /api/rules/whatif`, `GET /api/rules/versions`, `GET /api/rules/audit` (`docs/api.md` §3.6) |
| Versions | `out/rule_versions.jsonl`, append-only: version, time, by, reason, operation, `rule_set_version`. Replayed at API start. A decision stores `versions.rules`, so approvals made under older rules stop applying |
| Rule log | `out/rule_log.jsonl` from `nba.build`: per customer, every rule's result, measured values, `rule_set_version`, final action, `deferred_until` |
| Static page data | `rules.json` (`RulesFile`, `docs/schema/rules.schema.json`, about 41 KB): the rule tree and the Field / Operator catalog built from today's workbook columns (14 entities) |
| Marketer rulebook | `python -m nba.rules` (`rules.yaml`): new section "Pauses and limits per channel" for B-xx; "newsletters count" on the contact limit is a 🔒 hard rule |

**Custom rules** (the "Add rule" popup):
- Each row is **Field** (an entity: Customer, Consent, Energy contract, …, Offer) + **Operator** (a condition built from that entity's columns) + **Set rule** (hard / customized) + **Value** (active / inactive).
- A sub-rule **narrows** its parent: every condition must hold. Conditions on Offer select which offers are hit.
- The default effect blocks the matching offers, or all sales of matching customers.
- A sub-rule added under a built-in rule is its own rule, shown under that rule.

## 7. Card display (data ready; the UI renders it)

- **Checklist:** `card.rules.results` gives every rule's ✓/✗ with `rule_id` and the `reason_template` sentence.
- **"Blocked" section:** blocked rows with `rule_center_id`; held-back rows also carry `until`.
- **"Waiting until {date}":** taken from `chosen.deferred_until`.
- **Contact counter:** `card.rules.counter_line`.
- **Static export:** the card keeps only tier 2 outcomes and drops the counters list. The whole static export stays under 30 MB.

## 8. Legacy audit and test cases (engine output)

**Legacy audit** (`GET /api/rules/audit`), over 2,022 delivered, non-control sends:
- **1,496** would be stopped today, **1,059** of them by compliance.
- Per rule:

| Rule | Sends |
|---|---|
| C-01: no consent at send time | **829** (the spec's "~830") |
| C-01: no app / portal | 158, of which **114** are app pushes without the app (as in the spec) |
| C-02 | 86 |
| C-03 | 70 |
| C-06 | 81 |
| C-07 | 3 |
| C-08 | 24 |
| B-01 | 458 |
| B-02 | 217 |
| B-03 | 7 |
| B-04 | 5 |
| B-05 | 6 |
| B-06 | 73 |

- `consent_status` holds only the latest status: a consent withdrawn after the send counts as granted then.
- B-07, B-08 and B-09 are not audited.

**Test cases** (`tests/test_engine_rules.py`):

| Customer | Spec expects | Engine |
|---|---|---|
| MG-100267 | E-mail blocked (B-01), other channel tried | 9 e-mails in 90 days, B-01 holds e-mail; P-MO-01 · portal pop-up now |
| MG-100026 | Same | Only the newsletter is allowed and it is over the limit: **waiting until 02.12** (P-SL-01 newsletter) |
| MG-100023 | Newsletter yes, 1:1 e-mail no | P-AS-01 · portal pop-up |
| MG-100112 | Non-personalised call; check B-08 | P-EN-01 · call, ΔCLV €14.87 ≥ €10; P-MO-01 and P-SL-01 calls blocked by B-08 |
| MG-100067, MG-100102 | Newsletter blocked at once (C-03/C-04) | C-03 blocks the newsletter |
| MG-100001 | No app push, only portal pop-up | Portal pop-up; app push blocked (C-01). The offer is P-SL-01 since the look-alike learning |
| MG-100051 | P-EN-02 paused 60 days (B-05) | At 01.09: paused until 23.09. At the snapshot: over (R3) |
| MG-100096 | Service only (C-06) | P-SV-01 |
| MG-100186 | Service only (C-07) | P-SV-01 |
| B-01 5 → 3 | What-if shows more e-mail blocks | **285 → 410 customers**, 82 decisions change, ΔCLV now €8,898 → €8,617 |

## 9. Decisions (defaults applied; one setting switches each)

| # | Question | Default applied | Switch | Effect of the other option |
|---|---|---|---|---|
| R1 | Do newsletters count toward B-02? | No: only toward B-01 | `config/kg.yaml contact_cap.sources` + `newsletter`, or "newsletters count: yes" in `rules.yaml` (hard, sign-off) | 332 decisions change; act now 518 → 240, waiting 146 → 424, ΔCLV now €8,898 → €5,562 |
| R2 | C-07 scope | Stricter: any open ticket (allowed in tier 1; same result today) | `kg/policy.yaml` exclusion predicate | none today |
| R3 | MG-100051 B-05 test | Tested at 01.09 (paused until 23.09); the snapshot shows it over | — | — |
| R4 | Who builds the page | API + `rules.json` first; the Rule Center card is on the temporary branch `feat/rule-card` | — | — |
| R5 | B-08 €10 drops low-value calls | Keep €10 | `business_rules.B-08.min_eur` | MG-100112 under uplift would get the call back below €10 |
