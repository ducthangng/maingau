import type { Blocked, Candidate, CustomerCard, TimelineItem } from "../../types/contracts";
import { CHANNEL_LABEL } from "../../lib/format";
import { OFFER_NAME } from "../worklist/model";

// Plain-language helpers for Customer 360° (prompts/ui-customer360.md): no engine codes, no
// marketing labels, never a word about payment.

/** Profile items are Fact-shaped ({v, src, ...}); take the value. */
export function factV(f: unknown): unknown {
  return f && typeof f === "object" && "v" in f ? (f as { v: unknown }).v : f;
}

export function str(v: unknown): string {
  return v === null || v === undefined || v === "" ? "" : String(v);
}

export function offerName(id: string | null | undefined): string {
  if (!id) return "";
  return OFFER_NAME[id] ?? id;
}

export function channelName(c: string | null | undefined): string {
  if (!c) return "";
  return CHANNEL_LABEL[c] ?? c.replace(/_/g, " ");
}

/** Channel name inside a sentence: "phone call", but acronyms stay ("SMS"). */
function channelInText(c: string | null | undefined): string {
  const n = channelName(c);
  return n === n.toUpperCase() ? n : n.toLowerCase();
}

export function humanize(s: unknown): string {
  const t = str(s).replace(/_/g, " ");
  return t ? t[0].toUpperCase() + t.slice(1) : "";
}

/** Drop engine codes such as "[S3]", "(from S3, S4)" or legacy rule ids. */
export function plainText(s: string | null | undefined): string {
  return str(s)
    .replace(/\s*\[[A-Z]+[-\d]*\d\]/g, "")
    .replace(/\s*\(from S\d+(, S\d+)*\)/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

export function openTickets(card: CustomerCard): TimelineItem[] {
  return (card.timeline ?? []).filter((t) => t.kind === "service" && (t.flags ?? []).includes("open"));
}

export function ticketId(item: TimelineItem | undefined): string | null {
  return item?.ref?.startsWith("ticket:") ? item.ref.slice("ticket:".length) : null;
}

const PAYMENT = /dunning|payment|mahn|zahlung|inkasso/i;

/** Payment data only blocks offers (rule C-09); it is never named in Customer 360°. */
export function noPayment(text: string, fallback = "account status needs attention first"): string {
  return PAYMENT.test(text) ? fallback : text;
}

/** The reason in one plain sentence: the first `why`, without codes or the trailing parenthesis. */
export function reasonOf(c: Candidate | undefined): string {
  return noPayment(plainText(c?.why?.[0]).replace(/\s*\([^)]*\)\s*$/, ""));
}

/** Churn-driver labels for "what moves the CLV", with payment wording replaced. */
export function driverLabels(card: CustomerCard): string[] {
  const labels = (card.profile.value_risk.churn_drivers ?? []).map((d) => noPayment(d.label, "account status"));
  return [...new Set(labels.filter(Boolean))];
}

/** Actions by expected ΔCLV, service actions first while a ticket is open (§3.4). No other re-ranking. */
export function sortedActions(card: CustomerCard): Candidate[] {
  const service = openTickets(card).length > 0;
  return [...(card.candidates ?? [])].sort(
    (a, b) =>
      (service ? Number(b.action_type === "service") - Number(a.action_type === "service") : 0) ||
      (b.valuation?.delta_clv ?? -Infinity) - (a.valuation?.delta_clv ?? -Infinity),
  );
}

// ------------------------------------------------------------------ "Not recommended" (§3.4)

const CONTACT_LIMIT = new Set(["B-01", "B-02", "B-03", "B-04"]);

function contactLimit(b: Blocked): string {
  return b.until ? `Contact limit reached, possible from ${dateLabel(b.until)}` : "Contact limit reached";
}

function noChannel(b: Blocked): string {
  if (b.channel === "app_push") return "No app";
  if (b.channel === "portal_popup") return "No portal account";
  return `No ${channelInText(b.channel)} available`;
}

/** Rule → plain text; rule_center_id first, then rule_id. Account-status rules never quote their reason. */
export function blockedText(b: Blocked): string {
  const reason = plainText(b.reason).replace(/^[^:]{1,60}:\s*/, "");
  if (b.rule_id === "CHANNEL-AVAILABLE") return noChannel(b);
  switch (b.rule_center_id) {
    case "C-07":
      return "No sales offers while a ticket is open";
    case "C-06":
      return "No sales offers right now (account status)";
    case "C-08":
      return "No sales offers: a cancellation is in progress";
    case "C-01":
      return `The customer has not agreed to be contacted by ${channelInText(b.channel) || "this channel"}`;
    case "C-02":
      return "Newsletter: double opt-in not confirmed";
    case "C-03":
      return "The customer unsubscribed from the newsletter";
    case "C-05":
      return "No personalised offers (no consent for personalisation)";
    case "B-07":
      return humanize(reason) || "Already has it, or a needed product is missing";
    case "MEMORY":
      return `The customer said no to this before${reason ? ` (${reason})` : ""}`;
  }
  if (b.rule_center_id && CONTACT_LIMIT.has(b.rule_center_id)) return contactLimit(b);
  switch (b.rule_id) {
    case "EXCL-OPEN-TICKET":
      return "No sales offers while a ticket is open";
    case "EXCL-DUNNING":
      return "No sales offers right now (account status)";
    case "EXCL-CANCELLATION":
    case "EXCL-AUTOSTROM-CANCELLED":
      return "No sales offers: a cancellation is in progress";
    case "CONSENT-CHANNEL":
      return `The customer has not agreed to be contacted by ${channelInText(b.channel) || "this channel"}`;
    case "CONSENT-PROFILING":
      return "No personalised offers (no consent for personalisation)";
    case "HOLDING-PRECONDITION":
      return humanize(reason) || "Already has it, or a needed product is missing";
    case "CONTACT-CAP":
      return contactLimit(b);
    case "ECON-NONPOSITIVE":
      return "Not worth offering now";
    case "DATA-MISSING":
      return "Not enough data";
  }
  return noPayment(humanize(reason) || "Not recommended now", "No sales offers right now (account status)");
}

const ORDER = ["EXCL-", "CONSENT-PROFILING", "HOLDING-PRECONDITION", "CONTACT-CAP", "BUSINESS-RULE", "CONSENT-CHANNEL", "CHANNEL-AVAILABLE", "ECON-NONPOSITIVE", "DATA-MISSING"];
const rank = (b: Blocked) => {
  const i = ORDER.findIndex((r) => b.rule_id.startsWith(r));
  return i < 0 ? ORDER.length : i;
};

export interface NotRecommended {
  subject: string;
  text: string;
}

/** One line per offer, or per channel for customer-level channel rows; most telling first. */
export function notRecommended(card: CustomerCard): NotRecommended[] {
  const seen = new Set<string>();
  const out: NotRecommended[] = [];
  for (const b of [...(card.blocked ?? [])].sort((a, z) => rank(a) - rank(z))) {
    const subject = b.offer_id === "*" ? (b.channel ? channelName(b.channel) : "All sales offers") : offerName(b.offer_id);
    const text = blockedText(b);
    const key = `${subject}|${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ subject, text });
  }
  return out;
}
