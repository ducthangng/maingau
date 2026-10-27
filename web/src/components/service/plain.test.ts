import { describe, expect, it } from "vitest";
import type { Blocked, Candidate, CustomerCard } from "../../types/contracts";
import { blockedText, driverLabels, notRecommended, reasonOf, sortedActions } from "./plain";
import { normaliseId } from "./ViewSwitch";

// Plain-language rules of Customer 360° (prompts/ui-customer360.md §3.1, §3.4).

const blocked = (x: Partial<Blocked> & { rule_id: string }): Blocked => ({ offer_id: "*", reason: "", ...x }) as Blocked;

describe("blockedText: rule → plain text (rule_center_id first, then rule_id)", () => {
  it.each([
    [{ rule_center_id: "C-07", rule_id: "EXCL-OPEN-TICKET" }, "No sales offers while a ticket is open"],
    [{ rule_id: "EXCL-OPEN-TICKET" }, "No sales offers while a ticket is open"],
    [{ rule_center_id: "C-08", rule_id: "EXCL-CANCELLATION" }, "No sales offers: a cancellation is in progress"],
    [{ rule_id: "EXCL-AUTOSTROM-CANCELLED" }, "No sales offers: a cancellation is in progress"],
    [{ rule_center_id: "C-01", rule_id: "CONSENT-CHANNEL", channel: "outbound_call" }, "The customer has not agreed to be contacted by phone call"],
    [{ rule_center_id: "C-01", rule_id: "CONSENT-CHANNEL", channel: "sms" }, "The customer has not agreed to be contacted by SMS"],
    [{ rule_center_id: "C-01", rule_id: "CHANNEL-AVAILABLE", channel: "app_push" }, "No app"],
    [{ rule_center_id: "C-01", rule_id: "CHANNEL-AVAILABLE", channel: "portal_popup" }, "No portal account"],
    [{ rule_center_id: "C-02", rule_id: "CONSENT-CHANNEL" }, "Newsletter: double opt-in not confirmed"],
    [{ rule_center_id: "C-03", rule_id: "CONSENT-CHANNEL" }, "The customer unsubscribed from the newsletter"],
    [{ rule_center_id: "C-05", rule_id: "CONSENT-PROFILING" }, "No personalised offers (no consent for personalisation)"],
    [{ rule_center_id: "B-07", rule_id: "HOLDING-PRECONDITION", reason: "Wallbox-Integration (from S3): needs HEMS gateway" }, "Needs HEMS gateway"],
    [{ rule_center_id: "B-02", rule_id: "CONTACT-CAP", until: "2026-10-14T09:00:00" }, "Contact limit reached, possible from 14 Oct 2026"],
    [{ rule_center_id: "B-01", rule_id: "BUSINESS-RULE", until: "2026-12-02" }, "Contact limit reached, possible from 2 Dec 2026"],
    [{ rule_center_id: "MEMORY", rule_id: "BUSINESS-RULE", reason: "P-SH-01: declined on 2026-09-01" }, "The customer said no to this before (declined on 2026-09-01)"],
    [{ rule_id: "ECON-NONPOSITIVE", reason: "expected ΔCLV €-1.20 ≤ 0" }, "Not worth offering now"],
    [{ rule_id: "DATA-MISSING", reason: "GasAktiv: not enough data (Gas heating is not in the data)" }, "Not enough data"],
    // rule_center_id wins over rule_id
    [{ rule_center_id: "C-07", rule_id: "CONTACT-CAP" }, "No sales offers while a ticket is open"],
  ])("%o → %s", (row, text) => {
    expect(blockedText(blocked(row))).toBe(text);
  });

  it("never names payment, whatever the engine's reason says", () => {
    const rows = [
      blocked({ rule_center_id: "C-06", rule_id: "EXCL-DUNNING", reason: "All sales blocked: dunning_level = 3" }),
      blocked({ rule_id: "EXCL-DUNNING", reason: "dunning_level = 2" }),
      blocked({ rule_center_id: "B-09", rule_id: "BUSINESS-RULE", reason: "Payment overdue (Mahnung)" }),
    ];
    for (const r of rows) {
      const t = blockedText(r);
      expect(t).toBe("No sales offers right now (account status)");
      expect(t).not.toMatch(/payment|dunning|mahn/i);
    }
  });
});

describe("notRecommended", () => {
  it("one line per offer, per channel for customer-level rows, exclusions first", () => {
    const card = {
      blocked: [
        blocked({ offer_id: "P-MO-01", channel: "newsletter_email", rule_id: "ECON-NONPOSITIVE" }),
        blocked({ offer_id: "P-MO-01", channel: "email", rule_id: "ECON-NONPOSITIVE" }),
        blocked({ offer_id: "*", channel: "sms", rule_center_id: "C-01", rule_id: "CONSENT-CHANNEL" }),
        blocked({ offer_id: "P-IN-01", rule_id: "DATA-MISSING" }),
        blocked({ offer_id: "*", rule_center_id: "C-07", rule_id: "EXCL-OPEN-TICKET" }),
      ],
    } as unknown as CustomerCard;
    const lines = notRecommended(card);
    expect(lines).toHaveLength(4);
    expect(lines[0]).toEqual({ subject: "All sales offers", text: "No sales offers while a ticket is open" });
    expect(lines.find((l) => l.subject === "SMS")?.text).toBe("The customer has not agreed to be contacted by SMS");
    expect(lines.filter((l) => l.text === "Not worth offering now")).toHaveLength(1);
    expect(lines.at(-1)?.text).toBe("Not enough data");
  });
});

describe("sortedActions", () => {
  const cand = (offer_id: string, action_type: string, delta: number) =>
    ({ offer_id, tuple_id: `${offer_id}|x|sie`, action_type, valuation: { delta_clv: delta } }) as unknown as Candidate;
  const candidates = [cand("P-EN-02", "retention", 20), cand("P-SV-01", "service", 5), cand("P-MO-01", "sales", 30)];

  it("sorts by expected ΔCLV, highest first", () => {
    const card = { candidates, timeline: [] } as unknown as CustomerCard;
    expect(sortedActions(card).map((c) => c.offer_id)).toEqual(["P-MO-01", "P-EN-02", "P-SV-01"]);
  });

  it("puts service actions first while a ticket is open", () => {
    const card = { candidates, timeline: [{ kind: "service", flags: ["open"] }] } as unknown as CustomerCard;
    expect(sortedActions(card).map((c) => c.offer_id)).toEqual(["P-SV-01", "P-MO-01", "P-EN-02"]);
  });
});

describe("reasons and CLV drivers stay plain", () => {
  it("drops signal codes and the trailing parenthesis", () => {
    const c = { why: ["bought a Wallbox 11 kW on 2025-08-14 but has no Autostrom contract [S3]"] } as unknown as Candidate;
    expect(reasonOf(c)).toBe("bought a Wallbox 11 kW on 2025-08-14 but has no Autostrom contract");
    const g = { why: ["Generic catalog offer, the same for every customer (owns: StromAktiv)"] } as unknown as Candidate;
    expect(reasonOf(g)).toBe("Generic catalog offer, the same for every customer");
  });

  it("replaces payment wording in reasons and churn drivers", () => {
    expect(reasonOf({ why: ["dunning_level = 3 [S13]"] } as unknown as Candidate)).toBe("account status needs attention first");
    const card = {
      profile: { value_risk: { churn_drivers: [{ label: "price guarantee ends <90d" }, { label: "dunning level 3" }, { label: "2 tickets in 12m" }] } },
    } as unknown as CustomerCard;
    expect(driverLabels(card)).toEqual(["price guarantee ends <90d", "account status", "2 tickets in 12m"]);
  });
});

describe("customer search", () => {
  it("normalises typed IDs", () => {
    expect(normaliseId("100023")).toBe("MG-100023");
    expect(normaliseId(" mg-100023 ")).toBe("MG-100023");
  });
});
