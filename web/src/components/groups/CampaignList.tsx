import { Megaphone } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Campaign } from "../../lib/campaigns";
import { signedEur, tupleLabel } from "../../lib/format";
import { Num } from "./Num";

// Campaigns created by "Approve everything", newest first. View only: the decisions are in the log below.

const TH = "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const TD = "px-3 py-2.5 align-top";

const fmtDate = (ts: string) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};

export default function CampaignList({ campaigns, summary }: { campaigns: Campaign[]; summary: Summary | undefined }) {
  const rows = [...campaigns].reverse();
  return (
    <section aria-labelledby="campaigns-title" className="rounded-xl border border-neutral-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="campaigns-title" className="inline-flex items-center gap-2 text-[15px] font-semibold text-neutral-900">
          <Megaphone className="size-4 text-neutral-500" aria-hidden />
          Campaigns
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600 tabular-nums">{rows.length}</span>
        </h2>
        <p className="text-xs text-neutral-500">Created with Approve everything. Nothing has been sent.</p>
      </div>

      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No campaign yet: use Approve everything to create one.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-neutral-200">
              <tr>
                <th className={TH}>Campaign</th>
                <th className={TH}>Action and segment</th>
                <th className={`${TH} text-right`}>Groups</th>
                <th className={`${TH} text-right`}>Contacted</th>
                <th className={`${TH} text-right`}>Control group</th>
                <th className={`${TH} text-right`}>Σ ΔCLV</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {rows.map((c) => (
                <tr key={c.id}>
                  <td className={TD}>
                    <div className="font-medium text-neutral-900">{c.name}</div>
                    <div className="text-xs text-neutral-500 tabular-nums">{fmtDate(c.created_at)}</div>
                  </td>
                  <td className={`${TD} text-neutral-700`}>{c.scope}</td>
                  <td className={`${TD} text-right tabular-nums`} title={(c.groups ?? []).map(tupleLabel).join("\n")}>
                    {(c.groups ?? []).length}
                  </td>
                  <td className={`${TD} text-right tabular-nums`}>{c.contacted}</td>
                  <td className={`${TD} text-right tabular-nums`}>
                    {c.holdout} · {c.holdout_pct}%
                  </td>
                  <td className={`${TD} text-right`}>
                    <Num col="delta_clv" value={c.delta_clv} format={signedEur} summary={summary} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
