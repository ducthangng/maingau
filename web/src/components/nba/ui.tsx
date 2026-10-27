import type { ReactNode } from "react";
import { TriangleAlert } from "lucide-react";
import type { Candidate, CustomerCard, SourceInfo } from "../../types/contracts";
import { CHANNEL_LABEL, NOT_ENOUGH } from "../../lib/format";
import type { Decision } from "../../lib/decisions";

// Small shared pieces for the right card (README §4.2 C1–C8). Display only: nothing here
// re-derives valuation, ranking or rules.

export type Sources = Record<string, SourceInfo> | undefined;
export type Status = NonNullable<CustomerCard["chosen"]["status"]>;

export const ACTION_TYPE_LABEL: Record<Candidate["action_type"], string> = {
  sales: "Sales",
  upsell: "Upsell",
  retention: "Retention",
  one_off: "One-off",
  service: "Service",
};

export function toneLabel(t: string | null | undefined): string {
  if (t === "du") return "Du";
  if (t === "sie") return "Sie";
  return NOT_ENOUGH;
}

export function channelLabel(c: string | null | undefined): string {
  if (!c) return NOT_ENOUGH;
  return CHANNEL_LABEL[c] ?? c;
}

const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** chosen.send_at is either an ISO datetime or plain text ("next login"). */
export function sendAtLabel(v: string | null | undefined): string | null {
  if (!v) return null;
  if (/^\d{4}-\d{2}-\d{2}T/.test(v)) {
    const d = new Date(v);
    if (!Number.isNaN(d.getTime())) return dateTimeFmt.format(d);
  }
  return v;
}

export function tsLabel(ts: string | null | undefined): string {
  if (!ts) return NOT_ENOUGH;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : dateTimeFmt.format(d);
}

export function Missing({ children = NOT_ENOUGH }: { children?: ReactNode }) {
  return <span className="text-neutral-400 italic">{children}</span>;
}

const STATUS_STYLE: Record<Status, string> = {
  proposed: "bg-neutral-100 text-neutral-600 ring-neutral-200",
  approved: "bg-accent-50 text-accent-700 ring-accent-100",
  overridden: "bg-accent-50 text-accent-700 ring-accent-100",
  rejected: "bg-red-50 text-red-700 ring-red-200",
  revoked: "bg-neutral-100 text-neutral-500 ring-neutral-200",
};

export function StatusChip({ status, label }: { status: Status; label?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${STATUS_STYLE[status]}`}>
      {label ?? status}
    </span>
  );
}

export function RuleChip({ rule, title }: { rule: string; title?: string }) {
  return (
    <span
      title={title ?? rule}
      className="inline-flex whitespace-nowrap rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px] text-neutral-700 ring-1 ring-inset ring-neutral-200"
    >
      {rule}
    </span>
  );
}

export function Pill({ children, title, tone = "neutral" }: { children: ReactNode; title?: string; tone?: "neutral" | "warn" | "accent" }) {
  const style =
    tone === "warn"
      ? "bg-neutral-100 text-neutral-800 ring-neutral-300"
      : tone === "accent"
        ? "bg-accent-50 text-accent-700 ring-accent-100"
        : "bg-neutral-50 text-neutral-700 ring-neutral-200";
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs ring-1 ring-inset ${style}`}>
      {tone === "warn" && <TriangleAlert size={11} className="shrink-0 text-neutral-500" aria-hidden />}
      {children}
    </span>
  );
}

/** Status shown on an NBA card: the latest local decision wins over the engine's proposal. */
export function statusFor(tupleId: string, chosenTuple: string, engineStatus: Status | undefined, latest: Decision | undefined) {
  if (tupleId === chosenTuple) {
    if (!latest) return { status: engineStatus ?? "proposed", label: undefined };
    if (latest.action === "overridden") return { status: "overridden" as Status, label: "overridden" };
    return { status: latest.action as Status, label: undefined };
  }
  if (latest?.action === "overridden" && latest.tuple_id === tupleId) return { status: "approved" as Status, label: "chosen by override" };
  return { status: "proposed" as Status, label: "alternative" };
}

/** Highlight a blocked row or reason text that mentions a signal id like "S3". */
export function mentionsSignal(textValue: string | null | undefined, signal: string | null): boolean {
  if (!signal || !textValue) return false;
  return new RegExp(`\\b${signal.replace(/[^A-Za-z0-9]/g, "")}\\b`).test(textValue);
}
