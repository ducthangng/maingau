import { useLayoutEffect, useRef, useState } from "react";
import {
  Ban,
  Box,
  Database,
  Gift,
  Layers,
  Radio,
  Send,
  ShieldCheck,
  Target,
  User,
  type LucideIcon,
} from "lucide-react";
import type { EdgeStatus, KbGraph, KbNode } from "../../lib/kb";

// A layered graph read top to bottom: one row per column of the export (Customer → Data → Signals → … ).
// Rows wrap; the connectors are measured from the real card positions, so they follow any wrap.

const KIND_ICON: Record<string, LucideIcon> = {
  customer: User,
  data: Database,
  signal: Radio,
  need: Target,
  rule: Ban,
  offer: Gift,
  channel: Send,
  consent: ShieldCheck,
  instance: Box,
  type: Layers,
};

type LineStatus = EdgeStatus | "alternative";

const EDGE_STYLE: Record<LineStatus, { stroke: string; width: number; dash?: string }> = {
  chosen: { stroke: "var(--color-accent-600)", width: 2 },
  alternative: { stroke: "var(--color-neutral-300)", width: 1.25, dash: "2 3" },
  plain: { stroke: "var(--color-neutral-300)", width: 1.25 },
  waiting: { stroke: "var(--color-neutral-400)", width: 1.25, dash: "4 4" },
  blocked: { stroke: "var(--color-red-400)", width: 1.25, dash: "4 4" },
};

function nodeClass(n: KbNode, selected: boolean): string {
  const base = "relative flex w-44 min-w-0 items-start gap-2 rounded-xl border bg-white px-3 py-2 text-left shadow-sm transition-[box-shadow,background-color] duration-150 hover:bg-neutral-50";
  const status =
    n.status === "chosen" || n.path
      ? "border-accent-600"
      : n.status === "blocked"
        ? "border-dashed border-red-300 text-neutral-500"
        : n.status === "waiting"
          ? "border-dashed border-neutral-400"
          : "border-neutral-200";
  return `${base} ${status} ${selected ? "ring-2 ring-inset ring-accent-500" : ""}`;
}

/** A status the export adds later must not break the page: unknown ones draw as plain lines. */
const lineStatus = (s: string): LineStatus => (s in EDGE_STYLE ? (s as LineStatus) : "plain");

interface Line {
  key: string;
  d: string;
  status: LineStatus;
  label?: string;
  lx: number;
  ly: number;
}

export default function LayerGraph({
  graph,
  selected,
  onSelect,
}: {
  graph: KbGraph;
  selected: string | null;
  onSelect: (node: KbNode) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const cards = useRef(new Map<string, HTMLButtonElement>());
  const [lines, setLines] = useState<Line[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });

  const rows = graph.columns.map((title, col) => ({ title, nodes: graph.nodes.filter((n) => n.col === col) })).filter((r) => r.nodes.length);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      const origin = el.getBoundingClientRect();
      const z = el.offsetWidth ? origin.width / el.offsetWidth : 1; // the zoom canvas scales the graph as a whole
      const at = (id: string) => {
        const r = cards.current.get(id)?.getBoundingClientRect();
        return r ? { x: (r.left - origin.left + r.width / 2) / z, top: (r.top - origin.top) / z, bottom: (r.bottom - origin.top) / z } : null;
      };
      const out: Line[] = [];
      for (const [i, e] of graph.edges.entries()) {
        const a = at(e.from);
        const b = at(e.to);
        if (!a || !b) continue;
        const down = b.top >= a.bottom - 1;
        const y1 = down ? a.bottom : a.top;
        const y2 = down ? b.top : b.bottom;
        const bend = Math.max(18, Math.abs(y2 - y1) / 2);
        const c1 = down ? y1 + bend : y1 - bend;
        const c2 = down ? y2 - bend : y2 + bend;
        out.push({ key: `${i}`, d: `M ${a.x} ${y1} C ${a.x} ${c1}, ${b.x} ${c2}, ${b.x} ${y2}`, status: lineStatus(e.status), label: e.label,
                   lx: (a.x + b.x) / 2, ly: (y1 + y2) / 2 });
      }
      setLines(out);
      setSize({ w: el.scrollWidth, h: el.scrollHeight });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [graph]);

  // Chosen-path edges are drawn last (on top) and labelled; the others only in their tooltip-free grey.
  const ordered = [...lines].sort((a, b) => Number(a.status === "chosen") - Number(b.status === "chosen"));

  return (
    <div ref={box} className="relative">
      <svg className="pointer-events-none absolute inset-0" width={size.w} height={size.h} aria-hidden>
        <defs>
          {(Object.keys(EDGE_STYLE) as LineStatus[]).map((s) => (
            <marker key={s} id={`kb-arrow-${s}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill={EDGE_STYLE[s].stroke} />
            </marker>
          ))}
        </defs>
        {ordered.map((l) => (
          <path key={l.key} d={l.d} fill="none" stroke={EDGE_STYLE[l.status].stroke} strokeWidth={EDGE_STYLE[l.status].width}
                strokeDasharray={EDGE_STYLE[l.status].dash} markerEnd={`url(#kb-arrow-${l.status})`} />
        ))}
        {ordered
          .filter((l) => l.status === "chosen" && l.label)
          .map((l) => (
            <g key={`t${l.key}`}>
              <rect x={l.lx - 3.2 * (l.label?.length ?? 0) - 6} y={l.ly - 8} width={6.4 * (l.label?.length ?? 0) + 12} height={16} rx={8} fill="white" />
              <text x={l.lx} y={l.ly + 3.5} textAnchor="middle" fontSize="10.5" fill="var(--color-accent-700)">
                {l.label}
              </text>
            </g>
          ))}
      </svg>

      <ol className="relative space-y-9">
        {rows.map((row) => (
          <li key={row.title}>
            <p className="mb-2 text-center text-[11px] font-semibold uppercase tracking-wider text-neutral-500">{row.title}</p>
            <div className="flex flex-wrap justify-center gap-3">
              {row.nodes.map((n) => {
                const Icon = KIND_ICON[n.kind] ?? Box;
                const onPath = n.status === "chosen" || n.path;
                return (
                  <button
                    key={n.id}
                    ref={(el) => {
                      if (el) cards.current.set(n.id, el);
                      else cards.current.delete(n.id);
                    }}
                    type="button"
                    onClick={() => onSelect(n)}
                    aria-pressed={selected === n.id}
                    title={n.sub ? `${n.label} · ${n.sub}` : n.label}
                    className={nodeClass(n, selected === n.id)}
                  >
                    <span
                      className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-md ${
                        onPath ? "bg-accent-600 text-white" : n.status === "blocked" ? "bg-red-50 text-red-600" : "bg-neutral-100 text-neutral-500"
                      }`}
                    >
                      <Icon size={13} aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-medium text-neutral-900">{n.label}</span>
                      {n.sub && <span className="line-clamp-2 text-[11px] leading-snug text-neutral-500">{n.sub}</span>}
                    </span>
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
