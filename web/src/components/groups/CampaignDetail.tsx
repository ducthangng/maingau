import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Campaign } from "../../lib/campaigns";
import { latestByCustomer, type Decision } from "../../lib/decisions";
import { mockName } from "../../lib/customerMock";
import { pct, signedEur, tupleLabel } from "../../lib/format";
import { Stat } from "./GroupCard";
import { Num } from "./Num";
import { plural } from "./model";

// One campaign in a pop-up (the Campaigns list): its settings and every customer it approved, from the
// decision log (field `campaign`). View only; nothing is sent.

const TH = "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const TD = "px-3 py-2 align-top";

export const fmtDate = (ts: string) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};

export default function CampaignDetail({
  campaign: c,
  decisions,
  summary,
  onClose,
}: {
  campaign: Campaign;
  decisions: Decision[];
  summary: Summary | undefined;
  onClose: () => void;
}) {
  const [shown, setShown] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const closing = useRef(false);

  // Fade in; lock page scroll; focus the close button and restore focus on close.
  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => setShown(true));
    closeRef.current?.focus();
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
      const focusable = panelRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
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

  const members = useMemo(
    () => decisions.filter((d) => d.campaign === c.id).sort((a, b) => Number(a.holdout) - Number(b.holdout) || a.customer_id.localeCompare(b.customer_id)),
    [decisions, c.id],
  );
  // A later decision (a reject, an override, a new approval) replaces the campaign's for that customer.
  const latest = useMemo(() => latestByCustomer(decisions), [decisions]);

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
        aria-labelledby="campaign-detail-title"
        className={`relative flex max-h-full w-full max-w-4xl flex-col rounded-2xl bg-white shadow-2xl ring-1 ring-neutral-200 transition duration-150 motion-reduce:transition-none ${
          shown ? "scale-100 opacity-100" : "scale-95 opacity-0"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 px-8 py-5">
          <div className="min-w-0">
            <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">Campaign · {c.scope}</div>
            <h2 id="campaign-detail-title" className="mt-0.5 break-words text-lg font-semibold tracking-tight text-neutral-900">
              {c.name}
            </h2>
            <p className="text-sm text-neutral-500 tabular-nums">
              {fmtDate(c.created_at)} · by {c.reviewer} · {c.id}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={requestClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-8 py-6">
          <div className="grid grid-cols-2 gap-4 rounded-xl bg-neutral-50 p-5 sm:grid-cols-5">
            <Stat label="Included">
              <span className="tabular-nums">{c.customers}</span>
            </Stat>
            <Stat label="Contacted">
              <span className="tabular-nums">{c.contacted}</span>
            </Stat>
            <Stat label="Control group" hint={`${c.holdout_pct}%, not contacted`}>
              <span className="tabular-nums">{c.holdout}</span>
            </Stat>
            <Stat label="Groups">
              <span className="tabular-nums">{c.groups.length}</span>
            </Stat>
            <Stat label="Σ ΔCLV" hint="of the contacted">
              <Num col="delta_clv" value={c.delta_clv} format={signedEur} summary={summary} />
            </Stat>
          </div>

          {c.groups.length > 0 && (
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Groups</h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {c.groups.map((g) => (
                  <li key={g} className="rounded-full bg-neutral-100 px-2.5 py-1 text-xs text-neutral-700">
                    {tupleLabel(g)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
              Customers · {plural(members.length, "customer")}
            </h3>
            {members.length === 0 ? (
              <p className="mt-2 text-sm text-neutral-500">The decisions of this campaign are no longer in this browser's decision log.</p>
            ) : (
              <div className="mt-2 overflow-x-auto rounded-lg border border-neutral-200">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="border-b border-neutral-200 bg-neutral-50">
                    <tr>
                      <th className={TH}>Customer</th>
                      <th className={TH}>Group</th>
                      <th className={TH}>In campaign</th>
                      <th className={`${TH} text-right`}>Expected ΔCLV</th>
                      <th className={`${TH} text-right`}>Chance</th>
                      <th className={TH}>Now</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {members.map((d) => {
                      const now = latest.get(d.customer_id);
                      const replaced = now && now.id !== d.id;
                      return (
                        <tr key={d.id} data-campaign-member={d.customer_id}>
                          <td className={TD}>
                            <Link to={`/customer/${d.customer_id}`} className="font-medium text-neutral-900 hover:text-accent-700 hover:underline">
                              {mockName(d.customer_id)}
                            </Link>
                            <div className="text-xs text-neutral-500 tabular-nums">{d.customer_id}</div>
                          </td>
                          <td className={`${TD} text-neutral-700`}>{tupleLabel(d.tuple_id)}</td>
                          <td className={TD}>
                            {d.holdout ? (
                              <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">Control group</span>
                            ) : (
                              <span className="rounded-full bg-accent-50 px-2 py-0.5 text-xs text-accent-700">Contacted</span>
                            )}
                          </td>
                          <td className={`${TD} text-right tabular-nums`}>{d.delta_clv === null ? "—" : signedEur(d.delta_clv)}</td>
                          <td className={`${TD} text-right tabular-nums`}>{d.p_accept === null ? "—" : pct(d.p_accept)}</td>
                          <td className={`${TD} text-xs text-neutral-600`} title={replaced && now.reason ? now.reason : undefined}>
                            {replaced ? `${now.action[0].toUpperCase()}${now.action.slice(1)} later` : d.action === "overridden" ? "Approved (moved)" : "Approved"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-neutral-200 px-8 py-4">
          <p className="text-xs text-neutral-500">Nothing is sent. The contacted customers are in the hand-off file; the control group is recorded only.</p>
        </div>
      </div>
    </div>
  );
}
