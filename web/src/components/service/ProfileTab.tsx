import { User } from "lucide-react";
import type { CustomerCard, Products } from "../../types/contracts";
import { eur } from "../../lib/format";
import { mockName } from "../../lib/customerMock";
import Interaction from "../customer/Interaction";
import { Label } from "../customer/parts";
import { channelLabel } from "../nba/ui";
import { PRODUCT_META } from "../profile/Products";
import { dateLabel, factV, humanize, openTickets, str } from "./plain";

// Profile card (prompts/ui-customer360.md §3.2), in the look of the orchestration pop-up's profile
// column. Plain facts only: no tier, flags, segment, highlights or data-quality warnings, and never
// a payment or dunning field.

type Item = Record<string, unknown>;
const v = (item: Item, key: string) => factV(item[key]);

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="break-words">{value === "" || value === null || value === undefined ? "—" : value}</dd>
    </div>
  );
}

// Label left, value right; in a narrow column a long value drops onto its own line instead of
// squeezing both (ui-polish.md §3.3).
function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 py-1 text-sm">
      <dt className="min-w-0 text-neutral-500">{label}</dt>
      <dd className="ml-auto min-w-0 break-words text-right text-neutral-900">{value === "" || value === null || value === undefined ? "—" : value}</dd>
    </div>
  );
}

// Orchestration contract (ui-polish.md §2): static outlines are borders, never rings.
const BOX = "rounded-xl border border-neutral-200 bg-white";
const LIST = `${BOX} divide-y divide-neutral-100`;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2.5">
      <Label>{title}</Label>
      <div className={`${BOX} p-4`}>{children}</div>
    </section>
  );
}

function sinceYear(card: CustomerCard): string {
  const years = card.profile.header.tenure_years?.v;
  if (typeof years !== "number") return "";
  const evalDate = new Date(card.meta.eval_time);
  return `since ${new Date(evalDate.getTime() - years * 365.25 * 86_400_000).getFullYear()}`;
}

// One-word labels so the product tiles stay on one line, as in the orchestration pop-up.
const SHORT: Record<string, string> = { smart_living: "Smart", autostrom: "Auto" };

const yesNo = (x: unknown) => (x === true ? "yes" : x === false ? "no" : "");
const LANGUAGE: Record<string, string> = { de: "German", en: "English" };
const METER: Record<string, string> = { smart_meter_imsys: "Smart meter (iMSys)", conventional: "Conventional" };

// One row of the products list. The summary is secondary text: it stays on one line and keeps the
// full text in `title`; the focus outline is drawn inside the row so the column never clips it.
function Row({ title, summary, empty, children }: { title: string; summary: string; empty: boolean; children: React.ReactNode }) {
  const line = empty ? "none" : summary;
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-4 py-2.5 text-sm focus-visible:-outline-offset-2!">
        <span className="shrink-0 font-medium text-neutral-900">{title}</span>
        <span className="flex min-w-0 items-center gap-2 text-neutral-600">
          <span className="truncate" title={line}>
            {line}
          </span>
          <span className="shrink-0 text-neutral-400 transition-transform duration-150 group-open:rotate-90" aria-hidden>
            ›
          </span>
        </span>
      </summary>
      <div className="px-4 pb-3">{empty ? <p className="text-sm text-neutral-500">No contract or order on record.</p> : children}</div>
    </details>
  );
}

function Contract({ children }: { children: React.ReactNode }) {
  return <dl className="mb-2 rounded-lg bg-neutral-50 px-3 py-1.5 last:mb-0">{children}</dl>;
}

export default function ProfileTab({ card }: { card: CustomerCard }) {
  const h = card.profile.header;
  const p = card.profile.products;
  const energy = (p.energy.items ?? []) as Item[];
  const mobile = (p.mobile.items ?? []) as Item[];
  const autostrom = (p.autostrom.items ?? []) as Item[];
  const hems = (p.smart_living.items ?? []) as Item[];
  const shop = (p.shop.items ?? []) as Item[];
  const tickets = openTickets(card);
  const profiling = card.profile.consent.find((c) => c.type === "profiling_analytics")?.effective_status === "granted";
  const channels = card.profile.channels.filter((c) => c.channel !== "service_agent");

  return (
    <div className="flex flex-col gap-7">
      <div className="flex items-center gap-3">
        <div className="grid size-14 shrink-0 place-items-center rounded-2xl border border-neutral-200 bg-white text-neutral-300" aria-hidden>
          <User size={28} />
        </div>
        <div className="min-w-0">
          <p className="line-clamp-2 break-words text-lg font-semibold tracking-tight" title={mockName(card.customer_id)}>
            {mockName(card.customer_id)}{" "}
            <span className="rounded bg-neutral-100 px-1 align-middle text-[10px] font-medium uppercase text-neutral-500" title="Demo name: the data has no names">
              demo
            </span>
          </p>
          <p className="truncate text-sm text-neutral-500 tabular-nums" title={card.customer_id}>
            {card.customer_id}
          </p>
        </div>
      </div>

      <dl className={`grid grid-cols-2 gap-x-5 gap-y-3 p-4 text-sm @md:grid-cols-3 ${BOX}`}>
        <Fact label="Customer" value={sinceYear(card)} />
        <Fact label="City" value={str(h.city?.v)} />
        <Fact label="Household" value={h.household_size?.v ? `${h.household_size.v} people` : ""} />
        <Fact label="Language" value={LANGUAGE[str(h.digital?.language?.v)] ?? str(h.digital?.language?.v)} />
        <Fact label="Portal account" value={yesNo(h.digital?.portal_account?.v)} />
        <Fact label="App" value={yesNo(h.digital?.app_installed?.v)} />
      </dl>

      {/* Interaction is the pop-up's component (not edited here): its "View more" button gets the
          inset focus outline from this wrapper, so the column's scroll box never clips it. */}
      <div className="[&_button:focus-visible]:-outline-offset-2!">
        <Interaction card={card} />
      </div>

      <section className="space-y-2.5">
        <Label>Products</Label>
        {/* Same compact row of six 44 px tiles as the pop-up, but the tracks may shrink, so the row
            never overflows the column; below 14rem of column it breaks into two rows of three. */}
        <div className="grid grid-cols-[repeat(6,minmax(0,2.75rem))] gap-1 @max-[14rem]:grid-cols-3">
          {(Object.keys(PRODUCT_META) as (keyof Products)[]).map((l) => {
            const held = !!p[l]?.held;
            const Icon = PRODUCT_META[l].icon;
            return (
              <span key={l} className="flex min-w-0 flex-col items-center gap-1" title={`${PRODUCT_META[l].label}: ${held ? "in use" : "not used"}`}>
                <span
                  className={`grid size-8 place-items-center rounded-lg ${held ? "bg-accent-600 text-white" : "border border-neutral-200 bg-white text-neutral-400"}`}
                >
                  <Icon size={15} aria-hidden />
                </span>
                <span className="w-full truncate text-center text-[10px] text-neutral-600">{SHORT[l] ?? PRODUCT_META[l].label}</span>
              </span>
            );
          })}
        </div>
        <div className={LIST}>
        <Row title="Energy" empty={!energy.length} summary={energy.map((i) => `${str(v(i, "tariff"))} · ${humanize(v(i, "status"))}`).join(", ")}>
          {energy.map((i, k) => {
            const days = v(i, "guarantee_days_left");
            const until = str(v(i, "price_guarantee_until"));
            return (
              <Contract key={k}>
                <Field label="Commodity" value={humanize(v(i, "commodity"))} />
                <Field label="Tariff" value={str(v(i, "tariff"))} />
                <Field label="Status" value={humanize(v(i, "status"))} />
                <Field label="Start date" value={dateLabel(str(v(i, "start_date")))} />
                <Field
                  label="Price guarantee until"
                  value={until ? `${dateLabel(until)}${typeof days === "number" && days >= 0 ? ` (${days} days left)` : ""}` : ""}
                />
                <Field label="Meter" value={METER[str(v(i, "meter_type"))] ?? humanize(v(i, "meter_type"))} />
                <Field label="Annual consumption" value={v(i, "annual_consumption_kwh") ? `${Number(v(i, "annual_consumption_kwh")).toLocaleString("en-US")} kWh` : ""} />
              </Contract>
            );
          })}
        </Row>
        <Row title="Mobile" empty={!mobile.length} summary={mobile.map((i) => `${str(v(i, "plan"))} · ${humanize(v(i, "status"))}`).join(", ")}>
          {mobile.map((i, k) => (
            <Contract key={k}>
              <Field label="Plan" value={str(v(i, "plan"))} />
              <Field label="Data volume" value={v(i, "data_volume_gb") ? `${v(i, "data_volume_gb")} GB` : ""} />
              {i.monthly_fee_eur !== undefined && <Field label="Monthly fee" value={eur(Number(v(i, "monthly_fee_eur")), true)} />}
              <Field label="SIMs" value={str(v(i, "sim_count"))} />
              <Field label="Minimum term ends" value={dateLabel(str(v(i, "min_term_end")))} />
            </Contract>
          ))}
        </Row>
        <Row title="Autostrom" empty={!autostrom.length} summary={autostrom.map((i) => `${str(v(i, "car"))} · ${humanize(v(i, "status"))}`).join(", ")}>
          {autostrom.map((i, k) => (
            <Contract key={k}>
              <Field label="Car" value={str(v(i, "car"))} />
              <Field label="Battery" value={v(i, "battery_kwh") ? `${v(i, "battery_kwh")} kWh` : ""} />
              <Field label="Charge cards" value={str(v(i, "charge_cards"))} />
              <Field label="Start date" value={dateLabel(str(v(i, "start_date")))} />
              <Field label="Charging per month" value={v(i, "kwh_per_month") ? `${v(i, "kwh_per_month")} kWh` : ""} />
            </Contract>
          ))}
        </Row>
        <Row title="HEMS" empty={!hems.length} summary={`${hems.length} device${hems.length === 1 ? "" : "s"}`}>
          <ul className="space-y-1 rounded-lg bg-neutral-50 px-3 py-2 text-sm">
            {hems.map((i, k) => (
              <li key={k} className="flex flex-wrap justify-between gap-x-4">
                <span className="min-w-0 break-words">{humanize(v(i, "device_type"))}</span>
                <span className="ml-auto text-right text-neutral-600">{humanize(v(i, "connection_status"))}</span>
              </li>
            ))}
          </ul>
        </Row>
        <Row title="Shop orders" empty={!shop.length} summary={`${shop.length} recent order${shop.length === 1 ? "" : "s"}`}>
          <ul className="space-y-1 rounded-lg bg-neutral-50 px-3 py-2 text-sm">
            {shop.map((i, k) => (
              <li key={k} className="flex flex-wrap justify-between gap-x-4">
                <span className="min-w-0 break-words">{str(v(i, "product_name"))}</span>
                <span className="ml-auto text-right text-neutral-600">
                  {humanize(v(i, "order_status"))} · {dateLabel(str(v(i, "order_created_at")))}
                </span>
              </li>
            ))}
          </ul>
        </Row>
        </div>
      </section>

      {/* A list in the Orchestration list style (one bordered box, rows split by dividers) instead of
          grey tiles inside a ringed card. */}
      <section className="space-y-2.5">
        <Label>{`Open tickets (${tickets.length})`}</Label>
        {tickets.length === 0 ? (
          <p className={`${BOX} p-4 text-sm text-neutral-500`}>No open ticket.</p>
        ) : (
          <ul className={LIST}>
            {tickets.map((t) => {
              const name = humanize(t.title.replace(/^Ticket:\s*/, ""));
              return (
                <li key={t.id} className="px-4 py-3 text-sm">
                  <p className="line-clamp-2 break-words" title={`${name} · opened ${dateLabel(t.date)}`}>
                    <span className="font-medium">{name}</span>
                    <span className="text-neutral-600"> · opened {dateLabel(t.date)}</span>
                  </p>
                  {t.detail && <p className="break-words text-neutral-600">{t.detail}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <Card title="Consent">
        <p className="mb-2 text-sm">
          Personalised offers: <span className="font-medium">{profiling ? "yes" : "no"}</span>
        </p>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm @md:grid-cols-3">
          {channels.map((c) => (
            <li key={c.channel} className="flex min-w-0 items-baseline gap-2">
              <span className={`shrink-0 ${c.allowed ? "text-accent-600" : "text-neutral-400"}`} aria-hidden>
                {c.allowed ? "✓" : "–"}
              </span>
              <span className={`min-w-0 break-words ${c.allowed ? "text-neutral-900" : "text-neutral-500"}`}>
                {channelLabel(c.channel)}
                <span className="sr-only">{c.allowed ? ": may be contacted" : ": no contact"}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
