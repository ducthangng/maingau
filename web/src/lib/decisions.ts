import { useSyncExternalStore } from "react";

// Human-in-the-loop decisions (README §4.2 C8, §6.10). The static demo keeps them in localStorage
// and exports them as CSV/JSON; nothing is ever sent to a customer.
const KEY = "maingau.decisions.v1";
const EVENT = "maingau-decisions";

export type DecisionAction = "approved" | "overridden" | "rejected";

export interface Decision {
  id: string; // `${customer_id}@${ts}`
  customer_id: string;
  action: DecisionAction;
  tuple_id: string; // the tuple that was approved / chosen by the override / rejected
  from_tuple: string; // the engine's proposal
  reason: string | null; // required for reject and override
  reviewer: string;
  ts: string;
  delta_clv: number | null;
  p_accept: number | null;
  group: string | null; // chosen_tuple of a bulk approval
  holdout: boolean; // true = kept as control, not exported for sending
}

let cached: Decision[] | null = null;

function read(): Decision[] {
  if (cached) return cached;
  try {
    cached = JSON.parse(localStorage.getItem(KEY) ?? "[]") as Decision[];
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: Decision[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function recordDecisions(items: Omit<Decision, "id" | "ts">[]) {
  const ts = new Date().toISOString();
  write([...read(), ...items.map((d) => ({ ...d, ts, id: `${d.customer_id}@${ts}` }))]);
}

export function clearDecisions() {
  write([]);
}

/** Delete one decision (e.g. an override the reviewer takes back); the previous one applies again. */
export function removeDecision(id: string) {
  write(read().filter((d) => d.id !== id));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useDecisions(): Decision[] {
  return useSyncExternalStore(subscribe, read, () => []);
}

/** Latest decision per customer (the log itself is append-only). */
export function latestByCustomer(list: Decision[]): Map<string, Decision> {
  const out = new Map<string, Decision>();
  for (const d of list) out.set(d.customer_id, d);
  return out;
}

const CSV_COLUMNS: (keyof Decision)[] = [
  "customer_id", "action", "tuple_id", "from_tuple", "delta_clv", "p_accept", "reason", "reviewer", "ts", "group", "holdout",
];

export function toCSV(list: Decision[]): string {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [CSV_COLUMNS.join(","), ...list.map((d) => CSV_COLUMNS.map((c) => esc(d[c])).join(","))].join("\n");
}

export function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Deterministic holdout by FNV-1a hash of customer_id, so the same customers are held out every time. */
export function isHoldout(customerId: string, pct = 10): boolean {
  let h = 0x811c9dc5;
  for (let i = 0; i < customerId.length; i++) {
    h ^= customerId.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h % 100 < pct;
}

export const REVIEWER = "demo-marketer";

/** Approve or reject the engine's proposal straight from a worklist row (same record as the card's DecisionBar). */
export function decideRow(
  row: { customer_id: string; chosen_tuple?: string | null; delta_clv?: number | null; p_accept?: number | null },
  action: "approved" | "rejected",
  reason: string | null = null,
) {
  if (!row.chosen_tuple) return;
  recordDecisions([
    {
      customer_id: row.customer_id,
      action,
      tuple_id: row.chosen_tuple,
      from_tuple: row.chosen_tuple,
      reason,
      reviewer: REVIEWER,
      delta_clv: row.delta_clv ?? null,
      p_accept: row.p_accept ?? null,
      group: null,
      holdout: false,
    },
  ]);
}
