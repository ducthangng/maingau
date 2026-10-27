import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Users, X } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Decision } from "../../lib/decisions";
import { tupleLabel } from "../../lib/format";
import { TIER_LABEL, TierChip } from "../Chips";
import { alreadyApproved, gateCounts, plural, sumOf } from "../groups/model";
import { Num } from "../groups/Num";
import { ConfidenceRate, type TierBucket } from "./ActionGroups";
import { groupLink, type ActionStat } from "./model";
import { wholeEur } from "./format";

// One urgency tier of one action: its Offer · Channel · Tone groups, each leading to /group/:tuple?tier=.
// Slides in from the right like the approval sheet of the Groups page.

const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const GRID = "grid grid-cols-[minmax(0,1fr)_6rem_1rem] items-center gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1.6fr)_4.5rem_6.5rem_5.5rem_1rem]";

export default function TierSheet({
  action,
  bucket,
  summary,
  latest,
  onClose,
}: {
  action: ActionStat;
  bucket: TierBucket;
  summary: Summary | null;
  latest: Map<string, Decision>;
  onClose: () => void;
}) {
  const [shown, setShown] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const closing = useRef(false);
  const s = summary ?? undefined;

  // Slide in; lock page scroll; focus the sheet and restore focus on close.
  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => setShown(true));
    closeRef.current?.focus();
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      prevFocus?.focus?.();
    };
  }, []);

  const requestClose = () => {
    if (closing.current) return;
    closing.current = true;
    setShown(false);
    window.setTimeout(onClose, 180);
  };

  // Esc closes (and is consumed, so the Overview keeps the action open); Tab stays inside the sheet.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const delta = sumOf(bucket.rows, "delta_clv");

  return (
    <div className="fixed inset-0 z-40" role="presentation">
      <div
        aria-hidden
        onClick={requestClose}
        className={`absolute inset-0 bg-neutral-900/25 transition-opacity duration-200 motion-reduce:transition-none ${shown ? "opacity-100" : "opacity-0"}`}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tier-sheet-title"
        className={`absolute inset-y-0 right-0 flex w-full max-w-[640px] flex-col bg-white shadow-2xl ring-1 ring-neutral-200 transition-transform duration-200 ease-out motion-reduce:transition-none ${
          shown ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 px-6 py-4">
          <div className="min-w-0">
            <div className={LABEL}>{action.name} · groups</div>
            <h2 id="tier-sheet-title" className="mt-1 flex items-center gap-2 text-lg font-semibold tracking-tight text-neutral-900">
              <TierChip tier={bucket.tier} />
              {TIER_LABEL[bucket.tier]}
            </h2>
            <p className="text-sm tabular-nums text-neutral-500">
              {plural(bucket.rows.length, "customer")} · {plural(bucket.groups.length, "group")} ·{" "}
              <Num col="delta_clv" value={delta.total} format={wholeEur} summary={s} /> expected ΔCLV
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={requestClose}
            aria-label="Close groups"
            className="rounded-lg p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className={`${GRID} px-3 pb-2`}>
            <span className={LABEL}>Offer · Channel · Tone</span>
            <span className={`${LABEL} hidden sm:block`}>Customers</span>
            <span className={`${LABEL} text-right sm:text-left`}>Σ ΔCLV</span>
            <span className={`${LABEL} hidden sm:block`}>Confidence</span>
            <span />
          </div>
          <ul className="divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-white">
            {bucket.groups.map((g) => {
              const sum = sumOf(g.rows, "delta_clv");
              const gates = gateCounts(g.rows, latest, g.tuple);
              const approved = g.rows.filter((r) => alreadyApproved(latest.get(r.customer_id), g.tuple)).length;
              return (
                <li key={g.tuple}>
                  <Link
                    to={groupLink(g.tuple, bucket.tier)}
                    data-tier-group={g.tuple}
                    title={`Show the ${plural(g.rows.length, "customer")} of this group`}
                    className={`${GRID} group px-3 py-2.5 text-sm text-neutral-900 transition-colors duration-150 hover:bg-neutral-50 focus-visible:-outline-offset-2!`}
                  >
                    <span className="min-w-0">
                      <span className="block break-words font-medium">{tupleLabel(g.tuple)}</span>
                      <span className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-neutral-500">
                        <span className="inline-flex items-center gap-1 tabular-nums sm:hidden">
                          <Users size={12} aria-hidden />
                          {g.rows.length} · <ConfidenceRate rows={g.rows} />
                        </span>
                        <span>{gates.ready} ready</span>
                        {gates.review > 0 && <span>{gates.review} second look</span>}
                        {gates.blocked > 0 && <span className="text-red-700">{gates.blocked} do no harm</span>}
                        {approved > 0 && <span className="text-accent-700">{approved} approved</span>}
                      </span>
                    </span>
                    <span className="hidden items-center gap-1.5 tabular-nums sm:inline-flex">
                      <Users size={14} className="text-neutral-400" aria-hidden />
                      {g.rows.length}
                    </span>
                    <span className="min-w-0 text-right sm:text-left">
                      <Num col="delta_clv" value={sum.total} format={wholeEur} summary={s} className="font-semibold" />
                    </span>
                    <ConfidenceRate rows={g.rows} className="hidden sm:block" />
                    <ChevronRight
                      size={14}
                      className="col-start-3 row-start-1 text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5 sm:col-start-auto sm:row-start-auto"
                      aria-hidden
                    />
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
