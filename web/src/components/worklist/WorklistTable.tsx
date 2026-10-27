import { Fragment, useState } from "react";
import { ArrowRight, Check, Lock, Maximize2, TrendingUp, TriangleAlert, X } from "lucide-react";
import { Link } from "react-router-dom";
import { TierChip } from "../Chips";
import { Sourced } from "../Source";
import { ChannelIcon, DECISION_META, FlagIcons, Signed, dirOf } from "../viz";
import { decideRow, rejectText, type Decision, type ReasonCode } from "../../lib/decisions";
import { customerEvent, mockName } from "../../lib/customerMock";
import { useHardRules, violation, type HardRule } from "../../lib/hardRules";
import { RejectReasonSelect, ruleText } from "../customer/NbaPanel";
import { CHANNEL_LABEL, eur, isMissing, pct, signedEur, tupleLabel } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";
import { movedFromLabel, type GroupRow } from "../../lib/groupMoves";
import { NO_ACTION, OFFER_NAME, asOf, colSrc, isNoAction, type Group } from "./model";

// Action-first worklist: each row says why now, what to do, what it is worth, and lets the
// reviewer decide on the spot. Archetype, CLV and churn sit in the row tooltip and the pop-up.

// Row tint by urgency tier: only P1 (act now) is tinted; the tier chip names every tier.
const TIER_ROW: Record<string, string> = {
  P1: "bg-red-50/60",
  P2: "bg-white",
  P3: "bg-white",
  P4: "bg-white",
  P5: "bg-white",
};

const COLS: { label: string; width?: number; align?: "right"; title?: string }[] = [
  { label: "", width: 60 },
  { label: "Customer · latest action" },
  { label: "Recommended action", width: 200 },
  { label: "Expected ΔCLV", width: 120, align: "right", title: "Expected change in customer lifetime value" },
  { label: "Chance", width: 90, align: "right", title: "Chance of success (p) of the recommended action" },
  { label: "Confidence", width: 100, title: "How many observations stand behind p (high, medium, low)" },
  { label: "", width: 190, align: "right" },
];

/** Why the customer is on the list: their latest action, marked as an upsell chance (blue) or a potential issue (red). */
function WhyCell({ row }: { row: IndexRow }) {
  const ev = customerEvent(row);
  const positive = ev.polarity === "positive";
  const label = positive ? "Upsell chance" : "Potential issue";
  return (
    <div
      className="flex min-w-0 items-center gap-2"
      title={`${label}: ${ev.text}${ev.mock ? " (mock activity)" : ""}${row.top_reason ? `\nEngine: ${row.top_reason}` : ""}`}
    >
      <span
        className={`grid size-5 shrink-0 place-items-center rounded-full ${positive ? "bg-accent-100 text-accent-700" : "bg-red-100 text-red-700"}`}
        role="img"
        aria-label={label}
      >
        {positive ? <TrendingUp size={12} aria-hidden /> : <TriangleAlert size={12} aria-hidden />}
      </span>
      <span className="truncate text-xs text-neutral-600">{ev.text}</span>
    </div>
  );
}

function ActionCell({ row }: { row: IndexRow }) {
  if (isNoAction(row)) {
    const why = row.exclusions?.length ? row.exclusions.join(", ") : row.checklist_failed?.join(", ");
    return (
      <span className="text-[13px] text-neutral-500" title={why ?? undefined}>
        Do not contact
      </span>
    );
  }
  const name = OFFER_NAME[row.chosen_offer] ?? row.chosen_offer;
  return (
    <div className="flex min-w-0 items-center gap-1.5" title={`${tupleLabel(row.chosen_tuple)}\n${CHANNEL_LABEL[row.channel ?? ""] ?? row.channel}`}>
      <span className="grid size-5 shrink-0 place-items-center rounded bg-neutral-900 text-white">
        <ChannelIcon channel={row.channel} size={12} />
      </span>
      <span className="truncate text-[13px] font-medium text-neutral-900">{name}</span>
      <span className="shrink-0 text-[11px] text-neutral-400">{row.tone === "du" ? "Du" : "Sie"}</span>
      {movedFromLabel(row as GroupRow) && (
        <span title={movedFromLabel(row as GroupRow)!} className="shrink-0 rounded bg-accent-50 px-1 text-[10px] font-medium text-accent-700 ring-1 ring-inset ring-accent-100">
          moved
        </span>
      )}
    </div>
  );
}

// Expected value as plain numbers, one column each: ΔCLV, chance and its confidence (no bars).
const dash = <span className="text-neutral-300">—</span>;

function DeltaCell({ row, summary }: { row: IndexRow; summary: Summary | null }) {
  const v = row.delta_clv;
  if (isNoAction(row) || isMissing(v)) return dash;
  const src = colSrc(summary, "delta_clv");
  return (
    <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
      <span className={`text-[13px] font-medium tabular-nums ${v < 0 ? "text-red-700" : "text-neutral-900"}`}>{signedEur(v)}</span>
    </Sourced>
  );
}

function ChanceCell({ row, median }: { row: IndexRow; median: number | null }) {
  const p = row.p_accept;
  if (isNoAction(row) || isMissing(p)) return dash;
  return (
    <span className="text-[13px] tabular-nums text-neutral-800" title={median !== null ? `Median of proposals ${pct(median)}` : undefined}>
      {pct(p)}
    </span>
  );
}

function ConfidenceCell({ row }: { row: IndexRow }) {
  if (isNoAction(row) || !row.confidence) return dash;
  return <span className="text-[13px] capitalize text-neutral-700">{row.confidence}</span>;
}

const btn = "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors duration-150";

/** Replaces Approve on a page of its own (the group page: "Remove" / "Restore"); null = no button for that row. */
export type RowAction = (row: IndexRow) => { label: string; title: string; danger?: boolean; onClick: () => void } | null;

/** Two buttons only: Approve the engine's proposal (or the page's `rowAction`), or Expand into the pop-up for everything else. */
function DecisionCell({
  row,
  decision,
  lock,
  rowAction,
  onOpen,
}: {
  row: IndexRow;
  decision: Decision | undefined;
  lock: HardRule | undefined;
  rowAction?: RowAction;
  onOpen: () => void;
}) {
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };
  const expand = (
    <button
      type="button"
      onClick={stop(onOpen)}
      title="Expand: graph, override or reject (Enter)"
      className={`${btn} bg-white text-neutral-700 ring-1 ring-inset ring-neutral-200 hover:bg-neutral-50 hover:text-neutral-900`}
    >
      <Maximize2 size={12} aria-hidden /> Expand
    </button>
  );
  let main: React.ReactNode = null;
  const action = rowAction?.(row);
  if (rowAction) {
    main = action ? (
      <button
        type="button"
        onClick={stop(action.onClick)}
        title={action.title}
        className={`${btn} ${action.danger ? "bg-white text-red-700 ring-1 ring-inset ring-neutral-200 hover:bg-red-50" : "bg-white text-neutral-700 ring-1 ring-inset ring-neutral-200 hover:bg-neutral-50"}`}
      >
        {action.danger && <X size={12} aria-hidden />} {action.label}
      </button>
    ) : null;
    if (decision) {
      const m = DECISION_META[decision.action];
      const Icon = m.icon ?? Check;
      main = (
        <>
          <span className={`inline-flex items-center gap-1 text-xs font-medium ${m.text}`} title={`${m.label} by ${decision.reviewer}`}>
            <Icon size={14} aria-hidden /> {m.label}
          </span>
          {main}
        </>
      );
    }
  } else if (decision) {
    const m = DECISION_META[decision.action];
    const Icon = m.icon ?? Check;
    main = (
      <span
        className={`inline-flex items-center gap-1 text-xs font-medium ${m.text}`}
        title={`${m.label} by ${decision.reviewer}${decision.reason ? `\n${decision.reason}` : ""}`}
      >
        <Icon size={14} aria-hidden /> {m.label}
      </span>
    );
  } else if (lock) {
    main = (
      <span
        className="inline-flex items-center gap-1 text-xs text-neutral-500"
        title={`Locked by hard rule: ${ruleText(lock)}${lock.reason ? `\n${lock.reason}` : ""}`}
      >
        <Lock size={13} aria-hidden /> Rule
      </span>
    );
  } else if (!isNoAction(row)) {
    main = (
      <button
        type="button"
        onClick={stop(() => decideRow(row, "approved"))}
        className={`${btn} bg-accent-600 text-white hover:bg-accent-700`}
        title="Approve (A)"
      >
        <Check size={13} aria-hidden /> Approve
      </button>
    );
  }
  return (
    <div className="flex items-center justify-end gap-2">
      {main}
      {expand}
    </div>
  );
}

const rejectField = "rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm focus:border-red-400 focus:ring-2 focus:ring-red-100 focus:outline-none";

// A reason from the list is required (it becomes the API's reason_code); the note is optional.
function RejectRow({ row, onDone }: { row: IndexRow; onDone: () => void }) {
  const [code, setCode] = useState<ReasonCode | "">("");
  const [note, setNote] = useState("");
  const submit = () => {
    if (!code) return;
    decideRow(row, "rejected", rejectText(code, note), code);
    onDone();
  };
  return (
    <tr className="bg-red-50/40">
      <td colSpan={COLS.length} className="px-4 py-2.5">
        <form
          className="flex items-center gap-2"
          onKeyDown={(e) => e.key === "Escape" && onDone()}
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <X size={14} className="text-red-600" aria-hidden />
          <RejectReasonSelect autoFocus value={code} onChange={setCode} className={`${rejectField} pr-8 text-neutral-700`} />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={`Note on ${OFFER_NAME[row.chosen_offer] ?? row.chosen_offer} for ${mockName(row.customer_id)} (optional)`}
            aria-label="Short note"
            className={`${rejectField} min-w-0 flex-1 placeholder:text-neutral-400`}
          />
          <button type="submit" disabled={!code} className={`${btn} bg-red-600 py-1.5 text-white hover:bg-red-700 disabled:opacity-40`}>
            Confirm reject
          </button>
          <button type="button" onClick={onDone} className={`${btn} py-1.5 text-neutral-600 hover:bg-neutral-100`}>
            Cancel
          </button>
        </form>
      </td>
    </tr>
  );
}

function Row({
  row,
  summary,
  decision,
  highlighted,
  rejecting,
  lock,
  median,
  rowAction,
  onOpen,
  onReject,
}: {
  lock: HardRule | undefined;
  rowAction?: RowAction;
  row: IndexRow;
  summary: Summary | null;
  decision: Decision | undefined;
  highlighted: boolean;
  rejecting: boolean;
  median: number | null;
  onOpen: (id: string) => void;
  onReject: (id: string | null) => void;
}) {
  const outlier = row.outlier === true;
  const tint = decision ? "bg-white opacity-60" : isNoAction(row) ? "bg-neutral-50 text-neutral-500" : TIER_ROW[row.urgency_tier ?? "P5"];
  const context = [
    row.customer_id,
    row.archetype_name && `${row.archetype} · ${row.archetype_name}`,
    !isMissing(row.clv_eur) && `CLV ${eur(row.clv_eur)}`,
    !isMissing(row.churn) && `churn ${pct(row.churn, 0)}`,
    row.city,
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <Fragment>
      <tr
        data-row-id={row.customer_id}
        aria-selected={highlighted}
        onClick={() => onOpen(row.customer_id)}
        className={`cursor-pointer border-t border-white/80 transition-[filter] duration-150 hover:brightness-[0.97] ${tint} ${
          highlighted ? "outline-2 -outline-offset-2 outline-accent-500" : ""
        }`}
      >
        <td className={`border-l-4 py-3 pr-2 pl-4 ${outlier ? "border-l-red-500" : "border-l-transparent"}`}>
          <TierChip tier={row.urgency_tier} />
        </td>
        <td className="px-3 py-3" title={context}>
          <Link
            to={`/customer/${row.customer_id}`}
            onClick={(e) => {
              e.stopPropagation();
              // Plain click opens the pop-up; Cmd/Ctrl-click still opens the full page in a new tab.
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
              e.preventDefault();
              onOpen(row.customer_id);
            }}
            className="font-medium text-neutral-900 tabular-nums hover:text-accent-700 hover:underline"
          >
            {mockName(row.customer_id)}
          </Link>
          <span className="ml-1.5 inline-flex align-middle">
            <FlagIcons flags={row.flags ?? []} />
          </span>
          <div className="mt-1.5">
            <WhyCell row={row} />
          </div>
        </td>
        <td className="px-3 py-3">
          <ActionCell row={row} />
        </td>
        <td className="px-3 py-3 text-right">
          <DeltaCell row={row} summary={summary} />
        </td>
        <td className="px-3 py-3 text-right">
          <ChanceCell row={row} median={median} />
        </td>
        <td className="px-3 py-3">
          <ConfidenceCell row={row} />
        </td>
        <td className="py-3 pr-4 pl-3">
          <DecisionCell row={row} decision={decision} lock={lock} rowAction={rowAction} onOpen={() => onOpen(row.customer_id)} />
        </td>
      </tr>
      {rejecting && !decision && <RejectRow row={row} onDone={() => onReject(null)} />}
    </Fragment>
  );
}

function GroupHeader({ group, summary }: { group: Group; summary: Summary | null }) {
  const noAction = group.tuple === NO_ACTION;
  const offer = noAction ? null : group.tuple.split("|")[0];
  const channel = noAction ? null : group.tuple.split("|")[1];
  const src = colSrc(summary, "delta_clv");
  const service = !noAction && group.rows.some((r) => r.service_mode);
  return (
    <tr className="border-t border-neutral-200 bg-neutral-50">
      <td colSpan={COLS.length} className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {channel && <ChannelIcon channel={channel} size={15} className="text-neutral-500" />}
          <span className="font-semibold text-neutral-900">{noAction ? "Do not contact" : (OFFER_NAME[offer ?? ""] ?? offer)}</span>
          <span className="rounded-full bg-white px-2 py-0.5 text-xs text-neutral-600 ring-1 ring-neutral-200 ring-inset tabular-nums">
            {group.rows.length}
          </span>
          {!noAction && group.sum !== null && (
            <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
              <Signed dir={dirOf(group.sum)} className="font-medium text-neutral-900">
                {signedEur(group.sum)}
              </Signed>
            </Sourced>
          )}
          {group.reviewable ? (
            <Link
              to={`/groups?tuple=${encodeURIComponent(group.tuple)}`}
              className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-medium text-accent-600 transition-colors duration-150 hover:bg-accent-50 hover:text-accent-700"
            >
              Approve as group <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          ) : (
            <span className="ml-auto text-xs text-neutral-400">{service ? "service: one by one" : ""}</span>
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
  rejectingId,
  scale,
  onOpen,
  onReject,
  rowAction,
  empty,
}: {
  rows: IndexRow[];
  groups: Group[] | null;
  summary: Summary | null;
  decisions: Map<string, Decision>;
  highlightedId: string | null;
  rejectingId: string | null;
  /** Reference over the whole snapshot (the median p is in the Chance tooltip); `max` is no longer drawn. */
  scale: { max: number; median: number | null };
  onOpen: (id: string) => void;
  onReject: (id: string | null) => void;
  rowAction?: RowAction;
  empty: React.ReactNode;
}) {
  const rules = useHardRules();
  const today = (summary?.eval_time ?? new Date().toISOString()).slice(0, 10);
  const lockOf = (r: IndexRow) =>
    isNoAction(r)
      ? undefined
      : violation(rules, { customer_id: r.customer_id, archetype: r.archetype }, { offer: r.chosen_offer, channel: r.channel }, today);
  const renderRow = (r: IndexRow) => (
    <Row
      lock={lockOf(r)}
      key={r.customer_id}
      row={r}
      summary={summary}
      decision={decisions.get(r.customer_id)}
      highlighted={r.customer_id === highlightedId}
      rejecting={r.customer_id === rejectingId}
      median={scale.median}
      rowAction={rowAction}
      onOpen={onOpen}
      onReject={onReject}
    />
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
      <table className="w-full min-w-[900px] table-fixed border-collapse text-sm">
        <colgroup>
          {COLS.map((c, i) => (
            <col key={i} style={c.width ? { width: c.width } : undefined} />
          ))}
        </colgroup>
        <thead>
          <tr className="text-left text-xs font-medium text-neutral-500">
            {COLS.map((c, i) => (
              <th
                key={i}
                scope="col"
                title={c.title}
                className={`py-3 font-medium ${i === 0 ? "pr-2 pl-5" : i === COLS.length - 1 ? "pr-4 pl-3" : "px-3"} ${c.align === "right" ? "text-right" : ""}`}
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
                {empty}
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
