import { useState } from "react";
import { ChevronDown, LifeBuoy, Lock } from "lucide-react";
import type { Candidate, CustomerCard } from "../../types/contracts";
import { useHardRules, violation, type HardRule } from "../../lib/hardRules";
import { pct, signedEur } from "../../lib/format";
import { DecisionBox, OverrideNote, ruleText, scopeText, type Option, type Why } from "../customer/NbaPanel";
import { channelLabel, toneLabel } from "../nba/ui";
import { ValueBar } from "../viz";
import { dateLabel, noOfferReason, noPayment, notRecommended, reasonOf } from "./plain";

// Next best actions card (prompts/ui-customer360.md §3.4). The same options, ranking and decision
// box as the orchestration pop-up (NbaPanel): the engine's #1 first, click one to choose, a reason
// under any other choice, then Approve or Reject. Decisions go to the same decision log; nothing
// is sent to the customer. Only the wording stays plain: no rule codes or payment fields.

/** One option, in the look of the orchestration pop-up: rank, headline, why, value bar; click to choose, ⌄ for details. */
function OptionRow({
  c,
  n,
  maxDelta,
  lock,
  selected,
  onSelect,
  note,
}: {
  c: Candidate;
  n: number;
  maxDelta: number;
  lock: HardRule | undefined;
  selected: boolean;
  onSelect: () => void;
  /** "Why this one?" under the row when it is chosen instead of #1. */
  note?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const top = n === 1;
  const v = c.valuation;
  const lines = [...(c.why ?? []), ...(c.notes ?? [])].map((l) => noPayment(l));
  // Full text of the two lines, kept in `title` because a long one is clamped to two lines.
  const headline = `${c.offer_name} via ${channelLabel(c.channel)} · ${toneLabel(c.tone)}`;
  const reason = lock
    ? `Locked: ${ruleText(lock)} (${scopeText(lock)})`
    : `${reasonOf(c)}${c.deferred_until ? ` · possible from ${dateLabel(c.deferred_until)}` : ""}`;

  return (
    // Static edge is a 1px border (never clipped); the selected state is an inset ring, so nothing is
    // drawn outside the row. The border turns transparent when selected so the ring is the one edge.
    <li
      className={`rounded-xl border transition-[box-shadow,background-color,border-color] duration-150 ${
        selected
          ? top
            ? "border-transparent bg-accent-50/60 ring-2 ring-inset ring-accent-600"
            : "border-transparent bg-accent-50/60 ring-2 ring-inset ring-accent-500"
          : "border-neutral-200 bg-white hover:bg-neutral-50 hover:shadow-sm"
      } ${lock ? "opacity-60" : ""}`}
    >
      <div className="flex items-center gap-3 px-3.5 py-2.5">
        {/* Inset focus outline (the row sits in the column's scroll box); the padding and matching
            negative margin keep the outline off the content without moving it. `!` because the global
            :focus-visible rule in index.css is unlayered and would otherwise win over the utility. */}
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={selected}
          className="-mx-1.5 -my-1 flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg px-1.5 py-1 text-left focus-visible:-outline-offset-2!"
        >
          <span
            className={`grid size-6 shrink-0 place-items-center rounded-md text-xs font-semibold tabular-nums ${
              top ? "bg-gold-400 text-neutral-900" : selected ? "bg-accent-600 text-white" : "bg-neutral-100 text-neutral-600"
            }`}
          >
            {n}
          </span>
          <span className="min-w-0 flex-1">
            <span className="line-clamp-2 break-words text-sm font-medium text-neutral-900" title={headline}>
              {c.offer_name} via {channelLabel(c.channel)} <span className="font-normal text-neutral-400">· {toneLabel(c.tone)}</span>
            </span>
            <span className="flex items-start gap-1 text-xs text-neutral-500">
              {lock && <Lock size={11} className="mt-0.5 shrink-0" aria-hidden />}
              <span className="line-clamp-2 min-w-0 break-words" title={reason}>
                {lock ? `Locked: ${ruleText(lock)} (${scopeText(lock)})` : reasonOf(c)}
                {!lock && c.deferred_until && <> · possible from {dateLabel(c.deferred_until)}</>}
              </span>
            </span>
          </span>
          <span className="hidden w-20 shrink-0 @sm:block" title="Expected value, relative to the other options">
            <ValueBar value={v?.delta_clv ?? 0} max={maxDelta} tone={top || selected ? "accent" : "muted"} />
          </span>
        </button>
        <button
          type="button"
          onClick={() => setOpen((x) => !x)}
          aria-expanded={open}
          aria-label={open ? "Hide details" : "Show details"}
          className={`grid size-6 shrink-0 place-items-center rounded-md transition-colors duration-150 focus-visible:-outline-offset-2! ${open ? "bg-neutral-900 text-white" : "text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800"}`}
        >
          <ChevronDown size={14} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>
      {note}
      {open && (
        <div className="space-y-2 border-t border-neutral-100 px-3.5 py-2.5 pl-12 text-xs leading-relaxed text-neutral-600">
          <p>
            Expected value <span className="font-medium text-neutral-900">{v ? signedEur(v.delta_clv) : "—"}</span>
            {v && (
              <>
                {" "}
                · chance <span className="font-medium text-neutral-900">{pct(v.p_accept)}</span> to agree
              </>
            )}
          </p>
          {lines.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-4">
              {lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

type Ranked = Option & { cand: Candidate };

export default function ActionsTab({ card }: { card: CustomerCard }) {
  const allRules = useHardRules();
  const blocked = notRecommended(card);
  const chosen = card.chosen;
  const isNoAction = chosen.tuple_id === "NO_ACTION";
  const byTuple = new Map((card.candidates ?? []).map((c) => [c.tuple_id, c]));
  // The orchestration ranking: the engine's chosen tuple first, then its alternatives.
  const ranked: Option[] = [
    ...(isNoAction ? [] : [{ tuple: chosen.tuple_id, cand: byTuple.get(chosen.tuple_id) }]),
    ...(card.alternatives ?? []).map((a) => ({ tuple: a.tuple_id, cand: byTuple.get(a.tuple_id), alt: a })),
  ];
  const options = ranked.filter((o): o is Ranked => !!o.cand);
  const top = options[0];
  const [selected, setSelected] = useState<string | null>(top?.tuple ?? null);
  const [why, setWhy] = useState<Why>({ preset: "", note: "" });
  const choose = (t: string) => {
    if (t !== selected) setWhy({ preset: "", note: "" });
    setSelected(t);
  };
  const sel = options.find((o) => o.tuple === selected);
  const maxDelta = Math.max(1, ...options.map((o) => Math.abs(o.cand.valuation?.delta_clv ?? 0)));
  const subject = { customer_id: card.customer_id, archetype: card.triage.archetype.id };
  const today = (card.meta?.eval_time ?? new Date().toISOString()).slice(0, 10);
  const lockOf = (o: Ranked) => violation(allRules, subject, { offer: o.cand.offer_id, channel: o.cand.channel }, today);

  return (
    <div className="grid gap-6">
      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Suggested actions ({options.length})</h3>
          <span className="text-xs text-neutral-400">best first · click one to choose</span>
        </div>
        {chosen.service_mode && (
          // A border (never clipped) and the service icon; no warning colour (prompts/ui-colors.md).
          <p className="flex items-start gap-2 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-2.5 text-sm text-neutral-800">
            <LifeBuoy size={15} className="mt-0.5 shrink-0 text-neutral-500" aria-hidden />
            <span className="min-w-0 break-words">Resolve the service issue first.</span>
          </p>
        )}
        {options.length === 0 ? (
          <p className="rounded-xl border border-neutral-200 bg-white p-6 text-sm break-words text-neutral-600">
            No offer right now: {noOfferReason(card)}.
          </p>
        ) : (
          <ol className="space-y-2">
            {options.map((o, i) => (
              <OptionRow
                key={o.tuple}
                c={o.cand}
                n={i + 1}
                maxDelta={maxDelta}
                lock={lockOf(o)}
                selected={o.tuple === selected}
                onSelect={() => choose(o.tuple)}
                note={o.tuple === selected && i > 0 && !lockOf(o) ? <OverrideNote why={why} onChange={setWhy} /> : undefined}
              />
            ))}
          </ol>
        )}
        {top && sel && (
          // A normal list card around the in-card decision box (not the pop-up's sticky footer).
          <div className="rounded-xl border border-neutral-200 bg-white">
            <DecisionBox card={card} top={top} sel={sel} lock={lockOf(sel)} why={why} variant="inline" />
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Not recommended</h3>
        {blocked.length === 0 ? (
          <p className="text-sm text-neutral-500">Nothing ruled out.</p>
        ) : (
          <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white">
            {blocked.map((b) => (
              <li key={`${b.subject}|${b.text}`} className="px-4 py-2.5 text-sm break-words">
                <span className="font-medium text-neutral-900">{b.subject}</span>
                <span className="block text-neutral-600">{b.text}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
