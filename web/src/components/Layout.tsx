import { NavLink, Outlet } from "react-router-dom";
import { Network, TriangleAlert } from "lucide-react";
import { dataMode, loadManifest, loadSummary, useLoad } from "../lib/data";
import DecisionErrors from "./DecisionErrors";
import { Bone } from "./Skeleton";
import ViewSwitch, { useIsCustomer360 } from "./service/ViewSwitch";

// Active item: brand-blue pill with the 2 px yellow underline (one of the two yellow uses, prompts/ui-colors.md).
const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
    isActive ? "bg-accent-600 text-white inset-shadow-[0_-2px_0_var(--color-gold-400)]" : "text-neutral-600 hover:bg-neutral-100"
  }`;

export default function Layout() {
  const manifest = useLoad(loadManifest, []);
  const summary = useLoad(loadSummary, []);
  const mode = useLoad(dataMode, []);
  const isMock = manifest.status === "ready" && manifest.data?.source === "mock";
  const isC360 = useIsCustomer360();
  // Customer 360° uses the full screen width so its three cards sit side by side.
  const width = isC360 ? "max-w-none" : "max-w-[1400px]";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/85 backdrop-blur">
        <div className={`mx-auto flex ${width} flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6`}>
          <span className="whitespace-nowrap font-semibold tracking-tight">MAINGAU · Next Best Action</span>
          {isMock && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-semibold text-neutral-800 ring-1 ring-inset ring-neutral-300"
              title="Profile, timeline and KG output are real; valuation, ranking and content are mock (web/mock/build_mock.py)"
            >
              <TriangleAlert size={12} aria-hidden />
              MOCK DATA
            </span>
          )}
          <ViewSwitch />
          {!isC360 && (
          <nav className="flex gap-1 sm:ml-4">
            <NavLink to="/" end className={navClass}>
              Overview
            </NavLink>
            <NavLink to="/worklist" className={navClass}>
              Worklist
            </NavLink>
            <NavLink to="/groups" className={navClass}>
              Groups
            </NavLink>
            <NavLink to="/campaign" className={navClass}>
              Campaigns
            </NavLink>
          </nav>
          )}
          <span className="ml-auto flex items-center gap-2 text-xs text-neutral-500">
            {(mode.status === "loading" || summary.status === "loading") && (
              <span className="skeleton-reveal flex items-center gap-2" aria-hidden>
                <Bone className="h-5 w-12 rounded-full" soft />
                <Bone className="h-3 w-36" soft />
              </span>
            )}
            {mode.status === "ready" && summary.status !== "loading" && (
              <span
                className={`rounded-full px-2 py-0.5 font-medium ${mode.data === "api" ? "bg-neutral-200 text-neutral-800" : "bg-neutral-100 text-neutral-600"}`}
                title={
                  mode.data === "api"
                    ? "Live NBA API: decisions are re-checked and stored in out/decision_log.jsonl"
                    : "Static export: decisions stay in this browser"
                }
              >
                {mode.data === "api" ? "Live API" : "Static"}
              </span>
            )}
            {summary.status === "ready" && mode.status !== "loading" ? `Snapshot ${summary.data.eval_time.replace("T", " ")}` : ""}
            <NavLink
              to="/kb"
              className={({ isActive }) =>
                `inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium ring-1 ring-inset transition-colors duration-150 ${
                  isActive ? "bg-accent-600 text-white ring-accent-600" : "bg-white text-neutral-700 ring-neutral-200 hover:bg-neutral-50"
                }`
              }
              title="Knowledge Base: decision graphs, policy and ontology"
            >
              <Network size={13} aria-hidden />
              Knowledge Base
            </NavLink>
          </span>
        </div>
      </header>
      <main className={`mx-auto ${width} px-4 py-6 sm:px-6`}>
        <Outlet />
      </main>
      <DecisionErrors />
    </div>
  );
}
