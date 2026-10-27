import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import type { IndexRow } from "../../types/contracts";
import { CHANNEL_LABEL, isMissing, pct, signedEur, tupleLabel } from "../../lib/format";
import { customerEvent, mockName } from "../../lib/customerMock";
import { Signed, ValueBar, dirOf } from "../viz";
import { OFFER_NAME, isNoAction, sortRows } from "../worklist/model";
import { noPayment } from "./plain";

// Customer 360° start page: the orchestration worklist's table (same order, columns and look) for
// every customer, filtered by customer ID. Read-only: no tier chip, flags, row tint, icons or
// approve buttons; a click opens the customer. No payment wording (see customer360.test.tsx).

/** "100068", "mg-1000" or "MG-100068" all match MG-100068. */
export function matchesId(id: string, query: string): boolean {
  const q = query.trim().toUpperCase().replace(/^MG-?/, "");
  return !q || id.toUpperCase().replace(/^MG-?/, "").includes(q);
}

const COLS: { label: string; width?: number; title?: string }[] = [
  { label: "Customer · latest action" },
  { label: "Recommended action", width: 240 },
  { label: "Expected value", width: 220, title: "Expected ΔCLV (bars share one scale) and the chance the customer agrees" },
];

function ActionCell({ row }: { row: IndexRow }) {
  if (isNoAction(row)) return <span className="text-[13px] text-neutral-500">No offer right now</span>;
  return (
    <div className="flex min-w-0 items-baseline gap-1.5" title={`${tupleLabel(row.chosen_tuple)}\n${CHANNEL_LABEL[row.channel ?? ""] ?? row.channel}`}>
      <span className="truncate text-[13px] font-medium text-neutral-900">{OFFER_NAME[row.chosen_offer] ?? row.chosen_offer}</span>
      <span className="shrink-0 text-[11px] text-neutral-400">{CHANNEL_LABEL[row.channel ?? ""] ?? row.channel}</span>
    </div>
  );
}

function ValueCell({ row, max }: { row: IndexRow; max: number }) {
  const v = row.delta_clv;
  if (isNoAction(row) || isMissing(v)) return <span className="text-neutral-300">—</span>;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <Signed dir={dirOf(v)} className="text-[13px] font-medium text-neutral-900">
          {signedEur(v)}
        </Signed>
        {!isMissing(row.p_accept) && <span className="text-[11px] text-neutral-500">{pct(row.p_accept)} chance</span>}
      </div>
      <ValueBar value={v} max={max} />
    </div>
  );
}

export default function CustomerList({ rows }: { rows: IndexRow[] }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const all = useMemo(() => sortRows(rows), [rows]);
  const shown = useMemo(() => all.filter((r) => matchesId(r.customer_id, query)), [all, query]);
  // One bar scale over the whole snapshot, so bars do not jump while filtering.
  const max = useMemo(() => Math.max(1, ...rows.map((r) => Math.abs(r.delta_clv ?? 0))), [rows]);
  const open = (id: string) => navigate(`/service/${encodeURIComponent(id)}`);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            if (shown.length === 1) open(shown[0].customer_id);
          }}
          className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 focus-within:border-accent-500"
        >
          <Search className="size-4 text-neutral-400" aria-hidden />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            aria-label="Filter by customer ID"
            placeholder="Customer ID, e.g. MG-100023"
            className="w-56 bg-transparent text-sm outline-none placeholder:text-neutral-400 sm:w-72"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} className="text-xs text-neutral-500 hover:text-neutral-900">
              Clear
            </button>
          )}
        </form>
        <span className="ml-auto text-xs text-neutral-500 tabular-nums" aria-live="polite">
          {shown.length} of {rows.length} customers
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
        <table className="w-full min-w-[720px] table-fixed border-collapse text-sm">
          <colgroup>
            {COLS.map((c, i) => (
              <col key={i} style={c.width ? { width: c.width } : undefined} />
            ))}
          </colgroup>
          <thead>
            <tr className="text-left text-xs font-medium text-neutral-500">
              {COLS.map((c, i) => (
                <th key={i} scope="col" title={c.title} className={`py-3 font-medium ${i === 0 ? "pr-2 pl-5" : i === COLS.length - 1 ? "pr-5 pl-3" : "px-3"}`}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr className="border-t border-neutral-100">
                <td colSpan={COLS.length} className="px-4 py-12 text-center text-neutral-500">
                  No customer matches “{query}”.
                </td>
              </tr>
            ) : (
              shown.map((r) => {
                const ev = customerEvent(r);
                return (
                  <tr
                    key={r.customer_id}
                    onClick={() => open(r.customer_id)}
                    className="cursor-pointer border-t border-neutral-100 transition-[filter] duration-150 hover:brightness-[0.97] bg-white"
                  >
                    <td className="py-3 pr-2 pl-5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          open(r.customer_id);
                        }}
                        className="font-medium text-neutral-900 hover:text-accent-700 hover:underline"
                      >
                        {mockName(r.customer_id)}
                      </button>{" "}
                      <span className="rounded bg-neutral-100 px-1 text-[10px] font-medium uppercase text-neutral-500" title="Demo name: the data has no names">
                        demo
                      </span>
                      <span className="ml-1.5 font-mono text-xs text-neutral-400">{r.customer_id}</span>
                      <p className="mt-1.5 truncate text-xs text-neutral-600">{noPayment(ev.text, "Account status needs attention")}</p>
                    </td>
                    <td className="px-3 py-3">
                      <ActionCell row={r} />
                    </td>
                    <td className="py-3 pr-5 pl-3">
                      <ValueCell row={r} max={max} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
