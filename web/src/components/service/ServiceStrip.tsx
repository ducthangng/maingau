import type { CustomerCard } from "../../types/contracts";
import { eur } from "../../lib/format";
import { mockName } from "../../lib/customerMock";
import { channelLabel, toneLabel } from "../nba/ui";
import { dateLabel, driverLabels, notRecommended, offerName, openTickets, reasonOf } from "./plain";

// Fixed strip (prompts/ui-customer360.md §3.1): who, what happened, what to suggest — in one glance.
function Item({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">{label}</p>
      <div className="mt-0.5 text-sm text-neutral-900">{children}</div>
    </div>
  );
}

export default function ServiceStrip({ card }: { card: CustomerCard }) {
  const vr = card.profile.value_risk;
  const drivers = driverLabels(card);
  const tickets = openTickets(card).length;
  const chosen = card.chosen;
  const top = (card.candidates ?? []).find((c) => c.tuple_id === chosen.tuple_id);
  const clv = vr.clv_eur?.v;

  let nba: React.ReactNode;
  if (chosen.tuple_id === "NO_ACTION" || !top) {
    const why = notRecommended(card)[0]?.text;
    nba = (
      <>
        <span className="font-medium">No offer right now</span>
        {why && <span className="block text-neutral-600">{why}</span>}
      </>
    );
  } else {
    nba = (
      <>
        <span className="font-medium">{top.offer_name || offerName(top.offer_id)}</span>
        <span className="text-neutral-600"> · {channelLabel(top.channel)}</span>
        {chosen.deferred_until && <span className="text-neutral-600"> · from {dateLabel(chosen.deferred_until)}</span>}
        <span className="block text-neutral-600">{reasonOf(top)}</span>
      </>
    );
  }

  return (
    <div className="sticky top-14 z-10 rounded-xl border border-neutral-200 bg-white/95 p-4 shadow-sm backdrop-blur">
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-[minmax(0,1.2fr)_auto_minmax(0,1.4fr)_auto_auto] lg:grid-cols-[minmax(0,1.1fr)_auto_minmax(0,1.3fr)_auto_auto_minmax(0,2fr)]">
        <Item label="Customer" className="col-span-2 md:col-span-1">
          <span className="text-base font-semibold">{mockName(card.customer_id)}</span>{" "}
          <span className="rounded bg-neutral-100 px-1 text-[10px] font-medium uppercase text-neutral-500" title="Demo name: the data has no names">
            demo
          </span>
          <span className="block font-mono text-xs text-neutral-500">{card.customer_id}</span>
        </Item>
        <Item label="CLV now">
          <span className="text-2xl font-bold tabular-nums tracking-tight">{typeof clv === "number" ? eur(clv) : "not enough data"}</span>
        </Item>
        <Item label="What moves the CLV">{drivers.length ? drivers.join(" · ") : <span className="text-neutral-500">nothing notable</span>}</Item>
        <Item label="Open tickets">
          <span className="text-lg font-semibold tabular-nums">{tickets}</span>
        </Item>
        <Item label="Address as">
          <span className="text-lg font-semibold">{toneLabel(card.profile.header.tone.value)}</span>
        </Item>
        <Item label="Suggest first" className="col-span-2 md:col-span-5 lg:col-span-1">
          {nba}
        </Item>
      </div>
    </div>
  );
}
