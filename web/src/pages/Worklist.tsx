import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import KpiStrip from "../components/worklist/KpiStrip";
import Toolbar from "../components/worklist/Toolbar";
import WorklistTable from "../components/worklist/WorklistTable";
import {
  EMPTY_FILTERS,
  FILTER_KEYS,
  VIEWS,
  filterOptions,
  groupRows,
  matches,
  sortRows,
  type Filters,
  type ViewId,
} from "../components/worklist/model";
import { loadIndex, loadSummary, useLoad } from "../lib/data";
import { latestByCustomer, useDecisions } from "../lib/decisions";

// Remembered across in-app navigation so "back to the worklist" keeps the keyboard position.
let lastHighlighted: string | null = null;

const FILTER_FIELDS = ["q", ...FILTER_KEYS] as const;

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
  const viewCounts = useMemo(
    () => Object.fromEntries(VIEWS.map((v) => [v.id, all.filter(v.test).length])) as Record<ViewId, number>,
    [all],
  );
  const visible = useMemo(() => {
    const test = VIEWS.find((v) => v.id === view)?.test ?? (() => true);
    return all.filter((r) => test(r) && matches(r, filters));
  }, [all, view, filters]);
  const groups = useMemo(() => (groupBy ? groupRows(visible) : null), [groupBy, visible]);
  const order = useMemo(() => (groups ? groups.flatMap((g) => g.rows) : visible), [groups, visible]);

  const dirty = view !== "all" || FILTER_FIELDS.some((k) => filters[k] !== "");
  const clear = useCallback(() => update(Object.fromEntries([...FILTER_FIELDS, "view"].map((k) => [k, null]))), [update]);

  const [highlighted, setHighlighted] = useState<string | null>(lastHighlighted);
  useEffect(() => {
    lastHighlighted = highlighted;
  }, [highlighted]);

  const open = useCallback((id: string) => navigate(`/customer/${id}`), [navigate]);

  // ↑/↓ move the highlighted row, Enter opens it, "/" jumps to search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const target = e.target instanceof HTMLElement ? e.target : null;
      if (isTyping(target)) return;
      const inSearch = !!target?.hasAttribute("data-worklist-search");

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!order.length) return;
        e.preventDefault();
        const i = order.findIndex((r) => r.customer_id === highlighted);
        const next =
          i < 0 ? 0 : e.key === "ArrowDown" ? Math.min(i + 1, order.length - 1) : Math.max(i - 1, 0);
        const id = order[next].customer_id;
        setHighlighted(id);
        requestAnimationFrame(() =>
          document.querySelector(`[data-row-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" }),
        );
      } else if (e.key === "Enter") {
        // Let buttons and links handle their own Enter.
        if (target && !inSearch && (target.tagName === "BUTTON" || target.tagName === "A")) return;
        const id = highlighted && order.some((r) => r.customer_id === highlighted) ? highlighted : inSearch ? order[0]?.customer_id : null;
        if (!id) return;
        e.preventDefault();
        open(id);
      } else if (e.key === "/" && !inSearch) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [order, highlighted, open]);

  if (index.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading worklist…</p>;
  if (index.status === "error")
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        Could not load the worklist: {index.error}
      </div>
    );

  const clearButton = (
    <button
      type="button"
      onClick={clear}
      className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white transition-colors duration-150 hover:bg-neutral-700"
    >
      Clear filters
    </button>
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Worklist</h1>
          <p className="mt-0.5 text-sm text-neutral-500">
            Ranked by urgency tier, then urgency score. Nothing is sent without a human decision.
          </p>
        </div>
        <p className="text-xs text-neutral-400">
          <kbd className="rounded border border-neutral-200 bg-white px-1 font-sans">↑</kbd>{" "}
          <kbd className="rounded border border-neutral-200 bg-white px-1 font-sans">↓</kbd> move ·{" "}
          <kbd className="rounded border border-neutral-200 bg-white px-1 font-sans">Enter</kbd> open ·{" "}
          <kbd className="rounded border border-neutral-200 bg-white px-1 font-sans">/</kbd> search
        </p>
      </div>

      <KpiStrip rows={visible} summary={summary} />

      <Toolbar
        filters={filters}
        options={options}
        onFilter={(k, v) => update({ [k]: v })}
        view={view}
        viewCounts={viewCounts}
        onView={(v) => update({ view: v === "all" ? null : v })}
        groupBy={groupBy}
        onGroupBy={(on) => update({ group: on ? "1" : null })}
        onClear={clear}
        dirty={dirty}
        shown={visible.length}
        total={all.length}
        searchRef={searchRef}
      />

      <WorklistTable
        rows={visible}
        groups={groups}
        summary={summary}
        decisions={latest}
        highlightedId={highlighted}
        onOpen={open}
        emptyAction={clearButton}
      />
    </div>
  );
}
