import type { IndexRow } from "../types/contracts";

export type Tier = NonNullable<IndexRow["urgency_tier"]>;

const TIER_STYLE: Record<Tier, string> = {
  P1: "bg-red-600 text-white",
  P2: "bg-accent-700 text-white",
  P3: "bg-accent-100 text-accent-800",
  P4: "bg-neutral-200 text-neutral-700",
  P5: "bg-neutral-100 text-neutral-500",
};

export const TIER_LABEL: Record<Tier, string> = {
  P1: "Act now (service)",
  P2: "High",
  P3: "Time-bound opportunity",
  P4: "Opportunity",
  P5: "No trigger",
};

export function TierChip({ tier }: { tier: Tier | undefined }) {
  const t = tier ?? "P5";
  return (
    <span title={TIER_LABEL[t]} className={`inline-flex rounded px-1.5 py-0.5 text-xs font-semibold tabular-nums ${TIER_STYLE[t]}`}>
      {t}
    </span>
  );
}

export const OUTLIER_FLAGS = new Set(["service_critical", "no_marketing_channel", "negative_clv", "annoyed_before", "prefers_en"]);

export function FlagBadge({ id, label, title }: { id: string; label?: string; title?: string }) {
  const style =
    id === "top_clv"
      ? "bg-accent-50 text-accent-700 ring-accent-100"
      : OUTLIER_FLAGS.has(id)
        ? "bg-red-50 text-red-700 ring-red-200"
        : "bg-neutral-50 text-neutral-600 ring-neutral-200";
  return (
    <span title={title} className={`inline-flex whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset ${style}`}>
      {label ?? id.replace(/_/g, " ")}
    </span>
  );
}

export function ConfidenceDot({ confidence }: { confidence: string | null | undefined }) {
  if (!confidence) return <span className="text-neutral-400">—</span>;
  const color = confidence === "high" ? "bg-accent-600" : confidence === "medium" ? "bg-accent-300" : "bg-neutral-300";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-neutral-600">
      <span className={`size-2 rounded-full ${color}`} />
      {confidence}
    </span>
  );
}

// A card section with a small uppercase heading; `uiRef` makes it a jump target for path chips.
export function Section({
  title,
  uiRef,
  children,
  aside,
}: {
  title: string;
  uiRef?: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <section data-ui-ref={uiRef} className="scroll-mt-24 rounded-lg transition-colors duration-500">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}
