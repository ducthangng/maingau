import { useEffect, useState } from "react";
import type { CustomerCard, IndexRow, Summary } from "../types/contracts";

// Two sources with the same JSON shapes (docs/api.md):
// - API: the NBA service (`uvicorn api.app:app`), reached through the Vite proxy or VITE_API_BASE;
// - static: JSON written by `python -m nba.build --export web/public/data` (Vercel demo) or the mock.
// VITE_STATIC=1 forces static; otherwise the API is tried once and static is the fallback.
const STATIC_BASE = `${import.meta.env.BASE_URL}data`;
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export type DataMode = "api" | "static";

export interface Manifest {
  source: "mock" | string;
  generator?: string;
  real?: string[];
  mock?: string[];
  customers?: number;
}

const cache = new Map<string, Promise<unknown>>();

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.status === 404 ? "Unknown customer" : `${url}: HTTP ${res.status}`);
  // A static host answers unknown paths with index.html (vercel.json rewrite), so check the type.
  if (!res.headers.get("content-type")?.includes("json")) throw new Error(`${url}: not JSON`);
  return res.json() as Promise<T>;
}

// The probe doubles as the first summary request, so API mode costs no extra call.
let probe: Promise<Summary> | null = null;
let modePromise: Promise<DataMode> | null = null;
export function dataMode(): Promise<DataMode> {
  if (!modePromise) {
    if (import.meta.env.VITE_STATIC === "1") modePromise = Promise.resolve("static");
    else {
      probe = getJSON<Summary>(`${API_BASE}/api/summary`);
      modePromise = probe.then(
        () => "api" as const,
        () => "static" as const,
      );
    }
  }
  return modePromise;
}

function load<T>(key: string, apiPath: string, staticPath: string): Promise<T> {
  if (!cache.has(key)) {
    cache.set(
      key,
      dataMode().then((mode): Promise<T> => {
        if (mode === "static") return getJSON<T>(`${STATIC_BASE}/${staticPath}`);
        return key === "summary" && probe ? (probe as Promise<T>) : getJSON<T>(`${API_BASE}${apiPath}`);
      }),
    );
  }
  return cache.get(key) as Promise<T>;
}

export const loadIndex = () => load<IndexRow[]>("index", "/api/customers", "index.json");
export const loadSummary = () => load<Summary>("summary", "/api/summary", "summary.json");
export const loadCard = (id: string) => load<CustomerCard>(`card:${id}`, `/api/customers/${encodeURIComponent(id)}`, `customers/${id}.json`);

// Only the mock generator writes manifest.json; the real export and the API have none, so the badge disappears.
export const loadManifest = () =>
  dataMode().then((mode) => (mode === "api" ? null : getJSON<Manifest>(`${STATIC_BASE}/manifest.json`).catch(() => null)));

/** Drop every cached response (index, summary, cards): the API just learned from new outcomes, so every chance can move. */
export function invalidateAll() {
  cache.clear();
  probe = null;
}

/** Drop a cached card so the next load shows the decision the API just stored. */
export function invalidateCard(id: string) {
  cache.delete(`card:${id}`);
}

export type Loadable<T> = { status: "loading" } | { status: "error"; error: string } | { status: "ready"; data: T };

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    load().then(
      (data) => alive && setState({ status: "ready", data }),
      (err: unknown) => alive && setState({ status: "error", error: err instanceof Error ? err.message : String(err) }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
