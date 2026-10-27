import { useSyncExternalStore } from "react";
import type { DecisionRequest, TupleRef } from "../types/contracts";
import { API_BASE, dataMode, invalidateCard } from "./data";

// Human-in-the-loop decisions (README §4.2 C8, §6.10). They are kept in localStorage and exported
// as CSV/JSON; in API mode each one is also posted to POST /api/customers/{id}/decision, which
// re-checks every rule. A refusal (409) removes the local entry again. Nothing is ever sent to a customer.
const KEY = "maingau.decisions.v1";
const EVENT = "maingau-decisions";

export type DecisionAction = "approved" | "overridden" | "rejected";

/** Why a person said no (nba/contracts.py ReasonCode); the API turns it into the customer's memory. */
export type ReasonCode = NonNullable<DecisionRequest["reason_code"]>;

/** Plain labels for the reject reasons, in the order the select lists them. */
export const REJECT_REASONS: Record<ReasonCode, string> = {
  already_has_product: "Already has it",
  customer_upset: "Customer upset",
  no_time: "No time right now",
  not_relevant: "Not relevant",
  wrong_channel: "Wrong channel",
  wrong_timing: "Wrong timing",
  data_wrong: "Data looks wrong",
  other: "Other",
};

/** Reason text kept next to the code: the label plus the optional note ("Other" with a note is just the note). */
export function rejectText(code: ReasonCode, note: string): string {
  const n = note.trim();
  return code === "other" && n ? n : n ? `${REJECT_REASONS[code]}: ${n}` : REJECT_REASONS[code];
}

export interface Decision {
  id: string; // `${customer_id}@${ts}`
  customer_id: string;
  action: DecisionAction;
  tuple_id: string; // the tuple that was approved / chosen by the override / rejected
  from_tuple: string; // the engine's proposal
  reason: string | null; // required for reject and override
  reason_code?: ReasonCode | null; // reject and override; missing on records saved before reason codes
  reviewer: string;
  ts: string;
  delta_clv: number | null;
  p_accept: number | null;
  group: string | null; // chosen_tuple of a bulk approval
  holdout: boolean; // true = kept as control, not exported for sending
  campaign?: string | null; // id of the campaign an "Approve everything" created; missing on older records
}

let cached: Decision[] | null = null;

/** The stored log; records saved before reason codes load as they are (reason_code missing). */
export function parseDecisions(raw: string | null): Decision[] {
  const list: unknown = JSON.parse(raw ?? "[]");
  return Array.isArray(list) ? (list as Decision[]) : [];
}

function read(): Decision[] {
  if (cached) return cached;
  try {
    cached = parseDecisions(localStorage.getItem(KEY));
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
  const added = items.map((d) => ({ ...d, ts, id: `${d.customer_id}@${ts}` }));
  write([...read(), ...added]);
  void syncToApi(added);
}

/* ------------------------------------------------------------------ API sync */

/** A decision the API refused or could not store; shown by <DecisionErrors>. */
export interface DecisionError {
  id: string;
  customer_id: string;
  tuple_id: string;
  action: DecisionAction;
  rule_ids: string[];
  reasons: string[];
}

const ERR_EVENT = "maingau-decision-errors";
let errors: DecisionError[] = [];

function setErrors(list: DecisionError[]) {
  errors = list;
  window.dispatchEvent(new Event(ERR_EVENT));
}

export function dismissDecisionError(id: string) {
  setErrors(errors.filter((e) => e.id !== id));
}

export function useDecisionErrors(): DecisionError[] {
  return useSyncExternalStore(
    (cb) => {
      window.addEventListener(ERR_EVENT, cb);
      return () => window.removeEventListener(ERR_EVENT, cb);
    },
    () => errors,
    () => errors,
  );
}

function tupleRef(tupleId: string): TupleRef | null {
  const [offer_id, channel, tone] = tupleId.split("|");
  return offer_id && channel && tone ? ({ offer_id, channel, tone } as TupleRef) : null;
}

export function toRequest(d: Decision): DecisionRequest {
  const action = d.action === "approved" ? "approve" : d.action === "overridden" ? "override" : "reject";
  // Approve sends the proposal it saw, so the API refuses it if the proposal changed meanwhile.
  // reason_code is what the feedback memory counts; reason alone is only a note.
  return { action, user: d.reviewer, reason: d.reason, reason_code: d.reason_code ?? null, tuple: tupleRef(d.tuple_id) };
}

async function postDecision(d: Decision): Promise<DecisionError | null> {
  try {
    const res = await fetch(`${API_BASE}/api/customers/${encodeURIComponent(d.customer_id)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toRequest(d)),
    });
    if (res.ok) return null;
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = body?.detail;
    const refusal =
      detail && typeof detail === "object" && "rule_ids" in detail
        ? (detail as { rule_ids: string[]; reasons: string[] })
        : { rule_ids: [], reasons: [typeof detail === "string" ? detail : `HTTP ${res.status}`] };
    return { id: d.id, customer_id: d.customer_id, tuple_id: d.tuple_id, action: d.action, ...refusal };
  } catch (err) {
    return { id: d.id, customer_id: d.customer_id, tuple_id: d.tuple_id, action: d.action, rule_ids: [], reasons: [String(err)] };
  }
}

// Holdout customers are the control group: approved here, but never handed to the API as an action.
async function syncToApi(added: Decision[]) {
  if ((await dataMode()) !== "api") return;
  const failed: DecisionError[] = [];
  for (const d of added.filter((x) => !x.holdout)) {
    const err = await postDecision(d);
    invalidateCard(d.customer_id);
    if (err) failed.push(err);
  }
  if (!failed.length) return;
  const ids = new Set(failed.map((e) => e.id));
  write(read().filter((d) => !ids.has(d.id)));
  setErrors([...errors, ...failed]);
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

/** FNV-1a hash of customer_id: the stable order the control group is drawn in. */
export function holdoutHash(customerId: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < customerId.length; i++) {
    h ^= customerId.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

/** Deterministic holdout by FNV-1a hash of customer_id, so the same customers are held out every time. */
export function isHoldout(customerId: string, pct = 10): boolean {
  return holdoutHash(customerId) % 100 < pct;
}

export const REVIEWER = "demo-marketer";

/** Approve or reject the engine's proposal straight from a worklist row (same record as the card's DecisionBar). */
export function decideRow(
  row: { customer_id: string; chosen_tuple?: string | null; delta_clv?: number | null; p_accept?: number | null },
  action: "approved" | "rejected",
  reason: string | null = null,
  reasonCode: ReasonCode | null = null,
) {
  if (!row.chosen_tuple) return;
  recordDecisions([
    {
      customer_id: row.customer_id,
      action,
      tuple_id: row.chosen_tuple,
      from_tuple: row.chosen_tuple,
      reason,
      reason_code: reasonCode,
      reviewer: REVIEWER,
      delta_clv: row.delta_clv ?? null,
      p_accept: row.p_accept ?? null,
      group: null,
      holdout: false,
    },
  ]);
}
