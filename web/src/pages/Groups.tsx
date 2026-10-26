import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CircleCheck, Info, X } from "lucide-react";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { latestByCustomer, useDecisions } from "../lib/decisions";
import { tupleLabel } from "../lib/format";
import GroupCard from "../components/groups/GroupCard";
import PreviewSheet, { type ConfirmResult } from "../components/groups/PreviewSheet";
import ServiceList from "../components/groups/ServiceList";
import DecisionLog from "../components/groups/DecisionLog";
import { buildGroups } from "../components/groups/model";

// Bulk execution (prompts/agent-cards.md §1.2, §1.4): groups by chosen_tuple → preview sheet → approve for hand-off.
// Nothing is ever sent; approval writes the decision log and an export file.
export default function Groups() {
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : undefined;
  const log = useDecisions();
  const latest = useMemo(() => latestByCustomer(log), [log]);
  const [params, setParams] = useSearchParams();
  const openTuple = params.get("tuple");
  const [flash, setFlash] = useState<ConfirmResult | null>(null);

  const groups = useMemo(() => (index.status === "ready" ? buildGroups(index.data) : null), [index]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 8000);
    return () => window.clearTimeout(t);
  }, [flash]);

  // ?tuple= pointing at a service tuple: bring the service list into view instead of opening a sales preview.
  const serviceDeepLink = !!openTuple && !!groups?.service.some((r) => r.chosen_tuple === openTuple);
  useEffect(() => {
    if (serviceDeepLink) document.getElementById("service-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [serviceDeepLink]);

  if (index.status === "loading") return <p className="text-neutral-500">Loading…</p>;
  if (index.status === "error") return <p className="text-red-700">Could not load index.json: {index.error}</p>;
  if (!groups) return null;

  const open = (tuple: string) => setParams({ tuple });
  const close = () =>
    setParams(
      (p) => {
        p.delete("tuple");
        return p;
      },
      { replace: true },
    );

  const openGroup = openTuple ? groups.sales.find((g) => g.tuple === openTuple) : undefined;
  const openIsService = !openGroup && serviceDeepLink;
  const salesCustomers = groups.sales.reduce((n, g) => n + g.rows.length, 0);

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Groups</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          Customers who share the same recommended action. Approve a group after a preview of who is in, who is left out and why.
          Nothing is sent: approval produces a hand-off file for the campaign tool.
        </p>
        <p className="mt-2 text-sm text-neutral-500 tabular-nums">
          {groups.sales.length} sales groups · {salesCustomers} customers · {groups.service.length} service · {groups.noAction} no action
        </p>
      </header>

      <div aria-live="polite">
        {flash && (
          <div className="flex items-start gap-3 rounded-xl border border-accent-100 bg-accent-50 px-4 py-3 text-sm text-accent-700">
            <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="flex-1">
              Approved {flash.approved} for <span className="font-medium">{tupleLabel(flash.tuple)}</span>
              {flash.holdout ? ` and kept ${flash.holdout} as holdout` : ""}. Export the hand-off file from the decision log below.
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
                  : `No open group for ${tupleLabel(openTuple)} in this snapshot.`}
            </p>
            <button type="button" onClick={close} aria-label="Dismiss" className="rounded p-0.5 hover:bg-neutral-100">
              <X className="size-4" aria-hidden />
            </button>
          </div>
        )}
      </div>

      <section aria-labelledby="sales-title">
        <h2 id="sales-title" className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Sales groups · sorted by Σ expected ΔCLV
        </h2>
        {groups.sales.length === 0 ? (
          <p className="rounded-xl border border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">No sales groups in this snapshot.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {groups.sales.map((g) => (
              <GroupCard key={g.tuple} group={g} summary={summary} latest={latest} onOpen={open} />
            ))}
          </div>
        )}
      </section>

      <ServiceList rows={groups.service} summary={summary} highlight={openIsService} />

      <DecisionLog log={log} summary={summary} />

      {openGroup && (
        <PreviewSheet key={openGroup.tuple} group={openGroup} summary={summary} latest={latest} onClose={close} onConfirmed={setFlash} />
      )}
    </div>
  );
}
