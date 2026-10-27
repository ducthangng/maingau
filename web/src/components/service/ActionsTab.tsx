import { useState } from "react";
import type { Candidate, CustomerCard } from "../../types/contracts";
import { pct, signedEur } from "../../lib/format";
import {
  DISMISS_LABEL,
  recordReaction,
  useServiceFeedback,
  type ContactChannel,
  type DismissReason,
  type Reaction,
} from "../../lib/serviceFeedback";
import { channelLabel, toneLabel } from "../nba/ui";
import { dateLabel, noOfferReason, notRecommended, openTickets, reasonOf, sortedActions, ticketId } from "./plain";

// Tab 3: Next best actions (prompts/ui-customer360.md §3.4). Same engine output as the marketer's
// page; the only re-ordering is "service first while a ticket is open". The agent records the
// customer's reaction instead of approving; nothing is sent to the customer.

const timeFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function ActionRow({ card, c, n, channel, ticket }: { card: CustomerCard; c: Candidate; n: number; channel: ContactChannel; ticket: string | null }) {
  const all = useServiceFeedback();
  const mine = all.filter((f) => f.customer_id === card.customer_id && f.suggested_offer_id === c.offer_id);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState<DismissReason | "">("");

  const save = (reaction: Reaction, why: DismissReason | null = null) => {
    recordReaction({ customer_id: card.customer_id, offer_id: c.offer_id, reaction, reason: why, channel, ticket_id: ticket });
    setDeclining(false);
    setReason("");
  };

  const btn = "rounded-lg px-3 py-1.5 text-sm ring-1 ring-inset ring-neutral-200 transition-colors duration-150 hover:bg-neutral-50";

  return (
    <li className="rounded-xl border border-neutral-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-neutral-500">#{n}</p>
          <p className="font-medium text-neutral-900">{c.offer_name}</p>
          <p className="text-sm text-neutral-600">
            {channelLabel(c.channel)} · {toneLabel(c.tone)}
            {c.deferred_until && <> · possible from {dateLabel(c.deferred_until)}</>}
          </p>
        </div>
        <div className="text-right text-sm">
          <p className="font-semibold tabular-nums text-neutral-900">{c.valuation ? signedEur(c.valuation.delta_clv) : "—"}</p>
          <p className="text-neutral-600">{c.valuation ? `${pct(c.valuation.p_accept)} likely to agree` : ""}</p>
        </div>
      </div>
      <p className="mt-2 text-sm text-neutral-700">{reasonOf(c)}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className={btn} onClick={() => save("mentioned")}>
          Mentioned
        </button>
        <button type="button" className={btn} onClick={() => save("interested")}>
          Interested
        </button>
        <button type="button" className={btn} aria-expanded={declining} onClick={() => setDeclining(!declining)}>
          Declined…
        </button>
        {declining && (
          <span className="flex flex-wrap items-center gap-2">
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as DismissReason | "")}
              aria-label="Reason (optional)"
              className="rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-sm"
            >
              <option value="">Reason (optional)</option>
              {(Object.keys(DISMISS_LABEL) as DismissReason[]).map((r) => (
                <option key={r} value={r}>
                  {DISMISS_LABEL[r]}
                </option>
              ))}
            </select>
            <button type="button" className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white hover:bg-neutral-700" onClick={() => save("declined", reason || null)}>
              Save
            </button>
          </span>
        )}
      </div>

      {mine.length > 0 && (
        <ul className="mt-3 space-y-0.5 border-t border-neutral-100 pt-2 text-xs text-neutral-600">
          {mine.map((f) => (
            <li key={f.feedback_id}>
              {f.agent_action === "dismissed" ? "Declined" : f.customer_reaction === "interested" ? "Interested" : "Mentioned"}
              {f.dismiss_reason ? ` · ${DISMISS_LABEL[f.dismiss_reason]}` : ""} · {f.channel} · {timeFmt.format(new Date(f.shown_at))}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function ActionsTab({ card }: { card: CustomerCard }) {
  const [channel, setChannel] = useState<ContactChannel>("phone");
  const actions = sortedActions(card);
  const blocked = notRecommended(card);
  const ticket = ticketId(openTickets(card)[0]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Suggested actions ({actions.length})</h3>
          <label className="flex items-center gap-2 text-sm text-neutral-600">
            Talking via
            <select value={channel} onChange={(e) => setChannel(e.target.value as ContactChannel)} className="rounded-lg border border-neutral-200 bg-white px-2 py-1 text-sm">
              <option value="phone">Phone</option>
              <option value="chat">Chat</option>
            </select>
          </label>
        </div>
        {actions.length === 0 ? (
          <p className="rounded-xl border border-neutral-200 bg-white p-6 text-sm text-neutral-600">
            No offer right now: {noOfferReason(card)}.
          </p>
        ) : (
          <ol className="space-y-3">
            {actions.map((c, i) => (
              <ActionRow key={c.tuple_id} card={card} c={c} n={i + 1} channel={channel} ticket={ticket} />
            ))}
          </ol>
        )}
        <p className="text-xs text-neutral-500">
          Reactions are recorded for the feedback loop (a decline pauses that offer for 90 days); nothing is sent to the customer.
        </p>
      </section>

      <section>
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Not recommended</h3>
        {blocked.length === 0 ? (
          <p className="text-sm text-neutral-500">Nothing ruled out.</p>
        ) : (
          <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white">
            {blocked.map((b) => (
              <li key={`${b.subject}|${b.text}`} className="px-4 py-2.5 text-sm">
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
