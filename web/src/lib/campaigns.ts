import { useSyncExternalStore } from "react";

// Campaigns created by "Approve everything" on the Groups page: a name, the filter it ran under and
// what it approved. The decisions themselves are in lib/decisions.ts (field `campaign` = id).
// Stored in localStorage only; nothing is ever sent to a customer.
const KEY = "maingau.campaigns.v1";
const EVENT = "maingau-campaigns";

export interface Campaign {
  id: string; // `CMP-${epoch ms}`
  name: string;
  created_at: string;
  reviewer: string;
  offer: string | null; // the action filter used, null = all actions
  arch: string | null;
  pers: string | null; // "yes" | "no" | null
  scope: string; // readable action and segment, e.g. "StromGarant · A2 Traditional energy loyalist"
  holdout_pct: number;
  groups: string[]; // tuples with at least one approved customer
  customers: number; // approved, control group included
  contacted: number;
  holdout: number;
  delta_clv: number | null; // Σ expected ΔCLV of the contacted customers
}

/** The stored list; bad JSON or entries without an id and a name are dropped, never thrown. */
export function parseCampaigns(raw: string | null): Campaign[] {
  try {
    const list: unknown = JSON.parse(raw ?? "[]");
    if (!Array.isArray(list)) return [];
    return list.filter(
      (c): c is Campaign => !!c && typeof c === "object" && typeof (c as Campaign).id === "string" && typeof (c as Campaign).name === "string",
    );
  } catch {
    return [];
  }
}

let cached: Campaign[] | null = null;

function read(): Campaign[] {
  if (cached) return cached;
  try {
    cached = parseCampaigns(localStorage.getItem(KEY));
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: Campaign[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function saveCampaign(c: Campaign) {
  write([...read(), c]);
}

function subscribe(cb: () => void) {
  // Another tab wrote the list: drop the cache so read() picks up its rows.
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

/** Campaigns in the order they were created (oldest first); the list on the page reverses it. */
export function useCampaigns(): Campaign[] {
  return useSyncExternalStore(subscribe, read, () => []);
}
