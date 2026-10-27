import { describe, expect, it, vi } from "vitest";

// Rows recorded by the Mentioned / Interested / Declined buttons must have the exact shape of the
// workbook table service_nba_feedback (prompts/ui-customer360.md §3.4), because nba.ai.feedback reads them.
vi.mock("./data", () => ({ API_BASE: "", dataMode: async () => "static" }));

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => storage.get(k) ?? null,
  setItem: (k: string, v: string) => void storage.set(k, v),
});
vi.stubGlobal("window", new EventTarget());

const { recordReaction } = await import("./serviceFeedback");
const { REVIEWER } = await import("./decisions");

const FIELDS = [
  "agent_action", "agent_id", "channel", "converted_within_14d", "customer_id", "customer_reaction", "dismiss_reason",
  "feedback_id", "offer_mentioned_to_customer", "shown_at", "suggested_offer_id", "suggestion_source", "ticket_id",
];

const base = { customer_id: "MG-100186", offer_id: "P-SV-01", channel: "phone" as const, ticket_id: "TK-200745" };

describe("recordReaction", () => {
  it("writes a service_nba_feedback row", () => {
    const row = recordReaction({ ...base, reaction: "interested", reason: null });
    expect(Object.keys(row).sort()).toEqual(FIELDS);
    expect(row).toMatchObject({
      ticket_id: "TK-200745",
      customer_id: "MG-100186",
      channel: "phone",
      suggestion_source: "nba_engine",
      suggested_offer_id: "P-SV-01",
      agent_id: REVIEWER,
      agent_action: "accepted",
      dismiss_reason: null,
      offer_mentioned_to_customer: true,
      customer_reaction: "interested",
      converted_within_14d: null,
    });
    expect(row.feedback_id).toMatch(/^SF-\d+$/);
    expect(Number.isNaN(Date.parse(row.shown_at))).toBe(false);
  });

  it.each([
    ["mentioned", null, "accepted", null, null],
    ["declined", null, "dismissed", null, "declined"],
    ["declined", "no_time", "dismissed", "no_time", "declined"],
    ["declined", "customer_upset", "dismissed", "customer_upset", "annoyed"],
  ] as const)("%s (%s) → agent_action %s, dismiss_reason %s, reaction %s", (reaction, reason, action, dismiss, customerReaction) => {
    const row = recordReaction({ ...base, reaction, reason });
    expect(row.agent_action).toBe(action);
    expect(row.dismiss_reason).toBe(dismiss);
    expect(row.customer_reaction).toBe(customerReaction);
  });

  it("keeps every row in localStorage (maingau.serviceFeedback.v1)", () => {
    const before = JSON.parse(storage.get("maingau.serviceFeedback.v1") ?? "[]").length;
    recordReaction({ ...base, ticket_id: null, channel: "chat", reaction: "mentioned", reason: null });
    const saved = JSON.parse(storage.get("maingau.serviceFeedback.v1") ?? "[]");
    expect(saved).toHaveLength(before + 1);
    expect(saved.at(-1)).toMatchObject({ channel: "chat", ticket_id: null, agent_action: "accepted" });
  });
});
