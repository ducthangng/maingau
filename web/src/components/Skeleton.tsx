import type { ReactNode } from "react";
import { GRID as OVERVIEW_GRID, LABEL as OVERVIEW_LABEL } from "./overview/ActionTable";

// Loading skeletons: grey bones in the shape of the page that is about to appear, so nothing jumps when
// the data lands. They show no numbers or names (nothing that could be mistaken for data). Styles in
// index.css: a sheen sweeps across all bones at once; a skeleton fades in only after 150 ms.

/** One grey placeholder block. `soft` is the lighter tone for large surfaces. */
export function Bone({ className = "", soft = false }: { className?: string; soft?: boolean }) {
  const corners = className.includes("rounded") ? "" : "rounded-md"; // one radius class, so rounded-full always wins
  return <span aria-hidden className={`skeleton-bone block ${corners} ${soft ? "soft" : ""} ${className}`} />;
}

/** Lines of text with fixed, varied widths (the same on every render). */
export function Lines({ widths, className = "h-3" }: { widths: string[]; className?: string }) {
  return (
    <span className="block space-y-2" aria-hidden>
      {widths.map((w, i) => (
        <Bone key={i} className={`${className} ${w}`} />
      ))}
    </span>
  );
}

/** Announces the load to screen readers once and keeps the bones out of the accessibility tree. */
export function Loading({ label, className = "", children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div role="status" aria-busy="true" aria-live="polite" className={`skeleton-reveal ${className}`}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

const ROW_WIDTHS = ["w-3/4", "w-2/3", "w-5/6", "w-1/2", "w-3/5", "w-4/5", "w-2/3", "w-3/4", "w-1/2", "w-5/6"];
const BAR_WIDTHS = ["w-full", "w-4/5", "w-3/5", "w-1/2", "w-2/5", "w-1/3", "w-1/4", "w-1/5"];
const range = (n: number) => Array.from({ length: n }, (_, i) => i);

function PageHeader({ wide = true }: { wide?: boolean }) {
  return (
    <header className="max-w-3xl space-y-2.5">
      <Bone className="h-7 w-36" />
      <Lines widths={wide ? ["w-full", "w-3/4"] : ["w-2/3"]} className="h-3.5" />
      <Bone className="h-3 w-64" soft />
    </header>
  );
}

// --- Overview: the action ranking ---------------------------------------------------------------------------

export function OverviewSkeleton() {
  return (
    <Loading label="Loading the overview…" className="space-y-6">
      <PageHeader />
      <div className="flex items-center gap-3 rounded-2xl border border-neutral-200 bg-white px-5 py-3.5">
        <Bone className="size-4 rounded-full" />
        <Bone className="h-3.5 w-56" />
      </div>
      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className={`${OVERVIEW_GRID} border-b border-neutral-100 px-5 py-3`}>
          <span className={OVERVIEW_LABEL}>#</span>
          <span className={OVERVIEW_LABEL}>Action</span>
          <span className={`${OVERVIEW_LABEL} hidden md:block`}>Customers</span>
          <span className={`${OVERVIEW_LABEL} text-right md:text-left`}>Expected ΔCLV</span>
          <span className={`${OVERVIEW_LABEL} hidden md:block`}>Main reason</span>
          <span />
        </div>
        <ol className="divide-y divide-neutral-100">
          {range(7).map((i) => (
            <li key={i} className={`${OVERVIEW_GRID} items-start gap-y-2 px-5 py-4`}>
              <Bone className="mt-1 h-3 w-3" soft />
              <div className="min-w-0 space-y-2">
                <Bone className={`h-4 ${ROW_WIDTHS[i]}`} />
                <Bone className="h-3 w-12 md:hidden" soft />
              </div>
              <Bone className="mt-1 hidden h-3.5 w-10 md:block" soft />
              <div className="space-y-2 pt-0.5">
                <Bone className="ml-auto h-3.5 w-14 md:ml-0" />
                <Bone className={`hidden h-1.5 rounded-full md:block ${BAR_WIDTHS[i]}`} soft />
              </div>
              <div className="col-span-2 col-start-2 md:col-span-1 md:col-start-auto">
                <Lines widths={[ROW_WIDTHS[i + 2], ROW_WIDTHS[i + 1]]} />
              </div>
              <span />
            </li>
          ))}
        </ol>
      </div>
    </Loading>
  );
}

// --- Worklist: review on the left, execute on the right ------------------------------------------------------

function TableRows({ n, marker = false }: { n: number; marker?: boolean }) {
  return (
    <ul className="divide-y divide-neutral-100">
      {range(n).map((i) => (
        <li key={i} className="flex items-center gap-4 px-4 py-3.5">
          {marker && <Bone className="h-9 w-1 rounded-full" soft />}
          <div className="min-w-0 flex-1 space-y-2">
            <Bone className="h-3.5 w-24" />
            <Bone className={`h-3 ${ROW_WIDTHS[i]} max-w-72`} soft />
          </div>
          <div className="hidden w-44 items-center gap-2 sm:flex">
            <Bone className="size-5 shrink-0 rounded" />
            <Bone className={`h-3.5 ${BAR_WIDTHS[i % 4]}`} />
          </div>
          <div className="hidden w-40 space-y-2 md:block">
            <Bone className="h-3.5 w-16" />
            <Bone className={`h-1.5 rounded-full ${BAR_WIDTHS[(i + 2) % 8]}`} soft />
          </div>
          <div className="flex w-36 justify-end gap-2">
            <Bone className="h-7 w-16 rounded-lg" soft />
            <Bone className="h-7 w-16 rounded-lg" />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function WorklistSkeleton() {
  return (
    <Loading label="Loading the worklist…" className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="min-w-0 space-y-6">
        <div className="space-y-2">
          <Bone className="h-5 w-24" />
          <Bone className="h-3.5 w-72" soft />
        </div>
        <div className="flex flex-wrap items-center gap-x-10 gap-y-4 rounded-2xl border border-neutral-200 bg-white px-6 py-5">
          <div className="space-y-2">
            <Bone className="h-7 w-14" />
            <Bone className="h-3 w-32" soft />
          </div>
          <div className="min-w-56 flex-1 space-y-2.5">
            <Bone className="h-2.5 w-full rounded-full" />
            <div className="flex gap-4">
              {range(4).map((i) => (
                <Bone key={i} className="h-3 w-20" soft />
              ))}
            </div>
          </div>
          <div className="flex gap-3">
            {range(3).map((i) => (
              <div key={i} className="flex items-center gap-2.5 px-2 py-1">
                <Bone className="size-6" />
                <div className="space-y-1.5">
                  <Bone className="h-4 w-6" />
                  <Bone className="h-2.5 w-16" soft />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Bone className="h-8 w-56 rounded-lg" soft />
          {range(4).map((i) => (
            <Bone key={i} className="h-7 w-20 rounded-full" soft />
          ))}
          <Bone className="ml-auto h-8 w-48 rounded-lg" soft />
        </div>
        <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
          <div className="flex gap-4 border-b border-neutral-100 px-4 py-3">
            <Bone className="h-3 w-40" soft />
            <Bone className="ml-auto h-3 w-24" soft />
          </div>
          <TableRows n={8} marker />
        </div>
      </section>
      <div className="space-y-3 lg:rounded-2xl lg:bg-neutral-100/70 lg:p-5">
        <Bone className="h-4 w-28" />
        <Bone className="h-3 w-56" soft />
        <ul className="space-y-3 pt-1">
          {range(3).map((i) => (
            <li key={i} className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-neutral-200">
              <div className="flex items-start gap-3">
                <Bone className="size-8 shrink-0 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Bone className="h-3.5 w-28" />
                  <Bone className={`h-3 ${ROW_WIDTHS[i]}`} soft />
                </div>
              </div>
              <Bone className="h-8 w-full rounded-lg" soft />
            </li>
          ))}
        </ul>
      </div>
    </Loading>
  );
}

// --- Groups: one card per shared action ------------------------------------------------------------------------

export function GroupsSkeleton() {
  return (
    <Loading label="Loading the groups…" className="space-y-8">
      <PageHeader />
      <section className="space-y-3">
        <Bone className="h-3 w-60" soft />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {range(6).map((i) => (
            <article key={i} className="flex flex-col rounded-xl border border-neutral-200 bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
              <header className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <Lines widths={[ROW_WIDTHS[i + 2], "w-1/3"]} className="h-4" />
                </div>
                <Bone className="h-6 w-14 shrink-0 rounded-full" soft />
              </header>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {range(3).map((c) => (
                  <div key={c} className="space-y-1.5">
                    <Bone className="h-2.5 w-12" soft />
                    <Bone className="h-4 w-16" />
                  </div>
                ))}
              </div>
              <Bone className="mt-4 h-1.5 w-full rounded-full" soft />
              <Bone className="mt-5 h-9 w-full rounded-lg" />
            </article>
          ))}
        </div>
      </section>
    </Loading>
  );
}

// --- Customer 360: the customer list and the three-column view --------------------------------------------------

export function CustomerListSkeleton() {
  return (
    <Loading label="Loading customers…" className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Bone className="h-9 w-72 rounded-lg" soft />
        <Bone className="h-3 w-32" soft />
      </div>
      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
        <div className="flex gap-6 border-b border-neutral-100 px-4 py-3">
          {["w-24", "w-28", "w-32", "w-24"].map((w, i) => (
            <Bone key={i} className={`h-3 ${w}`} soft />
          ))}
        </div>
        <TableRows n={10} />
      </div>
    </Loading>
  );
}

function StripSkeleton() {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-5 lg:grid-cols-6">
        {["w-32", "w-20", "w-40", "w-16", "w-20", "w-48"].map((w, i) => (
          <div key={i} className={`space-y-1.5 ${i === 5 ? "hidden lg:block" : ""}`}>
            <Bone className="h-2.5 w-16" soft />
            <Bone className={`${i === 1 ? "h-7" : "h-4"} ${w}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

function JourneyBones({ n = 6 }: { n?: number }) {
  return (
    <ol className="space-y-4" aria-hidden>
      {range(n).map((i) => (
        <li key={i} className="flex gap-3">
          <Bone className="mt-0.5 size-6 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-2">
            <Bone className="h-2.5 w-20" soft />
            <Bone className={`h-3.5 ${ROW_WIDTHS[i]}`} />
            <Bone className={`h-3 ${ROW_WIDTHS[i + 3]}`} soft />
          </div>
        </li>
      ))}
    </ol>
  );
}

function ProfileBones() {
  return (
    <div className="space-y-5" aria-hidden>
      {range(4).map((i) => (
        <div key={i} className="space-y-2.5">
          <Bone className="h-3 w-24" />
          <Lines widths={[ROW_WIDTHS[i], ROW_WIDTHS[i + 4], ROW_WIDTHS[i + 1]]} />
        </div>
      ))}
      <div className="flex flex-wrap gap-1.5">
        {["w-16", "w-20", "w-14", "w-24", "w-16"].map((w, i) => (
          <Bone key={i} className={`h-6 rounded-full ${w}`} soft />
        ))}
      </div>
    </div>
  );
}

function ActionBones({ n = 3 }: { n?: number }) {
  return (
    <div className="space-y-3" aria-hidden>
      {range(n).map((i) => (
        <div key={i} className={`space-y-3 rounded-xl border bg-white p-4 ${i === 0 ? "border-neutral-300 shadow-sm" : "border-neutral-200"}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 space-y-2">
              <Bone className={`h-4 ${ROW_WIDTHS[i + 1]}`} />
              <Bone className="h-3 w-32" soft />
            </div>
            <Bone className="h-6 w-16 shrink-0" />
          </div>
          {i === 0 && <Lines widths={["w-full", "w-5/6", "w-2/3"]} />}
          <Bone className={`h-1.5 rounded-full ${BAR_WIDTHS[i + 1]}`} soft />
          {i === 0 && (
            <div className="flex gap-2 pt-1">
              <Bone className="h-8 w-24 rounded-lg" />
              <Bone className="h-8 w-20 rounded-lg" soft />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const C360_COLUMNS = [
  { label: "Profile", body: <ProfileBones /> },
  { label: "Customer journey", body: <JourneyBones /> },
  { label: "Next best actions", body: <ActionBones /> },
];

export function Customer360Skeleton({ id }: { id: string }) {
  return (
    <Loading label={`Loading ${id}…`} className="space-y-5">
      <Bone className="h-3.5 w-24" soft />
      <StripSkeleton />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.6fr)]">
        {C360_COLUMNS.map(({ label, body }) => (
          <section key={label} className="min-w-0 rounded-xl border border-neutral-200 bg-neutral-50/60 p-4">
            {/* The real column titles: they are labels, not data. */}
            <h2 className="mb-3 text-sm font-semibold text-neutral-900">{label}</h2>
            {body}
          </section>
        ))}
      </div>
    </Loading>
  );
}

/** The journey column on its own: it loads after the card. */
export function JourneySkeleton() {
  return (
    <Loading label="Loading the journey…">
      <JourneyBones n={5} />
    </Loading>
  );
}

// --- Customer page and the customer modal: profile on the left, next best action on the right ---------------

export function CustomerSkeleton({ id }: { id: string }) {
  return (
    <Loading label={`Loading ${id}…`} className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Bone className="h-3.5 w-20" soft />
        <Bone className="h-6 w-28" />
        <Bone className="h-5 w-10 rounded-full" />
        <Bone className="h-3.5 w-44" soft />
        <Bone className="ml-auto h-8 w-44 rounded-lg" soft />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
          <ProfileBones />
        </div>
        <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
          <ActionBones />
        </div>
      </div>
    </Loading>
  );
}

/** Fills the customer modal's two-column grid (profile column + NBA panel). */
export function CustomerModalSkeleton({ id }: { id: string }) {
  return (
    <Loading label={`Loading ${id}…`} className="col-span-full grid grid-cols-[minmax(0,1fr)] md:h-full md:grid-cols-[340px_minmax(0,1fr)]">
      <div className="space-y-7 bg-neutral-50 p-6">
        <div className="flex items-center gap-3">
          <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white ring-1 ring-neutral-200">
            <Bone className="size-7 rounded-full" soft />
          </span>
          <div className="flex-1 space-y-2">
            <Bone className="h-5 w-32" />
            <Bone className="h-3 w-24" soft />
          </div>
        </div>
        <ProfileBones />
      </div>
      <div className="space-y-5 p-6 pr-14">
        <div className="space-y-2">
          <Bone className="h-3 w-28" soft />
          <Bone className="h-5 w-2/3" />
        </div>
        <ActionBones />
      </div>
    </Loading>
  );
}
