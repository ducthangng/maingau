import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, ExternalLink, Package, User, X, type LucideIcon } from "lucide-react";
import type { CustomerCard, Products } from "../../types/contracts";
import { loadCard, useLoad } from "../../lib/data";
import { CHANNEL_LABEL, eur, isMissing, pct } from "../../lib/format";
import { TIER_LABEL, TierChip } from "../Chips";
import { FactValue } from "../Source";
import { RuleChip, toneLabel } from "../nba/ui";
import { PRODUCT_META } from "../profile/Products";
import { num } from "../profile/shared";
import { CHANNEL_ICON, FLAG_META, FlagIcon, RiskMeter, Signed, ValueBar, dirOf } from "../viz";
import ActionGraph from "./ActionGraph";
import { Label, SignalChip } from "./parts";

// Action-first pop-up opened from the worklist. Left: only the facts the decision depends on, as
// icons and meters. Right: the action graph (history → trigger → options → decision, see ActionGraph).
// Everything else stays on the full customer page. Display only, like the cards.

/* ---------------------------------------------------------------- left: who */

// One-word labels so the icon tiles stay on one line; the full name is in the tooltip.
const SHORT: Record<string, string> = {
  newsletter_email: "News",
  email: "E-mail",
  portal_popup: "Portal",
  app_push: "App",
  sms: "SMS",
  outbound_call: "Phone",
  smart_living: "Smart",
  autostrom: "Auto",
};

function IconTile({ icon: Icon, label, state, title }: { icon: LucideIcon; label: string; state: "on" | "maybe" | "off"; title?: string }) {
  const cls =
    state === "on"
      ? "bg-neutral-900 text-white"
      : state === "maybe"
        ? "bg-white text-accent-600 ring-1 ring-inset ring-accent-500"
        : "bg-neutral-100 text-neutral-300";
  return (
    <span className="flex w-11 flex-col items-center gap-1" title={title ?? label}>
      <span className={`relative grid size-8 place-items-center rounded-lg ${cls}`}>
        <Icon size={15} aria-hidden />
        {state === "off" && <span className="absolute h-[1.5px] w-6 rotate-45 rounded bg-neutral-300" aria-hidden />}
      </span>
      <span className={`w-full truncate text-center text-[10px] ${state === "off" ? "text-neutral-400" : "text-neutral-600"}`}>{label}</span>
    </span>
  );
}

function ProfileColumn({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const h = card.profile.header;
  const vr = card.profile.value_risk;
  const t = card.triage;
  const signals = card.signals ?? [];
  const products = card.profile.products;
  const channels = (card.profile.channels ?? []).filter((c) => c.channel !== "service_agent");
  const exclusions = (card.profile.exclusions ?? []).filter((e) => e.active);
  const d = h.digital ?? {};
  const pctl = vr.percentiles?.clv_all;
  const churn = vr.churn_prob_12m?.v as number | null | undefined;
  const drivers = vr.churn_drivers ?? [];
  const driverSum = drivers.reduce((a, x) => a + (x.delta ?? 0), 0);
  const allowed = channels.filter((c) => c.allowed);
  const lines = Object.keys(PRODUCT_META) as (keyof Products)[];
  const held = lines.filter((l) => products[l]?.held).map((l) => PRODUCT_META[l].label);
  const opps = lines.filter((l) => !products[l]?.held && products[l]?.opportunity).map((l) => PRODUCT_META[l].label);
  const firstReason = t.urgency_reasons?.[0]?.replace(/\s*\[[A-Z0-9-]+\]/g, "");

  return (
    <aside className="flex min-h-0 flex-col bg-neutral-50">
      <div className="flex min-h-0 flex-1 flex-col gap-7 p-6 md:overflow-y-auto">
        <div className="flex items-center gap-3">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white text-neutral-300 ring-1 ring-neutral-200" aria-hidden>
            <User size={28} />
          </div>
          <div className="min-w-0">
            <h2 id="customer-modal-title" className="text-lg font-semibold tracking-tight tabular-nums">
              {card.customer_id}
            </h2>
            <p className="truncate text-sm text-neutral-600" title={t.archetype.reason}>
              {t.archetype.name}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <TierChip tier={t.urgency_tier} />
          <span className="text-sm font-medium text-neutral-800">{TIER_LABEL[t.urgency_tier]}</span>
          {t.deadline && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800 ring-1 ring-inset ring-amber-200"
              title="Deadline"
            >
              <CalendarClock size={12} aria-hidden /> {t.deadline}
            </span>
          )}
          <span
            className="ml-auto rounded-md bg-white px-1.5 py-0.5 text-xs font-semibold text-neutral-700 ring-1 ring-neutral-200"
            title={h.tone.evidence}
          >
            {toneLabel(h.tone.value)}
          </span>
        </div>
        <p className="-mt-3 text-xs leading-relaxed text-neutral-500">
          {firstReason && firstReason !== "no trigger" ? <>On the list because {firstReason}. </> : <>No urgent trigger. </>}
          Segment: {t.archetype.reason}. Address as {toneLabel(h.tone.value)}
          {h.tone.method === "default" ? " (default)" : ` (from ${h.tone.method})`}.
        </p>

        <dl className="grid grid-cols-2 gap-x-5 gap-y-3 rounded-xl bg-white p-4 text-sm ring-1 ring-neutral-200">
          {(
            [
              ["City", <FactValue fact={h.city} sources={s} />],
              ["Age band", <FactValue fact={h.age_band} sources={s} />],
              ["Customer for", <FactValue fact={h.tenure_years} sources={s} format={(v: number) => `${num(v, 1)} years`} />],
              ["Household", <FactValue fact={h.household_size} sources={s} format={(v: number) => `${num(v)}`} />],
              ["Language", <FactValue fact={d.language} sources={s} />],
              ["Margin / year", <FactValue fact={vr.annual_margin_eur} sources={s} format={(v: number) => eur(v)} />],
            ] as [string, ReactNode][]
          ).map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-neutral-500">{label}</dt>
              <dd className="truncate">{value}</dd>
            </div>
          ))}
        </dl>

        {/* Value and risk as meters with a direction. */}
        <div className="grid grid-cols-2 gap-5">
          <div className="space-y-1.5">
            <Label>CLV</Label>
            <div className="text-sm font-semibold">
              {isMissing(pctl) ? (
                <FactValue fact={vr.clv_eur} sources={s} format={(v: number) => eur(v)} />
              ) : (
                <Signed dir={dirOf(pctl, 50)} title={`P${num(pctl)} of all customers (P50 = median)`}>
                  <FactValue fact={vr.clv_eur} sources={s} format={(v: number) => eur(v)} />
                </Signed>
              )}
            </div>
            {!isMissing(pctl) && <ValueBar value={pctl} max={100} tone="muted" />}
            {!isMissing(pctl) && (
              <p className="text-xs text-neutral-500">
                {pctl >= 50 ? `Top ${num(100 - pctl)}% of customers` : `Below ${num(100 - pctl)}% of customers`}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label>Churn 12m</Label>
            <div className="text-sm font-semibold">
              {drivers.length ? (
                <Signed
                  dir={dirOf(driverSum)}
                  good="down"
                  title={drivers.map((x) => `${(x.delta ?? 0) > 0 ? "+" : ""}${pct(x.delta, 0)} ${x.label}`).join("\n")}
                >
                  <FactValue fact={vr.churn_prob_12m} sources={s} format={(v: number) => pct(v, 0)} />
                </Signed>
              ) : (
                <FactValue fact={vr.churn_prob_12m} sources={s} format={(v: number) => pct(v, 0)} />
              )}
            </div>
            {!isMissing(churn) && <RiskMeter v={churn} />}
            <p className="text-xs text-neutral-500">
              {drivers.length ? `Driven by ${drivers.map((x) => x.label).join(", ")}` : "No churn driver found"}
            </p>
          </div>
        </div>

        {(t.flags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {(t.flags ?? []).map((f) => (
              <span
                key={f.id}
                className="inline-flex items-center gap-1.5 text-xs text-neutral-700"
                title={[f.detail, f.src].filter(Boolean).join("\n")}
              >
                <FlagIcon id={f.id} />
                {f.label ?? FLAG_META[f.id]?.label ?? f.id}
              </span>
            ))}
          </div>
        )}

        <div className="space-y-2.5">
          <Label>Why now</Label>
          {signals.length === 0 ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-neutral-500">
              <Package size={14} aria-hidden /> No trigger
            </span>
          ) : (
            <ul className="space-y-2.5">
              {signals.map((sig) => (
                <li key={sig.id} className="space-y-1">
                  <SignalChip sig={sig} />
                  {sig.detail && <p className="pl-1 text-xs leading-relaxed text-neutral-500">{sig.detail}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-2.5">
          <Label>Reachable via</Label>
          <div className="flex flex-wrap gap-1">
            {channels.map((c) => (
              <IconTile
                key={c.channel}
                icon={CHANNEL_ICON[c.channel]}
                label={SHORT[c.channel] ?? c.channel}
                state={c.allowed ? "on" : "off"}
                title={`${CHANNEL_LABEL[c.channel] ?? c.channel}: ${c.allowed ? "allowed" : "blocked"}\n${c.reason}`}
              />
            ))}
          </div>
          <p className="text-xs text-neutral-500">
            {allowed.length === 0
              ? "No channel allowed for marketing."
              : `${allowed.length} of ${channels.length} channels allowed by consent. Hover a channel for the reason.`}
          </p>
          {exclusions.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {exclusions.map((e) => (
                <RuleChip key={e.rule_id} rule={e.rule_id} title={[e.detail, e.src].filter(Boolean).join("\n")} />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-2.5">
          <Label>Products</Label>
          <div className="flex flex-wrap gap-1">
            {(Object.keys(PRODUCT_META) as (keyof Products)[]).map((l) => {
              const p = products[l];
              const state = p?.held ? "on" : p?.opportunity ? "maybe" : "off";
              return (
                <IconTile
                  key={l}
                  icon={PRODUCT_META[l].icon}
                  label={SHORT[l] ?? PRODUCT_META[l].label}
                  state={state}
                  title={`${PRODUCT_META[l].label}: ${p?.held ? "holds" : p?.opportunity ? "opportunity" : p?.held === null ? "unknown" : "not held"}${p?.note ? `\n${p.note}` : ""}`}
                />
              );
            })}
          </div>
          <p className="text-xs leading-relaxed text-neutral-500">
            {held.length ? `Holds ${held.join(", ")}.` : "Holds no product we know of."}
            {opps.length ? ` Open opportunity: ${opps.join(", ")}.` : ""}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-neutral-200 px-6 py-2.5">
        <Link
          to={`/customer/${card.customer_id}`}
          className="inline-flex items-center gap-1 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-900"
        >
          Full profile <ExternalLink size={12} aria-hidden />
        </Link>
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------- shell */

export default function CustomerModal({ id, onClose }: { id: string; onClose: () => void }) {
  const card = useLoad(() => loadCard(id), [id]);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const lastFocus = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    return () => {
      document.body.style.overflow = prev;
      lastFocus?.focus?.();
    };
  }, []);

  useEffect(() => {
    // Esc closes, but never while typing (a reject/override reason draft must not be lost).
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-neutral-900/40 p-3 backdrop-blur-[2px] sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="customer-modal-title"
        tabIndex={-1}
        className="relative grid max-h-full w-full max-w-6xl grid-cols-[minmax(0,1fr)] overflow-y-auto rounded-2xl bg-white shadow-2xl outline-none md:h-[min(860px,100%)] md:grid-cols-[340px_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)] md:overflow-hidden"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 z-10 rounded-lg p-1.5 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-800"
        >
          <X size={18} />
        </button>
        {card.status === "loading" && <p className="col-span-full p-10 text-center text-neutral-500">Loading {id}…</p>}
        {card.status === "error" && (
          <p className="col-span-full p-10 text-center text-red-700">
            Could not load {id}: {card.error}
          </p>
        )}
        {card.status === "ready" && (
          <>
            <ProfileColumn card={card.data} />
            <ActionGraph card={card.data} />
          </>
        )}
      </div>
    </div>
  );
}
