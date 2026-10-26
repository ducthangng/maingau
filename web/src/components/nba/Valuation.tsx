import type { ReactNode } from "react";
import type { Fact, PSource, Valuation } from "../../types/contracts";
import { eur, pct, signedEur } from "../../lib/format";
import { Sourced } from "../Source";
import { ConfidenceDot } from "../Chips";
import { Missing, type Sources } from "./ui";

// C4 valuation as given by the engine. The three waterfall terms are shown so a marketer can
// re-check the arithmetic; the total is always the engine's delta_clv, never a frontend sum.

const V = "engine.valuation";

export const FORMULA = "ΔCLV = p × (accept − now) + (1 − p) × (reject − now) − contact cost";

function Row({ label, sub, children }: { label: string; sub?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <div className="min-w-0">
        <div className="text-sm text-neutral-700">{label}</div>
        {sub && <div className="text-xs text-neutral-500">{sub}</div>}
      </div>
      <div className="shrink-0 text-right text-sm tabular-nums">{children}</div>
    </div>
  );
}

export function ClvImpact({ v, sources, clvFact }: { v: Valuation | null | undefined; sources: Sources; clvFact?: Fact }) {
  if (!v) return <Missing />;
  const gain = v.clv_after_accept - v.clv_now_model;
  const change = v.clv_after_reject - v.clv_now_model;
  const p = v.p_accept;
  const terms = [
    { key: "accept", label: "p × gain", title: "p × (CLV if accepted − CLV now)", value: p * gain, src: `${V}.clv_after_accept` },
    { key: "reject", label: "(1 − p) × change", title: "(1 − p) × (CLV if not accepted − CLV now)", value: (1 - p) * change || 0, src: `${V}.clv_after_reject` },
    { key: "cost", label: "− contact cost", title: "contact cost of the channel", value: -v.contact_cost || 0, src: `${V}.contact_cost` },
  ];

  // Floating waterfall: each bar starts where the previous one ended. Widths only.
  let run = 0;
  const steps = terms.map((t) => {
    const start = run;
    run += t.value;
    return { ...t, start, end: run };
  });
  const points = [0, v.delta_clv, ...steps.flatMap((s) => [s.start, s.end])];
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const span = hi - lo || 1;
  const pos = (x: number) => ((x - lo) / span) * 100;
  const bar = (a: number, b: number) => ({
    left: `${pos(Math.min(a, b))}%`,
    width: `${Math.max(((Math.abs(b - a)) / span) * 100, 0.6)}%`,
  });

  return (
    <div className="space-y-3">
      <div className="divide-y divide-neutral-100 rounded-lg border border-neutral-200 px-3">
        <Row
          label="CLV now (model)"
          sub={
            <>
              shown CLV (customer_value.clv_eur):{" "}
              <Sourced src="customer_value.clv_eur" updatedAt={clvFact?.updated_at} sources={sources}>
                {eur(v.clv_now_shown)}
              </Sourced>
            </>
          }
        >
          <Sourced src={`${V}.clv_now_model`} sources={sources}>{eur(v.clv_now_model, true)}</Sourced>
        </Row>
        <Row
          label="CLV if accepted"
          sub={
            <>
              gain <Sourced src={`${V}.clv_after_accept`} sources={sources}>{signedEur(gain)}</Sourced>
            </>
          }
        >
          <Sourced src={`${V}.clv_after_accept`} sources={sources}>{eur(v.clv_after_accept, true)}</Sourced>
        </Row>
        <Row
          label="CLV if not accepted"
          sub={
            change === 0 ? (
              "unchanged"
            ) : (
              <>
                change <Sourced src={`${V}.clv_after_reject`} sources={sources}>{signedEur(change)}</Sourced>
              </>
            )
          }
        >
          <Sourced src={`${V}.clv_after_reject`} sources={sources}>{eur(v.clv_after_reject, true)}</Sourced>
        </Row>
        <Row label="Contact cost">
          <Sourced src={`${V}.contact_cost`} sources={sources}>{eur(v.contact_cost, true)}</Sourced>
        </Row>
      </div>

      <div className="space-y-1.5" role="img" aria-label={`Waterfall to expected ΔCLV ${signedEur(v.delta_clv)}`}>
        {steps.map((s) => (
          <div key={s.key} className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_6rem] items-center gap-2 text-xs">
            <span className="truncate text-neutral-600" title={s.title}>{s.label}</span>
            <div className="relative h-3 rounded bg-neutral-50">
              <div className="absolute inset-y-0 w-px bg-neutral-300" style={{ left: `${pos(0)}%` }} />
              <div
                className={`absolute inset-y-0.5 rounded-sm ${s.value >= 0 ? "bg-accent-500" : "bg-red-300"}`}
                style={bar(s.start, s.end)}
              />
            </div>
            <Sourced src={s.src} sources={sources}>
              <span className="block text-right tabular-nums text-neutral-700">≈ {signedEur(s.value)}</span>
            </Sourced>
          </div>
        ))}
        <div className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_6rem] items-center gap-2 border-t border-neutral-100 pt-1.5 text-xs">
          <span className="font-medium text-neutral-900">= expected ΔCLV</span>
          <div className="relative h-3 rounded bg-neutral-50">
            <div className="absolute inset-y-0 w-px bg-neutral-300" style={{ left: `${pos(0)}%` }} />
            <div className="absolute inset-y-0.5 rounded-sm bg-neutral-800" style={bar(0, v.delta_clv)} />
          </div>
          <Sourced src={`${V}.delta_clv`} sources={sources}>
            <span className="block text-right font-semibold tabular-nums text-neutral-900">{signedEur(v.delta_clv)}</span>
          </Sourced>
        </div>
      </div>
      <p className="font-mono text-[11px] leading-relaxed text-neutral-500">{FORMULA}</p>
      <p className="text-[11px] text-neutral-400">Terms are shown for re-checking (≈, rounded); the total is the engine's value.</p>
    </div>
  );
}

const LEVELS: { id: PSource["level"]; label: string }[] = [
  { id: "offer_channel_tone", label: "offer × channel × tone" },
  { id: "offer_channel", label: "offer × channel" },
  { id: "offer", label: "offer" },
  { id: "global", label: "catalog average" },
];

function count(n: number | undefined, sources: Sources, src = "nba_action_history.response") {
  if (n === undefined || n === null) return <Missing />;
  return (
    <Sourced src={src} sources={sources}>
      <span className="tabular-nums">{n}</span>
    </Sourced>
  );
}

export function SuccessEvidence({ v, sources }: { v: Valuation | null | undefined; sources: Sources }) {
  if (!v) return <Missing />;
  const p = v.p_accept;
  const ps = v.p_source;
  const n = ps?.n_treated;
  const widthP = `${Math.min(Math.max(p * 100, 0), 100)}%`;

  return (
    <div className="space-y-3">
      <div>
        <div className="flex h-3 overflow-hidden rounded-full bg-neutral-200" aria-hidden>
          <div className="bg-accent-500 transition-[width] duration-200" style={{ width: widthP }} />
        </div>
        <div className="mt-1.5 flex justify-between text-xs">
          <span className="text-accent-700">
            Success p{" "}
            <Sourced src={`${V}.p_accept`} sources={sources}>
              <span className="font-semibold tabular-nums">{pct(p)}</span>
            </Sourced>
          </span>
          <span className="text-neutral-500">
            No success 1 − p{" "}
            <Sourced src={`${V}.p_accept`} sources={sources}>
              <span className="tabular-nums">{pct(1 - p)}</span>
            </Sourced>
          </span>
        </div>
      </div>

      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-xs">
        <dt className="text-neutral-500">Treated</dt>
        <dd className="text-neutral-800">
          {count(ps?.conv_treated, sources)} conversions of n = {count(n, sources)}
        </dd>
        <dt className="text-neutral-500">Control</dt>
        <dd className="text-neutral-800">
          {count(ps?.conv_control, sources)} of {count(ps?.n_control, sources)}
          {" · baseline "}
          {ps?.baseline_control === null || ps?.baseline_control === undefined ? (
            <Missing />
          ) : (
            <Sourced src={`${V}.p_source.baseline_control`} sources={sources}>
              <span className="tabular-nums">{pct(ps.baseline_control)}</span>
            </Sourced>
          )}
        </dd>
        <dt className="text-neutral-500">Method</dt>
        <dd className="text-neutral-800">
          <Sourced src={`${V}.p_source.mode`} sources={sources}>{ps?.mode ?? <Missing />}</Sourced>
        </dd>
        <dt className="text-neutral-500">Backoff level</dt>
        <dd>
          {ps?.level === "assumption" ? (
            <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-800 ring-1 ring-inset ring-amber-200">
              assumption (no history)
            </span>
          ) : (
            <ol className="flex flex-wrap items-center gap-1" aria-label="Backoff ladder">
              {LEVELS.map((l, i) => (
                <li key={l.id} className="flex items-center gap-1">
                  <span
                    className={`rounded px-1.5 py-0.5 ${
                      ps?.level === l.id ? "bg-accent-50 font-medium text-accent-700 ring-1 ring-inset ring-accent-100" : "text-neutral-400"
                    }`}
                    aria-current={ps?.level === l.id ? "step" : undefined}
                  >
                    {l.label}
                  </span>
                  {i < LEVELS.length - 1 && <span className="text-neutral-300">→</span>}
                </li>
              ))}
            </ol>
          )}
        </dd>
        <dt className="text-neutral-500">Confidence</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <Sourced src={`${V}.confidence`} sources={sources}>
            <ConfidenceDot confidence={v.confidence} />
          </Sourced>
          <span className="text-neutral-400">low when n &lt; 30</span>
        </dd>
      </dl>
    </div>
  );
}
