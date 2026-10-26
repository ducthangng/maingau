import { useMemo, useState, type ReactNode } from "react";
import {
  Archive,
  CalendarClock,
  Check,
  CircleSlash,
  Eye,
  Headset,
  Info,
  LifeBuoy,
  MousePointerClick,
  Package,
  ShoppingBag,
  Sparkles,
  Stamp,
  TriangleAlert,
  User,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Alternative, Candidate, CustomerCard, Signal } from "../../types/contracts";
import { latestByCustomer, useDecisions, type Decision } from "../../lib/decisions";
import { CHANNEL_LABEL, pct, signedEur, tupleLabel } from "../../lib/format";
import { DecisionBar } from "../nba/DecisionBar";
import { ReasoningPath } from "../nba/ReasoningPath";
import { WithSignalRefs } from "../nba/ActionCard";
import { StatusChip, statusFor } from "../nba/ui";
import { OFFER_NAME } from "../worklist/model";
import { CHANNEL_ICON, ConfidenceBars, Signed, ValueBar, dirOf } from "../viz";
import Canvas from "./Canvas";
import { SignalChip, upsideOf } from "./parts";

// The pop-up's right column as a flow graph on a pannable, zoomable canvas (see Canvas), read top to bottom: what happened before (actions taken
// or not taken), the trigger now, one branch per option, and the decision. Kept deliberately quiet:
// one line per node, icons for outcomes, comments folded to one line; every node explains itself on ⓘ.
// Display only: nothing here re-ranks or re-values.

/* ---------------------------------------------------------------- comments */

type Role = "engine" | "agent" | "reviewer" | "system" | "legacy";

interface Note {
  id: string;
  role: Role;
  author: string;
  date?: string | null;
  text: ReactNode;
}

const ROLE: Record<Role, { icon: LucideIcon; cls: string }> = {
  engine: { icon: Sparkles, cls: "bg-accent-600 text-white" },
  agent: { icon: Headset, cls: "bg-neutral-800 text-white" },
  reviewer: { icon: User, cls: "bg-emerald-600 text-white" },
  system: { icon: TriangleAlert, cls: "bg-amber-400 text-amber-950" },
  legacy: { icon: Archive, cls: "bg-neutral-400 text-white" },
};

/** A comment folded to one line (avatar + text); click to read it in full. */
function NoteChip({ note }: { note: Note }) {
  const [open, setOpen] = useState(false);
  const r = ROLE[note.role];
  const Icon = r.icon;
  return (
    <button
      type="button"
      onClick={() => setOpen((o) => !o)}
      aria-expanded={open}
      title={open ? undefined : `${note.author}${note.date ? ` · ${note.date.slice(0, 10)}` : ""}`}
      className="relative flex w-full items-start gap-2 rounded-lg bg-white px-2.5 py-2 text-left shadow-sm ring-1 ring-neutral-200 transition-shadow duration-150 hover:shadow-md"
    >
      <span className="absolute top-3.5 -left-8 hidden w-8 border-t border-dashed border-neutral-300 lg:block" aria-hidden />
      <span className={`mt-px grid size-4 shrink-0 place-items-center rounded-full ${r.cls}`}>
        <Icon size={9} aria-hidden />
      </span>
      <span className={`min-w-0 text-[11px] leading-snug text-neutral-700 ${open ? "" : "truncate"}`}>
        {open && (
          <span className="block font-medium text-neutral-900">
            {note.author}
            {note.date && <span className="ml-1 font-normal text-neutral-400">{note.date.slice(0, 10)}</span>}
          </span>
        )}
        {note.text}
      </span>
    </button>
  );
}

/** One graph row: node centred on the canvas, its comments in the gutter. The edge runs on below the node. */
function Row({ children, notes = [], last = false }: { children: ReactNode; notes?: Note[]; last?: boolean }) {
  return (
    <div className="grid gap-x-8 gap-y-2 lg:grid-cols-[minmax(0,1fr)_190px]">
      <div className="flex min-w-0 flex-col items-center">
        {children}
        {!last && <span className="min-h-6 flex-1 border-l-2 border-dashed border-neutral-300" aria-hidden />}
      </div>
      <div className="space-y-1.5">
        {notes.map((n) => (
          <NoteChip key={n.id} note={n} />
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- nodes */

function Stub({ solid, accent, h = 12 }: { solid?: boolean; accent?: boolean; h?: number }) {
  return (
    <span
      className={`border-l-2 ${solid ? "" : "border-dashed"} ${accent ? "border-accent-500" : "border-neutral-300"}`}
      style={{ height: h }}
      aria-hidden
    />
  );
}

function InfoButton({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onClick();
        }
      }}
      aria-expanded={open}
      aria-label={open ? "Hide explanation" : "Explain"}
      title={open ? "Hide explanation" : "Explain"}
      className={`grid size-5 shrink-0 cursor-pointer place-items-center rounded transition-colors duration-150 ${
        open ? "bg-neutral-900 text-white" : "text-neutral-300 hover:bg-neutral-100 hover:text-neutral-700"
      }`}
    >
      <Info size={13} aria-hidden />
    </span>
  );
}

function Explain({ children }: { children: ReactNode }) {
  return (
    <div className="mt-1.5 w-full space-y-1.5 rounded-lg bg-white p-2.5 text-[11px] leading-relaxed text-neutral-700 shadow-sm ring-1 ring-neutral-200">
      {children}
    </div>
  );
}

/** A one-line node: icon, label, an outcome mark on the right, and ⓘ to explain. */
function Pill({
  icon: Icon,
  label,
  mark,
  date,
  dashed,
  tone = "plain",
  explain,
  width = "max-w-[300px]",
}: {
  icon: LucideIcon;
  label: ReactNode;
  mark?: ReactNode;
  date?: string;
  dashed?: boolean;
  tone?: "plain" | "trigger" | "decision";
  explain?: ReactNode;
  width?: string;
}) {
  const [open, setOpen] = useState(false);
  const toneCls =
    tone === "trigger"
      ? "bg-red-50 text-red-900 ring-red-200"
      : tone === "decision"
        ? "bg-white ring-2 ring-accent-500"
        : "bg-white ring-neutral-200";
  return (
    <div className={`flex w-full flex-col items-center ${width}`}>
      {date && <span className="mb-1 text-[10px] text-neutral-400 tabular-nums">{date}</span>}
      <div
        className={`flex w-full items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-[13px] shadow-sm ${
          dashed ? "border border-dashed border-neutral-300 bg-white/80 text-neutral-500" : `ring-1 ${toneCls}`
        }`}
      >
        <Icon size={14} className="shrink-0 opacity-70" aria-hidden />
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {mark}
        {explain && <InfoButton open={open} onClick={() => setOpen((o) => !o)} />}
      </div>
      {open && explain && <Explain>{explain}</Explain>}
    </div>
  );
}

function Fact({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-16 shrink-0 text-neutral-400">{k}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

/* ---------------------------------------------------------------- history model */

type Outcome = "taken" | "not_taken" | "neutral";

interface HistoryItem {
  id: string;
  date: string;
  icon: LucideIcon;
  title: string;
  channel?: string | null;
  outcome: Outcome;
  outcomeLabel: string;
  facts: [string, string][];
  notes: Note[];
}

const OUTCOME: Record<string, [Outcome, string]> = {
  converted: ["taken", "Converted"],
  clicked: ["taken", "Clicked"],
  viewed: ["neutral", "Viewed"],
  ignored: ["not_taken", "Ignored"],
  dismissed: ["not_taken", "Dismissed"],
};

const offerName = (id: string | null | undefined) => (id ? (OFFER_NAME[id] ?? id) : "offer");
const human = (s: string) => s.replace(/_/g, " ");

/** Past actions and touchpoints from the card's timeline and agent feedback, oldest first. */
function buildHistory(card: CustomerCard): HistoryItem[] {
  const items: HistoryItem[] = [];
  const legacy = card.legacy_comparison;

  for (const t of card.timeline ?? []) {
    if (t.future) continue;
    if (t.kind === "marketing") {
      const m = /Offer (\S+) via (\S+)/.exec(t.title);
      const [rule, ...rest] = (t.detail ?? "").split(" · ");
      const [outcome, label] = OUTCOME[rest[rest.length - 1] ?? ""] ?? ["neutral", rest.join(" ") || "sent"];
      const notes: Note[] = (t.flags ?? []).map((f, i) => ({
        id: `${t.id}-f${i}`,
        role: "system" as const,
        author: "Compliance check",
        date: t.date,
        text: f,
      }));
      if (legacy && m && legacy.offer_id === m[1] && legacy.decided_at === t.date) {
        notes.push({
          id: `${t.id}-legacy`,
          role: "legacy",
          author: "Legacy engine",
          date: legacy.decided_at,
          text: `Rule ${legacy.rule_id ?? "?"}${legacy.blocked_now_by?.length ? `; blocked today by ${legacy.blocked_now_by.join(", ")}` : ""}`,
        });
      }
      items.push({
        id: t.id,
        date: t.date,
        icon: outcome === "taken" ? MousePointerClick : outcome === "not_taken" ? CircleSlash : Eye,
        title: m ? offerName(m[1]) : t.title,
        channel: m?.[2],
        outcome,
        outcomeLabel: label,
        facts: [
          ["Outcome", label],
          ["Channel", m ? (CHANNEL_LABEL[m[2]] ?? m[2]) : "–"],
          ["Rule", rule || "–"],
          ["Source", t.src],
        ],
        notes,
      });
    } else if (t.kind === "service") {
      const parts = (t.detail ?? "").split(" · ");
      const csat = /CSAT (\d)/.exec(t.detail ?? "")?.[1];
      items.push({
        id: t.id,
        date: t.date,
        icon: LifeBuoy,
        title: t.title.replace("Ticket: ", "Ticket · "),
        outcome: "neutral",
        outcomeLabel: csat ? `CSAT ${csat}` : (parts[1] ?? "ticket"),
        facts: [
          ["Channel", parts[0] || "–"],
          ["Status", parts[1] || "–"],
          ["CSAT", csat ?? "–"],
          ["Reference", t.ref ?? "–"],
        ],
        notes:
          csat && Number(csat) <= 2
            ? [
                {
                  id: `${t.id}-csat`,
                  role: "system",
                  author: "Service quality",
                  date: t.date,
                  text: `Low satisfaction (CSAT ${csat})`,
                },
              ]
            : [],
      });
    } else if (t.kind === "order") {
      items.push({
        id: t.id,
        date: t.date,
        icon: ShoppingBag,
        title: t.title,
        outcome: "taken",
        outcomeLabel: t.detail ?? "ordered",
        facts: [
          ["Status", t.detail ?? "–"],
          ["Reference", t.ref ?? "–"],
        ],
        notes: [],
      });
    }
  }

  for (const [i, raw] of (card.profile.fatigue?.agent_feedback ?? []).entries()) {
    const f = raw as Record<string, string | null>;
    const dismissed = f.agent_action === "dismissed";
    items.push({
      id: `fb-${i}`,
      date: f.date ?? "",
      icon: Headset,
      title: offerName(f.offer_id),
      outcome: dismissed ? "not_taken" : f.customer_reaction === "interested" ? "taken" : "neutral",
      outcomeLabel: dismissed ? "Not offered" : `Offered · ${f.customer_reaction ?? "no reaction"}`,
      facts: [
        ["Where", "Service call"],
        ["Ticket", f.ticket_id ?? "–"],
        ["Source", f.src ?? "service_nba_feedback"],
      ],
      notes: [
        {
          id: `fb-${i}-n`,
          role: "agent",
          author: "Service agent",
          date: f.date,
          text: dismissed ? `Not offered: ${human(f.dismiss_reason ?? "no reason")}` : `Offered; customer ${f.customer_reaction ?? "silent"}`,
        },
      ],
    });
  }

  return items.sort((a, b) => a.date.localeCompare(b.date));
}

/** Outcome as a single icon (word in the tooltip): ✓ taken, ✕ not taken, ● neutral. */
function OutcomeMark({ outcome, label }: { outcome: Outcome; label: string }) {
  if (outcome === "taken")
    return (
      <span title={label} aria-label={label} role="img" className="grid size-4 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
        <Check size={10} strokeWidth={3} aria-hidden />
      </span>
    );
  if (outcome === "not_taken")
    return (
      <span title={label} aria-label={label} role="img" className="grid size-4 shrink-0 place-items-center rounded-full bg-red-500 text-white">
        <X size={10} strokeWidth={3} aria-hidden />
      </span>
    );
  return (
    <span title={label} className="shrink-0 text-[11px] text-neutral-400">
      {label}
    </span>
  );
}

/* ---------------------------------------------------------------- options */

interface Option {
  tuple: string;
  cand?: Candidate;
  alt?: Alternative;
}

function condition(card: CustomerCard, o: Option): { text: string; signals: Signal[] } {
  if (o.tuple === "NO_ACTION") return { text: "All offers blocked", signals: [] };
  if (o.cand?.action_type === "service") return { text: "Service issue", signals: [] };
  const sigs = (card.signals ?? []).filter((s) => o.cand?.signals?.includes(s.id));
  if (sigs.length)
    return {
      text: sigs[0].label + (sigs.length > 1 ? ` +${sigs.length - 1}` : ""),
      signals: sigs,
    };
  return { text: "Catalog offer", signals: [] };
}

function IfChip({ text, accent }: { text: string; accent?: boolean }) {
  return (
    <span
      className={`inline-flex max-w-full items-stretch overflow-hidden rounded-md bg-white text-[11px] ring-1 ${accent ? "ring-accent-500" : "ring-neutral-300"}`}
      title={text}
    >
      <span className={`grid place-items-center px-1.5 font-semibold text-white ${accent ? "bg-accent-600" : "bg-neutral-700"}`}>IF</span>
      <span className="truncate px-1.5 py-0.5 text-neutral-700">{text}</span>
    </span>
  );
}

function OptionCard({
  o,
  selected,
  maxDelta,
  explaining,
  onSelect,
  onExplain,
}: {
  o: Option;
  selected: boolean;
  maxDelta: number;
  explaining: boolean;
  onSelect: () => void;
  onExplain: () => void;
}) {
  const d = o.cand?.valuation?.delta_clv ?? o.alt?.delta_clv ?? 0;
  const ch = o.cand?.channel ?? o.tuple.split("|")[1];
  const Ch = o.tuple === "NO_ACTION" ? CircleSlash : (CHANNEL_ICON[ch] ?? Package);
  const name = o.tuple === "NO_ACTION" ? "Do not contact" : (o.cand?.offer_name ?? tupleLabel(o.tuple));
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      title={`${name}${o.tuple !== "NO_ACTION" ? ` · ${CHANNEL_LABEL[ch] ?? ch}` : ""}${selected ? "" : "\nClick to follow this branch"}`}
      className={`w-full rounded-xl bg-white px-3 py-2.5 text-left shadow-sm transition-shadow duration-150 hover:shadow-md ${
        selected ? "ring-2 ring-accent-500" : "ring-1 ring-neutral-200"
      }`}
    >
      <span className="flex items-start gap-1.5">
        <Ch size={14} className={`mt-0.5 shrink-0 ${selected ? "text-accent-600" : "text-neutral-400"}`} aria-hidden />
        <span className="line-clamp-2 min-w-0 flex-1 text-[13px] leading-snug font-medium text-neutral-900">{name}</span>
        <InfoButton open={explaining} onClick={onExplain} />
      </span>
      {o.tuple !== "NO_ACTION" && (
        <span className="mt-1 flex items-center gap-2">
          <Signed dir={dirOf(d)} className="w-[72px] shrink-0 text-xs font-medium text-neutral-800">
            {signedEur(d)}
          </Signed>
          <ValueBar value={d} max={maxDelta} tone={selected ? "accent" : "muted"} className="flex-1" />
        </span>
      )}
    </button>
  );
}

function OptionExplain({ card, o }: { card: CustomerCard; o: Option }) {
  const c = o.cand;
  const v = c?.valuation;
  const up = upsideOf(c);
  const path = o.tuple === card.chosen.tuple_id && card.explanation_path?.length ? card.explanation_path : c?.path;
  const lines = [...(c?.why ?? []), ...(c?.notes ?? [])];
  const failed = (c?.checks ?? []).filter((k) => !k.passed);
  if (o.tuple === "NO_ACTION")
    return (
      <p>
        <WithSignalRefs text={card.chosen.reason_line} activeSignal={null} />
      </p>
    );
  return (
    <>
      {path && path.length > 0 && <ReasoningPath path={path} onNavigate={() => {}} />}
      {v && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 tabular-nums">
          <span>p {pct(v.p_accept)}</span>
          <span className="text-neutral-400">×</span>
          <span>{up === null ? "–" : signedEur(up)} if accepted</span>
          <span className="text-neutral-400">=</span>
          <span className="font-medium">{signedEur(v.delta_clv)}</span>
          <ConfidenceBars confidence={v.confidence} />
        </div>
      )}
      {o.alt?.why_lower && <p className="text-neutral-500">Lower: {o.alt.why_lower}</p>}
      {lines.map((l) => (
        <p key={l}>
          <WithSignalRefs text={l} activeSignal={null} />
        </p>
      ))}
      {c?.checks && (
        <p className={failed.length ? "text-red-700" : "text-emerald-700"}>
          {failed.length ? `Failed: ${failed.map((k) => k.rule_id).join(", ")}` : `${c.checks.length}/${c.checks.length} rules passed`}
        </p>
      )}
    </>
  );
}

/** Trigger → one branch per option → merge. The selected branch is solid and in the accent. */
function Branches({ card, options, selected, onSelect }: { card: CustomerCard; options: Option[]; selected: string; onSelect: (t: string) => void }) {
  const [explain, setExplain] = useState<string | null>(null);
  const n = options.length;
  const inset = `${50 / n}%`;
  const maxDelta = Math.max(1, ...options.map((o) => Math.abs(o.cand?.valuation?.delta_clv ?? o.alt?.delta_clv ?? 0)));
  const conds = options.map((o) => condition(card, o).text);
  const sameCond = conds.every((c) => c === conds[0]);
  const ex = options.find((o) => o.tuple === explain);
  return (
    <div className="flex w-full flex-col items-center">
      {sameCond && (
        <>
          <IfChip text={conds[0]} accent />
          <Stub solid accent h={8} />
        </>
      )}
      <div className="relative grid w-full gap-4" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {n > 1 && <span className="absolute top-0 border-t-2 border-dashed border-neutral-300" style={{ left: inset, right: inset }} aria-hidden />}
        {n > 1 && (
          <span className="absolute bottom-0 border-t-2 border-dashed border-neutral-300" style={{ left: inset, right: inset }} aria-hidden />
        )}
        {options.map((o, i) => {
          const on = o.tuple === selected;
          return (
            <div key={o.tuple} className="flex min-w-0 flex-col items-center">
              <Stub solid={on} accent={on} />
              {!sameCond && (
                <>
                  <IfChip text={conds[i]} accent={on} />
                  <Stub solid={on} accent={on} h={6} />
                </>
              )}
              <OptionCard
                o={o}
                selected={on}
                maxDelta={maxDelta}
                explaining={explain === o.tuple}
                onSelect={() => onSelect(o.tuple)}
                onExplain={() => setExplain(explain === o.tuple ? null : o.tuple)}
              />
              <Stub solid={on} accent={on} />
            </div>
          );
        })}
      </div>
      {ex && (
        <Explain>
          <OptionExplain card={card} o={ex} />
        </Explain>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- graph */

const MAX_OPTIONS = 3;
const MAX_HISTORY = 3;

const decisionNote = (d: Decision): Note => ({
  id: d.id,
  role: "reviewer",
  author: d.reviewer,
  date: d.ts,
  text: `${d.action[0].toUpperCase()}${d.action.slice(1)}${d.action === "overridden" ? ` → ${tupleLabel(d.tuple_id)}` : ""}${d.reason ? `: ${d.reason}` : ""}`,
});

export default function ActionGraph({ card }: { card: CustomerCard }) {
  const decisions = useDecisions();
  const mine = useMemo(() => decisions.filter((d) => d.customer_id === card.customer_id), [decisions, card.customer_id]);
  const latest = latestByCustomer(mine).get(card.customer_id);
  const chosen = card.chosen;
  const byTuple = useMemo(() => new Map((card.candidates ?? []).map((c) => [c.tuple_id, c])), [card.candidates]);
  const history = useMemo(() => buildHistory(card), [card]);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [showAllOptions, setShowAllOptions] = useState(false);

  const allOptions: Option[] = [
    { tuple: chosen.tuple_id, cand: byTuple.get(chosen.tuple_id) },
    ...(card.alternatives ?? []).map((a) => ({
      tuple: a.tuple_id,
      cand: byTuple.get(a.tuple_id),
      alt: a,
    })),
  ];
  const options = showAllOptions ? allOptions : allOptions.slice(0, MAX_OPTIONS);
  const [selected, setSelected] = useState(chosen.tuple_id);
  const sel = allOptions.find((o) => o.tuple === selected) ?? allOptions[0];
  const selSignals = condition(card, sel).signals;

  const shownHistory = showAllHistory ? history : history.slice(-MAX_HISTORY);
  const hidden = history.length - shownHistory.length;
  const next = (card.timeline ?? []).filter((t) => t.future).sort((a, b) => a.date.localeCompare(b.date))[0];
  const signals = card.signals ?? [];
  const blocked = card.blocked ?? [];
  const isNoAction = chosen.tuple_id === "NO_ACTION";
  const followingTop = sel.tuple === chosen.tuple_id;
  const status = statusFor(chosen.tuple_id, chosen.tuple_id, chosen.status, latest);

  const triggerNotes: Note[] = (card.triage.flags ?? [])
    .filter((f) => ["data_inconsistent", "annoyed_before", "service_critical"].includes(f.id) && f.detail)
    .map((f) => ({
      id: `flag-${f.id}`,
      role: "system" as const,
      author: f.label ?? human(f.id),
      text: f.detail,
    }));
  const engineNote: Note = {
    id: "engine",
    role: "engine",
    author: "NBA engine",
    date: card.meta?.eval_time,
    text: isNoAction ? "No contact now" : chosen.service_mode ? "Resolve the service issue first" : `#1 of ${allOptions.length} by expected ΔCLV`,
  };
  const extra = allOptions.length - options.length;

  return (
    <Canvas>
      <div>
        {/* before */}
        {hidden > 0 && (
          <Row>
            <button
              type="button"
              onClick={() => setShowAllHistory(true)}
              className="rounded-full bg-white px-2.5 py-0.5 text-[11px] text-neutral-500 ring-1 ring-neutral-200 transition-colors duration-150 hover:text-neutral-900"
            >
              {hidden} earlier
            </button>
          </Row>
        )}
        {shownHistory.map((h) => (
          <Row key={h.id} notes={h.notes}>
            <Pill
              icon={h.icon}
              date={h.date}
              dashed={h.outcome === "not_taken"}
              label={
                <span className="inline-flex min-w-0 items-center gap-1.5">
                  <span className="truncate">{h.title}</span>
                  {h.channel &&
                    (() => {
                      const Ch = CHANNEL_ICON[h.channel];
                      return Ch ? <Ch size={12} className="shrink-0 text-neutral-400" aria-label={CHANNEL_LABEL[h.channel] ?? h.channel} /> : null;
                    })()}
                </span>
              }
              mark={<OutcomeMark outcome={h.outcome} label={h.outcomeLabel} />}
              explain={h.facts.map(([k, v]) => (
                <Fact key={k} k={k}>
                  {v}
                </Fact>
              ))}
            />
          </Row>
        ))}

        {/* now */}
        <Row notes={triggerNotes}>
          <Pill
            icon={Zap}
            tone="trigger"
            date="Now"
            label={signals.length ? `${signals.length} signal${signals.length === 1 ? "" : "s"}` : "No trigger signal"}
            explain={
              signals.length ? (
                <div className="flex flex-col items-start gap-1">
                  {signals.map((s) => (
                    <span key={s.id} className={!selSignals.length || selSignals.some((x) => x.id === s.id) ? "" : "opacity-40"}>
                      <SignalChip sig={s} />
                    </span>
                  ))}
                </div>
              ) : (
                <p>Only generic catalog offers are possible.</p>
              )
            }
            width="max-w-[220px]"
          />
        </Row>

        <Row>
          <Branches card={card} options={options} selected={selected} onSelect={setSelected} />
          {(extra > 0 || blocked.length > 0) && (
            <div className="flex items-center gap-2 text-[11px] text-neutral-400">
              {extra > 0 && (
                <button type="button" onClick={() => setShowAllOptions(true)} className="rounded px-1 text-accent-600 hover:text-accent-700">
                  +{extra} more
                </button>
              )}
              {blocked.length > 0 && (
                <span title={blocked.map((b) => `${b.rule_id}: ${b.reason}`).join("\n")}>{blocked.length} blocked by rules</span>
              )}
            </div>
          )}
        </Row>

        {/* decision */}
        <Row notes={[engineNote, ...mine.map(decisionNote)]} last={!next}>
          <div className="flex w-full max-w-[440px] flex-col items-center">
            <div className="w-full rounded-xl bg-white px-4 py-3.5 shadow-sm ring-2 ring-accent-500">
              <div className="mb-3 flex items-center gap-2 text-[13px]">
                <Stamp size={14} className="shrink-0 text-neutral-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate font-medium">
                  {sel.tuple === "NO_ACTION" ? "Do not contact" : (sel.cand?.offer_name ?? tupleLabel(sel.tuple))}
                  {!followingTop && <span className="ml-1.5 text-[11px] font-normal text-accent-700">override</span>}
                </span>
                <StatusChip status={status.status} label={status.label} />
              </div>
              {sel.tuple === "NO_ACTION" ? (
                <p className="text-xs text-neutral-500">Nothing to send. Pick a branch above to override.</p>
              ) : followingTop ? (
                <DecisionBar key={sel.tuple} card={card} variant="top" candidate={sel.cand} allowOverride={false} />
              ) : sel.cand ? (
                <DecisionBar key={sel.tuple} card={card} variant="alternative" candidate={sel.cand} />
              ) : (
                <p className="text-xs text-neutral-500">Not a gated candidate; cannot be selected.</p>
              )}
              {followingTop && chosen.content?.body && (
                <details className="mt-2 text-[11px] text-neutral-500">
                  <summary className="cursor-pointer select-none hover:text-neutral-800">Message preview</summary>
                  <div className="mt-1 rounded-md bg-neutral-50 p-2 text-neutral-700">
                    {chosen.content.subject && <div className="font-medium">{chosen.content.subject}</div>}
                    {chosen.content.body}
                  </div>
                </details>
              )}
            </div>
          </div>
        </Row>

        {next && (
          <Row last>
            <Pill icon={CalendarClock} date={next.date} dashed label={next.title} explain={<Fact k="Source">{next.src}</Fact>} />
          </Row>
        )}
      </div>
    </Canvas>
  );
}
