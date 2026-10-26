// Display helpers. Missing values are never shown as 0 (README §0, prompts/agent-cards.md §2).
export const NOT_ENOUGH = "not enough data";

// English number style everywhere in the UI ("€1,440", "+€18.93"), matching the engine's reason lines.
const eurFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const eurCentFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR", minimumFractionDigits: 2 });

export function isMissing(v: unknown): v is null | undefined {
  return v === null || v === undefined || (typeof v === "number" && Number.isNaN(v));
}

export function eur(v: number | null | undefined, cents = false): string {
  if (isMissing(v)) return NOT_ENOUGH;
  return (cents ? eurCentFmt : eurFmt).format(v);
}

export function signedEur(v: number | null | undefined): string {
  if (isMissing(v)) return NOT_ENOUGH;
  return v > 0 ? `+${eurCentFmt.format(v)}` : eurCentFmt.format(v);
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (isMissing(v)) return NOT_ENOUGH;
  return `${(v * 100).toFixed(digits)}%`;
}

export function text(v: unknown): string {
  if (isMissing(v) || v === "") return NOT_ENOUGH;
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export const CHANNEL_LABEL: Record<string, string> = {
  newsletter_email: "Newsletter",
  email: "E-mail",
  portal_popup: "Portal pop-up",
  app_push: "App push",
  sms: "SMS",
  outbound_call: "Phone call",
  service_agent: "Service agent",
};

export function tupleLabel(tuple: string | null | undefined): string {
  if (!tuple) return NOT_ENOUGH;
  if (tuple === "NO_ACTION") return "No action";
  const [offer, channel, tone] = tuple.split("|");
  return `${offer} · ${CHANNEL_LABEL[channel] ?? channel} · ${tone === "du" ? "Du" : "Sie"}`;
}
