# Prompt for Agent CARDS: MAINGAU NBA orchestration dashboard

Paste everything below the line into the AI that builds the UI. It is self-contained, so it also works for tools without repo access (e.g. v0). With repo access, also read `README.md` §0–§6, §7.2, §9 and §12, and `log/agent-cards.md`.

---

You are **Agent CARDS** on a 5-person hackathon team (Futury Build Days, 26–27 Oct 2026) building a **Next Best Action (NBA) engine for MAINGAU Energie**, a German energy, mobile and e-mobility provider. Three agents work in parallel:
- **Agent KG** (Claude) builds the knowledge graph, signals, rules and triage, and reviews your work.
- **Agent NBA** builds the valuation (ΔCLV), ranking and German content.
- **You** build the marketer-facing dashboard.

Repo: `https://github.com/ducthangng/maingau`. Work in the folder `/Users/linhngo/Downloads/Work/Hackathon/MAINGAU` on branch `feat/cards`, and write only in `web/`, `nba/profile/`, `config/cards.yaml`, `tests/test_profile_*.py` and `log/agent-cards.md`. **Follow the git rules in §8 below.**

## 1. What to build

A comprehensive **orchestration dashboard** for MAINGAU marketers. It must be clean, calm and Apple-style easy to use, fast, with seamless transitions, and executable by non-experts.

Marketers want to:
1. solve the customer's problem;
2. upsell in a way that adds value for the customer and for MAINGAU;
3. see strong, honest reasoning for every recommendation.

### 1.1 Worklist (home screen)

- A Notion-like table of all 750 customers. Ranking:
  1. urgency tier, P1 first;
  2. `urgency_score` descending.
- **Columns:**
  - urgency tier chip;
  - customer ID;
  - archetype;
  - top reason, the first urgency reason in plain language;
  - recommended action (offer name + channel + Du/Sie);
  - expected ΔCLV in €;
  - success probability;
  - confidence;
  - flags as small badges;
  - CLV;
  - churn.
- **Search** by customer ID or city.
- **Filters:** archetype, tier, flag, offer, channel, confidence, service mode, personalised yes/no.
- **Saved views**, for example: "Act now (P1)", "Retention this month", "Upsell opportunities", "Outliers to review".
- **Group by recommended action** (`chosen_tuple`). This is the basis for bulk execution.
- **Outliers** (`outlier = true`: service critical, no marketing channel, negative CLV, annoyed before, prefers English) must be visually distinct: a left accent bar plus a badge. They also have their own "Review" view.
- **KPI strip at the top:**
  - customers to act on;
  - total expected ΔCLV of the current view;
  - number of outliers;
  - number blocked by rules.

### 1.2 Execute for one customer or for a group

- **One customer:** open the customer page (§1.3), then Approve, change channel / tone / offer, or Reject with a reason.
- **Group:** select rows that share the same `chosen_tuple`, or click "Approve group" on a grouped section. A **preview sheet** opens and shows:
  - the count;
  - Σ expected ΔCLV and the expected number of conversions (Σ p);
  - total contact cost;
  - who is **excluded and why**: outliers, a failing checklist item, the contact cap reached, low confidence when the user chooses to exclude it;
  - an optional **holdout control group** (default 10%, assigned deterministically by a hash of `customer_id`) so the campaign's uplift can be measured later.

  On confirm, the decisions are stored and the group can be exported as CSV/JSON for the campaign tool.
- **Never "send" anything.** Approval only produces an export or hand-off file, because a human is always in the loop.

### 1.3 Customer page

Two cards side by side; on narrow screens they stack. The user must understand the customer in about 30 seconds.

**Left card: Customer Profile.** "Who is this customer, and how are they changing?"
- **Header:**
  - customer ID;
  - age band (e.g. "50–59", never the exact age);
  - city;
  - household size;
  - tenure;
  - portal account and app;
  - preferred language;
  - Du/Sie with its evidence (e.g. "Sie – 3/3 messages use 'Sehr geehrte', latest 2026-08-14", or "Sie (default)").
- **Triage banner:** archetype with its reason, urgency tier with its reasons and deadline, flags.
- **Consent and exclusions as traffic lights at the top, never hidden:**
  - 6 consent types: newsletter_email, marketing_email, marketing_phone, marketing_sms, portal_app_personalisation, profiling_analytics. Each shows status, date and source; "effective" is set when an unsubscribe overrides the record.
  - Active exclusions: dunning, cancellation pending, open ticket, Autostrom cancelled.
- **Value and risk:**
  - CLV;
  - annual margin;
  - cost to serve;
  - business lines;
  - churn probability with driver tags;
  - "service issues are costing €X of CLV";
  - percentile vs all customers and vs the same product mix.
- **Product grid with 6 cells:** Energy, Autostrom, Mobile, Shop, Smart Living, Internet. Held products show their details. **Empty cells are lightly tinted as opportunities.** Internet shows "no ownership data".
- **2–3 highlights,** only genuinely unusual facts, each citing its column.
- **Timeline:** vertical, newest first, last 12 months plus future milestones (price guarantee end, mobile minimum term). Each row has a business-line icon and a source tag.
- **Trends as mini charts,** each stating its real date range:
  - charging kWh per month and failed sessions by reason, with the AC price cut on 2026-07-01 marked and a note that roaming data can arrive up to 72 h late;
  - portal sessions and views of `offers`, `tariff_overview` and `consumption_chart`;
  - newsletter real opens and clicks (Apple Mail privacy prefetch opens excluded);
  - tickets per quarter, latest CSAT and goodwill;
  - mobile usage vs limit as a bar;
  - HEMS (September only);
  - **no CLV trend.** Say "CLV is a single snapshot".
- **Contact history and fatigue:**
  - contacts in the last 30 and 90 days;
  - response rate;
  - offers ignored repeatedly;
  - legacy sends without a consent check;
  - agent feedback, e.g. "annoyed".
- **Signals:** chips such as "S1 Gas meter deregistered 2026-09-10 · strong". Clicking a chip highlights the NBA it drives on the right.

**Right card: Next Best Actions, ranked.** "What should we do, and why?"

Show the top action prominently, then the alternatives. **Every NBA card shows:**
- **the action:** offer name and ID, type (sales / upsell / one-off / retention / service), channel, tone, suggested send time, status (proposed / approved / overridden / rejected);
- **why it fits:** the `why` bullets in plain language, with signal references;
- **CLV impact:**
  - CLV now → CLV if it succeeds (+gain);
  - CLV if it does not succeed (unchanged, or lower when a sales contact would hit an open complaint or dunning);
  - **expected ΔCLV** = p × gain − (1 − p) × loss − contact cost, shown as a small waterfall a marketer can re-check;
- **success vs failure:**
  - a bar for p and 1 − p;
  - the evidence: sample size n, conversions, backoff level (offer × channel × tone → offer × channel → offer → catalog average), confidence (high / medium / low; low when n < 30), and uplift vs the control group;
- **notes:** caveats (assumptions, low confidence, data freshness, "nicht personalisiert");
- **checklist:** ✓/✗ with source for channel consent, profiling consent, no exclusion, not already owned, contact cap, data fresh;
- **German content preview:** subject plus 2–3 sentences in the right Du/Sie, with a "nicht personalisiert" badge when generic. No personalised prices and no false urgency;
- **reasoning path:** clickable chips `Customer → Signal → Need → Offer → Channel → Consent ✓`. Clicking a chip scrolls to and highlights the matching row in the left card (`ui_ref`);
- **buttons:** Approve, Change channel, Change tone, Change offer, Reject (reason required). A change to a blocked combination is refused with the rule shown.

Below the alternatives:
- **Blocked actions** with the rule that blocks each one, e.g. "P-MO-01 blocked: marketing_phone withdrawn 2025-03-02", "All sales blocked: dunning_level = 2", "S3 wallbox purchase ignored: no profiling consent".
- **Legacy comparison:** "The old rule engine would send R-SHOP-GENERIC (Balkonkraftwerk by newsletter): ΔCLV €−0.4 under our model".

**Service mode.** When the customer has an open ticket or the top action is P-SV-01, the right card switches to "Resolve first". It shows the agent script (apology and next step) and **no sales content**. A Marketing / Service toggle sits in the header.

### 1.4 Valuable best-practice features to include

1. **Holdout control** on bulk approval, so uplift can be measured instead of assumed.
2. **Expected value with confidence:** never show ΔCLV without the p evidence and confidence next to it.
3. **"Do no harm" guard:** customers in A4 or with service flags are never in bulk sales groups.
4. **Contact frequency cap indicator:** at most 2 marketing contacts per 30 days.
5. **Sensitivity hint:** whether the top action stays on top with p ±20%. Use the field if provided; otherwise hide it.
6. **Consent proof:** the date and source of each consent are one click away.
7. **Data freshness:** a source tooltip on every number (`table.column`, update time, refresh and latency of the source).
8. **Decision audit log** per customer: who, when, what, why.
9. **Outlier review queue.**
10. **Export:** CSV/JSON of approved actions with tuple, ΔCLV, p, reason and approver.

## 2. Tech stack

- **Vite + React + TypeScript + Tailwind CSS.** Use React Router for routes: `/` (worklist), `/customer/:id`, `/groups`.
- **Static site deployable on Vercel.** Add a `vercel.json` with an SPA rewrite. There is no backend.
- **Real data before valuation exists:** Agent KG's `python scripts/export_preview.py --out web/public/data` (run from your folder after `git merge origin/main`) writes `index.json` (750 `IndexRow`s with real triage, ranked; `chosen_offer` is `"PENDING"` and the valuation fields are null), `summary.json` (counts, `sources`, `column_src`, `value_date`) and `kg/<id>.json` (signals, candidates, blocked, consent, channels, exclusions, data_quality). Use it instead of hand-made mocks for those fields; mock only valuation, chosen and content until Agent NBA's export lands.
- **Data:** read JSON from `public/data/`:
  - `index.json` is an `IndexRow[]`;
  - `summary.json` is a `Summary`;
  - `customers/<id>.json` is a `CustomerCard`, loaded on demand.
  - Decisions go to `localStorage` (key `maingau.decisions.v1`), with export and reset buttons.
- **Libraries:** a virtualised table for 750 rows (`@tanstack/react-table` + `@tanstack/react-virtual`), Recharts for mini charts, and an icon set such as lucide-react.
- **Design:** neutral palette, one accent colour, generous whitespace, 14–15 px base text, smooth 150–200 ms transitions, keyboard navigation (↑/↓ and Enter in the worklist, Esc to close), visible focus states, accessible contrast, no horizontal scroll at 1280 px.
- **Show what the JSON says.** Do **not** re-implement valuation, ranking, rules or triage. If a field is missing, show "not enough data", never 0.

## 3. Data contract (TypeScript)

This mirrors `nba/contracts.py`. With repo access, generate the types from `docs/schema/*.json` instead (Agent KG exports them), and keep this as a reference.

```ts
type Channel = "newsletter_email" | "email" | "portal_popup" | "app_push" | "sms" | "outbound_call" | "service_agent";
type ConsentType = "newsletter_email" | "marketing_email" | "marketing_phone" | "marketing_sms" | "portal_app_personalisation" | "profiling_analytics";
type Tone = "du" | "sie";
type ActionType = "sales" | "upsell" | "retention" | "one_off" | "service";
type Confidence = "high" | "medium" | "low";
type ArchetypeId = "A1" | "A2" | "A3" | "A4" | "A5" | "A0";
type UrgencyTier = "P1" | "P2" | "P3" | "P4" | "P5";
type FlagId = "service_critical" | "no_marketing_channel" | "no_profiling" | "negative_clv" | "top_clv" | "contact_fatigue" | "annoyed_before" | "prefers_en" | "data_inconsistent";

interface Fact { v: unknown; src: string; updated_at?: string | null; row_key?: string | null }   // src = "table.column"
interface IndexRow {
  customer_id: string; age_band?: string; city?: string; lines?: number; clv_eur?: number; churn?: number;
  archetype: ArchetypeId; archetype_name?: string; urgency_tier: UrgencyTier; urgency_score: number; top_reason?: string;
  flags: FlagId[]; outlier: boolean; triggers: string[];
  chosen_offer: string; chosen_tuple?: string; channel?: string; tone?: Tone; delta_clv?: number; p_accept?: number;
  confidence?: Confidence; service_mode: boolean; personalised?: boolean;
  n_signals: number; n_candidates: number; n_blocked: number; exclusions: string[];
}
interface Summary {
  eval_time: string; n_customers: number;
  chosen_by_offer: Record<string, { count: number; sum_delta_clv: number }>;
  blocked_by_rule: Record<string, number>; no_action_by_reason: Record<string, number>; signal_counts: Record<string, number>;
  archetype_counts: Record<string, number>; urgency_counts: Record<string, number>; flag_counts: Record<string, number>;
}
interface Triage {
  archetype: { id: ArchetypeId; name: string; reason: string };
  urgency_tier: UrgencyTier; urgency_score: number; urgency_reasons: string[]; deadline?: string | null;
  flags: { id: FlagId; label: string; detail?: string | null; src?: string | null }[]; outlier: boolean;
}
interface Signal { id: string; label: string; date?: string | null; strength: "strong" | "medium" | "weak";
  purpose: "contract" | "device" | "behavioural" | "service"; src: string; evidence: string[]; needs: string[]; offers: string[]; detail?: string | null }
interface PathStep { kind: "node" | "edge"; type: string; id?: string | null; label?: string | null; ui_ref?: string | null }
interface Valuation { clv_now_shown: number; clv_now_model: number; clv_after_accept: number; clv_after_reject: number;
  p_accept: number; contact_cost: number; delta_clv: number; confidence: Confidence;
  p_source: { mode: "uplift" | "rate" | "assumption"; level: "offer_channel_tone" | "offer_channel" | "offer" | "global" | "assumption";
              n_treated: number; conv_treated: number; n_control: number; conv_control: number; baseline_control?: number | null } }
interface Candidate { tuple_id: string; offer_id: string; offer_name: string; action_type: ActionType; channel: Channel; tone: Tone;
  origin: "signal" | "service" | "generic"; personalised: boolean; need?: string | null; signals: string[];
  checks: { rule_id: string; passed: boolean; detail?: string | null; src?: string | null }[];
  valuation?: Valuation | null; rank?: number | null; why: string[]; notes: string[]; path: PathStep[] }
interface CustomerCard {
  schema_version: string; customer_id: string;
  meta: { eval_time: string; snapshot_mode: string; mode_default: "marketing" | "service"; versions: Record<string, string>; state_revision: string };
  sources: Record<string, { refresh?: string | null; latency?: string | null }>;   // keyed by table, for tooltips
  triage: Triage;
  profile: {
    header: { age_band: Fact; city: Fact; household_size: Fact; tenure_years: Fact; digital: Record<string, Fact>;
              tone: { value: Tone; method: "text" | "newsletter" | "default"; evidence: string; refs: string[] } };
    value_risk: { clv_eur: Fact; annual_margin_eur: Fact; cost_to_serve_12m_eur: Fact; active_business_lines: Fact; churn_prob_12m: Fact;
                  churn_drivers: { label: string; delta?: number | null }[]; clv_service_impact_eur: Fact;
                  percentiles: { clv_all?: number | null; clv_same_combo?: number | null; combo?: string | null } };
    products: Record<"energy" | "autostrom" | "mobile" | "shop" | "smart_living" | "internet",
                     { held?: boolean | null; opportunity: boolean; items: Record<string, unknown>[]; note?: string | null }>;
    consent: { type: ConsentType; status: string; effective_status: string; doi?: boolean | null; updated_at?: string | null; source?: string | null; override_reason?: string | null }[];
    channels: { channel: Channel; allowed: boolean; requires: ConsentType[]; reason: string }[];
    exclusions: { rule_id: string; active: boolean; detail?: string | null; src: string }[];
    highlights: { text: string; basis: string[]; rarity?: string | null }[];
    trends: Record<string, unknown> & { clv_note: string };
    fatigue: { contacts_30d: number; contacts_90d: number; response_rate?: number | null; repeatedly_ignored: string[]; legacy_no_consent_check: number; agent_feedback: Record<string, unknown>[] };
  };
  timeline: { id: string; date: string; future: boolean; kind: string; line?: string | null; title: string; detail?: string | null; src: string; ref?: string | null; flags: string[] }[];
  signals: Signal[]; candidates: Candidate[];
  blocked: { offer_id: string; channel?: Channel | null; rule_id: string; reason: string; src?: string | null; counterfactual_delta_clv?: number | null }[];
  chosen: { tuple_id: string /* "NO_ACTION" when nothing qualifies */; status: string; send_at?: string | null; reason_line: string;
            service_mode: boolean; agent_script?: string | null;
            content?: { language: "de"; tone: Tone; personalised: boolean; template_id: string; subject: string; body: string } | null };
  alternatives: { tuple_id: string; delta_clv: number; why_lower: string }[];
  legacy_comparison?: { rule_id?: string | null; offer_id?: string | null; channel?: string | null; decided_at?: string | null; delta_clv_our_model?: number | null; blocked_now_by: string[] } | null;
  explanation_path: PathStep[];
  checklist: { item: "consent_for_channel" | "profiling_consent" | "no_exclusion" | "not_owned" | "contact_cap" | "data_fresh"; passed: boolean; detail?: string | null; src?: string | null }[];
  data_quality: { code: string; level: "info" | "warn"; detail: string }[];
  decision_log: { ts: string; actor: string; action: string; tuple_id?: string | null; reason?: string | null }[];
}
```

## 4. Customer archetypes: use these, not older drafts

The archetypes are rule-based and computed by Agent KG; the first matching rule wins. The figures below are verified against the data at eval 2026-09-30. **Always show the engine's values; never present these ranges as facts about a customer.**

| ID | Name | Rule | Customers | CLV median | Churn median | Typical NBA focus |
|---|---|---|---|---|---|---|
| A4 | Retention risk ("do no harm") | Active exclusion (dunning, cancellation pending, open ticket, Autostrom cancelled) or churn ≥ 0.35 | 75 | €322 | 0.28 | Service first (P-SV-01). All cross- and upsell is blocked; a sales contact during a complaint or dunning adds +0.05 churn. StromGarant retention only when no exclusion is active |
| A1 | Smart eco-system adopter | Has a HEMS gateway | 33 | €932 | 0.07 | Dynamic tariff (P-EN-05) with a smart meter; Wallbox-Integration (P-SL-03); Speicher-Optimierung (P-SL-02) **only with a home battery**; retention when the price guarantee ends |
| A3 | EV driver | Active Autostrom | 201 | €517 | 0.20 | Service check after ≥ 3 failed sessions in 30 days (P-SV-01); otherwise home electricity (P-EN-01) or a wallbox |
| A5 | Growing connected household | Active mobile and (household size > SIM count, or data limit hit in the last 3 months) | 50 | €660 | 0.14 | Zusatz-SIM (P-MO-03); Mobil Upgrade (P-MO-02) after repeated data-limit hits |
| A2 | Traditional energy loyalist | Only energy contracts | 342 | €498 | 0.17 | Retention when the price guarantee ends; heat-pump tariff after a gas meter deregistration; otherwise a generic, non-personalised offer such as Mobil or Balkonkraftwerk |
| A0 | Other | Everything else | 49 | €256 | 0.22 | Case by case |

**Representative customers** for the demo. These facts are verified; use them in the mock data.

- **MG-100325, A1** (Hamburg, customer since 2020-02-23, household 2, app + portal):
  - StromWärme, 5,144 kWh/yr, smart meter + feed-in meter. The gas meter was deregistered (GasGarant, status `terminated_meter_deregistration`).
  - Mobil M: 30 GB, 3 SIMs, eSIM.
  - Autostrom: Mercedes-Benz EQA, 66 kWh.
  - HEMS devices: gateway, PV inverter, wallbox, heat pump, smart plug. **No home battery.**
  - Shop: Wallbox 11 kW (€699), Powerbank Solar (€59).
  - Margin €393.39; **cost to serve €55**; CLV €1,440; churn 0.149.
  - Churn drivers: multi-product (4 lines), **price guarantee ends < 90 days**, HEMS user.
  - Consent: newsletter, email, portal/app and profiling granted; phone withdrawn; SMS not given.
- **MG-100001, A2** (Köln, customer since 2013-11-22, born 1955 → "70–79", household 2, portal yes, app no):
  - StromAktiv, 1,770 kWh/yr, conventional meter, €61/month instalment.
  - Margin €86.94; cost to serve €19; CLV €261; churn 0.18 (driver: 2 tickets in 12 months).
  - Consent: newsletter, email, portal/app and profiling granted; phone and SMS withdrawn.
  - There is **no postal channel** in the data, so do not invent "statement inserts".

**Test customers** must render well: MG-100051, MG-100060, MG-100096, MG-100186, MG-100068, MG-100023, MG-100112, MG-100009, MG-100659, MG-100035, MG-100087, MG-100004, MG-100012. Expected stories:

- **MG-100009, MG-100659:** 3 failed charges in September → service first.
- **MG-100096:** dunning level 3 → service only.
- **MG-100186, MG-100004:** open complaint → service first.
- **MG-100035, MG-100087:** cancellation pending → no sales.
- **MG-100023:** wallbox bought, no Autostrom → Autostrom (P-AS-01).
- **MG-100112:** no profiling consent, so the wallbox signal is ignored; non-personalised logic only; the outcome is "no action" or a generic offer, depending on a pending team decision.
- **MG-100068:** gas deregistration + wallbox + price guarantee ending → ranking demo.
- **MG-100051, MG-100060:** gas deregistration → StromWärme.
- **MG-100012:** no profiling consent → generic offer, "nicht personalisiert".

## 5. The 18 actions in the catalog

| ID | Type | Name | Line | Margin if bought | Churn effect | Target signal |
|---|---|---|---|---|---|---|
| P-EN-01 | sales | StromAktiv | energy | +€114/yr | −0.02 | No electricity contract (e.g. Autostrom-only) |
| P-EN-03 | sales | StromWärme | energy | +€140/yr | −0.02 | Heat pump / gas meter deregistered |
| P-EN-04 | sales | GasAktiv | energy | +€111/yr | −0.02 | Gas heating: **not in the data, never evaluated** |
| P-EN-05 | sales | Dynamischer Stromtarif | energy | +€20/yr | −0.03 | Smart meter + HEMS / EV / heat pump |
| P-MO-01 | sales | Mobil S/M/L | mobile | +€54/yr | −0.02 | Energy customer without mobile |
| P-IN-01 | sales | Internet (DSL/Glasfaser) | internet | +€130/yr | −0.03 | **No ownership or availability data, never evaluated** |
| P-SL-01 | sales | HEMS Starter-Set | smart living | +€36/yr | −0.04 | PV / heat pump / EV without a HEMS gateway |
| P-AS-01 | sales | MAINGAU Autostrom | e-mobility | +€85/yr | −0.02 | EV driver (e.g. bought a wallbox) without Autostrom |
| P-MO-02 | upsell | Mobil Upgrade | mobile | +€18/yr | −0.03 | Data limit reached ≥ 2 of 3 months |
| P-MO-03 | upsell | Zusatz-SIM | mobile | +€29/yr | −0.01 | Household size > SIM count |
| P-SL-02 | upsell | HEMS Speicher-Optimierung | smart living | +€36/yr | −0.01 | HEMS + home battery |
| P-SL-03 | upsell | Wallbox-Integration | smart living | +€24/yr | −0.01 | HEMS + wallbox / EV |
| P-SH-01 | one_off | Balkonkraftwerk 800 W | shop | +€90 once | −0.01 | No PV |
| P-SH-02 | one_off | Wallbox 11 kW | shop | +€126 once | −0.01 | EV driver without a wallbox |
| P-SH-03 | one_off | Smarte Thermostate | shop | +€23 once | 0 | Gas heating |
| P-SH-04 | one_off | Smart Plug 4er-Set | shop | +€9 once | 0 | Digital customer, low basket |
| P-EN-02 | retention | StromGarant | energy | €0 (avoided churn) | −0.10 | Price guarantee ends < 90 days |
| P-SV-01 | service | Service-Only / No offer | service | €0 | Removes service churn drivers; costs €15 | Open complaint, dunning, cancellation, ≥ 3 failed charges |

One-off margins count **once**, not every year. Contact costs: email and newsletter €0.01, SMS €0.08, portal popup and app push €0, outbound call €6.

## 6. Hard rules the UI must make visible and never bypass

- Consent per channel:
  - newsletter needs `newsletter_email` with double opt-in;
  - email needs `marketing_email`;
  - call needs `marketing_phone`;
  - SMS needs `marketing_sms`;
  - popup / app push need `portal_app_personalisation` plus a portal account / installed app.
- Exclusions (dunning, cancellation pending, open ticket, Autostrom cancelled) block all sales, upsell, retention and one-off content. Service is still allowed.
- **No profiling consent → only non-personalised logic:** no signal is used for marketing; only generic catalog offers at the catalog-average probability; Sie; "nicht personalisiert".
- Payment data is only used for exclusion.
- Customer-facing content is German. No personalised prices, no false urgency.
- A human approves; nothing is sent automatically. Overrides cannot select a blocked combination.

## 7. Plan and definition of done

- **M0 (first hour):**
  - scaffold the app;
  - build mock `public/data/` for about 40 customers: both representatives, the 13 test customers, and the rest spread over archetypes, tiers and flags so every UI state appears;
  - put a visible "MOCK DATA" badge in the header.
- **M1:** worklist with ranking, filters, saved views, group-by and outlier styling; customer page with both cards.
- **M2:** NBA cards with waterfall, p evidence, notes, checklist, German preview and path chips; bulk preview with holdout; decisions in localStorage; export.
- **M3:**
  - switch to the real export (`python -m nba.build --export web/public/data`) when Agent NBA delivers it;
  - polish;
  - Vercel deploy;
  - (with repo access) Python `nba/profile/` builder for the left-card JSON (README §4.1 and §6.8).

**Done when:**
- all 13 test customers and both representatives render;
- every number has a source tooltip;
- missing data shows "not enough data";
- bulk approval excludes outliers and failing checklists unless explicitly confirmed;
- `npm run build` passes;
- the deployed site works without a backend.

**Working rules (with repo access):**
- Write only in your paths.
- Never edit `nba/contracts.py`. Ask Agent NBA in `log/agent-cards.md` if you need a field.
- At the end of every session, append an entry to `log/agent-cards.md` (template in the file): what you did, what you verified, questions, issues.
- Agent KG (Claude) reviews your work against README §7.2 and this prompt.

## 8. Git and commit rules (README §13; read them in full)

Three agents work in three folders of the same repo. On 26 Oct a branch switch in a shared folder put another agent's commit on the wrong branch, so these rules are strict.

- **Your folder:** `/Users/linhngo/Downloads/Work/Hackathon/MAINGAU` (the original folder), branch **`feat/cards`**.
  - Agent KG works in `../MAINGAU-kg` (`feat/kg`) and Agent NBA in `../MAINGAU-nba` (`feat/nba`). Never touch those folders.
  - Never switch branches in your folder.
- **Before every git command,** run `git status -sb`. It must show `## feat/cards`.
- **Stage only your paths:** `git add web nba/profile config/cards.yaml tests/test_profile_*.py log/agent-cards.md`.
  - Never `git add -A`, `git add .` or `git commit -a`.
  - Check `git diff --cached --stat` before each commit.
  - Never commit `web/node_modules/`, `web/dist/` or `.venv/`.
- **Contracts:** do not edit `nba/contracts.py`, `docs/schema/` or README §5. Ask Agent NBA in your log.
- **Sync:** `git fetch origin && git merge origin/main`. Do not rebase after you have pushed.
- **Deliver:**
  1. `npm run build` must pass.
  2. `git push -u origin feat/cards`.
  3. Then `git push origin feat/cards:main`. This works only as a fast-forward; if it is rejected, merge `origin/main` first. Never use `--force`.
- **Never** `git stash` (it is shared between worktrees), `git reset --hard`, `git clean`, or delete branches or worktrees.
- **If something goes wrong:** stop, log it under "Issues / risks" with the commands you ran, and ask Agent KG to repair it.
