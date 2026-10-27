import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { IndexRow } from "../../types/contracts";
import { type Decision, isHoldout } from "../../lib/decisions";
import { matches, EMPTY_FILTERS } from "../worklist/model";
import { assess, buildGroups, defaultCampaignName, filterLabel, filterRows, hasFilter, planCampaign, readFilter } from "./model";

// Groups filtered to one action and segment from the Overview, and "Approve everything", over the real export.

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const filter = (q: string) => readFilter(new URLSearchParams(q));
const decision = (customer_id: string, action: Decision["action"], tuple: string): Decision => ({
  id: `${customer_id}@t`,
  customer_id,
  action,
  tuple_id: tuple,
  from_tuple: tuple,
  reason: action === "approved" ? null : "test",
  reviewer: "demo-marketer",
  ts: "2026-10-27T09:00:00.000Z",
  delta_clv: null,
  p_accept: null,
  group: null,
  holdout: false,
});

describe("Groups filter", () => {
  it("keeps one action and segment, like the Worklist's matches()", () => {
    const a2 = filterRows(rows, filter("offer=P-EN-02&arch=A2&pers=yes"));
    expect(a2).toHaveLength(42);
    expect(filterRows(rows, filter("offer=P-EN-01&pers=no"))).toHaveLength(79);
    for (const q of ["offer=P-EN-02&arch=A2&pers=yes", "offer=P-EN-01&pers=no", "offer=P-MO-01", "arch=A3"]) {
      const f = filter(q);
      expect(filterRows(rows, f).length, q).toBe(rows.filter((r) => matches(r, { ...EMPTY_FILTERS, ...f })).length);
    }
  });

  it("shows the channel and tone groups of that action, with only that segment's customers", () => {
    const { sales, service, noAction } = buildGroups(filterRows(rows, filter("offer=P-EN-02&arch=A2&pers=yes")));
    expect(sales.length).toBeGreaterThan(1);
    expect(sales.every((g) => g.tuple.startsWith("P-EN-02|"))).toBe(true);
    expect(sales.flatMap((g) => g.rows).every((r) => r.archetype === "A2" && r.personalised === true)).toBe(true);
    expect(sales.reduce((n, g) => n + g.rows.length, 0)).toBe(42);
    expect([service.length, noAction]).toEqual([0, 0]);
  });

  it("no filter shows everything", () => {
    const f = filter("tuple=P-EN-02|email|sie");
    expect(hasFilter(f)).toBe(false);
    expect(filterRows(rows, f)).toHaveLength(rows.length);
  });

  it("names the filter and the prefilled campaign", () => {
    expect(filterLabel(filter("offer=P-EN-02&arch=A2&pers=yes"), rows)).toBe("StromGarant · A2 Traditional energy loyalist");
    expect(filterLabel(filter("offer=P-EN-01&pers=no"), rows)).toBe("StromAktiv · Not personalised");
    expect(filterLabel(filter(""), rows)).toBe("All actions");
    const day = new Date(2026, 9, 27);
    expect(defaultCampaignName(filter("offer=P-EN-02&arch=A2&pers=yes"), rows, day)).toBe("StromGarant · A2 · 27 Oct 2026");
    expect(defaultCampaignName(filter(""), rows, day)).toBe("All actions · 27 Oct 2026");
  });
});

describe("planCampaign", () => {
  const groups = buildGroups(filterRows(rows, filter("offer=P-EN-02&arch=A2&pers=yes"))).sales;
  const all = buildGroups(rows).sales;
  const none = new Map<string, Decision>();

  it("splits the included customers into control group and contacted at 0, 10 and 50 %", () => {
    const at = [0, 10, 50].map((pct) => planCampaign(groups, none, pct));
    for (const [i, pct] of [0, 10, 50].entries()) {
      const plan = at[i];
      expect(plan.holdout + plan.contacted, `${pct}%`).toBe(plan.included.length);
      expect(plan.included.filter((m) => m.holdout).every((m) => isHoldout(m.row.customer_id, pct))).toBe(true);
      expect(plan.included.filter((m) => !m.holdout).some((m) => isHoldout(m.row.customer_id, pct))).toBe(false);
      expect(plan.included.length + plan.secondLook + plan.skipped).toBe(42);
    }
    expect(at[0].holdout).toBe(0);
    expect(at[0].included.length).toBe(at[2].included.length);
    expect(at[2].holdout).toBeGreaterThan(at[1].holdout);
    expect(at[0].groups).toBe(new Set(at[0].included.map((m) => m.tuple)).size);
  });

  it("sums the expected ΔCLV of the contacted only", () => {
    const plan = planCampaign(groups, none, 10);
    const sum = plan.included.filter((m) => !m.holdout).reduce((n, m) => n + (m.row.delta_clv ?? 0), 0);
    expect(plan.delta_clv).toBeCloseTo(sum, 6);
  });

  it("never includes a customer who needs a second look or is do-no-harm", () => {
    const plan = planCampaign(all, none, 10);
    expect(plan.secondLook).toBeGreaterThan(0);
    for (const m of plan.included) expect(assess(m.row, false, undefined, m.tuple).gate).toBe("ready");
    const total = all.reduce((n, g) => n + g.rows.length, 0);
    expect(plan.included.length + plan.secondLook).toBe(total);
  });

  it("skips customers already approved for the tuple; a reject moves them to second look", () => {
    const base = planCampaign(groups, none, 10);
    const [a, b] = base.included;
    const latest = new Map([
      [a.row.customer_id, decision(a.row.customer_id, "approved", a.tuple)],
      [b.row.customer_id, decision(b.row.customer_id, "rejected", b.tuple)],
    ]);
    const plan = planCampaign(groups, latest, 10);
    expect(plan.skipped).toBe(1);
    expect(plan.secondLook).toBe(base.secondLook + 1);
    expect(plan.included.length).toBe(base.included.length - 2);
    expect(plan.included.some((m) => m.row.customer_id === a.row.customer_id || m.row.customer_id === b.row.customer_id)).toBe(false);
  });
});
