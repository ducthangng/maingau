import type { ReactNode } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Ban,
  BellOff,
  Check,
  EyeOff,
  Frown,
  Gem,
  Headset,
  Languages,
  LayoutPanelTop,
  LifeBuoy,
  Mail,
  MessageSquare,
  Newspaper,
  Phone,
  Repeat2,
  Smartphone,
  TrendingDown,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import { CHANNEL_LABEL } from "../lib/format";

// Small visual encodings shared by the worklist and the customer pop-up: icons instead of words,
// thin bars instead of number columns. Magnitude uses the one accent hue; status colours are only
// used for decision state and always come with an icon and a label (or a tooltip naming it).

/* ---------------------------------------------------------------- icons */

export const CHANNEL_ICON: Record<string, LucideIcon> = {
  newsletter_email: Newspaper,
  email: Mail,
  portal_popup: LayoutPanelTop,
  app_push: Smartphone,
  sms: MessageSquare,
  outbound_call: Phone,
  service_agent: Headset,
};

export function ChannelIcon({ channel, size = 14, className = "" }: { channel: string | null | undefined; size?: number; className?: string }) {
  const Icon = (channel && CHANNEL_ICON[channel]) || Mail;
  return <Icon size={size} aria-label={channel ? (CHANNEL_LABEL[channel] ?? channel) : undefined} className={className} />;
}

type FlagMeta = { icon: LucideIcon; label: string; tone: "red" | "amber" | "green" | "neutral" };

export const FLAG_META: Record<string, FlagMeta> = {
  service_critical: { icon: LifeBuoy, label: "Service critical", tone: "red" },
  no_marketing_channel: { icon: Ban, label: "No marketing channel", tone: "red" },
  negative_clv: { icon: TrendingDown, label: "Negative CLV", tone: "red" },
  annoyed_before: { icon: Frown, label: "Annoyed before", tone: "red" },
  contact_fatigue: { icon: BellOff, label: "Contact fatigue", tone: "amber" },
  data_inconsistent: { icon: TriangleAlert, label: "Data inconsistent", tone: "amber" },
  no_profiling: { icon: EyeOff, label: "No profiling consent", tone: "neutral" },
  prefers_en: { icon: Languages, label: "Prefers English", tone: "neutral" },
  top_clv: { icon: Gem, label: "Top 10% CLV", tone: "green" },
};

const ICON_TONE = {
  red: "bg-red-50 text-red-600 ring-red-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  neutral: "bg-neutral-50 text-neutral-500 ring-neutral-200",
};

/** One flag as a small icon square; the label is in the tooltip and for screen readers. */
export function FlagIcon({ id, title }: { id: string; title?: string }) {
  const m = FLAG_META[id] ?? { icon: TriangleAlert, label: id.replace(/_/g, " "), tone: "neutral" as const };
  const Icon = m.icon;
  const label = title ? `${m.label}: ${title}` : m.label;
  return (
    <span title={label} aria-label={label} role="img" className={`inline-grid size-[18px] place-items-center rounded ring-1 ring-inset ${ICON_TONE[m.tone]}`}>
      <Icon size={11} aria-hidden />
    </span>
  );
}

export function FlagIcons({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  return (
    <span className="inline-flex gap-0.5">
      {flags.map((f) => (
        <FlagIcon key={f} id={f} />
      ))}
    </span>
  );
}

/* ---------------------------------------------------------------- bars */

/**
 * Horizontal magnitude bar on a shared scale (0 → max). Negative values draw in red from the left
 * so a loss never looks like a small gain.
 */
export function ValueBar({ value, max, className = "", tone = "accent" }: { value: number; max: number; className?: string; tone?: "accent" | "muted" | "green" }) {
  const w = max > 0 ? Math.min(100, (Math.abs(value) / max) * 100) : 0;
  const fill = value < 0 ? "bg-red-500" : tone === "accent" ? "bg-accent-500" : tone === "green" ? "bg-emerald-500" : "bg-neutral-300";
  return (
    <span className={`block h-1.5 w-full overflow-hidden rounded-full bg-neutral-100 ${className}`} aria-hidden>
      <span className={`block h-full rounded-full ${fill}`} style={{ width: `${Math.max(w, value === 0 ? 0 : 3)}%` }} />
    </span>
  );
}

const CONF_STEPS: Record<string, number> = { low: 1, medium: 2, high: 3 };

/** Confidence as three ascending bars (like signal strength); the word is in the tooltip. */
export function ConfidenceBars({ confidence }: { confidence: string | null | undefined }) {
  const n = confidence ? (CONF_STEPS[confidence] ?? 0) : 0;
  return (
    <span className="inline-flex items-end gap-[2px]" title={`${confidence ?? "unknown"} confidence`} role="img" aria-label={`${confidence ?? "unknown"} confidence`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`w-[3px] rounded-sm ${i <= n ? "bg-neutral-700" : "bg-neutral-200"}`} style={{ height: 4 + i * 3 }} />
      ))}
    </span>
  );
}

/** A 0–1 probability as a short meter with the % beside it. */
export function ProbMeter({ p, children }: { p: number; children?: ReactNode }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-12 shrink-0 overflow-hidden rounded-full bg-neutral-100" aria-hidden>
        <span className="block h-full rounded-full bg-accent-500" style={{ width: `${Math.max(2, Math.min(100, p * 100))}%` }} />
      </span>
      {children}
    </span>
  );
}

/** Risk 0–1 as a meter whose colour steps up with the level (label always beside it). */
export function RiskMeter({ v }: { v: number }) {
  const fill = v >= 0.5 ? "bg-red-500" : v >= 0.25 ? "bg-amber-400" : "bg-emerald-500";
  return (
    <span className="block h-1.5 w-full overflow-hidden rounded-full bg-neutral-100" aria-hidden>
      <span className={`block h-full rounded-full ${fill}`} style={{ width: `${Math.max(2, Math.min(100, v * 100))}%` }} />
    </span>
  );
}

/* ---------------------------------------------------------------- decision state */

export type DecisionState = "pending" | "approved" | "overridden" | "rejected";

export const DECISION_META: Record<DecisionState, { label: string; icon: LucideIcon | null; dot: string; text: string }> = {
  approved: { label: "Approved", icon: Check, dot: "bg-emerald-500", text: "text-emerald-700" },
  overridden: { label: "Overridden", icon: Repeat2, dot: "bg-accent-500", text: "text-accent-700" },
  rejected: { label: "Rejected", icon: X, dot: "bg-red-500", text: "text-red-700" },
  pending: { label: "To review", icon: null, dot: "bg-neutral-300", text: "text-neutral-600" },
};

/* ---------------------------------------------------------------- direction */

export type Direction = "up" | "down" | "flat";

const DIR_META: Record<Direction, { icon: LucideIcon; cls: string; word: string }> = {
  up: { icon: ArrowUpRight, cls: "text-emerald-600", word: "up" },
  down: { icon: ArrowDownRight, cls: "text-red-600", word: "down" },
  flat: { icon: ArrowRight, cls: "text-neutral-400", word: "flat" },
};

/** A number that says which way it points: coloured arrow + neutral number, direction named in the tooltip. */
export function Signed({
  dir,
  children,
  title,
  good = "up",
  className = "",
}: {
  dir: Direction;
  children: ReactNode;
  title?: string;
  /** Which direction is good for this measure (churn: "down"). */
  good?: "up" | "down";
  className?: string;
}) {
  const m = DIR_META[dir];
  const tone = dir === "flat" ? m.cls : dir === good ? "text-emerald-600" : "text-red-600";
  const Icon = m.icon;
  return (
    <span className={`inline-flex items-center gap-0.5 whitespace-nowrap tabular-nums ${className}`} title={title}>
      <Icon size={14} strokeWidth={2.5} className={`shrink-0 ${tone}`} aria-label={m.word} />
      {children}
    </span>
  );
}

export function dirOf(v: number, ref = 0, eps = 1e-9): Direction {
  return v > ref + eps ? "up" : v < ref - eps ? "down" : "flat";
}

/** Probability meter with a reference tick (e.g. the no-contact baseline) and an arrow vs that reference. */
export function ProbVsRef({ p, baseline, refLabel, max = 1 }: { p: number; baseline: number | null | undefined; refLabel: string; max?: number }) {
  const ref = baseline;
  const pos = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  const has = typeof ref === "number";
  const ratio = has && ref! > 0 ? p / ref! : null;
  const title = has ? `${(p * 100).toFixed(1)}% vs ${refLabel} ${(ref! * 100).toFixed(1)}%${ratio ? ` (${ratio.toFixed(1)}×)` : ""}` : `${(p * 100).toFixed(1)}%`;
  return (
    <span className="flex items-center gap-2" title={title}>
      <span className="relative h-1.5 w-16 shrink-0 rounded-full bg-neutral-100" aria-hidden>
        <span className="absolute inset-y-0 left-0 rounded-full bg-accent-500" style={{ width: pos(p) }} />
        {has && <span className="absolute -top-1 h-3.5 w-[2px] rounded-full bg-neutral-800" style={{ left: pos(ref!) }} />}
      </span>
      {has ? (
        <Signed dir={dirOf(p, ref!, 0.0005)}>{(p * 100).toFixed(1)}%</Signed>
      ) : (
        <span className="tabular-nums">{(p * 100).toFixed(1)}%</span>
      )}
    </span>
  );
}
