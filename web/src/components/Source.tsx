import type { ReactNode } from "react";
import type { Fact, SourceInfo } from "../types/contracts";
import { NOT_ENOUGH, isMissing, text } from "../lib/format";

// Source tooltip for every displayed number (README §5.3): table.column, update time, refresh and latency.
export function sourceTitle(src: string | null | undefined, updatedAt?: string | null, sources?: Record<string, SourceInfo>) {
  if (!src) return "source unknown";
  const table = src.split(".")[0];
  const info = sources?.[table];
  return [
    src,
    updatedAt ? `updated ${updatedAt}` : null,
    info?.refresh ? `refresh: ${info.refresh}` : null,
    info?.latency ? `latency: ${info.latency}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

export function Sourced({
  src,
  updatedAt,
  sources,
  children,
}: {
  src: string | null | undefined;
  updatedAt?: string | null;
  sources?: Record<string, SourceInfo>;
  children: ReactNode;
}) {
  return (
    <span title={sourceTitle(src, updatedAt, sources)} className="cursor-help decoration-neutral-300 decoration-dotted underline-offset-4 hover:underline">
      {children}
    </span>
  );
}

export function FactValue({
  fact,
  sources,
  format = text,
}: {
  fact: Fact | null | undefined;
  sources?: Record<string, SourceInfo>;
  format?: (v: never) => string;
}) {
  if (!fact || isMissing(fact.v)) {
    return (
      <Sourced src={fact?.src} updatedAt={fact?.updated_at} sources={sources}>
        <span className="text-neutral-400 italic">{NOT_ENOUGH}</span>
      </Sourced>
    );
  }
  return (
    <Sourced src={fact.src} updatedAt={fact.updated_at} sources={sources}>
      {(format as (v: unknown) => string)(fact.v)}
    </Sourced>
  );
}
