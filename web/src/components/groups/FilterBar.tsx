import { ListFilter, X } from "lucide-react";

// The action and segment the Overview opened the Groups page with; Reset shows every group again.
export default function FilterBar({ label, onReset }: { label: string; onReset: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700">
      <ListFilter className="size-4 shrink-0 text-accent-700" aria-hidden />
      <p className="min-w-0 flex-1">
        Showing <span className="font-medium text-neutral-900">{label}</span>
        <span className="text-neutral-500"> · channel and tone groups of this action, with only these customers</span>
      </p>
      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 text-xs font-medium text-neutral-700 transition-colors duration-150 hover:border-accent-500 hover:text-accent-700"
      >
        Reset filter
        <X className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}
