import type { CustomerCard } from "../../types/contracts";
import { eur } from "../../lib/format";
import { channelLabel } from "../nba/ui";
import { dateLabel, factV, humanize, openTickets, str } from "./plain";

// Tab 1: Profile (prompts/ui-customer360.md §3.2). Plain facts only: no tier, flags, segment,
// highlights or data-quality warnings, and never a payment or dunning field.

type Item = Record<string, unknown>;
const v = (item: Item, key: string) => factV(item[key]);

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <dt className="text-neutral-500">{label}</dt>
      <dd className="text-right text-neutral-900">{value === "" || value === null || value === undefined ? "—" : value}</dd>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-4">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">{title}</h3>
      {children}
    </section>
  );
}

function sinceYear(card: CustomerCard): string {
  const years = card.profile.header.tenure_years?.v;
  if (typeof years !== "number") return "";
  const evalDate = new Date(card.meta.eval_time);
  return `since ${new Date(evalDate.getTime() - years * 365.25 * 86_400_000).getFullYear()}`;
}

const yesNo = (x: unknown) => (x === true ? "yes" : x === false ? "no" : "");
const LANGUAGE: Record<string, string> = { de: "German", en: "English" };
const METER: Record<string, string> = { smart_meter_imsys: "Smart meter (iMSys)", conventional: "Conventional" };

function Row({ title, summary, empty, children }: { title: string; summary: string; empty: boolean; children: React.ReactNode }) {
  return (
    <details className="group border-b border-neutral-100 last:border-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-2.5 text-sm">
        <span className="font-medium text-neutral-900">{title}</span>
        <span className="flex items-center gap-2 text-neutral-600">
          <span className="truncate">{empty ? "none" : summary}</span>
          <span className="text-neutral-400 transition-transform duration-150 group-open:rotate-90" aria-hidden>
            ›
          </span>
        </span>
      </summary>
      <div className="pb-3">{empty ? <p className="text-sm text-neutral-500">No contract or order on record.</p> : children}</div>
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
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <Card title="Customer details">
          <dl className="divide-y divide-neutral-100">
            <Field label="Customer" value={sinceYear(card)} />
            <Field label="City" value={str(h.city?.v)} />
            <Field label="Household" value={h.household_size?.v ? `${h.household_size.v} people` : ""} />
            <Field label="Portal account" value={yesNo(h.digital?.portal_account?.v)} />
            <Field label="App" value={yesNo(h.digital?.app_installed?.v)} />
            <Field label="Language" value={LANGUAGE[str(h.digital?.language?.v)] ?? str(h.digital?.language?.v)} />
            <Field label="Customer type" value="Private" />
          </dl>
        </Card>

        <Card title={`Open tickets (${tickets.length})`}>
          {tickets.length === 0 ? (
            <p className="text-sm text-neutral-500">No open ticket.</p>
          ) : (
            <ul className="space-y-2">
              {tickets.map((t) => (
                <li key={t.id} className="rounded-lg bg-neutral-50 px-3 py-2 text-sm">
                  <span className="font-medium">{humanize(t.title.replace(/^Ticket:\s*/, ""))}</span>
                  <span className="text-neutral-600"> · opened {dateLabel(t.date)}</span>
                  {t.detail && <span className="block text-neutral-600">{t.detail}</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Consent">
          <p className="mb-2 text-sm">
            Personalised offers: <span className="font-medium">{profiling ? "yes" : "no"}</span>
          </p>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            {channels.map((c) => (
              <li key={c.channel} className="flex items-center gap-2">
                <span className={c.allowed ? "text-neutral-900" : "text-neutral-400"} aria-hidden>
                  {c.allowed ? "✓" : "–"}
                </span>
                <span className={c.allowed ? "text-neutral-900" : "text-neutral-500"}>
                  {channelLabel(c.channel)}
                  <span className="sr-only">{c.allowed ? ": may be contacted" : ": no contact"}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Products and contracts">
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
              <li key={k} className="flex justify-between gap-4">
                <span>{humanize(v(i, "device_type"))}</span>
                <span className="text-neutral-600">{humanize(v(i, "connection_status"))}</span>
              </li>
            ))}
          </ul>
        </Row>
        <Row title="Shop orders" empty={!shop.length} summary={`${shop.length} recent order${shop.length === 1 ? "" : "s"}`}>
          <ul className="space-y-1 rounded-lg bg-neutral-50 px-3 py-2 text-sm">
            {shop.map((i, k) => (
              <li key={k} className="flex justify-between gap-4">
                <span>{str(v(i, "product_name"))}</span>
                <span className="text-neutral-600">
                  {humanize(v(i, "order_status"))} · {dateLabel(str(v(i, "order_created_at")))}
                </span>
              </li>
            ))}
          </ul>
        </Row>
      </Card>
    </div>
  );
}
