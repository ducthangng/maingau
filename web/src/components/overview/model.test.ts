import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { IndexRow, Summary } from "../../types/contracts";
import { matches } from "../worklist/model";
import {
  NOT_PERSONALISED,
  SERVICE_LINK,
  buildOverview,
  largestRemainder,
  linkFilters,
  reasonLine,
  segmentLink,
  type ActionStat,
} from "./model";

// Overview model over the real static export (prompts/ui-overview.md §3, §8, §9).

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const summary = JSON.parse(readFileSync(`${DATA}summary.json`, "utf8")) as Summary;
const overview = buildOverview(rows);
const action = (offer: string) => overview.actions.find((a) => a.offer === offer) as ActionStat;
const seg = (a: ActionStat, key: string) => a.segments.find((s) => s.key === key)!;

describe("largestRemainder", () => {
  it("adds up to exactly 100", () => {
    expect(largestRemainder([1, 1, 1])).toEqual([34, 33, 33]);
    expect(largestRemainder([44, 8, 6, 6, 2])).toEqual([67, 12, 9, 9, 3]);
    expect(largestRemainder([2, 1, 0]).reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("gives zeros when there is nothing to split", () => {
    expect(largestRemainder([0, 0])).toEqual([0, 0]);
  });
});

describe("actions match the summary", () => {
  it("every action equals summary.chosen_by_offer (count and ΔCLV)", () => {
    for (const a of overview.actions) {
      const s = summary.chosen_by_offer?.[a.offer] as { count: number; sum_delta_clv: number } | undefined;
      expect(s, a.offer).toBeDefined();
      expect(a.customers, a.offer).toBe(s!.count);
      expect(a.total, a.offer).toBeCloseTo(s!.sum_delta_clv, 6);
    }
  });

  it("totals: 11 actions, 617 customers, +€7,250; 47 service cases; NO_ACTION nowhere", () => {
    expect(overview.actions).toHaveLength(11);
    expect(overview.customers).toBe(617);
    expect(Math.round(overview.total)).toBe(7250);
    expect(overview.service).toBe(47);
    const noAction = rows.filter((r) => r.chosen_offer === "NO_ACTION").length;
    expect(noAction).toBe(86);
    expect(overview.customers + overview.service + noAction).toBe(rows.length);
    expect(overview.actions.map((a) => a.offer)).not.toContain("NO_ACTION");
  });

  it("ranks the actions as in the acceptance table", () => {
    expect(overview.actions.map((a) => [a.name, a.customers, Math.round(a.total)])).toEqual([
      ["StromAktiv", 175, 2684],
      ["Mobil S/M/L", 201, 1978],
      ["HEMS Starter-Set", 128, 1245],
      ["StromGarant", 63, 953],
      ["StromWärme", 6, 129],
      ["Zusatz-SIM", 21, 121],
      ["HEMS Speicher-Optimierung", 9, 77],
      ["Wallbox-Integration", 5, 31],
      ["MAINGAU Autostrom", 5, 21],
      ["Dynamischer Stromtarif", 3, 8],
      ["Mobil Upgrade", 1, 3],
    ]);
    expect(action("P-EN-01").waiting).toBe(49);
    expect(action("P-MO-01").waiting).toBe(46);
  });
});

describe("reasons", () => {
  const keys = (offer: string) => action(offer).reasons.map((r) => [r.key, r.count]);

  it("counts the signal → need behind each action, general offers apart", () => {
    expect(keys("P-EN-01")).toEqual([["S11|N-HOME-ELECTRICITY", 96], ["no-profiling", 79]]);
    expect(keys("P-MO-01")).toEqual([["no-profiling", 201]]);
    expect(keys("P-SL-01")).toEqual([["no-profiling", 102], ["S7|N-ENERGY-MANAGEMENT", 25], ["S1|N-HEAT-PUMP", 1]]);
    expect(keys("P-EN-02")).toEqual([["S4|N-PRICE-SECURITY", 63]]);
    expect(keys("P-EN-03")).toEqual([["S1|N-HEAT-PUMP", 6]]);
  });

  it("shows labels, never a signal code, outside the tooltip", () => {
    for (const a of overview.actions) {
      for (const r of a.reasons) {
        const line = reasonLine(r, summary);
        expect(line.text, `${a.offer} ${r.key}`).not.toMatch(/\bS\d{1,2}\b|\bN-[A-Z]/);
        expect(line.missing, `${a.offer} ${r.key}`).toBe(false);
        expect(line.title).toContain(`${r.count} customer`);
        if (r.signal) expect(line.title).toContain(r.signal);
      }
    }
    expect(reasonLine(action("P-EN-03").reasons[0], summary).text).toBe("Gas meter deregistered → Heat pump / electric heating");
    expect(reasonLine(action("P-EN-02").reasons[0], summary).text).toBe("Price guarantee ends within 90 days → Price certainty");
  });

  it("an older export without reason fields reads 'not enough data'", () => {
    const old = buildOverview(rows.map((r) => ({ ...r, reason_signal: null, reason_need: null })));
    const line = reasonLine(old.actions.find((a) => a.offer === "P-EN-02")!.reasons[0], summary);
    expect(line).toMatchObject({ text: "not enough data", missing: true });
  });
});

describe("segments", () => {
  it("both percentage columns add up to 100 for every action", () => {
    for (const a of overview.actions) {
      expect(a.segments.reduce((n, s) => n + s.customersPct, 0), a.offer).toBe(100);
      expect(a.segments.reduce((n, s) => n + s.totalPct, 0), a.offer).toBe(100);
      expect(a.segments.reduce((n, s) => n + s.customers, 0), a.offer).toBe(a.customers);
      expect(a.segments).toHaveLength(7);
    }
  });

  it("StromGarant splits as in the acceptance table, empty segments last", () => {
    const a = action("P-EN-02");
    expect(a.segments.map((s) => [s.key, s.customers, s.customersPct, Math.round(s.total), s.totalPct])).toEqual([
      ["A2", 42, 67, 516, 54],
      ["A3", 8, 13, 170, 18],
      ["A1", 6, 9, 148, 16],
      ["A5", 5, 8, 76, 8],
      ["A0", 2, 3, 42, 4],
      ["A4", 0, 0, 0, 0],
      [NOT_PERSONALISED, 0, 0, 0, 0],
    ]);
  });

  it("StromAktiv: A3 and Not personalised", () => {
    const a = action("P-EN-01");
    expect([seg(a, "A3").customers, seg(a, "A3").customersPct, Math.round(seg(a, "A3").total), seg(a, "A3").totalPct]).toEqual([96, 55, 1504, 56]);
    const np = seg(a, NOT_PERSONALISED);
    expect([np.customers, np.customersPct, Math.round(np.total), np.totalPct]).toEqual([79, 45, 1180, 44]);
  });
});

describe("Worklist links", () => {
  it("each segment link filters the Worklist to exactly that segment's customers", () => {
    for (const a of overview.actions) {
      for (const s of a.segments.filter((x) => x.customers > 0)) {
        const link = segmentLink(a.offer, s.key);
        expect(link).toContain("queue=all");
        const f = linkFilters(link);
        expect(rows.filter((r) => matches(r, f)).length, link).toBe(s.customers);
      }
    }
  });

  it("uses pers=yes for A segments and pers=no for Not personalised", () => {
    expect(segmentLink("P-EN-01", "A3")).toBe("/worklist?offer=P-EN-01&arch=A3&pers=yes&queue=all");
    expect(segmentLink("P-EN-01", NOT_PERSONALISED)).toBe("/worklist?offer=P-EN-01&pers=no&queue=all");
    expect(rows.filter((r) => matches(r, linkFilters(segmentLink("P-EN-01", NOT_PERSONALISED)))).length).toBe(79);
  });

  it("the service line opens all service cases", () => {
    expect(rows.filter((r) => matches(r, linkFilters(SERVICE_LINK))).length).toBe(overview.service);
  });
});
