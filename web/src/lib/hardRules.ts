import { useSyncExternalStore } from "react";
import { REVIEWER } from "./decisions";

// Hard rules: constraints a human sets before acting, for one customer, a segment (archetype) or
// everyone. They never re-rank the engine's output; they only lock options that break them so they
// cannot be approved. Like decisions, the static demo keeps them in localStorage.
const KEY = "maingau.hardRules.v1";
const EVENT = "maingau-hard-rules";

export type RuleKind = "block_channel" | "block_offer" | "pause_until";
export type RuleScope = "customer" | "segment" | "all";

export interface HardRule {
  id: string;
  kind: RuleKind;
  value: string; // channel id, offer id, or ISO date
  scope: RuleScope;
  target: string | null; // customer_id for "customer", archetype id for "segment"
  targetLabel: string | null;
  reason: string | null;
  createdBy: string;
  ts: string;
}

let cached: HardRule[] | null = null;

function read(): HardRule[] {
  if (cached) return cached;
  try {
    cached = JSON.parse(localStorage.getItem(KEY) ?? "[]") as HardRule[];
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: HardRule[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function addRule(r: Omit<HardRule, "id" | "ts" | "createdBy">) {
  const ts = new Date().toISOString();
  write([...read(), { ...r, id: `${r.kind}@${ts}`, ts, createdBy: REVIEWER }]);
}

export function removeRule(id: string) {
  write(read().filter((r) => r.id !== id));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useHardRules(): HardRule[] {
  return useSyncExternalStore(subscribe, read, () => []);
}

export interface RuleSubject {
  customer_id: string;
  archetype?: string | null;
}

/** Rules that cover this customer (their own, their segment's, and the global ones). */
export function rulesFor(rules: HardRule[], s: RuleSubject): HardRule[] {
  return rules.filter((r) => r.scope === "all" || (r.scope === "customer" && r.target === s.customer_id) || (r.scope === "segment" && r.target === s.archetype));
}

/**
 * The first rule an action breaks, or undefined. `today` is the snapshot date (YYYY-MM-DD), so a
 * pause is judged against the same "now" as the engine.
 */
export function violation(rules: HardRule[], s: RuleSubject, action: { offer?: string | null; channel?: string | null }, today: string): HardRule | undefined {
  return rulesFor(rules, s).find((r) => {
    if (r.kind === "block_channel") return !!action.channel && action.channel === r.value;
    if (r.kind === "block_offer") return !!action.offer && action.offer === r.value;
    return today < r.value; // pause_until
  });
}
