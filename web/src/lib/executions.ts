import { useSyncExternalStore } from "react";
import { REVIEWER, type Decision } from "./decisions";

// Group executions: a reviewer hands a group of reviewed decisions to the campaign tool (as a file;
// nothing is sent from here). Recorded so the group leaves the "ready" list and can be re-downloaded.
const KEY = "maingau.executions.v1";
const EVENT = "maingau-executions";

export interface Execution {
  id: string;
  tuple: string; // the action the group executes
  decisions: Decision[]; // snapshot of what was handed off
  reviewer: string;
  ts: string;
}

let cached: Execution[] | null = null;

function read(): Execution[] {
  if (cached) return cached;
  try {
    cached = JSON.parse(localStorage.getItem(KEY) ?? "[]") as Execution[];
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: Execution[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function recordExecution(tuple: string, decisions: Decision[]): Execution {
  const ts = new Date().toISOString();
  const e = { id: `${tuple}@${ts}`, tuple, decisions, reviewer: REVIEWER, ts };
  write([...read(), e]);
  return e;
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useExecutions(): Execution[] {
  return useSyncExternalStore(subscribe, read, () => []);
}

/** Ids of decisions already handed off in some execution. */
export function executedIds(list: Execution[]): Set<string> {
  return new Set(list.flatMap((e) => e.decisions.map((d) => d.id)));
}
