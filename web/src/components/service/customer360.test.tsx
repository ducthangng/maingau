import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CustomerCard } from "../../types/contracts";
import ActionsTab from "./ActionsTab";
import JourneyTab from "./JourneyTab";
import { dateLabel, notRecommended, sortedActions } from "./plain";
import ProfileTab from "./ProfileTab";
import ServiceStrip from "./ServiceStrip";

// Acceptance (prompts/ui-customer360.md §4): render the strip and the three tabs from the exported
// cards in web/public/data and read the text an agent would see.

const DIR = fileURLToPath(new URL("../../../public/data/customers/", import.meta.url));
const load = (id: string) => JSON.parse(readFileSync(`${DIR}${id}.json`, "utf8")) as CustomerCard;

function text(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ");
}

function screens(card: CustomerCard) {
  const [strip, profile, journey, actions] = [ServiceStrip, ProfileTab, JourneyTab, ActionsTab].map((C) => text(renderToStaticMarkup(<C card={card} />)));
  return { strip, profile, journey, actions, all: [strip, profile, journey, actions].join(" ") };
}

// No urgency tier, flags, segment name or payment field anywhere in Customer 360° (§3.2, §4).
const FORBIDDEN =
  /payment|zahlung|dunning|mahnung|mahnstufe|inkasso|sepa|direct debit|bank transfer|urgency|archetype|outlier|service critical|contact fatigue|\bP[1-5]\b|loyalist|retention risk|eco-system adopter|connected household|\bEV driver\b|snapshot inconsist/i;

describe("Customer 360° acceptance customers", () => {
  it("MG-100186: open complaint, service first, sales offers not recommended", () => {
    const card = load("MG-100186");
    const s = screens(card);
    expect(s.strip).toMatch(/Open tickets 1\b/);
    expect(s.profile).toMatch(/Open tickets \(1\)/);
    expect(s.profile).toMatch(/Complaint/);
    expect(sortedActions(card)[0].action_type).toBe("service");
    expect(s.actions).toContain("No sales offers while a ticket is open");
  });

  it("MG-100096: service only, account status without a word about payment", () => {
    const card = load("MG-100096");
    const s = screens(card);
    expect(sortedActions(card).every((c) => c.action_type === "service")).toBe(true);
    expect(notRecommended(card).map((l) => l.text)).toContain("No sales offers right now (account status)");
    expect(s.all).not.toMatch(/payment|dunning/i);
  });

  it("MG-100023: Autostrom by portal pop-up because of the wallbox", () => {
    const card = load("MG-100023");
    const s = screens(card);
    expect(card.chosen.tuple_id).toBe("P-AS-01|portal_popup|sie");
    expect(s.strip).toContain("MAINGAU Autostrom");
    expect(s.strip).toContain("Portal pop-up");
    expect(s.strip).toMatch(/bought a Wallbox .* no Autostrom contract/);
  });

  it("MG-100112: no personalised offers, StromAktiv by phone, Sie", () => {
    const card = load("MG-100112");
    const s = screens(card);
    expect(card.chosen.tuple_id).toMatch(/^P-EN-01\|outbound_call\|sie$/);
    expect(s.strip).toMatch(/Address as Sie/);
    expect(s.profile).toContain("Personalised offers: no");
    expect(s.actions).toContain("No personalised offers (no consent for personalisation)");
  });

  it("MG-100026: the strip says from when the NBA is possible", () => {
    const card = load("MG-100026");
    expect(card.chosen.deferred_until).toBeTruthy();
    expect(screens(card).strip).toContain(`from ${dateLabel(card.chosen.deferred_until)}`);
  });
});

describe("every customer", () => {
  const ids = readdirSync(DIR).filter((f) => f.endsWith(".json")).map((f) => f.replace(/\.json$/, ""));

  it("renders without tier, flags, segment or payment wording", () => {
    const leaks: string[] = [];
    for (const id of ids) {
      const m = screens(load(id)).all.match(new RegExp(`.{0,30}(?:${FORBIDDEN.source}).{0,30}`, "i"));
      if (m) leaks.push(`${id}: …${m[0]}…`);
    }
    expect(ids.length).toBeGreaterThan(0);
    expect(leaks).toEqual([]);
  });
});
