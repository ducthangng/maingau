# UI brief: Overview page for the Orchestration dashboard

For whoever builds the UI in `web/` (team member or AI coding agent). Checked against `main` (f3b4254) and the static export in `web/public/data` on 27 Oct 2026.

## 0. Goal

A marketer opens the app and sees at once:
1. which actions bring the most value, and why;
2. how each action splits across the customer segments.

From any segment they jump into the Worklist, already filtered to those customers.

The page belongs to the **Orchestration** dashboard and must look like it (§6): same cards, type scale, thin bars, icons and tooltips as the Worklist and Groups pages. **Not a bare table.**

## 1. What exists today

- **Routes:** `/` Worklist, `/customer/:id`, `/groups`, `/service`, `/service/:id`. Nav in `components/Layout.tsx`: Worklist, Groups. The dashboard switch (`components/service/ViewSwitch.tsx`) sends "Orchestration" to `/`.
- **Worklist filters live in the URL** (`pages/Worklist.tsx`, `matches()` in `components/worklist/model.ts`):
  - `offer` = `chosen_offer`; `arch` = `A0…A5`; `pers` = `yes` / `no` (`personalised`);
  - `queue` = `todo` (default) / `done` / `hold` / `all`.
- **Clearing filters:** the Toolbar already has an ✕ button (`onClear`) that removes every filter.
- **Data:** `loadIndex()` (750 `IndexRow`s) and `loadSummary()` from `lib/data.ts`, with an API-first, static-fallback pattern. The Overview needs nothing else: no card files.
- **Names:**
  - offer names: `OFFER_NAME` in `components/worklist/model.ts`;
  - segment names: `IndexRow.archetype_name`, e.g. A2 "Traditional energy loyalist".

## 2. Routes and navigation

| File | Change |
|---|---|
| `App.tsx` | index route → `pages/Overview.tsx`; new route `worklist` → `pages/Worklist.tsx` |
| `components/Layout.tsx` | nav: **Overview** (`/`, `end`) · Worklist (`/worklist`) · Groups |
| `pages/Customer.tsx` | the three links back to the worklist (`navigate("/")` fallback, "Back to the worklist", the back link at line ~67) → `/worklist` |

- Nothing else in the Worklist, Customer or Groups pages changes.
- `ViewSwitch` keeps sending "Orchestration" to `/`, which is now the Overview.

## 3. Data and computation (client side, from `index.json` and `summary.json`)

```text
actions  = index rows with chosen_offer not in {"NO_ACTION", "P-SV-01"}
service  = index rows with chosen_offer == "P-SV-01"
group actions by chosen_offer:
  customers = count
  total     = sum(delta_clv)
  waiting   = count with deferred_until set     (shown in a tooltip only)
  reasons   = count by reason key:
                personalised == false  -> "no-profiling"
                otherwise              -> reason_signal + "|" + reason_need   (§7)
  segments  = count and sum(delta_clv) by segment key:
                personalised == false  -> "NP" ("Not personalised")
                otherwise              -> archetype (A0…A5)
sort actions by total desc, then customers desc, then offer ID
```

- **Rows with chosen_offer NO_ACTION** are left out entirely.
- **Rows waiting for a contact limit** (`deferred_until`) count in full: the action is chosen, it just goes out later.
- **Check:** each action's `customers` and `total` equal `summary.chosen_by_offer[offer].count` and `.sum_delta_clv`. Assert this in a test (§9).
- **Percentages:** within one action, round with the largest-remainder method, so the shown integers add up to exactly 100%. Do this separately for customers and for ΔCLV.

## 4. Part 1: action ranking

### Service line (above the table)

One row: `LifeBuoy` icon · "**47 service cases need attention** →". It links to `/worklist?offer=P-SV-01&queue=all`, and is hidden when the count is 0.

### Table

One row per action. Columns: rank · offer · customers · expected ΔCLV · main reason.

```text
 1  StromAktiv          175 customers   +€2,684  ████████████████
    Autostrom without home electricity → Home electricity for an EV driver
    No need signal: general offer (no profiling consent)                     (grey)
```

- **Offer:** `OFFER_NAME[offer]` in 15 px semibold; the offer ID only in the tooltip.
- **Customers:** count with the `Users` icon. When some wait, the tooltip says "46 of them wait for a contact limit".
- **Expected ΔCLV:**
  - the total in whole euros with a sign ("+€2,684"; the app's euro style, not "2.684 €");
  - wrapped in `Sourced` with `colSrc(summary, "delta_clv")`, like the Worklist KPI strip;
  - below it a `ValueBar` (from `components/viz.tsx`) scaled to the largest action's total.
- **Main reason:** at most **2 lines**, the most frequent reasons first.
  - A signal reason reads `{signal label} → {need label}`, with both labels from `kg/policy.yaml` (§7). Examples: "Gas meter deregistered → Heat pump / electric heating", "Price guarantee ends within 90 days → Price certainty".
  - The "no-profiling" reason is grey, with the `EyeOff` icon (the same icon as the `no_profiling` flag): "No need signal: general offer (no profiling consent)".
  - **Signal codes and counts only on hover:** the line's tooltip reads e.g. "S11 · 96 customers".
  - With more than 2 reasons, a third grey line says "+N other reasons"; its tooltip lists each remaining reason with code and count.

### Interaction

- Clicking a row (or pressing Enter / Space on it) opens its segment breakdown directly below (§5). Only one row is open at a time.
- The open action is kept in the URL (`/?open=P-EN-02`), so the browser's back button restores it, as in the Worklist.
- ↑ / ↓ move between rows, Esc closes the open one. The chevron rotates when a row is open.

## 5. Part 2: segment breakdown

It opens inside the clicked row, as a panel under it. It has 7 rows: A0–A5 by name, plus **Not personalised**.

```text
Segment                          Customers          Expected ΔCLV
A2 Traditional energy loyalist   44 · 67%  ▆▆▆▆▆▆   +€552 · 54%  ▆▆▆▆▆
A3 EV driver                      8 · 12%  ▆        +€170 · 17%  ▆▆
...
A4 Retention risk (do no harm)    –                 –                     (muted, not clickable)
Not personalised                  –                 –
```

- **Each row:** segment (ID chip + name) · customers "n · x%" · ΔCLV "+€… · y%". Under each number, a thin `ValueBar` whose length is the percentage (`max = 100`).
- **Sort** by ΔCLV, highest first; rows with no customers go last, muted, showing "–".
- **The two percentage columns** each add up to exactly 100% (§3).
- **Not personalised** has a tooltip: "No profiling consent: the engine uses general offers without need signals".
- **Clicking a row with customers** (or pressing Enter on it) opens the Worklist, filtered and showing every decision state:
  - segment A0–A5: `/worklist?offer={offer}&arch={A}&pers=yes&queue=all`;
  - Not personalised: `/worklist?offer={offer}&pers=no&queue=all`.

  `pers=yes` is required: customers without profiling consent still carry an archetype (for example, 229 of them are A2), so `arch` alone would mix the two groups. `queue=all` makes the Worklist show the same number of customers as the Overview. The Worklist's existing ✕ clears the filters.
- An `ArrowRight` icon appears on hover, to show that the row leads to the Worklist.

## 6. Visual style: match the Orchestration pages

Reuse these; do not invent new styles.

| Element | Use |
|---|---|
| Page header | As `pages/Groups.tsx`: `h1` 2xl semibold tracking-tight; a one-line description (15 px, neutral-600); a summary line (sm, neutral-500, tabular-nums): "10 actions · 617 customers · +€7,302 expected ΔCLV" |
| Cards | `rounded-2xl border border-neutral-200 bg-white`, as `KpiStrip` and `GroupCard` |
| Column and section labels | `text-[11px] font-semibold uppercase tracking-wider text-neutral-500` (`Section` in `components/Chips.tsx`, `Stat` in `GroupCard`) |
| Numbers | `tabular-nums`; money with `lib/format.ts`; every number has its source tooltip (`Sourced`, README §5.3) |
| Magnitude | `ValueBar` in the one accent colour. No status colours (red, amber, green) on this page; red appears only if a value were negative, which `ValueBar` already handles |
| Icons | lucide-react, 14–16 px: `ChevronRight`, `Users`, `LifeBuoy`, `EyeOff`, `ArrowRight` |
| Rows | `hover:bg-neutral-50`, 150 ms colour transitions, visible focus ring (global outline in `index.css`) |
| Open panel | `border-t border-neutral-100 bg-neutral-50/60`, padded like the card |
| Tooltips | native `title`, as everywhere else in the app |
| Loading / error | the same states as the Worklist (`useLoad`) |

- **Missing values** show "not enough data", never 0.
- **Width:** no horizontal scroll at 1280 px. Below 768 px, the reason lines wrap under the offer name and the bars stay.

## 7. Backend (done): which signal and need led to the action

Done on `main`; `web/src/types/contracts.ts` is regenerated. The fields:

| Where | Field | Value |
|---|---|---|
| `IndexRow` | `reason_signal` | first `Signal` node on the chosen action's path, e.g. `"S11"`; `null` for general offers |
| `IndexRow` | `reason_need` | first `Need` node on that path, e.g. `"N-HOME-ELECTRICITY"`; `null` for general offers |
| `Summary` | `signal_labels` | `{"S4": "Price guarantee ends within 90 days", …}`: `kg/policy.yaml` labels with the parameters filled in |
| `Summary` | `need_labels` | `{"N-HEAT-PUMP": "Heat pump / electric heating", …}`: `label_en` |

- These fields reach both modes: the API (`/api/customers`, `/api/summary`) and the static files (`index.json`, `summary.json`).
- An older export without them: show the reason column as "not enough data".

## 8. Acceptance (static export on `main`)

| Rank | Offer | Customers | ΔCLV | Reasons (hover) |
|---|---|---|---|---|
| 1 | StromAktiv | 175 (46 waiting) | +€2,684 | S11 → Home electricity for an EV driver · 96; no profiling · 79 |
| 2 | Mobil S/M/L | 202 (45 waiting) | +€1,988 | no profiling · 202 |
| 3 | HEMS Starter-Set | 125 | +€1,226 | no profiling · 100; S7 → Use own PV energy · 25 |
| 4 | StromGarant | 66 | +€1,014 | S4 → Price certainty · 66 |
| 5 | StromWärme | 6 | +€129 | S1 Gas meter deregistered → Heat pump / electric heating · 6 |
| 6–10 | Zusatz-SIM, HEMS Speicher-Optimierung, Wallbox-Integration, MAINGAU Autostrom, Dynamischer Stromtarif | 21, 9, 5, 5, 3 | +€122, +€77, +€31, +€21, +€8 | S6, S8, S8, S3, S9 |

- **Totals:** 10 actions · 617 customers · +€7,302. Service line: 47. The 86 NO_ACTION customers appear nowhere.
- **StromGarant segments:**

  | Segment | Customers | ΔCLV |
  |---|---|---|
  | A2 | 44 · 67% | +€552 · 54% |
  | A3 | 8 · 12% | +€170 · 17% |
  | A1 | 6 · 9% | +€148 · 15% |
  | A5 | 6 · 9% | +€102 · 10% |
  | A0 | 2 · 3% | +€42 · 4% |
  | A4, Not personalised | – | – |

- **StromAktiv segments:** A3 96 · 55% / +€1,504 · 56%; Not personalised 79 · 45% / +€1,180 · 44%.
- **Links:** clicking StromAktiv → Not personalised opens the Worklist with 79 rows; the ✕ clears the filters.
- **Navigation:** `/` shows the Overview, `/worklist` the Worklist, and "Back to the worklist" on a customer page goes to `/worklist`. The dashboard switch and Customer 360° work as before.
- **Modes:** everything works with the API running and with `VITE_STATIC=1`.

## 9. Files, tests, git

- **New files:**
  - `pages/Overview.tsx`;
  - `components/overview/ActionTable.tsx` and `SegmentBreakdown.tsx`;
  - `components/overview/model.ts`: the pure aggregation from §3, the largest-remainder rounding, the Worklist links.
- **Tests (vitest), `components/overview/model.test.ts`, over the real `public/data`:**
  - every action matches `summary.chosen_by_offer`;
  - the totals above;
  - both percentage columns add up to 100 for every action;
  - the NP and A-segment links (the Worklist's `matches()` with the link's filters returns the same count);
  - no reason line shows a signal code outside its tooltip.
- **Edits to existing files:** only those in §2.
- **Git:** work on your own branch (README §13), stage only these files, and run `npm test` and `npm run build` before pushing.
