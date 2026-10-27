import { useState, type ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  Check,
  ChevronDown,
  Mail,
  MessageCircle,
  MessageSquare,
  Monitor,
  Phone,
  Smartphone,
  TrendingUp,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";
import { OFFER_NAME } from "../worklist/model";
import { channelLabel } from "../nba/ui";
import { mockName } from "../../lib/customerMock";
import { useLoad } from "../../lib/data";
import { eur } from "../../lib/format";
import { loadLearnImpact, type LearnChange, type LearnImpact } from "../../lib/kb";

// Knowledge Base "Learning", for a non-technical reader. Everything is sorted into three verdicts with one colour
// each: Kept (the old belief held), Learned (something works better than we thought), Mistake fixed (we overrated
// something, or the customer pushed back). Each changed decision is a card; the side panel shows it as a value
// race: what the old and the new offer are worth before and after learning. Numbers come from nba/learn/impact.py (GET /api/learn/impact).

type Verdict = "kept" | "better" | "mistake";

const VERDICT: Record<Verdict, { label: string; hint: string; icon: LucideIcon; dot: string; bar: string }> = {
  kept: { label: "Kept", hint: "Recommendation confirmed, nothing to change", icon: Check, dot: "bg-neutral-100 text-neutral-500", bar: "bg-neutral-300" },
  better: { label: "Learned", hint: "An offer works better than we thought", icon: TrendingUp, dot: "bg-accent-50 text-accent-600", bar: "bg-accent-500" },
  mistake: { label: "Mistake fixed", hint: "We overrated an offer, or the customer pushed back", icon: X, dot: "bg-red-50 text-red-600", bar: "bg-red-400" },
};

const CHANNEL_ICON: Record<string, LucideIcon> = {
  email: Mail,
  newsletter_email: Mail,
  app_push: Smartphone,
  sms: MessageSquare,
  outbound_call: Phone,
  portal_popup: Monitor,
};

const SHADOW = "shadow-[0_10px_30px_-16px_rgba(0,0,0,0.18)]";
const CARD = `rounded-3xl bg-white ${SHADOW}`;
const PAGE = 6;

const day = (s: string) => new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const none = (t: string) => !t || t === "NO_ACTION";
const offerOf = (t: string) => (none(t) ? "no offer" : (OFFER_NAME[t.split("|")[0]] ?? t.split("|")[0]));
const channelOf = (t: string) => (none(t) ? "" : channelLabel(t.split("|")[1]));
const paused = (c: LearnChange) => c.before.tuple === c.after.tuple && !!c.after.waits_until;

/** Learned when the old pick kept its value and a new one rose past it; otherwise the old pick was overrated. */
function verdictOf(c: LearnChange): Exclude<Verdict, "kept"> {
  if (c.cause === "memory") return "mistake";
  const was = c.before.delta_clv;
  const now = c.before_now?.tuple === c.before.tuple ? c.before_now.delta_clv : null;
  return was != null && now != null && Math.abs(now - was) < 1e-6 ? "better" : "mistake";
}

const said = (c: LearnChange) => c.sentence.match(/\(([^)]+)\)/)?.[1] ?? "not now";

/** What happened, in one sentence. */
function storyLine(c: LearnChange): string {
  const old = offerOf(c.before.tuple);
  const next = none(c.after.tuple) ? "we send nothing for now" : `${offerOf(c.after.tuple)} is now the better pick`;
  if (c.cause === "memory") {
    return paused(c)
      ? `The customer said “${said(c)}”, so we hold off on ${old} until ${day(c.after.waits_until!)}.`
      : `The customer said “${said(c)}” about ${old}, so we switch to ${offerOf(c.after.tuple)}.`;
  }
  if (verdictOf(c) === "better") return `Customers like this one bought ${offerOf(c.after.tuple)}, so it now beats ${old}.`;
  const n = c.before_now ?? {};
  if (n.lift != null && n.lift < 1) return `Customers like this one didn't buy ${old}, so ${next}.`;
  if (n.k != null && n.k < 1) return `${old} by ${channelOf(c.before.tuple).toLowerCase()} sold less than we predicted, so ${next}.`;
  return `${old} by ${channelOf(c.before.tuple).toLowerCase()} is no longer worth it, so ${next}.`;
}

function title(c: LearnChange): ReactNode {
  if (paused(c)) return <>{offerOf(c.before.tuple)} <span className="font-normal text-neutral-500">on hold until {day(c.after.waits_until!)}</span></>;
  return (
    <>
      <span className="font-normal text-neutral-400 line-through decoration-neutral-300">{offerOf(c.before.tuple)}</span>
      <ArrowRight size={14} className="mx-1.5 inline text-neutral-400" aria-hidden />
      {none(c.after.tuple) ? "No offer" : offerOf(c.after.tuple)}
    </>
  );
}

/** How far the expected value moved: used to sort the biggest changes first. */
const size = (c: LearnChange) => Math.abs((c.before.delta_clv ?? 0) - (c.before_now?.delta_clv ?? c.after.delta_clv ?? 0));

function Round({ icon: Icon, cls, big = false }: { icon: LucideIcon; cls: string; big?: boolean }) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-full ${cls} ${big ? "size-14" : "size-12"}`}>
      <Icon size={big ? 24 : 20} aria-hidden />
    </span>
  );
}

function Scoreboard({ counts, total }: { counts: Record<Verdict, number>; total: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {(["kept", "better", "mistake"] as const).map((v) => {
        const V = VERDICT[v];
        return (
          <div key={v} className={`${CARD} flex items-center gap-4 p-5`}>
            <Round icon={V.icon} cls={V.dot} big />
            <div className="min-w-0">
              <p className="text-3xl font-semibold tabular-nums text-neutral-900">
                {counts[v]}
                <span className="ml-2 text-[15px] font-semibold">{V.label}</span>
              </p>
              <p className="text-[13px] text-neutral-500">{V.hint}</p>
              <div className="mt-2 h-1.5 rounded-full bg-neutral-100">
                <div className={`h-1.5 rounded-full ${V.bar}`} style={{ width: `${(counts[v] / Math.max(total, 1)) * 100}%`, minWidth: counts[v] ? 6 : 0 }} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The selected change as a value race: what each option was worth before learning and now; the higher one wins. */
function Race({ c, demo }: { c: LearnChange; demo: Set<string> }) {
  const v = verdictOf(c);
  const oldNow = c.before_now?.tuple === c.before.tuple ? (c.before_now?.delta_clv ?? null) : null;
  const oldNote = paused(c) ? `on hold until ${day(c.after.waits_until!)}` : c.cause === "memory" ? "held back by the customer" : "too low to send";
  const rows: { tuple: string; before: number | null; now: number | null; note?: string; chosen: boolean }[] = [
    { tuple: c.before.tuple, before: c.before.delta_clv, now: oldNow, note: oldNow == null ? oldNote : undefined, chosen: false },
  ];
  if (!paused(c)) {
    rows.push(
      none(c.after.tuple)
        ? { tuple: c.after.tuple, before: null, now: null, note: "nothing else is worth sending", chosen: true }
        : { tuple: c.after.tuple, before: c.winner_before?.tuple === c.after.tuple ? (c.winner_before?.delta_clv ?? null) : null, now: c.after.delta_clv, chosen: true },
    );
  }
  const max = Math.max(...rows.flatMap((r) => [r.before ?? 0, r.now ?? 0]), 0.01);
  const w = (x: number) => `${Math.max((x / max) * 100, 2)}%`;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-[12px] text-neutral-500">
        <span>Worth for this customer</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1"><span className="h-2 w-3 rounded-full bg-neutral-200" />before</span>
          <span className="flex items-center gap-1"><span className="h-2 w-3 rounded-full bg-neutral-700" />now</span>
        </span>
      </div>
      <ul className="space-y-5">
        {rows.map((r) => {
          const Icon = none(r.tuple) ? Check : (CHANNEL_ICON[r.tuple.split("|")[1]] ?? Mail);
          const dropped = !r.chosen && (r.now == null || (r.before != null && r.now < r.before - 1e-6));
          const fill = r.chosen ? VERDICT.better.bar : dropped ? VERDICT.mistake.bar : "bg-neutral-500";
          return (
            <li key={`${r.tuple}:${r.chosen}`}>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className={`flex min-w-0 items-center gap-1.5 text-[14px] ${r.chosen ? "font-semibold text-neutral-900" : "text-neutral-600"}`}>
                  {!none(r.tuple) && <Icon size={14} className="shrink-0 text-neutral-400" aria-hidden />}
                  <span className="truncate">{none(r.tuple) ? "No offer" : offerOf(r.tuple)}</span>
                  {!none(r.tuple) && <span className="truncate text-[12px] font-normal text-neutral-400">· {channelOf(r.tuple)}</span>}
                </span>
                {r.chosen ? (
                  <span className="shrink-0 rounded-full bg-neutral-900 px-2 py-0.5 text-[11px] font-medium text-white">Chosen now</span>
                ) : (
                  <span className="shrink-0 rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-medium text-neutral-500">Old pick</span>
                )}
              </div>
              <div className="space-y-1">
                {r.before != null && (
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 flex-1"><span className="block h-2.5 rounded-full bg-neutral-200" style={{ width: w(r.before) }} /></span>
                    <span className="w-14 text-right text-[12px] tabular-nums text-neutral-400">{eur(r.before, true)}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="h-3.5 flex-1">
                    {r.now != null ? (
                      <span className={`block h-3.5 rounded-full ${fill}`} style={{ width: w(r.now) }} />
                    ) : (
                      <span className="flex h-3.5 items-center gap-1.5 text-[12px] text-red-700">
                        {!r.chosen && <X size={12} aria-hidden />}
                        <span className={r.chosen ? "text-neutral-500" : ""}>{r.note}</span>
                      </span>
                    )}
                  </span>
                  <span className="w-14 text-right text-[13px] font-medium tabular-nums text-neutral-900">{r.now != null ? eur(r.now, true) : ""}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-6 border-t border-neutral-100 pt-4">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-neutral-900">
          <span className={`grid size-6 place-items-center rounded-full ${VERDICT[v].dot}`}>
            {(() => {
              const I = VERDICT[v].icon;
              return <I size={12} aria-hidden />;
            })()}
          </span>
          {VERDICT[v].label}
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-neutral-600">{storyLine(c)}</p>
      </div>
      <Link
        to={demo.has(c.customer_id) ? `/kb?view=customer&c=${c.customer_id}` : `/customer/${c.customer_id}`}
        className="mt-4 inline-flex items-center gap-1 rounded-full border border-neutral-300 px-3 py-1.5 text-[13px] font-medium text-neutral-800 hover:bg-neutral-50"
      >
        {demo.has(c.customer_id) ? "Open the decision tree" : "Open the customer"} <ArrowRight size={12} aria-hidden />
      </Link>
    </div>
  );
}

/** Predicted vs actually sold as a tally of whole people, dots packed side by side: grey = a buyer we predicted who
 *  bought, blue = an extra buyer we did not predict, red ring = a predicted buyer who never came. The prediction is
 *  rounded to whole people; the exact figure is in the tooltip. */
function BuyerDots({ rows }: { rows: LearnImpact["k"] }) {
  const tally = rows
    .map((r) => {
      const expected = Math.round(r.expected);
      return { r, kept: Math.min(expected, r.bought), extra: Math.max(r.bought - expected, 0), missing: Math.max(expected - r.bought, 0) };
    })
    .sort((a, b) => b.missing - a.missing || a.extra - b.extra);
  const groups: { v: Exclude<Verdict, "kept">; label: string; rows: typeof tally }[] = [
    { v: "mistake", label: "Fewer buyers than we predicted", rows: tally.filter((t) => t.missing > 0) },
    { v: "better", label: "More buyers than we predicted", rows: tally.filter((t) => t.missing === 0) },
  ];
  const dots = (n: number, cls: string) => Array.from({ length: n }, (_, i) => <span key={i} className={`size-3 shrink-0 rounded-full ${cls}`} />);
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[12px] text-neutral-500">
        <span className="flex items-center gap-1.5"><span className="size-3 rounded-full bg-neutral-300" /> predicted, and bought</span>
        <span className="flex items-center gap-1.5"><span className="size-3 rounded-full bg-accent-500" /> extra buyer</span>
        <span className="flex items-center gap-1.5"><span className="size-3 rounded-full border-2 border-red-400" /> predicted, never came</span>
      </div>
      <div className="space-y-5">
        {groups
          .filter((g) => g.rows.length)
          .map((g) => {
            const V = VERDICT[g.v];
            return (
              <div key={g.v}>
                <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-neutral-900">
                  <span className={`grid size-6 place-items-center rounded-full ${V.dot}`}>
                    <V.icon size={12} aria-hidden />
                  </span>
                  {g.label}
                </p>
                <ul className="space-y-1">
                  {g.rows.map(({ r, kept, extra, missing }) => {
                    const Icon = CHANNEL_ICON[r.channel] ?? Mail;
                    return (
                      <li
                        key={`${r.offer}|${r.channel}|${r.tone}`}
                        className="grid grid-cols-[minmax(0,15rem)_minmax(0,1fr)_6rem] items-center gap-3 rounded-lg px-1 py-1.5 text-[13px] hover:bg-neutral-50"
                        title={`Sent to ${r.sends} customers. We predicted about ${r.expected.toFixed(1)} would buy; ${r.bought} did.`}
                      >
                        <span className="flex min-w-0 items-center gap-1.5 text-neutral-800">
                          <Icon size={13} className="shrink-0 text-neutral-400" aria-hidden />
                          <span className="truncate">{OFFER_NAME[r.offer] ?? r.offer}</span>
                          <span className="truncate text-neutral-400">· {channelLabel(r.channel)}</span>
                        </span>
                        <span className="flex flex-wrap items-center gap-1">
                          {dots(kept, "bg-neutral-300")}
                          {dots(extra, "bg-accent-500")}
                          {dots(missing, "border-2 border-red-400")}
                        </span>
                        <span className={`text-right font-medium tabular-nums ${missing ? "text-red-700" : "text-accent-700"}`}>
                          {missing ? `${missing} missing` : extra ? `+${extra} extra` : "as predicted"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
      </div>
    </div>
  );
}

const MEMORY_KIND: Record<string, string> = { pause_offer: "Stop this offer for a while", pause_sales: "Stop all selling for a while" };

type LookalikeOffer = LearnImpact["lookalike"]["offers"][number];

/** A profile value in plain units: euros without cents, churn as a percentage, other numbers trimmed. */
function trait(feature: string, label: string, v: number): string {
  if (label.includes("€")) return eur(v);
  if (feature === "churn_prob_12m") return `${Math.round(v * 100)}%`;
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

/** One offer: who bought it (traits vs the other recipients), then how the rest of the customers moved. */
function Lookalike({ o }: { o: LookalikeOffer }) {
  const scored = o.scored ?? o.more_likely + o.less_likely;
  const same = Math.max(scored - o.more_likely - o.less_likely, 0);
  const seg = [
    { n: o.more_likely, cls: VERDICT.better.bar, label: "look like buyers: more likely to get it", text: "text-accent-700" },
    { n: same, cls: "bg-neutral-200", label: "no clear match: unchanged", text: "text-neutral-500" },
    { n: o.less_likely, cls: VERDICT.mistake.bar, label: "look like non-buyers: less likely", text: "text-red-700" },
  ].filter((x) => x.n > 0);
  return (
    <div className="rounded-2xl bg-neutral-50 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[14px] font-semibold text-neutral-900">{o.name}</p>
        <p className="text-[12px] tabular-nums text-neutral-500">{o.buyers} of {o.recipients} bought</p>
      </div>
      {o.profile && o.profile.length > 0 && (
        <>
          <p className="mt-3 text-[12px] text-neutral-500">Compared with people who didn't buy, buyers have</p>
          <ul className="mt-1.5 space-y-1.5">
            {o.profile.map((p) => {
              const up = p.buyers > p.others;
              return (
                <li key={p.feature} className="flex items-center justify-between gap-2 text-[13px]">
                  <span className="flex items-center gap-1.5 text-neutral-800">
                    <span className={`grid size-5 place-items-center rounded-full text-[10px] ${up ? "bg-neutral-200 text-neutral-700" : "bg-white text-neutral-500 ring-1 ring-neutral-200"}`}>{up ? "▲" : "▼"}</span>
                    {up ? "higher" : "lower"} {p.label.replace(/\s*€$/, "")}
                  </span>
                  <span className="tabular-nums text-neutral-500">
                    <span className="font-medium text-neutral-900">{trait(p.feature, p.label, p.buyers)}</span> vs {trait(p.feature, p.label, p.others)}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
      <p className="mt-4 text-[12px] text-neutral-500">So, of {scored} customers we can compare</p>
      <div className="mt-1.5 flex h-3 overflow-hidden rounded-full">
        {seg.map((x) => (
          <span key={x.label} className={x.cls} style={{ width: `${(x.n / Math.max(scored, 1)) * 100}%` }} title={`${x.n} ${x.label}`} />
        ))}
      </div>
      <ul className="mt-2 space-y-0.5 text-[12px]">
        {seg.map((x) => (
          <li key={x.label} className="flex items-center gap-1.5 text-neutral-600">
            <span className={`size-2 rounded-full ${x.cls}`} />
            <span className={`font-medium tabular-nums ${x.text}`}>{x.n}</span> {x.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Evidence({ d }: { d: LearnImpact }) {
  const kinds = Object.entries(d.memory.by_kind).sort((a, b) => b[1] - a[1]);
  const maxKind = Math.max(...kinds.map(([, n]) => n), 1);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <section className={`${CARD} p-6`}>
        <div className="mb-5 flex items-start gap-4">
          <Round icon={BarChart3} cls="bg-neutral-100 text-neutral-700" />
          <div>
            <h3 className="text-[15px] font-semibold text-neutral-900">What we predicted vs what really sold</h3>
            <p className="text-[13px] text-neutral-500">How many people we expected to buy, and how many really did</p>
          </div>
        </div>
        {d.k.length ? <BuyerDots rows={d.k} /> : <p className="text-[13px] text-neutral-500">No sales results yet.</p>}
        {d.lookalike.active && d.lookalike.offers.length > 0 && (
          <div className="mt-6 border-t border-neutral-100 pt-5">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-neutral-900">
              <Users size={14} className="text-neutral-400" aria-hidden /> Who buys it, and who looks like them
            </p>
            <p className="mb-4 text-[12px] text-neutral-500">For offers that worked, we learn what the buyers have in common and favour customers who look like them.</p>
            <div className="grid gap-4 md:grid-cols-2">
              {d.lookalike.offers.map((o) => (
                <Lookalike key={o.offer} o={o} />
              ))}
            </div>
          </div>
        )}
      </section>

      <section className={`${CARD} p-6`}>
        <div className="mb-5 flex items-start gap-4">
          <Round icon={MessageCircle} cls="bg-red-50 text-red-600" />
          <div>
            <h3 className="text-[15px] font-semibold text-neutral-900">What customers told us</h3>
            <p className="text-[13px] text-neutral-500">Agents note when a customer is upset or not interested</p>
          </div>
        </div>
        {d.memory.entries === 0 ? (
          <p className="rounded-2xl bg-neutral-50 px-4 py-6 text-center text-[13px] text-neutral-500">No notes from customers yet.</p>
        ) : (
          <>
            <p className="text-[13px] text-neutral-600">
              <span className="mr-1.5 text-3xl font-semibold tabular-nums text-neutral-900">{d.memory.entries}</span>
              notes · {d.memory.active} still in force
            </p>
            <ul className="mt-5 space-y-3">
              {kinds.map(([k, n]) => (
                <li key={k} className="text-[13px]">
                  <div className="flex justify-between text-neutral-700">
                    <span>{MEMORY_KIND[k] ?? k.replace(/_/g, " ")}</span>
                    <span className="tabular-nums text-neutral-500">{n}</span>
                  </div>
                  <div className="mt-1 h-2.5 rounded-full bg-neutral-100">
                    <div className={`h-2.5 rounded-full ${VERDICT.mistake.bar}`} style={{ width: `${(n / maxKind) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}

export default function LearningView({ demo }: { demo: Set<string> }) {
  const data = useLoad(loadLearnImpact, []);
  const [filter, setFilter] = useState<Verdict | "all">("all");
  const [sort, setSort] = useState<"size" | "name">("size");
  const [sel, setSel] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE);

  if (data.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading what the system learned…</p>;
  if (data.status === "error") return <p className="text-red-700">Could not load the learning impact: {data.error}</p>;
  const d = data.data;
  const changes = d.changes.map((c) => ({ c, v: verdictOf(c), key: `${c.customer_id}:${c.cause}` }));
  const counts: Record<Verdict, number> = {
    kept: d.summary.customers - d.summary.changed,
    better: changes.filter((x) => x.v === "better").length,
    mistake: changes.filter((x) => x.v === "mistake").length,
  };
  const shown = changes
    .filter((x) => filter === "all" || x.v === filter)
    .sort((a, b) => (sort === "size" ? size(b.c) - size(a.c) : mockName(a.c.customer_id).localeCompare(mockName(b.c.customer_id))));
  const list = shown.slice(0, limit);
  const picked = shown.find((x) => x.key === sel) ?? shown[0] ?? null;

  return (
    <div className="space-y-6">
      <Scoreboard counts={counts} total={d.summary.customers} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-[14px] text-neutral-600">
              <span className="font-semibold text-neutral-900">{d.summary.changed} recommendations changed</span> · the other {counts.kept} were kept
            </p>
            <div className="flex flex-wrap gap-2">
              {(["all", "better", "mistake"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => {
                    setFilter(k);
                    setLimit(PAGE);
                  }}
                  className={`rounded-xl border px-3 py-1.5 text-sm transition-colors duration-150 ${
                    filter === k ? "border-neutral-900 bg-neutral-900 text-white" : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50"
                  }`}
                >
                  {k === "all" ? "All" : VERDICT[k].label} <span className="tabular-nums opacity-60">{k === "all" ? changes.length : counts[k]}</span>
                </button>
              ))}
              <label className="relative">
                <span className="sr-only">Sort</span>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as "size" | "name")}
                  className="appearance-none rounded-xl border border-neutral-300 bg-white py-1.5 pl-3 pr-8 text-sm text-neutral-700 hover:bg-neutral-50"
                >
                  <option value="size">Biggest change first</option>
                  <option value="name">Customer A–Z</option>
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-neutral-500" aria-hidden />
              </label>
            </div>
          </div>

          <ul className="relative space-y-4 pb-5">
            {list.map(({ c, v, key }) => {
              const on = picked?.key === key;
              const V = VERDICT[v];
              const Icon = CHANNEL_ICON[(paused(c) ? c.before : c.after).tuple.split("|")[1]] ?? Mail;
              return (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => setSel(key)}
                    className={`${CARD} flex w-full items-start gap-5 p-5 text-left transition duration-150 hover:-translate-y-0.5 ${on ? "ring-2 ring-neutral-900" : ""}`}
                  >
                    <Round icon={V.icon} cls={V.dot} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                        <p className="text-[15px] font-semibold text-neutral-900">{title(c)}</p>
                        <p className="flex items-center gap-1 text-[12px] text-neutral-500">
                          {mockName(c.customer_id)} · <Icon size={12} aria-hidden /> {channelOf((paused(c) ? c.before : c.after).tuple) || "no channel"}
                        </p>
                      </div>
                      <p className="mt-1 text-[13px] leading-relaxed text-neutral-600">{storyLine(c)}</p>
                    </div>
                  </button>
                  {on && (
                    <div className={`${CARD} mt-2 p-5 xl:hidden`}>
                      <Race c={c} demo={demo} />
                    </div>
                  )}
                </li>
              );
            })}
            {shown.length > limit && (
              <li className="absolute inset-x-0 bottom-0 flex justify-center">
                <button
                  type="button"
                  onClick={() => setLimit((n) => n + PAGE * 2)}
                  className="rounded-full bg-neutral-900 px-5 py-2 text-sm font-medium text-white shadow-lg hover:bg-neutral-800"
                >
                  {shown.length - limit} more
                </button>
              </li>
            )}
          </ul>
        </section>

        <aside className={`${CARD} hidden h-fit p-6 xl:sticky xl:top-20 xl:block`}>
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-[17px] font-semibold text-neutral-900">Why it changed</h3>
              <div className="mt-1 h-0.5 w-6 rounded-full bg-neutral-300" />
            </div>
            {picked && <span className="rounded-full border border-neutral-300 px-3 py-1 text-[13px] font-medium text-neutral-800">{mockName(picked.c.customer_id)}</span>}
          </div>
          {picked ? <Race c={picked.c} demo={demo} /> : <p className="text-sm text-neutral-500">Nothing changed.</p>}
        </aside>
      </div>

      <Evidence d={d} />
    </div>
  );
}
