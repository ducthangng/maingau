import { useState, type ReactNode } from "react";
import { ArrowRight, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import { OFFER_NAME } from "../worklist/model";
import { channelLabel } from "../nba/ui";
import { mockName } from "../../lib/customerMock";
import { useLoad } from "../../lib/data";
import { eur, pct } from "../../lib/format";
import { loadLearnImpact, type LearnChange, type LearnDecision } from "../../lib/kb";

// Knowledge Base "Learning": what the feedback loop learned and which decisions it changed (nba/learn/impact.py,
// GET /api/learn/impact). Three runs of the engine: nothing learned → + track record k and look-alike lift →
// + customer memory. Each changed decision names the value that moved.

const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const CAUSE: Record<LearnChange["cause"], { label: string; cls: string }> = {
  evidence: { label: "Learned chance (k, lift)", cls: "bg-accent-50 text-accent-700 ring-accent-100" },
  memory: { label: "Customer memory", cls: "bg-neutral-100 text-neutral-700 ring-neutral-200" },
};

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

const money = (v: number | null | undefined) => (v == null ? "–" : `€${v.toFixed(2)}`);
const signed = (v: number) => `${v >= 0 ? "+" : "−"}€${Math.abs(v).toFixed(2)}`;

function action(t: string): string {
  if (!t || t === "NO_ACTION") return "No action";
  const [offer, channel] = t.split("|");
  return `${OFFER_NAME[offer] ?? offer} · ${channelLabel(channel)}`;
}

function Step({ k, v, note }: { k: string; v: ReactNode; note?: string }) {
  return (
    <li className="rounded-lg border border-neutral-200 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wider text-neutral-500">{k}</p>
      <p className="text-sm font-medium tabular-nums text-neutral-900">{v}</p>
      {note && <p className="text-[12px] text-neutral-500">{note}</p>}
    </li>
  );
}

/** The selected change as a chain: before → the learned value → after (ΔCLV moves by Δp × (CLV_buy − CLV_no)). */
function Chain({ c }: { c: LearnChange }) {
  const b = c.before;
  const now = c.cause === "evidence" ? (c.before_now ?? {}) : {};
  const winner = c.winner_before ?? null;
  const showWinner = c.cause === "evidence" && winner && now.p != null && b.p != null && Math.abs(now.p - b.p) < 1e-6;
  const moving: Partial<LearnDecision> = showWinner ? (winner as Partial<LearnDecision>) : b;
  const moved: Partial<LearnDecision> = showWinner ? c.after : now;
  const dp = moving.p != null && moved.p != null ? moved.p - moving.p : null;
  const spread = moving.clv_buy != null && moving.clv_no != null ? moving.clv_buy - moving.clv_no : null;
  return (
    <ol className="space-y-2">
      <Step k="Before learning" v={action(b.tuple)} note={b.delta_clv != null ? `ΔCLV ${money(b.delta_clv)} · chance ${b.p != null ? pct(b.p) : "–"}` : undefined} />
      {c.cause === "evidence" ? (
        <Step
          k={showWinner ? `What was learned · ${action(c.after.tuple)}` : "What was learned"}
          v={
            moved.k != null && Math.abs(moved.k - 1) >= 0.01
              ? `track record k = ${moved.k.toFixed(2)}`
              : moved.lift != null
                ? `look-alike lift ×${moved.lift.toFixed(2)}`
                : "a rule threshold now stops it"
          }
          note={
            dp != null
              ? `chance ${pct(moving.p ?? null)} → ${pct(moved.p ?? null)}; ΔCLV ${money(moving.delta_clv)} → ${money(moved.delta_clv)}` +
                (spread != null ? ` (Δp × (CLV_buy − CLV_no) = ${signed(dp * spread)})` : "")
              : undefined
          }
        />
      ) : (
        <Step k="What was learned" v="customer memory from feedback" note={c.sentence.split(";")[0]} />
      )}
      <Step k="After learning" v={action(c.after.tuple)} note={c.after.delta_clv != null ? `ΔCLV ${money(c.after.delta_clv)}${c.after.waits_until ? ` · waits until ${c.after.waits_until.slice(0, 10)}` : ""}` : c.after.waits_until ? `waits until ${c.after.waits_until.slice(0, 10)}` : undefined} />
    </ol>
  );
}

export default function LearningView({ demo }: { demo: Set<string> }) {
  const data = useLoad(loadLearnImpact, []);
  const [cause, setCause] = useState<LearnChange["cause"] | "all">("all");
  const [sel, setSel] = useState<string | null>(null);

  if (data.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading what the system learned…</p>;
  if (data.status === "error") return <p className="text-red-700">Could not load the learning impact: {data.error}</p>;
  const d = data.data;
  const shown = d.changes.filter((c) => cause === "all" || c.cause === cause);
  const picked = d.changes.find((c) => `${c.customer_id}:${c.cause}` === sel) ?? shown[0] ?? null;
  const t = d.summary.delta_clv;

  return (
    <div className="grid gap-5 xl:grid-cols-[19rem_minmax(0,1fr)_19rem]">
      <aside className="space-y-3">
        <Fold title="What learning changes" open>
          <p className="rounded-lg bg-neutral-50 px-3 py-2 font-mono text-[12px] text-neutral-700">{d.formula}</p>
          <dl className="mt-2 space-y-1 text-[13px]">
            <div className="flex justify-between"><dt className="text-neutral-500">decisions changed</dt><dd className="font-medium tabular-nums">{d.summary.changed} of {d.summary.customers}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">· by learned chance</dt><dd className="tabular-nums">{d.summary.by_cause.evidence ?? 0}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">· by customer memory</dt><dd className="tabular-nums">{d.summary.by_cause.memory ?? 0}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">Σ ΔCLV nothing learned</dt><dd className="tabular-nums">{eur(t.baseline)}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">+ k and lift</dt><dd className="tabular-nums">{eur(t.evidence)}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">+ customer memory</dt><dd className="font-medium tabular-nums text-accent-700">{eur(t.learned)}</dd></div>
          </dl>
        </Fold>
        <Fold title="Track record k (offer · channel · tone)" open>
          <p className="mb-2 text-[12px] text-neutral-500">k = (bought + 5) / (expected + 5); p × k. Below 1: sold less than forecast.</p>
          <table className="w-full text-[12.5px] tabular-nums">
            <thead>
              <tr className="text-left text-[11px] text-neutral-500"><th className="font-medium">group</th><th className="whitespace-nowrap pl-2 text-right font-medium">bought / exp.</th><th className="pl-3 text-right font-medium">k</th></tr>
            </thead>
            <tbody>
              {d.k.map((r) => (
                <tr key={`${r.offer}|${r.channel}|${r.tone}`} className="border-t border-neutral-100">
                  <td className="py-1 pr-2">{OFFER_NAME[r.offer] ?? r.offer} · {channelLabel(r.channel)} · {r.tone === "du" ? "Du" : "Sie"}</td>
                  <td className="whitespace-nowrap py-1 pl-2 text-right text-neutral-600">{r.bought} / {r.expected}</td>
                  <td className={`py-1 pl-3 text-right font-medium ${r.k < 1 ? "text-red-700" : "text-accent-700"}`}>{r.k.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Fold>
        <Fold title="Customer memory">
          <p>{d.memory.entries} entries from feedback, {d.memory.active} active now.</p>
          <ul className="mt-1 text-[13px] text-neutral-600">
            {Object.entries(d.memory.by_kind).map(([k, n]) => (
              <li key={k}>{k.replace(/_/g, " ")}: {n}</li>
            ))}
          </ul>
        </Fold>
        <Fold title="Look-alike lift">
          {d.lookalike.active ? (
            <ul className="space-y-1 text-[13px]">
              {d.lookalike.offers.map((o) => (
                <li key={o.offer}>
                  <span className="text-neutral-900">{o.name}</span>{" "}
                  <span className="text-neutral-500">· {o.buyers}/{o.recipients} bought · {o.more_likely} more likely, {o.less_likely} less</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-neutral-500">Not active.</p>
          )}
        </Fold>
      </aside>

      <section className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {(["all", "evidence", "memory"] as const).map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCause(c)}
              className={`rounded-full px-3 py-1 text-sm transition-colors duration-150 ${cause === c ? "bg-accent-600 text-white" : "bg-white text-neutral-600 ring-1 ring-neutral-200 hover:bg-neutral-50"}`}
            >
              {c === "all" ? `All ${d.changes.length}` : `${CAUSE[c].label} ${d.changes.filter((x) => x.cause === c).length}`}
            </button>
          ))}
        </div>
        <ul className="space-y-2">
          {shown.map((c) => {
            const key = `${c.customer_id}:${c.cause}`;
            const on = picked && `${picked.customer_id}:${picked.cause}` === key;
            return (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => setSel(key)}
                  className={`w-full rounded-2xl border bg-white px-4 py-3 text-left transition-colors duration-150 hover:bg-neutral-50 ${on ? "border-accent-600 ring-1 ring-inset ring-accent-600" : "border-neutral-200"}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[12px] text-neutral-500">{c.customer_id}</span>
                    <span className="text-sm font-medium text-neutral-900">{mockName(c.customer_id)}</span>
                    <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${CAUSE[c.cause].cls}`}>{CAUSE[c.cause].label}</span>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm">
                    <span className="text-neutral-500 line-through decoration-neutral-300">{action(c.before.tuple)}</span>
                    <ArrowRight size={13} className="text-neutral-400" aria-hidden />
                    <span className="font-medium text-neutral-900">{action(c.after.tuple)}</span>
                    {c.after.waits_until && <span className="text-[12px] text-neutral-500">· waits until {c.after.waits_until.slice(0, 10)}</span>}
                  </p>
                  <p className="mt-1 text-[13px] text-neutral-600">{c.sentence}</p>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <aside className="h-fit space-y-3 rounded-2xl border border-neutral-200 bg-white p-4 xl:sticky xl:top-20">
        <p className={LABEL}>How it changed</p>
        {picked ? (
          <>
            <p className="text-sm font-medium text-neutral-900">
              {mockName(picked.customer_id)} <span className="font-mono text-[12px] font-normal text-neutral-500">{picked.customer_id}</span>
            </p>
            <Chain c={picked} />
            <Link
              to={demo.has(picked.customer_id) ? `/kb?view=customer&c=${picked.customer_id}` : `/customer/${picked.customer_id}`}
              className="inline-flex items-center gap-1 text-[13px] font-medium text-accent-700 hover:text-accent-600"
            >
              {demo.has(picked.customer_id) ? "Open the decision tree" : "Open the customer card"} <ArrowRight size={12} aria-hidden />
            </Link>
          </>
        ) : (
          <p className="text-sm text-neutral-500">Nothing changed.</p>
        )}
      </aside>
    </div>
  );
}
