import { ArrowRight } from "lucide-react";
import type { PathStep } from "../../types/contracts";
import { CHANNEL_LABEL } from "../../lib/format";
import { Missing } from "./ui";

// C3 reasoning chain: Customer → Signal → Need → Offer → Channel → Consent ✓.
// Nodes with a ui_ref are buttons that scroll to and flash the matching row on the left card.

function shortLabel(s: PathStep): string {
  const label = s.label ?? "";
  switch (s.type) {
    case "Customer":
      return s.id ?? label;
    case "Signal":
      return [s.id, label.split(":")[0]].filter(Boolean).join(" · ");
    case "Offer":
      return [s.id, label].filter(Boolean).join(" ");
    case "Channel":
      return (s.id && CHANNEL_LABEL[s.id]) || label || s.id || s.type;
    case "Consent": {
      const mark = label.trim().endsWith("✓") ? " ✓" : label.trim().endsWith("✗") ? " ✗" : "";
      return `${s.id ?? label}${mark}`;
    }
    default:
      return label || s.id || s.type;
  }
}

export function ReasoningPath({ path, onNavigate }: { path: PathStep[] | null | undefined; onNavigate: (uiRef: string) => void }) {
  if (!path || path.length === 0) return <Missing />;
  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2" aria-label="Reasoning path">
      {path.map((s, i) => {
        if (s.kind === "edge") {
          return (
            <li key={i} className="flex items-center gap-0.5 text-[10px] font-medium uppercase tracking-wide text-neutral-400" title={s.label ?? s.type}>
              <span>{s.type.replace(/_/g, " ")}</span>
              <ArrowRight size={12} aria-hidden />
            </li>
          );
        }
        const text = shortLabel(s);
        const title = [s.type, s.label ?? s.id].filter(Boolean).join(": ");
        const body = (
          <>
            <span className="text-[10px] uppercase tracking-wide text-neutral-400">{s.type}</span>
            <span className="max-w-[9rem] truncate sm:max-w-[16rem]">{text}</span>
          </>
        );
        const base = "inline-flex max-w-full items-center gap-1.5 rounded-lg px-2 py-1 text-xs ring-1 ring-inset";
        return (
          <li key={i} className="min-w-0 max-w-full">
            {s.ui_ref ? (
              <button
                type="button"
                title={`${title}\nClick to show it in the profile`}
                onClick={() => onNavigate(s.ui_ref as string)}
                className={`${base} bg-white text-neutral-800 ring-neutral-200 transition-colors duration-150 hover:bg-accent-50 hover:text-accent-700 hover:ring-accent-100`}
              >
                {body}
              </button>
            ) : (
              <span title={title} className={`${base} bg-neutral-50 text-neutral-600 ring-neutral-100`}>
                {body}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
