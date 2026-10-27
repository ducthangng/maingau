import { NavLink, Outlet } from "react-router-dom";
import { dataMode, loadManifest, loadSummary, useLoad } from "../lib/data";
import DecisionErrors from "./DecisionErrors";
import ViewSwitch, { useIsCustomer360 } from "./service/ViewSwitch";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
    isActive ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-100"
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
              className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800"
              title="Profile, timeline and KG output are real; valuation, ranking and content are mock (web/mock/build_mock.py)"
            >
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
          </nav>
          )}
          <span className="ml-auto flex items-center gap-2 text-xs text-neutral-500">
            {mode.status === "ready" && (
              <span
                className={`rounded-full px-2 py-0.5 font-medium ${mode.data === "api" ? "bg-emerald-50 text-emerald-700" : "bg-neutral-100 text-neutral-600"}`}
                title={
                  mode.data === "api"
                    ? "Live NBA API: decisions are re-checked and stored in out/decision_log.jsonl"
                    : "Static export: decisions stay in this browser"
                }
              >
                {mode.data === "api" ? "Live API" : "Static"}
              </span>
            )}
            {summary.status === "ready" ? `Snapshot ${summary.data.eval_time.replace("T", " ")}` : ""}
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
