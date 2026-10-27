// Knowledge Base data (nba/kg/viz.py): the ontology, the policy layer and the decision graphs of the demo customers.
// API mode: GET /api/kb, built from the live engine. Static mode: public/data/kg_viz.json (scripts/export_kg_viz.py).

import { API_BASE, dataMode } from "./data";

export type NodeStatus = "chosen" | "blocked" | "waiting" | null;
export type EdgeStatus = "plain" | "chosen" | "blocked" | "waiting";

export interface KbNode {
  id: string;
  col: number;
  kind: string;
  label: string;
  sub?: string;
  status?: NodeStatus;
  detail?: Record<string, unknown>;
  path?: boolean;
}

export interface KbEdge {
  from: string;
  to: string;
  label?: string;
  status: EdgeStatus;
  path?: boolean;
}

export interface KbGraph {
  columns: string[];
  nodes: KbNode[];
  edges: KbEdge[];
}

export interface KbValuation {
  offer: string;
  channel: string;
  tone: string;
  dclv: number;
  p: number;
  confidence: string;
  p_level: string;
  n: number;
  conv: number;
  clv_now: number;
  clv_accept: number;
  clv_reject: number;
  cost: number;
  why?: string[];
}

export interface KbCustomer {
  id: string;
  case: string;
  headline: {
    archetype: string;
    urgency: string;
    urgency_reasons: string[];
    flags: string[];
    clv: number | null;
    churn: number | null;
    lines: number | null;
    tone: string;
    profiled: boolean;
  };
  evidence: { id: string; kind: string; label: string; src: string; facts: Record<string, unknown> }[];
  chosen: {
    tuple: string;
    reason: string;
    send_at?: string | null;
    until?: string | null;
    service?: boolean;
    subject?: string | null;
    template?: string | null;
    valuation?: KbValuation | null;
  };
  path: { kind: string; type: string; id?: string; label?: string }[];
  rules: { rule_id: string; tier: string; name: string; result: string; detail?: string }[];
  counter_line?: string;
  graph: KbGraph;
}

export interface KnowledgeBase {
  meta: { eval_time: string; customers: number; rule_set_version: string; workbook: string; act_now: number; waiting: number; no_action: number };
  ontology: KbGraph;
  policy_graph: KbGraph;
  policy: {
    compliance: { id: string; label: string; effect: string; kg_rules?: string[] }[];
    business: { id: string; name: string; kind: string; effect: string }[];
  };
  customers: Record<string, KbCustomer>;
}

/** Where the page's data came from: the API's live engine, or the generated file (static mode, or an API without /api/kb). */
export interface KbLoad {
  kb: KnowledgeBase;
  source: "live" | "file";
}

const STATIC_KB = `${import.meta.env.BASE_URL}data/kg_viz.json`;

async function getKb(url: string): Promise<KnowledgeBase | null> {
  const res = await fetch(url);
  // A static host answers a missing file with index.html (vercel.json rewrite): that is "no file" too.
  if (res.status === 404 || !res.headers.get("content-type")?.includes("json")) return null;
  if (!res.ok) throw new Error(`knowledge base: HTTP ${res.status}`);
  return res.json() as Promise<KnowledgeBase>;
}

/** Thrown when there is no knowledge base anywhere yet; the page then offers to generate it. */
export class NoKnowledgeBase extends Error {
  constructor() {
    super("No knowledge base has been generated yet.");
  }
}

/** API `GET /api/kb` (live: memory, campaign outcomes and rule edits included); the generated `data/kg_viz.json` when
 *  the API has no such route (started before it existed) or in static mode. Asked again on every visit; the API caches. */
export async function loadKnowledgeBase(): Promise<KbLoad> {
  if ((await dataMode()) === "api") {
    const live = await getKb(`${API_BASE}/api/kb`);
    if (live) return { kb: live, source: "live" };
  }
  const file = await getKb(STATIC_KB);
  if (file) return { kb: file, source: "file" };
  throw new NoKnowledgeBase();
}

/** API `POST /api/kb/generate`: build the knowledge base from the live engine and save it as `data/kg_viz.json`. */
export async function generateKnowledgeBase(): Promise<void> {
  if ((await dataMode()) !== "api") throw new Error("Generating needs the API: start it, or run the export script below.");
  const res = await fetch(`${API_BASE}/api/kb/generate`, { method: "POST" });
  if (res.status === 404 || res.status === 405)
    throw new Error("The API running now is older than this page and cannot generate it: restart the API, or run the export script below.");
  if (!res.ok) throw new Error(`Generating the knowledge base failed: HTTP ${res.status}`);
}

// ---------------------------------------------------------------- learning impact (nba/learn/impact.py)

export interface LearnDecision {
  tuple: string;
  waits_until: string | null;
  p: number | null;
  k: number | null;
  lift: number | null;
  delta_clv: number | null;
  clv_buy: number | null;
  clv_no: number | null;
}

export interface LearnChange {
  customer_id: string;
  cause: "evidence" | "memory";
  before: LearnDecision;
  after: LearnDecision;
  before_now?: Partial<LearnDecision>;
  winner_before?: Partial<LearnDecision> | null;
  sentence: string;
}

export interface LearnImpact {
  formula: string;
  summary: { customers: number; changed: number; by_cause: Record<string, number>; delta_clv: { baseline: number; evidence: number; learned: number } };
  k: { offer: string; channel: string; tone: string; sends: number; bought: number; expected: number; k: number }[];
  memory: { entries: number; active: number; by_kind: Record<string, number>; by_source: Record<string, number> };
  lookalike: { active: boolean; offers: { offer: string; name: string; recipients: number; buyers: number; more_likely: number; less_likely: number }[] };
  changes: LearnChange[];
}

let impactCache: Promise<LearnImpact> | null = null;

/** The next loadLearnImpact() asks again (after a campaign fast-forward taught the API new outcomes). */
export function invalidateLearnImpact() {
  impactCache = null;
}

/** API `GET /api/learn/impact`, static `data/learn_impact.json` (written by nba.build). */
export function loadLearnImpact(): Promise<LearnImpact> {
  if (!impactCache) {
    impactCache = dataMode()
      .then((mode) => fetch(mode === "api" ? `${API_BASE}/api/learn/impact` : `${import.meta.env.BASE_URL}data/learn_impact.json`))
      .then((res) => {
        if (!res.ok) throw new Error(`learning impact: HTTP ${res.status}`);
        return res.json() as Promise<LearnImpact>;
      });
    impactCache.catch(() => (impactCache = null));
  }
  return impactCache;
}
