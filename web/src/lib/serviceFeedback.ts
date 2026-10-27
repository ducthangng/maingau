import { useSyncExternalStore } from "react";
import { API_BASE, dataMode } from "./data";
import { REVIEWER } from "./decisions";

// Customer reactions a service agent records in Customer 360° (prompts/ui-customer360.md §3.4).
// One row per reaction, in the shape of the workbook table `service_nba_feedback`; they feed the
// feedback loop (nba.ai.feedback). Stored in localStorage; in API mode also posted (best effort).
// Nothing is ever sent to the customer.
const KEY = "maingau.serviceFeedback.v1";
const EVENT = "maingau-service-feedback";

export type Reaction = "mentioned" | "interested" | "declined";
export type DismissReason = "customer_already_has_product" | "customer_upset" | "no_time" | "not_relevant";
export type ContactChannel = "phone" | "chat";

export interface ServiceFeedback {
  feedback_id: string;
  ticket_id: string | null;
  customer_id: string;
  shown_at: string;
  channel: ContactChannel;
  suggestion_source: "nba_engine";
  suggested_offer_id: string;
  agent_id: string;
  agent_action: "accepted" | "dismissed";
  dismiss_reason: DismissReason | null;
  offer_mentioned_to_customer: true;
  customer_reaction: "interested" | "declined" | "annoyed" | null;
  converted_within_14d: null;
}

export const DISMISS_LABEL: Record<DismissReason, string> = {
  customer_already_has_product: "already has it",
  customer_upset: "upset",
  no_time: "no time",
  not_relevant: "not relevant",
};

let cached: ServiceFeedback[] | null = null;

function read(): ServiceFeedback[] {
  if (cached) return cached;
  try {
    cached = JSON.parse(localStorage.getItem(KEY) ?? "[]") as ServiceFeedback[];
  } catch {
    cached = [];
  }
  return cached;
}

function write(list: ServiceFeedback[]) {
  cached = list;
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // storage blocked: keep the in-memory copy for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

export function recordReaction(input: {
  customer_id: string;
  offer_id: string;
  reaction: Reaction;
  reason: DismissReason | null;
  channel: ContactChannel;
  ticket_id: string | null;
}): ServiceFeedback {
  const now = new Date();
  const declined = input.reaction === "declined";
  const row: ServiceFeedback = {
    feedback_id: `SF-${now.getTime()}`,
    ticket_id: input.ticket_id,
    customer_id: input.customer_id,
    shown_at: now.toISOString(),
    channel: input.channel,
    suggestion_source: "nba_engine",
    suggested_offer_id: input.offer_id,
    agent_id: REVIEWER,
    agent_action: declined ? "dismissed" : "accepted",
    dismiss_reason: declined ? input.reason : null,
    offer_mentioned_to_customer: true,
    customer_reaction:
      input.reaction === "interested" ? "interested" : !declined ? null : input.reason === "customer_upset" ? "annoyed" : "declined",
    converted_within_14d: null,
  };
  write([...read(), row]);
  void post(row);
  return row;
}

// The endpoint is planned (§5); until it exists the local row is the record.
async function post(row: ServiceFeedback) {
  if ((await dataMode()) !== "api") return;
  try {
    await fetch(`${API_BASE}/api/customers/${encodeURIComponent(row.customer_id)}/service-feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(row),
    });
  } catch {
    // offline or endpoint missing: keep the local row
  }
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useServiceFeedback(): ServiceFeedback[] {
  return useSyncExternalStore(subscribe, read, () => []);
}
