# UI brief: polish Customer 360° and the Overview to the Orchestration standard (borders, clipping, responsive)

For whoever works on `web/` (team member or AI coding agent). Checked against `main` (c6c1708) on 27 Oct 2026.

## 0. Goal

The Orchestration pages (Worklist, the customer pop-up, Groups) set the visual standard: clean card edges, nothing clipped, text that wraps instead of being cut, and layouts that hold from a phone to a wide screen. Bring two views to that standard:
1. **Customer 360° customer page** (`/service/:id`): the three cards Profile · Customer journey · Next best actions.
2. **Overview** (`/`): the action ranking and the segment breakdown.

**Styling and layout only.** No change to data, wording, ranking or behaviour. The Orchestration pages must look exactly as they do now.

## 1. What is wrong today (with causes)

The screenshot shows the Next best actions card of `/service/MG-100096` at ≥ 1280 px. The left and top edges of the yellow banner and of the selected option are cut off.

| # | Problem | Cause |
|---|---|---|
| 1 | **Card edges are clipped** at the left and top of each Customer 360° column: the banner, the selected option (2 px green), and the lists. The keyboard focus outline is clipped too | `pages/Service.tsx` wraps each column body in `xl:max-h-[calc(100vh-17rem)] xl:overflow-y-auto xl:pr-1`. Outlines are drawn with `ring-*` (a box-shadow *outside* the element) and the global `:focus-visible` outline has `outline-offset-2` (`index.css`). An `overflow` box clips everything outside its padding box, and only the right side has padding |
| 2 | **Decision box looks broken**: a second top border inside the card, a large empty area on the left, and it sticks to the bottom of the scroll area | `components/service/ActionsTab.tsx` (~168) embeds `DecisionBox` from `components/customer/NbaPanel.tsx`. That is the pop-up's sticky footer: `sticky bottom-0 border-t … px-6 py-4 md:px-8`, with the status text placed `mr-auto` on the left |
| 3 | **Mixed card styles** | Orchestration cards are `rounded-2xl border border-neutral-200 bg-white` (KpiStrip, Overview, Groups). Customer 360° uses `rounded-xl … ring-1 ring-neutral-200` cards inside grey `bg-neutral-50/60` column cards, and column titles in a different style (`text-sm font-semibold`) |
| 4 | **Titles cut off in narrow columns** | `OptionRow` (ActionsTab ~60-66) uses `truncate` on the offer line and the reason line. At 1280 px the NBA column is about 550 px wide and the others about 345 px |
| 5 | **Hidden content in the column scroll areas**: the last list item is half visible ("Dynamischer Stromtarif"), with no hint that there is more | Fixed `max-h-[calc(100vh-17rem)]` (a guess at the header + strip height) and no visual cue at the bottom |
| 6 | **Overview at small widths** (check, then fix what fails): the segment breakdown keeps 4 columns (`SegmentBreakdown.tsx` GRID), so "42 · 67%" and "+€516 · 54%" get cramped below 640 px; the segment links have no inset focus style inside the `overflow-hidden` card | `components/overview/SegmentBreakdown.tsx` GRID and the `<Link>` classes |

## 2. Style rules (the Orchestration contract)

- **Cards:** `rounded-2xl border border-neutral-200 bg-white`. A list inside a card: `rounded-xl border border-neutral-200 bg-white divide-y divide-neutral-100`.
- **Static outlines use `border`**, which stays inside the box and is never clipped. `ring` is only for state (selected, focus). Use `ring-inset`, or give the parent room for it.
- **Every scroll or overflow container gets room for outlines:** at least 4 px of padding on all sides, with a matching negative margin so the alignment does not move (e.g. `p-1 -m-1`). Or every child inside uses inset rings or outlines (`focus-visible:outline-offset-[-2px]`, as `ActionTable.tsx` already does).
- **Labels:** 11 px uppercase tracking-wider neutral-500 (`Section` in `components/Chips.tsx`). Numbers `tabular-nums`. One accent colour for magnitude. Colours follow `prompts/ui-colors.md` (brand blue #034c99 as the one accent, yellow #f3bf00 only for the engine's #1 badge and the active nav, red only for danger); a status always comes with an icon and a label, as `FLAG_META` in `components/viz.tsx` does.
- **Text:** a primary title wraps (`line-clamp-2`, `break-words`). Only secondary text may `truncate`, and then it keeps the full text in `title`.
- **Size components by their container, not the viewport:** Tailwind v4 container queries (`@container` on the column, `@sm:` / `@md:` on children). A card in a narrow column must lay out like a card on a phone.

## 3. Changes

### 3.1 Customer 360° page (`pages/Service.tsx`)

- **Column cards:** use the Orchestration card (`rounded-2xl border border-neutral-200 bg-white`) and an 11 px uppercase title (`Section` style). Drop the grey `bg-neutral-50/60` layer, or keep it only as the page background, not as a card inside a card.
- **Scroll areas** (≥ xl):
  - replace `xl:pr-1` with padding on every side plus a negative margin (e.g. `xl:p-1 xl:-m-1`), and add `[scrollbar-gutter:stable]`;
  - set the height from the real layout, not `17rem`. Measure the header and strip height into a CSS variable (a `ResizeObserver` in `Service.tsx`), or let the three columns stretch to the viewport with a flex column layout;
  - add a bottom fade while the content overflows (`mask-image: linear-gradient(...)`, or a sticky gradient element) so the agent sees there is more.
- **Breakpoints:** one column below lg; from xl the three columns as now (`1fr 1fr 1.6fr`). Between lg and xl: Profile and Next best actions side by side, Journey full width below. Check that each column has a sensible minimum width.
- Add `@container` to each column so the cards inside can adapt (§3.2).

### 3.2 Next best actions card (`components/service/ActionsTab.tsx`)

- **Banner "Resolve the service issue first":**
  - `border border-neutral-200 bg-neutral-50` (no warning colour, see `prompts/ui-colors.md`), plus the `LifeBuoy` icon (the service icon in Orchestration) so the colour is not the only signal;
  - same padding and radius as the other notices.
  - Whether Customer 360° shows warning colours at all is a team decision (prompts/ui-customer360.md says no). Keep the colour, fix the style.
- **Option rows:**
  - `border border-neutral-200` at rest; selected: `ring-2 ring-inset ring-accent-600` with the yellow #1 badge (engine #1) or `ring-accent-500` (another choice), so nothing is drawn outside the row;
  - the offer line wraps (`line-clamp-2`) instead of `truncate`; the reason line also wraps (`line-clamp-2`);
  - the value bar shows from `@sm:` (container width), not `sm:` (viewport).
- **Decision box:** add an opt-in `variant="inline"` prop to `DecisionBox` in `NbaPanel.tsx`. The default stays exactly as today (the pop-up must not change). `inline` means:
  - no `sticky`, no `border-t`, no backdrop blur, padding `px-4 py-3`;
  - the status or hint text on its own line above the buttons;
  - buttons right-aligned from `@sm:` and full width below it.

  Wrap it in a normal list card (`rounded-xl border border-neutral-200 bg-white`), not a ring.
- **"Not recommended" list:** `border` instead of `ring-1`; long subjects wrap.

### 3.3 Profile and Customer journey cards

- `components/service/ProfileTab.tsx`, `JourneyTab.tsx`: the same rules. `ring-1` card outlines become `border`. Long values wrap or keep the full text in `title`. Product tiles and chips must not overflow the column at 345 px. Filter chips wrap onto two lines.

### 3.4 Overview (`pages/Overview.tsx`, `components/overview/*`)

- Check it at 375, 768, 1024, 1280 and 1440 px. Fix only what fails, keeping the current look.
- **Segment breakdown below `sm`:** two lines per segment: the name, then "customers · %" and "ΔCLV · %" with their bars side by side. No four cramped columns. From `sm` up, keep today's grid.
- **Segment links** inside the `overflow-hidden` card: an inset focus outline (`focus-visible:outline-offset-[-2px]`), like the action rows.
- No horizontal page scroll at 375 px. The reason lines wrap. Numbers are never cut.

## 4. Do not change

- Data, wording, ranking, links, keyboard behaviour, `aria-*` attributes.
- The Orchestration pages: `pages/Worklist.tsx`, `pages/Customer.tsx`, `pages/Groups.tsx`, `components/worklist/*`, `components/groups/*`, `components/nba/*`, and the pop-up.
  - `NbaPanel.tsx` only gains the opt-in `variant`, and its default rendering stays byte-for-byte the same.
  - A change in a shared file (`index.css`, `viz.tsx`, `Chips.tsx`) must not change how the Orchestration pages look.
- No new npm dependencies.

## 5. Acceptance

- **Widths:** 375, 768, 1024, 1280, 1440, 1920 px.
- **Customers:**
  - MG-100096 (service only, with the banner: the screenshot case);
  - MG-100023 (several options, a long reason);
  - MG-100186 (open ticket);
  - MG-100068 (many "Not recommended" rows).

| Check | Pass |
|---|---|
| Edges | No card, banner, selected row or list is clipped on any side. Tab through the page: every focus outline is fully visible |
| Decision box | One border, no empty left area, not sticky inside a column; the buttons fit at every width |
| Text | Offer names and reasons wrap (at most 2 lines), never cut mid-word without a tooltip |
| Scroll areas (≥ xl) | All content can be reached; a fade shows when there is more; nothing is half hidden at rest |
| Overview | No horizontal scroll at 375 px; the segment breakdown reads as two lines per segment on a phone; focus outlines visible |
| Orchestration | Screenshots of `/worklist`, `/customer/MG-100068` (pop-up open) and `/groups` are identical before and after |

- **Checks:** `npx tsc --noEmit`, `npm test`, `npm run build` in `web/`. The existing tests must stay green; they check text, not pixels.
- **Before and after screenshots** at the widths above (any browser, or an ad-hoc `npx playwright screenshot` run that is not committed). Attach them to the PR.

## 6. Git

Work on your own branch (README §13). Stage only the files you changed (`git add <paths>`, never `git add -A`). The commit message ends with your attribution line. Do not touch `web/public/data`.
