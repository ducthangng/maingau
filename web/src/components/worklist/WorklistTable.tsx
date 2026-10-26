import { Fragment, useState } from "react";
import { ArrowRight, Ban, Check, LifeBuoy, Package, Maximize2, X, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { TierChip } from "../Chips";
import { Sourced } from "../Source";
import { ChannelIcon, ConfidenceBars, DECISION_META, FlagIcons, Signed, ValueBar, dirOf } from "../viz";
import { decideRow, type Decision } from "../../lib/decisions";
import { CHANNEL_LABEL, eur, isMissing, pct, signedEur, tupleLabel } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";
import { NO_ACTION, OFFER_NAME, asOf, colSrc, isNoAction, type Group } from "./model";

// Action-first worklist: each row says why now, what to do, what it is worth, and lets the
// reviewer decide on the spot. Archetype, CLV and churn sit in the row tooltip and the pop-up.

// Row tint by urgency tier: the hotter the row, the warmer the background (the tier chip names it).
const TIER_ROW: Record<string, string> = {
  P1: "bg-red-50",
  P2: "bg-orange-50/80",
  P3: "bg-amber-50/70",
  P4: "bg-sky-50/50",
  P5: "bg-white",
};

const COLS: { label: string; width?: number; align?: "right"; title?: string }[] = [
  { label: "", width: 60 },
  { label: "Customer · why now" },
  { label: "Recommended action", width: 200 },
  { label: "Expected value", width: 190, title: "Expected ΔCLV (bars share one scale) and the chance of success vs the median proposal" },
  { label: "", width: 190, align: "right" },
];

/** "electricity price guarantee ends … [S4]" → without the bracketed ids (they stay in the tooltip). */
const plain = (s: string) => s.replace(/\s*\[[A-Z0-9-]+\]/g, "").trim();

function WhyCell({ row }: { row: IndexRow }) {
  const reason = row.top_reason ? plain(row.top_reason) : null;
  const [Icon, tone, kind] = isNoAction(row)
    ? [Ban, "bg-neutral-100 text-neutral-500", "Blocked"]
    : row.service_mode
      ? [LifeBuoy, "bg-amber-50 text-amber-700", "Service issue"]
      : (row.triggers?.length ?? 0) > 0 && row.personalised !== false
        ? [Zap, "bg-accent-50 text-accent-700", "Signal"]
        : [Package, "bg-neutral-100 text-neutral-500", "Generic catalog offer"];
  return (
    <div className="flex min-w-0 items-center gap-2" title={[kind, row.top_reason].filter(Boolean).join(": ")}>
      <span className={`grid size-5 shrink-0 place-items-center rounded ${tone}`} aria-label={kind} role="img">
        <Icon size={12} aria-hidden />
      </span>
      <span className="truncate text-xs text-neutral-500">{reason ?? (row.personalised === false ? "No trigger: generic offer" : "–")}</span>
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
    </div>
  );
}

/** Expected ΔCLV and its chance in one cell: value on top, shared-scale bar, chance vs the median below. */
function ValueCell({ row, max, median, summary }: { row: IndexRow; max: number; median: number | null; summary: Summary | null }) {
  const v = row.delta_clv;
  const p = row.p_accept;
  if (isNoAction(row) || isMissing(v)) return <span className="text-neutral-300">—</span>;
  const src = colSrc(summary, "delta_clv");
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
          <Signed dir={dirOf(v)} className="text-[13px] font-medium text-neutral-900">
            {signedEur(v)}
          </Signed>
        </Sourced>
        {!isMissing(p) && (
          <span
            className="inline-flex items-center gap-1.5 text-[11px] text-neutral-500"
            title={`Chance ${pct(p)}${median !== null ? ` vs median of proposals ${pct(median)}` : ""} · ${row.confidence ?? "unknown"} confidence`}
          >
            {median !== null ? <Signed dir={dirOf(p, median, 0.0005)}>{pct(p)}</Signed> : pct(p)}
            <ConfidenceBars confidence={row.confidence} />
          </span>
        )}
      </div>
      <ValueBar value={v} max={max} />
    </div>
  );
}

const btn = "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors duration-150";

/** Two buttons only: Approve the engine's proposal, or Expand into the pop-up for everything else. */
function DecisionCell({ row, decision, onOpen }: { row: IndexRow; decision: Decision | undefined; onOpen: () => void }) {
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
  if (decision) {
    const m = DECISION_META[decision.action];
    const Icon = m.icon ?? Check;
    main = (
      <span className={`inline-flex items-center gap-1 text-xs font-medium ${m.text}`} title={`${m.label} by ${decision.reviewer}${decision.reason ? `\n${decision.reason}` : ""}`}>
        <Icon size={14} aria-hidden /> {m.label}
      </span>
    );
  } else if (!isNoAction(row)) {
    main = (
      <button type="button" onClick={stop(() => decideRow(row, "approved"))} className={`${btn} bg-accent-600 text-white hover:bg-accent-700`} title="Approve (A)">
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

function RejectRow({ row, onDone }: { row: IndexRow; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const submit = () => {
    if (!reason.trim()) return;
    decideRow(row, "rejected", reason.trim());
    onDone();
  };
  return (
    <tr className="bg-red-50/40">
      <td colSpan={COLS.length} className="px-4 py-2.5">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <X size={14} className="text-red-600" aria-hidden />
          <input
            autoFocus
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && onDone()}
            placeholder={`Why reject ${OFFER_NAME[row.chosen_offer] ?? row.chosen_offer} for ${row.customer_id}? (required)`}
            aria-label="Reject reason"
            className="min-w-0 flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm placeholder:text-neutral-400 focus:border-red-400 focus:ring-2 focus:ring-red-100 focus:outline-none"
          />
          <button type="submit" disabled={!reason.trim()} className={`${btn} bg-red-600 py-1.5 text-white hover:bg-red-700 disabled:opacity-40`}>
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
  max,
  median,
  onOpen,
  onReject,
}: {
  row: IndexRow;
  summary: Summary | null;
  decision: Decision | undefined;
  highlighted: boolean;
  rejecting: boolean;
  max: number;
  median: number | null;
  onOpen: (id: string) => void;
  onReject: (id: string | null) => void;
}) {
  const outlier = row.outlier === true;
  const tint = decision ? "bg-white opacity-60" : isNoAction(row) ? "bg-neutral-50 text-neutral-500" : TIER_ROW[row.urgency_tier ?? "P5"];
  const context = [
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
            {row.customer_id}
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
        <td className="px-3 py-3">
          <ValueCell row={row} max={max} median={median} summary={summary} />
        </td>
        <td className="py-3 pr-4 pl-3">
          <DecisionCell row={row} decision={decision} onOpen={() => onOpen(row.customer_id)} />
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
  empty,
}: {
  rows: IndexRow[];
  groups: Group[] | null;
  summary: Summary | null;
  decisions: Map<string, Decision>;
  highlightedId: string | null;
  rejectingId: string | null;
  /** Shared bar scale and reference over the whole snapshot, so bars do not jump when filtering. */
  scale: { max: number; median: number | null };
  onOpen: (id: string) => void;
  onReject: (id: string | null) => void;
  empty: React.ReactNode;
}) {
  const renderRow = (r: IndexRow) => (
    <Row
      key={r.customer_id}
      row={r}
      summary={summary}
      decision={decisions.get(r.customer_id)}
      highlighted={r.customer_id === highlightedId}
      rejecting={r.customer_id === rejectingId}
      max={scale.max}
      median={scale.median}
      onOpen={onOpen}
      onReject={onReject}
    />
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
      <table className="w-full min-w-[820px] table-fixed border-collapse text-sm">
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
