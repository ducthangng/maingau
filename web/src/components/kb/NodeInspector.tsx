import { ArrowDown, Ban, Check, ChevronDown, Clock, X } from "lucide-react";
import type { KbCustomer, KbGraph, KbNode, KnowledgeBase } from "../../lib/kb";
import { explain, fact, nameOf, story, tidy } from "./explain";

// What the Selected panel says about one box of the graph: why it is there (reason), how the engine got to it
// (the boxes upstream, also lit on the graph), and the rules that touched it. Everything is read from the export;
// the rules come from the blocked and waiting lines that carry a rule id, the box's "blocked by", and rule boxes.

const RULE_ID = /^([CBU]-\d+)\b/;

/** Every box upstream of `id` (its ancestors along the edges), plus the box itself. */
export function upstream(graph: KbGraph, id: string): Set<string> {
  const into = new Map<string, string[]>();
  for (const e of graph.edges) into.set(e.to, [...(into.get(e.to) ?? []), e.from]);
  const seen = new Set([id]);
  const todo = [id];
  while (todo.length) {
    for (const from of into.get(todo.pop()!) ?? []) {
      if (!seen.has(from)) {
        seen.add(from);
        todo.push(from);
      }
    }
  }
  return seen;
}

interface RuleHit {
  id: string;
  name: string;
  result: "block" | "defer" | "pass" | string;
  detail?: string;
}

export function rulesOf(node: KbNode, graph: KbGraph, kb: KnowledgeBase, customer?: KbCustomer): RuleHit[] {
  if (!customer) return [];
  const ids = new Map<string, string | undefined>(); // rule id -> what the graph says about it here
  const add = (id: string | undefined, note?: string) => id && !ids.has(id) && ids.set(id, note);
  const d = (node.detail ?? {}) as Record<string, unknown>;
  if (node.kind === "rule") add(node.label, d.reason as string | undefined);
  add(typeof d["blocked by"] === "string" ? (d["blocked by"] as string) : undefined, d.reason as string | undefined);
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  for (const e of graph.edges) {
    if (e.from !== node.id && e.to !== node.id) continue;
    if (e.status !== "blocked" && e.status !== "waiting") continue;
    const m = e.label?.match(RULE_ID) ?? e.label?.match(/^(ECON-[A-Z-]+)/);
    if (m) add(m[1], e.label);
    const other = byId.get(e.from === node.id ? e.to : e.from);
    if (other?.kind === "rule") add(other.label, (other.detail as Record<string, unknown> | undefined)?.reason as string | undefined);
    // A line without a rule id ("waits → date") is held back by the rule box that points at its other end.
    if (!m && other && other.kind !== "rule") {
      for (const r of graph.edges) {
        const rule = r.to === other.id ? byId.get(r.from) : undefined;
        if (rule?.kind === "rule") add(rule.label, (rule.detail as Record<string, unknown> | undefined)?.reason as string | undefined);
      }
    }
  }
  // A channel or consent that is not allowed is the consent rule's doing.
  if ((node.kind === "channel" || node.kind === "consent") && node.status === "blocked") add("C-01");
  const names = new Map<string, string>([
    ["ECON-NONPOSITIVE", "Expected gain is not positive"],
    ...kb.policy.compliance.map((r) => [r.id, r.label] as [string, string]),
    ...kb.policy.business.map((r) => [r.id, r.name] as [string, string]),
  ]);
  return [...ids].map(([id, note]) => {
    const r = customer.rules.find((x) => x.rule_id === id);
    return { id, name: r?.name ?? names.get(id) ?? id, result: r?.result ?? (node.status === "waiting" ? "defer" : "block"), detail: note ?? r?.detail };
  });
}

const RESULT: Record<string, { icon: typeof Ban; cls: string; label: string }> = {
  block: { icon: Ban, cls: "border-red-200 bg-red-50 text-red-700", label: "blocks" },
  defer: { icon: Clock, cls: "border-neutral-300 bg-neutral-50 text-neutral-700", label: "waits" },
  pass: { icon: Check, cls: "border-accent-200 bg-accent-50 text-accent-700", label: "passes" },
};

const SECTION = "text-[10px] font-semibold uppercase tracking-wider text-neutral-500";

export function Legend() {
  return (
    <div className="space-y-3 text-sm text-neutral-600">
      <p>Click a box in the graph to see why it is there, the path that leads to it, and the rules that touched it.</p>
      <ul className="space-y-1.5 text-[13px]">
        <li className="flex items-center gap-2"><span className="h-0.5 w-6 bg-accent-600" /> chosen path</li>
        <li className="flex items-center gap-2"><span className="h-0.5 w-6 bg-neutral-300" /> allowed alternative</li>
        <li className="flex items-center gap-2"><span className="w-6 border-t border-dashed border-neutral-400" /> waiting (a rule holds it back)</li>
        <li className="flex items-center gap-2"><span className="w-6 border-t border-dashed border-red-400" /> blocked by a rule</li>
      </ul>
    </div>
  );
}

export default function NodeInspector({
  node,
  graph,
  kb,
  customer,
  onClose,
}: {
  node: KbNode;
  graph: KbGraph;
  kb: KnowledgeBase;
  customer?: KbCustomer;
  onClose: () => void;
}) {
  const facts = customer?.evidence.find((e) => e.id === node.id)?.facts;
  const detail = Object.entries({ ...(node.detail ?? {}), ...(facts ?? {}) }).filter(
    ([k, v]) => v !== null && v !== undefined && v !== "" && k !== "reason" && k !== "detail",
  );
  const status = node.status ?? (node.path ? "on the path" : null);
  const tone =
    node.status === "blocked" ? "bg-red-50 text-red-700" : node.status === "chosen" || node.path ? "bg-accent-50 text-accent-700" : "bg-neutral-100 text-neutral-600";
  const ex = explain(node, graph, kb, customer);
  const rules = rulesOf(node, graph, kb, customer);
  const steps = story(graph, node.id, kb);

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${tone}`}>
            {node.kind}
            {status ? ` · ${status}` : ""}
          </span>
          <p className="mt-1.5 break-words text-base font-semibold text-neutral-900">{nameOf(node, kb, customer)}</p>
          <p className="font-mono text-[11px] text-neutral-500">{node.id}</p>
        </div>
        <button type="button" onClick={onClose} className="grid size-7 shrink-0 place-items-center rounded-md text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700" aria-label="Close">
          <X size={15} aria-hidden />
        </button>
      </div>

      <section className="space-y-1.5">
        <p className={SECTION}>What this means</p>
        <div className="space-y-1.5 rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2.5 text-[13px] leading-relaxed">
          <p className="font-medium text-neutral-900">{ex.what}</p>
          {ex.why && <p className="text-neutral-700">{ex.why}</p>}
        </div>
      </section>

      {steps.length > 0 && (
        <section className="space-y-1.5">
          <p className={SECTION}>How the engine got here</p>
          <ol className="space-y-0.5 text-[13px]">
            {steps.map((st, i) => (
              <li key={i}>
                {i === 0 && <p className="font-medium text-neutral-900">{st.from}</p>}
                <p className="flex items-center gap-1.5 py-0.5 pl-1 text-[12px] text-neutral-500">
                  <ArrowDown size={12} className="shrink-0 text-accent-400" aria-hidden />
                  {st.verb}
                </p>
                <p className={i === steps.length - 1 ? "font-semibold text-accent-700" : "font-medium text-neutral-900"}>{st.to}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {customer && (
        <section className="space-y-1.5">
          <p className={SECTION}>Rules that apply</p>
          {rules.length === 0 ? (
            <p className="text-[13px] text-neutral-500">Nothing blocks or holds back this box.</p>
          ) : (
            <ul className="space-y-1.5">
              {rules.map((r) => {
                const meta = RESULT[r.result] ?? RESULT.defer;
                const Icon = meta.icon;
                return (
                  <li key={r.id} className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-[13px] ${meta.cls}`}>
                    <Icon size={14} className="mt-0.5 shrink-0" aria-hidden />
                    <span className="min-w-0">
                      <span className="font-medium">{r.name}</span>
                      <span className="ml-1.5 font-mono text-[11px] opacity-75">
                        {r.id} · {meta.label}
                      </span>
                      {r.detail && <span className="block break-words text-neutral-600">{tidy(r.detail).replace(/^[CBU]-\d+\s*·\s*/, "")}</span>}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {detail.length > 0 && (
        <details className="group">
          <summary className={`flex cursor-pointer list-none items-center gap-1 ${SECTION} [&::-webkit-details-marker]:hidden`}>
            Data behind it ({detail.length})
            <ChevronDown size={12} className="transition-transform duration-150 group-open:rotate-180" aria-hidden />
          </summary>
          <dl className="mt-1.5 divide-y divide-neutral-100 rounded-xl border border-neutral-200 text-[13px]">
            {detail.map(([k, val]) => {
              const [label, text] = fact(k, val);
              return (
                <div key={k} className="flex flex-wrap justify-between gap-x-3 px-3 py-1.5">
                  <dt className="text-neutral-500">{label}</dt>
                  <dd className={`ml-auto min-w-0 break-words text-right text-neutral-900 ${typeof val === "number" ? "tabular-nums" : ""}`}>{text}</dd>
                </div>
              );
            })}
          </dl>
        </details>
      )}
    </div>
  );
}
