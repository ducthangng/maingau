import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Maximize2, Minus, Plus } from "lucide-react";

// A plain white canvas that zooms and pans: − / + / Fit buttons, Ctrl or ⌘ + wheel to zoom, drag the background to
// move. The content is laid out once at its natural size and scaled as a whole, so connectors stay attached.

const MIN = 0.4;
const MAX = 1.6;
const clamp = (z: number) => Math.min(MAX, Math.max(MIN, Math.round(z * 100) / 100));

export default function ZoomCanvas({ children, resetKey }: { children: ReactNode; resetKey: string }) {
  const view = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);

  const fit = useCallback(() => {
    const v = view.current;
    const el = inner.current;
    if (!v || !el || !el.offsetWidth) return;
    setZoom(clamp(Math.min(1, (v.clientWidth - 32) / el.offsetWidth)));
    v.scrollTo({ left: 0, top: 0 });
  }, []);

  // Natural size of the content (unscaled), and a fit to the width whenever the graph changes.
  useLayoutEffect(() => {
    const el = inner.current;
    if (!el) return;
    const measure = () => setSize({ w: el.offsetWidth, h: el.offsetHeight });
    measure();
    fit();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [resetKey, fit]);

  const onWheel = (e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    setZoom((z) => clamp(z * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
  };

  const btn =
    "grid size-7 place-items-center rounded-md text-neutral-600 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900 disabled:opacity-40";

  return (
    <div className="relative">
      <div className="absolute right-3 top-3 z-10 flex items-center gap-0.5 rounded-lg border border-neutral-200 bg-white/95 p-0.5 shadow-sm backdrop-blur">
        <button type="button" className={btn} onClick={() => setZoom((z) => clamp(z - 0.1))} disabled={zoom <= MIN} aria-label="Zoom out">
          <Minus size={14} aria-hidden />
        </button>
        <button type="button" onClick={() => setZoom(1)} className="min-w-12 rounded-md px-1.5 py-1 text-xs tabular-nums text-neutral-700 hover:bg-neutral-100" title="Reset to 100%">
          {Math.round(zoom * 100)}%
        </button>
        <button type="button" className={btn} onClick={() => setZoom((z) => clamp(z + 0.1))} disabled={zoom >= MAX} aria-label="Zoom in">
          <Plus size={14} aria-hidden />
        </button>
        <button type="button" className={btn} onClick={fit} aria-label="Fit to width" title="Fit to width">
          <Maximize2 size={13} aria-hidden />
        </button>
      </div>
      <div
        ref={view}
        onWheel={onWheel}
        onPointerDown={(e) => {
          if ((e.target as HTMLElement).closest("button") || !view.current) return;
          drag.current = { x: e.clientX, y: e.clientY, left: view.current.scrollLeft, top: view.current.scrollTop };
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d || !view.current) return;
          view.current.scrollLeft = d.left - (e.clientX - d.x);
          view.current.scrollTop = d.top - (e.clientY - d.y);
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
        className="h-[72vh] cursor-grab overflow-auto rounded-2xl border border-neutral-200 bg-white active:cursor-grabbing"
      >
        <div className="relative mx-auto my-4" style={{ width: size.w * zoom, height: size.h * zoom }}>
          <div ref={inner} className="absolute left-0 top-0 w-[1040px] origin-top-left p-6" style={{ transform: `scale(${zoom})` }}>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
