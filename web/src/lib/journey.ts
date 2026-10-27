import type { Journey } from "../types/contracts";
import { API_BASE, dataMode } from "./data";

// Customer journey for the Customer 360° view (docs/api.md §3.7), a document next to the card:
// API `GET /api/customers/{id}/journey`, static `data/journey/{id}.json` (same shape without `src` and `facts`).
const STATIC_BASE = `${import.meta.env.BASE_URL}data`;
const cache = new Map<string, Promise<Journey>>();

async function getJSON(url: string): Promise<Journey> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  if (!res.headers.get("content-type")?.includes("json")) throw new Error(`${url}: not JSON`);
  return res.json() as Promise<Journey>;
}

export function loadJourney(id: string): Promise<Journey> {
  if (!cache.has(id)) {
    const p = dataMode().then((mode) =>
      mode === "static"
        ? getJSON(`${STATIC_BASE}/journey/${id}.json`)
        : getJSON(`${API_BASE}/api/customers/${encodeURIComponent(id)}/journey`),
    );
    p.catch(() => cache.delete(id)); // a failed load is retried next time
    cache.set(id, p);
  }
  return cache.get(id)!;
}
