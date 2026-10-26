import { Layers, Search, X } from "lucide-react";
import type { RefObject } from "react";
import { VIEWS, type FilterKey, type Filters, type Option, type ViewId } from "./model";

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

export default function Toolbar({
  filters,
  options,
  onFilter,
  view,
  viewCounts,
  onView,
  groupBy,
  onGroupBy,
  onClear,
  dirty,
  shown,
  total,
  searchRef,
}: {
  filters: Filters;
  options: Partial<Record<FilterKey, Option[]>>;
  onFilter: (key: keyof Filters, value: string) => void;
  view: ViewId;
  viewCounts: Record<ViewId, number>;
  onView: (v: ViewId) => void;
  groupBy: boolean;
  onGroupBy: (on: boolean) => void;
  onClear: () => void;
  dirty: boolean;
  shown: number;
  total: number;
  searchRef: RefObject<HTMLInputElement>;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
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
                  active
                    ? "bg-neutral-900 text-white"
                    : "bg-white text-neutral-700 ring-1 ring-neutral-200 ring-inset hover:bg-neutral-100"
                }`}
              >
                {v.label}
                <span className={`text-xs tabular-nums ${active ? "text-neutral-300" : "text-neutral-400"}`}>{viewCounts[v.id]}</span>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={groupBy}
          onClick={() => onGroupBy(!groupBy)}
          className="ml-auto inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-neutral-700 transition-colors duration-150 hover:bg-neutral-100"
        >
          <Layers className="size-4 text-neutral-400" aria-hidden />
          Group by recommended action
          <span
            aria-hidden
            className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${groupBy ? "bg-accent-600" : "bg-neutral-300"}`}
          >
            <span
              className={`absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                groupBy ? "translate-x-4" : ""
              }`}
            />
          </span>
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-neutral-400" aria-hidden />
          <input
            ref={searchRef}
            data-worklist-search
            type="search"
            value={filters.q}
            onChange={(e) => onFilter("q", e.target.value)}
            placeholder="Search customer ID or city"
            aria-label="Search customer ID or city"
            className="w-60 rounded-lg border border-neutral-200 bg-white py-1.5 pr-2.5 pl-8 text-sm placeholder:text-neutral-400 transition-colors duration-150 hover:border-neutral-300 focus:border-accent-500 focus:ring-2 focus:ring-accent-100 focus:outline-none"
          />
        </div>
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
          onClick={onClear}
          disabled={!dirty}
          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-neutral-600 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900 disabled:cursor-default disabled:text-neutral-300 disabled:hover:bg-transparent"
        >
          <X className="size-3.5" aria-hidden />
          Clear
        </button>
        <span className="ml-auto text-xs text-neutral-500 tabular-nums" aria-live="polite">
          {shown === total ? `${total} customers` : `${shown} of ${total} customers`}
        </span>
      </div>
    </div>
  );
}
