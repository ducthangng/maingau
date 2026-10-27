import { useMemo, useState } from "react";
import { Check, ChevronDown, CircleSlash, LifeBuoy, Lock, Plus, ShieldBan, Trash2 } from "lucide-react";
import type { Alternative, Candidate, CustomerCard } from "../../types/contracts";
import { addRule, removeRule, rulesFor, useHardRules, violation, type HardRule, type RuleKind, type RuleScope } from "../../lib/hardRules";
import {
  latestByCustomer,
  recordDecisions,
  REJECT_REASONS,
  rejectText,
  removeDecision,
  REVIEWER,
  useDecisions,
  type DecisionAction,
  type ReasonCode,
} from "../../lib/decisions";
import { CHANNEL_LABEL, pct, signedEur, tupleLabel } from "../../lib/format";
import { WithSignalRefs } from "../nba/ActionCard";
import { RuleChip, StatusChip, statusFor, toneLabel } from "../nba/ui";
import { OFFER_NAME } from "../worklist/model";
import { ValueBar } from "../viz";

// Right column of the customer pop-up: the reviewer's hard rules, the engine's options ranked #1
// first (a readable headline, one line of why, one small bar; click to choose, ⌄ for details), and
// one decision box at the bottom. Hard rules only lock options; the engine's ranking is unchanged.

/* ---------------------------------------------------------------- hard rules */

export function ruleText(r: HardRule): string {
  if (r.kind === "block_channel") return `No ${CHANNEL_LABEL[r.value] ?? r.value}`;
  if (r.kind === "block_offer") return `No ${OFFER_NAME[r.value] ?? r.value}`;
  return `No contact until ${r.value}`;
}

export const scopeText = (r: HardRule) =>
  r.scope === "customer" ? "this customer" : r.scope === "segment" ? `segment ${r.targetLabel ?? r.target}` : "all customers";

const MARKETING_CHANNELS = ["newsletter_email", "email", "portal_popup", "app_push", "sms", "outbound_call"];

const field =
  "rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 text-sm focus:border-accent-500 focus:ring-2 focus:ring-accent-100 focus:outline-none";

function RuleForm({ card, onDone }: { card: CustomerCard; onDone: () => void }) {
  const offers = useMemo(() => [...new Set((card.candidates ?? []).map((c) => c.offer_id))], [card.candidates]);
  const [kind, setKind] = useState<RuleKind>("block_channel");
  const [value, setValue] = useState(MARKETING_CHANNELS[0]);
  const [scope, setScope] = useState<RuleScope>("customer");
  const [reason, setReason] = useState("");
  const arch = card.triage.archetype;

  const changeKind = (k: RuleKind) => {
    setKind(k);
    setValue(k === "block_channel" ? MARKETING_CHANNELS[0] : k === "block_offer" ? (offers[0] ?? "") : (card.meta?.eval_time ?? "").slice(0, 10));
  };

  const submit = () => {
    if (!value) return;
    addRule({
      kind,
      value,
      scope,
      target: scope === "customer" ? card.customer_id : scope === "segment" ? arch.id : null,
      targetLabel: scope === "customer" ? card.customer_id : scope === "segment" ? arch.name : null,
      reason: reason.trim() || null,
    });
    onDone();
  };

  return (
    <form
      className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-neutral-200"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="flex flex-col gap-2">
        <select aria-label="Rule type" value={kind} onChange={(e) => changeKind(e.target.value as RuleKind)} className={field}>
          <option value="block_channel">Block a channel</option>
          <option value="block_offer">Block an offer</option>
          <option value="pause_until">Pause contact until</option>
        </select>
        {kind === "block_channel" ? (
          <select aria-label="Channel" value={value} onChange={(e) => setValue(e.target.value)} className={field}>
            {MARKETING_CHANNELS.map((c) => (
              <option key={c} value={c}>
                {CHANNEL_LABEL[c]}
              </option>
            ))}
          </select>
        ) : kind === "block_offer" ? (
          <select aria-label="Offer" value={value} onChange={(e) => setValue(e.target.value)} className={field}>
            {offers.map((o) => (
              <option key={o} value={o}>
                {OFFER_NAME[o] ?? o}
              </option>
            ))}
          </select>
        ) : (
          <input aria-label="Until" type="date" value={value} onChange={(e) => setValue(e.target.value)} className={field} />
        )}
      </div>
      <div className="flex flex-col gap-1" role="radiogroup" aria-label="Applies to">
        <span className="text-xs text-neutral-500">Applies to</span>
        {(
          [
            ["customer", "This customer"],
            ["segment", `Segment: ${arch.name}`],
            ["all", "All customers"],
          ] as [RuleScope, string][]
        ).map(([s, label]) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={scope === s}
            onClick={() => setScope(s)}
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors duration-150 ${
              scope === s ? "bg-neutral-900 text-white" : "text-neutral-700 hover:bg-neutral-100"
            }`}
          >
            <span className={`size-3 shrink-0 rounded-full ring-1 ${scope === s ? "bg-white ring-white" : "ring-neutral-300"}`} aria-hidden />
            {label}
          </button>
        ))}
      </div>
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Why? (optional)"
        aria-label="Reason"
        className={`${field} w-full`}
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!value}
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-40"
        >
          Add rule
        </button>
        <button type="button" onClick={onDone} className="rounded-lg px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100">
          Cancel
        </button>
      </div>
    </form>
  );
}

function HardRules({ card, rules }: { card: CustomerCard; rules: HardRule[] }) {
  const [adding, setAdding] = useState(false);
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldBan size={15} className="text-neutral-400" aria-hidden />
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Hard rules</h3>
        <span className="text-xs text-neutral-400">set by people, applied before any action</span>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-accent-600 hover:bg-accent-50"
          >
            <Plus size={13} aria-hidden /> Add rule
          </button>
        )}
      </div>
      {rules.length === 0 && !adding && <p className="text-sm text-neutral-400">No hard rule covers this customer.</p>}
      {rules.length > 0 && (
        <ul className="space-y-1.5">
          {rules.map((r) => (
            <li key={r.id} className="flex items-center gap-2.5 rounded-lg bg-white px-3 py-2 text-sm ring-1 ring-neutral-200">
              <Lock size={13} className="shrink-0 text-neutral-500" aria-hidden />
              <span className="font-medium">{ruleText(r)}</span>
              <span className="truncate text-xs text-neutral-500" title={r.reason ?? undefined}>
                · {scopeText(r)}
                {r.reason ? ` · ${r.reason}` : ""}
              </span>
              <button
                type="button"
                onClick={() => removeRule(r.id)}
                className="ml-auto rounded p-1 text-neutral-300 hover:bg-neutral-100 hover:text-red-600"
                aria-label={`Remove rule ${ruleText(r)}`}
                title="Remove rule"
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {adding && <RuleForm card={card} onDone={() => setAdding(false)} />}
    </section>
  );
}

/* ---------------------------------------------------------------- ranking */

export interface Option {
  tuple: string;
  cand?: Candidate;
  alt?: Alternative;
}

const channelOf = (o: Option) => o.cand?.channel ?? o.tuple.split("|")[1];
const nameOf = (o: Option) => o.cand?.offer_name ?? tupleLabel(o.tuple);

/** Headline an agent can read aloud: "StromGarant via Newsletter". */
const headline = (o: Option) => `${nameOf(o)} via ${CHANNEL_LABEL[channelOf(o)] ?? channelOf(o)}`;

/** One plain line: what drives the option. */
function driver(card: CustomerCard, o: Option): string {
  if (o.cand?.action_type === "service") return "Resolves the open service issue";
  const sigs = (card.signals ?? []).filter((s) => o.cand?.signals?.includes(s.id)).map((s) => s.label);
  return sigs.length ? sigs.join(", ") : "Catalog offer, no specific signal";
}

function OptionItem({
  card,
  o,
  rank,
  top,
  maxDelta,
  lock,
  selected,
  onSelect,
  note,
}: {
  card: CustomerCard;
  o: Option;
  rank: number;
  top: boolean;
  maxDelta: number;
  lock: HardRule | undefined;
  selected: boolean;
  onSelect: () => void;
  /** Justification shown right under the row when it is chosen instead of #1. */
  note?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const c = o.cand;
  const v = c?.valuation;
  const d = v?.delta_clv ?? o.alt?.delta_clv ?? 0;
  const base = v?.p_source?.baseline_control;
  const lines = [...(c?.why ?? []), ...(c?.notes ?? [])];
  const failed = (c?.checks ?? []).filter((k) => !k.passed);
  const tone = toneLabel(c?.tone ?? o.tuple.split("|")[2]);

  return (
    <li
      className={`rounded-xl ring-1 transition-[box-shadow,background-color] duration-150 ${
        selected
          ? "bg-accent-50/60 ring-2 ring-accent-500"
          : "bg-white ring-neutral-200 hover:bg-neutral-50 hover:shadow-sm"
      } ${lock ? "opacity-60" : ""}`}
    >
      <div className="flex items-center gap-3 px-3.5 py-2.5">
        <button type="button" onClick={onSelect} aria-pressed={selected} className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-left">
          <span
            className={`grid size-6 shrink-0 place-items-center rounded-md text-xs font-semibold tabular-nums ${
              top ? "bg-gold-400 text-neutral-900" : selected ? "bg-accent-600 text-white" : "bg-neutral-100 text-neutral-600"
            }`}
            title={c?.rank ? `Engine rank #${c.rank}` : undefined}
          >
            {rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-neutral-900">
              {headline(o)} <span className="font-normal text-neutral-400">· {tone}</span>
            </span>
            <span className="flex items-center gap-1 truncate text-xs text-neutral-500">
              {lock && <Lock size={11} className="shrink-0" aria-hidden />}
              <span className="truncate">{lock ? `Locked: ${ruleText(lock)} (${scopeText(lock)})` : driver(card, o)}</span>
            </span>
          </span>
          <span className="hidden w-20 shrink-0 sm:block" title="Expected value, relative to the other options">
            <ValueBar value={d} max={maxDelta} tone={top || selected ? "accent" : "muted"} />
          </span>
        </button>
        <button
          type="button"
          onClick={() => setOpen((x) => !x)}
          aria-expanded={open}
          aria-label={open ? "Hide details" : "Show details"}
          title={open ? "Hide details" : "Show details"}
          className={`grid size-6 shrink-0 place-items-center rounded-md transition-colors duration-150 ${open ? "bg-neutral-900 text-white" : "text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800"}`}
        >
          <ChevronDown size={14} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>

      {note}

      {open && (
        <div className="space-y-2 border-t border-neutral-100 px-3.5 py-2.5 pl-12 text-xs leading-relaxed text-neutral-600">
          <p>
            {v ? (
              <>
                Expected value <span className="font-medium text-neutral-900">{signedEur(v.delta_clv)}</span> · chance{" "}
                <span className="font-medium text-neutral-900">{pct(v.p_accept)}</span>
                {typeof base === "number" && <> (without contact {pct(base)})</>} · {v.confidence} confidence
              </>
            ) : (
              <>Expected value {signedEur(d)}</>
            )}
            {c?.checks && <> · {failed.length ? `failed: ${failed.map((k) => k.rule_id).join(", ")}` : `all ${c.checks.length} rules passed`}</>}
          </p>
          {!top && o.alt?.why_lower && <p>Ranked lower: {o.alt.why_lower}</p>}
          {lines.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-4">
              {lines.map((l) => (
                <li key={l}>
                  <WithSignalRefs text={l} activeSignal={null} />
                </li>
              ))}
            </ul>
          )}
          {top && card.chosen.content?.body && (
            <div className="rounded-lg bg-neutral-50 p-2.5">
              <div className="mb-0.5 text-[10px] uppercase tracking-wide text-neutral-400">Message preview · {card.chosen.content.language}</div>
              {card.chosen.content.subject && <div className="font-medium text-neutral-800">{card.chosen.content.subject}</div>}
              <div>{card.chosen.content.body}</div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

/* ---------------------------------------------------------------- decision */

// Decision buttons: large, raised and with a pressed state so they read as the main action.
const btn =
  "inline-flex min-w-28 items-center justify-center rounded-xl px-5 py-2.5 text-sm font-semibold shadow-sm transition-[background-color,transform,box-shadow] duration-150 active:translate-y-px active:scale-[0.98] active:shadow-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100";

function recordFor(card: CustomerCard, action: DecisionAction, target: Option, why: string | null, code: ReasonCode | null = null) {
  recordDecisions([
    {
      customer_id: card.customer_id,
      action,
      tuple_id: target.tuple,
      from_tuple: card.chosen.tuple_id,
      reason: why,
      reason_code: code,
      reviewer: REVIEWER,
      delta_clv: target.cand?.valuation?.delta_clv ?? null,
      p_accept: target.cand?.valuation?.p_accept ?? null,
      group: null,
      holdout: false,
    },
  ]);
}

// Common reasons for choosing another option than the engine's #1, each with the code the API
// remembers for the engine's proposal (a recent talk makes it badly timed); "Other" needs a note.
export const OVERRIDE_REASONS: Record<string, ReasonCode> = {
  "Customer asked for this": "other",
  "Better channel for this customer": "wrong_channel",
  "More relevant right now": "not_relevant",
  "Recent talk with the customer": "wrong_timing",
  Other: "other",
};

export interface Why {
  preset: string;
  note: string;
}

export const whyOk = (w: Why) => !!w.preset && (w.preset !== "Other" || !!w.note.trim());
export const whyText = (w: Why) => (w.preset === "Other" ? w.note.trim() : w.note.trim() ? `${w.preset}: ${w.note.trim()}` : w.preset);
/** The preset's reason code; "wrong channel" only when the new option really uses another channel. */
export const whyCode = (w: Why, from?: string, to?: string): ReasonCode => {
  const code = OVERRIDE_REASONS[w.preset] ?? "other";
  return code === "wrong_channel" && from && to && from.split("|")[1] === to.split("|")[1] ? "other" : code;
};

// Small reason select and note, shared by the override note and the reject bar.
const pick = "rounded-md border border-neutral-200 bg-white py-1 pr-6 pl-2 text-xs text-neutral-700 focus:border-accent-500 focus:outline-none";
const noteField =
  "min-w-0 flex-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs placeholder:text-neutral-400 focus:border-accent-500 focus:outline-none";

/** Justification right under a newly chosen option: a reason dropdown and a short note. Approve is at the bottom. */
export function OverrideNote({ why, onChange }: { why: Why; onChange: (w: Why) => void }) {
  return (
    <div className="flex items-center gap-2 border-t border-accent-100 px-3.5 py-2 pl-12">
      <select autoFocus aria-label="Why this option" value={why.preset} onChange={(e) => onChange({ ...why, preset: e.target.value })} className={pick}>
        <option value="" disabled>
          Why this one?
        </option>
        {Object.keys(OVERRIDE_REASONS).map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      <input
        value={why.note}
        maxLength={80}
        onChange={(e) => onChange({ ...why, note: e.target.value })}
        placeholder={why.preset === "Other" ? "Short note (required)" : "Short note (optional)"}
        aria-label="Short note"
        className={noteField}
      />
    </div>
  );
}

/** The required reason for a reject, in plain words; the decision keeps its code (DecisionRequest.reason_code). */
export function RejectReasonSelect({
  value,
  onChange,
  id,
  autoFocus,
  className = pick,
}: {
  value: ReasonCode | "";
  onChange: (code: ReasonCode) => void;
  id?: string;
  autoFocus?: boolean;
  className?: string;
}) {
  return (
    <select
      id={id}
      autoFocus={autoFocus}
      required
      aria-label="Reject reason"
      value={value}
      onChange={(e) => onChange(e.target.value as ReasonCode)}
      className={className}
    >
      <option value="" disabled>
        Why reject?
      </option>
      {Object.entries(REJECT_REASONS).map(([code, label]) => (
        <option key={code} value={code}>
          {label}
        </option>
      ))}
    </select>
  );
}

export interface RejectWhy {
  code: ReasonCode | "";
  note: string;
}

/** Reject bar for the engine's proposal: a required reason and an optional note; Reject stays off until a reason is picked. */
export function RejectBar({
  why,
  onChange,
  onReject,
  onCancel,
}: {
  why: RejectWhy;
  onChange: (w: RejectWhy) => void;
  onReject: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2">
        <RejectReasonSelect autoFocus value={why.code} onChange={(code) => onChange({ ...why, code })} />
        <input
          value={why.note}
          maxLength={120}
          onChange={(e) => onChange({ ...why, note: e.target.value })}
          placeholder="Short note (optional)"
          aria-label="Short note"
          className={noteField}
        />
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" disabled={!why.code} onClick={onReject} className={`${btn} shrink-0 bg-red-600 text-white hover:bg-red-700`}>
          Reject
        </button>
        <button type="button" onClick={onCancel} className={`${btn} shrink-0 bg-white text-neutral-600 shadow-none hover:bg-neutral-100`}>
          Cancel
        </button>
      </div>
    </div>
  );
}

/**
 * The one place to act, for whichever option is selected. Approve on #1 approves the proposal; Approve
 * on another option saves an override with the reason picked under it. A saved override can be deleted.
 */
export function DecisionBox({ card, top, sel, lock, why }: { card: CustomerCard; top: Option; sel: Option; lock: HardRule | undefined; why: Why }) {
  const decisions = useDecisions();
  const latest = useMemo(
    () => latestByCustomer(decisions.filter((d) => d.customer_id === card.customer_id)).get(card.customer_id),
    [decisions, card.customer_id],
  );
  const [rejecting, setRejecting] = useState(false);
  const [rejectWhy, setRejectWhy] = useState<RejectWhy>({ code: "", note: "" });
  const chosen = card.chosen;
  const isTop = sel.tuple === top.tuple;
  const status = statusFor(chosen.tuple_id, chosen.tuple_id, chosen.status, latest);
  const canApprove = !lock && (isTop || (!!sel.cand && whyOk(why)));

  const approve = () => {
    if (!canApprove) return;
    if (isTop) recordFor(card, "approved", sel, null);
    else recordFor(card, "overridden", sel, whyText(why), whyCode(why, top.tuple, sel.tuple));
  };
  const reject = () => {
    const { code, note } = rejectWhy;
    if (!code) return;
    recordFor(card, "rejected", top, rejectText(code, note), code);
    setRejectWhy({ code: "", note: "" });
    setRejecting(false);
  };
  const overridden = latest?.action === "overridden" ? latest : undefined;
  const overriddenTo = overridden ? (card.candidates ?? []).find((c) => c.tuple_id === overridden.tuple_id) : undefined;

  return (
    <section className="sticky bottom-0 space-y-2.5 border-t border-neutral-200 bg-white/95 px-6 py-4 backdrop-blur md:px-8">
      {overridden && (
        <div className="flex items-center gap-2 rounded-lg bg-accent-50 px-3 py-2 text-xs text-accent-800">
          <span className="min-w-0 flex-1 truncate">
            Overridden to{" "}
            <span className="font-medium">
              {overriddenTo
                ? `${overriddenTo.offer_name} via ${CHANNEL_LABEL[overriddenTo.channel] ?? overriddenTo.channel}`
                : tupleLabel(overridden.tuple_id)}
            </span>
            {overridden.reason ? ` · ${overridden.reason}` : ""}
          </span>
          <button
            type="button"
            onClick={() => removeDecision(overridden.id)}
            className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-accent-700 hover:bg-white hover:text-red-700"
            title="Delete this override; the engine's proposal applies again"
          >
            <Trash2 size={12} aria-hidden /> Delete
          </button>
        </div>
      )}

      {lock ? (
        <p className="flex items-center gap-1.5 text-xs text-neutral-600">
          <Lock size={12} aria-hidden /> Locked by hard rule: {ruleText(lock)}. Pick another option or remove the rule.
        </p>
      ) : rejecting ? (
        <RejectBar why={rejectWhy} onChange={setRejectWhy} onReject={reject} onCancel={() => setRejecting(false)} />
      ) : (
        <div className="flex flex-wrap items-center justify-end gap-3">
          {latest && !overridden ? (
            <span className="mr-auto">
              <StatusChip status={status.status} label={status.label} />
            </span>
          ) : !isTop && !canApprove ? (
            <span className="mr-auto text-xs text-neutral-500">Pick a reason under your choice to approve it.</span>
          ) : null}
          {isTop && (
            <button
              type="button"
              onClick={() => setRejecting(true)}
              className={`${btn} bg-white text-red-700 ring-1 ring-inset ring-neutral-300 hover:bg-red-50 focus-visible:ring-red-300`}
            >
              Reject…
            </button>
          )}
          <button
            type="button"
            onClick={approve}
            disabled={!canApprove}
            className={`${btn} bg-accent-600 text-white hover:bg-accent-700 focus-visible:ring-accent-400`}
          >
            <Check size={16} strokeWidth={2.5} className="mr-1.5" aria-hidden />
            Approve
          </button>
        </div>
      )}
    </section>
  );
}

export default function NbaPanel({ card }: { card: CustomerCard }) {
  const allRules = useHardRules();
  const [showBlocked, setShowBlocked] = useState(false);
  const subject = { customer_id: card.customer_id, archetype: card.triage.archetype.id };
  const rules = rulesFor(allRules, subject);
  const today = (card.meta?.eval_time ?? new Date().toISOString()).slice(0, 10);
  const chosen = card.chosen;
  const byTuple = new Map((card.candidates ?? []).map((c) => [c.tuple_id, c]));
  const isNoAction = chosen.tuple_id === "NO_ACTION";
  const options: Option[] = [
    ...(isNoAction ? [] : [{ tuple: chosen.tuple_id, cand: byTuple.get(chosen.tuple_id) }]),
    ...(card.alternatives ?? []).map((a) => ({ tuple: a.tuple_id, cand: byTuple.get(a.tuple_id), alt: a })),
  ];
  const top = isNoAction ? undefined : options[0];
  const [selected, setSelected] = useState<string | null>(top?.tuple ?? null);
  const [why, setWhy] = useState<Why>({ preset: "", note: "" });
  const choose = (t: string) => {
    if (t !== selected) setWhy({ preset: "", note: "" });
    setSelected(t);
  };
  const sel = options.find((o) => o.tuple === selected);
  const maxDelta = Math.max(1, ...options.map((o) => Math.abs(o.cand?.valuation?.delta_clv ?? o.alt?.delta_clv ?? 0)));
  const blocked = card.blocked ?? [];
  const lockOf = (o: Option) => violation(allRules, subject, { offer: o.cand?.offer_id ?? o.tuple.split("|")[0], channel: channelOf(o) }, today);

  return (
    <div className="flex min-h-0 flex-col md:overflow-y-auto">
      <div className="flex-1 space-y-8 p-6 md:p-8">
        <div className="pr-8">
          <HardRules card={card} rules={rules} />
        </div>

        <section className="space-y-3">
          <div className="flex items-baseline gap-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Next best actions</h3>
            <span className="text-xs text-neutral-400">best first · click one to choose</span>
          </div>

          {chosen.service_mode && (
            <p className="flex items-center gap-2 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-2.5 text-sm text-neutral-800">
              <LifeBuoy size={15} className="shrink-0 text-neutral-500" aria-hidden />
              Resolve the service issue first.
            </p>
          )}
          {isNoAction && (
            <div className="flex items-start gap-3 rounded-xl bg-neutral-50 p-4 text-sm ring-1 ring-neutral-200">
              <CircleSlash size={18} className="mt-0.5 shrink-0 text-neutral-400" aria-hidden />
              <div className="space-y-1">
                <div className="font-medium">Do not contact now</div>
                <p className="text-neutral-600">
                  <WithSignalRefs text={chosen.reason_line} activeSignal={null} />
                </p>
              </div>
            </div>
          )}

          {options.length > 0 && (
            <ol className="space-y-2">
              {options.map((o, i) => (
                <OptionItem
                  key={o.tuple}
                  card={card}
                  o={o}
                  rank={i + 1}
                  top={!isNoAction && i === 0}
                  maxDelta={maxDelta}
                  lock={lockOf(o)}
                  selected={o.tuple === selected}
                  onSelect={() => choose(o.tuple)}
                  note={o.tuple === selected && i > 0 && !lockOf(o) ? <OverrideNote why={why} onChange={setWhy} /> : undefined}
                />
              ))}
            </ol>
          )}

          {blocked.length > 0 && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setShowBlocked((b) => !b)}
                aria-expanded={showBlocked}
                className="inline-flex items-center gap-0.5 text-xs font-medium text-neutral-500 hover:text-neutral-800"
              >
                {blocked.length} more options blocked by engine rules
                <ChevronDown size={14} className={`transition-transform duration-200 ${showBlocked ? "rotate-180" : ""}`} aria-hidden />
              </button>
              {showBlocked && (
                <ul className="space-y-1.5 rounded-xl bg-white p-4 text-xs text-neutral-600 ring-1 ring-neutral-200">
                  {blocked.map((b, i) => (
                    <li key={`${b.offer_id}-${b.channel ?? ""}-${i}`} className="flex flex-wrap items-center gap-2">
                      <RuleChip rule={b.rule_id} />
                      <span>{b.reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>

      {top && sel && <DecisionBox card={card} top={top} sel={sel} lock={lockOf(sel)} why={why} />}
    </div>
  );
}
