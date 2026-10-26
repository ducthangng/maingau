import { TrendingDown } from "lucide-react";
import type { CustomerCard } from "../../types/contracts";
import { NOT_ENOUGH, eur, isMissing, pct } from "../../lib/format";
import { FactValue, Sourced } from "../Source";
import { Section } from "../Chips";
import { num } from "./shared";

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg bg-neutral-50 px-3 py-2">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="truncate text-base font-semibold tabular-nums tracking-tight">{children}</div>
    </div>
  );
}

function Percentile({ v }: { v: number | null | undefined }) {
  if (isMissing(v)) return <span className="font-normal text-neutral-400 italic">{NOT_ENOUGH}</span>;
  return <>P{num(v)}</>;
}

/** A4: value and risk. All numbers come from the JSON; nothing is recomputed here. */
export function ValueRiskPanel({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const vr = card.profile.value_risk;
  const drivers = vr.churn_drivers ?? [];
  const p = vr.percentiles ?? {};
  const impact = vr.clv_service_impact_eur;
  const impactV = typeof impact?.v === "number" ? impact.v : null;

  return (
    <Section title="Value & risk" uiRef="value">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Tile label="CLV">
          <FactValue fact={vr.clv_eur} sources={s} format={(v: number) => eur(v)} />
        </Tile>
        <Tile label="Annual margin">
          <FactValue fact={vr.annual_margin_eur} sources={s} format={(v: number) => eur(v)} />
        </Tile>
        <Tile label="Cost to serve (12 mo)">
          <FactValue fact={vr.cost_to_serve_12m_eur} sources={s} format={(v: number) => eur(v)} />
        </Tile>
        <Tile label="Business lines">
          <FactValue fact={vr.active_business_lines} sources={s} format={(v: number) => num(v)} />
        </Tile>
        <Tile label="Churn (12 mo)">
          <FactValue fact={vr.churn_prob_12m} sources={s} format={(v: number) => pct(v)} />
        </Tile>
        <Tile label="CLV percentile">
          <Sourced src={vr.clv_eur?.src} updatedAt={vr.clv_eur?.updated_at} sources={s}>
            <Percentile v={p.clv_all} />
          </Sourced>
          <span className="ml-1 text-xs font-normal text-neutral-500">all</span>
        </Tile>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-500">
        <span>
          Same product mix{p.combo ? <span className="text-neutral-400"> ({p.combo.replace(/\+/g, " + ")})</span> : null}:{" "}
          <Sourced src={vr.clv_eur?.src} updatedAt={vr.clv_eur?.updated_at} sources={s}>
            <span className="font-medium text-neutral-700">
              <Percentile v={p.clv_same_combo} />
            </span>
          </Sourced>
        </span>
      </div>

      {drivers.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-0.5 text-xs text-neutral-500">Churn drivers</span>
          {drivers.map((d) => {
            const up = (d.delta ?? 0) > 0;
            const down = (d.delta ?? 0) < 0;
            return (
              <Sourced key={d.label} src={vr.churn_prob_12m?.src} updatedAt={vr.churn_prob_12m?.updated_at} sources={s}>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1 ring-inset ${
                    up ? "bg-red-50 text-red-700 ring-red-200" : down ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-neutral-50 text-neutral-600 ring-neutral-200"
                  }`}
                >
                  {d.label}
                  {!isMissing(d.delta) && (
                    <span className="tabular-nums font-medium">
                      {d.delta > 0 ? "+" : d.delta < 0 ? "−" : ""}
                      {num(Math.abs(d.delta) * 100, 1)} pp
                    </span>
                  )}
                </span>
              </Sourced>
            );
          })}
        </div>
      )}

      {impactV !== null && impactV < 0 && (
        <p className="mt-2 flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-sm text-amber-900 ring-1 ring-inset ring-amber-200">
          <TrendingDown className="size-4 shrink-0" aria-hidden />
          <span>
            Service issues are costing{" "}
            <Sourced src={impact.src} updatedAt={impact.updated_at} sources={s}>
              <span className="font-semibold">{eur(Math.abs(impactV))}</span>
            </Sourced>{" "}
            of CLV
          </span>
        </p>
      )}
    </Section>
  );
}
