import { useEffect, useState } from "react";
import type { CustomerCard, IndexRow, Summary } from "../types/contracts";

// Static JSON written by web/mock/build_mock.py (mock) or `python -m nba.build --export web/public/data`.
const BASE = `${import.meta.env.BASE_URL}data`;

export interface Manifest {
  source: "mock" | string;
  generator?: string;
  real?: string[];
  mock?: string[];
  customers?: number;
}

const cache = new Map<string, Promise<unknown>>();

function fetchJSON<T>(path: string, optional = false): Promise<T | null> {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(`${BASE}/${path}`).then(async (res) => {
        if (!res.ok) {
          if (optional) return null;
          throw new Error(`${path}: HTTP ${res.status}`);
        }
        return res.json();
      }),
    );
  }
  return cache.get(path) as Promise<T | null>;
}

export const loadIndex = () => fetchJSON<IndexRow[]>("index.json") as Promise<IndexRow[]>;
export const loadSummary = () => fetchJSON<Summary>("summary.json") as Promise<Summary>;
export const loadCard = (id: string) => fetchJSON<CustomerCard>(`customers/${id}.json`) as Promise<CustomerCard>;
// Only the mock generator writes manifest.json; the real export has none, so the badge disappears.
export const loadManifest = () => fetchJSON<Manifest>("manifest.json", true);

export type Loadable<T> = { status: "loading" } | { status: "error"; error: string } | { status: "ready"; data: T };

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    load().then(
      (data) => alive && setState({ status: "ready", data }),
      (err: unknown) => alive && setState({ status: "error", error: String(err) }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
