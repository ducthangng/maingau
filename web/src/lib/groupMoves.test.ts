import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { planCampaign } from "../components/groups/model";
import type { IndexRow } from "../types/contracts";
import { applyMoves, groupView, latestMoves, movedFromLabel, parseMoves, type GroupMove } from "./groupMoves";

// Group membership after a person's Remove / Change to this group (the group page, /group/:tuple).

const row = (id: string, tuple: string, delta = 10) =>
  ({ customer_id: id, chosen_tuple: tuple, chosen_offer: tuple.split("|")[0], channel: tuple.split("|")[1], tone: tuple.split("|")[2], delta_clv: delta, p_accept: 0.1 }) as IndexRow;
const move = (m: Partial<GroupMove> & Pick<GroupMove, "customer_id" | "from" | "to">): GroupMove =>
  ({ reason: null, ts: "2026-10-27T10:00:00Z", delta_clv: null, p_accept: null, ...m });

const A = "P-EN-02|email|sie";
const B = "P-EN-02|app_push|du";

describe("group moves", () => {
  const rows = [row("C1", A), row("C2", A), row("C3", A)];

  it("keeps the engine's rows when nobody moved anyone", () => {
    const out = applyMoves(rows, new Map());
    expect(out.rows.map((r) => r.chosen_tuple)).toEqual([A, A, A]);
    expect(out.removed).toEqual([]);
  });

  it("moves a customer to the picked option's group with its valuation, and remembers where they came from", () => {
    const moves = latestMoves([move({ customer_id: "C1", from: A, to: B, reason: "Better channel", delta_clv: 42, p_accept: 0.3 })]);
    const c1 = applyMoves(rows, moves).rows.find((r) => r.customer_id === "C1")!;
    expect(c1).toMatchObject({ chosen_tuple: B, channel: "app_push", tone: "du", delta_clv: 42, p_accept: 0.3, engine_tuple: A });
    expect(movedFromLabel(c1)).toMatch(/^Moved by a person from .+ · E-mail · Sie: Better channel$/);
  });

  it("takes a removed customer out of every group; the latest move wins (restore)", () => {
    const removed = latestMoves([move({ customer_id: "C2", from: A, to: null })]);
    const out = applyMoves(rows, removed);
    expect(out.rows.map((r) => r.customer_id)).toEqual(["C1", "C3"]);
    expect(out.removed.map((r) => r.customer_id)).toEqual(["C2"]);
    const restored = latestMoves([move({ customer_id: "C2", from: A, to: null }), move({ customer_id: "C2", from: A, to: A })]);
    expect(applyMoves(rows, restored).rows.map((r) => r.customer_id)).toEqual(["C1", "C2", "C3"]);
  });

  it("moving back to the engine's choice restores the engine's row", () => {
    const back = latestMoves([move({ customer_id: "C1", from: A, to: B }), move({ customer_id: "C1", from: B, to: A })]);
    const c1 = applyMoves(rows, back).rows.find((r) => r.customer_id === "C1")!;
    expect(c1).toEqual(rows[0]);
  });

  it("drops broken storage instead of throwing", () => {
    expect(parseMoves("not json")).toEqual([]);
    expect(parseMoves('[{"customer_id":"C1"},{"customer_id":"C2","from":"x","to":null}]')).toHaveLength(1);
  });
});

describe("group page: Remove", () => {
  // Real data: P-EN-02 via e-mail (Sie), every tier.
  const all = JSON.parse(readFileSync(fileURLToPath(new URL("../../public/data/index.json", import.meta.url)), "utf8")) as IndexRow[];
  const tuple = "P-EN-02|email|sie";
  const before = groupView(all, new Map(), new Map(), tuple, null);
  const out = before.rows[0];
  const moves = latestMoves([move({ customer_id: out.customer_id, from: tuple, to: null, reason: "Removed from the group" })]);
  const after = groupView(all, moves, new Map(), tuple, null);

  it("moves the customer from Sending to Removed", () => {
    expect(before.rows.length).toBe(11);
    expect(after.rows.map((r) => r.customer_id)).not.toContain(out.customer_id);
    expect(after.removed.map((r) => r.customer_id)).toEqual([out.customer_id]);
    expect(after.rows.length).toBe(10);
  });

  it("leaves them out of Approve group (Included, Contacted and the decisions Save & Run writes)", () => {
    const plan = planCampaign([{ tuple, rows: after.rows }], new Map(), 10, true);
    expect(plan.included.map((m) => m.row.customer_id)).not.toContain(out.customer_id);
    expect(plan.included.length).toBe(10);
    expect(plan.contacted + plan.holdout).toBe(10);
  });

  it("counts them again once restored", () => {
    const restored = latestMoves([
      move({ customer_id: out.customer_id, from: tuple, to: null }),
      move({ customer_id: out.customer_id, from: tuple, to: tuple, delta_clv: out.delta_clv ?? null, p_accept: out.p_accept ?? null }),
    ]);
    const view = groupView(all, restored, new Map(), tuple, null);
    expect(view.removed).toEqual([]);
    expect(planCampaign([{ tuple, rows: view.rows }], new Map(), 10, true).included.length).toBe(11);
  });
});

describe("group page: customers sent before", () => {
  const all = JSON.parse(readFileSync(fileURLToPath(new URL("../../public/data/index.json", import.meta.url)), "utf8")) as IndexRow[];
  const tuple = "P-EN-02|email|sie";
  const [first, second, third] = groupView(all, new Map(), new Map(), tuple, null).rows;
  const decided = (id: string, action: "approved" | "overridden" | "rejected", to = tuple, holdout = false) =>
    [id, { id: `${id}@t`, customer_id: id, action, tuple_id: to, from_tuple: tuple, reason: null, reviewer: "x", ts: "t", delta_clv: null, p_accept: null, group: null, holdout }] as const;

  it("leaves out anyone approved before (this action, another one, or the control group); a reject stays", () => {
    const latest = new Map([
      decided(first.customer_id, "approved", tuple, true),
      decided(second.customer_id, "overridden", "P-EN-01|sms|sie"),
      decided(third.customer_id, "rejected"),
    ]);
    const view = groupView(all, new Map(), latest, tuple, null);
    const ids = view.rows.map((r) => r.customer_id);
    expect(ids).not.toContain(first.customer_id);
    expect(ids).not.toContain(second.customer_id);
    expect(ids).toContain(third.customer_id);
    expect(view.sent.map((r) => r.customer_id).sort()).toEqual([first.customer_id, second.customer_id].sort());
    expect(planCampaign([{ tuple, rows: view.rows }], latest, 10, true).included.length).toBe(9);
  });

  it("keeps a removed customer who was sent before out of Removed too", () => {
    const moves = latestMoves([move({ customer_id: first.customer_id, from: tuple, to: null })]);
    const view = groupView(all, moves, new Map([decided(first.customer_id, "approved")]), tuple, null);
    expect(view.removed).toEqual([]);
    expect(view.sent.map((r) => r.customer_id)).toEqual([first.customer_id]);
  });
});
