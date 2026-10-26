import { CalendarClock } from "lucide-react";
import type { CustomerCard } from "../../types/contracts";
import { FactValue, Sourced } from "../Source";
import { FlagBadge, Section, TIER_LABEL, TierChip } from "../Chips";
import { Field, num, type Sources } from "./shared";

const LANG: Record<string, string> = { de: "German", en: "English" };

/** A1–A2: who the customer is, plus Du/Sie with its evidence. */
export function ProfileHeader({ card }: { card: CustomerCard }) {
  const h = card.profile.header;
  const s = card.sources;
  const d = h.digital ?? {};
  const tone = h.tone;

  return (
    <Section title="Customer" uiRef="header">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold tracking-tight">{card.customer_id}</h2>
        <span
          className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs text-neutral-700"
          title={[tone.evidence, tone.refs?.length ? `refs: ${tone.refs.join(", ")}` : null].filter(Boolean).join("\n")}
        >
          <span className="font-semibold">{tone.value === "du" ? "Du" : "Sie"}</span>
          {tone.method === "default" ? (
            <span className="rounded bg-white px-1 text-[10px] uppercase tracking-wide text-neutral-500 ring-1 ring-neutral-200">default</span>
          ) : (
            <span className="text-neutral-500">from {tone.method}</span>
          )}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        <Field label="Age band">
          <FactValue fact={h.age_band} sources={s} />
        </Field>
        <Field label="City">
          <FactValue fact={h.city} sources={s} />
        </Field>
        <Field label="Household">
          <FactValue fact={h.household_size} sources={s} format={(v: number) => `${num(v)} ${v === 1 ? "person" : "people"}`} />
        </Field>
        <Field label="Customer for">
          <FactValue fact={h.tenure_years} sources={s} format={(v: number) => `${num(v, 1)} years`} />
        </Field>
        <Field label="Portal account">
          <FactValue fact={d.portal_account} sources={s} />
        </Field>
        <Field label="App">
          <FactValue fact={d.app_installed} sources={s} />
        </Field>
        <Field label="Language">
          <FactValue fact={d.language} sources={s} format={(v: string) => LANG[v] ?? v} />
        </Field>
      </dl>
      <p className="mt-2 text-xs leading-relaxed text-neutral-500">
        <span className="font-medium text-neutral-700">Tone: </span>
        {tone.evidence}
      </p>
    </Section>
  );
}

/** A3: why this customer is on the worklist (archetype, urgency, flags). */
export function TriageBanner({ card, sources }: { card: CustomerCard; sources: Sources }) {
  const t = card.triage;
  const reasons = t.urgency_reasons ?? [];
  const flags = t.flags ?? [];
  return (
    <div className="rounded-xl border border-neutral-200 bg-neutral-50/70 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <TierChip tier={t.urgency_tier} />
        <span className="text-sm font-medium">{TIER_LABEL[t.urgency_tier]}</span>
        <span className="text-xs text-neutral-500">
          score <Sourced src="triage.urgency_score" sources={sources}>{num(t.urgency_score, 1)}</Sourced>
        </span>
        {t.deadline && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs text-neutral-700 ring-1 ring-neutral-200">
            <CalendarClock className="size-3.5 text-neutral-500" aria-hidden />
            Deadline <Sourced src="triage.deadline" sources={sources}>{t.deadline}</Sourced>
          </span>
        )}
      </div>
      <p className="mt-2 text-sm">
        <span className="font-medium">{t.archetype.name}</span>
        <span className="text-neutral-400"> · {t.archetype.id}</span>
        <span className="text-neutral-600"> — {t.archetype.reason}</span>
      </p>
      {reasons.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-sm text-neutral-700">
          {reasons.map((r) => (
            <li key={r} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-neutral-400" aria-hidden />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
      {flags.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {flags.map((f) => (
            <FlagBadge key={f.id} id={f.id} label={f.label} title={[f.detail, f.src].filter(Boolean).join("\n") || undefined} />
          ))}
        </div>
      )}
    </div>
  );
}
