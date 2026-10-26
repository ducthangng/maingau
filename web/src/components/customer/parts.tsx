import type { ReactNode } from "react";
import { Activity, ChevronDown, Cpu, FileText, LifeBuoy, type LucideIcon } from "lucide-react";
import type { Candidate, Signal } from "../../types/contracts";

// Pieces shared by the pop-up's profile column and its action graph.

export function Label({ children }: { children: ReactNode }) {
  return <h4 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">{children}</h4>;
}

export function ShowMore({ open, onToggle, more = "Show more", less = "Show less" }: { open: boolean; onToggle: () => void; more?: string; less?: string }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="inline-flex items-center gap-0.5 text-xs font-medium text-accent-600 transition-colors duration-150 hover:text-accent-700"
    >
      {open ? less : more}
      <ChevronDown size={14} aria-hidden className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
    </button>
  );
}

export const PURPOSE_ICON: Record<Signal["purpose"], LucideIcon> = {
  contract: FileText,
  device: Cpu,
  behavioural: Activity,
  service: LifeBuoy,
};

const STRENGTH_STEPS: Record<Signal["strength"], number> = { weak: 1, medium: 2, strong: 3 };

export function StrengthBars({ strength }: { strength: Signal["strength"] }) {
  const n = STRENGTH_STEPS[strength];
  return (
    <span className="inline-flex items-end gap-[2px]" role="img" aria-label={`${strength} signal`} title={`${strength} signal`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`w-[3px] rounded-sm ${i <= n ? "bg-accent-600" : "bg-neutral-200"}`} style={{ height: 4 + i * 3 }} />
      ))}
    </span>
  );
}

/** A signal as a compact chip: what kind of evidence (icon), what it says, how strong. */
export function SignalChip({ sig }: { sig: Signal }) {
  const Icon = PURPOSE_ICON[sig.purpose] ?? Activity;
  return (
    <span
      className="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-accent-50 px-2 py-1 text-xs text-accent-700 ring-1 ring-inset ring-accent-100"
      title={[`${sig.id} · ${sig.purpose}`, sig.detail, sig.src].filter(Boolean).join("\n")}
    >
      <Icon size={13} className="shrink-0" aria-hidden />
      <span className="truncate">{sig.label}</span>
      <StrengthBars strength={sig.strength} />
    </span>
  );
}

/** Upside if the customer accepts: CLV after accept minus CLV now (both from the engine's valuation). */
export const upsideOf = (c: Candidate | undefined) => (c?.valuation ? c.valuation.clv_after_accept - c.valuation.clv_now_model : null);
