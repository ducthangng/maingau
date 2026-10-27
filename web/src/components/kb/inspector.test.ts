import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { KnowledgeBase } from "../../lib/kb";
import { rulesOf, upstream } from "./NodeInspector";
import { explain, story } from "./explain";

// Against the real export (public/data/kg_viz.json): the path and the rules the Selected panel shows per box.
const kb = JSON.parse(readFileSync(new URL("../../../public/data/kg_viz.json", import.meta.url), "utf-8")) as KnowledgeBase;

function box(cid: string, id: string) {
  const c = kb.customers[cid];
  const node = c.graph.nodes.find((n) => n.id === id)!;
  return { c, node, ids: rulesOf(node, c.graph, kb, c).map((r) => r.id) };
}

describe("node inspector", () => {
  it("traces a box back to the customer", () => {
    const g = kb.customers["MG-100023"].graph;
    const t = upstream(g, "consent:portal_app_personalisation");
    for (const id of ["MG-100023", "order:SO-900005", "sig:S3", "need:N-EV-CHARGING", "offer:P-AS-01", "ch:portal_popup"]) expect(t.has(id)).toBe(true);
  });

  it("names the rules that blocked or held back a box", () => {
    expect(box("MG-100023", "offer:P-EN-01").ids).toContain("B-07");
    expect(box("MG-100023", "ch:email").ids).toEqual(["C-01"]); // no consent
    expect(box("MG-100023", "ch:newsletter_email").ids).toEqual(["B-01"]); // over the e-mail limit, waits
    expect(box("MG-100026", "ch:newsletter_email").ids).toContain("B-02"); // "waits → date" line: the contact cap behind it
    expect(box("MG-100096", "offer:P-SL-01").ids).toContain("C-06"); // dunning: a rule box blocks the offer
    expect(box("MG-100023", "offer:P-AS-01").ids).not.toContain("C-01");
  });

  it("shows no rule on the chosen consent", () => {
    expect(box("MG-100023", "consent:portal_app_personalisation").ids).toEqual([]);
  });

  it("explains a box in plain words", () => {
    const say = (cid: string, id: string) => {
      const { c, node } = box(cid, id);
      const e = explain(node, c.graph, kb, c);
      return `${e.what} ${e.why ?? ""}`;
    };
    expect(say("MG-100023", "offer:P-AS-01")).toMatch(/^Chosen as the next best action: MAINGAU Autostrom through portal pop-up\./);
    expect(say("MG-100023", "offer:P-EN-01")).toContain("“Never offer what they own”");
    expect(say("MG-100023", "ch:email")).toContain("withdrawn on 2 Apr 2024");
    expect(say("MG-100096", "offer:P-SL-01")).toContain("dunning level 3");
    expect(say("MG-100112", "offer:P-SH-01")).toContain("expected gain is not positive");
    // no engine codes or ISO dates leak into the sentences
    for (const c of Object.values(kb.customers))
      for (const n of c.graph.nodes) expect(say(c.id, n.id)).not.toMatch(/\[S\d+\]|\d{4}-\d{2}-\d{2}|_[a-z]/);
  });

  it("tells the route from the customer to the box", () => {
    const steps = story(kb.customers["MG-100023"].graph, "ch:portal_popup", kb);
    expect(steps.map((s) => s.verb)).toEqual(["placed", "is evidence for", "points to", "is answered by", "is sent through"]);
  });
});
