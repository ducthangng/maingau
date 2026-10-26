import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Maximize, Minus, Move, Plus } from "lucide-react";

// A Figma-like work area: drag the empty canvas (or hold Space / use the middle button) to move,
// scroll to pan, ⌘/Ctrl + scroll or pinch to zoom around the cursor. Content keeps a fixed layout
// width and is placed with one transform, so anything a node expands stays where the reviewer works.

const MIN = 0.4;
const MAX = 2;
const GRID = 18;

/** Elements that keep their own pointer behaviour (clicks, text selection) instead of panning. */
const INTERACTIVE = "button, a, input, textarea, select, summary, label, [role=button], [data-no-pan]";

type View = { x: number; y: number; z: number };

const clamp = (z: number) => Math.min(MAX, Math.max(MIN, z));

export default function Canvas({ children, contentWidth = 820 }: { children: ReactNode; contentWidth?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, z: 1 });
  const [dragging, setDragging] = useState(false);
  const [space, setSpace] = useState(false);
  const drag = useRef<{ id: number; x: number; y: number } | null>(null);

  /** Zoom to `z`, keeping the canvas point under (px, py) — container coordinates — fixed. */
  const zoomAt = useCallback((z: number, px: number, py: number) => {
    setView((v) => {
      const nz = clamp(z);
      return { z: nz, x: px - (px - v.x) * (nz / v.z), y: py - (py - v.y) * (nz / v.z) };
    });
  }, []);

  const zoomCenter = (factor: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    zoomAt(view.z * factor, r.width / 2, r.height / 2);
  };

  /** Fit the whole graph in view (never above 100%), centred horizontally, from the top. */
  const fit = useCallback(() => {
    const r = box.current?.getBoundingClientRect();
    const c = content.current;
    if (!r || !c) return;
    const pad = 32;
    const z = clamp(Math.min(1, (r.width - pad * 2) / c.offsetWidth, (r.height - pad * 2) / c.offsetHeight));
    setView({ z, x: (r.width - c.offsetWidth * z) / 2, y: pad });
  }, []);

  useLayoutEffect(fit, [fit]);

  // Wheel needs a non-passive listener so the page does not scroll underneath.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const r = el.getBoundingClientRect();
        setView((v) => {
          // A mouse-wheel notch (~100) is about ×1.6; trackpad pinch sends small deltas, so it stays smooth.
          const nz = clamp(v.z * Math.exp(-Math.max(-100, Math.min(100, e.deltaY)) * 0.005));
          const px = e.clientX - r.left;
          const py = e.clientY - r.top;
          return { z: nz, x: px - (px - v.x) * (nz / v.z), y: py - (py - v.y) * (nz / v.z) };
        });
      } else {
        setView((v) => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }));
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // Space held = hand tool, like Figma (ignored while typing).
  useEffect(() => {
    const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !typing(e.target) && box.current?.matches(":hover")) {
        e.preventDefault();
        setSpace(true);
      }
    };
    const up = (e: KeyboardEvent) => e.code === "Space" && setSpace(false);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    const onControl = (e.target as HTMLElement).closest(INTERACTIVE);
    if (!(e.button === 1 || space || (e.button === 0 && !onControl))) return;
    e.preventDefault();
    drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setDragging(true);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    d.x = e.clientX;
    d.y = e.clientY;
    setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
  };
  const endDrag = () => {
    drag.current = null;
    setDragging(false);
  };

  const btn =
    "grid size-7 place-items-center rounded-md text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900 disabled:opacity-30 disabled:hover:bg-transparent";

  return (
    <div className="relative min-h-120 overflow-hidden bg-neutral-50/60 md:min-h-0">
      <div
        ref={box}
        className={`absolute inset-0 touch-none select-none ${dragging ? "cursor-grabbing" : space ? "cursor-grab" : "cursor-default"}`}
        style={{
          backgroundImage: "radial-gradient(circle, rgb(212 212 212 / 0.8) 1px, transparent 1px)",
          backgroundSize: `${GRID * view.z}px ${GRID * view.z}px`,
          backgroundPosition: `${view.x}px ${view.y}px`,
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <div
          ref={content}
          className="absolute top-0 left-0 origin-top-left select-text"
          style={{ width: contentWidth, transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})` }}
        >
          {children}
        </div>
      </div>

      {/* controls */}
      <div className="pointer-events-none absolute inset-x-4 bottom-4 flex items-end justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-white/90 px-2 py-1 text-[11px] text-neutral-500 shadow-sm ring-1 ring-neutral-200">
          <Move size={12} aria-hidden /> Drag to move · scroll to pan · ⌘/Ctrl + scroll to zoom
        </span>
        <div className="pointer-events-auto inline-flex items-center gap-0.5 rounded-lg bg-white p-0.5 shadow-md ring-1 ring-neutral-200" role="group" aria-label="Canvas zoom">
          <button type="button" onClick={() => zoomCenter(1 / 1.2)} disabled={view.z <= MIN} className={btn} aria-label="Zoom out" title="Zoom out">
            <Minus size={14} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => {
              const r = box.current?.getBoundingClientRect();
              if (r) zoomAt(1, r.width / 2, r.height / 2);
            }}
            className="w-11 text-center text-[11px] text-neutral-600 tabular-nums hover:text-neutral-900"
            title="Zoom to 100%"
          >
            {Math.round(view.z * 100)}%
          </button>
          <button type="button" onClick={() => zoomCenter(1.2)} disabled={view.z >= MAX} className={btn} aria-label="Zoom in" title="Zoom in">
            <Plus size={14} aria-hidden />
          </button>
          <span className="mx-0.5 h-4 w-px bg-neutral-200" aria-hidden />
          <button type="button" onClick={fit} className={btn} aria-label="Fit to view" title="Fit to view">
            <Maximize size={14} aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
