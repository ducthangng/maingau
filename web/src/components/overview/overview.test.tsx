import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { IndexRow, Summary } from "../../types/contracts";
import ActionTable from "./ActionTable";
import { buildOverview } from "./model";

// What a marketer sees on the Overview (prompts/ui-overview.md §4–§5), rendered from the real export.

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const summary = JSON.parse(readFileSync(`${DATA}summary.json`, "utf8")) as Summary;
const model = buildOverview(rows);

function render(open: string | null) {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <ActionTable actions={model.actions} summary={summary} maxTotal={model.maxTotal} open={open} onToggle={() => {}} />
    </MemoryRouter>,
  );
  const visible = html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#x27;/g, "'")
    .replace(/\s+/g, " ");
  return { html, visible };
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
