import type { IndexRow, Summary } from "../../types/contracts";
import { EMPTY_FILTERS, OFFER_NAME, type Filters } from "../worklist/model";

// Overview (prompts/ui-overview.md §3): which actions bring the most value and why, and how each
// splits across the customer segments. Pure aggregation of index.json; nothing is re-valued.

export const SERVICE_OFFER = "P-SV-01";
export const NO_ACTION = "NO_ACTION";
export const NOT_PERSONALISED = "NP";
export const NO_PROFILING = "no-profiling";
/** Older exports without reason_signal / reason_need. */
export const UNKNOWN_REASON = "unknown";

export const SEGMENT_KEYS = ["A0", "A1", "A2", "A3", "A4", "A5", NOT_PERSONALISED] as const;
export type SegmentKey = (typeof SEGMENT_KEYS)[number];

// Fallback names (README §6.13) for segments no row in the export carries.
const SEGMENT_FALLBACK: Record<SegmentKey, string> = {
  A0: "Other",
  A1: "Smart eco-system adopter",
  A2: "Traditional energy loyalist",
  A3: "EV driver",
  A4: "Retention risk (do no harm)",
  A5: "Growing connected household",
  NP: "Not personalised",
};

export interface ReasonCount {
  key: string; // "no-profiling" | "unknown" | "<signal>|<need>"
  signal: string | null;
  need: string | null;
  count: number;
}

export interface SegmentStat {
  key: SegmentKey;
  name: string;
  customers: number;
  total: number;
  valued: number; // rows with a ΔCLV; 0 means "not enough data", never €0
  customersPct: number;
  totalPct: number;
}

export interface ActionStat {
  offer: string;
  name: string;
  customers: number;
  total: number;
  valued: number; // rows with a ΔCLV; 0 means "not enough data", never €0
  waiting: number;
  reasons: ReasonCount[];
  segments: SegmentStat[];
}

export interface Overview {
  actions: ActionStat[];
  service: number;
  customers: number;
  total: number;
  maxTotal: number;
}

/**
 * Integer percentages that add up to exactly `target` (largest-remainder method). Ties in the
 * remainder go to the larger value, then to the earlier position, so the result is deterministic.
 */
export function largestRemainder(values: number[], target = 100): number[] {
  const sum = values.reduce((a, v) => a + Math.max(0, v), 0);
  if (sum <= 0) return values.map(() => 0);
  const raw = values.map((v) => (Math.max(0, v) / sum) * target);
  const out = raw.map(Math.floor);
  let left = target - out.reduce((a, v) => a + v, 0);
  const order = raw
    .map((r, i) => ({ i, rem: r - Math.floor(r), v: values[i] }))
    .sort((a, b) => b.rem - a.rem || b.v - a.v || a.i - b.i);
  for (const { i } of order) {
    if (left <= 0) break;
    out[i] += 1;
    left -= 1;
  }
  return out;
}

export function reasonKey(r: IndexRow): string {
  if (r.personalised === false) return NO_PROFILING;
  if (!r.reason_signal && !r.reason_need) return UNKNOWN_REASON;
  return `${r.reason_signal ?? ""}|${r.reason_need ?? ""}`;
}

export function segmentKey(r: IndexRow): SegmentKey {
  if (r.personalised === false) return NOT_PERSONALISED;
  return (SEGMENT_KEYS as readonly string[]).includes(r.archetype ?? "") ? (r.archetype as SegmentKey) : "A0";
}

export function offerName(offer: string): string {
  return OFFER_NAME[offer] ?? offer;
}

export function buildOverview(rows: IndexRow[]): Overview {
  const names = new Map<string, string>();
  for (const r of rows) if (r.archetype && r.archetype_name && !names.has(r.archetype)) names.set(r.archetype, r.archetype_name);

  const byOffer = new Map<string, IndexRow[]>();
  let service = 0;
  for (const r of rows) {
    const offer = r.chosen_offer;
    if (!offer || offer === NO_ACTION) continue;
    if (offer === SERVICE_OFFER) {
      service += 1;
      continue;
    }
    byOffer.set(offer, [...(byOffer.get(offer) ?? []), r]);
  }

  const actions: ActionStat[] = [...byOffer.entries()].map(([offer, list]) => {
    const reasons = new Map<string, ReasonCount>();
    for (const r of list) {
      const key = reasonKey(r);
      const cur = reasons.get(key) ?? {
        key,
        signal: key.includes("|") ? r.reason_signal ?? null : null,
        need: key.includes("|") ? r.reason_need ?? null : null,
        count: 0,
      };
      cur.count += 1;
      reasons.set(key, cur);
    }
    const seg = new Map<SegmentKey, { customers: number; total: number; valued: number }>(
      SEGMENT_KEYS.map((k) => [k, { customers: 0, total: 0, valued: 0 }]),
    );
    for (const r of list) {
      const s = seg.get(segmentKey(r))!;
      s.customers += 1;
      s.total += r.delta_clv ?? 0;
      if (typeof r.delta_clv === "number") s.valued += 1;
    }
    const keys = [...SEGMENT_KEYS];
    const custPct = largestRemainder(keys.map((k) => seg.get(k)!.customers));
    const totalPct = largestRemainder(keys.map((k) => seg.get(k)!.total));
    const segments: SegmentStat[] = keys
      .map((k, i) => ({
        key: k,
        name: k === NOT_PERSONALISED ? SEGMENT_FALLBACK.NP : names.get(k) ?? SEGMENT_FALLBACK[k],
        customers: seg.get(k)!.customers,
        total: seg.get(k)!.total,
        valued: seg.get(k)!.valued,
        customersPct: custPct[i],
        totalPct: totalPct[i],
      }))
      .sort((a, b) => Number(b.customers > 0) - Number(a.customers > 0) || b.total - a.total || b.customers - a.customers || a.key.localeCompare(b.key));
    return {
      offer,
      name: offerName(offer),
      customers: list.length,
      total: list.reduce((a, r) => a + (r.delta_clv ?? 0), 0),
      valued: list.filter((r) => typeof r.delta_clv === "number").length,
      waiting: list.filter((r) => !!r.deferred_until).length,
      reasons: [...reasons.values()].sort((a, b) => b.count - a.count || a.key.localeCompare(b.key)),
      segments,
    };
  });
  actions.sort((a, b) => b.total - a.total || b.customers - a.customers || a.offer.localeCompare(b.offer));

  return {
    actions,
    service,
    customers: actions.reduce((a, x) => a + x.customers, 0),
    total: actions.reduce((a, x) => a + x.total, 0),
    maxTotal: Math.max(0, ...actions.map((a) => a.total)),
  };
}

// ---------------------------------------------------------------- reason lines (§4)

export interface ReasonLine {
  text: string; // visible text: labels only, never a signal code
  title: string; // tooltip: code and count
  general: boolean; // no-profiling line (grey, EyeOff icon)
  missing: boolean; // older export: "not enough data"
}

export function reasonLine(reason: ReasonCount, summary: Summary | null): ReasonLine {
  const n = `${reason.count} customer${reason.count === 1 ? "" : "s"}`;
  if (reason.key === NO_PROFILING) {
    return { text: "No need signal: general offer (no profiling consent)", title: `no profiling · ${n}`, general: true, missing: false };
  }
  if (reason.key === UNKNOWN_REASON) {
    return { text: "not enough data", title: `reason not in this export · ${n}`, general: false, missing: true };
  }
  const signal = reason.signal ? summary?.signal_labels?.[reason.signal] ?? null : null;
  const need = reason.need ? summary?.need_labels?.[reason.need] ?? null : null;
  const code = [reason.signal, reason.need].filter(Boolean).join(" → ");
  // Both halves or nothing: a lone label would read like a complete reason (older or mismatched summary).
  const missing = (!!reason.signal && !signal) || (!!reason.need && !need) || (!signal && !need);
  const text = missing ? "not enough data" : [signal, need].filter(Boolean).join(" → ");
  return { text, title: `${code} · ${n}`, general: false, missing };
}

// ---------------------------------------------------------------- Groups and Worklist links (§5)

/** Groups URL filtered to one action and segment (the Worklist's param names: offer, arch, pers). */
export function segmentLink(offer: string, segment: SegmentKey): string {
  const p = new URLSearchParams({ offer });
  if (segment === NOT_PERSONALISED) p.set("pers", "no");
  else {
    p.set("arch", segment);
    p.set("pers", "yes");
  }
  return `/groups?${p.toString()}`;
}

/** Groups URL with every segment of one action. */
export function actionGroupsLink(offer: string): string {
  return `/groups?${new URLSearchParams({ offer }).toString()}`;
}

export const SERVICE_LINK = `/worklist?offer=${SERVICE_OFFER}&queue=all`;

/** The filters a link sets (the Worklist and the Groups page read them from the query string). */
export function linkFilters(link: string): Filters {
  const p = new URLSearchParams(link.split("?")[1] ?? "");
  const f: Filters = { ...EMPTY_FILTERS };
  for (const k of Object.keys(EMPTY_FILTERS) as (keyof Filters)[]) f[k] = p.get(k) ?? "";
  return f;
}
