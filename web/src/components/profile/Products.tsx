import type { ReactNode } from "react";
import { House, PlugZap, ShoppingBag, Smartphone, Wifi, Zap, type LucideIcon } from "lucide-react";
import type { CustomerCard, ProductLine, Products } from "../../types/contracts";
import { eur, pct } from "../../lib/format";
import { FactValue } from "../Source";
import { Section } from "../Chips";
import { REF_CLS, asFact, day, hasValue, humanize, num, withUnit, type Sources } from "./shared";

type Line = keyof Products;
type Item = Record<string, unknown>;

export const PRODUCT_META: Record<Line, { label: string; icon: LucideIcon }> = {
  energy: { label: "Energy", icon: Zap },
  autostrom: { label: "Autostrom", icon: PlugZap },
  mobile: { label: "Mobile", icon: Smartphone },
  shop: { label: "Shop", icon: ShoppingBag },
  smart_living: { label: "Smart Living", icon: House },
  internet: { label: "Internet", icon: Wifi },
};

const ORDER: Line[] = ["energy", "autostrom", "mobile", "shop", "smart_living", "internet"];

/** One fact of an item, with its source tooltip. */
function V({ item, k, s, fmt }: { item: Item; k: string; s: Sources; fmt?: (v: never) => string }) {
  return <FactValue fact={asFact(item[k])} sources={s} format={fmt} />;
}

function StatusPill({ item, k, s }: { item: Item; k: string; s: Sources }) {
  const f = asFact(item[k]);
  if (!f || typeof f.v !== "string") return null;
  const ok = f.v === "active" || f.v === "online" || f.v === "delivered";
  return (
    <span
      className={`rounded px-1.5 py-px text-[11px] ${ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}
    >
      <FactValue fact={f} sources={s} format={(v: string) => humanize(v)} />
    </span>
  );
}

const dateFmt = (v: string) => day(v);

/** Negative days = the guarantee already ended (never "-231 days left"). */
const daysLeftFmt = (v: number) => (v < 0 ? `${num(-v)} days ago` : v === 0 ? "ends today" : `${num(v)} days left`);

function EnergyItem({ it, s }: { it: Item; s: Sources }) {
  const daysLeft = asFact(it.guarantee_days_left)?.v;
  const ended = typeof daysLeft === "number" && daysLeft < 0;
  return (
    <div className="space-y-0.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium">
          <V item={it} k="tariff" s={s} />
        </span>
        <span className="text-xs text-neutral-500">
          <V item={it} k="commodity" s={s} />
        </span>
        <StatusPill item={it} k="status" s={s} />
      </div>
      <div className="text-xs text-neutral-600">
        <V item={it} k="annual_consumption_kwh" s={s} fmt={withUnit("kWh/yr")} />
        {hasValue(it, "meter_type") && (
          <>
            {" · "}
            <V item={it} k="meter_type" s={s} fmt={(v: string) => humanize(v)} />
          </>
        )}
      </div>
      {hasValue(it, "price_guarantee_until") && (
        <div className="text-xs text-neutral-600">
          {ended ? "Price guarantee ended" : "Price guarantee until"} <V item={it} k="price_guarantee_until" s={s} fmt={dateFmt} />
          {hasValue(it, "guarantee_days_left") && (
            <span className={ended ? "text-neutral-500" : "font-medium text-neutral-800"}>
              {" "}
              (<V item={it} k="guarantee_days_left" s={s} fmt={daysLeftFmt} />)
            </span>
          )}
        </div>
      )}
      {hasValue(it, "meter_deregistered_at") && (
        <div className="text-xs text-amber-800">
          Meter deregistered <V item={it} k="meter_deregistered_at" s={s} fmt={dateFmt} />
        </div>
      )}
      {hasValue(it, "cancellation_received_at") && (
        <div className="text-xs text-red-700">
          Cancellation received <V item={it} k="cancellation_received_at" s={s} fmt={dateFmt} />
        </div>
      )}
    </div>
  );
}

function AutostromItem({ it, s }: { it: Item; s: Sources }) {
  return (
    <div className="space-y-0.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium">
          <V item={it} k="car" s={s} />
        </span>
        <StatusPill item={it} k="status" s={s} />
      </div>
      <div className="text-xs text-neutral-600">
        <V item={it} k="battery_kwh" s={s} fmt={withUnit("kWh battery")} />
        {" · "}
        <V item={it} k="kwh_per_month" s={s} fmt={withUnit("kWh/month", 1)} />
      </div>
      <div className="text-xs text-neutral-600">
        DC share <V item={it} k="dc_share" s={s} fmt={(v: number) => pct(v, 0)} />
        {hasValue(it, "charge_cards") && (
          <>
            {" · "}
            <V item={it} k="charge_cards" s={s} fmt={withUnit("charge card(s)")} />
          </>
        )}
      </div>
      {hasValue(it, "cancelled_at") && (
        <div className="text-xs text-red-700">
          Cancelled <V item={it} k="cancelled_at" s={s} fmt={dateFmt} />
        </div>
      )}
    </div>
  );
}

function MobileItem({ it, s }: { it: Item; s: Sources }) {
  return (
    <div className="space-y-0.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium">
          <V item={it} k="plan" s={s} />
        </span>
        <StatusPill item={it} k="status" s={s} />
      </div>
      <div className="text-xs text-neutral-600">
        <V item={it} k="avg_data_used_gb_3m" s={s} fmt={withUnit("GB", 1)} /> used of{" "}
        <V item={it} k="data_volume_gb" s={s} fmt={withUnit("GB")} /> <span className="text-neutral-400">(avg 3 mo)</span>
      </div>
      <div className="text-xs text-neutral-600">
        <V item={it} k="sim_count" s={s} fmt={withUnit("SIM(s)")} />
        {" · limit reached "}
        <V item={it} k="data_limit_reached_3m" s={s} fmt={(v: number) => `${num(v)}/3 months`} />
      </div>
      {hasValue(it, "min_term_end") && (
        <div className="text-xs text-neutral-500">
          Minimum term ends <V item={it} k="min_term_end" s={s} fmt={dateFmt} />
        </div>
      )}
    </div>
  );
}

function ShopItem({ it, s }: { it: Item; s: Sources }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <span className="min-w-0 truncate text-sm">
        <V item={it} k="product_name" s={s} />
      </span>
      <span className="shrink-0 tabular-nums text-neutral-600">
        <V item={it} k="line_value_eur" s={s} fmt={(v: number) => eur(v)} />
        {" · "}
        <V item={it} k="order_created_at" s={s} fmt={dateFmt} />
      </span>
    </div>
  );
}

function DeviceItem({ it, s }: { it: Item; s: Sources }) {
  const status = asFact(it.connection_status)?.v;
  const online = status === "online";
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="flex min-w-0 items-center gap-1.5">
        <span className={`size-1.5 shrink-0 rounded-full ${online ? "bg-emerald-500" : "bg-red-500"}`} aria-hidden />
        <span className="truncate text-sm">
          <V item={it} k="device_type" s={s} fmt={(v: string) => humanize(v)} />
        </span>
      </span>
      <span className={online ? "text-neutral-500" : "font-medium text-red-700"}>
        <V item={it} k="connection_status" s={s} />
      </span>
    </div>
  );
}

const MAX_ITEMS: Record<Line, number> = { energy: 2, autostrom: 1, mobile: 1, shop: 3, smart_living: 6, internet: 0 };

function renderItem(line: Line, it: Item, s: Sources): ReactNode {
  switch (line) {
    case "energy":
      return <EnergyItem it={it} s={s} />;
    case "autostrom":
      return <AutostromItem it={it} s={s} />;
    case "mobile":
      return <MobileItem it={it} s={s} />;
    case "shop":
      return <ShopItem it={it} s={s} />;
    case "smart_living":
      return <DeviceItem it={it} s={s} />;
    default:
      return null;
  }
}

function Cell({ line, p, s }: { line: Line; p: ProductLine | undefined; s: Sources }) {
  const meta = PRODUCT_META[line];
  const Icon = meta.icon;
  const held = p?.held;
  const items = (p?.items ?? []) as Item[];
  const shown = items.slice(0, MAX_ITEMS[line]);
  const rest = items.length - shown.length;
  // Not held but with records (e.g. a cancelled Autostrom contract): show them as former, not as an upsell opportunity.
  const former = held === false && items.length > 0;
  const isOpportunity = held === false && !former;
  const unknown = held === null || held === undefined;

  const tone = isOpportunity
    ? "border-accent-100 bg-accent-50/70"
    : unknown
      ? "border-dashed border-neutral-200 bg-white"
      : "border-neutral-200 bg-white";

  return (
    <div data-ui-ref={`product:${line}`} className={`${REF_CLS} rounded-lg border p-3 ${tone}`}>
      <div className="mb-1.5 flex items-center gap-2">
        <Icon className={`size-4 ${isOpportunity ? "text-accent-600" : "text-neutral-500"}`} aria-hidden />
        <span className="text-sm font-semibold">{meta.label}</span>
        {isOpportunity && (
          <span className="ml-auto rounded-full bg-white px-2 py-px text-[11px] font-medium text-accent-700 ring-1 ring-inset ring-accent-100">
            Opportunity
          </span>
        )}
        {former && (
          <span className="ml-auto rounded-full bg-neutral-100 px-2 py-px text-[11px] font-medium text-neutral-600">Not held</span>
        )}
        {held === true && items.length > 1 && (
          <span className="ml-auto text-[11px] text-neutral-400">{items.length} records</span>
        )}
      </div>

      {former && <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-neutral-500">Former contract</div>}
      {items.length > 0 && (held === true || former) && (
        <div className={line === "shop" || line === "smart_living" ? "space-y-1" : "space-y-2 text-sm"}>
          {shown.map((it, i) => (
            <div key={i} className={i > 0 && line !== "shop" && line !== "smart_living" ? "border-t border-neutral-100 pt-2" : ""}>
              {renderItem(line, it, s)}
            </div>
          ))}
          {rest > 0 && <div className="text-[11px] text-neutral-400">+{rest} more</div>}
        </div>
      )}
      {isOpportunity && <p className="text-xs text-neutral-500">Not held</p>}
      {unknown && <p className="text-xs text-neutral-400 italic">no ownership data</p>}
      {p?.note && <p className={`mt-1.5 text-[11px] leading-snug ${unknown ? "text-neutral-400" : "text-amber-800"}`}>{p.note}</p>}
    </div>
  );
}

/** B1: the six product lines. Empty cells are tinted as opportunities; Internet has no ownership data. */
export function ProductGrid({ card }: { card: CustomerCard }) {
  const products = card.profile.products;
  return (
    <Section title="Products">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ORDER.map((line) => (
          <Cell key={line} line={line} p={products?.[line]} s={card.sources} />
        ))}
      </div>
    </Section>
  );
}
