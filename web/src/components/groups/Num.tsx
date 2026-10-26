import type { Summary } from "../../types/contracts";
import { NOT_ENOUGH, isMissing } from "../../lib/format";
import { Sourced } from "../Source";

// Column → table.column, from summary.column_src (fallback: the engine output the value comes from).
const FALLBACK_SRC: Record<string, string> = {
  delta_clv: "engine.valuation.delta_clv",
  p_accept: "engine.valuation.p_accept",
  contact_cost: "engine.valuation.contact_cost",
  urgency_score: "engine.triage.urgency_score",
};

export function colSrc(summary: Summary | undefined, col: string): string {
  return summary?.column_src?.[col] ?? FALLBACK_SRC[col] ?? `index.${col}`;
}

/** A number with a source tooltip. Missing → "not enough data", never 0. */
export function Num({
  col,
  value,
  format,
  summary,
  className = "",
}: {
  col: string;
  value: number | null | undefined;
  format: (v: number) => string;
  summary: Summary | undefined;
  className?: string;
}) {
  const missing = isMissing(value);
  return (
    <Sourced src={colSrc(summary, col)} updatedAt={summary?.eval_time} sources={summary?.sources}>
      <span className={missing ? "italic text-neutral-400" : `tabular-nums ${className}`}>{missing ? NOT_ENOUGH : format(value)}</span>
    </Sourced>
  );
}

export const conversions = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
