import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import Layout from "../Layout";
import { describe, expect, it } from "vitest";
import type { IndexRow, Summary } from "../../types/contracts";
import ActionTable from "./ActionTable";
import { buildOverview, reasonLine, type ActionStat } from "./model";
import SegmentBreakdown from "./SegmentBreakdown";

// What a marketer sees on the Overview (prompts/ui-overview.md §4–§5), rendered from the real export.

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const summary = JSON.parse(readFileSync(`${DATA}summary.json`, "utf8")) as Summary;
const model = buildOverview(rows);

function render(open: string | null, actions: ActionStat[] = model.actions) {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <ActionTable actions={actions} summary={summary} maxTotal={model.maxTotal} open={open} onToggle={() => {}} />
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
    expect(visible).toContain("No need signal: general offer (no profiling consent)");
  });

  it("keeps signal codes, offer IDs and counts in tooltips only", () => {
    expect(visible).not.toMatch(/\bS\d{1,2}\b|\bP-[A-Z]{2}-\d{2}\b|\bN-[A-Z]/);
    expect(html).toContain('title="S11 → N-HOME-ELECTRICITY · 96 customers"');
    expect(html).toContain('title="P-EN-01"');
  });

  it("tells how many wait for a contact limit", () => {
    expect(html).toContain("46 of them wait for a contact limit");
  });

  it("opens no segment panel until a row is chosen", () => {
    expect(html).not.toContain("segments-");
  });
});

describe("segment breakdown", () => {
  const { html, visible } = render("P-EN-02");

  it("shows customers and ΔCLV with their shares", () => {
    expect(visible).toMatch(/A2 Traditional energy loyalist 44 · 67% \+€552 · 54%/);
    expect(visible).toMatch(/A0 .*? 2 · 3% \+€42 · 4%/);
  });

  it("links each segment with customers to the filtered Worklist, empty ones are not links", () => {
    expect(html).toContain('href="/worklist?offer=P-EN-02&amp;arch=A2&amp;pers=yes&amp;queue=all"');
    expect(html).not.toContain("arch=A4");
    expect(html).not.toContain("offer=P-EN-02&amp;pers=no");
    expect(html).toContain('aria-label="Retention risk (do no harm): no customers"');
  });

  it("explains Not personalised", () => {
    const np = render("P-EN-01").html;
    expect(np).toContain('href="/worklist?offer=P-EN-01&amp;pers=no&amp;queue=all"');
    expect(np).toContain("No profiling consent: the engine uses general offers without need signals");
  });
});

describe("review fixes", () => {
  it("shows at most two reasons and folds the rest into '+N other reasons' with a tooltip", () => {
    const a = model.actions.find((x) => x.offer === "P-EN-01")!;
    const extra = [
      { key: "S3|N-EV-CHARGING", signal: "S3", need: "N-EV-CHARGING", count: 3 },
      { key: "S9|N-DYNAMIC-TARIFF", signal: "S9", need: "N-DYNAMIC-TARIFF", count: 2 },
    ];
    const { html, visible } = render(null, [{ ...a, reasons: [...a.reasons, ...extra] }]);
    expect(visible).toContain("+2 other reasons");
    expect(visible).not.toContain("Wallbox bought, no Autostrom");
    expect(html).toMatch(/title="[^"]*S3 → N-EV-CHARGING · 3 customers[^"]*S9 → N-DYNAMIC-TARIFF · 2 customers/);
  });

  it("never shows the internal 'NP' key; Not personalised gets the no-profiling icon", () => {
    const { visible, html } = render("P-EN-01");
    expect(visible).not.toMatch(/\bNP\b/);
    expect(html).toContain("lucide-eye-off");
  });

  it("shows 'not enough data' for a missing ΔCLV, never €0", () => {
    const blank = buildOverview(rows.map((r) => (r.chosen_offer === "P-EN-03" ? { ...r, delta_clv: null } : r)));
    const a = blank.actions.find((x) => x.offer === "P-EN-03")!;
    expect(a.valued).toBe(0);
    const { visible } = render("P-EN-03", [a]);
    expect(visible).toContain("not enough data");
    expect(visible).not.toMatch(/€0\b/);
    const seg = visibleText(renderToStaticMarkup(<MemoryRouter><SegmentBreakdown action={a} summary={summary} /></MemoryRouter>));
    expect(seg).toContain("not enough data");
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
