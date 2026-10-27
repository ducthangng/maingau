import { useEffect, useRef, useSyncExternalStore } from "react";
import { MousePointer2 } from "lucide-react";

// Presenter pointer, for demos on a projector or a shared screen: a yellow halo on the mouse pointer, a softer ring
// that trails it (so a fast movement can be followed), a ripple on every click, and a gold outline on whatever
// clickable thing is under the pointer (index.css, html[data-presenter]). On by default; the header button or Alt+P
// turns it off, remembered per browser. Mouse and pen only: a touch screen has no pointer to follow.
const KEY = "maingau.presenter";
const EVENT = "maingau-presenter";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

function setPresenter(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // storage blocked: the switch still works for this page
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function usePresenter(): boolean {
  return useSyncExternalStore(subscribe, read, () => true);
}

/** Header switch. */
export function PresenterToggle() {
  const on = usePresenter();
  return (
    <button
      type="button"
      onClick={() => setPresenter(!on)}
      aria-pressed={on}
      title={`Presenter pointer: ${on ? "on" : "off"} (Alt+P)`}
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium ring-1 ring-inset transition-colors duration-150 ${
        on ? "bg-gold-50 text-neutral-900 ring-gold-400" : "bg-white text-neutral-500 ring-neutral-200 hover:bg-neutral-50"
      }`}
    >
      <MousePointer2 size={13} aria-hidden />
      Presenter
    </button>
  );
}

const HALO = 44; // px, the ring on the pointer
const TRAIL = 84; // px, the soft ring that follows

export default function PresenterPointer() {
  const on = usePresenter();
  const halo = useRef<HTMLDivElement>(null);
  const trail = useRef<HTMLDivElement>(null);
  const ripples = useRef<HTMLDivElement>(null);

  // Alt+P toggles, also while presenting (not inside a text field, where Alt+P may type a character).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey || e.code !== "KeyP") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      e.preventDefault();
      setPresenter(!read());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (!on) {
      delete root.dataset.presenter;
      return;
    }
    root.dataset.presenter = "";
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let x = -200, y = -200, tx = -200, ty = -200, raf = 0, seen = false;

    const show = (v: boolean) => {
      for (const el of [halo.current, trail.current]) if (el) el.style.opacity = v ? "1" : "0";
    };
    const frame = () => {
      // The trail eases toward the pointer; with reduced motion it sits on it.
      tx = reduce ? x : tx + (x - tx) * 0.22;
      ty = reduce ? y : ty + (y - ty) * 0.22;
      if (halo.current) halo.current.style.transform = `translate(${x - HALO / 2}px, ${y - HALO / 2}px)`;
      if (trail.current) trail.current.style.transform = `translate(${tx - TRAIL / 2}px, ${ty - TRAIL / 2}px)`;
      raf = Math.abs(x - tx) + Math.abs(y - ty) > 0.5 ? requestAnimationFrame(frame) : 0;
    };
    const move = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      x = e.clientX;
      y = e.clientY;
      if (!seen) {
        seen = true;
        tx = x;
        ty = y;
        show(true);
      }
      if (!raf) raf = requestAnimationFrame(frame);
    };
    const down = (e: PointerEvent) => {
      if (e.pointerType === "touch" || !ripples.current) return;
      const r = document.createElement("span");
      r.className = "presenter-ripple";
      r.style.left = `${e.clientX}px`;
      r.style.top = `${e.clientY}px`;
      ripples.current.appendChild(r);
      window.setTimeout(() => r.remove(), 650);
    };
    const leave = () => {
      seen = false;
      show(false);
    };

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", down, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    window.addEventListener("blur", leave);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
      document.documentElement.removeEventListener("pointerleave", leave);
      window.removeEventListener("blur", leave);
      delete root.dataset.presenter;
    };
  }, [on]);

  if (!on) return null;
  // Above every dialog (z-40) and sheet; pointer-events-none so it never takes a click.
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[100] overflow-hidden">
      <div
        ref={trail}
        className="absolute left-0 top-0 rounded-full border-2 border-gold-400/60 opacity-0 transition-opacity duration-150"
        style={{ width: TRAIL, height: TRAIL }}
      />
      <div
        ref={halo}
        className="absolute left-0 top-0 rounded-full border-[3px] border-gold-400 bg-gold-400/25 opacity-0 shadow-[0_0_0_2px_rgba(255,255,255,0.8)] transition-opacity duration-150"
        style={{ width: HALO, height: HALO }}
      />
      <div ref={ripples} />
    </div>
  );
}
