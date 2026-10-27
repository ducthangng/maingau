import { X } from "lucide-react";
import { dismissDecisionError, useDecisionErrors } from "../lib/decisions";
import { tupleLabel } from "../lib/format";

// UI labels for the rule IDs in a 409 refusal (docs/api.md §4).
const RULE_LABEL: Record<string, string> = {
  "CONSENT-CHANNEL": "No consent for this channel",
  "CHANNEL-AVAILABLE": "Channel not available (no portal account / app)",
  "CONSENT-PROFILING": "No profiling consent: only non-personalised offers, tone Sie",
  "EXCL-DUNNING": "Sales blocked: dunning",
  "EXCL-CANCELLATION": "Sales blocked: cancellation",
  "EXCL-OPEN-TICKET": "Sales blocked: open ticket",
  "EXCL-AUTOSTROM-CANCELLED": "Sales blocked: Autostrom cancelled",
  "HOLDING-PRECONDITION": "Already owned, prerequisite missing, or the proposal changed",
  "CONTACT-CAP": "Contact limit reached; the action waits until it frees up",
  "ECON-NONPOSITIVE": "Expected ΔCLV ≤ 0",
  "DATA-MISSING": "Not enough data, or a combination the engine did not evaluate",
};

const label = (id: string) => RULE_LABEL[id] ?? (/^[BU]-/.test(id) ? `Rule Center rule ${id}` : id);

/** Decisions the API refused; the local entry was removed, so the reviewer sees why and picks again. */
export default function DecisionErrors() {
  const errors = useDecisionErrors();
  if (!errors.length) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex max-h-[60vh] w-[min(26rem,calc(100vw-2rem))] flex-col gap-2 overflow-y-auto" role="alert">
      {errors.map((e) => (
        <div key={e.id} className="rounded-xl border border-red-200 bg-white p-3 text-sm shadow-lg">
          <div className="flex items-start gap-2">
            <p className="min-w-0 flex-1 font-medium text-red-800">
              Not saved: {e.action.replace(/ed$/, "e")} {e.customer_id} · {tupleLabel(e.tuple_id)}
            </p>
            <button
              type="button"
              onClick={() => dismissDecisionError(e.id)}
              className="rounded p-0.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
              aria-label="Dismiss"
            >
              <X size={14} aria-hidden />
            </button>
          </div>
          {e.rule_ids.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-neutral-700">
              {e.rule_ids.map((id) => (
                <li key={id}>
                  <span className="font-mono text-neutral-500">{id}</span> {label(id)}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-1 text-xs text-neutral-500">{e.reasons.join("; ")}</p>
        </div>
      ))}
    </div>
  );
}
