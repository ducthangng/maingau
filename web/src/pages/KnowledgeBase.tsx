import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, Clock, History, MinusCircle, Route, Search, ShieldCheck,  Zap, type LucideIcon } from "lucide-react";
import LayerGraph from "../components/kb/LayerGraph";
import NodeInspector, { Legend, upstream } from "../components/kb/NodeInspector";
import ProfileSummary from "../components/kb/ProfileSummary";
import ZoomCanvas from "../components/kb/ZoomCanvas";
import { mockName } from "../lib/customerMock";
import { useLoad } from "../lib/data";
import { loadKnowledgeBase, type KbCustomer, type KbGraph, type KbNode, type KnowledgeBase as KB } from "../lib/kb";

// Knowledge Base (scripts/export_kg_viz.py): how the engine got from a customer's data to the decision, the policy
// layer behind every rule, and the ontology. Demo view over the 8 demo customers; read only.

type View = "customer" | "policy" | "ontology";
const VIEWS: { id: View; label: string }[] = [
  { id: "customer", label: "Customer decision" },
  { id: "policy", label: "Policy" },
  { id: "ontology", label: "Ontology" },
];

const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";

/** A collapsible section of the left column (closed sections keep the column short). The accent tone marks the
 *  decision itself; every other section is neutral. */
function Fold({ title, icon: Icon, open = false, accent = false, children }: { title: string; icon?: LucideIcon; open?: boolean; accent?: boolean; children: ReactNode }) {
  return (
    <details open={open} className={`group overflow-hidden rounded-2xl border bg-white ${accent ? "border-accent-200" : "border-neutral-200"}`}>
      <summary
        className={`flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden ${accent ? "bg-accent-50" : ""}`}
      >
        <span className={`flex items-center gap-1.5 ${LABEL} ${accent ? "text-accent-700!" : ""}`}>
          {Icon && <Icon size={14} className={accent ? "text-accent-600" : "text-neutral-400"} aria-hidden />}
          {title}
        </span>
        <ChevronDown size={14} className="text-neutral-400 transition-transform duration-150 group-open:rotate-180" aria-hidden />
      </summary>
      <div className={`border-t px-4 py-3 text-sm text-neutral-700 ${accent ? "border-accent-100" : "border-neutral-100"}`}>{children}</div>
    </details>
  );
}

function resultChip(result: string) {
  const cls = result === "block" ? "bg-red-50 text-red-700 ring-red-200" : "bg-neutral-100 text-neutral-700 ring-neutral-200";
  return <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${cls}`}>{result}</span>;
}

function CustomerFolds({ c }: { c: KbCustomer }) {
  return (
    <>
      <Fold title="Rules" icon={ShieldCheck}>
        {c.counter_line && <p className="mb-2 rounded-lg bg-neutral-50 px-3 py-1.5 font-mono text-[11.5px] text-neutral-600">{c.counter_line}</p>}
        <ul className="space-y-2">
          {c.rules.map((r) => (
            <li key={`${r.rule_id}-${r.result}`} className="flex items-start gap-2 text-[13px]">
              <span className="w-12 shrink-0 font-mono text-[12px] text-neutral-500">{r.rule_id}</span>
              {resultChip(r.result)}
              <span className="min-w-0 text-neutral-700">{r.detail ?? r.name}</span>
            </li>
          ))}
        </ul>
      </Fold>
      <Fold title="Explanation path" icon={Route}>
        <ol className="space-y-1.5">
          {c.path
            .filter((s) => s.kind === "node")
            .map((s, i) => (
              <li key={`${s.type}-${i}`} className="flex gap-2 text-[13px]">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent-600 text-[10px] font-semibold text-white">{i + 1}</span>
                <span className="min-w-0">
                  <span className="text-neutral-500">{s.type}</span> · <span className="text-neutral-900">{s.label ?? s.id}</span>
                </span>
              </li>
            ))}
        </ol>
      </Fold>
    </>
  );
}

function PolicyFolds({ kb }: { kb: KB }) {
  return (
    <>
      <Fold title="Compliance rules (always on)" open>
        <ul className="space-y-1.5 text-[13px]">
          {kb.policy.compliance.map((r) => (
            <li key={r.id} className="flex gap-2">
              <span className="w-10 shrink-0 font-mono text-[12px] text-neutral-500">{r.id}</span>
              <span className="min-w-0 text-neutral-800">{r.label}</span>
            </li>
          ))}
        </ul>
      </Fold>
      <Fold title="Business rules">
        <ul className="space-y-1.5 text-[13px]">
          {kb.policy.business.map((r) => (
            <li key={r.id} className="flex gap-2">
              <span className="w-10 shrink-0 font-mono text-[12px] text-neutral-500">{r.id}</span>
              <span className="min-w-0 text-neutral-800">
                {r.name} <span className="text-neutral-400">· {r.effect.replace(/_/g, " ").toLowerCase()}</span>
              </span>
            </li>
          ))}
        </ul>
      </Fold>
    </>
  );
}

function OntologyFolds({ graph }: { graph: KbGraph }) {
  const kinds = graph.nodes.reduce<Record<string, number>>((m, n) => ({ ...m, [n.kind]: (m[n.kind] ?? 0) + 1 }), {});
  return (
    <Fold title="About the ontology" open>
      <p>
        The node and edge types every customer graph is built from: {kinds.instance ?? 0} instance types (from the data) and {kinds.type ?? 0} policy
        types (from <span className="font-mono text-[12px]">kg/policy.yaml</span>), joined by {graph.edges.length} edge types.
      </p>
    </Fold>
  );
}

/** The search that replaces the customer chips: only the demo customers of the export. */
function CustomerSearch({ kb, value, onPick }: { kb: KB; value: string; onPick: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const all = Object.values(kb.customers);
  const hits = all.filter((c) => `${c.id} ${c.case} ${mockName(c.id)}`.toLowerCase().includes(q.trim().toLowerCase()));
  const pick = (id: string) => {
    onPick(id);
    setQ("");
    setOpen(false);
  };
  return (
    <div className="relative w-full max-w-md">
      <label className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 focus-within:border-accent-500">
        <Search className="size-4 text-neutral-400" aria-hidden />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && hits[0]) pick(hits[0].id);
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder={`${value} · search customers`}
          aria-label="Search a demo customer"
          className="w-full bg-transparent text-sm outline-none placeholder:text-neutral-500"
        />
      </label>
      {open && (
        <ul className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-xl border border-neutral-200 bg-white py-1 shadow-lg" role="listbox">
          {hits.length === 0 ? (
            <li className="px-3 py-2 text-sm text-neutral-500">No demo customer matches.</li>
          ) : (
            hits.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={c.id === value}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(c.id)}
                  className={`flex w-full items-baseline gap-2 px-3 py-1.5 text-left text-sm hover:bg-neutral-50 ${c.id === value ? "bg-accent-50" : ""}`}
                >
                  <span className="font-mono text-[12px] text-neutral-500">{c.id}</span>
                  <span className="min-w-0 truncate text-neutral-900">{c.case}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

/** A count in the snapshot strip; a status always comes with an icon as well as a colour. */
function Pill({ icon: Icon, accent = false, children }: { icon?: LucideIcon; accent?: boolean; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-medium ${
        accent ? "border-accent-200 bg-accent-50 text-accent-700" : "border-neutral-200 bg-neutral-100 text-neutral-700"
      }`}
    >
      {Icon && <Icon size={12} aria-hidden />}
      {children}
    </span>
  );
}

export default function KnowledgeBase() {
  const kb = useLoad(loadKnowledgeBase, []);
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<KbNode | null>(null);
  const view = (VIEWS.some((v) => v.id === params.get("view")) ? params.get("view") : "customer") as View;
  const data = kb.status === "ready" ? kb.data : null;
  const ids = useMemo(() => (data ? Object.keys(data.customers) : []), [data]);
  const cid = data && params.get("c") && data.customers[params.get("c")!] ? params.get("c")! : ids[0];

  if (kb.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading the knowledge base…</p>;
  if (kb.status === "error") return <p className="text-red-700">Could not load the knowledge base: {kb.error}</p>;
  if (!data) return null;

  const customer = view === "customer" ? data.customers[cid] : undefined;
  const graph = view === "customer" ? customer!.graph : view === "policy" ? data.policy_graph : data.ontology;
  const go = (patch: Record<string, string>) => {
    setSelected(null);
    setParams((p) => {
      const next = new URLSearchParams(p);
      for (const [k, v] of Object.entries(patch)) next.set(k, v);
      return next;
    });
  };
  const m = data.meta;

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Knowledge Base</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          How the engine gets from a customer's data to a decision, the rules behind every block, and the ontology the graph is built from.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] tabular-nums">
          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 font-mono text-neutral-700" title="Snapshot time">
            <History size={12} className="text-neutral-400" aria-hidden />
            {m.eval_time.replace("T", " ").slice(0, 16)}
          </span>
          <Pill>{m.customers} customers</Pill>
          <Pill icon={Zap} accent>
            {m.act_now} act now
          </Pill>
          <Pill icon={Clock}>{m.waiting} waiting</Pill>
          <Pill icon={MinusCircle}>{m.no_action} no action</Pill>
          <span className="rounded-md border border-neutral-200 bg-white px-2 py-1 font-mono text-[11px] text-neutral-500" title="Rule set version">
            rules {m.rule_set_version}
          </span>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg bg-neutral-100 p-0.5" role="tablist" aria-label="Knowledge base view">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              role="tab"
              aria-selected={view === v.id}
              onClick={() => go({ view: v.id })}
              className={`rounded-md px-3 py-1 text-sm transition-colors duration-150 ${view === v.id ? "bg-white shadow-sm" : "text-neutral-500 hover:text-neutral-800"}`}
            >
              {v.label}
            </button>
          ))}
        </div>
        {view === "customer" && <CustomerSearch kb={data} value={cid} onPick={(id) => go({ view: "customer", c: id })} />}
      </div>

      <div className="grid gap-5 xl:grid-cols-[22rem_minmax(0,1fr)_17rem]">
        <aside className="space-y-3">
          {view === "customer" && customer && <ProfileSummary c={customer} />}
          {view === "customer" && customer && <CustomerFolds c={customer} />}
          {view === "policy" && <PolicyFolds kb={data} />}
          {view === "ontology" && <OntologyFolds graph={graph} />}
        </aside>

        <section className="min-w-0" aria-label="Graph">
          <ZoomCanvas resetKey={`${view}:${cid}`}>
            <LayerGraph
              graph={graph}
              selected={selected?.id ?? null}
              trace={selected ? upstream(graph, selected.id) : null}
              onSelect={(n) => setSelected(n.id === selected?.id ? null : n)}
            />
          </ZoomCanvas>
        </section>

        {/* On a wide screen the panel sits beside the graph; below xl a selected box opens it as a sheet from the
            bottom, so the graph stays in view. */}
        <aside
          className={`rounded-2xl border border-neutral-200 bg-white p-4 xl:sticky xl:top-20 xl:block xl:h-fit xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto ${
            selected ? "fixed inset-x-0 bottom-0 z-40 max-h-[65vh] overflow-y-auto rounded-b-none shadow-2xl xl:inset-auto xl:z-auto xl:rounded-b-2xl xl:shadow-none" : "hidden"
          }`}
          aria-label="Selected box"
        >
          <p className={`${LABEL} mb-2`}>Selected</p>
          {selected ? (
            <NodeInspector node={selected} graph={graph} kb={data} customer={customer} onClose={() => setSelected(null)} />
          ) : (
            <Legend />
          )}
        </aside>
      </div>
    </div>
  );
}
