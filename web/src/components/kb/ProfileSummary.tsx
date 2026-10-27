import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Clock, Sparkles, User } from "lucide-react";
import type { KbCustomer } from "../../lib/kb";
import { TierChip, type Tier } from "../Chips";
import { loadCard, useLoad } from "../../lib/data";
import { mockName } from "../../lib/customerMock";
import { eur, pct, signedEur } from "../../lib/format";
import { OFFER_NAME } from "../worklist/model";
import { channelLabel, toneLabel } from "../nba/ui";
import { tidy } from "./explain";
import { ProductTiles } from "../service/ProfileTab";
import { openTickets } from "../service/plain";

// The Knowledge Base's left card: who the customer is, what the engine decided for them and what it is worth
// (the export), then only the profile facts the decision rests on (products, open tickets, consent) and a link to
// the full profile. The profile part comes from the customer card, which loads like everywhere else (API, else the
// static JSON).

/** A label left, a number right (tabular, so the column of amounts lines up). */
function Amount({ k, children, strong = false }: { k: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5">
      <dt className="text-[13px] text-neutral-500">{k}</dt>
      <dd className={`font-mono text-[13px] tabular-nums ${strong ? "font-semibold text-accent-700" : "text-neutral-900"}`}>{children}</dd>
    </div>
  );
}

/** A big number with its label: the figures a reader looks for first. */
function Kpi({ label, value, note, accent = false }: { label: string; value: string; note?: string; accent?: boolean }) {
  return (
    <div className={`min-w-0 rounded-xl border px-3 py-2.5 ${accent ? "border-accent-200 bg-accent-50" : "border-neutral-200 bg-neutral-50"}`}>
      <p className={`text-[10px] font-semibold uppercase tracking-wider ${accent ? "text-accent-700" : "text-neutral-500"}`}>{label}</p>
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5">
        <span className={`text-xl font-semibold tabular-nums tracking-tight ${accent ? "text-accent-700" : "text-neutral-900"}`}>{value}</span>
        {note && <span className="text-[11px] text-neutral-500">{note}</span>}
      </p>
    </div>
  );
}

function tupleText(tuple: string): string {
  if (!tuple || tuple === "NO_ACTION") return "No action";
  const [offer, channel, tone] = tuple.split("|");
  return `${OFFER_NAME[offer] ?? offer} · ${channelLabel(channel)} · ${toneLabel(tone)}`;
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="truncate text-neutral-900 tabular-nums">{children === "" || children == null ? "—" : children}</dd>
    </div>
  );
}

export default function ProfileSummary({ c }: { c: KbCustomer }) {
  const card = useLoad(() => loadCard(c.id), [c.id]);
  const h = c.headline;
  const ready = card.status === "ready" ? card.data : null;
  const tickets = ready ? openTickets(ready).length : 0;
  const v = c.chosen.valuation;
  const profiling = ready?.profile.consent.find((x) => x.type === "profiling_analytics")?.effective_status === "granted";

  return (
    <section className="@container rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <div className="grid size-12 shrink-0 place-items-center rounded-2xl border border-neutral-200 text-neutral-300" aria-hidden>
          <User size={24} />
        </div>
        <div className="min-w-0">
          <p className="truncate text-base font-semibold tracking-tight text-neutral-900" title={mockName(c.id)}>
            {mockName(c.id)}{" "}
            <span className="rounded bg-neutral-100 px-1 align-middle text-[10px] font-medium uppercase text-neutral-500" title="Demo name: the data has no names">
              demo
            </span>
          </p>
          <p className="truncate text-[12px] text-neutral-500" title={h.archetype}>
            <span className="font-mono">{c.id}</span> · {h.archetype.replace(/^A\d+\s+/, "")}
          </p>
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-x-3 text-sm">
        <Fact label="CLV">{h.clv == null ? "no data" : eur(h.clv)}</Fact>
        <Fact label="Churn 12 m">{h.churn == null ? "no data" : pct(h.churn, 0)}</Fact>
        <Fact label="Urgency">
          <TierChip tier={h.urgency as Tier} />
        </Fact>
      </dl>

      {/* The decision first: it is what this page explains. */}
      <div className="mt-3 rounded-xl border border-accent-200 bg-accent-50/60 p-3">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-accent-700">
          <Sparkles size={12} aria-hidden /> Next best action
        </p>
        <p className="mt-1 font-semibold text-neutral-900">{tupleText(c.chosen.tuple)}</p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-neutral-600">Why: {tidy(c.chosen.reason.split("→")[0])}</p>
        {(c.chosen.send_at || c.chosen.until) && (
          <p className="mt-1.5 flex items-center gap-1 text-[12px] tabular-nums text-neutral-600">
            <Clock size={12} className="text-neutral-400" aria-hidden />
            {c.chosen.until ? `waits until ${c.chosen.until.replace("T", " ").slice(0, 16)}` : `sent at ${c.chosen.send_at}`}
          </p>
        )}
        {v ? (
          <>
            <div className="mt-2.5 grid grid-cols-2 gap-2">
              <Kpi label="ΔCLV" value={signedEur(v.dclv)} accent />
              <Kpi label="p (agree)" value={pct(v.p)} note={`${v.confidence} conf.`} />
            </div>
            <details className="group mt-2">
              <summary className="flex cursor-pointer list-none items-center gap-1 text-[12px] font-medium text-accent-700 [&::-webkit-details-marker]:hidden">
                How the gain is calculated
                <ChevronDown size={12} className="transition-transform duration-150 group-open:rotate-180" aria-hidden />
              </summary>
              <div className="mt-2 space-y-2">
                <p className="rounded-lg bg-neutral-900 px-3 py-2 font-mono text-[11px] leading-relaxed text-neutral-200">
                  ΔCLV = p·(CLV<sub>buy</sub> − CLV<sub>now</sub>) + (1−p)·(CLV<sub>no</sub> − CLV<sub>now</sub>) − cost
                </p>
                <dl>
                  <Amount k="CLV now">{eur(v.clv_now)}</Amount>
                  <Amount k="CLV if yes" strong>{eur(v.clv_accept)}</Amount>
                  <Amount k="CLV if no">{eur(v.clv_reject)}</Amount>
                  <Amount k="Contact cost">{eur(v.cost, true)}</Amount>
                  <Amount k="Evidence">
                    {v.conv}/{v.n} bought
                  </Amount>
                </dl>
              </div>
            </details>
          </>
        ) : (
          <p className="mt-2 text-[12px] text-neutral-500">No action, so no expected gain.</p>
        )}
      </div>

      {card.status === "loading" && <div className="mt-3 h-24 animate-pulse rounded-xl bg-neutral-100" aria-label="Loading the profile" />}
      {ready && (
        <>
          <div className="mt-3">
            <ProductTiles products={ready.profile.products} />
          </div>
          <dl className="mt-3 space-y-1 border-t border-neutral-100 pt-2.5 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-neutral-500">Open tickets</dt>
              <dd className={tickets ? "font-medium text-red-700" : "text-neutral-900"}>{tickets}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-neutral-500">Personalised offers</dt>
              <dd className="text-neutral-900">{profiling ? "yes" : "no"}</dd>
            </div>
          </dl>
        </>
      )}

      <Link
        to={`/service/${encodeURIComponent(c.id)}`}
        className="mt-4 flex items-center justify-center gap-1.5 rounded-lg bg-accent-600 px-3 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700"
      >
        Full profile in Customer 360° <ArrowUpRight size={15} aria-hidden />
      </Link>
    </section>
  );
}
