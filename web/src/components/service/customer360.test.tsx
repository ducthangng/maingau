import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { CustomerCard, IndexRow, Journey } from "../../types/contracts";
import { mockName } from "../../lib/customerMock";
import Service from "../../pages/Service";
import Layout from "../Layout";
import ActionsTab from "./ActionsTab";
import CustomerList from "./CustomerList";
import JourneyTab, { fromTimeline, JourneyList } from "./JourneyTab";
import { dateLabel, notRecommended, sortedActions } from "./plain";
import ProfileTab from "./ProfileTab";
import ServiceStrip from "./ServiceStrip";

// Acceptance (prompts/ui-customer360.md §4): render the strip and the three tabs from the exported
// cards in web/public/data and read the text an agent would see.

const DIR = fileURLToPath(new URL("../../../public/data/customers/", import.meta.url));
const load = (id: string) => JSON.parse(readFileSync(`${DIR}${id}.json`, "utf8")) as CustomerCard;
const JOURNEY_DIR = fileURLToPath(new URL("../../../public/data/journey/", import.meta.url));
const loadJourney = (id: string) => JSON.parse(readFileSync(`${JOURNEY_DIR}${id}.json`, "utf8")) as Journey;
const journeyText = (id: string) => text(renderToStaticMarkup(<JourneyList events={loadJourney(id).events} />));

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
// Engine wording: rule and offer codes, tuple IDs, ΔCLV thresholds, "Held back until".
const ENGINE_CODE = /\b[BCU]-\d{2}\b|\bP-[A-Z]{2}-\d{2}\b|ΔCLV|Held back|\[S\d+\]/;
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
    expect(s.actions).toContain("MAINGAU Autostrom · Newsletter Contact limit reached, possible from 5 Nov 2026");
    const journey = journeyText("MG-100023");
    expect(journey).toMatch(/Newsletters 13 .*Past proposals 3 .*Portal 16/);
    expect(journey).toContain("Offer MAINGAU Autostrom via newsletter email");
    expect(journey).toContain("tone Sie");
    expect(journey).toMatch(/Customer reaction: not opened/);
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
    expect(screens(card).strip).toContain("from 2 Dec 2026");
    expect(dateLabel(card.chosen.deferred_until)).toBe("2 Dec 2026");
  });
});

describe("no offer right now", () => {
  it("names the account-level reason, not a single offer's", () => {
    expect(screens(load("MG-100011")).strip).toContain("No offer right now No sales offers right now (account status)");
    expect(screens(load("MG-100017")).strip).toContain("No offer right now No marketing contact agreed: service contact only");
  });
});

describe("dashboard switch and landing page", () => {
  const at = (path: string, el: React.ReactElement) =>
    text(
      renderToStaticMarkup(
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/" element={el}>
              <Route index element={<p>worklist page</p>} />
              <Route path="service" element={<Service />} />
            </Route>
          </Routes>
        </MemoryRouter>,
      ),
    );

  it("labels every mock name in the customer list as a demo name", () => {
    const rows = JSON.parse(readFileSync(fileURLToPath(new URL("../../../public/data/index.json", import.meta.url)), "utf8")) as IndexRow[];
    const page = text(
      renderToStaticMarkup(
        <MemoryRouter>
          <CustomerList rows={rows} />
        </MemoryRouter>,
      ),
    );
    expect(page).toContain(`of ${rows.length} customers`);
    for (const id of ["MG-100186", "MG-100096", "MG-100023", "MG-100112", "MG-100026"]) expect(page).toContain(`${mockName(id)} demo ${id}`);
    expect(page).not.toMatch(/payment|dunning|P[1-5]|approve/i);
  });

  it("keeps the Orchestration navigation on its pages and hides it in Customer 360°", () => {
    const orchestration = at("/", <Layout />);
    expect(orchestration).toMatch(/Overview .*Campaigns .*Worklist/);
    expect(orchestration).toContain("worklist page");
    expect(at("/service", <Layout />)).not.toMatch(/Worklist|Campaigns/);
  });
});

describe("every customer", () => {
  const ids = readdirSync(DIR).filter((f) => f.endsWith(".json")).map((f) => f.replace(/\.json$/, ""));

  it("renders without tier, flags, segment or payment wording", () => {
    const leaks: string[] = [];
    for (const id of ids) {
      const card = load(id);
      const all = screens(card).all;
      const m = all.match(new RegExp(`.{0,30}(?:${FORBIDDEN.source}|${ENGINE_CODE.source}).{0,30}`, "i"));
      if (m) leaks.push(`${id}: …${m[0]}…`);
      // this card's own triage words: flag labels and segment name (highlights repeat facts that the
      // NBA reason may state, e.g. "3 failed charging sessions in 30 days", so they are not checked)
      const own = [...(card.triage.flags ?? []).map((f) => f.label), card.triage.archetype.name];
      for (const w of own) if (w && w.length > 3 && w !== "Other" && all.includes(w)) leaks.push(`${id}: shows "${w}"`);
    }
    expect(ids.length).toBeGreaterThan(0);
    expect(leaks).toEqual([]);
  });

  it("journey: every event type somewhere, no CLV, tier, flags, segment or payment wording", () => {
    const leaks: string[] = [];
    const chips = new Set<string>();
    for (const id of ids) {
      const t = journeyText(id);
      for (const m of t.matchAll(/(Newsletters|Past proposals|Agent suggestions|Tickets|Orders|Charging|Portal|Contracts|Consent) \d+/g)) chips.add(m[1]);
      const m = t.match(new RegExp(`.{0,30}(?:${FORBIDDEN.source}|\\bCLV\\b).{0,30}`, "i"));
      if (m) leaks.push(`${id}: …${m[0]}…`);
    }
    expect(chips.size).toBe(9);
    expect(leaks).toEqual([]);
  });

  it("journey tab waits for the journey, and falls back to the card timeline", () => {
    const card = load("MG-100186");
    expect(text(renderToStaticMarkup(<JourneyTab card={card} />))).toContain("Loading the journey");
    const fallback = text(renderToStaticMarkup(<JourneyList events={(card.timeline ?? []).map(fromTimeline)} />));
    expect(fallback).toMatch(/Tickets \d+/);
    expect(fallback).toMatch(/Ticket: complaint/i);
    expect(fallback).not.toMatch(new RegExp(FORBIDDEN.source, "i"));
  });
});
