import type { IndexRow } from "../../types/contracts";
import { OUTLIER_FLAGS } from "../Chips";
import { type Decision, isHoldout } from "../../lib/decisions";
import { isMissing, tupleLabel } from "../../lib/format";

// Grouping and bulk-approval gates for the Groups screen (prompts/agent-cards.md §1.2, §1.4).
// Valuation numbers come from index.json as-is; this file only sums and sorts them for display.

export const SERVICE_OFFER = "P-SV-01";
export const HOLDOUT_PCT = 10;

export type ChecklistKey = NonNullable<IndexRow["checklist_failed"]>[number];

export const CHECKLIST_LABEL: Record<ChecklistKey, string> = {
  consent_for_channel: "no channel consent",
  profiling_consent: "no profiling consent",
  no_exclusion: "exclusion active",
  not_owned: "already owns the product",
  contact_cap: "contact cap reached",
  data_fresh: "data not fresh",
};

export function isServiceRow(r: IndexRow): boolean {
  return r.service_mode === true || r.chosen_offer === SERVICE_OFFER || (r.chosen_tuple ?? "").startsWith(`${SERVICE_OFFER}|`);
}

/** Sum of the values that exist; null when rows exist but none has a value ("not enough data", never 0). An empty selection sums to 0. */
export function sumOf(rows: IndexRow[], key: "delta_clv" | "p_accept" | "contact_cost"): { total: number | null; missing: number } {
  let total = 0;
  let present = 0;
  for (const r of rows) {
    const v = r[key];
    if (isMissing(v)) continue;
    total += v;
    present++;
  }
  return { total: present || !rows.length ? total : null, missing: rows.length - present };
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export interface Group {
  tuple: string;
  rows: IndexRow[];
}

export function buildGroups(rows: IndexRow[]): { sales: Group[]; service: IndexRow[]; noAction: number } {
  const byTuple = new Map<string, IndexRow[]>();
  const service: IndexRow[] = [];
  let noAction = 0;
  for (const r of rows) {
    const tuple = r.chosen_tuple;
    if (!tuple || tuple === "NO_ACTION") {
      noAction++;
      continue;
    }
    if (isServiceRow(r)) {
      service.push(r);
      continue;
    }
    const list = byTuple.get(tuple) ?? [];
    list.push(r);
    byTuple.set(tuple, list);
  }
  const sales = [...byTuple.entries()].map(([tuple, list]) => ({ tuple, rows: list }));
  sales.sort((a, b) => (sumOf(b.rows, "delta_clv").total ?? -Infinity) - (sumOf(a.rows, "delta_clv").total ?? -Infinity) || b.rows.length - a.rows.length);
  service.sort((a, b) => (b.urgency_score ?? 0) - (a.urgency_score ?? 0));
  return { sales, service, noAction };
}

// ---------------------------------------------------------------- member gates

export type Gate = "ready" | "review" | "blocked";

export interface Reason {
  kind: "do_no_harm" | "outlier" | "checklist" | "low_confidence" | "no_data" | "prior_decision";
  label: string;
  title?: string;
}

export interface Member {
  row: IndexRow;
  gate: Gate;
  reasons: Reason[];
}

const flagName = (f: string) => f.replace(/_/g, " ");

/** A human decision a bulk approval must not silently replace: a reject, or an override to another tuple (§1.2, C8). */
export function priorDecisionReason(previous: Decision | undefined, tuple: string | undefined): Reason | null {
  if (!previous) return null;
  const why = previous.reason ? `: ${previous.reason}` : "";
  const by = `${previous.reviewer} · ${previous.ts}`;
  if (previous.action === "rejected") {
    return { kind: "prior_decision", label: `Rejected earlier${why}`, title: `Rejected by ${by}` };
  }
  if (previous.action === "overridden" && previous.tuple_id !== tuple) {
    return {
      kind: "prior_decision",
      label: `Overridden earlier → ${tupleLabel(previous.tuple_id)}${why}`,
      title: `Overridden by ${by}`,
    };
  }
  return null;
}

/**
 * blocked: "do no harm" (archetype A4 or service_critical) — never in a bulk sales group.
 * review: outlier, failing checklist item, missing valuation, low confidence (when chosen), or an
 *         earlier reject / override by a marketer — excluded by default, included only by an explicit
 *         tick ("second look").
 */
export function assess(row: IndexRow, excludeLowConfidence: boolean, previous?: Decision, tuple?: string): Member {
  const reasons: Reason[] = [];
  const flags = row.flags ?? [];

  if (row.archetype === "A4") {
    reasons.push({ kind: "do_no_harm", label: "Do no harm · A4", title: row.archetype_name ?? "Archetype A4 (retention risk)" });
  }
  if (flags.includes("service_critical")) {
    reasons.push({ kind: "do_no_harm", label: "Do no harm · service critical", title: "Open service issue: resolve first, no sales contact" });
  }

  const outlierFlags = flags.filter((f) => OUTLIER_FLAGS.has(f) && f !== "service_critical");
  if (outlierFlags.length) {
    reasons.push({ kind: "outlier", label: `Outlier · ${outlierFlags.map(flagName).join(", ")}`, title: "Outlier: review individually before including" });
  } else if (row.outlier && !reasons.length) {
    reasons.push({ kind: "outlier", label: "Outlier", title: "Marked as outlier by triage" });
  }

  for (const item of row.checklist_failed ?? []) {
    reasons.push({ kind: "checklist", label: `✗ ${CHECKLIST_LABEL[item] ?? flagName(item)}`, title: `Checklist item failed: ${item}` });
  }

  if (isMissing(row.delta_clv) || isMissing(row.p_accept)) {
    reasons.push({ kind: "no_data", label: "No valuation", title: "ΔCLV or p is missing: not enough data" });
  }

  if (excludeLowConfidence && row.confidence === "low") {
    reasons.push({ kind: "low_confidence", label: "Low confidence", title: "Fewer than 30 observations behind p" });
  }

  const prior = priorDecisionReason(previous, tuple ?? row.chosen_tuple ?? undefined);
  if (prior) reasons.unshift(prior);

  const gate: Gate = reasons.some((r) => r.kind === "do_no_harm") ? "blocked" : reasons.length ? "review" : "ready";
  return { row, gate, reasons };
}

export interface GateCounts {
  ready: number;
  review: number;
  blocked: number;
}

export function gateCounts(rows: IndexRow[], latest?: Map<string, Decision>, tuple?: string): GateCounts {
  const out: GateCounts = { ready: 0, review: 0, blocked: 0 };
  for (const r of rows) out[assess(r, false, latest?.get(r.customer_id), tuple).gate]++;
  return out;
}

export function holdoutOf(customerId: string, enabled: boolean): boolean {
  return enabled && isHoldout(customerId, HOLDOUT_PCT);
}
