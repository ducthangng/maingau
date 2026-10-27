import { useState } from "react";
import { ChevronRight, Megaphone } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Campaign } from "../../lib/campaigns";
import { signedEur, tupleLabel } from "../../lib/format";
import { useDecisions } from "../../lib/decisions";
import { Num } from "./Num";
import CampaignDetail, { fmtDate } from "./CampaignDetail";

// Campaigns created by "Approve everything" or "Save & Run" on a group page, newest first. A row opens
// the campaign's details (CampaignDetail). View only: the decisions are in the log.

const TH = "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const TD = "px-3 py-2.5 align-top";

export default function CampaignList({ campaigns, summary }: { campaigns: Campaign[]; summary: Summary | undefined }) {
  const rows = [...campaigns].reverse();
  const decisions = useDecisions();
  const [openId, setOpenId] = useState<string | null>(null);
  const open = rows.find((c) => c.id === openId);
  return (
    <section aria-labelledby="campaigns-title" className="rounded-xl border border-neutral-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="campaigns-title" className="inline-flex items-center gap-2 text-[15px] font-semibold text-neutral-900">
          <Megaphone className="size-4 text-neutral-500" aria-hidden />
          Campaigns
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600 tabular-nums">{rows.length}</span>
        </h2>
        <p className="text-xs text-neutral-500">Created with Approve everything or Approve group. Nothing has been sent.</p>
      </div>

      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No campaign yet: use Approve everything or Approve group to create one.</p>
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
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {rows.map((c) => (
                <tr
                  key={c.id}
                  data-campaign={c.id}
                  onClick={() => setOpenId(c.id)}
                  className="group cursor-pointer transition-colors duration-150 hover:bg-neutral-50"
                >
                  <td className={TD}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenId(c.id);
                      }}
                      className="text-left font-medium text-neutral-900 hover:text-accent-700 hover:underline"
                    >
                      {c.name}
                    </button>
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
                  <td className={`${TD} text-right`}>
                    <ChevronRight size={14} className="text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && <CampaignDetail key={open.id} campaign={open} decisions={decisions} summary={summary} onClose={() => setOpenId(null)} />}
    </section>
  );
}
