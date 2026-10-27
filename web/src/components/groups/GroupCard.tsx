import type { ReactNode } from "react";
import { Users } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Decision } from "../../lib/decisions";
import { eur, signedEur, tupleLabel } from "../../lib/format";
import { type Group, gateCounts, plural, sumOf } from "./model";
import { Num, conversions } from "./Num";

export function Stat({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-0.5 truncate text-[15px] font-semibold text-neutral-900">{children}</div>
      {hint && <div className="text-[11px] text-neutral-400">{hint}</div>}
    </div>
  );
}

export default function GroupCard({
  group,
  summary,
  latest,
  onOpen,
}: {
  group: Group;
  summary: Summary | undefined;
  latest: Map<string, Decision>;
  onOpen: (tuple: string) => void;
}) {
  const delta = sumOf(group.rows, "delta_clv");
  const p = sumOf(group.rows, "p_accept");
  const cost = sumOf(group.rows, "contact_cost");
  const gates = gateCounts(group.rows, latest, group.tuple);
  const decided = group.rows.filter((r) => {
    const d = latest.get(r.customer_id);
    return d && (d.action === "approved" || d.action === "overridden") && d.tuple_id === group.tuple;
  }).length;
  const missingHint = (n: number) => (n ? `${n} without data` : undefined);

  return (
    <article className="flex flex-col rounded-xl border border-neutral-200 bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition-shadow duration-200 hover:shadow-md">
      <header className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 text-[15px] font-semibold leading-snug text-neutral-900">{tupleLabel(group.tuple)}</h3>
        <span title={plural(group.rows.length, "customer")} className="inline-flex shrink-0 items-center gap-1 rounded-full bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-700 tabular-nums">
          <Users className="size-3.5" aria-hidden />
          {group.rows.length}
        </span>
      </header>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Stat label="Σ ΔCLV" hint={missingHint(delta.missing)}>
          <Num col="delta_clv" value={delta.total} format={signedEur} summary={summary} />
        </Stat>
        <Stat label="Exp. conv." hint={missingHint(p.missing)}>
          <Num col="p_accept" value={p.total} format={conversions} summary={summary} />
        </Stat>
        <Stat label="Contact cost" hint={missingHint(cost.missing)}>
          <Num col="contact_cost" value={cost.total} format={(v) => eur(v, true)} summary={summary} />
        </Stat>
      </div>

      <ul className="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-600" aria-label="Who can be bulk-approved">
        <li className="inline-flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-accent-600" aria-hidden />
          {gates.ready} ready
        </li>
        {gates.review > 0 && (
          <li className="inline-flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-neutral-400" aria-hidden />
            {gates.review} need a second look
          </li>
        )}
        {gates.blocked > 0 && (
          <li className="inline-flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-red-500" aria-hidden />
            {gates.blocked} do no harm
          </li>
        )}
        {decided > 0 && <li className="text-accent-700">{decided} approved</li>}
      </ul>

      <div className="mt-5 flex flex-1 items-end">
        <button
          type="button"
          onClick={() => onOpen(group.tuple)}
          className="w-full rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-sm font-medium text-accent-700 transition-colors duration-150 hover:border-accent-500 hover:bg-accent-50"
        >
          Approve group…
        </button>
      </div>
    </article>
  );
}
