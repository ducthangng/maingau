import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCheck, CircleCheck, Users, X } from "lucide-react";
import CustomerModal from "../components/customer/CustomerModal";
import CampaignDialog, { type CampaignResult } from "../components/groups/CampaignDialog";
import { Stat } from "../components/groups/GroupCard";
import { Num } from "../components/groups/Num";
import { HOLDOUT_PCT, datedName, gateCounts, isServiceRow, planCampaign, sumOf } from "../components/groups/model";
import { ConfidenceRate, TIERS, channelLabel } from "../components/overview/ActionGroups";
import { offerName } from "../components/overview/model";
import { wholeEur } from "../components/overview/format";
import WorklistTable, { type RowAction } from "../components/worklist/WorklistTable";
import { isActionable } from "../components/worklist/model";
import { TIER_LABEL, TierChip, type Tier } from "../components/Chips";
import { WorklistSkeleton } from "../components/Skeleton";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { latestByCustomer, useDecisions } from "../lib/decisions";
import { tupleLabel } from "../lib/format";
import { GroupContext, groupView, latestMoves, recordMove, useGroupMoves } from "../lib/groupMoves";
import type { IndexRow } from "../types/contracts";

/**
 * One Offer · Channel · Tone group (/group/:tuple), optionally one urgency tier of it (?tier=P2), as
 * opened from the Overview: the customers in it, in the Worklist table. "Approve group…" names a
 * campaign and its control group, then "Save & Run" approves the ready customers (listed in /campaign).
 * Membership follows the people's moves (lib/groupMoves.ts): "Remove" takes a customer out, "Change to this
 * group" in the pop-up moves them to another group; a removed customer can be restored.
 */
export default function GroupDetail() {
  const { tuple = "" } = useParams();
  const [params] = useSearchParams();
  const tier = (TIERS as string[]).includes(params.get("tier") ?? "") ? (params.get("tier") as Tier) : null;
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : null;
  const log = useDecisions();
  const latest = useMemo(() => latestByCustomer(log), [log]);
  const moveLog = useGroupMoves();
  const moves = useMemo(() => latestMoves(moveLog), [moveLog]);
  const [selected, setSelected] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);
  const [flash, setFlash] = useState<CampaignResult | null>(null);

  const all = useMemo(() => (index.status === "ready" ? index.data : []), [index]);
  // Customers sent before are not on this page at all; a removed customer is in `removed` only, so
  // Approve group (Save & Run) takes exactly `rows`.
  const { rows, removed, sent } = useMemo(() => groupView(all, moves, latest, tuple, tier), [all, moves, latest, tuple, tier]);
  // The Worklist's bar scale and p reference over the whole snapshot, so bars read the same on both pages.
  const scale = useMemo(() => {
    const d = all.filter(isActionable).map((r) => Math.abs(r.delta_clv ?? 0));
    const p = all
      .filter(isActionable)
      .map((r) => r.p_accept)
      .filter((v): v is number => typeof v === "number")
      .sort((a, b) => a - b);
    return { max: Math.max(1, ...d), median: p.length ? p[Math.floor(p.length / 2)] : null };
  }, [all]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 8000);
    return () => window.clearTimeout(t);
  }, [flash]);

  if (index.status === "loading") return <WorklistSkeleton />;
  if (index.status === "error")
    return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">Could not load the group: {index.error}</div>;

  const offer = tuple.split("|")[0];
  const back = `/?${new URLSearchParams(tier ? { open: offer, tier } : { open: offer }).toString()}`;
  const delta = sumOf(rows, "delta_clv");
  const gates = gateCounts(rows, latest, tuple);
  const groups = [{ tuple, rows }];
  const scope = [offerName(offer), channelLabel(tuple), tier].filter(Boolean).join(" · ");
  const sales = rows.length > 0 && !rows.some(isServiceRow);

  // Remove needs a reason: it opens the customer pop-up with the remove reason showing.
  const open = (id: string) => {
    setRemoving(null);
    setSelected(id);
  };
  const remove = (r: IndexRow) => {
    setRemoving(r.customer_id);
    setSelected(r.customer_id);
  };
  // Back into this group with the valuation it had here (the engine's, or the option it was moved to).
  const restore = (r: IndexRow) => {
    const here = [...moveLog].reverse().find((m) => m.customer_id === r.customer_id && m.to === tuple);
    recordMove({
      customer_id: r.customer_id,
      from: tuple,
      to: tuple,
      reason: here?.reason ?? null,
      delta_clv: here ? here.delta_clv : (r.delta_clv ?? null),
      p_accept: here ? here.p_accept : (r.p_accept ?? null),
    });
  };
  const ready = sales && planCampaign(groups, latest, HOLDOUT_PCT, true).included.length > 0;

  return (
    <div className="space-y-6">
      <Link
        to={back}
        className="inline-flex items-center gap-1 rounded text-sm font-medium text-neutral-600 transition-colors duration-150 hover:text-neutral-900"
      >
        <ArrowLeft size={14} aria-hidden />
        {offerName(offer)} in the Overview
      </Link>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Group</div>
          <h1 className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight text-neutral-900">
            {tupleLabel(tuple)}
            {tier && (
              <span className="inline-flex items-center gap-1.5 text-sm font-medium text-neutral-600">
                <TierChip tier={tier} />
                {TIER_LABEL[tier]}
              </span>
            )}
          </h1>
          <p className="mt-1 text-[15px] text-neutral-600">
            The customers with this recommended action{tier ? ` in urgency tier ${tier}` : ""}. Open a customer for the details, or approve the
            group as a named campaign.
          </p>
        </div>
        {sales && (
          <button
            type="button"
            onClick={() => setApproveOpen(true)}
            disabled={!ready}
            title={ready ? "Name a campaign and its control group, then Save & Run" : "No ready customer left to approve"}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          >
            <CheckCheck className="size-4" aria-hidden />
            Approve group…
          </button>
        )}
      </header>

      {rows.length > 0 && (
        <div className="grid grid-cols-2 gap-4 rounded-xl border border-neutral-200 bg-white p-4 sm:grid-cols-4">
          <Stat label="Customers">
            <span className="inline-flex items-center gap-1.5 tabular-nums">
              <Users size={14} className="text-neutral-400" aria-hidden />
              {rows.length}
            </span>
          </Stat>
          <Stat label="Σ ΔCLV" hint={delta.missing ? `${delta.missing} without data` : undefined}>
            <Num col="delta_clv" value={delta.total} format={wholeEur} summary={summary ?? undefined} />
          </Stat>
          <Stat label="Confidence" hint="high or medium">
            <ConfidenceRate rows={rows} />
          </Stat>
          <Stat label="Approval">
            <span className="text-sm font-medium">
              {rows.length} to send
              {sent.length > 0 && (
                <span className="text-neutral-500" title="Approved before (in a campaign or one by one): not shown on this page">
                  {" "}
                  · {sent.length} sent before
                </span>
              )}
              {gates.blocked > 0 && (
                <span className="text-red-700" title="Retention risk or open service issue: Remove them if they should not be contacted">
                  {" "}
                  · {gates.blocked} do no harm
                </span>
              )}
            </span>
          </Stat>
        </div>
      )}

      <div aria-live="polite">
        {flash && (
          <div className="flex items-start gap-3 rounded-xl border border-accent-100 bg-accent-50 px-4 py-3 text-sm text-accent-700">
            <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="flex-1">
              Campaign <span className="font-medium">{flash.campaign}</span>: approved {flash.approved}, {flash.holdout} in the control group.{" "}
              <Link to="/campaign" className="font-medium underline underline-offset-2">
                See it in Campaigns
              </Link>
              .
            </p>
            <button type="button" onClick={() => setFlash(null)} aria-label="Dismiss" className="rounded p-0.5 hover:bg-accent-100">
              <X className="size-4" aria-hidden />
            </button>
          </div>
        )}
      </div>

      {/* The tables: 75% from xl up, where that still fits every column; the full width below. */}
      {rows.length === 0 && removed.length === 0 ? (
        <p className="rounded-xl border border-neutral-200 bg-white px-4 py-12 text-center text-sm text-neutral-500">
          No customer in {tupleLabel(tuple)}
          {tier ? ` with urgency ${tier}` : ""} in this snapshot.
        </p>
      ) : (
        <div className="space-y-6 xl:mx-auto xl:w-[75%]">
          {[
            {
              id: "sending",
              title: "Sending",
              list: rows,
              empty: sent.length ? "Nobody left to send: every other customer of this group was sent before or removed." : "Every customer of this group is removed.",
              action: ((row) => ({
                label: "Remove",
                title: "Take this customer out of the group, with a reason: Approve group leaves them out",
                danger: true,
                onClick: () => remove(row),
              })) as RowAction,
            },
            {
              id: "removed",
              title: "Removed",
              list: removed,
              empty: "Nobody removed: every customer above is sent with the group.",
              action: ((row) => ({ label: "Restore", title: "Put this customer back into the group", onClick: () => restore(row) })) as RowAction,
            },
          ].map((sec) => (
            <section key={sec.id} aria-labelledby={`${sec.id}-title`} className="space-y-3">
              <h2 id={`${sec.id}-title`} className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                {sec.title}
                <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium normal-case tracking-normal text-neutral-600 tabular-nums">
                  {sec.list.length}
                </span>
              </h2>
              <WorklistTable
                rows={sec.list}
                groups={null}
                summary={summary}
                decisions={latest}
                highlightedId={selected}
                rejectingId={rejecting}
                scale={scale}
                onOpen={open}
                onReject={setRejecting}
                rowAction={sec.action}
                empty={sec.empty}
              />
            </section>
          ))}
        </div>
      )}

      {selected && (
        <GroupContext.Provider value={{ tuple, removing, onMoved: () => setSelected(null) }}>
          <CustomerModal key={`${selected}-${removing ?? ""}`} id={selected} onClose={() => setSelected(null)} />
        </GroupContext.Provider>
      )}
      {approveOpen && (
        <CampaignDialog
          groups={groups}
          latest={latest}
          filter={{ offer, arch: "", pers: "" }}
          scope={scope}
          initialName={datedName(scope)}
          summary={summary ?? undefined}
          eyebrow={`Approve group · ${scope}`}
          confirmLabel="Save & Run"
          keepReview
          onClose={() => setApproveOpen(false)}
          onConfirmed={setFlash}
        />
      )}
    </div>
  );
}
