import type { KeyboardEvent } from "react";
import { ChevronRight, EyeOff, Users } from "lucide-react";
import type { Summary } from "../../types/contracts";
import { NOT_ENOUGH } from "../../lib/format";
import { Sourced, sourceTitle } from "../Source";
import { asOf, colSrc } from "../worklist/model";
import { NO_PROFILING, reasonLine, type ActionStat, type ReasonCount } from "./model";
import { wholeEur } from "./format";
import type { Tier } from "../Chips";
import type { Group } from "../groups/model";
import ActionGroups from "./ActionGroups";

// Action ranking (prompts/ui-overview.md §4): one row per action, its urgency tiers open below.

export const LABEL = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
// Below md: rank · offer (+ customers) · ΔCLV · chevron, reasons on a second line under the offer.
export const GRID =
  "grid grid-cols-[1.5rem_minmax(0,1fr)_5.5rem_1rem] gap-x-4 md:grid-cols-[1.5rem_minmax(0,1.1fr)_7rem_9rem_minmax(0,1.9fr)_1rem]";

function Reason({ r, summary }: { r: ReasonCount; summary: Summary | null }) {
  const line = reasonLine(r, summary);
  if (line.missing) return <p className="text-sm italic text-neutral-400" title={line.title}>{NOT_ENOUGH}</p>;
  return (
    <p title={line.title} className={`flex items-start gap-1.5 text-sm leading-snug ${line.general ? "text-neutral-500" : "text-neutral-800"}`}>
      {line.general && <EyeOff size={14} className="mt-0.5 shrink-0" aria-hidden />}
      <span>{line.text}</span>
    </p>
  );
}

function Reasons({ reasons: all, summary }: { reasons: ReasonCount[]; summary: Summary | null }) {
  if (all.length === 0) return <p className="text-sm italic text-neutral-400">{NOT_ENOUGH}</p>;
  // General offers (no profiling consent) have no reason to show: they get no line of their own.
  const reasons = all.filter((r) => r.key !== NO_PROFILING);
  if (reasons.length === 0) return null;
  const rest = reasons.slice(2);
  return (
    <div className="space-y-1">
      {reasons.slice(0, 2).map((r) => (
        <Reason key={r.key} r={r} summary={summary} />
      ))}
      {rest.length > 0 && (
        <p
          className="text-sm text-neutral-400"
          title={rest
            .map((r) => {
              const l = reasonLine(r, summary);
              return `${l.text} (${l.title})`;
            })
            .join("\n")}
        >
          +{rest.length} other reason{rest.length === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}

function focusRow(from: HTMLElement, step: 1 | -1) {
  const rows = [...document.querySelectorAll<HTMLElement>("[data-overview-row]")];
  rows[rows.indexOf(from) + step]?.focus();
}

export default function ActionTable({
  actions,
  summary,
  groups,
  open,
  onToggle,
  onOpenTier,
}: {
  actions: ActionStat[];
  summary: Summary | null;
  groups: Map<string, Group[]>;
  open: string | null;
  onToggle: (offer: string | null) => void;
  onOpenTier: (tier: Tier) => void;
}) {
  const valueSrc = colSrc(summary, "delta_clv");
  const countSrc = colSrc(summary, "chosen_offer");

  const onKey = (e: KeyboardEvent<HTMLElement>, offer: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onToggle(open === offer ? null : offer);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      focusRow(e.currentTarget, e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      onToggle(null);
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
      <div className={`${GRID} border-b border-neutral-100 px-5 py-3`}>
        <span className={LABEL}>#</span>
        <span className={LABEL}>Action</span>
        <span className={`${LABEL} hidden md:block`}>Customers</span>
        <span className={`${LABEL} text-right md:text-left`}>Expected ΔCLV</span>
        <span className={`${LABEL} hidden md:block`}>Main reason</span>
        <span />
      </div>
      {actions.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-neutral-500">No actions in this snapshot.</p>
      ) : (
        <ol className="divide-y divide-neutral-100">
          {actions.map((a, i) => {
            const isOpen = open === a.offer;
            const customersTitle = [
              a.waiting > 0 ? `${a.waiting} of them wait for a contact limit` : null,
              sourceTitle(countSrc, summary?.eval_time, summary?.sources),
            ]
              .filter(Boolean)
              .join("\n");
            const customers = (
              <span
                title={customersTitle}
                className="inline-flex cursor-help items-center gap-1.5 tabular-nums text-neutral-800 decoration-neutral-300 decoration-dotted underline-offset-4 hover:underline"
              >
                <Users size={14} className="text-neutral-400" aria-hidden />
                {a.customers}
              </span>
            );
            return (
              <li key={a.offer}>
                <div
                  role="button"
                  tabIndex={0}
                  data-overview-row={a.offer}
                  aria-expanded={isOpen}
                  aria-controls={isOpen ? `groups-${a.offer}` : undefined}
                  onClick={() => onToggle(isOpen ? null : a.offer)}
                  onKeyDown={(e) => onKey(e, a.offer)}
                  className={`${GRID} cursor-pointer gap-y-2 px-5 py-4 transition-colors duration-150 hover:bg-neutral-50 focus-visible:-outline-offset-2! ${isOpen ? "bg-neutral-50" : ""}`}
                >
                  <span className="pt-0.5 text-sm tabular-nums text-neutral-400">{i + 1}</span>
                  <div className="min-w-0">
                    <p className="line-clamp-2 break-words text-[15px] font-semibold text-neutral-900" title={a.offer}>
                      {a.name}
                    </p>
                    <p className="mt-0.5 text-sm md:hidden">{customers}</p>
                  </div>
                  <div className="hidden pt-0.5 text-sm md:block">{customers}</div>
                  <div className="min-w-0 text-right md:text-left">
                    <Sourced src={valueSrc} updatedAt={asOf(summary, valueSrc)} sources={summary?.sources}>
                      <span className="text-[15px] font-semibold tabular-nums text-neutral-900">{a.valued ? wholeEur(a.total) : NOT_ENOUGH}</span>
                    </Sourced>
                  </div>
                  <div className="col-span-2 col-start-2 min-w-0 md:col-span-1 md:col-start-auto">
                    <Reasons reasons={a.reasons} summary={summary} />
                  </div>
                  <ChevronRight
                    size={16}
                    className={`col-start-4 row-start-1 mt-0.5 text-neutral-400 transition-transform duration-150 md:col-start-6 ${isOpen ? "rotate-90" : ""}`}
                    aria-hidden
                  />
                </div>
                {isOpen && (
                  <ActionGroups action={a} groups={groups.get(a.offer) ?? []} summary={summary} onOpen={onOpenTier} />
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
