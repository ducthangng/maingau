import { describe, expect, it } from "vitest";
import { type MemberOutcome, outcomeTotals, seeded } from "./outcomes";

describe("outcomes", () => {
  it("draws the same numbers for the same campaign and customer", () => {
    const a = seeded("CMP-1|MG-100001");
    const b = seeded("CMP-1|MG-100001");
    const c = seeded("CMP-2|MG-100001");
    const x = a();
    expect(x).toBe(b());
    expect(x).toBeGreaterThanOrEqual(0);
    expect(x).toBeLessThan(1);
    expect(c()).not.toBe(x);
  });

  it("sums the simulated sends only: the control group has no actual ΔCLV", () => {
    const rows: MemberOutcome[] = [
      { customer_id: "A", tuple_id: "P|email|du", contacted: true, status: "bought", p: 0.4, expected_delta_clv: 10, actual_delta_clv: 30 },
      { customer_id: "B", tuple_id: "P|email|du", contacted: true, status: "not_bought", p: 0.2, expected_delta_clv: 5, actual_delta_clv: -2.5 },
      { customer_id: "C", tuple_id: "P|email|du", contacted: false, status: "control" },
      { customer_id: "D", tuple_id: "P|email|du", contacted: true, status: "not_valued" },
    ];
    expect(outcomeTotals(rows)).toEqual({
      members: 4, contacted: 3, simulated: 2, control: 1, not_valued: 1, bought: 1,
      expected_bought: 0.6, expected_delta_clv: 15, actual_delta_clv: 27.5,
    });
  });
});
