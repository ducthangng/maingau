# UI colours

MAINGAU palette: brand blue `#034c99`, yellow `#f3bf00`, white. Other teams use the same palette, so the
web UI keeps colour rare: white and neutral greys carry ~90% of every page. Tokens live in
`web/src/index.css` (`@theme`). This page replaces the colour notes in `ui-polish.md` (emerald, amber).

## Roles

| Role | Token / class | Used for |
|---|---|---|
| Base | white, `neutral-50…900` | Page, cards, text, borders, warnings |
| Primary, active | `accent-600` `#034c99` | Primary buttons (Approve, Execute), active nav pill, selected option badge, held product tile, consent granted |
| Text on light | `accent-700` `#033d7a`, `accent-800` `#022f5e` | Accent text and icons, trend "up and good", P2 chip fill |
| Fills | `accent-500` `#1f62ad`, `accent-400` `#4f86c6`, `accent-300` `#86a9d6` | Bars, rings, focus outline, online dot, confidence dots |
| Soft surfaces | `accent-100` `#d6e4f3`, `accent-50` `#eef4fb` | Selected row, approved chip, allowed channel, P3 chip |
| Danger only | `red-*` | Reject, blocked / compliance, negative ΔCLV, P1, errors, consent withdrawn, offline, high churn risk |
| Signature | `gold-400` `#f3bf00` (`gold-50` `#fff8db` spare) | Only the two uses below |

- **No green.** Approved, granted, held, online, converted and "up and good" are accent.
- **No amber.** Warnings, waiting, fatigue and data quality are neutral surfaces (`bg-neutral-50/100`,
  `text-neutral-700/800`, ring or border `neutral-200/300`) and always carry an icon (`TriangleAlert`,
  `LifeBuoy`, `BellOff`, `Clock`…), so meaning never depends on colour.
- **Urgency tiers:** P1 `bg-red-600 text-white` · P2 `bg-accent-700 text-white` · P3 `bg-accent-100 text-accent-800` ·
  P4 `bg-neutral-200 text-neutral-700` · P5 `bg-neutral-100 text-neutral-500`. Only P1 rows are tinted (`bg-red-50/60`).
- **Risk meter:** low `neutral-300`, medium `neutral-500`, high `red-500` (the label always sits beside it).
- **Charts** (Recharts, `components/profile/shared.tsx` `CHART`): hex values of `accent-500`, `accent-100`, `red-600`.

## Yellow: decoration only

Yellow only for the engine's #1 badge and the active nav underline:

1. The rank badge of the engine's #1 option (`bg-gold-400 text-neutral-900`): customer pop-up option list,
   Customer 360 NBA card, `#1` chip in the action header.
2. A 2 px underline (`inset-shadow-[0_-2px_0_var(--color-gold-400)]`) under the active main-nav item and the
   active side of the dashboard switch. The pill and `aria-selected` carry the state; the line is decoration.

Never use yellow for text, icons or thin lines on white, and never for a third purpose.

## Contrast (WCAG 2.x, on white unless noted)

| Pair | Ratio | Verdict |
|---|---|---|
| `#034c99` (accent-600) on white, and white on it | 8.41:1 | Text OK |
| `#033d7a` (accent-700) on white | 10.76:1 | Text OK |
| `#022f5e` (accent-800) on `#d6e4f3` (accent-100) | 10.35:1 | Text OK (P3 chip) |
| `#1f62ad` (accent-500) on white | 6.16:1 | Text OK |
| `#4f86c6` (accent-400) on white | 3.78:1 | Fills and rings only |
| `#f3bf00` (gold-400) on white | 1.71:1 | Decoration only |
| `neutral-900` on `#f3bf00` | 10.47:1 | Badge text OK |
| `#f3bf00` on `#034c99` | 4.91:1 | Underline on the nav pill is visible |
