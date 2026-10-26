import { useSyncExternalStore } from "react";

// Global rules (docs/rule-center.md). Seed rules and the condition catalogue come from
// public/data/rules.json (web/mock/build_rules.py now, Agent NBA's export later); this browser only
// overlays ticks and user-added rules, kept in localStorage. Nothing here evaluates a rule.

export type RuleTier = "hard" | "custom";
export type RuleOp = "=" | "!=" | ">=" | "<=" | "within_days";
export type RuleValue = string | number | boolean;

export interface Condition {
  entity: string; // sheet name, e.g. "energy_contracts"
  column: string;
  op: RuleOp;
  value: RuleValue;
  label: string; // "dunning level ≥ 2"
}

export interface RuleNode {
  id: string;
  name: string;
  tier: RuleTier;
  active: boolean;
  locked?: boolean; // tier 1 compliance, legally required: the card asks before it is unticked
  target?: string;
  condition?: Condition;
  children: RuleNode[];
}

export interface Operator {
  id: string; // `${column}|${op}|${value}`
  column: string;
  op: RuleOp;
  value: RuleValue;
  label: string;
}

export interface Entity {
  id: string;
  label: string;
  operators: Operator[];
}

export interface RulesFile {
  version: 1;
  generated_at: string;
  rules: RuleNode[];
  entities: Entity[];
}

let file: Promise<RulesFile> | null = null;

export function loadRules(): Promise<RulesFile> {
  file ??= fetch(`${import.meta.env.BASE_URL}data/rules.json`).then((res) => {
    if (!res.ok) throw new Error(`rules.json: HTTP ${res.status}`);
    return res.json() as Promise<RulesFile>;
  });
  return file;
}

// ---- local overlay -------------------------------------------------------------------------

const KEY = "maingau.rules.v1";
const EVENT = "maingau-rules";
export const ROOT = "root";

/** added[parentId | "root"] = user rules under that parent; active[id] = a tick that differs from the rule's preset. */
export interface RuleState {
  version: 1;
  added: Record<string, RuleNode[]>;
  active: Record<string, boolean>;
  next: number; // next user id: U-1, U-2, … never reused
}

const EMPTY: RuleState = { version: 1, added: {}, active: {}, next: 1 };
let cached: RuleState | null = null;

const isObject = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

function isCondition(v: unknown): boolean {
  return (
    isObject(v) &&
    ["entity", "column", "op", "label"].every((k) => typeof v[k] === "string") &&
    ["string", "number", "boolean"].includes(typeof v.value)
  );
}

/** A stored user rule, checked all the way down: one bad node would otherwise break the page on render. */
function isNode(v: unknown): boolean {
  return (
    isObject(v) &&
    typeof v.id === "string" &&
    typeof v.name === "string" &&
    (v.tier === "hard" || v.tier === "custom") &&
    typeof v.active === "boolean" &&
    (v.condition === undefined || isCondition(v.condition)) &&
    Array.isArray(v.children) &&
    v.children.every(isNode)
  );
}

function isState(v: unknown): v is RuleState {
  return (
    isObject(v) &&
    v.version === 1 &&
    Number.isInteger(v.next) &&
    isObject(v.added) &&
    Object.values(v.added).every((list) => Array.isArray(list) && list.every(isNode)) &&
    isObject(v.active) &&
    Object.values(v.active).every((on) => typeof on === "boolean")
  );
}

function read(): RuleState {
  if (cached) return cached;
  try {
    const s: unknown = JSON.parse(localStorage.getItem(KEY) ?? "null");
    cached = isState(s) ? s : EMPTY; // anything malformed: start clean rather than crash
  } catch {
    cached = EMPTY;
  }
  return cached;
}

function write(s: RuleState) {
  cached = s;
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void) {
  const onStorage = (e: StorageEvent) => {
    if (e.key !== KEY) return;
    cached = null; // another tab wrote: re-read
    cb();
  };
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", onStorage);
  };
}

export function useRuleState(): RuleState {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}

/** Tick or untick a rule. A tick equal to the preset is dropped, so a later rules.json default still applies. */
export function setActive(id: string, on: boolean, preset: boolean) {
  const s = read();
  const active = { ...s.active };
  if (on === preset) delete active[id];
  else active[id] = on;
  write({ ...s, active });
}

/** A rule from the popup before it gets an id. */
export type NewRule = Omit<RuleNode, "id" | "children"> & { children: NewRule[] };

/** Append rules under a parent (ROOT for a top-level rule); returns the new top-level ids. */
export function addRules(parentId: string, rules: NewRule[]): string[] {
  const s = read();
  let next = s.next;
  const withIds = (r: NewRule): RuleNode => ({ ...r, id: `U-${next++}`, children: r.children.map(withIds) });
  const nodes = rules.map(withIds);
  write({ ...s, next, added: { ...s.added, [parentId]: [...(s.added[parentId] ?? []), ...nodes] } });
  return nodes.map((n) => n.id);
}

/** Remove a user rule with everything under it. Seed rules are not in `added`, so they stay. */
export function removeRule(id: string) {
  const s = read();
  const gone = new Set<string>();
  const collect = (n: RuleNode) => {
    gone.add(n.id);
    n.children.forEach(collect);
    (s.added[n.id] ?? []).forEach(collect);
  };
  const prune = (list: RuleNode[]): RuleNode[] =>
    list.flatMap((n) => {
      if (n.id === id) {
        collect(n);
        return [];
      }
      return [{ ...n, children: prune(n.children) }];
    });
  const added: Record<string, RuleNode[]> = {};
  for (const [parent, list] of Object.entries(s.added)) added[parent] = prune(list);
  for (const g of gone) delete added[g];
  const active = Object.fromEntries(Object.entries(s.active).filter(([k]) => !gone.has(k)));
  write({ ...s, added, active });
}

// ---- merged view ---------------------------------------------------------------------------

export interface RuleView extends Omit<RuleNode, "children"> {
  user: boolean; // added in this browser: removable
  preset: boolean; // the tick in rules.json, or the Value chosen in the popup
  children: RuleView[];
}

/** Seed rules from the file with this browser's ticks and additions laid over them. */
export function mergeRules(seed: RuleNode[], s: RuleState): RuleView[] {
  const view = (n: RuleNode, user: boolean): RuleView => ({
    ...n,
    user,
    preset: n.active,
    active: s.active[n.id] ?? n.active,
    children: [...n.children.map((c) => view(c, user)), ...(s.added[n.id] ?? []).map((c) => view(c, true))],
  });
  return [...seed.map((n) => view(n, false)), ...(s.added[ROOT] ?? []).map((n) => view(n, true))];
}

/** Rules that are on and whose parents are all on. */
export function countActive(rules: RuleView[], parentOn = true): number {
  return rules.reduce((sum, r) => {
    const on = parentOn && r.active;
    return sum + (on ? 1 : 0) + countActive(r.children, on);
  }, 0);
}
