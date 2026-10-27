import { Check, ShieldAlert, ShieldCheck, X } from "lucide-react";
import type { ConsentItem, CustomerCard } from "../../types/contracts";
import { CHANNEL_LABEL } from "../../lib/format";
import { sourceTitle } from "../Source";
import { Section } from "../Chips";
import { REF_CLS, humanize, type Sources } from "./shared";

const CONSENT_LABEL: Record<ConsentItem["type"], string> = {
  newsletter_email: "Newsletter",
  marketing_email: "Marketing e-mail",
  marketing_phone: "Phone",
  marketing_sms: "SMS",
  portal_app_personalisation: "Portal & app",
  profiling_analytics: "Profiling",
};

const LIGHT: Record<ConsentItem["effective_status"], string> = {
  granted: "bg-accent-600",
  withdrawn: "bg-red-500",
  not_given: "bg-neutral-300",
};

const STATUS_TEXT: Record<ConsentItem["effective_status"], string> = {
  granted: "granted",
  withdrawn: "withdrawn",
  not_given: "not given",
};

export const EXCLUSION_LABEL: Record<string, string> = {
  "EXCL-DUNNING": "Dunning",
  "EXCL-CANCELLATION": "Cancellation pending",
  "EXCL-OPEN-TICKET": "Open complaint ticket",
  "EXCL-AUTOSTROM-CANCELLED": "Autostrom cancelled",
};

function consentTitle(c: ConsentItem, sources: Sources) {
  return [
    sourceTitle("consent_status.status", c.updated_at, sources),
    c.source ? `recorded via: ${humanize(c.source)}` : null,
    c.doi === true ? "double opt-in: yes" : c.doi === false ? "double opt-in: no" : null,
  ]
    .filter(Boolean)
    .join("\n");
}

/** A5: consent, exclusions and channels as traffic lights. Always visible, never collapsed. */
export function ConsentPanel({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const consent = card.profile.consent ?? [];
  const exclusions = card.profile.exclusions ?? [];
  const active = exclusions.filter((e) => e.active);
  const channels = card.profile.channels ?? [];

  return (
    <Section
      title="Consent & exclusions"
      aside={
        <span className="flex items-center gap-2.5 text-[11px] text-neutral-500">
          <Legend color="bg-accent-600" label="granted" />
          <Legend color="bg-red-500" label="withdrawn" />
          <Legend color="bg-neutral-300" label="not given" />
        </span>
      }
    >
      <ul className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        {consent.map((c) => {
          const overridden = c.status !== c.effective_status || !!c.override_reason;
          return (
            <li
              key={c.type}
              data-ui-ref={`consent:${c.type}`}
              title={consentTitle(c, s)}
              className={`${REF_CLS} flex cursor-help items-start gap-2 border border-neutral-200 bg-white px-2.5 py-1.5`}
            >
              <span className={`mt-1.5 size-2.5 shrink-0 rounded-full ${LIGHT[c.effective_status]}`} aria-hidden />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{CONSENT_LABEL[c.type] ?? c.type}</div>
                <div className="text-xs text-neutral-500">
                  {STATUS_TEXT[c.effective_status]}
                  {c.updated_at ? ` · ${c.updated_at}` : ""}
                </div>
                {overridden && (
                  <div className="mt-0.5 text-[11px] leading-snug text-neutral-700">
                    record says {STATUS_TEXT[c.status]}
                    {c.override_reason ? ` — ${c.override_reason}` : ""}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-2.5">
        {active.length > 0 ? (
          <ul className="space-y-1.5">
            {active.map((e) => (
              <li
                key={e.rule_id}
                data-ui-ref={`exclusion:${e.rule_id}`}
                title={sourceTitle(e.src, null, s)}
                className={`${REF_CLS} flex cursor-help items-start gap-2 bg-red-50 px-2.5 py-1.5 text-sm text-red-800 ring-1 ring-inset ring-red-200`}
              >
                <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  <span className="font-medium">{EXCLUSION_LABEL[e.rule_id] ?? e.rule_id}</span>
                  {e.detail ? <span className="text-red-700"> — {e.detail}</span> : null}
                  <span className="ml-1.5 font-mono text-[10px] text-red-500">{e.rule_id}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p
            className="flex items-center gap-1.5 text-sm text-neutral-500"
            title={`Checked: ${exclusions.map((e) => `${e.rule_id} (${e.src})`).join(", ") || "none"}`}
          >
            <ShieldCheck className="size-4 text-accent-600" aria-hidden />
            No active exclusion
          </p>
        )}
      </div>

      {channels.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="mr-0.5 text-xs text-neutral-500">Channels</span>
          {channels.map((c) => (
            <span
              key={c.channel}
              title={c.reason}
              className={`inline-flex cursor-help items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1 ring-inset ${
                c.allowed ? "bg-accent-50 text-accent-800 ring-accent-100" : "bg-neutral-50 text-neutral-400 ring-neutral-200"
              }`}
            >
              {c.allowed ? <Check className="size-3" aria-label="allowed" /> : <X className="size-3" aria-label="not allowed" />}
              {CHANNEL_LABEL[c.channel] ?? c.channel}
            </span>
          ))}
        </div>
      )}
    </Section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`size-2 rounded-full ${color}`} aria-hidden />
      {label}
    </span>
  );
}
