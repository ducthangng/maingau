import type { ReactNode } from "react";
import { Sourced } from "../Source";
import { NOT_ENOUGH, signedEur } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";
import { asOf, colSrc, isActionable, isBlocked, sumDelta } from "./model";

function Tile({ label, value, sub, src, summary }: { label: string; value: ReactNode; sub: string; src: string; summary: Summary | null }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white px-4 py-3.5">
      <div className="text-[13px] text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight text-neutral-900">
        <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
          {value}
        </Sourced>
      </div>
      <div className="mt-0.5 text-xs text-neutral-500">{sub}</div>
    </div>
  );
}

/** Four calm stat tiles over the rows currently in view (prompts/agent-cards.md §1.1). */
export default function KpiStrip({ rows, summary }: { rows: IndexRow[]; summary: Summary | null }) {
  const n = rows.length;
  const toAct = rows.filter(isActionable).length;
  const delta = sumDelta(rows);
  const outliers = rows.filter((r) => r.outlier === true).length;
  const blocked = rows.filter(isBlocked).length;
  const of = `of ${n} in view`;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile label="Customers to act on" value={toAct} sub={of} src="engine.chosen_tuple" summary={summary} />
      <Tile
        label="Expected ΔCLV in view"
        value={delta.sum === null ? <span className="text-base font-normal italic text-neutral-400">{NOT_ENOUGH}</span> : signedEur(delta.sum)}
        sub={delta.n ? `sum over ${delta.n} proposed action${delta.n === 1 ? "" : "s"}` : "no valued action in view"}
        src={colSrc(summary, "delta_clv")}
        summary={summary}
      />
      <Tile label="Outliers" value={outliers} sub={outliers ? "need a human look first" : of} src="engine.triage.outlier" summary={summary} />
      <Tile label="Blocked by rules" value={blocked} sub="no action or an active exclusion" src="engine.rules.exclusions" summary={summary} />
    </div>
  );
}
