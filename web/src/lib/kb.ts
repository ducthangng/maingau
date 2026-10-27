// Knowledge Base data (scripts/export_kg_viz.py → public/data/kg_viz.json): the ontology, the policy layer and
// the decision graphs of the demo customers. A static file in both modes; regenerate it with the script.

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

let cache: Promise<KnowledgeBase> | null = null;

export function loadKnowledgeBase(): Promise<KnowledgeBase> {
  if (!cache) {
    cache = fetch(`${import.meta.env.BASE_URL}data/kg_viz.json`).then((res) => {
      if (!res.ok) throw new Error(`kg_viz.json: HTTP ${res.status}`);
      return res.json() as Promise<KnowledgeBase>;
    });
    cache.catch(() => (cache = null)); // a failed load is retried next time
  }
  return cache;
}
