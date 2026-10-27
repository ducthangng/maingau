import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { IndexRow, Summary } from "../../types/contracts";
import Groups from "../../pages/Groups";
import CampaignDialog from "./CampaignDialog";
import CampaignList from "./CampaignList";
import CampaignDetail from "./CampaignDetail";
import { buildGroups, filterRows, readFilter } from "./model";

// What the Groups page shows under an Overview filter, and the Approve everything dialog, from the real export.

vi.mock("../../lib/data", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../lib/data")>();
  const { readFileSync: read } = await import("node:fs");
  const dir = new URL("../../../public/data/", import.meta.url);
  const index = JSON.parse(read(new URL("index.json", dir), "utf8"));
  const summary = JSON.parse(read(new URL("summary.json", dir), "utf8"));
  return { ...orig, useLoad: (load: unknown) => ({ status: "ready", data: load === orig.loadIndex ? index : summary }) };
});

const DATA = fileURLToPath(new URL("../../../public/data/", import.meta.url));
const rows = JSON.parse(readFileSync(`${DATA}index.json`, "utf8")) as IndexRow[];
const summary = JSON.parse(readFileSync(`${DATA}summary.json`, "utf8")) as Summary;

const visibleText = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#x27;/g, "'")
    .replace(/\s+/g, " ");

const page = (url: string) =>
  renderToStaticMarkup(
    <MemoryRouter initialEntries={[url]}>
      <Groups />
    </MemoryRouter>,
  );

describe("Groups page under an Overview filter", () => {
  it("shows the filter bar with Reset, filtered counts and no service list", () => {
    const html = page("/groups?offer=P-EN-02&arch=A2&pers=yes");
    const text = visibleText(html);
    expect(text).toContain("Showing StromGarant · A2 Traditional energy loyalist");
    expect(text).toContain("Reset filter");
    expect(text).toMatch(/\d+ sales groups · 42 customers/);
    expect(text).not.toContain("Service — handle individually");
    expect(text).toContain("Service cases are not part of this action");
    expect(text).toContain("Approve everything…");
    expect(text).toContain("No campaign yet: use Approve everything or Approve group to create one.");
  });

  it("without a filter shows everything as before", () => {
    const text = visibleText(page("/groups"));
    expect(text).not.toContain("Reset filter");
    expect(text).toContain("Service — handle individually");
    expect(text).toMatch(/sales groups · \d+ customers · 47 service · 86 no action/);
  });
});

describe("Approve everything dialog", () => {
  const groups = buildGroups(filterRows(rows, readFilter(new URLSearchParams("offer=P-EN-02&arch=A2&pers=yes")))).sales;
  const dialog = (initialName: string) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <CampaignDialog
          groups={groups}
          latest={new Map()}
          filter={{ offer: "P-EN-02", arch: "A2", pers: "yes" }}
          scope="StromGarant · A2 Traditional energy loyalist"
          initialName={initialName}
          summary={summary}
          onClose={() => {}}
          onConfirmed={() => {}}
        />
      </MemoryRouter>,
    );
  const confirmButton = (html: string) => html.match(/<button[^>]*>Approve and create campaign<\/button>/)?.[0] ?? "";

  it("cannot confirm without a name", () => {
    expect(confirmButton(dialog(""))).toContain('disabled=""');
    expect(confirmButton(dialog("   "))).toContain('disabled=""');
    expect(confirmButton(dialog("StromGarant · A2 · 27 Oct 2026"))).not.toContain('disabled=""');
  });

  it("defaults the control group to 10 % and shows the live summary", () => {
    const html = dialog("x");
    expect(html).toMatch(/<option value="10" selected="">10%<\/option>/);
    const text = visibleText(html);
    for (const label of ["Groups", "Included", "Control group", "Contacted"]) expect(text).toContain(label);
    expect(text).not.toContain("Σ ΔCLV");
  });

  it("on a group page: names the campaign, sets the control group, then Save & Run", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CampaignDialog
          groups={[groups[0]]}
          latest={new Map()}
          filter={{ offer: "P-EN-02", arch: "", pers: "" }}
          scope="StromGarant · App push · Du · P3"
          initialName="StromGarant · App push · Du · P3 · 27 Oct 2026"
          summary={summary}
          eyebrow="Approve group · StromGarant · App push · Du · P3"
          confirmLabel="Save & Run"
          onClose={() => {}}
          onConfirmed={() => {}}
        />
      </MemoryRouter>,
    );
    const text = visibleText(html);
    expect(text).toContain("Approve group · StromGarant · App push · Du · P3");
    expect(text).toContain("Campaign name");
    expect(text).toContain("Control group");
    expect(html).toMatch(/<button[^>]*>Save &amp; Run<\/button>/);
    expect(text).not.toContain("Approve and create campaign");
  });
});

describe("Campaign list", () => {
  it("lists campaigns newest first with the control group as n · %", () => {
    const base = {
      created_at: "2026-10-27T09:00:00.000Z",
      reviewer: "demo-marketer",
      offer: null,
      arch: null,
      pers: null,
      scope: "All actions",
      holdout_pct: 20,
      groups: ["P-EN-02|email|sie", "P-EN-01|sms|sie"],
      customers: 50,
      contacted: 40,
      holdout: 10,
      delta_clv: 100,
    };
    const text = visibleText(
      renderToStaticMarkup(<CampaignList campaigns={[{ ...base, id: "C1", name: "First" }, { ...base, id: "C2", name: "Second" }]} summary={summary} />),
    );
    expect(text.indexOf("Second")).toBeLessThan(text.indexOf("First"));
    expect(text).toContain("10 · 20%");
    expect(text).not.toContain("No campaign yet");
  });
});

describe("Campaign details", () => {
  const campaign = {
    id: "CMP-1",
    name: "StromAktiv · App push · Du · P3 · 27 Oct 2026",
    created_at: "2026-10-27T09:00:00.000Z",
    reviewer: "demo-marketer",
    offer: "P-EN-02",
    arch: null,
    pers: null,
    scope: "StromAktiv · App push · Du · P3",
    holdout_pct: 10,
    groups: ["P-EN-02|app_push|du"],
    customers: 2,
    contacted: 1,
    holdout: 1,
    delta_clv: 12.5,
  };
  const decision = (id: string, holdout: boolean, campaignId: string | null = "CMP-1") => ({
    id: `${id}@t`,
    customer_id: id,
    action: "approved" as const,
    tuple_id: "P-EN-02|app_push|du",
    from_tuple: "P-EN-02|app_push|du",
    reason: null,
    reviewer: "demo-marketer",
    ts: "2026-10-27T09:00:00.000Z",
    delta_clv: 12.5,
    p_accept: 0.2,
    group: "P-EN-02|app_push|du",
    holdout,
    campaign: campaignId,
  });

  it("shows the settings and only this campaign's customers, contacted and control group", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CampaignDetail
          campaign={campaign}
          decisions={[decision("MG-1", false), decision("MG-2", true), decision("MG-3", false, "CMP-OTHER")]}
          summary={summary}
          onClose={() => {}}
        />
      </MemoryRouter>,
    );
    const text = visibleText(html);
    expect(text).toContain("StromAktiv · App push · Du · P3 · 27 Oct 2026");
    expect(text).toContain("10%, not contacted");
    expect(html.match(/data-campaign-member=/g)?.length).toBe(2);
    expect(html).not.toContain('data-campaign-member="MG-3"');
    expect(text).toContain("Contacted");
    expect(text).toContain("Control group");
    expect(html).toContain('href="/customer/MG-1"');
  });

  it("makes every row of the list open its details", () => {
    const html = renderToStaticMarkup(<MemoryRouter><CampaignList campaigns={[campaign]} summary={summary} /></MemoryRouter>);
    expect(html).toContain('data-campaign="CMP-1"');
    expect(html).toMatch(/<button[^>]*>StromAktiv · App push · Du · P3 · 27 Oct 2026<\/button>/);
  });
});
