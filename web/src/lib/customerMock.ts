import type { IndexRow } from "../types/contracts";

// Display-only stand-ins for the demo: a readable name per customer and the customer's latest
// action ("why they are on the list") phrased as something the customer did. Names are always mock
// (the data holds no names); the action comes from the engine's trigger signal when there is one,
// otherwise a plausible mock activity is shown and marked as mock.

function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

const FIRST = [
  "Anna",
  "Lukas",
  "Sophie",
  "Jonas",
  "Marie",
  "Felix",
  "Laura",
  "Paul",
  "Julia",
  "Max",
  "Lea",
  "Tim",
  "Hannah",
  "Leon",
  "Emma",
  "Ben",
  "Clara",
  "Noah",
  "Mia",
  "Elias",
  "Lena",
  "David",
  "Sarah",
  "Jan",
  "Katharina",
  "Moritz",
  "Nina",
  "Tobias",
  "Johanna",
  "Simon",
];
const LAST = [
  "Müller",
  "Schmidt",
  "Schneider",
  "Fischer",
  "Weber",
  "Meyer",
  "Wagner",
  "Becker",
  "Schulz",
  "Hoffmann",
  "Koch",
  "Bauer",
  "Richter",
  "Klein",
  "Wolf",
  "Schröder",
  "Neumann",
  "Schwarz",
  "Zimmermann",
  "Braun",
  "Krüger",
  "Hofmann",
  "Hartmann",
  "Lange",
  "Werner",
];

/** Mock full name, stable per customer id. */
export function mockName(customerId: string): string {
  const h = hash(customerId);
  return `${FIRST[h % FIRST.length]} ${LAST[(h >>> 8) % LAST.length]}`;
}

export type Polarity = "positive" | "negative";

export interface CustomerEvent {
  text: string;
  polarity: Polarity; // positive = upsell chance, negative = potential issue
  mock: boolean;
}

/** Trigger signal → what the customer did (or what just happened to them). */
const SIGNAL_EVENT: Record<string, { text: string; polarity: Polarity }> = {
  S1: { text: "Deregistered their gas meter", polarity: "positive" },
  S2: { text: "EV charging failed 3 times", polarity: "negative" },
  S3: { text: "Bought a Wallbox in the MAINGAU shop", polarity: "positive" },
  S4: { text: "Price guarantee is running out", polarity: "positive" },
  S5: { text: "Hit their mobile data limit again", polarity: "positive" },
  S6: { text: "More people at home than SIM cards", polarity: "positive" },
  S7: { text: "Installed solar panels", polarity: "positive" },
  S8: { text: "Connected a battery or wallbox to their HEMS", polarity: "positive" },
  S9: { text: "Got a smart meter with EV or heat pump", polarity: "positive" },
  S10: { text: "Read about heat pumps on our website", polarity: "positive" },
  S11: { text: "Charges an EV with us, but no home electricity", polarity: "positive" },
  S12: { text: "Opened a complaint", polarity: "negative" },
  S13: { text: "Missed a payment", polarity: "negative" },
};

/** Customer-level exclusions read as what the customer did. */
const EXCLUSION_EVENT: Record<string, string> = {
  "EXCL-CANCELLATION": "Sent a cancellation",
  "EXCL-DUNNING": "Missed a payment",
  "EXCL-OPEN-TICKET": "Opened a complaint",
  "EXCL-AUTOSTROM-CANCELLED": "Cancelled their Autostrom contract",
};

const MOCK_ACTIVITY = [
  "Logged into the customer portal 3 times this month",
  "Opened our latest newsletter",
  "Looked at mobile tariffs in the portal",
  "Bought LED bulbs in the MAINGAU shop",
  "Checked their consumption chart twice this week",
  "Updated their contact details",
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "29 Aug" from the first ISO date in the text (with the year when it is not this year), if any. */
function dateIn(s: string | null | undefined): string | null {
  const m = /(\d{4})-(\d{2})-(\d{2})/.exec(s ?? "");
  if (!m) return null;
  const label = `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}`;
  return Number(m[1]) === new Date().getFullYear() ? label : `${label} ${m[1]}`;
}

/**
 * The customer's latest action and whether it is an upsell chance or a potential issue. Any issue
 * (cancellation, dunning, complaint, failed charging, open service case) makes the case negative.
 * The date is shown only when the engine's top reason is about that same event.
 */
export function customerEvent(r: IndexRow): CustomerEvent {
  const ref = /\[([A-Z0-9-]+)\]/.exec(r.top_reason ?? "")?.[1];
  const date = dateIn(r.top_reason);
  const triggers = r.triggers ?? [];
  const at = (id: string, text: string) => (id === ref && date ? `${text} · ${date}` : text);

  const issues: [string, string][] = [
    ...(r.exclusions ?? []).filter((e) => EXCLUSION_EVENT[e]).map((e): [string, string] => [e, EXCLUSION_EVENT[e]]),
    ...triggers.filter((t) => SIGNAL_EVENT[t]?.polarity === "negative").map((t): [string, string] => [t, SIGNAL_EVENT[t].text]),
  ];
  if (issues.length) {
    const [id, text] = issues.find(([i]) => i === ref) ?? issues[0];
    return { text: at(id, text), polarity: "negative", mock: false };
  }
  if (r.service_mode || (r.flags ?? []).includes("service_critical")) return { text: "Has an open service issue", polarity: "negative", mock: false };

  const chances = triggers.filter((t) => SIGNAL_EVENT[t]);
  if (chances.length) {
    const id = chances.find((t) => t === ref) ?? chances[0];
    return { text: at(id, SIGNAL_EVENT[id].text), polarity: "positive", mock: false };
  }
  return { text: MOCK_ACTIVITY[hash(r.customer_id) % MOCK_ACTIVITY.length], polarity: "positive", mock: true };
}
