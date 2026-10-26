import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, X } from "lucide-react";
import type { IndexRow, Summary } from "../../types/contracts";
import { type Decision, REVIEWER, recordDecisions } from "../../lib/decisions";
import { eur, pct, signedEur, tupleLabel } from "../../lib/format";
import { ConfidenceDot } from "../Chips";
import { type Gate, type Group, type Member, type Reason, HOLDOUT_PCT, assess, holdoutOf, plural, sumOf } from "./model";
import { Num, conversions } from "./Num";
import { Stat } from "./GroupCard";

export interface ConfirmResult {
  tuple: string;
  approved: number;
  holdout: number;
}

const GATE_HEADING: Record<Gate, { title: string; note: string }> = {
  ready: { title: "Ready", note: "Included by default." },
  review: { title: "Needs a second look", note: "Excluded by default. Tick to include after checking the reason." },
  blocked: { title: "Do no harm", note: "A4 or open service issue: never part of a bulk sales approval." },
};

const REASON_STYLE: Record<Reason["kind"], string> = {
  do_no_harm: "bg-red-50 text-red-700 ring-red-200",
  outlier: "bg-red-50 text-red-700 ring-red-200",
  checklist: "bg-amber-50 text-amber-800 ring-amber-200",
  no_data: "bg-neutral-100 text-neutral-600 ring-neutral-200",
  low_confidence: "bg-neutral-100 text-neutral-600 ring-neutral-200",
  prior_decision: "bg-amber-50 text-amber-800 ring-amber-200",
};

function Switch({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full items-start gap-3 rounded-lg p-2 text-left transition-colors duration-150 hover:bg-neutral-50"
    >
      <span
        aria-hidden
        className={`mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors duration-200 ${checked ? "bg-accent-600" : "bg-neutral-300"}`}
      >
        <span className={`size-4 rounded-full bg-white shadow transition-transform duration-200 ${checked ? "translate-x-4" : ""}`} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-neutral-900">{label}</span>
        <span className="block text-xs text-neutral-500">{hint}</span>
      </span>
    </button>
  );
}

export default function PreviewSheet({
  group,
  summary,
  latest,
  onClose,
  onConfirmed,
}: {
  group: Group;
  summary: Summary | undefined;
  latest: Map<string, Decision>;
  onClose: () => void;
  onConfirmed: (r: ConfirmResult) => void;
}) {
  const [holdoutOn, setHoldoutOn] = useState(true);
  const [excludeLow, setExcludeLow] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [shown, setShown] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const closing = useRef(false);

  // Slide in; lock page scroll; focus the sheet and restore focus on close.
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
    window.setTimeout(onClose, 180);
  };

  // Esc closes; Tab stays inside the sheet.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
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

  // An earlier reject / override moves the customer to "second look": never silently re-approved in bulk.
  const members = useMemo(
    () => group.rows.map((r) => assess(r, excludeLow, latest.get(r.customer_id), group.tuple)),
    [group.rows, group.tuple, excludeLow, latest],
  );

  const isIncluded = (m: Member) => m.gate !== "blocked" && (overrides[m.row.customer_id] ?? m.gate === "ready");
  const included = members.filter(isIncluded);
  const holdout = included.filter((m) => holdoutOf(m.row.customer_id, holdoutOn));
  const contacted: IndexRow[] = included.filter((m) => !holdoutOf(m.row.customer_id, holdoutOn)).map((m) => m.row);
  const delta = sumOf(contacted, "delta_clv");
  const p = sumOf(contacted, "p_accept");
  const cost = sumOf(contacted, "contact_cost");
  const excluded = members.length - included.length;

  const byGate: Record<Gate, Member[]> = { ready: [], review: [], blocked: [] };
  for (const m of members) byGate[m.gate].push(m);

  const confirm = () => {
    if (!included.length) return;
    recordDecisions(
      included.map((m) => ({
        customer_id: m.row.customer_id,
        action: "approved" as const,
        tuple_id: group.tuple,
        from_tuple: group.tuple,
        reason: null,
        reviewer: REVIEWER,
        delta_clv: m.row.delta_clv ?? null,
        p_accept: m.row.p_accept ?? null,
        group: group.tuple,
        holdout: holdoutOf(m.row.customer_id, holdoutOn),
      })),
    );
    onConfirmed({ tuple: group.tuple, approved: contacted.length, holdout: holdout.length });
    requestClose();
  };

  return (
    <div className="fixed inset-0 z-40" role="presentation">
      <div
        aria-hidden
        onClick={requestClose}
        className={`absolute inset-0 bg-neutral-900/25 transition-opacity duration-200 motion-reduce:transition-none ${shown ? "opacity-100" : "opacity-0"}`}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="group-sheet-title"
        className={`absolute inset-y-0 right-0 flex w-full max-w-[640px] flex-col bg-white shadow-2xl ring-1 ring-neutral-200 transition-transform duration-200 ease-out motion-reduce:transition-none ${
          shown ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 px-6 py-4">
          <div className="min-w-0">
            <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">Approve group · preview</div>
            <h2 id="group-sheet-title" className="mt-0.5 text-lg font-semibold tracking-tight text-neutral-900">
              {tupleLabel(group.tuple)}
            </h2>
            <p className="text-sm text-neutral-500">
              {plural(group.rows.length, "customer")} with this recommended action · {excluded} excluded
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={requestClose}
            aria-label="Close preview"
            className="rounded-lg p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Summary */}
          <div className="grid grid-cols-2 gap-4 rounded-xl bg-neutral-50 p-4 sm:grid-cols-4" aria-live="polite">
            <Stat label="Included" hint={holdout.length ? `+ ${holdout.length} holdout` : holdoutOn ? "0 holdout" : "no holdout"}>
              <span className="tabular-nums">{contacted.length}</span>
            </Stat>
            <Stat label="Σ ΔCLV">
              <Num col="delta_clv" value={delta.total} format={signedEur} summary={summary} />
            </Stat>
            <Stat label="Exp. conv. (Σ p)">
              <Num col="p_accept" value={p.total} format={conversions} summary={summary} />
            </Stat>
            <Stat label="Contact cost">
              <Num col="contact_cost" value={cost.total} format={(v) => eur(v, true)} summary={summary} />
            </Stat>
          </div>

          {/* Controls */}
          <div className="mt-4 grid gap-1 sm:grid-cols-2">
            <Switch
              checked={holdoutOn}
              onChange={setHoldoutOn}
              label={`Holdout control group (${HOLDOUT_PCT}%)`}
              hint="Fixed by a hash of the customer ID. Recorded, not contacted, so uplift can be measured."
            />
            <Switch
              checked={excludeLow}
              onChange={setExcludeLow}
              label="Exclude low confidence"
              hint="Moves customers whose p rests on fewer than 30 observations to “second look”."
            />
          </div>

          {/* Members */}
          {(["ready", "review", "blocked"] as const).map((gate) =>
            byGate[gate].length ? (
              <section key={gate} className="mt-6" aria-labelledby={`gate-${gate}`}>
                <div className="mb-2 flex items-baseline justify-between gap-2">
                  <h3 id={`gate-${gate}`} className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                    {GATE_HEADING[gate].title} · {byGate[gate].length}
                  </h3>
                  <span className="text-right text-xs text-neutral-400">{GATE_HEADING[gate].note}</span>
                </div>
                <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200">
                  {byGate[gate].map((m) => (
                    <MemberRow
                      key={m.row.customer_id}
                      member={m}
                      included={isIncluded(m)}
                      holdout={isIncluded(m) && holdoutOf(m.row.customer_id, holdoutOn)}
                      previous={latest.get(m.row.customer_id)}
                      summary={summary}
                      onToggle={(v) => setOverrides((o) => ({ ...o, [m.row.customer_id]: v }))}
                    />
                  ))}
                </ul>
              </section>
            ) : null,
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-neutral-200 bg-white px-6 py-4">
          <p className="text-xs text-neutral-500">
            Nothing is sent. Approved customers go to the decision log and the hand-off file for the campaign tool; holdout customers are logged
            but left out of the export.
          </p>
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
              disabled={!included.length}
              className="rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              Approve {contacted.length}
              {holdout.length ? ` + ${holdout.length} holdout` : ""} for hand-off
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MemberRow({
  member,
  included,
  holdout,
  previous,
  summary,
  onToggle,
}: {
  member: Member;
  included: boolean;
  holdout: boolean;
  previous: Decision | undefined;
  summary: Summary | undefined;
  onToggle: (v: boolean) => void;
}) {
  const { row, gate, reasons } = member;
  const blocked = gate === "blocked";
  const secondLook = gate === "review" && included;
  const id = `inc-${row.customer_id}`;

  return (
    <li className={`flex items-start gap-3 px-3 py-2.5 transition-colors duration-150 ${included ? "bg-white" : "bg-neutral-50/60"}`}>
      <input
        id={id}
        type="checkbox"
        checked={included}
        disabled={blocked}
        onChange={(e) => onToggle(e.target.checked)}
        aria-label={`Include ${row.customer_id}`}
        title={blocked ? "Do no harm: cannot be included in a bulk sales approval" : undefined}
        className="mt-1 size-4 shrink-0 cursor-pointer accent-accent-600 disabled:cursor-not-allowed"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Link
            to={`/customer/${row.customer_id}`}
            target="_blank"
            rel="noopener"
            className="inline-flex items-center gap-0.5 rounded text-sm font-medium text-neutral-900 hover:text-accent-700"
            title="Open the customer page in a new tab"
          >
            {row.customer_id}
            <ArrowUpRight className="size-3.5 text-neutral-400" aria-hidden />
          </Link>
          {row.archetype && (
            <span className="text-xs text-neutral-500">
              {row.archetype}
              {row.archetype_name ? ` · ${row.archetype_name}` : ""}
            </span>
          )}
          {holdout && (
            <span
              title="Control group: logged as approved, not contacted, left out of the export"
              className="rounded bg-accent-50 px-1.5 py-0.5 text-[11px] font-medium text-accent-700 ring-1 ring-inset ring-accent-100"
            >
              Holdout
            </span>
          )}
          {previous && !reasons.some((r) => r.kind === "prior_decision") && (
            <span className="text-[11px] text-neutral-400" title={`${previous.action} by ${previous.reviewer} · ${previous.ts}`}>
              {previous.action} earlier
            </span>
          )}
        </div>
        {reasons.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {reasons.map((r) => (
              <span key={r.label} title={r.title} className={`rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset ${REASON_STYLE[r.kind]}`}>
                {r.label}
              </span>
            ))}
            {secondLook && <span className="px-1 py-0.5 text-[11px] font-medium text-accent-700">included after second look</span>}
          </div>
        )}
      </div>
      <div className="shrink-0 text-right">
        <div className="text-sm font-medium">
          <Num col="delta_clv" value={row.delta_clv} format={signedEur} summary={summary} />
        </div>
        <div className="mt-0.5 flex items-center justify-end gap-2 text-xs text-neutral-500">
          <span>
            p <Num col="p_accept" value={row.p_accept} format={(v) => pct(v)} summary={summary} />
          </span>
          <ConfidenceDot confidence={row.confidence} />
        </div>
      </div>
    </li>
  );
}
