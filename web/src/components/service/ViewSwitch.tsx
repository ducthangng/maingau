import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

// Dashboard switch (prompts/ui-customer360.md §2): Orchestration | Customer 360°.
// The choice is remembered in localStorage; a direct link (any URL other than the bare "/") wins.
const KEY = "maingau.view.v1";
type View = "orchestration" | "c360";

function readView(): View | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "c360" || v === "orchestration" ? v : null;
  } catch {
    return null;
  }
}

function saveView(v: View) {
  try {
    localStorage.setItem(KEY, v);
  } catch {
    // storage blocked: the switch still works for this tab
  }
}

export function useIsCustomer360(): boolean {
  return useLocation().pathname.startsWith("/service");
}

let restored = false;
let lastServicePath = "/service";

/** Normalise "100023", "mg-100023" or "MG-100023" to the customer_id format. */
export function normaliseId(raw: string): string {
  const t = raw.trim().toUpperCase();
  return /^\d+$/.test(t) ? `MG-${t}` : t;
}

export function CustomerSearch({ autoFocus = false, size = "sm" }: { autoFocus?: boolean; size?: "sm" | "lg" }) {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        const id = normaliseId(value);
        if (id) navigate(`/service/${encodeURIComponent(id)}`);
        setValue("");
      }}
      className={`flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-2.5 focus-within:border-accent-500 ${
        size === "lg" ? "py-2.5" : "py-1"
      }`}
    >
      <Search className="size-4 text-neutral-400" aria-hidden />
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus={autoFocus}
        aria-label="Customer ID"
        placeholder="Customer ID, e.g. MG-100023"
        className={`w-56 bg-transparent outline-none placeholder:text-neutral-400 ${size === "lg" ? "text-base sm:w-80" : "text-sm"}`}
      />
    </form>
  );
}

export default function ViewSwitch() {
  const location = useLocation();
  const navigate = useNavigate();
  const isC360 = location.pathname.startsWith("/service");

  useEffect(() => {
    if (isC360) lastServicePath = location.pathname;
  }, [isC360, location.pathname]);

  // Restore the remembered dashboard once, only when the app opens on the bare start page.
  useEffect(() => {
    if (restored) return;
    restored = true;
    if (location.pathname === "/" && !location.search && readView() === "c360") navigate("/service", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = (v: View) => {
    saveView(v);
    if (v === "c360" && !isC360) navigate(lastServicePath);
    if (v === "orchestration" && isC360) navigate("/");
  };

  const btn = (active: boolean) =>
    `rounded-md px-3 py-1 text-sm transition-colors duration-150 ${active ? "bg-white shadow-sm" : "text-neutral-500 hover:text-neutral-800"}`;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="inline-flex rounded-lg bg-neutral-100 p-0.5" role="tablist" aria-label="Dashboard">
        <button type="button" role="tab" aria-selected={!isC360} onClick={() => pick("orchestration")} className={btn(!isC360)}>
          Orchestration
        </button>
        <button type="button" role="tab" aria-selected={isC360} onClick={() => pick("c360")} className={btn(isC360)}>
          Customer 360°
        </button>
      </div>
      {isC360 && <CustomerSearch />}
    </div>
  );
}
