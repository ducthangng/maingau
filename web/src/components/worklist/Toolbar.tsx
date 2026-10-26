import { Layers, Search, SlidersHorizontal, X } from "lucide-react";
import type { RefObject } from "react";
import { QUEUES, VIEWS, type FilterKey, type Filters, type Option, type QueueId, type ViewId } from "./model";

const SELECTS: { key: FilterKey; label: string; all: string }[] = [
  { key: "tier", label: "Tier", all: "All tiers" },
  { key: "arch", label: "Archetype", all: "All archetypes" },
  { key: "flag", label: "Flag", all: "All flags" },
  { key: "offer", label: "Offer", all: "All offers" },
  { key: "channel", label: "Channel", all: "All channels" },
  { key: "conf", label: "Confidence", all: "Any confidence" },
  { key: "mode", label: "Mode", all: "Any mode" },
  { key: "pers", label: "Personalised", all: "Personalised: any" },
];

const FIXED: Partial<Record<FilterKey, Option[]>> = {
  mode: [
    { value: "marketing", label: "Marketing" },
    { value: "service", label: "Service mode" },
  ],
  pers: [
    { value: "yes", label: "Personalised" },
    { value: "no", label: "Not personalised" },
  ],
};

/** Queue tabs and search up front; saved views, filters and group-by fold away behind "Filters". */
export default function Toolbar({
  queue,
  queueCounts,
  onQueue,
  filters,
  options,
  onFilter,
  view,
  viewCounts,
  onView,
  groupBy,
  onGroupBy,
  onClear,
  activeFilters,
  showFilters,
  onShowFilters,
  shown,
  searchRef,
}: {
  queue: QueueId;
  queueCounts: Record<QueueId, number>;
  onQueue: (q: QueueId) => void;
  filters: Filters;
  options: Partial<Record<FilterKey, Option[]>>;
  onFilter: (key: keyof Filters, value: string) => void;
  view: ViewId;
  viewCounts: Record<ViewId, number>;
  onView: (v: ViewId) => void;
  groupBy: boolean;
  onGroupBy: (on: boolean) => void;
  onClear: () => void;
  activeFilters: number;
  showFilters: boolean;
  onShowFilters: (on: boolean) => void;
  shown: number;
  searchRef: RefObject<HTMLInputElement>;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="Queue" className="inline-flex rounded-lg bg-neutral-100 p-0.5">
          {QUEUES.map((q) => {
            const active = q.id === queue;
            return (
              <button
                key={q.id}
                role="tab"
                aria-selected={active}
                title={q.hint}
                onClick={() => onQueue(q.id)}
                className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm transition-colors duration-150 ${
                  active ? "bg-white font-medium text-neutral-900 shadow-sm" : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                {q.label}
                <span className="text-xs tabular-nums text-neutral-400">{queueCounts[q.id]}</span>
              </button>
            );
          })}
        </div>

        <div className="relative ml-auto">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-neutral-400" aria-hidden />
          <input
            ref={searchRef}
            data-worklist-search
            type="search"
            value={filters.q}
            onChange={(e) => onFilter("q", e.target.value)}
            placeholder="Customer ID or city"
            aria-label="Search customer ID or city"
            className="w-52 rounded-lg border border-neutral-200 bg-white py-1.5 pr-2.5 pl-8 text-sm placeholder:text-neutral-400 transition-colors duration-150 hover:border-neutral-300 focus:border-accent-500 focus:ring-2 focus:ring-accent-100 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={() => onShowFilters(!showFilters)}
          aria-expanded={showFilters}
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm ring-1 ring-inset transition-colors duration-150 ${
            activeFilters ? "bg-accent-50 text-accent-700 ring-accent-100" : "bg-white text-neutral-700 ring-neutral-200 hover:bg-neutral-50"
          }`}
        >
          <SlidersHorizontal className="size-4" aria-hidden />
          Filters
          {activeFilters > 0 && <span className="rounded-full bg-accent-600 px-1.5 text-[11px] font-medium text-white tabular-nums">{activeFilters}</span>}
        </button>
        {activeFilters > 0 && (
          <button
            type="button"
            onClick={onClear}
            title="Clear filters"
            aria-label="Clear filters"
            className="rounded-lg p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-4" aria-hidden />
          </button>
        )}
        <span className="w-20 text-right text-xs text-neutral-500 tabular-nums" aria-live="polite">
          {shown} shown
        </span>
      </div>

      {showFilters && (
        <div className="space-y-3 rounded-xl border border-neutral-200 bg-white p-3">
          <div role="tablist" aria-label="Saved views" className="flex flex-wrap gap-1.5">
            {VIEWS.map((v) => {
              const active = v.id === view;
              return (
                <button
                  key={v.id}
                  role="tab"
                  aria-selected={active}
                  title={v.hint}
                  onClick={() => onView(v.id)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition-colors duration-150 ${
                    active ? "bg-neutral-900 text-white" : "bg-white text-neutral-700 ring-1 ring-neutral-200 ring-inset hover:bg-neutral-100"
                  }`}
                >
                  {v.label}
                  <span className={`text-xs tabular-nums ${active ? "text-neutral-300" : "text-neutral-400"}`}>{viewCounts[v.id]}</span>
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {SELECTS.map(({ key, label, all }) => {
              const opts = FIXED[key] ?? options[key] ?? [];
              const value = filters[key];
              return (
                <select
                  key={key}
                  aria-label={label}
                  value={value}
                  onChange={(e) => onFilter(key, e.target.value)}
                  className={`max-w-48 rounded-lg border bg-white py-1.5 pr-7 pl-2.5 text-sm transition-colors duration-150 hover:border-neutral-300 ${
                    value ? "border-accent-500 text-accent-700" : "border-neutral-200 text-neutral-700"
                  }`}
                >
                  <option value="">{all}</option>
                  {opts.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              );
            })}
            <button
              type="button"
              role="switch"
              aria-checked={groupBy}
              onClick={() => onGroupBy(!groupBy)}
              className="ml-auto inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-neutral-700 transition-colors duration-150 hover:bg-neutral-100"
            >
              <Layers className="size-4 text-neutral-400" aria-hidden />
              Group by action
              <span aria-hidden className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${groupBy ? "bg-accent-600" : "bg-neutral-300"}`}>
                <span
                  className={`absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${groupBy ? "translate-x-4" : ""}`}
                />
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
