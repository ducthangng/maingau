import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCheck, CircleCheck, Info, X } from "lucide-react";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { latestByCustomer, useDecisions } from "../lib/decisions";
import { useCampaigns } from "../lib/campaigns";
import { tupleLabel } from "../lib/format";
import GroupCard from "../components/groups/GroupCard";
import PreviewSheet, { type ConfirmResult } from "../components/groups/PreviewSheet";
import CampaignDialog, { type CampaignResult } from "../components/groups/CampaignDialog";
import CampaignList from "../components/groups/CampaignList";
import FilterBar from "../components/groups/FilterBar";
import ServiceList from "../components/groups/ServiceList";
import DecisionLog from "../components/groups/DecisionLog";
import {
  FILTER_PARAMS,
  HOLDOUT_PCT,
  buildGroups,
  defaultCampaignName,
  filterLabel,
  filterRows,
  hasFilter,
  planCampaign,
  readFilter,
} from "../components/groups/model";
import { GroupsSkeleton } from "../components/Skeleton";

// Bulk execution (prompts/agent-cards.md §1.2, §1.4): groups by chosen_tuple → preview sheet → approve for hand-off.
// Nothing is ever sent; approval writes the decision log and an export file.
// The Overview opens this page filtered to one action and segment (?offer=&arch=&pers=); "Approve
// everything" approves every ready customer of the shown groups as one named campaign.
export default function Groups() {
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : undefined;
  const log = useDecisions();
  const campaigns = useCampaigns();
  const latest = useMemo(() => latestByCustomer(log), [log]);
  const [params, setParams] = useSearchParams();
  const openTuple = params.get("tuple");
  const [flash, setFlash] = useState<ConfirmResult | CampaignResult | null>(null);
  const [campaignOpen, setCampaignOpen] = useState(false);

  const filter = readFilter(params);
  const filtered = hasFilter(filter);
  const { offer, arch, pers } = filter;
  const shownRows = useMemo(
    () => (index.status === "ready" ? filterRows(index.data, { offer, arch, pers }) : null),
    [index, offer, arch, pers],
  );
  const groups = useMemo(() => (shownRows ? buildGroups(shownRows) : null), [shownRows]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 8000);
    return () => window.clearTimeout(t);
  }, [flash]);

  // ?tuple= pointing at a service tuple: bring the service list into view instead of opening a sales preview.
  const serviceDeepLink = !filtered && !!openTuple && !!groups?.service.some((r) => r.chosen_tuple === openTuple);
  useEffect(() => {
    if (serviceDeepLink) document.getElementById("service-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [serviceDeepLink]);

  if (index.status === "loading") return <GroupsSkeleton />;
  if (index.status === "error") return <p className="text-red-700">Could not load index.json: {index.error}</p>;
  if (!groups) return null;

  // Opening and closing a group keeps the action and segment filter in the URL.
  const open = (tuple: string) =>
    setParams((p) => {
      p.set("tuple", tuple);
      return p;
    });
  const close = () =>
    setParams(
      (p) => {
        p.delete("tuple");
        return p;
      },
      { replace: true },
    );
  const resetFilter = () =>
    setParams((p) => {
      for (const k of FILTER_PARAMS) p.delete(k);
      return p;
    });

  const openGroup = openTuple ? groups.sales.find((g) => g.tuple === openTuple) : undefined;
  const openIsService = !openGroup && serviceDeepLink;
  const salesCustomers = groups.sales.reduce((n, g) => n + g.rows.length, 0);
  const scope = filterLabel(filter, index.data);
  const canApproveAll = planCampaign(groups.sales, latest, HOLDOUT_PCT).included.length > 0;

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Groups</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          Customers who share the same recommended action. Approve a group after a preview of who is in, who is left out and why.
          Nothing is sent: approval produces a hand-off file for the campaign tool.
        </p>
        <p className="mt-2 text-sm text-neutral-500 tabular-nums">
          {groups.sales.length} sales groups · {salesCustomers} customers
          {filtered ? "" : ` · ${groups.service.length} service · ${groups.noAction} no action`}
        </p>
      </header>

      {filtered && <FilterBar label={scope} onReset={resetFilter} />}

      <div aria-live="polite">
        {flash && (
          <div className="flex items-start gap-3 rounded-xl border border-accent-100 bg-accent-50 px-4 py-3 text-sm text-accent-700">
            <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="flex-1">
              {"campaign" in flash ? (
                <>
                  Campaign <span className="font-medium">{flash.campaign}</span>: approved {flash.approved}, {flash.holdout} in the control group.
                </>
              ) : (
                <>
                  Approved {flash.approved} for <span className="font-medium">{tupleLabel(flash.tuple)}</span>
                  {flash.holdout ? ` and kept ${flash.holdout} as holdout` : ""}.
                </>
              )}{" "}
              Export the hand-off file from the decision log below.
            </p>
            <button type="button" onClick={() => setFlash(null)} aria-label="Dismiss" className="rounded p-0.5 hover:bg-accent-100">
              <X className="size-4" aria-hidden />
            </button>
          </div>
        )}
        {openTuple && !openGroup && (
          <div className="flex items-start gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700">
            <Info className="mt-0.5 size-4 shrink-0 text-neutral-500" aria-hidden />
            <p className="flex-1">
              {openIsService
                ? `${tupleLabel(openTuple)} is a service action. Handle each customer individually in the service list below.`
                : openTuple === "NO_ACTION"
                  ? "“No action” is not a group: there is nothing to approve."
                  : filtered
                    ? `No group for ${tupleLabel(openTuple)} under this filter.`
                    : `No open group for ${tupleLabel(openTuple)} in this snapshot.`}
            </p>
            <button type="button" onClick={close} aria-label="Dismiss" className="rounded p-0.5 hover:bg-neutral-100">
              <X className="size-4" aria-hidden />
            </button>
          </div>
        )}
      </div>

      <section aria-labelledby="sales-title">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="sales-title" className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
            Sales groups · sorted by Σ expected ΔCLV
          </h2>
          <button
            type="button"
            onClick={() => setCampaignOpen(true)}
            disabled={!canApproveAll}
            title={canApproveAll ? "Approve every ready customer of the groups below as one campaign" : "No ready customer left to approve"}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          >
            <CheckCheck className="size-4" aria-hidden />
            Approve everything…
          </button>
        </div>
        {groups.sales.length === 0 ? (
          <p className="rounded-xl border border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
            {filtered ? "No sales group for this action and segment." : "No sales groups in this snapshot."}
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {groups.sales.map((g) => (
              <GroupCard key={g.tuple} group={g} summary={summary} latest={latest} onOpen={open} />
            ))}
          </div>
        )}
      </section>

      <CampaignList campaigns={campaigns} summary={summary} />

      {filtered ? (
        <p className="text-sm text-neutral-500">Service cases are not part of this action. Reset the filter to see the service list.</p>
      ) : (
        <ServiceList rows={groups.service} summary={summary} highlight={openIsService} />
      )}

      <DecisionLog log={log} summary={summary} />

      {openGroup && (
        <PreviewSheet key={openGroup.tuple} group={openGroup} summary={summary} latest={latest} onClose={close} onConfirmed={setFlash} />
      )}
      {campaignOpen && (
        <CampaignDialog
          groups={groups.sales}
          latest={latest}
          filter={filter}
          scope={scope}
          initialName={defaultCampaignName(filter, index.data)}
          summary={summary}
          onClose={() => setCampaignOpen(false)}
          onConfirmed={setFlash}
        />
      )}
    </div>
  );
}
