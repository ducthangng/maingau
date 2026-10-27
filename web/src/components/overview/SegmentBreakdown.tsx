import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { Summary } from "../../types/contracts";
import { Sourced } from "../Source";
import { ValueBar } from "../viz";
import { asOf, colSrc } from "../worklist/model";
import { NOT_PERSONALISED, segmentLink, type ActionStat, type SegmentStat } from "./model";
import { wholeEur } from "./format";

// Segment breakdown of one action (prompts/ui-overview.md §5): A0–A5 and Not personalised, each
// row leading to the Worklist filtered to exactly those customers.

const GRID = "grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_1rem] items-center gap-x-4";
const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const NP_HINT = "No profiling consent: the engine uses general offers without need signals";

function SegmentName({ s }: { s: SegmentStat }) {
  return (
    <span className="flex min-w-0 items-center gap-2" title={s.key === NOT_PERSONALISED ? NP_HINT : undefined}>
      <span className="shrink-0 rounded-md bg-white px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-neutral-600 ring-1 ring-inset ring-neutral-200">
        {s.key}
      </span>
      <span className="min-w-0 break-words md:truncate">{s.name}</span>
    </span>
  );
}

export default function SegmentBreakdown({ action, summary }: { action: ActionStat; summary: Summary | null }) {
  const valueSrc = colSrc(summary, "delta_clv");
  const segSrc = colSrc(summary, "archetype");
  return (
    <div className="border-t border-neutral-100 bg-neutral-50/60 px-5 py-4" id={`segments-${action.offer}`}>
      <div className={`${GRID} px-3 pb-2`}>
        <span className={LABEL}>Segment</span>
        <span className={LABEL}>Customers</span>
        <span className={LABEL}>Expected ΔCLV</span>
        <span />
      </div>
      <ul className="space-y-0.5">
        {action.segments.map((s) =>
          s.customers > 0 ? (
            <li key={s.key}>
              <Link
                to={segmentLink(action.offer, s.key)}
                title={`Open these ${s.customers} customers in the Worklist`}
                className={`${GRID} group rounded-lg px-3 py-2 text-sm text-neutral-900 transition-colors duration-150 hover:bg-white`}
              >
                <SegmentName s={s} />
                <span className="min-w-0">
                  <Sourced src={segSrc} updatedAt={asOf(summary, segSrc)} sources={summary?.sources}>
                    <span className="tabular-nums">
                      {s.customers} · {s.customersPct}%
                    </span>
                  </Sourced>
                  <ValueBar value={s.customersPct} max={100} className="mt-1" />
                </span>
                <span className="min-w-0">
                  <Sourced src={valueSrc} updatedAt={asOf(summary, valueSrc)} sources={summary?.sources}>
                    <span className="tabular-nums">
                      {wholeEur(s.total)} · {s.totalPct}%
                    </span>
                  </Sourced>
                  <ValueBar value={s.totalPct} max={100} className="mt-1" />
                </span>
                <ArrowRight size={14} className="text-neutral-400 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden />
              </Link>
            </li>
          ) : (
            <li key={s.key} className={`${GRID} rounded-lg px-3 py-2 text-sm text-neutral-400`} aria-label={`${s.name}: no customers`}>
              <SegmentName s={s} />
              <span>–</span>
              <span>–</span>
              <span />
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
