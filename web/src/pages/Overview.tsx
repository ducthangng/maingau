import { useCallback, useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, LifeBuoy } from "lucide-react";
import ActionTable from "../components/overview/ActionTable";
import { wholeEur } from "../components/overview/format";
import { SERVICE_LINK, buildOverview } from "../components/overview/model";
import { Sourced } from "../components/Source";
import { asOf, colSrc } from "../components/worklist/model";
import { loadIndex, loadSummary, useLoad } from "../lib/data";

/**
 * Orchestration home (prompts/ui-overview.md): which actions bring the most value and why, how each
 * splits across segments, and a jump into the Worklist filtered to one segment.
 */
export default function Overview() {
  const index = useLoad(loadIndex, []);
  const summaryState = useLoad(loadSummary, []);
  const summary = summaryState.status === "ready" ? summaryState.data : null;
  const model = useMemo(() => (index.status === "ready" ? buildOverview(index.data) : null), [index]);

  // The open action lives in the URL (?open=P-EN-02), so the back button restores it.
  const [params, setParams] = useSearchParams();
  const open = model?.actions.some((a) => a.offer === params.get("open")) ? params.get("open") : null;
  const setOpen = useCallback(
    (offer: string | null) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (offer) next.set("open", offer);
          else next.delete("open");
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  // Esc closes the open action from anywhere on the page; focus returns to its row.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key !== "Escape" || e.defaultPrevented || (el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      setOpen(null);
      document.querySelector<HTMLElement>(`[data-overview-row="${CSS.escape(open)}"]`)?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  if (index.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading overview…</p>;
  if (index.status === "error")
    return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">Could not load the overview: {index.error}</div>;
  if (!model) return null;
  const valueSrc = colSrc(summary, "delta_clv");
  const countSrc = colSrc(summary, "chosen_offer");

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Overview</h1>
        <p className="mt-1 text-[15px] text-neutral-600">
          Which actions bring the most value, and why. Open an action to see how it splits across the customer segments, then jump into
          the Worklist.
        </p>
        <p className="mt-2 text-sm tabular-nums text-neutral-500">
          {model.actions.length} actions ·{" "}
          <Sourced src={countSrc} updatedAt={summary?.eval_time} sources={summary?.sources}>
            {model.customers} customers
          </Sourced>{" "}
          ·{" "}
          <Sourced src={valueSrc} updatedAt={asOf(summary, valueSrc)} sources={summary?.sources}>
            {wholeEur(model.total)}
          </Sourced>{" "}
          expected ΔCLV
        </p>
      </header>

      {model.service > 0 && (
        <Link
          to={SERVICE_LINK}
          className="group flex items-center gap-2 rounded-2xl border border-neutral-200 bg-white px-5 py-3 text-sm text-neutral-700 transition-colors duration-150 hover:bg-neutral-50"
        >
          <LifeBuoy size={16} className="text-neutral-500" aria-hidden />
          <span>
            <Sourced src={countSrc} updatedAt={summary?.eval_time} sources={summary?.sources}>
              <span className="font-semibold tabular-nums text-neutral-900">{model.service} service cases</span>
            </Sourced>{" "}
            need attention
          </span>
          <ArrowRight size={14} className="text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
        </Link>
      )}

      <ActionTable actions={model.actions} summary={summary} maxTotal={model.maxTotal} open={open} onToggle={setOpen} />
    </div>
  );
}
