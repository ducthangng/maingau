import { Link } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Clock, Sparkles, User } from "lucide-react";
import type { Products } from "../../types/contracts";
import type { KbCustomer } from "../../lib/kb";
import { TierChip, type Tier } from "../Chips";
import { loadCard, useLoad } from "../../lib/data";
import { mockName } from "../../lib/customerMock";
import { eur, pct, signedEur } from "../../lib/format";
import { OFFER_NAME } from "../worklist/model";
import { channelLabel, toneLabel } from "../nba/ui";
import { PRODUCT_META } from "../profile/Products";
import { openTickets } from "../service/plain";
import { tidy } from "./explain";

// The Knowledge Base's left card, kept compact: who the customer is, the decision in one line with what it is worth,
// and only the profile facts the decision rests on (products held, open tickets, consent). The reason and the gain
// calculation are folded away under the action; the full profile is one link away. The profile part
// comes from the customer card, which loads like everywhere else (API, else the static JSON).

function tupleText(tuple: string): string {
  if (!tuple || tuple === "NO_ACTION") return "No action";
  const [offer, channel, tone] = tuple.split("|");
  return `${OFFER_NAME[offer] ?? offer} · ${channelLabel(channel)} · ${toneLabel(tone)}`;
}

const held = (p: Products) => (Object.keys(PRODUCT_META) as (keyof Products)[]).filter((l) => p[l]?.held).map((l) => PRODUCT_META[l].label);

export default function ProfileSummary({ c }: { c: KbCustomer }) {
  const card = useLoad(() => loadCard(c.id), [c.id]);
  const h = c.headline;
  const ready = card.status === "ready" ? card.data : null;
  const tickets = ready ? openTickets(ready).length : 0;
  const v = c.chosen.valuation;
  const profiling = ready?.profile.consent.find((x) => x.type === "profiling_analytics")?.effective_status === "granted";
  const products = ready ? held(ready.profile.products) : [];

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-3.5">
      <div className="flex items-center gap-2.5">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl border border-neutral-200 text-neutral-300" aria-hidden>
          <User size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold tracking-tight text-neutral-900" title={`${mockName(c.id)} (demo name: the data has no names)`}>
            {mockName(c.id)}
          </p>
          <p className="truncate text-[12px] text-neutral-500" title={h.archetype}>
            <span className="font-mono">{c.id}</span> · {h.archetype.replace(/^A\d+\s+/, "")}
          </p>
        </div>
        <TierChip tier={h.urgency as Tier} />
      </div>

      <p className="mt-2 text-[12px] tabular-nums text-neutral-600">
        CLV <span className="font-medium text-neutral-900">{h.clv == null ? "no data" : eur(h.clv)}</span> · churn{" "}
        <span className="font-medium text-neutral-900">{h.churn == null ? "no data" : pct(h.churn, 0)}</span>
      </p>

      <div className="mt-2.5 rounded-lg border border-accent-200 bg-accent-50/60 px-2.5 py-2">
        <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-accent-700">
          <Sparkles size={11} aria-hidden /> Next best action
        </p>
        <p className="mt-0.5 text-[13px] font-semibold leading-snug text-neutral-900">{tupleText(c.chosen.tuple)}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12px] tabular-nums text-neutral-600">
          {v ? (
            <>
              <span className="font-semibold text-accent-700">ΔCLV {signedEur(v.dclv)}</span>
              <span title={`${v.confidence} confidence`}>p {pct(v.p)}</span>
            </>
          ) : (
            <span>no expected gain</span>
          )}
          {(c.chosen.send_at || c.chosen.until) && (
            <span className="inline-flex items-center gap-1">
              <Clock size={11} className="text-neutral-400" aria-hidden />
              {c.chosen.until ? `waits until ${c.chosen.until.slice(0, 10)}` : c.chosen.send_at}
            </span>
          )}
        </p>
        <details className="group mt-1">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-[11px] font-medium text-accent-700 [&::-webkit-details-marker]:hidden">
            {v ? "Why · how the gain is calculated" : "Why"}
            <ChevronDown size={11} className="transition-transform duration-150 group-open:rotate-180" aria-hidden />
          </summary>
          <p className="mt-1 text-[12px] leading-relaxed text-neutral-600">{tidy(c.chosen.reason.split("→")[0])}</p>
          {v && (
            <>
              <p className="mt-1.5 font-mono text-[10px] leading-relaxed text-neutral-500">
                ΔCLV = p·(CLV<sub>buy</sub> − CLV<sub>now</sub>) + (1−p)·(CLV<sub>no</sub> − CLV<sub>now</sub>) − cost
              </p>
              <dl className="mt-1 grid grid-cols-2 gap-x-3 text-[11px] tabular-nums">
                {(
                  [
                    ["CLV now", eur(v.clv_now)],
                    ["CLV if yes", eur(v.clv_accept)],
                    ["CLV if no", eur(v.clv_reject)],
                    ["Contact cost", eur(v.cost, true)],
                    ["Evidence", `${v.conv}/${v.n} bought`],
                    ["Confidence", v.confidence],
                  ] as const
                ).map(([k, val]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="text-neutral-500">{k}</dt>
                    <dd className="text-neutral-900">{val}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </details>
      </div>

      {card.status === "loading" && <div className="mt-2.5 h-10 animate-pulse rounded-lg bg-neutral-100" aria-label="Loading the profile" />}
      {ready && (
        <dl className="mt-2.5 space-y-0.5 text-[12px]">
          <div className="flex justify-between gap-3">
            <dt className="text-neutral-500">Has</dt>
            <dd className="truncate text-right text-neutral-900" title={products.join(", ")}>
              {products.length ? products.join(", ") : "nothing yet"}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-neutral-500">Personalised offers</dt>
            <dd className="text-neutral-900">{profiling ? "yes" : "no"}</dd>
          </div>
          {tickets > 0 && (
            <div className="flex justify-between gap-3">
              <dt className="text-neutral-500">Open tickets</dt>
              <dd className="font-medium text-red-700">{tickets}</dd>
            </div>
          )}
        </dl>
      )}

      <Link
        to={`/service/${encodeURIComponent(c.id)}`}
        className="mt-2.5 inline-flex items-center gap-1 text-[12px] font-medium text-accent-700 hover:underline"
      >
        Full profile in Customer 360° <ArrowUpRight size={13} aria-hidden />
      </Link>
    </section>
  );
}
