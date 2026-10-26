import { useEffect, useMemo, useState } from "react";
import { ChevronDown, CircleSlash, LifeBuoy, ShieldAlert, Sparkles } from "lucide-react";
import type { Alternative, Candidate, CustomerCard } from "../../types/contracts";
import type { Mode } from "../../pages/Customer";
import { latestByCustomer, useDecisions, type Decision } from "../../lib/decisions";
import { pct, signedEur, tupleLabel } from "../../lib/format";
import { ConfidenceDot, Section } from "../Chips";
import { Sourced } from "../Source";
import { ActionDetail, ActionHeader, WithSignalRefs } from "./ActionCard";
import { DecisionBar } from "./DecisionBar";
import { AuditLog, BlockedList, DataQualityList, LegacyComparisonBox } from "./Lists";
import { ACTION_TYPE_LABEL, Missing, Pill, RuleChip, StatusChip, channelLabel, mentionsSignal, statusFor, toneLabel, type Sources } from "./ui";

export interface NbaCardProps {
  card: CustomerCard;
  mode: Mode;
  /** Signal chip selected on the left; candidates driven by it are highlighted. */
  activeSignal: string | null;
  /** Jump to a ui_ref target on the left card (path chips). */
  onNavigate: (uiRef: string) => void;
}

// Right card "Next Best Actions, ranked" (README §4.2 C1–C8, prompts/agent-cards.md §1.3).
// Everything shown comes from the card JSON as-is; the frontend never re-ranks or re-values.

const drives = (c: Candidate | undefined, signal: string | null) => !!signal && !!c?.signals?.includes(signal);

function ReasonLine({ text, activeSignal }: { text: string; activeSignal: string | null }) {
  return (
    <p className="rounded-xl bg-accent-50 px-4 py-3 text-[15px] leading-relaxed text-neutral-900">
      <WithSignalRefs text={text} activeSignal={activeSignal} />
    </p>
  );
}

function SignalFocus({ card, activeSignal, ranked }: { card: CustomerCard; activeSignal: string; ranked: Candidate[] }) {
  const signal = card.signals?.find((s) => s.id === activeSignal);
  const driven = ranked.filter((c) => drives(c, activeSignal));
  const blocked = (card.blocked ?? []).some((b) => mentionsSignal(b.reason, activeSignal));
  return (
    <div className="flex items-start gap-2 rounded-lg border border-accent-100 bg-white px-3 py-2 text-sm text-neutral-700" role="status">
      <Sparkles size={15} className="mt-0.5 shrink-0 text-accent-500" aria-hidden />
      <span>
        <span className="font-medium text-accent-700">{activeSignal}</span>
        {signal ? ` ${signal.label}` : ""}:{" "}
        {driven.length > 0
          ? `drives ${driven.map((c) => `${c.offer_name} (#${c.rank ?? "–"})`).join(", ")}`
          : blocked
            ? "not used by a ranked action; see the blocked actions below"
            : "not used by any ranked action"}
      </span>
    </div>
  );
}

function TopCard({
  card,
  cand,
  latest,
  activeSignal,
  onNavigate,
  sources,
  service,
}: {
  card: CustomerCard;
  cand: Candidate | undefined;
  latest: Decision | undefined;
  activeSignal: string | null;
  onNavigate: (uiRef: string) => void;
  sources: Sources;
  service: boolean;
}) {
  const chosen = card.chosen;
  const status = statusFor(chosen.tuple_id, chosen.tuple_id, chosen.status, latest);
  const hl = drives(cand, activeSignal);
  return (
    <article
      className={`space-y-5 rounded-xl border bg-white p-4 shadow-sm transition-shadow duration-200 ${
        hl ? "border-accent-500 ring-2 ring-accent-500" : "border-neutral-200"
      }`}
      aria-label="Top action"
    >
      <ActionHeader cand={cand} tupleId={chosen.tuple_id} status={status} sendAt={chosen.send_at} showSendAt sources={sources} prominent />
      <ActionDetail
        card={card}
        cand={cand}
        tupleId={chosen.tuple_id}
        activeSignal={activeSignal}
        onNavigate={onNavigate}
        sources={sources}
        isTop
        content={chosen.content}
        checklist={card.checklist}
        path={card.explanation_path && card.explanation_path.length > 0 ? card.explanation_path : cand?.path}
        agentScript={service ? chosen.agent_script : null}
        decision={<DecisionBar card={card} variant="top" candidate={cand} allowOverride={!service} />}
      />
    </article>
  );
}

function AlternativeRow({
  card,
  alt,
  cand,
  latest,
  activeSignal,
  onNavigate,
  sources,
  open,
  onToggle,
}: {
  card: CustomerCard;
  alt: Alternative;
  cand: Candidate | undefined;
  latest: Decision | undefined;
  activeSignal: string | null;
  onNavigate: (uiRef: string) => void;
  sources: Sources;
  open: boolean;
  onToggle: () => void;
}) {
  const status = statusFor(alt.tuple_id, card.chosen.tuple_id, card.chosen.status, latest);
  const hl = drives(cand, activeSignal);
  const panelId = `alt-${card.customer_id}-${alt.tuple_id}`.replace(/[^A-Za-z0-9_-]/g, "_");
  return (
    <li
      className={`overflow-hidden rounded-xl border bg-white transition-shadow duration-200 ${
        hl ? "border-accent-500 ring-2 ring-accent-500" : "border-neutral-200"
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-neutral-50"
      >
        <span className="mt-0.5 rounded-md bg-neutral-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-neutral-600">
          #{cand?.rank ?? "–"}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium text-neutral-900">{cand?.offer_name ?? tupleLabel(alt.tuple_id)}</span>
            <span className="text-sm text-neutral-500">
              {channelLabel(cand?.channel ?? alt.tuple_id.split("|")[1])} · {toneLabel(cand?.tone ?? alt.tuple_id.split("|")[2])}
            </span>
            {status.label === "chosen by override" && <StatusChip status={status.status} label={status.label} />}
          </span>
          <span className="mt-0.5 block text-xs text-neutral-500">{alt.why_lower}</span>
        </span>
        <span className="shrink-0 text-right">
          <span className="block font-semibold tabular-nums text-neutral-900">
            <Sourced src="engine.alternatives.delta_clv" sources={sources}>{signedEur(alt.delta_clv)}</Sourced>
          </span>
          <span className="flex items-center justify-end gap-2 text-xs text-neutral-500">
            {cand?.valuation ? (
              <Sourced src="engine.valuation.p_accept" sources={sources}>
                p {pct(cand.valuation.p_accept)}
              </Sourced>
            ) : (
              <Missing />
            )}
            <ConfidenceDot confidence={cand?.valuation?.confidence} />
          </span>
        </span>
        <ChevronDown
          size={16}
          aria-hidden
          className={`mt-1 shrink-0 text-neutral-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div id={panelId} className="space-y-5 border-t border-neutral-100 px-4 pb-4 pt-4">
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
            {cand && <Pill>{ACTION_TYPE_LABEL[cand.action_type]}</Pill>}
            <span className="font-mono text-neutral-600">{cand?.offer_id ?? alt.tuple_id.split("|")[0]}</span>
            <StatusChip status={status.status} label={status.label} />
            <span>· send time is set for the top action only</span>
          </div>
          <ActionDetail
            card={card}
            cand={cand}
            tupleId={alt.tuple_id}
            activeSignal={activeSignal}
            onNavigate={onNavigate}
            sources={sources}
            isTop={false}
            decision={
              cand ? (
                <DecisionBar card={card} variant="alternative" candidate={cand} />
              ) : (
                <p className="text-xs text-neutral-500">This alternative is not among the gated candidates, so it cannot be selected.</p>
              )
            }
          />
        </div>
      )}
    </li>
  );
}

function Alternatives({
  card,
  byTuple,
  latest,
  activeSignal,
  onNavigate,
  sources,
}: {
  card: CustomerCard;
  byTuple: Map<string, Candidate>;
  latest: Decision | undefined;
  activeSignal: string | null;
  onNavigate: (uiRef: string) => void;
  sources: Sources;
}) {
  const alts = card.alternatives ?? [];
  const [open, setOpen] = useState<Set<string>>(new Set());

  // A signal clicked on the left opens the alternatives it drives.
  useEffect(() => {
    if (!activeSignal) return;
    const hit = alts.filter((a) => drives(byTuple.get(a.tuple_id), activeSignal)).map((a) => a.tuple_id);
    if (hit.length > 0) setOpen((cur) => new Set([...cur, ...hit]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSignal]);

  const toggle = (t: string) =>
    setOpen((cur) => {
      const next = new Set(cur);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  return (
    <Section title={`Alternatives (${alts.length})`} aside={<span className="text-xs text-neutral-400">ranked lower by the engine</span>}>
      {alts.length === 0 ? (
        <p className="text-sm text-neutral-500">No alternative passed every rule.</p>
      ) : (
        <ul className="space-y-2">
          {alts.map((a) => (
            <AlternativeRow
              key={a.tuple_id}
              card={card}
              alt={a}
              cand={byTuple.get(a.tuple_id)}
              latest={latest}
              activeSignal={activeSignal}
              onNavigate={onNavigate}
              sources={sources}
              open={open.has(a.tuple_id)}
              onToggle={() => toggle(a.tuple_id)}
            />
          ))}
        </ul>
      )}
    </Section>
  );
}

/** Service mode without a service candidate: the engine's own outcome, never a claim that contradicts the triage. */
function NoServiceAction({
  card,
  activeSignal,
  onNavigate,
}: {
  card: CustomerCard;
  activeSignal: string | null;
  onNavigate: (uiRef: string) => void;
}) {
  const exclusions = (card.profile?.exclusions ?? []).filter((e) => e.active);
  const critical = (card.triage?.flags ?? []).find((f) => f.id === "service_critical");

  if (exclusions.length === 0 && !critical) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-700">
        <LifeBuoy size={18} className="mt-0.5 shrink-0 text-neutral-400" aria-hidden />
        <div>
          <div className="font-medium text-neutral-900">No open service issue — switch to Marketing</div>
          <div className="text-neutral-500">The engine found nothing to resolve for this customer. Sales offers are hidden in service mode.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-neutral-200 bg-neutral-50 p-4 text-sm">
      <ShieldAlert size={18} className="mt-0.5 shrink-0 text-red-500" aria-hidden />
      <div className="min-w-0 space-y-2">
        <div className="font-medium text-neutral-900">No service action proposed</div>
        <p className="text-neutral-700">
          <WithSignalRefs text={card.chosen.reason_line} activeSignal={activeSignal} />
        </p>
        {exclusions.length > 0 ? (
          <ul className="space-y-1" aria-label="Active exclusions">
            {exclusions.map((e) => (
              <li key={e.rule_id}>
                <button
                  type="button"
                  onClick={() => onNavigate(`exclusion:${e.rule_id}`)}
                  title="Show on the customer profile"
                  className="flex flex-wrap items-center gap-2 rounded-md px-1 py-0.5 text-left text-xs text-neutral-600 transition-colors duration-150 hover:bg-white"
                >
                  <RuleChip rule={e.rule_id} />
                  <span>{e.detail ?? "active"}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          critical?.detail && <p className="text-xs text-neutral-600">Service critical: {critical.detail}</p>
        )}
        <p className="text-xs text-neutral-500">Sales offers are hidden in service mode.</p>
      </div>
    </div>
  );
}

export default function NbaCard({ card, mode, activeSignal, onNavigate }: NbaCardProps) {
  const decisions = useDecisions();
  const mine = useMemo(() => decisions.filter((d) => d.customer_id === card.customer_id), [decisions, card.customer_id]);
  const latest = latestByCustomer(mine).get(card.customer_id);
  const sources = card.sources;
  const chosen = card.chosen;
  const candidates = card.candidates ?? [];
  const byTuple = useMemo(() => new Map((card.candidates ?? []).map((c) => [c.tuple_id, c])), [card.candidates]);

  const isNoAction = chosen.tuple_id === "NO_ACTION";
  const chosenCand = isNoAction ? undefined : (byTuple.get(chosen.tuple_id) ?? candidates[0]);
  // The header toggle decides the view; meta.mode_default only sets the toggle's starting value.
  const serviceView = mode === "service";
  const serviceCand = chosen.service_mode ? chosenCand : candidates.find((c) => c.action_type === "service");
  const ranked = [chosenCand, ...(card.alternatives ?? []).map((a) => byTuple.get(a.tuple_id))].filter((c): c is Candidate => !!c);
  const hiddenSales = candidates.filter((c) => c.action_type !== "service").length;

  return (
    <div className="min-w-0 space-y-6" key={card.customer_id}>
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {serviceView ? (
            <LifeBuoy size={18} className="text-accent-600" aria-hidden />
          ) : (
            <Sparkles size={18} className="text-accent-600" aria-hidden />
          )}
          <h2 className="text-lg font-semibold tracking-tight">{serviceView ? "Resolve first" : "Next best actions, ranked"}</h2>
          <span className="ml-auto text-xs text-neutral-400">nothing is sent automatically</span>
        </div>
        {(serviceView ? !!serviceCand : !isNoAction) && <ReasonLine text={chosen.reason_line} activeSignal={activeSignal} />}
      </header>

      {activeSignal && !serviceView && <SignalFocus card={card} activeSignal={activeSignal} ranked={ranked} />}

      {serviceView ? (
        serviceCand ? (
          <>
            <TopCard
              card={card}
              cand={serviceCand}
              latest={latest}
              activeSignal={activeSignal}
              onNavigate={onNavigate}
              sources={sources}
              service
            />
            {hiddenSales > 0 && (
              <p className="text-sm text-neutral-500">
                Sales offers hidden in service mode ({hiddenSales} gated {hiddenSales === 1 ? "candidate" : "candidates"}). Resolve the issue first.
              </p>
            )}
          </>
        ) : (
          <NoServiceAction card={card} activeSignal={activeSignal} onNavigate={onNavigate} />
        )
      ) : isNoAction ? (
        <>
          <div className="flex items-start gap-3 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <CircleSlash size={18} className="mt-0.5 shrink-0 text-neutral-400" aria-hidden />
            <div className="space-y-1 text-sm">
              <div className="font-medium text-neutral-900">No action</div>
              <p className="text-neutral-700">
                <WithSignalRefs text={chosen.reason_line} activeSignal={activeSignal} />
              </p>
              <p className="text-xs text-neutral-500">The engine recommends not contacting this customer now. The rules that block each offer are listed below.</p>
            </div>
          </div>
          {(card.alternatives ?? []).length > 0 && (
            <Alternatives card={card} byTuple={byTuple} latest={latest} activeSignal={activeSignal} onNavigate={onNavigate} sources={sources} />
          )}
        </>
      ) : (
        <>
          {chosen.service_mode && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="note">
              <LifeBuoy size={15} className="mt-0.5 shrink-0 text-amber-600" aria-hidden />
              <span>The engine recommends resolving the service issue first. Sales alternatives are shown for review; switch to Service for the agent script.</span>
            </div>
          )}
          <TopCard
            card={card}
            cand={chosenCand}
            latest={latest}
            activeSignal={activeSignal}
            onNavigate={onNavigate}
            sources={sources}
            service={false}
          />
          <Alternatives card={card} byTuple={byTuple} latest={latest} activeSignal={activeSignal} onNavigate={onNavigate} sources={sources} />
        </>
      )}

      <BlockedList blocked={card.blocked} sources={sources} activeSignal={activeSignal} />
      <LegacyComparisonBox legacy={card.legacy_comparison} sources={sources} />
      <DataQualityList items={card.data_quality} />
      <AuditLog card={card} local={mine} />
    </div>
  );
}
