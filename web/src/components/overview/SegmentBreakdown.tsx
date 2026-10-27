import { ArrowRight, EyeOff } from "lucide-react";
import { Link } from "react-router-dom";
import type { Summary } from "../../types/contracts";
import { Sourced } from "../Source";
import { ValueBar } from "../viz";
import { asOf, colSrc } from "../worklist/model";
import { NOT_PERSONALISED, actionGroupsLink, segmentLink, type ActionStat, type SegmentStat } from "./model";
import { NOT_ENOUGH } from "../../lib/format";
import { wholeEur } from "./format";

// Segment breakdown of one action (prompts/ui-overview.md §5): A0–A5 and Not personalised, each
// row leading to the Groups page filtered to exactly those customers.

// Sized by the panel (@container), not the viewport. From @lg (32rem) up: one row per segment, four
// columns (segment · customers · ΔCLV · arrow), as before. Below @lg (a phone): two lines per segment,
// the name across the top next to the arrow, then customers and ΔCLV side by side with their bars.
const GRID =
  "grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1rem] items-center gap-x-4 gap-y-1.5 @lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_1rem] @lg:gap-y-0";
// The name takes the whole first line below @lg; the last cell (arrow) sits at the end of that line.
const NAME_CELL = "col-span-2 @lg:col-span-1";
const END_CELL = "col-start-3 row-start-1 @lg:col-start-auto @lg:row-start-auto";
const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const NP_HINT = "No profiling consent: the engine uses general offers without need signals";

function SegmentName({ s }: { s: SegmentStat }) {
  return (
    <span className={`${NAME_CELL} flex min-w-0 items-center gap-2`} title={s.key === NOT_PERSONALISED ? NP_HINT : undefined}>
      <span className="inline-flex shrink-0 items-center rounded-md bg-white px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-neutral-600 ring-1 ring-inset ring-neutral-200">
        {s.key === NOT_PERSONALISED ? <EyeOff size={12} aria-hidden /> : s.key}
      </span>
      <span className="min-w-0 break-words md:truncate">{s.name}</span>
    </span>
  );
}

export default function SegmentBreakdown({ action, summary }: { action: ActionStat; summary: Summary | null }) {
  const valueSrc = colSrc(summary, "delta_clv");
  const segSrc = colSrc(summary, "archetype");
  return (
    <div className="@container border-t border-neutral-100 bg-neutral-50/60 px-5 py-4" id={`segments-${action.offer}`}>
      <div className="flex justify-end px-3 pb-2">
        <Link
          to={actionGroupsLink(action.offer)}
          className="inline-flex items-center gap-1 rounded text-xs font-medium text-accent-700 transition-colors duration-150 hover:text-accent-600"
        >
          All segments in Groups
          <ArrowRight size={12} aria-hidden />
        </Link>
      </div>
      {/* Below @lg the "Segment" label is dropped, so the other two sit over the customers and ΔCLV line. */}
      <div className={`${GRID} px-3 pb-2`}>
        <span className={`${LABEL} hidden @lg:block`}>Segment</span>
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
                title={`Open these ${s.customers} customers in Groups`}
                className={`${GRID} group rounded-lg px-3 py-2 text-sm text-neutral-900 transition-colors duration-150 hover:bg-white focus-visible:-outline-offset-2!`}
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
                    <span className="tabular-nums">{s.valued ? `${wholeEur(s.total)} · ${s.totalPct}%` : NOT_ENOUGH}</span>
                  </Sourced>
                  {s.valued > 0 && <ValueBar value={s.totalPct} max={100} className="mt-1" />}
                </span>
                <ArrowRight
                  size={14}
                  className={`${END_CELL} text-neutral-400 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100`}
                  aria-hidden
                />
              </Link>
            </li>
          ) : (
            <li key={s.key} className={`${GRID} rounded-lg px-3 py-2 text-sm text-neutral-400`} aria-label={`${s.name}: no customers`}>
              <SegmentName s={s} />
              <span>–</span>
              <span>–</span>
              <span className={END_CELL} />
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
