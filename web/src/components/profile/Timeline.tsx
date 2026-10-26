import { useMemo, useState } from "react";
import {
  CircleDot,
  FileText,
  House,
  LifeBuoy,
  Megaphone,
  Package,
  PlugZap,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  Wifi,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { CustomerCard, TimelineItem } from "../../types/contracts";
import { sourceTitle } from "../Source";
import { Section } from "../Chips";
import { REF_CLS } from "./shared";

const ICON: Record<string, LucideIcon> = {
  energy: Zap,
  autostrom: PlugZap,
  mobile: Smartphone,
  shop: ShoppingBag,
  smart_living: House,
  internet: Wifi,
  service: LifeBuoy,
  marketing: Megaphone,
  consent: ShieldCheck,
  contract: FileText,
  order: Package,
};

function iconFor(t: TimelineItem): LucideIcon {
  return (t.line && ICON[t.line]) || ICON[t.kind] || CircleDot;
}

const INITIAL = 8;

/** B3: vertical timeline, newest first, future milestones marked "upcoming". */
export function Timeline({ card }: { card: CustomerCard }) {
  const [all, setAll] = useState(false);
  const rows = useMemo(
    () => [...(card.timeline ?? [])].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)),
    [card.timeline],
  );
  const shown = all ? rows : rows.slice(0, INITIAL);

  return (
    <Section
      title="Timeline"
      aside={
        rows.length > INITIAL ? (
          <button
            type="button"
            onClick={() => setAll((v) => !v)}
            className="rounded px-1.5 text-xs text-accent-600 transition-colors duration-150 hover:text-accent-700"
          >
            {all ? "Show fewer" : `Show all (${rows.length})`}
          </button>
        ) : undefined
      }
    >
      {rows.length === 0 ? (
        <p className="text-sm text-neutral-400 italic">not enough data</p>
      ) : (
        <ol>
          {shown.map((t, i) => {
            const Icon = iconFor(t);
            const last = i === shown.length - 1;
            return (
              <li key={t.id} data-ui-ref={`timeline:${t.id}`} className={`${REF_CLS} relative flex gap-3 pb-3 last:pb-0`}>
                {!last && <span className="absolute top-7 bottom-0 left-[13px] w-px bg-neutral-200" aria-hidden />}
                <span
                  className={`relative z-[1] flex size-7 shrink-0 items-center justify-center rounded-full ring-1 ring-inset ${
                    t.future ? "bg-accent-50 text-accent-600 ring-accent-100" : "bg-white text-neutral-500 ring-neutral-200"
                  }`}
                >
                  <Icon className="size-3.5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-xs tabular-nums text-neutral-500">{t.date}</span>
                    {t.future && (
                      <span className="rounded bg-accent-50 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-accent-700">
                        upcoming
                      </span>
                    )}
                    <span className="text-sm font-medium">{t.title}</span>
                  </div>
                  {t.detail && <div className="text-xs text-neutral-500">{t.detail}</div>}
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                    {(t.flags ?? []).map((f) => (
                      <span key={f} className="rounded bg-amber-50 px-1.5 py-px text-[10px] text-amber-800 ring-1 ring-inset ring-amber-200">
                        {f}
                      </span>
                    ))}
                    <span
                      title={sourceTitle(t.src, null, card.sources) + (t.ref ? `\nref: ${t.ref}` : "")}
                      className="cursor-help font-mono text-[10px] text-neutral-400"
                    >
                      {t.src}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Section>
  );
}
