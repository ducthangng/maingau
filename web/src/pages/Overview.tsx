import { useCallback, useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, LifeBuoy } from "lucide-react";
import ActionTable from "../components/overview/ActionTable";
import { TIERS, tierBuckets } from "../components/overview/ActionGroups";
import TierSheet from "../components/overview/TierSheet";
import type { Tier } from "../components/Chips";
import { type Group, buildGroups } from "../components/groups/model";
import { latestByCustomer, useDecisions } from "../lib/decisions";
import { alreadySent, applyMoves, latestMoves, useGroupMoves } from "../lib/groupMoves";
import { wholeEur } from "../components/overview/format";
import { SERVICE_LINK, buildOverview } from "../components/overview/model";
import { Sourced } from "../components/Source";
import { asOf, colSrc } from "../components/worklist/model";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { OverviewSkeleton } from "../components/Skeleton";
import { NOT_ENOUGH } from "../lib/format";

/**
 * Orchestration home (prompts/ui-overview.md): which actions bring the most value and why. An action
 * opens its urgency tiers (P1–P5); a tier opens a sheet with its Offer · Channel · Tone groups, and a
 * group leads to its own page (/group/:tuple?tier=) with the customers in it.
 */
export default function Overview() {
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : null;
  // The engine's rows with the people's group moves applied (Remove, Change to this group on /group/:tuple).
  const moveLog = useGroupMoves();
  const rows = useMemo(
    () => (index.status === "ready" ? applyMoves(index.data, latestMoves(moveLog)).rows : null),
    [index, moveLog],
  );
  const model = useMemo(() => (rows ? buildOverview(rows) : null), [rows]);
  const log = useDecisions();
  const latest = useMemo(() => latestByCustomer(log), [log]);
  // Sales groups (one per chosen_tuple) by action, in the Groups page order, as the group pages show
  // them: customers sent before (approved, control group included) are left out of the tiers and groups.
  const groups = useMemo(() => {
    const byOffer = new Map<string, Group[]>();
    if (!rows) return byOffer;
    for (const g of buildGroups(rows.filter((r) => !alreadySent(latest.get(r.customer_id)))).sales) {
      const offer = g.rows[0]?.chosen_offer;
      if (offer) byOffer.set(offer, [...(byOffer.get(offer) ?? []), g]);
    }
    return byOffer;
  }, [rows, latest]);
  // The open action lives in the URL (?open=P-EN-02), so the back button restores it.
  const [params, setParams] = useSearchParams();
  const open = model?.actions.some((a) => a.offer === params.get("open")) ? params.get("open") : null;
  // The groups sheet of one urgency tier of the open action (?tier=P2).
  const tier = (TIERS as string[]).includes(params.get("tier") ?? "") ? (params.get("tier") as Tier) : null;
  const openAction = open ? model?.actions.find((a) => a.offer === open) : undefined;
  const openBucket = useMemo(
    () => (open && tier ? tierBuckets(groups.get(open) ?? []).find((b) => b.tier === tier && b.rows.length > 0) : undefined),
    [groups, open, tier],
  );
  const setTier = useCallback(
    (next: Tier | null) =>
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          if (next) p.set("tier", next);
          else p.delete("tier");
          return p;
        },
        { replace: !next },
      ),
    [setParams],
  );
  const setOpen = useCallback(
    (offer: string | null) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (offer) next.set("open", offer);
          else next.delete("open");
          next.delete("tier");
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  // Esc closes the open action from anywhere on the page; focus returns to its row.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key !== "Escape" || e.defaultPrevented || (el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      setOpen(null);
      document.querySelector<HTMLElement>(`[data-overview-row="${CSS.escape(open)}"]`)?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  // Wait for the summary too: without its labels every reason would flash "not enough data".
  if (index.status === "loading" || summaryState.status === "loading")
    return <OverviewSkeleton />;
  if (index.status === "error")
    return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">Could not load the overview: {index.error}</div>;
  if (!model) return null;
  const valueSrc = colSrc(summary, "delta_clv");
  const countSrc = colSrc(summary, "chosen_offer");

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Overview</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          Which actions bring the most value, and why. Open an action to see its urgency tiers, then the groups of a tier and the customers in each group.
        </p>
        <p className="mt-2 text-sm tabular-nums text-neutral-500">
          <Sourced src={countSrc} updatedAt={summary?.eval_time} sources={summary?.sources}>
            {model.actions.length} actions
          </Sourced>{" "}
          ·{" "}
          <Sourced src={countSrc} updatedAt={summary?.eval_time} sources={summary?.sources}>
            {model.customers} customers
          </Sourced>{" "}
          ·{" "}
          <Sourced src={valueSrc} updatedAt={asOf(summary, valueSrc)} sources={summary?.sources}>
            {model.actions.some((a) => a.valued) ? wholeEur(model.total) : NOT_ENOUGH}
          </Sourced>{" "}
          expected ΔCLV
        </p>
      </header>

      {model.service > 0 && (
        <Link
          to={SERVICE_LINK}
          className="group flex items-center gap-2 rounded-2xl border border-neutral-200 bg-white px-5 py-3 text-sm text-neutral-700 transition-colors duration-150 hover:bg-neutral-50"
        >
          <LifeBuoy size={16} className="text-neutral-500" aria-hidden />
          <span>
            <Sourced src={countSrc} updatedAt={summary?.eval_time} sources={summary?.sources}>
              <span className="font-semibold tabular-nums text-neutral-900">{model.service} service cases</span>
            </Sourced>{" "}
            need attention
          </span>
          <ArrowRight size={14} className="text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
        </Link>
      )}

      {/* 65% of the page and centred from lg up; the full width below, where the columns would not fit. */}
      <div className="lg:mx-auto lg:w-[65%]">
        <ActionTable
          actions={model.actions}
          summary={summary}
          groups={groups}
          open={open}
          onToggle={setOpen}
          onOpenTier={setTier}
        />
      </div>

      {openAction && openBucket && (
        <TierSheet
          key={`${openAction.offer}-${openBucket.tier}`}
          action={openAction}
          bucket={openBucket}
          summary={summary}
          latest={latest}
          onClose={() => setTier(null)}
        />
      )}
    </div>
  );
}
