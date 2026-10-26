import { Link } from "react-router-dom";
import { ArrowUpRight, Headset } from "lucide-react";
import type { IndexRow, Summary } from "../../types/contracts";
import { pct, signedEur, text, tupleLabel } from "../../lib/format";
import { ConfidenceDot, FlagBadge, TierChip } from "../Chips";
import { Num } from "./Num";

// Service tuples (P-SV-01 / service mode) are never bulk-approved as sales (prompts/agent-cards.md §1.3 service mode, §1.4 #3).
export default function ServiceList({ rows, summary, highlight }: { rows: IndexRow[]; summary: Summary | undefined; highlight: boolean }) {
  return (
    <section
      id="service-list"
      aria-labelledby="service-title"
      className={`scroll-mt-20 rounded-xl border bg-white p-5 transition-colors duration-500 ${highlight ? "border-accent-500 ring-2 ring-accent-100" : "border-neutral-200"}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="service-title" className="inline-flex items-center gap-2 text-[15px] font-semibold text-neutral-900">
          <Headset className="size-4 text-neutral-500" aria-hidden />
          Service — handle individually
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600 tabular-nums">{rows.length}</span>
        </h2>
        <p className="text-xs text-neutral-500">Resolve first. These are never bulk-approved as a sales action.</p>
      </div>

      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No customer needs service handling in this snapshot.</p>
      ) : (
        <ul className="mt-3 divide-y divide-neutral-100">
          {rows.map((r) => (
            <li key={r.customer_id} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-2.5">
              <TierChip tier={r.urgency_tier} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-sm font-medium text-neutral-900">{r.customer_id}</span>
                  <span className="text-xs text-neutral-500">{tupleLabel(r.chosen_tuple)}</span>
                  {(r.flags ?? []).map((f) => (
                    <FlagBadge key={f} id={f} />
                  ))}
                </div>
                <p className="mt-0.5 truncate text-xs text-neutral-500" title={r.top_reason ?? undefined}>
                  {text(r.top_reason)}
                </p>
              </div>
              <div className="text-right">
                <div className="text-sm">
                  <Num col="delta_clv" value={r.delta_clv} format={signedEur} summary={summary} />
                </div>
                <div className="mt-0.5 flex items-center justify-end gap-2 text-xs text-neutral-500">
                  <span>
                    p <Num col="p_accept" value={r.p_accept} format={(v) => pct(v)} summary={summary} />
                  </span>
                  <ConfidenceDot confidence={r.confidence} />
                </div>
              </div>
              <Link
                to={`/customer/${r.customer_id}`}
                className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 px-2.5 py-1.5 text-xs font-medium text-neutral-700 transition-colors duration-150 hover:border-accent-500 hover:text-accent-700"
              >
                Open
                <ArrowUpRight className="size-3.5" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
