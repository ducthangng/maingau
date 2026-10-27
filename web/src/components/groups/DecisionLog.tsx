import { Link } from "react-router-dom";
import { FileJson, FileSpreadsheet, RotateCcw } from "lucide-react";
import type { Summary } from "../../types/contracts";
import { type Decision, REVIEWER, clearDecisions, download, latestByCustomer, toCSV } from "../../lib/decisions";
import { signedEur, tupleLabel } from "../../lib/format";
import { Num } from "./Num";

// Hand-off export (prompts/agent-cards.md §1.2, §1.4 #10): latest decision per customer, only approved /
// overridden and not in the holdout. Holdout customers go to a separate list in the JSON. Nothing is sent.
export function exportable(log: Decision[]): { handoff: Decision[]; holdout: Decision[] } {
  const latest = [...latestByCustomer(log).values()].filter((d) => d.action === "approved" || d.action === "overridden");
  return { handoff: latest.filter((d) => !d.holdout), holdout: latest.filter((d) => d.holdout) };
}

const ACTION_STYLE: Record<string, string> = {
  approved: "bg-accent-50 text-accent-700 ring-accent-100",
  overridden: "bg-white text-accent-700 ring-accent-200",
  rejected: "bg-neutral-100 text-neutral-600 ring-neutral-200",
};

const fmtTime = (ts: string) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("en-GB", { dateStyle: "short", timeStyle: "medium" });
};

const stamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");

const btn =
  "inline-flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 transition-colors duration-150 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50";

export default function DecisionLog({ log, summary }: { log: Decision[]; summary: Summary | undefined }) {
  const { handoff, holdout } = exportable(log);
  const rows = [...log].reverse();

  const exportCSV = () => download(`maingau-handoff-${stamp()}.csv`, toCSV(handoff), "text/csv;charset=utf-8");
  const exportJSON = () =>
    download(
      `maingau-handoff-${stamp()}.json`,
      JSON.stringify(
        {
          exported_at: new Date().toISOString(),
          exported_by: REVIEWER,
          snapshot: summary?.eval_time ?? null,
          note: "Hand-off file for the campaign tool. Nothing has been sent; a human approved each entry.",
          approved: handoff,
          holdout,
        },
        null,
        2,
      ),
      "application/json",
    );
  const reset = () => {
    if (window.confirm(`Reset all ${log.length} decisions in this browser? This cannot be undone.`)) clearDecisions();
  };

  return (
    <section aria-labelledby="log-title" className="rounded-xl border border-neutral-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="log-title" className="text-[15px] font-semibold text-neutral-900">
            Decision log
          </h2>
          <p className="text-xs text-neutral-500">
            {log.length} decisions · {handoff.length} in the hand-off export · {holdout.length} holdout (kept as control, not exported for
            contact)
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={exportCSV} disabled={!handoff.length} className={btn}>
            <FileSpreadsheet className="size-4" aria-hidden />
            Export CSV
          </button>
          <button type="button" onClick={exportJSON} disabled={!handoff.length && !holdout.length} className={btn}>
            <FileJson className="size-4" aria-hidden />
            Export JSON
          </button>
          <button type="button" onClick={reset} disabled={!log.length} className={`${btn} hover:border-red-200 hover:text-red-700`}>
            <RotateCcw className="size-4" aria-hidden />
            Reset decisions
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 rounded-lg bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
          No decisions yet. Approve a group above, or decide on a customer page.
        </p>
      ) : (
        <div className="mt-4 max-h-[420px] overflow-auto rounded-lg border border-neutral-200">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="sticky top-0 bg-neutral-50 text-left text-[11px] uppercase tracking-wider text-neutral-500">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">Customer</th>
                <th scope="col" className="px-3 py-2 font-semibold">Action</th>
                <th scope="col" className="px-3 py-2 font-semibold">Tuple</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">ΔCLV</th>
                <th scope="col" className="px-3 py-2 font-semibold">Reviewer</th>
                <th scope="col" className="px-3 py-2 font-semibold">Time</th>
                <th scope="col" className="px-3 py-2 font-semibold">Holdout</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {rows.map((d) => (
                <tr key={d.id} className="transition-colors duration-150 hover:bg-neutral-50">
                  <td className="px-3 py-2 font-medium">
                    <Link to={`/customer/${d.customer_id}`} className="rounded hover:text-accent-700">
                      {d.customer_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${ACTION_STYLE[d.action] ?? ACTION_STYLE.rejected}`}>
                      {d.action}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-neutral-700" title={d.reason ?? undefined}>
                    {tupleLabel(d.tuple_id)}
                    {d.tuple_id !== d.from_tuple && <span className="block text-[11px] text-neutral-400">from {tupleLabel(d.from_tuple)}</span>}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Num col="delta_clv" value={d.delta_clv} format={signedEur} summary={summary} />
                  </td>
                  <td className="px-3 py-2 text-neutral-600">{d.reviewer}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-neutral-600 tabular-nums" title={d.ts}>
                    {fmtTime(d.ts)}
                  </td>
                  <td className="px-3 py-2 text-neutral-600">{d.holdout ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
