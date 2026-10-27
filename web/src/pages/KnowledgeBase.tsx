import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, Search } from "lucide-react";
import LayerGraph from "../components/kb/LayerGraph";
import ZoomCanvas from "../components/kb/ZoomCanvas";
import { OFFER_NAME } from "../components/worklist/model";
import { channelLabel, toneLabel } from "../components/nba/ui";
import { mockName } from "../lib/customerMock";
import { useLoad } from "../lib/data";
import { eur, pct, signedEur } from "../lib/format";
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

/** A collapsible section of the left column (closed sections keep the column short). */
function Fold({ title, open = false, children }: { title: string; open?: boolean; children: ReactNode }) {
  return (
    <details open={open} className="group rounded-2xl border border-neutral-200 bg-white">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className={LABEL}>{title}</span>
        <ChevronDown size={14} className="text-neutral-400 transition-transform duration-150 group-open:rotate-180" aria-hidden />
      </summary>
      <div className="border-t border-neutral-100 px-4 py-3 text-sm text-neutral-700">{children}</div>
    </details>
  );
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2 py-0.5">
      <dt className="text-neutral-500">{k}</dt>
      <dd className="min-w-0 break-words text-neutral-900">{children}</dd>
    </div>
  );
}

const plain = (s: string) => s.replace(/\s*\[[A-Z]+[-\d]*\d\]/g, "");

function tupleText(tuple: string): string {
  if (!tuple || tuple === "NO_ACTION") return "No action";
  const [offer, channel, tone] = tuple.split("|");
  return `${OFFER_NAME[offer] ?? offer} · ${channelLabel(channel)} · ${toneLabel(tone)}`;
}

function resultChip(result: string) {
  const cls = result === "block" ? "bg-red-50 text-red-700 ring-red-200" : "bg-neutral-100 text-neutral-700 ring-neutral-200";
  return <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${cls}`}>{result}</span>;
}

function CustomerFolds({ c }: { c: KbCustomer }) {
  const v = c.chosen.valuation;
  const h = c.headline;
  return (
    <>
      <Fold title="Decision" open>
        <p className="font-medium text-neutral-900">{tupleText(c.chosen.tuple)}</p>
        <p className="mt-1 text-neutral-600">{plain(c.chosen.reason)}</p>
        <dl className="mt-2 text-[13px]">
          {c.chosen.send_at && <Row k="send">{c.chosen.send_at}</Row>}
          {c.chosen.until && <Row k="waits until">{c.chosen.until.replace("T", " ")}</Row>}
          {c.chosen.subject && <Row k="subject">{c.chosen.subject}</Row>}
        </dl>
      </Fold>
      <Fold title="Expected gain" open>
        {v ? (
          <>
            <p className="rounded-lg bg-neutral-50 px-3 py-2 font-mono text-[12px] text-neutral-700">
              ΔCLV = p·(CLV<sub>buy</sub> − CLV<sub>now</sub>) + (1−p)·(CLV<sub>no</sub> − CLV<sub>now</sub>) − cost
            </p>
            <dl className="mt-2 text-[13px]">
              <Row k="p (agree)">{pct(v.p)} · {v.confidence} confidence</Row>
              <Row k="CLV now">{eur(v.clv_now)}</Row>
              <Row k="CLV if yes">{eur(v.clv_accept)}</Row>
              <Row k="CLV if no">{eur(v.clv_reject)}</Row>
              <Row k="contact cost">{eur(v.cost, true)}</Row>
              <Row k="ΔCLV">
                <span className="font-semibold text-accent-700">{signedEur(v.dclv)}</span>
              </Row>
              <Row k="evidence">
                {v.conv}/{v.n} bought · {v.p_level.replace(/_/g, " ")}
              </Row>
            </dl>
          </>
        ) : (
          <p className="text-neutral-500">No action, so no expected gain.</p>
        )}
      </Fold>
      <Fold title="Customer">
        <dl className="text-[13px]">
          <Row k="segment">{h.archetype}</Row>
          <Row k="urgency">{h.urgency}</Row>
          <Row k="why">{h.urgency_reasons.map(plain).join("; ") || "–"}</Row>
          <Row k="CLV">{h.clv == null ? "not enough data" : eur(h.clv)}</Row>
          <Row k="churn 12 m">{h.churn == null ? "not enough data" : pct(h.churn, 0)}</Row>
          <Row k="flags">{h.flags.length ? h.flags.map((f) => f.replace(/_/g, " ")).join(", ") : "none"}</Row>
          <Row k="address as">{toneLabel(h.tone)}</Row>
          <Row k="profiling">{h.profiled ? "granted" : "no consent"}</Row>
        </dl>
      </Fold>
      <Fold title="Rules">
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
      <Fold title="Explanation path">
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
          placeholder={`${value} · search the ${all.length} demo customers`}
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

function Selected({ node, customer }: { node: KbNode | null; customer?: KbCustomer }) {
  if (!node)
    return (
      <div className="space-y-3 text-sm text-neutral-600">
        <p>Select a box in the tree to see the row or rule behind it.</p>
        <ul className="space-y-1.5 text-[13px]">
          <li className="flex items-center gap-2"><span className="h-0.5 w-6 bg-accent-600" /> chosen path</li>
          <li className="flex items-center gap-2"><span className="h-0.5 w-6 bg-neutral-300" /> allowed alternative</li>
          <li className="flex items-center gap-2"><span className="w-6 border-t border-dashed border-neutral-400" /> waiting (a rule holds it back)</li>
          <li className="flex items-center gap-2"><span className="w-6 border-t border-dashed border-red-400" /> blocked by a rule</li>
        </ul>
      </div>
    );
  const facts = customer?.evidence.find((e) => e.id === node.id)?.facts;
  const detail = Object.entries({ ...(node.detail ?? {}), ...(facts ?? {}) }).filter(([, v]) => v !== null && v !== undefined && v !== "");
  return (
    <div className="space-y-2 text-sm">
      <p className="font-medium text-neutral-900">{node.label}</p>
      {node.sub && <p className="text-neutral-600">{node.sub}</p>}
      <p className="text-[12px] text-neutral-500">
        {node.kind}
        {node.status ? ` · ${node.status}` : node.path ? " · on the chosen path" : ""}
      </p>
      {detail.length > 0 && (
        <dl className="border-t border-neutral-100 pt-2 text-[13px]">
          {detail.map(([k, v]) => (
            <Row key={k} k={k}>
              {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </Row>
          ))}
        </dl>
      )}
    </div>
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
        <p className="mt-2 text-sm tabular-nums text-neutral-500">
          Snapshot {m.eval_time.replace("T", " ").slice(0, 16)} · {m.customers} customers · {m.act_now} act now · {m.waiting} waiting · {m.no_action} no action ·
          rules {m.rule_set_version}
        </p>
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

      <div className="grid gap-5 xl:grid-cols-[19rem_minmax(0,1fr)_17rem]">
        <aside className="space-y-3">
          {view === "customer" && customer && (
            <div className="rounded-2xl border border-neutral-200 bg-white px-4 py-3">
              <p className={LABEL}>Customer</p>
              <p className="mt-1 font-medium text-neutral-900">
                {mockName(customer.id)}{" "}
                <span className="rounded bg-neutral-100 px-1 text-[10px] font-medium uppercase text-neutral-500" title="Demo name: the data has no names">demo</span>
              </p>
              <p className="font-mono text-[12px] text-neutral-500">{customer.id}</p>
              <p className="mt-1 text-[13px] text-neutral-600">{customer.case}</p>
            </div>
          )}
          {view === "customer" && customer && <CustomerFolds c={customer} />}
          {view === "policy" && <PolicyFolds kb={data} />}
          {view === "ontology" && <OntologyFolds graph={graph} />}
        </aside>

        <section className="min-w-0" aria-label="Graph">
          <ZoomCanvas resetKey={`${view}:${cid}`}>
            <LayerGraph graph={graph} selected={selected?.id ?? null} onSelect={(n) => setSelected(n.id === selected?.id ? null : n)} />
          </ZoomCanvas>
        </section>

        <aside className="h-fit rounded-2xl border border-neutral-200 bg-white p-4 xl:sticky xl:top-20">
          <p className={`${LABEL} mb-2`}>Selected</p>
          <Selected node={selected} customer={customer} />
        </aside>
      </div>
    </div>
  );
}
