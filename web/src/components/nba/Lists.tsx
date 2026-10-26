import { useState } from "react";
import { AlertTriangle, History, Info } from "lucide-react";
import type { Blocked, CustomerCard, DataQuality, LegacyComparison } from "../../types/contracts";
import type { Decision } from "../../lib/decisions";
import { pct, signedEur, tupleLabel } from "../../lib/format";
import { Section } from "../Chips";
import { Sourced } from "../Source";
import { Missing, RuleChip, StatusChip, channelLabel, mentionsSignal, tsLabel, type Sources, type Status } from "./ui";

// Below the ranked actions: blocked actions (C6), legacy comparison (C6), data quality (§6.9)
// and the decision audit log (C8).

const FIRST = 6;

function BlockedRow({ b, sources, active }: { b: Blocked; sources: Sources; active: boolean }) {
  return (
    <li className={`flex flex-col gap-1 px-3 py-2.5 text-sm transition-colors duration-200 ${active ? "bg-accent-50" : ""}`}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <RuleChip rule={b.rule_id} />
        {b.offer_id === "*" ? (
          <span className="font-medium text-neutral-900">All offers</span>
        ) : (
          <span className="font-mono text-xs text-neutral-800">{b.offer_id}</span>
        )}
        <span className="text-xs text-neutral-500">{b.channel ? channelLabel(b.channel) : "any channel"}</span>
        {b.counterfactual_delta_clv !== null && b.counterfactual_delta_clv !== undefined && (
          <span className="ml-auto text-xs text-neutral-500">
            would be{" "}
            <Sourced src="engine.blocked.counterfactual_delta_clv" sources={sources}>
              <span className="tabular-nums">{signedEur(b.counterfactual_delta_clv)}</span>
            </Sourced>
          </span>
        )}
      </div>
      <Sourced src={b.src ?? `engine.rules.${b.rule_id}`} sources={sources}>
        <span className="text-neutral-600">{b.reason}</span>
      </Sourced>
    </li>
  );
}

const RULE_ORDER = ["EXCL-", "CONTACT-CAP", "CONSENT-PROFILING", "HOLDING-PRECONDITION", "ECON-NONPOSITIVE", "CONSENT-CHANNEL", "CHANNEL-AVAILABLE", "DATA-MISSING"];

function rulePriority(ruleId: string): number {
  const i = RULE_ORDER.findIndex((r) => ruleId.startsWith(r));
  return i < 0 ? RULE_ORDER.length : i;
}

export function BlockedList({ blocked, sources, activeSignal }: { blocked: Blocked[] | undefined; sources: Sources; activeSignal: string | null }) {
  const [all, setAll] = useState(false);
  const list = blocked ?? [];
  // Most telling rules first (exclusions and ignored signals explain the decision; per-channel consent
  // and missing-data rows are background), then customer-level blocks ("*") within a rule.
  const sorted = [...list].sort(
    (a, b) => rulePriority(a.rule_id) - rulePriority(b.rule_id) || Number(b.offer_id === "*") - Number(a.offer_id === "*"),
  );
  const shown = all ? sorted : sorted.slice(0, FIRST);
  return (
    <Section title={`Blocked actions (${list.length})`} aside={<span className="text-xs text-neutral-400">never selectable</span>}>
      {list.length === 0 ? (
        <p className="text-sm text-neutral-500">Nothing blocked for this customer.</p>
      ) : (
        <>
          <ul className="divide-y divide-neutral-100 overflow-hidden rounded-lg border border-neutral-200">
            {shown.map((b, i) => (
              <BlockedRow key={`${b.offer_id}-${b.rule_id}-${i}`} b={b} sources={sources} active={mentionsSignal(b.reason, activeSignal)} />
            ))}
          </ul>
          {list.length > FIRST && (
            <button
              type="button"
              onClick={() => setAll(!all)}
              className="mt-2 rounded-md px-2 py-1 text-xs font-medium text-accent-700 transition-colors duration-150 hover:bg-accent-50"
            >
              {all ? "Show fewer" : `Show all ${list.length}`}
            </button>
          )}
        </>
      )}
    </Section>
  );
}

export function LegacyComparisonBox({ legacy, sources }: { legacy: LegacyComparison | null | undefined; sources: Sources }) {
  return (
    <Section title="Legacy comparison">
      {!legacy || !legacy.rule_id ? (
        <p className="text-sm text-neutral-500">No legacy rule-engine send on record.</p>
      ) : (
        <div className="space-y-2 rounded-lg border border-neutral-200 p-3 text-sm text-neutral-700">
          <p>
            The old rule engine would send{" "}
            <Sourced src="nba_action_history.rule_id" sources={sources}>
              <span className="font-mono text-xs font-medium text-neutral-900">{legacy.rule_id}</span>
            </Sourced>{" "}
            ({legacy.offer_id ? <span className="font-mono text-xs">{legacy.offer_id}</span> : <Missing />} via {channelLabel(legacy.channel)},{" "}
            <Sourced src="nba_action_history.decided_at" sources={sources}>
              {legacy.decided_at ?? <Missing />}
            </Sourced>
            ): ΔCLV{" "}
            <Sourced src="engine.legacy_comparison.delta_clv_our_model" sources={sources}>
              <span className="font-semibold tabular-nums text-neutral-900">{signedEur(legacy.delta_clv_our_model)}</span>
            </Sourced>{" "}
            under our model.
          </p>
          {legacy.blocked_now_by && legacy.blocked_now_by.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
              Now blocked by {legacy.blocked_now_by.map((r) => <RuleChip key={r} rule={r} />)}
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

export function DataQualityList({ items }: { items: DataQuality[] | undefined }) {
  if (!items || items.length === 0) return null;
  return (
    <Section title="Data quality" aside={<span className="text-xs text-neutral-400">warnings never block</span>}>
      <ul className="space-y-1.5">
        {items.map((d, i) => {
          const warn = d.level === "warn";
          return (
            <li
              key={`${d.code}-${i}`}
              className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ring-1 ring-inset ${
                warn ? "bg-amber-50 text-amber-900 ring-amber-200" : "bg-neutral-50 text-neutral-700 ring-neutral-200"
              }`}
            >
              {warn ? (
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-500" aria-label="warning" />
              ) : (
                <Info size={15} className="mt-0.5 shrink-0 text-neutral-400" aria-label="info" />
              )}
              <span>
                <span className="mr-1.5 font-mono text-[11px]">{d.code}</span>
                {d.detail}
              </span>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

interface LogRow {
  key: string;
  ts: string;
  actor: string;
  action: Status;
  tuple: string | null | undefined;
  from: string | null | undefined;
  reason: string | null | undefined;
  /** ΔCLV and p are rendered separately so each carries its source tooltip. */
  delta?: number | null;
  p?: number | null;
  scoreSrc: string;
  extra?: string;
  local: boolean;
}

export function AuditLog({ card, local }: { card: CustomerCard; local: Decision[] }) {
  const rows: LogRow[] = [
    ...(card.decision_log ?? []).map((e, i) => ({
      key: `engine-${i}`,
      ts: e.ts,
      actor: e.actor,
      action: e.action,
      tuple: e.to_tuple ?? e.tuple_id,
      from: e.from_tuple,
      reason: e.reason,
      delta: e.scores?.delta_clv,
      p: e.scores?.p_accept,
      scoreSrc: "engine.decision_log.scores",
      extra: [
        e.rules_applied && e.rules_applied.length > 0 ? `rules: ${e.rules_applied.join(", ")}` : null,
        e.versions ? Object.entries(e.versions).map(([k, v]) => `${k} ${v}`).join(" · ") : null,
      ]
        .filter(Boolean)
        .join(" · "),
      local: false,
    })),
    ...local.map((d) => ({
      key: d.id,
      ts: d.ts,
      actor: d.reviewer,
      action: d.action as Status,
      tuple: d.tuple_id,
      from: d.action === "overridden" ? d.from_tuple : null,
      reason: d.reason,
      delta: d.delta_clv ?? undefined,
      p: d.p_accept ?? undefined,
      scoreSrc: "engine.valuation",
      local: true,
    })),
  ].sort((a, b) => (a.ts < b.ts ? 1 : -1));

  return (
    <Section title="Decision log" aside={<span className="text-xs text-neutral-400">append-only · local decisions stay in this browser</span>}>
      {rows.length === 0 ? (
        <p className="text-sm text-neutral-500">No decisions yet.</p>
      ) : (
        <ol className="space-y-2">
          {rows.map((r) => (
            <li key={r.key} className="flex gap-2.5 text-sm">
              <History size={14} className="mt-1 shrink-0 text-neutral-400" aria-hidden />
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <StatusChip status={r.action} />
                  <span className="font-medium text-neutral-800">{r.tuple ? tupleLabel(r.tuple) : "—"}</span>
                  {r.from && r.from !== r.tuple && <span className="text-xs text-neutral-500">from {tupleLabel(r.from)}</span>}
                </div>
                <div className="text-xs text-neutral-500">
                  {tsLabel(r.ts)} · {r.actor}
                  {r.local ? " · this browser" : ""}
                </div>
                {r.reason && <div className="text-xs text-neutral-600">“{r.reason}”</div>}
                {(r.delta !== undefined || r.p !== undefined || r.extra) && (
                  <div className="break-words text-[11px] text-neutral-400">
                    {[
                      r.delta !== undefined && (
                        <span key="d">
                          ΔCLV{" "}
                          <Sourced src={`${r.scoreSrc}.delta_clv`} sources={card.sources}>
                            <span className="tabular-nums">{signedEur(r.delta)}</span>
                          </Sourced>
                        </span>
                      ),
                      r.p !== undefined && (
                        <span key="p">
                          p{" "}
                          <Sourced src={`${r.scoreSrc}.p_accept`} sources={card.sources}>
                            <span className="tabular-nums">{pct(r.p)}</span>
                          </Sourced>
                        </span>
                      ),
                      r.extra ? <span key="x">{r.extra}</span> : null,
                    ]
                      .filter(Boolean)
                      .flatMap((el, i) => (i ? [<span key={`sep-${i}`}> · </span>, el] : [el]))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}
