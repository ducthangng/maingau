import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import CustomerModal from "../components/customer/CustomerModal";
import ExecutePanel from "../components/worklist/ExecutePanel";
import KpiStrip from "../components/worklist/KpiStrip";
import Toolbar from "../components/worklist/Toolbar";
import WorklistTable from "../components/worklist/WorklistTable";
import {
  EMPTY_FILTERS,
  FILTER_KEYS,
  VIEWS,
  filterOptions,
  groupRows,
  isActionable,
  matches,
  queueOf,
  sortRows,
  type QueueId,
  type Filters,
  type ViewId,
} from "../components/worklist/model";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { decideRow, latestByCustomer, useDecisions } from "../lib/decisions";
import { useHardRules, violation } from "../lib/hardRules";

// Remembered across in-app navigation so "back to the worklist" keeps the keyboard position.
let lastHighlighted: string | null = null;

const FILTER_FIELDS = ["q", ...FILTER_KEYS] as const;

// "All" lists what needs a decision first, then what is decided, then who must not be contacted;
// inside each part the engine's ranking (tier, then urgency score) is kept.
const QUEUE_RANK = { todo: 0, done: 1, hold: 2 } as const;

function isTyping(el: HTMLElement | null): boolean {
  if (!el) return false;
  if (el.hasAttribute("data-worklist-search")) return false;
  return el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA" || el.isContentEditable;
}

/** Home screen: ranked worklist with KPIs, filters, saved views and group-by (prompts/agent-cards.md §1.1). */
export default function Worklist() {
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : null;
  const decisions = useDecisions();
  const rules = useHardRules();
  const latest = useMemo(() => latestByCustomer(decisions), [decisions]);
  const navigate = useNavigate();
  const searchRef = useRef<HTMLInputElement>(null);

  // View state lives in the URL, so the browser's back button restores it.
  const [params, setParams] = useSearchParams();
  const filters: Filters = useMemo(() => {
    const f = { ...EMPTY_FILTERS };
    for (const k of FILTER_FIELDS) f[k] = params.get(k) ?? "";
    return f;
  }, [params]);
  const view = (VIEWS.some((v) => v.id === params.get("view")) ? params.get("view") : "all") as ViewId;
  const groupBy = params.get("group") === "1";
  const queue = (["todo", "done", "hold", "all"].includes(params.get("queue") ?? "") ? params.get("queue") : "todo") as QueueId;

  const update = useCallback(
    (patch: Record<string, string | null>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(patch)) {
            if (v) next.set(k, v);
            else next.delete(k);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const all = useMemo(() => (index.status === "ready" ? sortRows(index.data) : []), [index]);
  const options = useMemo(() => filterOptions(all), [all]);
  const viewCounts = useMemo(() => Object.fromEntries(VIEWS.map((v) => [v.id, all.filter(v.test).length])) as Record<ViewId, number>, [all]);
  // Rows decided in this session stay in "To review" (dimmed) until the queue changes, so a row never
  // jumps away under the cursor right after a click.
  const [recent, setRecent] = useState<Set<string>>(new Set());
  const known = useRef<Set<string> | null>(null);
  useEffect(() => setRecent(new Set()), [queue]);
  useEffect(() => {
    if (!known.current) {
      known.current = new Set(latest.keys());
      return;
    }
    const added = [...latest.keys()].filter((id) => !known.current!.has(id));
    if (!added.length) return;
    added.forEach((id) => known.current!.add(id));
    setRecent((cur) => new Set([...cur, ...added]));
  }, [latest]);

  const filtered = useMemo(() => {
    const test = VIEWS.find((v) => v.id === view)?.test ?? (() => true);
    return all.filter((r) => test(r) && matches(r, filters));
  }, [all, view, filters]);
  const queueCounts = useMemo(() => {
    const c: Record<QueueId, number> = { todo: 0, done: 0, hold: 0, all: filtered.length };
    for (const r of filtered) c[queueOf(r, latest.has(r.customer_id))] += 1;
    return c;
  }, [filtered, latest]);
  const visible = useMemo(
    () =>
      queue === "all"
        ? [...filtered].sort((a, b) => QUEUE_RANK[queueOf(a, latest.has(a.customer_id))] - QUEUE_RANK[queueOf(b, latest.has(b.customer_id))])
        : filtered.filter((r) => {
            const q = queueOf(r, latest.has(r.customer_id));
            return q === queue || (queue === "todo" && q === "done" && recent.has(r.customer_id));
          }),
    [filtered, queue, latest, recent],
  );
  // One bar scale and one p reference for the whole snapshot (display only: max and median of the JSON values).
  const scale = useMemo(() => {
    const d = all.filter(isActionable).map((r) => Math.abs(r.delta_clv ?? 0));
    const p = all
      .filter(isActionable)
      .map((r) => r.p_accept)
      .filter((v): v is number => typeof v === "number")
      .sort((a, b) => a - b);
    return { max: Math.max(1, ...d), median: p.length ? p[Math.floor(p.length / 2)] : null };
  }, [all]);
  const groups = useMemo(() => (groupBy ? groupRows(visible) : null), [groupBy, visible]);
  const order = useMemo(() => (groups ? groups.flatMap((g) => g.rows) : visible), [groups, visible]);

  const activeFilters = (view !== "all" ? 1 : 0) + FILTER_KEYS.filter((k) => filters[k] !== "").length;
  const dirty = activeFilters > 0 || filters.q !== "";
  const [showFilters, setShowFilters] = useState(activeFilters > 0);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const clear = useCallback(() => update(Object.fromEntries([...FILTER_FIELDS, "view"].map((k) => [k, null]))), [update]);

  const [highlighted, setHighlighted] = useState<string | null>(lastHighlighted);
  useEffect(() => {
    lastHighlighted = highlighted;
  }, [highlighted]);

  // The customer pop-up lives in the URL (?c=ID): Back closes it, and a link can open it directly.
  const selected = params.get("c");
  const openedHere = useRef(false);
  const open = useCallback(
    (id: string) => {
      setHighlighted(id);
      openedHere.current = true;
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("c", id);
        return next;
      });
    },
    [setParams],
  );
  const close = useCallback(() => {
    if (openedHere.current) {
      openedHere.current = false;
      navigate(-1);
    } else update({ c: null });
  }, [navigate, update]);

  // ↑/↓ move the highlighted row, Enter opens it, "/" jumps to search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (selected || rejecting || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const target = e.target instanceof HTMLElement ? e.target : null;
      if (isTyping(target)) return;
      const inSearch = !!target?.hasAttribute("data-worklist-search");

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!order.length) return;
        e.preventDefault();
        const i = order.findIndex((r) => r.customer_id === highlighted);
        const next = i < 0 ? 0 : e.key === "ArrowDown" ? Math.min(i + 1, order.length - 1) : Math.max(i - 1, 0);
        const id = order[next].customer_id;
        setHighlighted(id);
        requestAnimationFrame(() => document.querySelector(`[data-row-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" }));
      } else if (e.key === "Enter") {
        // Let buttons and links handle their own Enter.
        if (target && !inSearch && (target.tagName === "BUTTON" || target.tagName === "A")) return;
        const id = highlighted && order.some((r) => r.customer_id === highlighted) ? highlighted : inSearch ? order[0]?.customer_id : null;
        if (!id) return;
        e.preventDefault();
        open(id);
      } else if ((e.key === "a" || e.key === "r") && !inSearch && highlighted) {
        const row = order.find((r) => r.customer_id === highlighted);
        if (!row || !isActionable(row) || latest.has(row.customer_id)) return;
        const today = (summary?.eval_time ?? new Date().toISOString()).slice(0, 10);
        if (violation(rules, { customer_id: row.customer_id, archetype: row.archetype }, { offer: row.chosen_offer, channel: row.channel }, today))
          return;
        e.preventDefault();
        if (e.key === "a") decideRow(row, "approved");
        else setRejecting(row.customer_id);
      } else if (e.key === "/" && !inSearch) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [order, highlighted, open, selected, rejecting, latest, rules, summary]);

  if (index.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading worklist…</p>;
  if (index.status === "error")
    return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">Could not load the worklist: {index.error}</div>;

  const kbd = "rounded border border-neutral-200 bg-white px-1 font-sans";
  const empty =
    queue === "todo" && !dirty ? (
      <p>Nothing left to review. Every proposal has a decision.</p>
    ) : (
      <>
        <p>No customers match this view.</p>
        {dirty && (
          <button
            type="button"
            onClick={clear}
            className="mt-3 rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white transition-colors duration-150 hover:bg-neutral-700"
          >
            Clear filters
          </button>
        )}
      </>
    );

  return (
    // Two jobs, side by side: review case by case on the left, execute reviewed cases group by group on the right.
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="min-w-0 space-y-6" aria-label="Review">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Review</h1>
            <p className="mt-0.5 text-sm text-neutral-500">One case at a time: approve, or expand to change it.</p>
          </div>
          <p className="text-xs text-neutral-400">
            <kbd className={kbd}>↑</kbd> <kbd className={kbd}>↓</kbd> move · <kbd className={kbd}>A</kbd> approve · <kbd className={kbd}>R</kbd>{" "}
            reject · <kbd className={kbd}>Enter</kbd> open · <kbd className={kbd}>/</kbd> search
          </p>
        </div>

        <KpiStrip
          rows={all}
          summary={summary}
          decisions={latest}
          onQueue={(q) => update({ queue: q === "todo" ? null : q })}
          onOutliers={() => update({ queue: null, view: "outliers" })}
          onService={() => update({ queue: null, mode: "service" })}
        />

        <Toolbar
          queue={queue}
          queueCounts={queueCounts}
          onQueue={(q) => update({ queue: q === "todo" ? null : q })}
          filters={filters}
          options={options}
          onFilter={(k, v) => update({ [k]: v })}
          view={view}
          viewCounts={viewCounts}
          onView={(v) => update({ view: v === "all" ? null : v })}
          groupBy={groupBy}
          onGroupBy={(on) => update({ group: on ? "1" : null })}
          onClear={clear}
          activeFilters={activeFilters}
          showFilters={showFilters}
          onShowFilters={setShowFilters}
          shown={visible.length}
          searchRef={searchRef}
        />

        <WorklistTable
          rows={visible}
          groups={groups}
          summary={summary}
          decisions={latest}
          highlightedId={highlighted}
          rejectingId={rejecting}
          scale={scale}
          onOpen={open}
          onReject={setRejecting}
          empty={empty}
        />
      </section>

      <div className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6.5rem)] lg:self-start lg:overflow-y-auto lg:rounded-2xl lg:bg-neutral-100/70 lg:p-5">
        <ExecutePanel decisions={latest} onOpen={open} />
      </div>

      {selected && <CustomerModal key={selected} id={selected} onClose={close} />}
    </div>
  );
}
