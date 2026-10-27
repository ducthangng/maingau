import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseDecisions, REJECT_REASONS, rejectText, toRequest, type Decision } from "./decisions";

// What a reject / override sends to POST /api/customers/{id}/decision: the coded reason
// (DecisionRequest.reason_code) the feedback memory acts on, not only a free-text note.

const SCHEMA = fileURLToPath(new URL("../../../docs/schema/decision_request.schema.json", import.meta.url));

const base: Decision = {
  id: "MG-TEST-1@2026-10-27T09:00:00.000Z",
  customer_id: "MG-TEST-1",
  action: "rejected",
  tuple_id: "P-EN-02|email|sie",
  from_tuple: "P-EN-02|email|sie",
  reason: "Already has it",
  reason_code: "already_has_product",
  reviewer: "demo-marketer",
  ts: "2026-10-27T09:00:00.000Z",
  delta_clv: 12.5,
  p_accept: 0.1,
  group: null,
  holdout: false,
};

describe("decision request", () => {
  it("sends the reason code with a reject", () => {
    expect(toRequest(base)).toEqual({
      action: "reject",
      user: "demo-marketer",
      reason: "Already has it",
      reason_code: "already_has_product",
      tuple: { offer_id: "P-EN-02", channel: "email", tone: "sie" },
    });
  });

  it("sends the reason code and the chosen tuple with an override", () => {
    const d: Decision = { ...base, action: "overridden", tuple_id: "P-EN-02|sms|du", reason: "Better channel for this customer", reason_code: "wrong_channel" };
    expect(toRequest(d)).toMatchObject({
      action: "override",
      reason_code: "wrong_channel",
      tuple: { offer_id: "P-EN-02", channel: "sms", tone: "du" },
    });
  });

  it("sends no code with an approval", () => {
    expect(toRequest({ ...base, action: "approved", reason: null, reason_code: null })).toMatchObject({ action: "approve", reason_code: null });
  });

  it("still loads a decision stored before reason codes", () => {
    const old: Record<string, unknown> = { ...base, reason: "customer asked not to be contacted" };
    delete old.reason_code;
    const [d] = parseDecisions(JSON.stringify([old]));
    expect(d.customer_id).toBe("MG-TEST-1");
    expect(d.reason_code).toBeUndefined();
    expect(toRequest(d)).toMatchObject({ action: "reject", reason: "customer asked not to be contacted", reason_code: null });
    expect(parseDecisions(null)).toEqual([]);
  });
});

describe("reject reasons", () => {
  it("offer exactly the API's reason codes, in plain words", () => {
    const schema = JSON.parse(readFileSync(SCHEMA, "utf8"));
    const codes = schema.properties.reason_code.anyOf.find((s: { enum?: string[] }) => s.enum).enum;
    expect(Object.keys(REJECT_REASONS)).toEqual(codes);
    expect(Object.values(REJECT_REASONS)).toEqual([
      "Already has it",
      "Customer upset",
      "No time right now",
      "Not relevant",
      "Wrong channel",
      "Wrong timing",
      "Data looks wrong",
      "Other",
    ]);
  });

  it("keep the label and the optional note as the reason text", () => {
    expect(rejectText("no_time", "  ")).toBe("No time right now");
    expect(rejectText("wrong_channel", " prefers letters ")).toBe("Wrong channel: prefers letters");
    expect(rejectText("other", "moving abroad")).toBe("moving abroad");
    expect(rejectText("other", "")).toBe("Other");
  });
});
