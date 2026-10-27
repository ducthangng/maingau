import { useState, type ReactNode } from "react";
import { ChevronDown, LayoutPanelTop, LifeBuoy, Megaphone, Newspaper, type LucideIcon } from "lucide-react";
import type { CustomerCard } from "../../types/contracts";
import type { TypedTrends } from "../../types/trends";
import { pct } from "../../lib/format";
import { Label } from "./parts";

// Recap of how this customer and MAINGAU have interacted: our contacts and how they ended, service,
// newsletter and portal. One line each with one small mark; all numbers come from the card JSON.

const OUTCOME_DOT: Record<string, string> = {
  converted: "bg-accent-600",
  clicked: "bg-accent-600",
  viewed: "bg-neutral-400",
  ignored: "bg-red-400",
  dismissed: "bg-red-400",
};

function Line({ icon: Icon, title, children, viz }: { icon: LucideIcon; title: string; children: ReactNode; viz?: ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white text-neutral-500 ring-1 ring-neutral-200">
        <Icon size={14} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-neutral-800">{title}</span>
          {viz}
        </div>
        <p className="mt-0.5 text-xs leading-relaxed text-neutral-500">{children}</p>
      </div>
    </li>
  );
}

export default function Interaction({ card }: { card: CustomerCard }) {
  const [open, setOpen] = useState(false);
  const f = card.profile.fatigue;
  const tr = (card.profile.trends ?? {}) as Partial<TypedTrends>;
  const sv = tr.service;
  const nl = tr.newsletter;
  const portal = tr.portal;

  // Our past campaign contacts, oldest → newest, with how each ended.
  const campaigns = (card.timeline ?? [])
    .filter((t) => t.kind === "marketing" && !t.future)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((t) => ({ date: t.date, title: t.title, outcome: (t.detail ?? "").split(" · ").pop() ?? "" }));
  const positive = campaigns.filter((c) => c.outcome === "clicked" || c.outcome === "converted").length;
  const negative = campaigns.filter((c) => c.outcome === "ignored" || c.outcome === "dismissed").length;
  const tickets12m = sv?.quarters?.reduce((a, q) => a + q.tickets, 0) ?? 0;
  const sessions = portal?.months ?? [];
  const maxS = Math.max(1, ...sessions.map((m) => m.sessions));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Label>Interaction with us</Label>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="inline-flex shrink-0 items-center gap-0.5 text-xs font-medium text-accent-600 hover:text-accent-700"
        >
          {open ? "View less" : "View more"}
          <ChevronDown size={14} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>
      {open && (
        <ul className="space-y-3.5">
          <Line
            icon={Megaphone}
            title="Our campaigns"
            viz={
              campaigns.length > 0 && (
                <span
                  className="flex gap-[3px]"
                  role="img"
                  aria-label={`${positive} responded, ${negative} ignored or dismissed of ${campaigns.length}`}
                >
                  {campaigns.slice(-12).map((c, i) => (
                    <span
                      key={i}
                      title={`${c.date} · ${c.title} · ${c.outcome}`}
                      className={`size-2 rounded-full ${OUTCOME_DOT[c.outcome] ?? "bg-neutral-300"}`}
                    />
                  ))}
                </span>
              )
            }
          >
            {campaigns.length === 0
              ? "No campaign contact on record."
              : `${campaigns.length} contacts: ${positive} responded, ${negative} ignored or dismissed. ${f?.contacts_90d ?? 0} in the last 90 days${
                  typeof f?.response_rate === "number" ? `, ${pct(f.response_rate, 0)} response rate` : ""
                }.`}
          </Line>

          <Line icon={LifeBuoy} title="Service">
            {sv
              ? `${tickets12m} ticket${tickets12m === 1 ? "" : "s"} in 12 months, ${sv.open} open${
                  sv.latest_csat ? `. Last satisfaction ${sv.latest_csat.v}/5 on ${sv.latest_csat.date}` : ""
                }${sv.goodwill_eur ? `. Goodwill €${sv.goodwill_eur}` : ""}.`
              : "No service data."}
          </Line>

          <Line icon={Newspaper} title="Newsletter">
            {nl
              ? nl.unsubscribed
                ? "Unsubscribed."
                : `${nl.delivered} delivered, ${nl.real_opens} opened, ${nl.clicks} clicked${
                    nl.clicks
                      ? ` (${Object.keys(nl.clicks_by_target)
                          .map((k) => k.replace(/_/g, " "))
                          .join(", ")})`
                      : ""
                  }.`
              : "Not subscribed."}
          </Line>

          <Line
            icon={LayoutPanelTop}
            title="Portal visits"
            viz={
              sessions.length > 0 && (
                <span className="flex h-5 items-end gap-1" role="img" aria-label={sessions.map((m) => `${m.month}: ${m.sessions}`).join(", ")}>
                  {sessions.map((m) => (
                    <span
                      key={m.month}
                      title={`${m.month}: ${m.sessions} sessions`}
                      className="w-2 rounded-sm bg-accent-500"
                      style={{ height: `${Math.max(12, (m.sessions / maxS) * 100)}%` }}
                    />
                  ))}
                </span>
              )
            }
          >
            {sessions.length
              ? `${sessions.reduce((a, m) => a + m.sessions, 0)} sessions in ${sessions.length} months; looked at offers ${sessions.reduce((a, m) => a + m.offers, 0)} times.`
              : "No portal activity."}
          </Line>
        </ul>
      )}
    </div>
  );
}
