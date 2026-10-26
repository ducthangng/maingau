import type { ReactNode } from "react";
import type { Fact, SourceInfo } from "../../types/contracts";
import { isMissing } from "../../lib/format";

export type Sources = Record<string, SourceInfo> | undefined;

/** Classes for any element that is a jump target (data-ui-ref) so the flash from Customer.jumpTo looks right. */
export const REF_CLS = "scroll-mt-24 rounded-md transition-colors duration-500";

/** Chart colours: hex equivalents of the accent tokens in index.css (SVG attributes do not resolve CSS vars everywhere). */
export const CHART = {
  accent: "#007cd9",
  accentSoft: "#d4ebff",
  red: "#dc2626",
  grid: "#e5e5e5",
  axis: "#a3a3a3",
};

const numFmt = (digits: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: digits });

export function num(v: number, digits = 0): string {
  return numFmt(digits).format(v);
}

/** Formatter factory for FactValue: number with unit. */
export const withUnit =
  (unit: string, digits = 0) =>
  (v: number) =>
    `${num(v, digits)} ${unit}`;

/** ISO datetime or date -> YYYY-MM-DD; anything else unchanged. */
export function day(v: string): string {
  return /^\d{4}-\d{2}-\d{2}/.test(v) ? v.slice(0, 10) : v;
}

export function humanize(v: string): string {
  return v.replace(/_/g, " ");
}

/** Items in products.*.items and similar dicts hold Fact-shaped values; narrow one safely. */
export function asFact(v: unknown): Fact | null {
  if (v && typeof v === "object" && "src" in (v as Record<string, unknown>)) return v as Fact;
  return null;
}

/** True when the item has the key with a real (non-null) value. */
export function hasValue(item: Record<string, unknown>, key: string): boolean {
  const f = asFact(item[key]);
  return !!f && !isMissing(f.v) && f.v !== "";
}

export function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="truncate text-sm text-neutral-900">{children}</dd>
    </div>
  );
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-neutral-400 italic">{children}</span>;
}
