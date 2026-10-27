import { useMemo, useState } from "react";
import type { CustomerCard, TimelineItem } from "../../types/contracts";
import { channelName, dateLabel, humanize, offerName } from "./plain";

// Tab 2: Customer journey (prompts/ui-customer360.md §3.3): what happened and how the customer
// reacted, newest first. No CLV marks, no marketing warnings.

type Group = "proposal" | "ticket" | "order" | "contract" | "consent" | "event";

const GROUP_LABEL: Record<Group, string> = {
  proposal: "Past proposals",
  ticket: "Service tickets",
  order: "Shop orders",
  contract: "Contracts",
  consent: "Consent changes",
  event: "Other events",
};

function groupOf(t: TimelineItem): Group {
  switch (t.kind) {
    case "marketing":
      return "proposal";
    case "service":
      return "ticket";
    case "order":
      return "order";
    case "contract":
    case "milestone":
      return "contract";
    case "consent":
      return "consent";
    default:
      return "event";
  }
}

/** Plain title and detail: offer names instead of IDs, no legacy rule codes. */
function describe(t: TimelineItem): { title: string; detail: string } {
  if (t.kind === "marketing") {
    const m = /^Offer (\S+) via (\S+)/.exec(t.title);
    const parts = (t.detail ?? "").split(" · ").filter((p) => p && !/^R-/.test(p));
    const reaction = parts.map((p) => (p === "converted" ? "bought within 14 days" : p)).join(" · ");
    return {
      title: m ? `Proposal: ${offerName(m[1])} by ${channelName(m[2]).toLowerCase()}` : t.title,
      detail: reaction ? `Customer reaction: ${reaction}` : "",
    };
  }
  if (t.kind === "consent") {
    return { title: t.title.replace(/^Consent (\S+):/, (_, c: string) => `Consent ${c.replace(/_/g, " ")}:`), detail: t.detail ? `via ${t.detail.replace(/_/g, " ")}` : "" };
  }
  if (t.kind === "service") {
    const extra = (t.flags ?? []).includes("repeat contact") ? " · repeat contact" : "";
    return { title: humanize(t.title), detail: `${t.detail ?? ""}${extra}` };
  }
  if (t.kind === "order") return { title: `Order: ${t.title}`, detail: humanize(t.detail) };
  return { title: t.title, detail: t.detail ?? "" };
}

export default function JourneyTab({ card }: { card: CustomerCard }) {
  const items = card.timeline ?? [];
  const counts = useMemo(() => {
    const c = new Map<Group, number>();
    for (const t of items) c.set(groupOf(t), (c.get(groupOf(t)) ?? 0) + 1);
    return c;
  }, [items]);
  const [filter, setFilter] = useState<Group | null>(null);
  const shown = filter ? items.filter((t) => groupOf(t) === filter) : items;

  const chip = (active: boolean) =>
    `rounded-full px-3 py-1 text-sm transition-colors duration-150 ${
      active ? "bg-neutral-900 text-white" : "bg-white text-neutral-600 ring-1 ring-neutral-200 hover:bg-neutral-50"
    }`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter events">
        <button type="button" className={chip(filter === null)} onClick={() => setFilter(null)}>
          All {items.length}
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
          {shown.map((t) => {
            const d = describe(t);
            return (
              <li key={t.id} className="relative rounded-lg px-3 py-2 hover:bg-white">
                <span className="absolute -left-[25px] top-3.5 size-2 rounded-full bg-neutral-300 ring-4 ring-neutral-50" aria-hidden />
                <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                  <p className="text-sm font-medium text-neutral-900">{d.title}</p>
                  <p className="text-xs tabular-nums text-neutral-500">
                    {t.future ? "upcoming · " : ""}
                    {dateLabel(t.date)}
                  </p>
                </div>
                {d.detail && <p className="text-sm text-neutral-600">{d.detail}</p>}
                <p className="text-[11px] text-neutral-400">{GROUP_LABEL[groupOf(t)]}</p>
              </li>
            );
          })}
        </ol>
      )}

      <p className="text-xs text-neutral-500">
        Newsletter deliveries, suggestions by other agents, charging days and portal visits are not in the journey yet; the portal data does
        not name the pages a customer used.
      </p>
    </div>
  );
}
