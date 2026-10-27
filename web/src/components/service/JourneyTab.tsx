import { useMemo, useState } from "react";
import { useLoad } from "../../lib/data";
import { loadJourney } from "../../lib/journey";
import type { CustomerCard, Journey, JourneyEvent, TimelineItem } from "../../types/contracts";
import { channelName, dateLabel, humanize, offerName } from "./plain";

// Tab 2: Customer journey (prompts/ui-customer360.md §3.3): what happened and how the customer
// reacted, newest first. Reads the Journey document (docs/api.md §3.7); if it cannot be loaded,
// the card timeline is shown instead. No CLV marks, no marketing warnings.

type Group = "newsletter" | "proposal" | "agent_suggestion" | "ticket" | "order" | "charging" | "portal" | "contract" | "consent";

const GROUP_LABEL: Record<Group, string> = {
  newsletter: "Newsletters",
  proposal: "Past proposals",
  agent_suggestion: "Agent suggestions",
  ticket: "Tickets",
  order: "Orders",
  charging: "Charging",
  portal: "Portal",
  contract: "Contracts",
  consent: "Consent",
};

const groupOf = (e: JourneyEvent): Group => (e.type === "milestone" ? "contract" : e.type);

/** The card timeline in the journey shape, used only when the journey cannot be loaded. */
export function fromTimeline(t: TimelineItem): JourneyEvent {
  const base = { id: t.id, date: t.date, future: t.future, flags: t.flags };
  if (t.kind === "marketing") {
    const m = /^Offer (\S+) via (\S+)/.exec(t.title);
    const parts = (t.detail ?? "").split(" · ").filter((p) => p && !/^R-/.test(p));
    return {
      ...base,
      type: "proposal",
      title: m ? `Offer ${offerName(m[1])} via ${channelName(m[2]).toLowerCase()}` : t.title,
      reaction: parts.map((p) => (p === "converted" ? "bought within 14 days" : p)).join(" · ") || null,
    };
  }
  if (t.kind === "consent") {
    return { ...base, type: "consent", title: t.title.replace(/^Consent (\S+):/, (_, c: string) => `Consent ${c.replace(/_/g, " ")}:`), detail: t.detail?.replace(/_/g, " ") };
  }
  if (t.kind === "service") return { ...base, type: "ticket", title: humanize(t.title), detail: t.detail };
  if (t.kind === "order") return { ...base, type: "order", title: t.title, detail: humanize(t.detail) };
  return { ...base, type: t.kind === "milestone" ? "milestone" : "contract", title: t.title, detail: t.detail };
}

export function JourneyList({ events }: { events: JourneyEvent[] }) {
  const counts = useMemo(() => {
    const c = new Map<Group, number>();
    for (const e of events) c.set(groupOf(e), (c.get(groupOf(e)) ?? 0) + 1);
    return c;
  }, [events]);
  const [filter, setFilter] = useState<Group | null>(null);
  const shown = filter ? events.filter((e) => groupOf(e) === filter) : events;

  const chip = (active: boolean) =>
    `rounded-full px-3 py-1 text-sm transition-colors duration-150 ${
      active ? "bg-neutral-900 text-white" : "bg-white text-neutral-600 ring-1 ring-neutral-200 hover:bg-neutral-50"
    }`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter events">
        <button type="button" className={chip(filter === null)} onClick={() => setFilter(null)}>
          All {events.length}
        </button>
        {(Object.keys(GROUP_LABEL) as Group[])
          .filter((g) => counts.get(g))
          .map((g) => (
            <button key={g} type="button" className={chip(filter === g)} onClick={() => setFilter(filter === g ? null : g)}>
              {GROUP_LABEL[g]} {counts.get(g)}
            </button>
          ))}
      </div>

      {shown.length === 0 ? (
        <p className="rounded-xl border border-neutral-200 bg-white p-6 text-center text-sm text-neutral-500">Nothing recorded in the last 12 months.</p>
      ) : (
        <ol className="relative space-y-1 border-l border-neutral-200 pl-5">
          {shown.map((e) => (
            <li key={e.id} className="relative rounded-lg px-3 py-2 hover:bg-white">
              <span className="absolute -left-[25px] top-3.5 size-2 rounded-full bg-neutral-300 ring-4 ring-neutral-50" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <p className="text-sm font-medium text-neutral-900">{e.title}</p>
                <p className="text-xs tabular-nums text-neutral-500">
                  {e.future ? "upcoming · " : ""}
                  {dateLabel(e.date)}
                </p>
              </div>
              {e.detail && <p className="text-sm text-neutral-600">{e.detail}</p>}
              {e.reaction && <p className="text-sm text-neutral-700">Customer reaction: {e.reaction}</p>}
              <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-neutral-400">
                {GROUP_LABEL[groupOf(e)]}
                {(e.flags ?? []).map((f) => (
                  <span key={f} className="rounded bg-neutral-100 px-1.5 py-px text-neutral-600">
                    {f}
                  </span>
                ))}
              </p>
            </li>
          ))}
        </ol>
      )}

      <p className="text-xs text-neutral-500">
        Last 12 months and upcoming contract dates. A newsletter that a mail app only preloaded counts as not opened.
      </p>
    </div>
  );
}

export default function JourneyTab({ card }: { card: CustomerCard }) {
  const journey = useLoad<Journey>(() => loadJourney(card.customer_id), [card.customer_id]);
  if (journey.status === "loading") return <p className="py-8 text-center text-sm text-neutral-500">Loading the journey…</p>;
  if (journey.status === "error") return <JourneyList key={card.customer_id} events={(card.timeline ?? []).map(fromTimeline)} />;
  return <JourneyList key={card.customer_id} events={journey.data.events} />;
}
