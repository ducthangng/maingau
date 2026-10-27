import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Summary } from "../../types/contracts";
import { type Decision, REVIEWER, recordDecisions } from "../../lib/decisions";
import { saveCampaign } from "../../lib/campaigns";
import { signedEur } from "../../lib/format";
import { type Group, type GroupFilter, HOLDOUT_PCT, plural, planCampaign } from "./model";
import { Num } from "./Num";
import { Stat } from "./GroupCard";

export interface CampaignResult {
  campaign: string;
  approved: number;
  holdout: number;
}

const PCT_OPTIONS = Array.from({ length: 11 }, (_, i) => i * 5);

const field =
  "mt-1 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 transition-colors duration-150 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100";

// "Approve everything": every ready customer of the shown groups in one go, with a named campaign and a
// control group. Customers who need a second look stay out; they are approved per group (PreviewSheet).
export default function CampaignDialog({
  groups,
  latest,
  filter,
  scope,
  initialName,
  summary,
  onClose,
  onConfirmed,
}: {
  groups: Group[];
  latest: Map<string, Decision>;
  filter: GroupFilter;
  scope: string;
  initialName: string;
  summary: Summary | undefined;
  onClose: () => void;
  onConfirmed: (r: CampaignResult) => void;
}) {
  const [name, setName] = useState(initialName);
  const [pct, setPct] = useState(HOLDOUT_PCT);
  const [shown, setShown] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const closing = useRef(false);

  // Fade in; lock page scroll; focus the name and restore focus on close.
  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => setShown(true));
    nameRef.current?.focus();
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      prevFocus?.focus?.();
    };
  }, []);

  const requestClose = () => {
    if (closing.current) return;
    closing.current = true;
    setShown(false);
    window.setTimeout(onClose, 150);
  };

  // Esc closes; Tab stays inside the dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const plan = useMemo(() => planCampaign(groups, latest, pct), [groups, latest, pct]);
  const canConfirm = !!name.trim() && plan.included.length > 0;

  const confirm = () => {
    if (!canConfirm) return;
    const now = new Date();
    const id = `CMP-${now.getTime()}`;
    recordDecisions(
      plan.included.map((m) => ({
        customer_id: m.row.customer_id,
        action: "approved" as const,
        tuple_id: m.tuple,
        from_tuple: m.tuple,
        reason: null,
        reviewer: REVIEWER,
        delta_clv: m.row.delta_clv ?? null,
        p_accept: m.row.p_accept ?? null,
        group: m.tuple,
        holdout: m.holdout,
        campaign: id,
      })),
    );
    saveCampaign({
      id,
      name: name.trim(),
      created_at: now.toISOString(),
      reviewer: REVIEWER,
      offer: filter.offer || null,
      arch: filter.arch || null,
      pers: filter.pers || null,
      scope,
      holdout_pct: pct,
      groups: [...new Set(plan.included.map((m) => m.tuple))],
      customers: plan.included.length,
      contacted: plan.contacted,
      holdout: plan.holdout,
      delta_clv: plan.delta_clv,
    });
    onConfirmed({ campaign: name.trim(), approved: plan.contacted, holdout: plan.holdout });
    requestClose();
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" role="presentation">
      <div
        aria-hidden
        onClick={requestClose}
        className={`absolute inset-0 bg-neutral-900/25 transition-opacity duration-150 motion-reduce:transition-none ${shown ? "opacity-100" : "opacity-0"}`}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="campaign-title"
        className={`relative flex max-h-full w-full max-w-lg flex-col overflow-y-auto rounded-2xl bg-white shadow-2xl ring-1 ring-neutral-200 transition duration-150 motion-reduce:transition-none ${
          shown ? "scale-100 opacity-100" : "scale-95 opacity-0"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 px-6 py-4">
          <div className="min-w-0">
            <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">Approve everything · {scope}</div>
            <h2 id="campaign-title" className="mt-0.5 text-lg font-semibold tracking-tight text-neutral-900">
              Create a campaign
            </h2>
          </div>
          <button
            type="button"
            onClick={requestClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_9rem]">
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Campaign name</span>
              <input
                ref={nameRef}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                aria-invalid={!name.trim()}
                className={field}
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Control group</span>
              <select value={pct} onChange={(e) => setPct(Number(e.target.value))} className={`${field} tabular-nums`}>
                {PCT_OPTIONS.map((v) => (
                  <option key={v} value={v}>
                    {v}%
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4 rounded-xl bg-neutral-50 p-4 sm:grid-cols-3" aria-live="polite">
            <Stat label="Groups">
              <span className="tabular-nums">{plan.groups}</span>
            </Stat>
            <Stat label="Included" hint="ready customers">
              <span className="tabular-nums">{plan.included.length}</span>
            </Stat>
            <Stat label="Control group" hint={`${pct}%, not contacted`}>
              <span className="tabular-nums">{plan.holdout}</span>
            </Stat>
            <Stat label="Contacted">
              <span className="tabular-nums">{plan.contacted}</span>
            </Stat>
            <Stat label="Σ ΔCLV" hint="of the contacted">
              <Num col="delta_clv" value={plan.delta_clv} format={signedEur} summary={summary} />
            </Stat>
          </div>

          <ul className="space-y-1 text-xs text-neutral-500">
            <li>Only customers marked ready are included. The control group is fixed by a hash of the customer ID.</li>
            {plan.secondLook > 0 && (
              <li className="text-neutral-700">
                Not included: {plural(plan.secondLook, "customer")} with a second look or “do no harm”. Approve them per group.
              </li>
            )}
            {plan.skipped > 0 && <li>Skipped: {plural(plan.skipped, "customer")} already approved for the same action.</li>}
          </ul>
        </div>

        <div className="border-t border-neutral-200 px-6 py-4">
          <p className="text-xs text-neutral-500">Nothing is sent. Approved customers go to the decision log and the hand-off file.</p>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={requestClose}
              className="rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-sm font-medium text-neutral-700 transition-colors duration-150 hover:bg-neutral-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirm}
              disabled={!canConfirm}
              className="rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              Approve and create campaign
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
