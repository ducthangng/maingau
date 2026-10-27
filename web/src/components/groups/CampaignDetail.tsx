import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FastForward, Loader2, X } from "lucide-react";
import type { Summary } from "../../types/contracts";
import type { Campaign } from "../../lib/campaigns";
import { latestByCustomer, type Decision } from "../../lib/decisions";
import { mockName } from "../../lib/customerMock";
import { pct, signedEur, tupleLabel } from "../../lib/format";
import { type CampaignOutcome, type MemberOutcome, fastForward, syncOutcome, useOutcomes } from "../../lib/outcomes";
import { Stat } from "./GroupCard";
import { Num } from "./Num";
import { plural } from "./model";

// One campaign in a pop-up (the Campaigns list): its settings and every customer it approved, from the
// decision log (field `campaign`). "Fast forward" simulates the 14 days after the send (lib/outcomes.ts): the
// contacted customers get an actual ΔCLV, the control group none.

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

  const outcome: CampaignOutcome | undefined = useOutcomes()[c.id];
  const byCustomer = useMemo(() => new Map((outcome?.outcomes ?? []).map((o) => [o.customer_id, o])), [outcome]);
  const nextAction = useMemo(() => new Map((outcome?.impact ?? []).map((x) => [x.customer_id, x])), [outcome]);
  const [running, setRunning] = useState(false);
  const [ffError, setFfError] = useState<string | null>(null);
  useEffect(() => {
    void syncOutcome(c.id);
  }, [c.id]);
  const runFastForward = async () => {
    setRunning(true);
    setFfError(null);
    try {
      await fastForward(c.id, members);
    } catch (err) {
      setFfError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };
  const t = outcome?.totals;
  const learned = (outcome?.learned ?? []).filter((k) => k.k_before !== null && k.k_after !== null && Math.abs(k.k_after - k.k_before) >= 0.005);

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
        className={`relative flex h-full max-h-full w-full flex-col rounded-2xl sm:h-[75vh] sm:w-[75vw] bg-white shadow-2xl ring-1 ring-neutral-200 transition duration-150 motion-reduce:transition-none ${
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

          {t && (
            <div className="rounded-xl border border-accent-100 bg-accent-50/40 p-5" data-campaign-outcome>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-accent-700">
                  Fast-forwarded {outcome.horizon_days} days · simulated
                </h3>
                <span className="text-xs text-neutral-500 tabular-nums">{fmtDate(outcome.simulated_at)}</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Bought" hint={`${t.expected_bought.toFixed(1)} expected`}>
                  <span className="tabular-nums">
                    {t.bought} of {t.simulated}
                  </span>
                </Stat>
                <Stat label="Actual Σ ΔCLV" hint="of the contacted">
                  <span className={`tabular-nums ${t.actual_delta_clv < 0 ? "text-red-700" : ""}`}>{signedEur(t.actual_delta_clv)}</span>
                </Stat>
                <Stat label="Expected Σ ΔCLV" hint="same customers">
                  <span className="tabular-nums">{signedEur(t.expected_delta_clv)}</span>
                </Stat>
                <Stat label="Actual − expected">
                  <span className={`tabular-nums ${t.actual_delta_clv - t.expected_delta_clv < 0 ? "text-red-700" : ""}`}>
                    {signedEur(t.actual_delta_clv - t.expected_delta_clv)}
                  </span>
                </Stat>
              </div>
              {(t.control > 0 || t.not_valued > 0) && (
                <p className="mt-3 text-xs text-neutral-500">
                  {t.control > 0 && `${plural(t.control, "control customer")} not sent, so no actual ΔCLV.`}
                  {t.not_valued > 0 && ` ${plural(t.not_valued, "customer")} skipped: the action is no longer valued for them.`}
                </p>
              )}
              {outcome.source === "api" ? (
                learned.length > 0 ? (
                  <div className="mt-3">
                    <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">Track record learned</div>
                    <ul className="mt-1.5 flex flex-wrap gap-2">
                      {learned.map((k) => (
                        <li
                          key={k.tuple_id}
                          className="rounded-full bg-white px-2.5 py-1 text-xs text-neutral-700 ring-1 ring-neutral-200 tabular-nums"
                          title={`bought ${k.bought} where ${k.expected} were expected · chance ${pct(k.p_before, 2)} → ${pct(k.p_after, 2)}`}
                        >
                          {tupleLabel(k.tuple_id)}: k {k.k_before!.toFixed(2)} → {k.k_after!.toFixed(2)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-neutral-500">The outcomes are in the engine's history; no track record moved noticeably.</p>
                )
              ) : null}
              {outcome.source === "api" ? (
                <p className="mt-3 text-xs text-neutral-600">
                  Each sent customer's outcome is remembered (offer paused: bought 365 days, dismissed 90, no response 30), so their next
                  best action moves on{outcome.impact ? `: ${plural(outcome.impact.length, "customer")} with a new proposal` : ""}.
                </p>
              ) : (
                <p className="mt-3 text-xs text-neutral-500">Static demo: simulated in this browser, the engine does not learn from it.</p>
              )}
            </div>
          )}

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
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="border-b border-neutral-200 bg-neutral-50">
                    <tr>
                      <th className={TH}>Customer</th>
                      <th className={TH}>Group</th>
                      <th className={TH}>In campaign</th>
                      <th className={`${TH} text-right`}>Expected ΔCLV</th>
                      <th className={`${TH} text-right`}>Actual ΔCLV</th>
                      <th className={`${TH} text-right`}>Chance</th>
                      <th className={TH}>Now</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {members.map((d) => {
                      const now = latest.get(d.customer_id);
                      const replaced = now && now.id !== d.id;
                      const next = nextAction.get(d.customer_id);
                      return (
                        <tr key={d.id} data-campaign-member={d.customer_id}>
                          <td className={TD}>
                            <Link to={`/worklist?c=${encodeURIComponent(d.customer_id)}`} className="font-medium text-neutral-900 hover:text-accent-700 hover:underline">
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
                          <td className={`${TD} text-right`}>
                            <Actual outcome={byCustomer.get(d.customer_id)} holdout={d.holdout} run={!!outcome} />
                          </td>
                          <td className={`${TD} text-right tabular-nums`}>{d.p_accept === null ? "—" : pct(d.p_accept)}</td>
                          <td className={`${TD} text-xs text-neutral-600`} title={next ? next.sentence : replaced && now.reason ? now.reason : undefined}>
                            {next ? (
                              <>
                                <span className="text-neutral-500">Next: </span>
                                <span className="text-neutral-900">{next.after.tuple === "NO_ACTION" ? "No action" : tupleLabel(next.after.tuple)}</span>
                                {next.after.waits_until && <div className="text-neutral-500">waits until {next.after.waits_until.slice(0, 10)}</div>}
                              </>
                            ) : replaced ? (
                              `${now.action[0].toUpperCase()}${now.action.slice(1)} later`
                            ) : d.settled ? (
                              d.holdout ? "Control, done" : "Sent"
                            ) : d.action === "overridden" ? (
                              "Approved (moved)"
                            ) : (
                              "Approved"
                            )}
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

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 px-8 py-4">
          <p className="text-xs text-neutral-500" role={ffError ? "alert" : undefined}>
            {ffError ? (
              <span className="text-red-700">{ffError}</span>
            ) : outcome ? (
              `Outcomes simulated ${outcome.horizon_days} days after the send.`
            ) : (
              "Simulate the 14 days after the send: who of the contacted bought, and their actual ΔCLV."
            )}
          </p>
          <button
            type="button"
            onClick={runFastForward}
            disabled={running || !!outcome || members.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          >
            {running ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FastForward className="size-4" aria-hidden />}
            {outcome ? "Fast-forwarded" : running ? "Simulating…" : "Fast forward 14 days"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Actual ΔCLV of one member: only a contacted customer who was simulated has one. */
function Actual({ outcome: o, holdout, run }: { outcome: MemberOutcome | undefined; holdout: boolean; run: boolean }) {
  if (holdout) return <span className="text-neutral-400" title="Control group: not sent, so no actual ΔCLV">—</span>;
  if (!run) return <span className="text-xs text-neutral-400">not yet</span>;
  if (!o || o.actual_delta_clv === undefined) return <span className="text-neutral-400" title="Not simulated: the action is no longer valued">—</span>;
  return (
    <span className="inline-flex flex-col items-end">
      <span className={`tabular-nums ${o.actual_delta_clv < 0 ? "text-red-700" : "text-neutral-900"}`}>{signedEur(o.actual_delta_clv)}</span>
      <span className="text-[11px] text-neutral-500">{o.status === "bought" ? "bought" : "did not buy"}</span>
    </span>
  );
}
