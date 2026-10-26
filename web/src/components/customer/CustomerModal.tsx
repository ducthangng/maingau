import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, ExternalLink, User, X, type LucideIcon } from "lucide-react";
import type { CustomerCard, Products } from "../../types/contracts";
import { loadCard, useLoad } from "../../lib/data";
import { mockName } from "../../lib/customerMock";
import { eur } from "../../lib/format";
import { TIER_LABEL, TierChip } from "../Chips";
import { FactValue } from "../Source";
import { toneLabel } from "../nba/ui";
import { PRODUCT_META } from "../profile/Products";
import { num } from "../profile/shared";
import { FLAG_META, FlagIcon } from "../viz";
import Interaction from "./Interaction";
import NbaPanel from "./NbaPanel";
import { Label } from "./parts";

// Action-first pop-up opened from the worklist. Left: who the customer is and how they have dealt
// with us. Right: hard rules, then the ranked next best actions (see NbaPanel).
// Everything else stays on the full customer page. Display only, like the cards.

/* ---------------------------------------------------------------- left: who */

// One-word labels so the product tiles stay on one line; the full name is in the tooltip.
const SHORT: Record<string, string> = { smart_living: "Smart", autostrom: "Auto" };

/** Product tile: green when the customer uses the product, white when not. */
function IconTile({ icon: Icon, label, state, title }: { icon: LucideIcon; label: string; state: "held" | "free"; title?: string }) {
  const cls = state === "held" ? "bg-emerald-500 text-white" : "bg-white text-neutral-400 ring-1 ring-inset ring-neutral-200";
  return (
    <span className="flex w-11 flex-col items-center gap-1" title={title ?? label}>
      <span className={`grid size-8 place-items-center rounded-lg ${cls}`}>
        <Icon size={15} aria-hidden />
      </span>
      <span className="w-full truncate text-center text-[10px] text-neutral-600">{label}</span>
    </span>
  );
}

function ProfileColumn({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const h = card.profile.header;
  const vr = card.profile.value_risk;
  const t = card.triage;
  const products = card.profile.products;
  const d = h.digital ?? {};

  return (
    <aside className="flex min-h-0 flex-col bg-neutral-50">
      <div className="flex min-h-0 flex-1 flex-col gap-7 p-6 md:overflow-y-auto">
        <div className="flex items-center gap-3">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white text-neutral-300 ring-1 ring-neutral-200" aria-hidden>
            <User size={28} />
          </div>
          <div className="min-w-0">
            <h2 id="customer-modal-title" className="text-lg font-semibold tracking-tight">
              {mockName(card.customer_id)}
            </h2>
            <p className="truncate text-sm text-neutral-600" title={t.archetype.reason}>
              {t.archetype.name} <span className="text-neutral-400 tabular-nums">· {card.customer_id}</span>
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

        <Interaction card={card} />

        <div className="space-y-2.5">
          <Label>Products</Label>
          <div className="flex flex-wrap gap-1">
            {(Object.keys(PRODUCT_META) as (keyof Products)[]).map((l) => {
              const p = products[l];
              const state = p?.held ? "held" : "free";
              return (
                <IconTile
                  key={l}
                  icon={PRODUCT_META[l].icon}
                  label={SHORT[l] ?? PRODUCT_META[l].label}
                  state={state}
                  title={`${PRODUCT_META[l].label}: ${p?.held ? "in use" : "not used"}${p?.note ? `\n${p.note}` : ""}`}
                />
              );
            })}
          </div>
          <p className="flex items-center gap-3 text-xs text-neutral-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-sm bg-emerald-500" aria-hidden /> in use
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-sm bg-white ring-1 ring-neutral-300" aria-hidden /> not used
            </span>
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
            <NbaPanel card={card.data} />
          </>
        )}
      </div>
    </div>
  );
}
