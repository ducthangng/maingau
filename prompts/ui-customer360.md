# UI brief: Customer 360° dashboard and the dashboard switch (demo)

For whoever builds the UI in `web/` (team member or AI coding agent). Checked against `main` at UI v0.2 (639115e) on 27 Oct 2026.

## 0. Goal

The challenge asks for two dashboards (slides p.10–11):
- **Orchestration dashboard** for marketing: top NBAs across customers and segments; set offers, priorities and contact limits; approve content, channels and tone.
- **Customer 360° dashboard** for customer service: current status (products, contracts, open cases), CLV at a glance, the most favourable NBAs ranked with a reason.

For the demo, add **one switch** between the two. The Customer 360° view is for a service agent on a call: type a `customer_id` and, within about 30 seconds, know who the customer is, what has happened, and what to suggest. It shows plain information only: no marketing labels, warnings or priority scores.

## 1. What exists today (UI v0.2)

- **Routes:** `/` (worklist), `/customer/:id` (profile card + NBA card), `/groups` (bulk approval). Layout nav: Worklist, Groups.
- **`/customer/:id` already has a `marketing | service` toggle** (`pages/Customer.tsx` → `NbaCard mode`). That is a mode of the marketer's page, not the Customer 360° dashboard. Keep it; the new switch is one level higher.
- **Data:** `lib/data.ts` tries the API (`uvicorn api.app:app`, Vite proxy `/api`) and falls back to the static JSON in `web/public/data` (real export: 750 customers, `index.json`, `summary.json`, `rules.json`). Use `loadCard(id)`; the shape is `CustomerCard` (`types/contracts.ts`, `docs/schema/customer_card.schema.json`).
- **Names:** the data has no names. `lib/customerMock.ts` makes a readable mock name per customer; label it as a demo name.
- **Reusable pieces (import only, never edit):**
  - `lib/format.ts` (`eur`, `signedEur`, `pct`, `CHANNEL_LABEL`) and `components/nba/ui.tsx` (`channelLabel`, `toneLabel`);
  - `lib/data.ts` (`loadCard`) and `lib/customerMock.ts`.

  Components that carry marketing labels (`ProfileCard`, `NbaCard`, `Lists`, `Timeline`, `Products`, `Consent`) get new, plain counterparts in `components/service/`.

**Do not change the Orchestration dashboard.** Its pages (`Worklist`, `Customer`, `Groups`), their components, and its existing behaviour, including the `marketing | service` toggle on `/customer/:id`, stay exactly as they are. Customer 360° lives in new files only:
- `pages/Service.tsx`;
- `components/service/*`;
- `lib/serviceFeedback.ts`.

The only edits to existing files are:
- the two new routes in `App.tsx`;
- the switch in `components/Layout.tsx`, added beside the existing nav without changing it.

## 2. The switch

- A segmented control in the `Layout` header: **Orchestration** | **Customer 360°**.
- **Orchestration** keeps today's nav and pages untouched.
- **Customer 360°** shows a search box (customer ID, Enter opens it) and the page `/service/:id`. Add the routes `/service` and `/service/:id` in `App.tsx`.
- Remember the choice in `localStorage` (`maingau.view.v1`), wrapped in try/catch; the URL wins when the user opens a link directly.
- The two views share the data and the engine; nothing is computed twice.

## 3. Customer 360° page (`/service/:id`)

### 3.1 Fixed strip (always visible, above the tabs)

| Item | Source in the card | Notes |
|---|---|---|
| Name and customer ID | mock name from `customerMock.ts`, `customer_id` | Mark the name "demo" |
| **CLV now** (bold, large) | `profile.value_risk.clv_eur.v` | `eur()` |
| What moves the CLV | `profile.value_risk.churn_drivers[].label`, joined with " · " | e.g. "price guarantee ends <90d · 3 tickets in 12m". Show labels only, no numbers |
| Open tickets | count of `timeline[]` with `kind == "service"` and `"open"` in `flags` | Number only |
| How to address | `profile.header.tone.value` → "Du" / "Sie" | |
| NBA no. 1 + one-line reason | `chosen.tuple_id` → the matching `candidates[]` entry: `offer_name`, channel, and `why[0]` as the reason | If `chosen.tuple_id == "NO_ACTION"`: "No offer right now" plus the first plain reason from §3.4. If `chosen.deferred_until` is set: "from {date}" |

### 3.2 Tab 1: Profile

**Customer details:**
- customer since: `profile.header.tenure_years`, shown as "since YYYY";
- city;
- household size;
- portal account and app: `profile.header.digital.portal_account` / `.app_installed`;
- language;
- customer type: not in the card; every mock customer is B2C, so leave it out or show "Private".

**Products and contracts:** one collapsible row per line (`<details>`, closed by default), from `profile.products.<line>.items` (each value is a Fact, so show `.v`):

| Row | Line | Fields to show when opened |
|---|---|---|
| Energy | `energy` | commodity, tariff, status, start date, price guarantee until (+ days left), meter type, annual consumption |
| Mobile | `mobile` | plan, data volume, monthly fee, SIMs, minimum term end |
| Autostrom | `autostrom` | car, battery, charge cards, start date, kWh per month |
| HEMS | `smart_living` | devices and their status |
| Shop orders | `shop` | product, status, date |

**Never show `payment_method` or any dunning field.** Payment data is only used to block offers (rule C-09).

**Open tickets:** `timeline[]` items of kind `service` with flag `open`: category (from the title), created date, channel and status (from `detail`). Facts only, no warning styling.

**Consent:**
- per channel, whether the customer allows contact: `profile.channels[]` (`channel`, `allowed`);
- profiling consent: `profile.consent[]` where `type == "profiling_analytics"`, using `effective_status`. Show it as "Personalised offers: yes / no".

**Do not show here:**
- urgency tier or score (`TierChip`), "act now", archetype or segment name;
- flags (`service_critical`, `contact_fatigue`, …), highlights, the contact-fatigue panel;
- `data_quality` warnings ("snapshot inconsistency").

### 3.3 Tab 2: Customer journey

A timeline, newest first, with a filter chip per event type. Each event says what happened and how the customer reacted, as recorded. **No CLV and no "CLV up/down" marks on events.**

| Event | Available in `card.timeline` today | Missing (needs the backend, §5) |
|---|---|---|
| Past engine proposals (`kind: marketing`) | offer and channel (`title`); response and "converted" (`detail`) | tone of address |
| Service tickets (`kind: service`) | category, channel, status, CSAT | resolution code |
| Shop orders (`kind: order`) | product, status | order value |
| Contracts and milestones, consent changes | yes | — |
| Newsletters | not in the timeline (only totals in `profile.trends.newsletter`) | subject, delivered or bounced, opened, click target, bought within 7 days, unsubscribed |
| Suggestions by other service agents | no | suggested offer, customer reaction |
| Charging sessions | no (only totals in `profile.trends.charging`) | per day: completed / failed count |
| Portal visits | no (only totals in `profile.trends.portal`) | pages viewed, duration, offer banner shown |

Until the backend adds the missing events, show what exists and hide the empty filter chips. The portal data never names the pages, so the timeline cannot say what the customer did on the portal; write that as a one-line note on portal events.

### 3.4 Tab 3: Next best actions

**List:** every action in `candidates[]`, sorted by `valuation.delta_clv`, highest first. Each row shows:
- the offer (`offer_name`), channel (`channelLabel`) and tone (`toneLabel`);
- ΔCLV (`signedEur`) and the chance the customer agrees (`pct(valuation.p_accept)`);
- the reason in one sentence: `why[0]`;
- for a row with `deferred_until`: "possible from {date}".

**Ordering and source:**
- When the customer has an open ticket, put service actions (`action_type == "service"`) first.
- The API returns every evaluated channel; the static export keeps the best channel per offer. Either is fine for the demo.
- This is the same engine as the marketer's page; do not re-rank in the UI beyond the service-first rule.

**"Not recommended":** the actions in `blocked[]`, one line per offer (or per channel for channel rows), in plain words. Map `rule_center_id` first, then `rule_id`:

| Rule | Plain text |
|---|---|
| `C-07` / `EXCL-OPEN-TICKET` | No sales offers while a ticket is open |
| `C-06` / `EXCL-DUNNING` | No sales offers right now (account status). Do not mention payment |
| `C-08` / `EXCL-CANCELLATION`, `EXCL-AUTOSTROM-CANCELLED` | No sales offers: a cancellation is in progress |
| `C-01` / `CONSENT-CHANNEL` | The customer has not agreed to be contacted by {channel} |
| `C-02` | Newsletter: double opt-in not confirmed |
| `C-03` | The customer unsubscribed from the newsletter |
| `CHANNEL-AVAILABLE` | No app / no portal account |
| `C-05` / `CONSENT-PROFILING` | No personalised offers (no consent for personalisation) |
| `B-07` / `HOLDING-PRECONDITION` | Already has it, or a needed product is missing (use `reason`) |
| `B-02` / `CONTACT-CAP`, `B-01`, `B-03`, `B-04` | Contact limit reached, possible from {until} |
| `MEMORY` | The customer said no to this before (use `reason`) |
| `ECON-NONPOSITIVE` | Not worth offering now |
| `DATA-MISSING` | Not enough data |

**Record the customer's reaction:** instead of "approve", each action row has three buttons: **Mentioned** · **Interested** · **Declined**. Declined opens an optional reason: already has it / upset / no time / not relevant. Save one row in the shape of the workbook table `service_nba_feedback`:

| Field | Value |
|---|---|
| `feedback_id` | `SF-<timestamp>` |
| `ticket_id` | the open ticket's ID if there is one, else null |
| `customer_id`, `shown_at` (now), `channel` | `phone` (or `chat`, a small select) |
| `suggestion_source` | `nba_engine` |
| `suggested_offer_id` | the row's `offer_id` |
| `agent_id` | the reviewer name from `lib/decisions.ts` |
| `agent_action` | `accepted` for Mentioned / Interested; `dismissed` for Declined |
| `dismiss_reason` | `customer_already_has_product` \| `customer_upset` \| `no_time` \| `not_relevant` \| null |
| `offer_mentioned_to_customer` | true |
| `customer_reaction` | `interested` \| `declined` \| null for Mentioned; `annoyed` when the reason is "upset" |
| `converted_within_14d` | null |

**Where the rows go:**
- **Static demo:** store them in `localStorage` (`maingau.serviceFeedback.v1`, try/catch), following the pattern in `lib/decisions.ts`, and list them under the buttons.
- **API:** POST them once the endpoint exists (§5).

These rows feed the feedback loop (`nba.ai.feedback`): a decline pauses that offer for the customer for 90 days; an upset customer gets no sales for 30 days. Nothing is sent to the customer.

### 3.5 Style

- English UI, same look as the rest of the app.
- Calm and factual: no red or amber badges for state.
- Large, bold CLV in the strip.
- The 30-second test: the strip alone answers "who, what happened, what to suggest".

## 4. Acceptance (demo customers)

| Customer | What the agent must see |
|---|---|
| MG-100186 | Open complaint in the strip and Profile; service action first; sales offers under "Not recommended" with "No sales offers while a ticket is open" |
| MG-100096 | Service only; "No sales offers right now (account status)", with no word about payment |
| MG-100023 | NBA no. 1: MAINGAU Autostrom by portal pop-up, reason "bought a Wallbox … no Autostrom contract"; newsletter "possible from" a later date |
| MG-100112 | No personalised offers; StromAktiv by phone; tone Sie |
| MG-100026 | Strip says the NBA is possible from a later date |
| Any customer | No urgency tier, flags, segment name or payment field anywhere in Customer 360° |

The switch keeps both dashboards working with the API running and with `VITE_STATIC=1`.

## 5. Backend needed (not in `web/`; ask Agent KG / Agent NBA)

1. **Journey events in `card.timeline`:**
   - newsletter deliveries (subject, delivered/bounced, opened, click target, bought within 7 days, unsubscribed);
   - agent suggestions (`service_nba_feedback`);
   - charging per day (completed / failed);
   - portal visits (pages, duration, banner);
   - plus tone on past proposals, order value and ticket resolution code.
2. **`POST /api/customers/{id}/service-feedback`:** append the row above to `out/service_feedback.jsonl`, which `nba.ai.feedback` reads next to the workbook table.

## 6. Git

- Work on your own branch and folder (README §13).
- Stage only the new Customer 360° files plus the small edits to `App.tsx` and `Layout.tsx`.
- `git diff` must show no change to the Orchestration pages or components.
- Run `npm run build` before pushing.
