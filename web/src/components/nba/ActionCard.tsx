import type { ReactNode } from "react";
import { AlertTriangle, Check, Clock, X } from "lucide-react";
import type { Candidate, Check as RuleCheck, ChecklistItem, Content, CustomerCard, PathStep } from "../../types/contracts";
import { pct, signedEur } from "../../lib/format";
import { ConfidenceDot, Section } from "../Chips";
import { Sourced } from "../Source";
import { ClvImpact, SuccessEvidence } from "./Valuation";
import { ReasoningPath } from "./ReasoningPath";
import { ACTION_TYPE_LABEL, Missing, Pill, StatusChip, channelLabel, mentionsSignal, sendAtLabel, toneLabel, type Sources, type Status } from "./ui";

// One NBA card (README §4.2 C1–C8): the action, why it fits, CLV impact, success vs failure,
// notes, checklist, German content, reasoning path and the decision buttons.

/** Renders "[S1]" style references as small chips; the active signal gets the accent. */
export function WithSignalRefs({ text, activeSignal }: { text: string; activeSignal: string | null }) {
  const parts = text.split(/(\[S\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(S\d+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const on = m[1] === activeSignal;
        return (
          <span
            key={i}
            className={`mx-0.5 inline-flex rounded px-1 py-px align-baseline font-mono text-[11px] ring-1 ring-inset ${
              on ? "bg-accent-500 text-white ring-accent-500" : "bg-accent-50 text-accent-700 ring-accent-100"
            }`}
          >
            {m[1]}
          </span>
        );
      })}
    </>
  );
}

function tupleParts(tupleId: string) {
  const [offer, channel, tone] = tupleId.split("|");
  return { offer, channel, tone };
}

export function ActionHeader({
  cand,
  tupleId,
  status,
  sendAt,
  showSendAt,
  sources,
  prominent,
}: {
  cand: Candidate | undefined;
  tupleId: string;
  status: { status: Status; label?: string };
  sendAt?: string | null;
  showSendAt: boolean;
  sources: Sources;
  prominent: boolean;
}) {
  const t = tupleParts(tupleId);
  const v = cand?.valuation;
  const send = sendAtLabel(sendAt);
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {cand?.rank ? (
            <span className="rounded-md bg-neutral-900 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-white">#{cand.rank}</span>
          ) : null}
          {cand && <Pill>{ACTION_TYPE_LABEL[cand.action_type]}</Pill>}
          <StatusChip status={status.status} label={status.label} />
        </div>
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className={`${prominent ? "text-lg" : "text-[15px]"} font-semibold tracking-tight text-neutral-900`}>
            {cand?.offer_name ?? t.offer}
          </span>
          <span className="font-mono text-xs text-neutral-500">{cand?.offer_id ?? t.offer}</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-neutral-600">
          <span>{channelLabel(cand?.channel ?? t.channel)}</span>
          <span className="text-neutral-300">·</span>
          <span>{toneLabel(cand?.tone ?? t.tone)}</span>
          {showSendAt && (
            <>
              <span className="text-neutral-300">·</span>
              <span className="inline-flex items-center gap-1">
                <Clock size={14} aria-hidden className="text-neutral-400" />
                {send ? <Sourced src="engine.chosen.send_at" sources={sources}>{send}</Sourced> : <Missing />}
              </span>
            </>
          )}
        </div>
      </div>
      <div className="text-right">
        <div className={`${prominent ? "text-2xl" : "text-lg"} font-semibold tabular-nums tracking-tight text-neutral-900`}>
          {v ? <Sourced src="engine.valuation.delta_clv" sources={sources}>{signedEur(v.delta_clv)}</Sourced> : <Missing />}
        </div>
        <div className="text-xs text-neutral-500">expected ΔCLV</div>
        <div className="mt-1 flex items-center justify-end gap-2 text-xs text-neutral-600">
          <span>
            p{" "}
            {v ? (
              <Sourced src="engine.valuation.p_accept" sources={sources}>
                <span className="tabular-nums">{pct(v.p_accept)}</span>
              </Sourced>
            ) : (
              <Missing />
            )}
          </span>
          <ConfidenceDot confidence={v?.confidence} />
        </div>
      </div>
    </div>
  );
}

const CHECK_LABEL: Record<ChecklistItem["item"], string> = {
  consent_for_channel: "Consent for the channel",
  profiling_consent: "Profiling consent",
  no_exclusion: "No exclusion",
  not_owned: "Not already owned",
  contact_cap: "Contact cap (≤ 2 per 30 days)",
  data_fresh: "Data fresh enough",
};

interface CheckRow {
  key: string;
  label: string;
  passed: boolean;
  warnOnly: boolean;
  detail?: string | null;
  src?: string | null;
}

function Checklist({ rows, sources }: { rows: CheckRow[]; sources: Sources }) {
  if (rows.length === 0) return <Missing />;
  return (
    <ul className="divide-y divide-neutral-100 rounded-lg border border-neutral-200">
      {rows.map((r) => {
        const icon = r.passed ? (
          <Check size={15} className="text-emerald-600" aria-label="passed" />
        ) : r.warnOnly ? (
          <AlertTriangle size={15} className="text-amber-500" aria-label="warning, does not block" />
        ) : (
          <X size={15} className="text-red-600" aria-label="failed" />
        );
        return (
          <li key={r.key} className="flex items-start gap-2.5 px-3 py-2 text-sm">
            <span className="mt-0.5 shrink-0">{icon}</span>
            <div className="min-w-0 flex-1">
              <div className="text-neutral-800">{r.label}</div>
              {r.detail && (
                <div className="text-xs text-neutral-500">
                  <Sourced src={r.src} sources={sources}>{r.detail}</Sourced>
                </div>
              )}
            </div>
            <span className="hidden max-w-[12rem] shrink-0 truncate font-mono text-[10px] text-neutral-400 sm:block" title={r.src ?? "source unknown"}>
              {r.src ?? "—"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function checklistRows(checklist: ChecklistItem[] | undefined, checks: RuleCheck[] | undefined): CheckRow[] {
  if (checklist && checklist.length > 0) {
    return checklist.map((c) => ({
      key: c.item,
      label: CHECK_LABEL[c.item] ?? c.item,
      passed: c.passed,
      warnOnly: c.item === "data_fresh",
      detail: c.detail,
      src: c.src,
    }));
  }
  return (checks ?? []).map((c, i) => ({
    key: `${c.rule_id}-${i}`,
    label: c.rule_id,
    passed: c.passed,
    warnOnly: false,
    detail: c.detail,
    src: c.src,
  }));
}

function ContentPreview({ content, offerId, sources }: { content: Content; offerId: string; sources: Sources }) {
  const generic = content.personalised === false && offerId !== "P-SV-01";
  return (
    <div className="space-y-2 rounded-lg border border-neutral-200 bg-neutral-50/60 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill>{toneLabel(content.tone)}</Pill>
        <Pill title="templates version / template id">
          <Sourced src="engine.content.template_id" sources={sources}>
            <span className="font-mono text-[11px]">{content.template_id}</span>
          </Sourced>
        </Pill>
        {generic && <Pill tone="amber">nicht personalisiert</Pill>}
      </div>
      <div lang="de" className="space-y-1">
        <div className="text-sm font-semibold text-neutral-900">{content.subject}</div>
        <p className="whitespace-pre-line text-sm leading-relaxed text-neutral-700">{content.body}</p>
      </div>
    </div>
  );
}

export function ActionDetail({
  card,
  cand,
  tupleId,
  activeSignal,
  onNavigate,
  sources,
  isTop,
  content,
  checklist,
  path,
  agentScript,
  decision,
}: {
  card: CustomerCard;
  cand: Candidate | undefined;
  tupleId: string;
  activeSignal: string | null;
  onNavigate: (uiRef: string) => void;
  sources: Sources;
  isTop: boolean;
  content?: Content | null;
  checklist?: ChecklistItem[];
  path?: PathStep[] | null;
  agentScript?: string | null;
  decision: ReactNode;
}) {
  const v = cand?.valuation;
  const notes = cand?.notes ?? [];
  const offerId = cand?.offer_id ?? tupleParts(tupleId).offer;
  return (
    <div className="space-y-6">
      {agentScript && (
        <Section title="Agent script (say this)">
          <div lang="de" className="whitespace-pre-line rounded-lg border border-accent-100 bg-accent-50 p-3 text-sm leading-relaxed text-neutral-800">
            {agentScript}
          </div>
        </Section>
      )}

      <Section title="Why it fits">
        {cand?.why && cand.why.length > 0 ? (
          <ul className="space-y-1.5 text-sm text-neutral-700">
            {cand.why.map((w, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-2 size-1 shrink-0 rounded-full bg-neutral-400" aria-hidden />
                <span className={mentionsSignal(w, activeSignal) ? "text-neutral-900" : undefined}>
                  <WithSignalRefs text={w} activeSignal={activeSignal} />
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Missing />
        )}
      </Section>

      <Section title="CLV impact">
        <ClvImpact v={v} sources={sources} clvFact={card.profile.value_risk?.clv_eur} />
      </Section>

      <Section title="Success vs failure">
        <SuccessEvidence v={v} sources={sources} />
      </Section>

      {notes.length > 0 && (
        <Section title="Notes">
          <ul className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {notes.map((n, i) => (
              <li key={i} className="flex gap-2">
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" aria-hidden />
                <span>{n}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={isTop ? "Checklist" : "Rule checks"}>
        <Checklist rows={checklistRows(isTop ? checklist : undefined, cand?.checks)} sources={sources} />
      </Section>

      <Section title={offerId === "P-SV-01" ? "Apology preview (German)" : "Content preview (German)"}>
        {content ? (
          <ContentPreview content={content} offerId={offerId} sources={sources} />
        ) : isTop ? (
          <Missing />
        ) : (
          <p className="text-sm text-neutral-500">
            Content is drafted for the top action only.
            {cand?.personalised === false && offerId !== "P-SV-01" && (
              <span className="ml-2 align-middle">
                <Pill tone="amber">nicht personalisiert</Pill>
              </span>
            )}
          </p>
        )}
      </Section>

      <Section title="Reasoning path">
        <ReasoningPath path={path ?? cand?.path} onNavigate={onNavigate} />
      </Section>

      <div className="border-t border-neutral-100 pt-4">{decision}</div>
    </div>
  );
}
