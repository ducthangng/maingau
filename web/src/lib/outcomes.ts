import { useSyncExternalStore } from "react";
import { API_BASE, dataMode, invalidateAll, loadCard } from "./data";
import { invalidateLearnImpact } from "./kb";
import { REVIEWER, type Decision, settleCampaign } from "./decisions";

// Campaign fast-forward (the Campaigns pop-up): the simulated 14 days after the send. In API mode the NBA
// service draws the outcomes (POST /api/campaigns/{id}/fast-forward, nba/learn/outcomes.py) and adds them to the
// history it learns from; in static mode the same formula runs here, on the exported cards, and nothing learns.
//   actual ΔCLV = (CLV_buy if bought else CLV_no) − CLV_now − cost
// The control group was not sent: no outcome, no actual ΔCLV. Kept in localStorage, one entry per campaign.
const KEY = "maingau.outcomes.v1";
const EVENT = "maingau-outcomes";

export type OutcomeStatus = "bought" | "not_bought" | "control" | "not_valued";

export interface MemberOutcome {
  customer_id: string;
  tuple_id: string;
  contacted: boolean;
  status: OutcomeStatus;
  response?: string;
  response_at?: string | null;
  p?: number;
  expected_delta_clv?: number;
  actual_delta_clv?: number;
  conversion_value_eur?: number | null;
}

export interface OutcomeTotals {
  members: number;
  contacted: number;
  simulated: number;
  control: number;
  not_valued: number;
  bought: number;
  expected_bought: number;
  expected_delta_clv: number;
  actual_delta_clv: number;
}

/** Track record k of one offer × channel × tone, before and after the campaign's outcomes (API mode only). */
export interface LearnedK {
  tuple_id: string;
  k_before: number | null;
  k_after: number | null;
  p_before: number;
  p_after: number;
  bought: number;
  expected: number;
}

/** A sent customer whose next best action changed once the outcome was remembered (API mode only). */
export interface NextAction {
  customer_id: string;
  before: { tuple: string };
  after: { tuple: string; waits_until: string | null; delta_clv: number | null };
  sentence: string;
}

export interface CampaignOutcome {
  campaign: string;
  simulated_at: string;
  horizon_days: number;
  outcomes: MemberOutcome[];
  totals: OutcomeTotals;
  learned: LearnedK[];
  impact?: NextAction[];
  source: "api" | "static";
}

type Store = Record<string, CampaignOutcome>;

let cached: Store | null = null;

function read(): Store {
  if (cached) return cached;
  try {
    const v: unknown = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    cached = v && typeof v === "object" && !Array.isArray(v) ? (v as Store) : {};
  } catch {
    cached = {};
  }
  return cached;
}

function save(o: CampaignOutcome) {
  settleCampaign(o.campaign, o.simulated_at);
  cached = { ...read(), [o.campaign]: o };
  try {
    localStorage.setItem(KEY, JSON.stringify(cached));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
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

export function useOutcomes(): Store {
  return useSyncExternalStore(subscribe, read, () => ({}));
}

/** Sums over the simulated sends (control and not valued excluded); the same as the API's `totals`. */
export function outcomeTotals(outcomes: MemberOutcome[]): OutcomeTotals {
  const sent = outcomes.filter((o) => o.status === "bought" || o.status === "not_bought");
  const sum = (f: (o: MemberOutcome) => number) => Math.round(sent.reduce((s, o) => s + f(o), 0) * 100) / 100;
  return {
    members: outcomes.length,
    contacted: outcomes.filter((o) => o.contacted).length,
    simulated: sent.length,
    control: outcomes.filter((o) => o.status === "control").length,
    not_valued: outcomes.filter((o) => o.status === "not_valued").length,
    bought: outcomes.filter((o) => o.status === "bought").length,
    expected_bought: sum((o) => o.p ?? 0),
    expected_delta_clv: sum((o) => o.expected_delta_clv ?? 0),
    actual_delta_clv: sum((o) => o.actual_delta_clv ?? 0),
  };
}

/** A [0, 1) draw that depends only on the text (FNV-1a, then mulberry32): same campaign and customer, same outcome. */
export function seeded(text: string): () => number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  let a = h >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r2 = (v: number) => Math.round(v * 100) / 100;

/** Static mode: the API's simulation on the exported cards (same formula, a different random stream). */
async function simulateStatic(campaign: string, members: Decision[]): Promise<MemberOutcome[]> {
  return Promise.all(
    members.map(async (d): Promise<MemberOutcome> => {
      const base = { customer_id: d.customer_id, tuple_id: d.tuple_id, contacted: !d.holdout };
      if (d.holdout) return { ...base, status: "control" };
      const card = await loadCard(d.customer_id).catch(() => null);
      const v = card?.candidates?.find((c) => c.tuple_id === d.tuple_id)?.valuation;
      if (!v) return { ...base, status: "not_valued" };
      const rand = seeded(`${campaign}|${d.customer_id}`);
      const bought = rand() < v.p_accept;
      const after = bought ? v.clv_after_accept : v.clv_after_reject;
      return {
        ...base,
        status: bought ? "bought" : "not_bought",
        response: bought ? "clicked" : "ignored",
        p: Math.round(v.p_accept * 1e4) / 1e4,
        expected_delta_clv: r2(v.delta_clv),
        actual_delta_clv: r2(after - v.clv_now_model - v.contact_cost),
        conversion_value_eur: bought ? r2(Math.max(v.clv_after_accept - v.clv_after_reject, 1)) : null,
      };
    }),
  );
}

/** Simulate the campaign's outcomes once; a second call (or another tab's) returns the stored result. */
export async function fastForward(campaign: string, members: Decision[]): Promise<CampaignOutcome> {
  const known = read()[campaign];
  if (known) return known;
  if ((await dataMode()) === "api") {
    const res = await fetch(`${API_BASE}/api/campaigns/${encodeURIComponent(campaign)}/fast-forward`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: REVIEWER,
        members: members.map((d) => ({ customer_id: d.customer_id, tuple_id: d.tuple_id, holdout: d.holdout })),
      }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
      throw new Error(typeof body?.detail === "string" ? body.detail : `Fast-forward failed: HTTP ${res.status}`);
    }
    const o = (await res.json()) as Omit<CampaignOutcome, "source">;
    // The outcomes are now in the API's history: chances, proposals and the Learning view can all have moved.
    invalidateAll();
    invalidateLearnImpact();
    const out: CampaignOutcome = { ...o, learned: o.learned ?? [], source: "api" };
    save(out);
    return out;
  }
  const outcomes = await simulateStatic(campaign, members);
  const out: CampaignOutcome = {
    campaign,
    simulated_at: new Date().toISOString(),
    horizon_days: 14,
    outcomes,
    totals: outcomeTotals(outcomes),
    learned: [],
    source: "static",
  };
  save(out);
  return out;
}

/** Settle the decisions of every campaign this browser has an outcome for (e.g. one stored before settling existed). */
export function settleKnownOutcomes() {
  for (const o of Object.values(read())) settleCampaign(o.campaign, o.simulated_at);
}

/** API mode: pick up a fast-forward this browser has no copy of (another browser ran it, or local data was cleared). */
export async function syncOutcome(campaign: string): Promise<void> {
  const known = read()[campaign];
  if (known) return settleCampaign(campaign, known.simulated_at);
  if ((await dataMode()) !== "api") return;
  const res = await fetch(`${API_BASE}/api/campaigns/${encodeURIComponent(campaign)}/outcomes`).catch(() => null);
  if (!res?.ok) return;
  const o = (await res.json().catch(() => null)) as Omit<CampaignOutcome, "source"> | null;
  if (o?.campaign === campaign) save({ ...o, learned: o.learned ?? [], source: "api" });
}
