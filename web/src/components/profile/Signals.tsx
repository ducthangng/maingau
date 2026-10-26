import { Sparkles } from "lucide-react";
import type { CustomerCard, Signal } from "../../types/contracts";
import { sourceTitle } from "../Source";
import { Section } from "../Chips";
import { REF_CLS } from "./shared";

/** B2: 2–3 genuinely unusual facts, each citing its column(s). */
export function Highlights({ card }: { card: CustomerCard }) {
  const hl = (card.profile.highlights ?? []).slice(0, 3);
  if (hl.length === 0) return null;
  return (
    <Section title="Highlights">
      <ul className="space-y-1.5">
        {hl.map((h) => (
          <li
            key={h.text}
            className="flex cursor-help items-start gap-2 text-sm"
            title={[
              ...h.basis.map((b) => sourceTitle(b, null, card.sources)),
              h.rarity ? `rarity: ${h.rarity}` : null,
            ]
              .filter(Boolean)
              .join("\n")}
          >
            <Sparkles className="mt-0.5 size-4 shrink-0 text-accent-500" aria-hidden />
            <span className="min-w-0">
              <span className="font-medium">{h.text}</span>
              {h.rarity && <span className="ml-1.5 text-xs text-neutral-500">{h.rarity}</span>}
              <span className="ml-1.5 font-mono text-[10px] text-neutral-400">{h.basis.join(", ")}</span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

const STRENGTH_DOT: Record<Signal["strength"], string> = {
  strong: "bg-accent-600",
  medium: "bg-accent-500/60",
  weak: "bg-neutral-300",
};

/** B4: signal chips. Clicking one highlights the NBAs it drives on the right. */
export function SignalChips({
  card,
  activeSignal,
  onSignalClick,
}: {
  card: CustomerCard;
  activeSignal: string | null;
  onSignalClick: (id: string) => void;
}) {
  const signals = card.signals ?? [];
  return (
    <Section title="Signals" aside={signals.length > 0 ? <span className="text-[11px] text-neutral-400">click to highlight the actions they drive</span> : undefined}>
      {signals.length === 0 ? (
        <p className="text-sm text-neutral-500">No signal fired for this customer.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {signals.map((sg) => {
            const active = activeSignal === sg.id;
            return (
              <button
                key={sg.id}
                type="button"
                data-ui-ref={`signal:${sg.id}`}
                aria-pressed={active}
                onClick={() => onSignalClick(sg.id)}
                title={[sg.detail, sourceTitle(sg.src, null, card.sources), sg.evidence?.length ? `evidence: ${sg.evidence.join(", ")}` : null]
                  .filter(Boolean)
                  .join("\n")}
                className={`${REF_CLS} inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-left text-xs ring-1 ring-inset transition-colors duration-150 ${
                  active
                    ? "bg-accent-600 text-white ring-accent-600"
                    : "bg-white text-neutral-700 ring-neutral-200 hover:bg-neutral-50 hover:ring-neutral-300"
                }`}
              >
                <span className={`size-1.5 shrink-0 rounded-full ${active ? "bg-white" : STRENGTH_DOT[sg.strength]}`} aria-hidden />
                <span className="font-semibold">{sg.id}</span>
                <span className="truncate">
                  {sg.label}
                  {sg.date ? ` · ${sg.date}` : ""} · {sg.strength}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Section>
  );
}
