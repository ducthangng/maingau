import { CHANNEL_LABEL } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";

// Worklist view model (prompts/agent-cards.md §1.1). Everything here only orders, filters and
// sums what index.json already says; no valuation, rule or triage logic is re-implemented.

export const NO_ACTION = "NO_ACTION";

const TIER_RANK: Record<string, number> = { P1: 1, P2: 2, P3: 3, P4: 4, P5: 5 };

/** Ranking of the spec: urgency tier P1 first, then urgency_score descending. */
export function sortRows(rows: IndexRow[]): IndexRow[] {
  return [...rows].sort((a, b) => {
    const ta = TIER_RANK[a.urgency_tier ?? ""] ?? 9;
    const tb = TIER_RANK[b.urgency_tier ?? ""] ?? 9;
    if (ta !== tb) return ta - tb;
    return (b.urgency_score ?? -Infinity) - (a.urgency_score ?? -Infinity);
  });
}

export function isNoAction(r: IndexRow): boolean {
  return r.chosen_tuple === NO_ACTION || r.chosen_offer === NO_ACTION;
}

/** A row the marketer can act on: the engine proposed a concrete tuple. */
export function isActionable(r: IndexRow): boolean {
  return !!r.chosen_tuple && !isNoAction(r);
}

/** Blocked by rules: no action left, or an active customer-level exclusion. */
export function isBlocked(r: IndexRow): boolean {
  return isNoAction(r) || (r.exclusions?.length ?? 0) > 0;
}

// ---------------------------------------------------------------- saved views

export type ViewId = "all" | "p1" | "retention" | "upsell" | "outliers";

export const VIEWS: { id: ViewId; label: string; hint: string; test: (r: IndexRow) => boolean }[] = [
  { id: "all", label: "All", hint: "Every customer in the snapshot", test: () => true },
  { id: "p1", label: "Act now (P1)", hint: "Urgency tier P1", test: (r) => r.urgency_tier === "P1" },
  {
    id: "retention",
    label: "Retention this month",
    hint: "StromGarant (P-EN-02) proposed, or urgency tier P2",
    test: (r) => r.chosen_offer === "P-EN-02" || r.urgency_tier === "P2",
  },
  {
    id: "upsell",
    label: "Upsell opportunities",
    hint: "Marketing mode with a proposed action",
    test: (r) => !r.service_mode && isActionable(r),
  },
  { id: "outliers", label: "Outliers to review", hint: "outlier = true", test: (r) => r.outlier === true },
];

// ---------------------------------------------------------------- filters

export interface Filters {
  q: string;
  tier: string;
  arch: string;
  flag: string;
  offer: string;
  channel: string;
  conf: string;
  mode: string; // "" | "service" | "marketing"
  pers: string; // "" | "yes" | "no"
}

export const FILTER_KEYS = ["tier", "arch", "flag", "offer", "channel", "conf", "mode", "pers"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];

export const EMPTY_FILTERS: Filters = { q: "", tier: "", arch: "", flag: "", offer: "", channel: "", conf: "", mode: "", pers: "" };

/** Lower-case and strip diacritics so "munchen" finds "München". */
export function fold(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

export function matches(r: IndexRow, f: Filters): boolean {
  if (f.q) {
    const q = fold(f.q);
    if (!fold(r.customer_id).includes(q) && !fold(r.city ?? "").includes(q)) return false;
  }
  if (f.tier && r.urgency_tier !== f.tier) return false;
  if (f.arch && r.archetype !== f.arch) return false;
  if (f.flag && !(r.flags ?? []).includes(f.flag as never)) return false;
  if (f.offer && r.chosen_offer !== f.offer) return false;
  if (f.channel && r.channel !== f.channel) return false;
  if (f.conf && r.confidence !== f.conf) return false;
  if (f.mode === "service" && !r.service_mode) return false;
  if (f.mode === "marketing" && r.service_mode) return false;
  if (f.pers === "yes" && r.personalised !== true) return false;
  if (f.pers === "no" && r.personalised !== false) return false;
  return true;
}

export interface Option {
  value: string;
  label: string;
}

/** Filter choices taken from the data itself, so the selects never offer an empty bucket. */
export function filterOptions(rows: IndexRow[]): Record<"tier" | "arch" | "flag" | "offer" | "channel" | "conf", Option[]> {
  const uniq = (vals: (string | null | undefined)[]) => [...new Set(vals.filter((v): v is string => !!v))].sort();
  const archNames = new Map<string, string>();
  for (const r of rows) if (r.archetype && !archNames.has(r.archetype)) archNames.set(r.archetype, r.archetype_name ?? "");
  const confOrder = ["high", "medium", "low"];
  return {
    tier: uniq(rows.map((r) => r.urgency_tier)).map((v) => ({ value: v, label: v })),
    arch: [...archNames.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([id, name]) => ({ value: id, label: name ? `${id} · ${name}` : id })),
    flag: uniq(rows.flatMap((r) => r.flags ?? [])).map((v) => ({ value: v, label: v.replace(/_/g, " ") })),
    offer: uniq(rows.map((r) => r.chosen_offer)).map((v) => ({ value: v, label: v === NO_ACTION ? "No action" : offerLabel(v) })),
    channel: uniq(rows.map((r) => r.channel)).map((v) => ({ value: v, label: CHANNEL_LABEL[v] ?? v })),
    conf: confOrder.filter((c) => rows.some((r) => r.confidence === c)).map((v) => ({ value: v, label: v })),
  };
}

// ---------------------------------------------------------------- offers (display names only)

// Display names from the action catalog (prompts/agent-cards.md §5). index.json carries only the id.
export const OFFER_NAME: Record<string, string> = {
  "P-EN-01": "StromAktiv",
  "P-EN-02": "StromGarant",
  "P-EN-03": "StromWärme",
  "P-EN-04": "GasAktiv",
  "P-EN-05": "Dynamischer Stromtarif",
  "P-MO-01": "Mobil S/M/L",
  "P-MO-02": "Mobil Upgrade",
  "P-MO-03": "Zusatz-SIM",
  "P-IN-01": "Internet (DSL/Glasfaser)",
  "P-SL-01": "HEMS Starter-Set",
  "P-SL-02": "HEMS Speicher-Optimierung",
  "P-SL-03": "Wallbox-Integration",
  "P-AS-01": "MAINGAU Autostrom",
  "P-SH-01": "Balkonkraftwerk 800 W",
  "P-SH-02": "Wallbox 11 kW",
  "P-SH-03": "Smarte Thermostate",
  "P-SH-04": "Smart Plug 4er-Set",
  "P-SV-01": "Service only",
};

export function offerLabel(offerId: string | null | undefined): string {
  if (!offerId) return "";
  return OFFER_NAME[offerId] ? `${OFFER_NAME[offerId]} (${offerId})` : offerId;
}

// ---------------------------------------------------------------- KPIs and groups

/** Sum of the JSON's delta_clv over rows that have one; null when no row has a value. */
export function sumDelta(rows: IndexRow[]): { sum: number | null; n: number } {
  let sum = 0;
  let n = 0;
  for (const r of rows) {
    if (typeof r.delta_clv === "number" && !Number.isNaN(r.delta_clv)) {
      sum += r.delta_clv;
      n += 1;
    }
  }
  return { sum: n ? sum : null, n };
}

export interface Group {
  tuple: string;
  rows: IndexRow[];
  sum: number | null;
  n: number;
  reviewable: boolean; // bulk review only for marketing groups with an action
}

/** Group by chosen_tuple; order: highest Σ ΔCLV first, "No action" last. Rows keep their ranking. */
export function groupRows(rows: IndexRow[]): Group[] {
  const map = new Map<string, IndexRow[]>();
  for (const r of rows) {
    const key = r.chosen_tuple ?? (isNoAction(r) ? NO_ACTION : "unknown");
    const list = map.get(key);
    if (list) list.push(r);
    else map.set(key, [r]);
  }
  const groups: Group[] = [...map.entries()].map(([tuple, list]) => {
    const { sum, n } = sumDelta(list);
    const reviewable = tuple !== NO_ACTION && tuple !== "unknown" && list.every((r) => !r.service_mode);
    return { tuple, rows: list, sum, n, reviewable };
  });
  const last = (g: Group) => (g.tuple === NO_ACTION || g.tuple === "unknown" ? 1 : 0);
  return groups.sort((a, b) => last(a) - last(b) || (b.sum ?? -Infinity) - (a.sum ?? -Infinity) || b.rows.length - a.rows.length);
}

// ---------------------------------------------------------------- sources

/** Source string for an index column (summary.column_src), with a readable fallback. */
export function colSrc(summary: Summary | null, field: string): string {
  return summary?.column_src?.[field] ?? `index.${field}`;
}

/** As-of time for a source: customer_value is monthly (value_date); engine output is the snapshot. */
export function asOf(summary: Summary | null, src: string): string | null {
  if (!summary) return null;
  return src.startsWith("customer_value") ? (summary.value_date ?? summary.eval_time) : summary.eval_time;
}

// ---------------------------------------------------------------- action queues

// The worklist is a review queue: what still needs a human decision comes first. A queue only
// combines the engine's proposal with the local decision log; nothing is re-ranked.
export type QueueId = "todo" | "done" | "hold" | "all";

export const QUEUES: { id: QueueId; label: string; hint: string }[] = [
  { id: "todo", label: "To review", hint: "The engine proposed an action and nobody has decided yet" },
  { id: "done", label: "Decided", hint: "Approved, overridden or rejected in this browser" },
  { id: "hold", label: "Do not contact", hint: "No action passed the rules; nothing to decide" },
  { id: "all", label: "All", hint: "Every customer in the snapshot" },
];

export function queueOf(r: IndexRow, decided: boolean): Exclude<QueueId, "all"> {
  if (!isActionable(r)) return "hold";
  return decided ? "done" : "todo";
}
