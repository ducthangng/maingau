import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import Layout from "../Layout";
import { describe, expect, it } from "vitest";
import type { IndexRow, Summary } from "../../types/contracts";
import ActionTable from "./ActionTable";
import { channelLabel, confidenceRate, tierBuckets } from "./ActionGroups";
import TierSheet from "./TierSheet";
import { groupLink } from "./model";
import { buildGroups, type Group } from "../groups/model";
import { buildOverview, reasonLine, type ActionStat } from "./model";

// What a marketer sees on the Overview (prompts/ui-overview.md §4–§5), rendered from the real export.

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const summary = JSON.parse(readFileSync(`${DATA}summary.json`, "utf8")) as Summary;
const model = buildOverview(rows);
const groups = new Map<string, Group[]>();
for (const g of buildGroups(rows).sales) {
  const offer = g.rows[0].chosen_offer!;
  groups.set(offer, [...(groups.get(offer) ?? []), g]);
}

function render(open: string | null, actions: ActionStat[] = model.actions) {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <ActionTable
        actions={actions}
        summary={summary}
        groups={groups}
        open={open}
        onToggle={() => {}}
        onOpenTier={() => {}}
      />
    </MemoryRouter>,
  );
  return { html, visible: visibleText(html) };
}

function visibleText(html: string) {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#x27;/g, "'")
    .replace(/\s+/g, " ");
}

describe("action table", () => {
  const { html, visible } = render(null);

  it("shows offer names, whole-euro totals and plain reasons", () => {
    expect(visible).toContain("StromAktiv");
    expect(visible).toContain("+€2,684");
    expect(visible).toContain("Autostrom without home electricity → Home electricity for an EV driver");
    expect(visible).not.toContain("No need signal");
    expect(visible).not.toContain("general offer");
  });

  it("keeps signal codes, offer IDs and counts in tooltips only", () => {
    expect(visible).not.toMatch(/\bS\d{1,2}\b|\bP-[A-Z]{2}-\d{2}\b|\bN-[A-Z]/);
    expect(html).toContain('title="S11 → N-HOME-ELECTRICITY · 96 customers"');
    expect(html).toContain('title="P-EN-01"');
  });

  it("tells how many wait for a contact limit", () => {
    expect(html).toContain("49 of them wait for a contact limit");
  });

  it("opens no group list until a row is chosen", () => {
    expect(html).not.toContain("groups-");
  });

  it("draws no bar under the expected ΔCLV", () => {
    expect(html).not.toContain("h-1.5 w-full overflow-hidden rounded-full");
  });
});

describe("urgency tiers", () => {
  const { html, visible } = render("P-EN-02");

  it("lists the action's tiers as on the Worklist; tiers without customers are not shown", () => {
    expect([...html.matchAll(/data-overview-tier="(P\d)"/g)].map((m) => m[1])).toEqual(["P2", "P3"]);
    expect(visible).toMatch(/P2 .*P3/);
    expect(visible).not.toMatch(/\bP1\b|\bP4\b|\bP5\b/);
    expect(html).toContain("Show the 11 groups of P2");
    expect(html).toContain("Show the 8 groups of P3");
  });

  it("splits the action's groups by tier, sorted by channel", () => {
    const buckets = tierBuckets(groups.get("P-EN-02")!);
    expect(buckets.map((b) => b.rows.length)).toEqual([0, 27, 36, 0, 0]);
    const p3 = buckets[2].groups.map((g) => channelLabel(g.tuple));
    expect(p3).toEqual([...p3].sort((a, b) => a.localeCompare(b)));
    expect(p3[0]).toBe("App push · Du");
    expect(buckets[2].groups[0].rows.length).toBe(7);
  });

  it("shows the confidence rate of each group, breakdown in the tooltip", () => {
    expect(visible).toContain("Confidence");
    expect(html).toMatch(/title="Confidence \(high or medium\) · \d+ high · \d+ medium · \d+ low/);
    expect(confidenceRate([])).toMatchObject({ pct: null });
    const rows3 = [{ confidence: "high" }, { confidence: "low" }, { confidence: null }] as IndexRow[];
    expect(confidenceRate(rows3)).toEqual({ pct: 50, title: "Confidence (high or medium) · 1 high · 0 medium · 1 low · 1 unknown" });
  });

  it("opens a sheet with the tier's Offer · Channel · Tone groups, each linking to its group page", () => {
    const action = model.actions.find((a) => a.offer === "P-EN-02")!;
    const bucket = tierBuckets(groups.get("P-EN-02")!)[2];
    const sheet = renderToStaticMarkup(
      <MemoryRouter>
        <TierSheet action={action} bucket={bucket} summary={summary} latest={new Map()} onClose={() => {}} />
      </MemoryRouter>,
    );
    expect(sheet.match(/data-tier-group=/g)?.length).toBe(8);
    expect(visibleText(sheet)).toContain("P-EN-02 · App push · Du");
    expect(sheet).toContain('href="/group/P-EN-02%7Capp_push%7Cdu?tier=P3"');
    expect(visibleText(sheet)).toMatch(/\d+ ready/);
    expect(groupLink("P-EN-02|email|sie")).toBe("/group/P-EN-02%7Cemail%7Csie");
  });

  it("links the whole action to Groups from the panel header", () => {
    expect(html).toContain('href="/groups?offer=P-EN-02"');
    expect(visible).toContain("Open in Groups");
  });
});

describe("review fixes", () => {
  it("shows at most two reasons and folds the rest into '+N other reasons' with a tooltip", () => {
    const a = model.actions.find((x) => x.offer === "P-EN-01")!;
    // The no-profiling reason of P-EN-01 has no line, so one more reason fills the second slot.
    const extra = [
      { key: "S5|N-MORE-DATA", signal: "S5", need: "N-MORE-DATA", count: 4 },
      { key: "S3|N-EV-CHARGING", signal: "S3", need: "N-EV-CHARGING", count: 3 },
      { key: "S9|N-DYNAMIC-TARIFF", signal: "S9", need: "N-DYNAMIC-TARIFF", count: 2 },
    ];
    const { html, visible } = render(null, [{ ...a, reasons: [...a.reasons, ...extra] }]);
    expect(visible).toContain("+2 other reasons");
    expect(visible).not.toContain("Wallbox bought, no Autostrom");
    expect(html).toMatch(/title="[^"]*S3 → N-EV-CHARGING · 3 customers[^"]*S9 → N-DYNAMIC-TARIFF · 2 customers/);
  });

  it("never shows the internal 'NP' key", () => {
    expect(render("P-EN-01").visible).not.toMatch(/\bNP\b/);
  });

  it("shows 'not enough data' for a missing ΔCLV, never €0", () => {
    const blank = buildOverview(rows.map((r) => (r.chosen_offer === "P-EN-03" ? { ...r, delta_clv: null } : r)));
    const a = blank.actions.find((x) => x.offer === "P-EN-03")!;
    expect(a.valued).toBe(0);
    const { visible } = render("P-EN-03", [a]);
    expect(visible).toContain("not enough data");
    expect(visible).not.toMatch(/€0\b/);
  });

  it("does not show half a reason when one label is missing", () => {
    const r = { key: "S11|N-HOME-ELECTRICITY", signal: "S11", need: "N-HOME-ELECTRICITY", count: 96 };
    const noSignal = { ...summary, signal_labels: { ...summary.signal_labels, S11: undefined } } as unknown as Summary;
    expect(reasonLine(r, noSignal)).toMatchObject({ text: "not enough data", missing: true });
    expect(reasonLine(r, summary)).toMatchObject({ text: "Autostrom without home electricity → Home electricity for an EV driver", missing: false });
  });

  it("puts Overview first in the Orchestration navigation and the Worklist at /worklist", () => {
    const nav = renderToStaticMarkup(<MemoryRouter initialEntries={["/"]}><Layout /></MemoryRouter>);
    expect(visibleText(nav)).toMatch(/Overview .*Worklist .*Groups/);
    expect(nav).toContain('href="/worklist"');
  });
});
