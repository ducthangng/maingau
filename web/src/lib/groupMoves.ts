import { createContext, useSyncExternalStore } from "react";
import type { IndexRow } from "../types/contracts";
import { OFFER_NAME, sortRows } from "../components/worklist/model";
import type { Decision } from "./decisions";
import { CHANNEL_LABEL } from "./format";

// Group membership changed by a person on the group page (/group/:tuple): "Remove" takes a customer out
// of the group, "Change to this group" in the customer pop-up moves them to the group of another option.
// A move is not an approval: the customer waits in the new group until it is approved (Save & Run).
// Stored in localStorage only, like the campaigns; nothing is ever sent to a customer.
const KEY = "maingau.groupMoves.v1";
const EVENT = "maingau-group-moves";

export interface GroupMove {
  customer_id: string;
  from: string; // the group the customer left
  to: string | null; // the group they joined; null = removed from every group
  reason: string | null;
  ts: string;
  delta_clv: number | null; // valuation of the `to` option (from the customer card), shown in its group
  p_accept: number | null;
}

/** A customer's row as their group shows it; `engine_tuple` and `move_reason` are set when a person moved them. */
export type GroupRow = IndexRow & { engine_tuple?: string; move_reason?: string | null };

export function parseMoves(raw: string | null): GroupMove[] {
  try {
    const list: unknown = JSON.parse(raw ?? "[]");
    if (!Array.isArray(list)) return [];
    return list.filter(
      (m): m is GroupMove => !!m && typeof m === "object" && typeof m.customer_id === "string" && typeof m.from === "string",
    );
  } catch {
    return [];
  }
}

let cached: GroupMove[] | null = null;

function read(): GroupMove[] {
  if (cached) return cached;
  try {
    cached = parseMoves(localStorage.getItem(KEY));
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: GroupMove[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function recordMove(m: Omit<GroupMove, "ts">) {
  write([...read(), { ...m, ts: new Date().toISOString() }]);
}

function subscribe(cb: () => void) {
  const onStorage = (e: StorageEvent) => {
    if (e.key !== KEY && e.key !== null) return;
    cached = null;
    cb();
  };
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", onStorage);
  };
}

export function useGroupMoves(): GroupMove[] {
  return useSyncExternalStore(subscribe, read, () => []);
}

/** The latest move per customer. */
export function latestMoves(list: GroupMove[]): Map<string, GroupMove> {
  const out = new Map<string, GroupMove>();
  for (const m of list) out.set(m.customer_id, m);
  return out;
}

/**
 * The rows as their groups show them: a moved customer carries the tuple (and the valuation) of the
 * option a person picked; a removed one is returned in `removed` and is in no group. Moving a customer
 * back to the engine's own choice restores the engine's row.
 */
export function applyMoves(rows: IndexRow[], moves: Map<string, GroupMove>): { rows: GroupRow[]; removed: GroupRow[] } {
  const out: GroupRow[] = [];
  const removed: GroupRow[] = [];
  for (const r of rows) {
    const m = moves.get(r.customer_id);
    if (!m || m.to === r.chosen_tuple) {
      out.push(r);
      continue;
    }
    if (m.to === null) {
      removed.push({ ...r, move_reason: m.reason });
      continue;
    }
    const [offer, channel, tone] = m.to.split("|");
    out.push({
      ...r,
      chosen_tuple: m.to,
      chosen_offer: offer,
      channel,
      tone,
      delta_clv: m.delta_clv,
      p_accept: m.p_accept,
      engine_tuple: r.chosen_tuple ?? undefined,
      move_reason: m.reason,
    } as GroupRow);
  }
  return { rows: out, removed };
}

/** "Moved from StromAktiv · E-mail · Sie" for the row tooltip. */
export function movedFromLabel(r: GroupRow): string | null {
  if (!r.engine_tuple) return null;
  const [offer, channel, tone] = r.engine_tuple.split("|");
  return `Moved by a person from ${OFFER_NAME[offer] ?? offer} · ${CHANNEL_LABEL[channel] ?? channel} · ${tone === "du" ? "Du" : "Sie"}${r.move_reason ? `: ${r.move_reason}` : ""}`;
}

export interface GroupView {
  rows: GroupRow[]; // in the group now and never sent ("Sending"): what "Approve group" (Save & Run) approves
  removed: GroupRow[]; // taken out of this group with Remove, never sent ("Removed")
  sent: GroupRow[]; // in the group or removed from it, but already sent before: not shown on the page
}

/** Already sent: the latest decision approves an action (this group's or another), control group included. */
export function alreadySent(d: Decision | undefined): boolean {
  return !!d && (d.action === "approved" || d.action === "overridden");
}

/** The group page's membership: the engine's rows with the moves applied, restricted to one tuple (and tier). */
export function groupView(
  all: IndexRow[],
  moves: Map<string, GroupMove>,
  latest: Map<string, Decision>,
  tuple: string,
  tier: string | null,
): GroupView {
  const inTier = (r: IndexRow) => !tier || (r.urgency_tier ?? "P5") === tier;
  const applied = applyMoves(all, moves);
  const members = applied.rows.filter((r) => r.chosen_tuple === tuple && inTier(r));
  const out = applied.removed.filter((r) => moves.get(r.customer_id)?.from === tuple && inTier(r));
  const sent = (r: IndexRow) => alreadySent(latest.get(r.customer_id));
  return {
    rows: sortRows(members.filter((r) => !sent(r))) as GroupRow[],
    removed: sortRows(out.filter((r) => !sent(r))) as GroupRow[],
    sent: sortRows([...members, ...out].filter(sent)) as GroupRow[],
  };
}

/**
 * Set by the group page around the customer pop-up: there, choosing another option than the group's
 * moves the customer to that option's group ("Change to this group") instead of saving an override.
 */
export interface GroupContextValue {
  tuple: string;
  /** The customer whose pop-up was opened by the row's "Remove": the remove reason shows right away. */
  removing?: string | null;
  onMoved: () => void;
}

export const GroupContext = createContext<GroupContextValue | null>(null);
