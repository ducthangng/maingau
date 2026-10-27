import { useCampaigns } from "../lib/campaigns";
import { loadSummary, useLoad } from "../lib/data";
import CampaignList from "../components/groups/CampaignList";

/** Every campaign saved so far: from "Approve everything" on Groups, or "Save & Run" on a group page. */
export default function Campaigns() {
  const campaigns = useCampaigns();
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : undefined;
  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Campaigns</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          The campaigns saved so far, newest first, with their control group. Nothing is sent: approval produces a hand-off file for the
          campaign tool.
        </p>
      </header>
      <CampaignList campaigns={campaigns} summary={summary} />
    </div>
  );
}
