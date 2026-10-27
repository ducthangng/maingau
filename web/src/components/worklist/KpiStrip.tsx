import type { ReactNode } from "react";
import { Ban, LifeBuoy, TriangleAlert } from "lucide-react";
import { Sourced } from "../Source";
import { DECISION_META, type DecisionState } from "../viz";
import type { Decision } from "../../lib/decisions";
import { signedEur } from "../../lib/format";
import type { IndexRow, Summary } from "../../types/contracts";
import { asOf, colSrc, isActionable, isNoAction, sumDelta } from "./model";

const ORDER: DecisionState[] = ["approved", "overridden", "rejected", "pending"];

function Shortcut({ icon, n, label, onClick, tone }: { icon: ReactNode; n: number; label: string; onClick: () => void; tone: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={n === 0}
      title={`Show: ${label}`}
      className="flex items-center gap-2.5 rounded-lg px-2 py-1 text-left transition-colors duration-150 hover:bg-neutral-100 disabled:opacity-40 disabled:hover:bg-transparent"
    >
      <span className={`grid size-6 place-items-center rounded-md ${tone}`}>{icon}</span>
      <span>
        <span className="block text-base font-semibold leading-none tabular-nums">{n}</span>
        <span className="text-xs text-neutral-500">{label}</span>
      </span>
    </button>
  );
}

/**
 * Review progress over the whole snapshot: how many proposals still wait for a human, what they are
 * worth, and one-click shortcuts to the rows that need care first.
 */
export default function KpiStrip({
  rows,
  summary,
  decisions,
  onQueue,
  onOutliers,
  onService,
}: {
  rows: IndexRow[];
  summary: Summary | null;
  decisions: Map<string, Decision>;
  onQueue: (q: "todo" | "hold") => void;
  onOutliers: () => void;
  onService: () => void;
}) {
  const actionable = rows.filter(isActionable);
  const counts: Record<DecisionState, number> = { approved: 0, overridden: 0, rejected: 0, pending: 0 };
  for (const r of actionable) counts[decisions.get(r.customer_id)?.action ?? "pending"] += 1;
  const pending = actionable.filter((r) => !decisions.has(r.customer_id));
  const waiting = sumDelta(pending);
  const total = actionable.length;
  const src = colSrc(summary, "delta_clv");

  const outliers = rows.filter((r) => r.outlier === true && !decisions.has(r.customer_id)).length;
  const service = pending.filter((r) => r.service_mode).length;
  const hold = rows.filter(isNoAction).length;

  return (
    <div className="flex flex-wrap items-center gap-x-10 gap-y-4 rounded-2xl border border-neutral-200 bg-white px-6 py-5">
      <button type="button" onClick={() => onQueue("todo")} className="text-left" title="Show the review queue">
        <div className="text-2xl font-semibold tracking-tight tabular-nums">{pending.length}</div>
        <div className="text-xs text-neutral-500">
          to review ·{" "}
          <Sourced src={src} updatedAt={asOf(summary, src)} sources={summary?.sources}>
            <span className="font-medium text-neutral-800">{waiting.sum === null ? "–" : signedEur(waiting.sum)}</span>
          </Sourced>{" "}
          waiting
        </div>
      </button>

      <div className="min-w-56 flex-1 space-y-2">
        <div
          className="flex h-2.5 gap-[2px] overflow-hidden rounded-full"
          role="img"
          aria-label={ORDER.map((k) => `${DECISION_META[k].label} ${counts[k]}`).join(", ")}
        >
          {ORDER.filter((k) => counts[k] > 0).map((k) => (
            <span
              key={k}
              title={`${DECISION_META[k].label}: ${counts[k]} of ${total}`}
              className={`h-full first:rounded-l-full last:rounded-r-full ${k === "pending" ? "bg-neutral-200" : DECISION_META[k].dot}`}
              style={{ flexGrow: counts[k] }}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
          {ORDER.map((k) => {
            const Icon = DECISION_META[k].icon;
            return (
              <span key={k} className="inline-flex items-center gap-1.5">
                <span className={`size-2 rounded-full ${k === "pending" ? "bg-neutral-200 ring-1 ring-neutral-300" : DECISION_META[k].dot}`} aria-hidden />
                {Icon && <Icon size={12} className={DECISION_META[k].text} aria-hidden />}
                {DECISION_META[k].label}
                <span className="font-medium tabular-nums text-neutral-900">{counts[k]}</span>
              </span>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        <Shortcut
          icon={<TriangleAlert size={15} />}
          tone="bg-red-50 text-red-600"
          n={outliers}
          label="Outliers first"
          onClick={onOutliers}
        />
        <Shortcut icon={<LifeBuoy size={15} />} tone="bg-neutral-100 text-neutral-700" n={service} label="Service first" onClick={onService} />
        <Shortcut icon={<Ban size={15} />} tone="bg-neutral-100 text-neutral-500" n={hold} label="Do not contact" onClick={() => onQueue("hold")} />
      </div>
    </div>
  );
}
