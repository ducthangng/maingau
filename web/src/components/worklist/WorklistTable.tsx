import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { ConfidenceDot, FlagBadge, TierChip } from "../Chips";
import { Sourced } from "../Source";
import type { Decision } from "../../lib/decisions";
import { NOT_ENOUGH, eur, isMissing, pct, signedEur, tupleLabel } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";
import { NO_ACTION, OFFER_NAME, asOf, colSrc, isNoAction, type Group } from "./model";

const MAX_FLAGS = 3;

// Fixed column widths keep the table inside 1280 px; "Top reason" takes what is left.
const COLS: { label: string; width?: number; align?: "right"; title?: string }[] = [
  { label: "Tier", width: 48 },
  { label: "Customer", width: 116 },
  { label: "Archetype", width: 116 },
  { label: "Top reason" },
  { label: "Recommended action", width: 172 },
  { label: "Exp. ΔCLV", width: 92, align: "right", title: "Expected change in customer lifetime value" },
  { label: "Success", width: 64, align: "right", title: "Success probability (p accept)" },
  { label: "Confidence", width: 80 },
  { label: "Flags", width: 128 },
  { label: "CLV", width: 72, align: "right", title: "Customer lifetime value" },
  { label: "Churn", width: 58, align: "right", title: "Churn probability, 12 months" },
  { label: "Status", width: 88 },
];

const STATUS_STYLE: Record<string, string> = {
  proposed: "bg-neutral-100 text-neutral-600",
  approved: "bg-emerald-50 text-emerald-700",
  overridden: "bg-accent-50 text-accent-700",
  rejected: "bg-red-50 text-red-700",
};

function Missing() {
  return <span className="text-xs text-neutral-400 italic">{NOT_ENOUGH}</span>;
}

/** A number from index.json with its source tooltip; "—" when the engine proposed no action. */
function NumCell({
  row,
  field,
  format,
  summary,
  valuation = false,
  className = "",
}: {
  row: IndexRow;
  field: "delta_clv" | "p_accept" | "clv_eur" | "churn";
  format: (v: number) => string;
  summary: Summary | null;
  valuation?: boolean;
  className?: string;
}) {
  const v = row[field];
  if (valuation && isNoAction(row) && isMissing(v)) {
    return (
      <span title="No action proposed, so there is no valuation" className="text-neutral-300">
        —
      </span>
    );
  }
  const src = colSrc(summary, field);
  return (
    <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
      {isMissing(v) ? <Missing /> : <span className={className}>{format(v)}</span>}
    </Sourced>
  );
}

function ActionCell({ row }: { row: IndexRow }) {
  if (isNoAction(row)) {
    const why = row.exclusions?.length ? row.exclusions.join(", ") : row.checklist_failed?.length ? row.checklist_failed.join(", ") : null;
    return (
      <div className="min-w-0">
        <div className="text-neutral-500">No action</div>
        {why && (
          <div className="truncate text-xs text-neutral-400" title={why}>
            {why}
          </div>
        )}
      </div>
    );
  }
  const name = OFFER_NAME[row.chosen_offer] ?? row.chosen_offer;
  return (
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="truncate font-medium text-neutral-900" title={name}>
          {name}
        </span>
        {row.service_mode ? (
          <span className="shrink-0 rounded bg-neutral-100 px-1 text-[11px] text-neutral-600">service</span>
        ) : row.personalised === false ? (
          <span className="shrink-0 rounded bg-neutral-100 px-1 text-[11px] text-neutral-600" title="nicht personalisiert: generic catalog offer">
            generic
          </span>
        ) : null}
      </div>
      <div className="truncate text-xs text-neutral-500" title={tupleLabel(row.chosen_tuple)}>
        {tupleLabel(row.chosen_tuple ?? row.chosen_offer)}
      </div>
    </div>
  );
}

function Flags({ flags }: { flags: string[] }) {
  if (!flags.length) return <span className="text-neutral-300">—</span>;
  const shown = flags.slice(0, MAX_FLAGS);
  const rest = flags.slice(MAX_FLAGS);
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((f) => (
        <FlagBadge key={f} id={f} title={f.replace(/_/g, " ")} />
      ))}
      {rest.length > 0 && (
        <span className="rounded px-1 py-0.5 text-[11px] text-neutral-500" title={rest.map((f) => f.replace(/_/g, " ")).join(", ")}>
          +{rest.length}
        </span>
      )}
    </div>
  );
}

function StatusPill({ decision }: { decision: Decision | undefined }) {
  const status = decision?.action ?? "proposed";
  const title = decision
    ? `${decision.action} by ${decision.reviewer} at ${decision.ts.replace("T", " ").slice(0, 16)}${decision.reason ? `\n${decision.reason}` : ""}`
    : "Proposed by the engine, not yet reviewed";
  return (
    <div title={title}>
      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[status] ?? STATUS_STYLE.proposed}`}>{status}</span>
      {decision?.holdout && <div className="mt-0.5 text-[11px] text-neutral-400">holdout</div>}
    </div>
  );
}

function Row({
  row,
  summary,
  decision,
  highlighted,
  onOpen,
}: {
  row: IndexRow;
  summary: Summary | null;
  decision: Decision | undefined;
  highlighted: boolean;
  onOpen: (id: string) => void;
}) {
  const outlier = row.outlier === true;
  return (
    <tr
      data-row-id={row.customer_id}
      aria-selected={highlighted}
      onClick={() => onOpen(row.customer_id)}
      className={`cursor-pointer border-t border-neutral-100 align-top transition-colors duration-150 ${
        highlighted ? "bg-accent-50" : "hover:bg-neutral-50"
      }`}
    >
      <td className={`border-l-4 py-2.5 pr-2 pl-3 ${outlier ? "border-l-red-500" : "border-l-transparent"}`}>
        <TierChip tier={row.urgency_tier} />
        {!isMissing(row.urgency_score) && (
          <div className="mt-1 text-[11px] text-neutral-400 tabular-nums">
            <Sourced src={colSrc(summary, "urgency_score")} updatedAt={summary?.eval_time} sources={summary?.sources}>
              {row.urgency_score.toFixed(0)}
            </Sourced>
          </div>
        )}
      </td>
      <td className="px-2 py-2.5">
        <Link
          to={`/customer/${row.customer_id}`}
          onClick={(e) => e.stopPropagation()}
          className="font-medium text-neutral-900 tabular-nums hover:text-accent-700 hover:underline"
        >
          {row.customer_id}
        </Link>
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-neutral-500">
          {row.city && (
            <Sourced src={colSrc(summary, "city")} updatedAt={summary?.eval_time} sources={summary?.sources}>
              {row.city}
            </Sourced>
          )}
          {outlier && <span className="rounded bg-red-600 px-1.5 py-px text-[11px] font-medium text-white">Outlier</span>}
        </div>
      </td>
      <td className="px-2 py-2.5">
        {row.archetype ? (
          <div className="min-w-0" title={row.archetype_name ?? row.archetype}>
            <span className="text-xs font-semibold text-neutral-500 tabular-nums">{row.archetype}</span>
            <div className="line-clamp-2 text-[13px] leading-snug text-neutral-700">{row.archetype_name ?? NOT_ENOUGH}</div>
          </div>
        ) : (
          <Missing />
        )}
      </td>
      <td className="px-2 py-2.5">
        {row.top_reason ? (
          <p className="line-clamp-2 text-[13px] leading-snug text-neutral-700" title={row.top_reason}>
            {row.top_reason}
          </p>
        ) : (
          <Missing />
        )}
      </td>
      <td className="px-2 py-2.5 text-[13px]">
        <ActionCell row={row} />
      </td>
      <td className="px-2 py-2.5 text-right tabular-nums">
        <NumCell
          row={row}
          field="delta_clv"
          format={signedEur}
          summary={summary}
          valuation
          className={`font-medium ${(row.delta_clv ?? 0) < 0 ? "text-red-700" : "text-neutral-900"}`}
        />
      </td>
      <td className="px-2 py-2.5 text-right tabular-nums">
        <NumCell row={row} field="p_accept" format={(v) => pct(v)} summary={summary} valuation />
      </td>
      <td className="px-2 py-2.5">
        <ConfidenceDot confidence={row.confidence} />
      </td>
      <td className="px-2 py-2.5">
        <Flags flags={row.flags ?? []} />
      </td>
      <td className="px-2 py-2.5 text-right text-neutral-700 tabular-nums">
        <NumCell row={row} field="clv_eur" format={(v) => eur(v)} summary={summary} />
      </td>
      <td className="px-2 py-2.5 text-right text-neutral-700 tabular-nums">
        <NumCell row={row} field="churn" format={(v) => pct(v, 0)} summary={summary} />
      </td>
      <td className="py-2.5 pr-3 pl-2">
        <StatusPill decision={decision} />
      </td>
    </tr>
  );
}

function GroupHeader({ group, summary }: { group: Group; summary: Summary | null }) {
  const noAction = group.tuple === NO_ACTION;
  const offer = noAction ? null : group.tuple.split("|")[0];
  const src = colSrc(summary, "delta_clv");
  const service = !noAction && group.rows.some((r) => r.service_mode);
  return (
    <tr className="border-t border-neutral-200 bg-neutral-50">
      <td colSpan={COLS.length} className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="font-semibold text-neutral-900">{noAction ? "No action" : (OFFER_NAME[offer ?? ""] ?? offer)}</span>
          {!noAction && <span className="text-neutral-500">{tupleLabel(group.tuple)}</span>}
          <span className="rounded-full bg-white px-2 py-0.5 text-xs text-neutral-600 ring-1 ring-neutral-200 ring-inset tabular-nums">
            {group.rows.length} customer{group.rows.length === 1 ? "" : "s"}
          </span>
          {!noAction && (
            <span className="text-neutral-600 tabular-nums">
              Σ ΔCLV{" "}
              <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
                <span className="font-medium text-neutral-900">{group.sum === null ? NOT_ENOUGH : signedEur(group.sum)}</span>
              </Sourced>
            </span>
          )}
          {group.reviewable ? (
            <Link
              to={`/groups?tuple=${encodeURIComponent(group.tuple)}`}
              className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-medium text-accent-600 transition-colors duration-150 hover:bg-accent-50 hover:text-accent-700"
            >
              Review group <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          ) : (
            <span className="ml-auto text-xs text-neutral-400">
              {noAction ? "nothing to send" : service ? "service mode: handled one by one" : ""}
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function WorklistTable({
  rows,
  groups,
  summary,
  decisions,
  highlightedId,
  onOpen,
  emptyAction,
}: {
  rows: IndexRow[];
  groups: Group[] | null;
  summary: Summary | null;
  decisions: Map<string, Decision>;
  highlightedId: string | null;
  onOpen: (id: string) => void;
  emptyAction: React.ReactNode;
}) {
  const renderRow = (r: IndexRow) => (
    <Row
      key={r.customer_id}
      row={r}
      summary={summary}
      decision={decisions.get(r.customer_id)}
      highlighted={r.customer_id === highlightedId}
      onOpen={onOpen}
    />
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
      <table className="w-full min-w-[1100px] table-fixed border-collapse text-sm">
        <colgroup>
          {COLS.map((c) => (
            <col key={c.label} style={c.width ? { width: c.width } : undefined} />
          ))}
        </colgroup>
        <thead>
          <tr className="text-left text-xs font-medium text-neutral-500">
            {COLS.map((c, i) => (
              <th
                key={c.label}
                scope="col"
                title={c.title}
                className={`py-2.5 font-medium ${i === 0 ? "pr-2 pl-4" : i === COLS.length - 1 ? "pr-3 pl-2" : "px-2"} ${
                  c.align === "right" ? "text-right" : ""
                }`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        {rows.length === 0 ? (
          <tbody>
            <tr className="border-t border-neutral-100">
              <td colSpan={COLS.length} className="px-4 py-12 text-center text-neutral-500">
                <p>No customers match this view.</p>
                <div className="mt-3">{emptyAction}</div>
              </td>
            </tr>
          </tbody>
        ) : groups ? (
          groups.map((g) => (
            <tbody key={g.tuple}>
              <GroupHeader group={g} summary={summary} />
              {g.rows.map(renderRow)}
            </tbody>
          ))
        ) : (
          <tbody>{rows.map(renderRow)}</tbody>
        )}
      </table>
    </div>
  );
}
