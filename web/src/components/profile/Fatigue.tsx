import { TriangleAlert } from "lucide-react";
import type { CustomerCard } from "../../types/contracts";
import { NOT_ENOUGH, isMissing, pct } from "../../lib/format";
import { Sourced, sourceTitle } from "../Source";
import { Section } from "../Chips";
import { humanize, num } from "./shared";

const HISTORY = "nba_action_history";
const CONTACT_CAP_30D = 2; // README §4 / brief §1.4: at most 2 marketing contacts per 30 days (display only)

function str(v: unknown): string | null {
  return typeof v === "string" && v !== "" ? v : null;
}

/** B (fatigue): contact history, response, ignored offers, legacy sends, agent feedback. */
export function FatiguePanel({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const f = card.profile.fatigue;
  if (!f) {
    return (
      <Section title="Contact history & fatigue">
        <p className="text-sm text-neutral-400 italic">{NOT_ENOUGH}</p>
      </Section>
    );
  }
  const ignored = f.repeatedly_ignored ?? [];
  const feedback = f.agent_feedback ?? [];
  const legacy = f.legacy_no_consent_check;
  const c30 = f.contacts_30d;

  return (
    <Section title="Contact history & fatigue">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Cell label="Contacts 30 d">
          <Sourced src={`${HISTORY}.decided_at`} sources={s}>
            {isMissing(c30) ? <Missing /> : <span className={c30 >= CONTACT_CAP_30D ? "text-amber-700" : ""}>{num(c30)}</span>}
          </Sourced>
          <span className="ml-1 text-[11px] font-normal text-neutral-400">cap {CONTACT_CAP_30D}</span>
        </Cell>
        <Cell label="Contacts 90 d">
          <Sourced src={`${HISTORY}.decided_at`} sources={s}>
            {isMissing(f.contacts_90d) ? <Missing /> : num(f.contacts_90d)}
          </Sourced>
        </Cell>
        <Cell label="Response rate">
          <Sourced src={`${HISTORY}.response`} sources={s}>
            {isMissing(f.response_rate) ? <Missing /> : pct(f.response_rate, 0)}
          </Sourced>
        </Cell>
        <Cell label="Legacy sends, no consent check">
          <Sourced src={`${HISTORY}.consent_checked`} sources={s}>
            {isMissing(legacy) ? (
              <Missing />
            ) : (
              <span className={legacy > 0 ? "inline-flex items-center gap-1 text-amber-700" : ""}>
                {legacy > 0 && <TriangleAlert className="size-3.5" aria-label="warning" />}
                {num(legacy)}
              </span>
            )}
          </Sourced>
        </Cell>
      </div>

      {ignored.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-0.5 text-xs text-neutral-500">Ignored repeatedly</span>
          {ignored.map((o) => (
            <span
              key={o}
              title={sourceTitle(`${HISTORY}.response`, null, s)}
              className="cursor-help rounded bg-neutral-100 px-1.5 py-px font-mono text-[11px] text-neutral-700"
            >
              {o}
            </span>
          ))}
        </div>
      )}

      {feedback.length > 0 && (
        <ul className="mt-2 space-y-1">
          {feedback.map((fb, i) => {
            const reason = str(fb.dismiss_reason);
            const reaction = str(fb.customer_reaction);
            const upset = reason === "customer_upset" || reaction === "annoyed";
            return (
              <li
                key={i}
                title={sourceTitle(str(fb.src) ?? "service_nba_feedback", null, s) + (str(fb.ticket_id) ? `\nticket: ${str(fb.ticket_id)}` : "")}
                className={`flex cursor-help flex-wrap items-baseline gap-x-1.5 rounded-md px-2.5 py-1.5 text-xs ${
                  upset ? "bg-red-50 text-red-800" : "bg-neutral-50 text-neutral-700"
                }`}
              >
                <span className="font-medium">Agent feedback</span>
                <span className="tabular-nums text-neutral-500">{str(fb.date) ?? ""}</span>
                <span className="font-mono text-[11px]">{str(fb.offer_id) ?? ""}</span>
                <span>
                  {humanize(str(fb.agent_action) ?? "")}
                  {reason ? ` — ${humanize(reason)}` : ""}
                  {reaction ? ` · customer ${humanize(reaction)}` : ""}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg bg-neutral-50 px-3 py-2">
      <div className="text-[11px] leading-tight text-neutral-500">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums">{children}</div>
    </div>
  );
}

function Missing() {
  return <span className="font-normal text-neutral-400 italic">{NOT_ENOUGH}</span>;
}
