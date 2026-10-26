import type { ReactNode } from "react";

// Pieces shared by the pop-up's profile column and its NBA panel.

export function Label({ children }: { children: ReactNode }) {
  return <h4 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">{children}</h4>;
}
