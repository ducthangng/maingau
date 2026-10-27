import { useEffect, useRef, useState, type ReactNode } from "react";

// One Customer 360° column (prompts/ui-polish.md §3.1): an Orchestration card with an 11 px title.
// The body is a container (`@container`) so the cards inside size by the column, not the screen.
// From xl it scrolls inside the card: its padding leaves room on every side for rings and focus
// outlines, and a fade at the bottom shows while more content follows.
export default function ServiceColumn({ label, className = "", children }: { label: string; className?: string; children: ReactNode }) {
  const body = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);

  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const check = () => setMore(el.scrollHeight - el.clientHeight - el.scrollTop > 2);
    check();
    el.addEventListener("scroll", check, { passive: true });
    const ro = new ResizeObserver(check);
    ro.observe(el);
    if (inner.current) ro.observe(inner.current);
    return () => {
      el.removeEventListener("scroll", check);
      ro.disconnect();
    };
  }, []);

  return (
    <section aria-label={label} className={`flex min-h-0 min-w-0 flex-col rounded-2xl border border-neutral-200 bg-white ${className}`}>
      <h2 className="px-4 pb-2 pt-4 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">{label}</h2>
      <div
        ref={body}
        data-more={more || undefined}
        className="@container min-h-0 flex-1 px-4 pb-4 pt-1.5 xl:overflow-y-auto xl:[scrollbar-gutter:stable] xl:data-[more]:[-webkit-mask-image:linear-gradient(to_bottom,black_calc(100%-3rem),transparent)] xl:data-[more]:[mask-image:linear-gradient(to_bottom,black_calc(100%-3rem),transparent)]"
      >
        <div ref={inner}>{children}</div>
      </div>
    </section>
  );
}
