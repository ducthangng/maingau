import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import NbaCard from "../components/nba/NbaCard";
import ProfileCard from "../components/profile/ProfileCard";
import { TierChip } from "../components/Chips";
import { loadCard, useLoad } from "../lib/data";
import { CustomerSkeleton } from "../components/Skeleton";

export type Mode = "marketing" | "service";

const HIGHLIGHT = ["ring-2", "ring-accent-500", "bg-accent-50"];

/** Scroll the left card to the element tagged data-ui-ref and flash it (README §5.4 ui_ref, spec C3). */
function jumpTo(uiRef: string) {
  const el = document.querySelector<HTMLElement>(`[data-ui-ref="${CSS.escape(uiRef)}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add(...HIGHLIGHT);
  window.setTimeout(() => el.classList.remove(...HIGHLIGHT), 1600);
}

export default function Customer() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const card = useLoad(() => loadCard(id), [id]);
  const [mode, setMode] = useState<Mode>("marketing");
  const [activeSignal, setActiveSignal] = useState<string | null>(null);

  // Going back restores the worklist's filters and view (kept in its URL); a direct link falls back to "/worklist".
  const backToWorklist = useCallback(() => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate("/worklist");
  }, [navigate]);

  useEffect(() => {
    if (card.status === "ready") setMode(card.data.meta.mode_default ?? "marketing");
    setActiveSignal(null);
  }, [card]);

  useEffect(() => {
    // Esc goes back to the worklist, but never while typing (a reject/override reason draft must not be lost).
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      backToWorklist();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [backToWorklist]);

  const onSignalClick = useCallback((sid: string) => setActiveSignal((cur) => (cur === sid ? null : sid)), []);

  if (card.status === "loading") return <CustomerSkeleton id={id} />;
  if (card.status === "error")
    return (
      <p className="text-red-700">
        Could not load {id}: {card.error}. <Link to="/worklist" className="underline">Back to the worklist</Link>
      </p>
    );
  const c = card.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/worklist"
          onClick={(e) => {
            e.preventDefault();
            backToWorklist();
          }}
          className="text-sm text-neutral-500 hover:text-neutral-900"
        >
          ← Worklist
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">{c.customer_id}</h1>
        <TierChip tier={c.triage.urgency_tier} />
        <span className="text-sm text-neutral-600">{c.triage.archetype.name}</span>
        <div className="ml-auto inline-flex rounded-lg bg-neutral-100 p-0.5 text-sm" role="tablist" aria-label="Mode">
          {(["marketing", "service"] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1 capitalize transition-colors duration-150 ${
                mode === m ? "bg-white shadow-sm" : "text-neutral-500 hover:text-neutral-800"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
          <ProfileCard card={c} activeSignal={activeSignal} onSignalClick={onSignalClick} />
        </div>
        <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
          <NbaCard card={c} mode={mode} activeSignal={activeSignal} onNavigate={jumpTo} />
        </div>
      </div>
    </div>
  );
}
