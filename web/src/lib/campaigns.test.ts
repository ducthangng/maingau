import { describe, expect, it, vi } from "vitest";
import type { Campaign } from "./campaigns";

// Campaign store (maingau.campaigns.v1): survives bad JSON and blocked storage.

const storage = new Map<string, string>();
let blocked = false;
vi.stubGlobal("localStorage", {
  getItem: (k: string) => storage.get(k) ?? null,
  setItem: (k: string, v: string) => {
    if (blocked) throw new Error("QuotaExceededError");
    storage.set(k, v);
  },
});
vi.stubGlobal("window", new EventTarget());

const { parseCampaigns, saveCampaign } = await import("./campaigns");

const campaign = (id: string): Campaign => ({
  id,
  name: `StromGarant · A2 · ${id}`,
  created_at: "2026-10-27T09:00:00.000Z",
  reviewer: "demo-marketer",
  offer: "P-EN-02",
  arch: "A2",
  pers: "yes",
  scope: "StromGarant · A2 Traditional energy loyalist",
  holdout_pct: 10,
  groups: ["P-EN-02|email|sie"],
  customers: 30,
  contacted: 27,
  holdout: 3,
  delta_clv: 312.5,
});

describe("campaign store", () => {
  it("tolerates bad JSON and drops entries without an id and a name", () => {
    expect(parseCampaigns(null)).toEqual([]);
    expect(parseCampaigns("{not json")).toEqual([]);
    expect(parseCampaigns('{"id":"x"}')).toEqual([]);
    expect(parseCampaigns(JSON.stringify([campaign("C1"), null, 3, { id: "C2" }]))).toEqual([campaign("C1")]);
  });

  it("saves campaigns in order and reads them back", () => {
    saveCampaign(campaign("C1"));
    saveCampaign(campaign("C2"));
    expect(parseCampaigns(storage.get("maingau.campaigns.v1") ?? null).map((c) => c.id)).toEqual(["C1", "C2"]);
  });

  it("keeps working when storage is blocked", () => {
    blocked = true;
    expect(() => saveCampaign(campaign("C3"))).not.toThrow();
    blocked = false;
  });
});
