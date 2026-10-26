import { NavLink, Outlet } from "react-router-dom";
import { loadManifest, loadSummary, useLoad } from "../lib/data";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
    isActive ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-100"
  }`;

export default function Layout() {
  const manifest = useLoad(loadManifest, []);
  const summary = useLoad(loadSummary, []);
  const isMock = manifest.status === "ready" && manifest.data?.source === "mock";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <span className="whitespace-nowrap font-semibold tracking-tight">MAINGAU · Next Best Action</span>
          {isMock && (
            <span
              className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800"
              title="Profile, timeline and KG output are real; valuation, ranking and content are mock (web/mock/build_mock.py)"
            >
              MOCK DATA
            </span>
          )}
          <nav className="flex gap-1 sm:ml-4">
            <NavLink to="/" end className={navClass}>
              Worklist
            </NavLink>
            <NavLink to="/groups" className={navClass}>
              Groups
            </NavLink>
            <NavLink to="/rules" className={navClass}>
              Rules
            </NavLink>
          </nav>
          <span className="ml-auto text-xs text-neutral-500">
            {summary.status === "ready" ? `Snapshot ${summary.data.eval_time.replace("T", " ")}` : ""}
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
