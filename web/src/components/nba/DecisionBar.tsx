import { useId, useMemo, useState } from "react";
import { Check, Repeat2, X } from "lucide-react";
import type { Candidate, CustomerCard } from "../../types/contracts";
import { recordDecisions, rejectText, REVIEWER, type DecisionAction, type ReasonCode } from "../../lib/decisions";
import { signedEur, tupleLabel } from "../../lib/format";
import { OVERRIDE_REASONS, RejectReasonSelect, whyCode, whyOk, whyText } from "../customer/NbaPanel";

// C8 human in the loop. Decisions go to the local decision log only; there is no send button.
// Override choices are limited to tuples the engine already gated (Q-CARDS-13), so a blocked
// combination can never be selected here. Reject and override need a reason from a list, so the
// decision carries a reason_code the feedback memory can act on; the note is optional.

type Panel = null | "override" | "reject";

const btn =
  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40";
const select =
  "w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100";

function record(
  card: CustomerCard,
  action: DecisionAction,
  target: Candidate | undefined,
  tupleId: string,
  reason: string | null,
  code: ReasonCode | null = null,
) {
  const v = target?.valuation;
  recordDecisions([
    {
      customer_id: card.customer_id,
      action,
      tuple_id: tupleId,
      from_tuple: card.chosen.tuple_id,
      reason,
      reason_code: code,
      reviewer: REVIEWER,
      delta_clv: v?.delta_clv ?? null,
      p_accept: v?.p_accept ?? null,
      group: null,
      holdout: false,
    },
  ]);
}

export function DecisionBar({
  card,
  variant,
  candidate,
  allowOverride = true,
}: {
  card: CustomerCard;
  /** "top" acts on the engine's choice; "alternative" offers this candidate as an override. */
  variant: "top" | "alternative";
  candidate: Candidate | undefined;
  allowOverride?: boolean;
}) {
  const [panel, setPanel] = useState<Panel>(null);
  const [reason, setReason] = useState(""); // the note under the reason
  const [preset, setPreset] = useState(""); // override reason (OVERRIDE_REASONS)
  const [code, setCode] = useState<ReasonCode | "">(""); // reject reason
  const [saved, setSaved] = useState<string | null>(null);
  const others = useMemo(
    () => (card.candidates ?? []).filter((c) => c.tuple_id !== card.chosen.tuple_id),
    [card.candidates, card.chosen.tuple_id],
  );
  const [target, setTarget] = useState<string>(variant === "alternative" ? (candidate?.tuple_id ?? "") : (others[0]?.tuple_id ?? ""));
  const reasonId = useId();
  const selectId = useId();
  const codeId = useId();
  const why = { preset, note: reason };

  const close = () => {
    setPanel(null);
    setReason("");
    setPreset("");
    setCode("");
  };
  const done = (msg: string) => {
    close();
    setSaved(msg);
  };

  const approve = () => {
    record(card, "approved", candidate, card.chosen.tuple_id, null);
    done("Approved");
  };
  const reject = () => {
    if (!code) return;
    record(card, "rejected", candidate, card.chosen.tuple_id, rejectText(code, reason), code);
    done("Rejected");
  };
  const override = () => {
    const to = others.find((c) => c.tuple_id === target);
    if (!to || !whyOk(why)) return;
    record(card, "overridden", to, to.tuple_id, whyText(why), whyCode(why, card.chosen.tuple_id, to.tuple_id));
    done(`Overridden → ${tupleLabel(to.tuple_id)}`);
  };

  const reasonPick = (control: React.ReactNode) => (
    <div className="space-y-1">
      <label htmlFor={codeId} className="text-xs font-medium text-neutral-600">
        Reason <span className="text-neutral-400">(required)</span>
      </label>
      {control}
    </div>
  );

  const reasonBox = (placeholder: string, required: boolean) => (
    <div className="space-y-1">
      <label htmlFor={reasonId} className="text-xs font-medium text-neutral-600">
        Note <span className="text-neutral-400">({required ? "required" : "optional"})</span>
      </label>
      <textarea
        id={reasonId}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        placeholder={placeholder}
        className="w-full resize-y rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100"
      />
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {variant === "top" ? (
          <>
            <button type="button" onClick={approve} className={`${btn} bg-accent-600 text-white hover:bg-accent-700`}>
              <Check size={16} aria-hidden /> Approve
            </button>
            {allowOverride && (
              <button
                type="button"
                onClick={() => setPanel(panel === "override" ? null : "override")}
                aria-expanded={panel === "override"}
                disabled={others.length === 0}
                title={others.length === 0 ? "No other engine-gated combination for this customer" : "Change channel, tone or offer"}
                className={`${btn} bg-white text-neutral-800 ring-1 ring-inset ring-neutral-200 hover:bg-neutral-50`}
              >
                <Repeat2 size={16} aria-hidden /> Override…
              </button>
            )}
            <button
              type="button"
              onClick={() => setPanel(panel === "reject" ? null : "reject")}
              aria-expanded={panel === "reject"}
              className={`${btn} bg-white text-red-700 ring-1 ring-inset ring-neutral-200 hover:bg-red-50`}
            >
              <X size={16} aria-hidden /> Reject…
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setPanel(panel === "override" ? null : "override")}
            aria-expanded={panel === "override"}
            className={`${btn} bg-white text-neutral-800 ring-1 ring-inset ring-neutral-200 hover:bg-neutral-50`}
          >
            <Repeat2 size={16} aria-hidden /> Use this instead…
          </button>
        )}
        {saved && !panel && (
          <span className="text-xs text-neutral-500" role="status">
            {saved} · saved in this browser, nothing is sent
          </span>
        )}
      </div>

      {panel === "override" && (
        <div className="space-y-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3">
          {variant === "top" ? (
            <div className="space-y-1">
              <label htmlFor={selectId} className="text-xs font-medium text-neutral-600">
                Change channel, tone or offer
              </label>
              <select id={selectId} value={target} onChange={(e) => setTarget(e.target.value)} className={select}>
                {others.map((c) => (
                  <option key={c.tuple_id} value={c.tuple_id}>
                    {c.rank ? `#${c.rank} ` : ""}
                    {c.offer_name} · {tupleLabel(c.tuple_id)} · ΔCLV {signedEur(c.valuation?.delta_clv)}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <p className="text-sm text-neutral-700">
              Replace the engine's choice with <span className="font-medium">{tupleLabel(candidate?.tuple_id)}</span>.
            </p>
          )}
          <p className="text-xs text-neutral-500">Only combinations that passed every rule can be selected.</p>
          {reasonPick(
            <select id={codeId} value={preset} onChange={(e) => setPreset(e.target.value)} className={select}>
              <option value="" disabled>
                Why this one?
              </option>
              {Object.keys(OVERRIDE_REASONS).map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>,
          )}
          {reasonBox("Why is this the better action?", preset === "Other")}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={override}
              disabled={!whyOk(why) || !others.some((c) => c.tuple_id === target)}
              className={`${btn} bg-neutral-900 text-white hover:bg-neutral-700`}
            >
              Confirm override
            </button>
            <button type="button" onClick={close} className={`${btn} text-neutral-600 hover:bg-neutral-100`}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {panel === "reject" && (
        <div className="space-y-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3">
          {reasonPick(<RejectReasonSelect id={codeId} value={code} onChange={setCode} className={select} />)}
          {reasonBox("e.g. customer asked not to be contacted about this", false)}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={reject}
              disabled={!code}
              className={`${btn} bg-red-600 text-white hover:bg-red-700`}
            >
              Confirm reject
            </button>
            <button type="button" onClick={close} className={`${btn} text-neutral-600 hover:bg-neutral-100`}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
