import { ArrowRight, ChevronRight, Users } from "lucide-react";
import { Link } from "react-router-dom";
import type { IndexRow, Summary } from "../../types/contracts";
import { CHANNEL_LABEL, NOT_ENOUGH } from "../../lib/format";
import { TIER_LABEL, TierChip, type Tier } from "../Chips";
import { type Group, sumOf } from "../groups/model";
import { Num } from "../groups/Num";
import { actionGroupsLink, type ActionStat } from "./model";
import { wholeEur } from "./format";

// Urgency tiers of one action (P1–P5, as on the Worklist; a tier without customers is not listed). A tier opens a sheet with its
// Offer · Channel · Tone groups; each of those leads to /group/:tuple?tier=.

export const TIERS: Tier[] = ["P1", "P2", "P3", "P4", "P5"];

const GRID =
  "grid grid-cols-[minmax(0,1fr)_5.5rem_1rem] items-center gap-x-4 gap-y-1 @lg:grid-cols-[minmax(0,1.6fr)_5rem_7rem_6.5rem_4.5rem_1rem]";
const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";

/** "Newsletter · Sie": the sort key of the group lists (every group of one action shares the offer). */
export function channelLabel(tuple: string): string {
  const [, channel, tone] = tuple.split("|");
  return `${CHANNEL_LABEL[channel] ?? channel} · ${tone === "du" ? "Du" : "Sie"}`;
}

/**
 * Share of the group's customers whose p rests on enough observations (confidence high or medium).
 * Customers without a confidence are left out; null when none has one ("not enough data", never 0%).
 */
export function confidenceRate(rows: IndexRow[]): { pct: number | null; title: string } {
  const n = { high: 0, medium: 0, low: 0 };
  let unknown = 0;
  for (const r of rows) {
    if (r.confidence) n[r.confidence]++;
    else unknown++;
  }
  const known = n.high + n.medium + n.low;
  const parts = [`${n.high} high`, `${n.medium} medium`, `${n.low} low`];
  if (unknown) parts.push(`${unknown} unknown`);
  return {
    pct: known ? Math.round(((n.high + n.medium) / known) * 100) : null,
    title: `Confidence (high or medium) · ${parts.join(" · ")}`,
  };
}

export function ConfidenceRate({ rows, className = "" }: { rows: IndexRow[]; className?: string }) {
  const c = confidenceRate(rows);
  return (
    <span title={c.title} className={`tabular-nums ${c.pct === null ? "italic text-neutral-400" : ""} ${className}`}>
      {c.pct === null ? NOT_ENOUGH : `${c.pct}%`}
    </span>
  );
}

export interface TierBucket {
  tier: Tier;
  rows: IndexRow[];
  groups: Group[]; // Offer · Channel · Tone groups restricted to this tier, sorted by channel
}

/** The action's sales groups split by urgency tier, P1 to P5 (a tier without customers keeps an empty bucket). */
export function tierBuckets(groups: Group[]): TierBucket[] {
  return TIERS.map((tier) => {
    const sub = groups
      .map((g) => ({ tuple: g.tuple, rows: g.rows.filter((r) => (r.urgency_tier ?? "P5") === tier) }))
      .filter((g) => g.rows.length > 0)
      .sort((a, b) => channelLabel(a.tuple).localeCompare(channelLabel(b.tuple)));
    return { tier, rows: sub.flatMap((g) => g.rows), groups: sub };
  });
}

export default function ActionGroups({
  action,
  groups,
  summary,
  onOpen,
}: {
  action: ActionStat;
  groups: Group[];
  summary: Summary | null;
  onOpen: (tier: Tier) => void;
}) {
  const s = summary ?? undefined;
  return (
    <div className="@container border-t border-neutral-100 bg-neutral-50/60 px-5 py-4" id={`groups-${action.offer}`}>
      <div className="flex justify-end px-3 pb-2">
        <Link
          to={actionGroupsLink(action.offer)}
          className="inline-flex items-center gap-1 rounded text-xs font-medium text-accent-700 transition-colors duration-150 hover:text-accent-600"
        >
          Open in Groups
          <ArrowRight size={12} aria-hidden />
        </Link>
      </div>
      {groups.length === 0 ? (
        <p className="px-3 py-2 text-sm text-neutral-500">Nobody left to send: every customer of this action was sent before or removed.</p>
      ) : (
        <>
          <div className={`${GRID} px-3 pb-2`}>
            <span className={LABEL}>Urgency</span>
            <span className={`${LABEL} hidden @lg:block`}>Customers</span>
            <span className={`${LABEL} text-right @lg:text-left`}>Σ ΔCLV</span>
            <span className={`${LABEL} hidden @lg:block`}>Confidence</span>
            <span className={`${LABEL} hidden @lg:block`}>Groups</span>
            <span />
          </div>
          <ul className="divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-white">
            {/* Only the tiers with customers to send. */}
            {tierBuckets(groups)
              .filter((b) => b.rows.length > 0)
              .map((b) => {
                const name = (
                  <span className="flex min-w-0 items-center gap-2">
                    <TierChip tier={b.tier} />
                    <span className="min-w-0 break-words">{TIER_LABEL[b.tier]}</span>
                  </span>
                );
                const delta = sumOf(b.rows, "delta_clv");
                return (
                  <li key={b.tier}>
                    <button
                      type="button"
                      data-overview-tier={b.tier}
                      onClick={() => onOpen(b.tier)}
                      title={`Show the ${b.groups.length} group${b.groups.length === 1 ? "" : "s"} of ${b.tier}`}
                      className={`${GRID} group w-full px-3 py-2.5 text-left text-sm text-neutral-900 transition-colors duration-150 hover:bg-neutral-50 focus-visible:-outline-offset-2!`}
                    >
                      <span className="min-w-0">
                        {name}
                        <span className="mt-1 inline-flex items-center gap-1 text-xs tabular-nums text-neutral-500 @lg:hidden">
                          <Users size={12} aria-hidden />
                          {b.rows.length} · <ConfidenceRate rows={b.rows} /> confidence · {b.groups.length} groups
                        </span>
                      </span>
                      <span className="hidden items-center gap-1.5 tabular-nums @lg:inline-flex">
                        <Users size={14} className="text-neutral-400" aria-hidden />
                        {b.rows.length}
                      </span>
                      <span className="min-w-0 text-right @lg:text-left">
                        <Num col="delta_clv" value={delta.total} format={wholeEur} summary={s} className="font-semibold" />
                      </span>
                      <ConfidenceRate rows={b.rows} className="hidden @lg:block" />
                      <span className="hidden tabular-nums @lg:block">{b.groups.length}</span>
                      <ChevronRight
                        size={14}
                        className="col-start-3 row-start-1 text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5 @lg:col-start-auto @lg:row-start-auto"
                        aria-hidden
                      />
                    </button>
                  </li>
                );
              })}
          </ul>
        </>
      )}
    </div>
  );
}
