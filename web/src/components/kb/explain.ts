import type { KbCustomer, KbEdge, KbGraph, KbNode, KnowledgeBase } from "../../lib/kb";
import { CHANNEL_LABEL, eur, pct, signedEur } from "../../lib/format";
import { mockName } from "../../lib/customerMock";
import { TIER_LABEL, type Tier } from "../Chips";
import { dateLabel, plainText } from "../service/plain";

// Plain-language explanations for one box of the Knowledge Base graph: what it is, why it has the state it has,
// how the engine reached it, and which rules touched it. Read only from the export (scripts/export_kg_viz.py).

type Detail = Record<string, unknown>;
const det = (n: KbNode): Detail => (n.detail ?? {}) as Detail;
const s = (d: Detail, k: string) => (typeof d[k] === "string" && d[k] ? (d[k] as string) : "");

const CONSENT: Record<string, string> = {
  newsletter_email: "the newsletter",
  marketing_email: "marketing e-mails",
  marketing_phone: "marketing calls",
  marketing_sms: "marketing SMS",
  portal_app_personalisation: "personalised content in the portal and app",
  profiling_analytics: "personalised offers (profiling)",
};
const SOURCE: Record<string, string> = {
  shop_orders: "Shop order",
  energy_contracts: "Energy contract",
  mobile_contracts: "Mobile contract",
  autostrom_contracts: "Autostrom contract",
  hems_devices: "Smart-home device",
  service_interactions: "Service ticket",
  charge_sessions: "Charging session",
};

/** Engine text made readable: no signal codes, dates as "5 Nov 2026", "dunning_level = 3" as "dunning level 3". */
export function tidy(t: string): string {
  return plainText(t)
    .replace(/(\d{4}-\d{2}-\d{2})(?:[T ]\d{2}:\d{2}(?::\d{2})?)?/g, (_, d: string) => dateLabel(d))
    .replace(/\b([a-z]+)_([a-z_]+)\s*=\s*/g, (_, a: string, b: string) => `${a} ${b.replace(/_/g, " ")} `)
    .replace(/;\s*marketing waits\.?$/, "")
    .replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (w) => w.replace(/_/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}
const sentence = (t: string) => (t ? t[0].toUpperCase() + t.slice(1) : t);

const consentName = (type: string) => CONSENT[type] ?? type.replace(/_/g, " ");
const channelName = (c: string) => CHANNEL_LABEL[c] ?? c.replace(/_/g, " ");
const channelOf = (n: KbNode) => n.id.replace(/^ch:/, "");
const lower = (t: string) => (t === t.toUpperCase() ? t : t.toLowerCase());
const list = (xs: string[]) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

/** The name a reader knows a box by (not its engine id). */
export function nameOf(n: KbNode, kb?: KnowledgeBase, c?: KbCustomer): string {
  const d = det(n);
  switch (n.kind) {
    case "customer":
      return mockName(n.id);
    case "data":
      return `${SOURCE[s(d, "source")] ?? "Record"} ${n.label}`;
    case "signal":
    case "need":
      return n.sub ?? n.label;
    case "offer":
      return s(d, "name") || n.label;
    case "channel":
      return channelName(channelOf(n));
    case "consent":
      return `consent to ${consentName(n.id.replace(/^consent:/, ""))}`;
    case "rule":
      return ruleName(n.label, kb, c) ?? sentence(n.sub ?? n.label);
    default:
      return n.label;
  }
}

export function ruleName(id: string, kb?: KnowledgeBase, c?: KbCustomer): string | undefined {
  if (id === "ECON-NONPOSITIVE") return "Expected gain is not positive";
  return c?.rules.find((r) => r.rule_id === id)?.name ?? kb?.policy.compliance.find((r) => r.id === id)?.label ?? kb?.policy.business.find((r) => r.id === id)?.name;
}

/** "withdrawn on 2 Apr 2024" / "never given (last change …)" / "granted on …". */
function consentState(c: KbNode | undefined): { ok: boolean; text: string } {
  if (!c) return { ok: false, text: "not on record" };
  const d = det(c);
  const eff = s(d, "effective") || "not_given";
  const when = s(d, "updated") ? dateLabel(s(d, "updated")) : "";
  if (eff === "granted") return { ok: true, text: `granted${when ? ` on ${when}` : ""}${d["double opt-in"] ? ", confirmed by double opt-in" : ""}` };
  if (eff === "withdrawn") return { ok: false, text: `withdrawn${when ? ` on ${when}` : ""}` };
  return { ok: false, text: `never given${when ? ` (last change ${when})` : ""}` };
}

export interface Explanation {
  /** What the box is, in one sentence. */
  what: string;
  /** Why it has its state and what that means for the decision. */
  why?: string;
}

export function explain(n: KbNode, g: KbGraph, kb: KnowledgeBase, c?: KbCustomer): Explanation {
  const d = det(n);
  const byId = new Map(g.nodes.map((x) => [x.id, x]));
  const out = (pred: (e: KbEdge) => boolean) => g.edges.filter((e) => e.from === n.id && pred(e)).map((e) => byId.get(e.to)!).filter(Boolean);
  const inn = (pred: (e: KbEdge) => boolean) => g.edges.filter((e) => e.to === n.id && pred(e)).map((e) => byId.get(e.from)!).filter(Boolean);
  const names = (xs: KbNode[]) => list([...new Set(xs.map((x) => nameOf(x, kb, c)))]);

  switch (n.kind) {
    case "customer": {
      if (!c) return { what: n.sub ?? n.label };
      const h = c.headline;
      const tier = TIER_LABEL[h.urgency as Tier];
      const why = h.urgency_reasons.map((r) => plainText(r)).filter(Boolean);
      return {
        what: `${mockName(c.id)} belongs to the segment “${h.archetype.replace(/^A\d+\s+/, "")}”, with a lifetime value of ${eur(h.clv)} and a ${pct(h.churn, 0)} risk of leaving within 12 months.`,
        why: `Urgency ${h.urgency}${tier ? ` – ${lower(tier)}` : ""}.${why.length ? ` Why: ${why.map(tidy).join("; ")}.` : ""}`,
      };
    }
    case "data": {
      const sig = out(() => true).filter((x) => x.kind === "signal");
      const date = Object.entries(d).find(([k, v]) => /(_at|_date)$/.test(k) && typeof v === "string")?.[1] as string | undefined;
      return {
        what: `${nameOf(n)} from the customer data: ${n.sub ?? ""}${date ? `, ${dateLabel(date)}` : ""}.`,
        why: sig.length ? `This record is the evidence for the signal${sig.length > 1 ? "s" : ""} ${names(sig)}.` : undefined,
      };
    }
    case "signal": {
      const needs = out((e) => byId.get(e.to)?.kind === "need");
      return {
        what: `The engine noticed: ${tidy(s(d, "detail")) || n.sub}.`,
        why: `${s(d, "strength") ? `A ${s(d, "strength")} signal` : "A signal"}${s(d, "date") ? ` from ${dateLabel(s(d, "date"))}` : ""}${needs.length ? `. It points to the need: ${names(needs)}` : ""}.`,
      };
    }
    case "need": {
      const sigs = inn(() => true).filter((x) => x.kind === "signal");
      const offers = out(() => true).filter((x) => x.kind === "offer");
      const tag = (o: KbNode) => `${nameOf(o)}${o.status === "chosen" ? " (chosen)" : o.status === "blocked" ? " (blocked)" : o.status === "waiting" ? " (waiting)" : ""}`;
      return {
        what: `What the customer probably needs: ${n.sub ?? n.label}.`,
        why: [sigs.length ? `Raised by ${names(sigs)}.` : "", offers.length ? `Offers that answer it: ${list(offers.map(tag))}.` : ""].filter(Boolean).join(" ") || undefined,
      };
    }
    case "offer": {
      const name = nameOf(n);
      const sends = g.edges.filter((e) => e.from === n.id && byId.get(e.to)?.kind === "channel");
      if (n.status === "chosen" && c) {
        const v = c.chosen.valuation;
        const ch = sends.find((e) => e.status === "chosen");
        const cause = plainText(c.chosen.reason).split("→")[0].trim();
        return {
          what: `Chosen as the next best action: ${name}${ch ? ` through ${lower(nameOf(byId.get(ch.to)!))}` : ""}.`,
          why: [
            cause ? `Why: ${tidy(cause)}.` : "",
            v ? `Expected gain ${signedEur(v.dclv)}: a ${pct(v.p)} chance they agree, which would lift their value from ${eur(v.clv_now)} to ${eur(v.clv_accept)}.` : "",
          ]
            .filter(Boolean)
            .join(" "),
        };
      }
      if (n.status === "blocked") {
        const reason = tidy(s(d, "reason")).replace(/^.*?(not offered|blocked):\s*/i, "");
        const rule = s(d, "blocked by");
        const ruleBox = inn((e) => e.status === "blocked").find((x) => x.kind === "rule");
        return {
          what: `Not offered: ${name}.`,
          why: reason
            ? `${rule ? `The rule “${ruleName(rule, kb, c) ?? rule}” stops it: ` : ""}${reason}.`
            : ruleBox
              ? `The rule “${nameOf(ruleBox, kb, c)}” stops it: ${tidy(s(det(ruleBox), "reason"))}.`
              : `No channel is left for it: ${list([...new Set(sends.map((e) => ruleName(e.label ?? "", kb, c) ?? e.label ?? "").filter(Boolean))]).toLowerCase()}.`,
        };
      }
      if (n.status === "waiting") {
        const rule = inn((e) => e.status === "waiting").find((x) => x.kind === "rule");
        const until = sends.map((e) => e.label?.match(/waits → (\S+)/)?.[1]).find(Boolean) ?? (rule ? s(det(rule), "until") : "");
        return {
          what: `Held back for now: ${name}.`,
          why: `${rule ? `The rule “${nameOf(rule, kb, c)}” holds it: ${tidy(s(det(rule), "reason"))}. ` : ""}${until ? `It can go out on ${dateLabel(until)} at the earliest.` : ""}`.trim() || undefined,
        };
      }
      const best = sends
        .filter((e) => e.status === "alternative" && e.label)
        .map((e) => ({ v: Number(e.label!.replace(/[^\d.-]/g, "")), ch: nameOf(byId.get(e.to)!) }))
        .sort((a, b) => b.v - a.v)[0];
      const chosen = c?.chosen.valuation?.dclv;
      return {
        what: `Allowed, but not chosen: ${name}.`,
        why: best
          ? `Its best expected gain is ${eur(best.v, true)} (${lower(best.ch)})${chosen != null ? `, lower than the ${signedEur(chosen)} of the chosen action` : ""}.`
          : undefined,
      };
    }
    case "channel": {
      const ch = channelOf(n);
      const consent = out((e) => byId.get(e.to)?.kind === "consent")[0];
      const used = g.edges.some((e) => e.to === n.id && e.status === "chosen");
      const reason = s(d, "reason");
      if (ch === "service_agent") return { what: "Service agent: a service contact, not marketing.", why: "It needs no marketing consent and never carries a sales offer." };
      if (n.status === "blocked") {
        if (/no app/i.test(reason)) return { what: `${nameOf(n)} can't be used.`, why: "The customer has no app installed." };
        const st = consentState(consent);
        return { what: `${nameOf(n)} can't be used for marketing.`, why: `Consent to ${consentName(consent?.id.replace(/^consent:/, "") ?? "")} was ${st.text}.` };
      }
      const st = consentState(consent);
      const waits = g.edges.filter((e) => e.to === n.id && e.status === "waiting");
      const until = waits.map((e) => e.label?.match(/waits → (\S+)/)?.[1]).find(Boolean);
      return {
        what: used ? `The chosen action goes out through ${lower(nameOf(n))}.` : `${nameOf(n)} may be used.`,
        why: [consent ? `Consent to ${consentName(consent.id.replace(/^consent:/, ""))} was ${st.text}.` : "", waits.length ? `${names(waits.map((e) => byId.get(e.from)!))} ${waits.length > 1 ? "wait" : "waits"} to go out here${until ? ` until ${dateLabel(until)}` : ""}.` : ""]
          .filter(Boolean)
          .join(" ") || undefined,
      };
    }
    case "consent": {
      const type = n.id.replace(/^consent:/, "");
      const st = consentState(n);
      const chans = inn(() => true).filter((x) => x.kind === "channel");
      const what = `The customer's consent to ${consentName(type)} was ${st.text}.`;
      return {
        what,
        why: chans.length ? (st.ok ? `That allows ${list(chans.map((x) => lower(nameOf(x))))}.` : `So ${list(chans.map((x) => lower(nameOf(x))))} can't be used for marketing.`) : undefined,
      };
    }
    case "rule": {
      const until = s(d, "until");
      const hit = out(() => true).filter((x) => x.kind === "offer");
      return {
        what: `${nameOf(n, kb, c)}. ${sentence(tidy(s(d, "reason")))}.`,
        why: `${until ? `This lifts on ${dateLabel(until)}. ` : ""}${hit.length ? `It ${until ? "holds back" : "blocks"} ${names(hit)}.` : ""}`.trim() || undefined,
      };
    }
    default:
      return { what: n.sub ?? n.label, why: s(d, "note") || undefined };
  }
}

const RANK: Record<string, number> = { chosen: 0, plain: 1, alternative: 1, waiting: 2, blocked: 3 };

export interface Step {
  from: string;
  verb: string;
  to: string;
}

function verbOf(e: KbEdge, g: KbGraph): string {
  const to = g.nodes.find((n) => n.id === e.to);
  if (to?.kind === "channel") return e.status === "chosen" ? "is sent through" : e.status === "alternative" ? "could go through" : e.status === "waiting" ? "waits for" : "is blocked on";
  const v: Record<string, string> = {
    "evidence for": "is evidence for",
    indicates: "points to",
    reinforces: "reinforces",
    "addressed by": "is answered by",
    requires: "needs",
    emitted: "shows",
    "catalog offer": "can get the catalogue offer",
    blocks: "blocks",
    "holds back": "holds back",
  };
  return v[e.label ?? ""] ?? e.label ?? "leads to";
}

/** One route from the customer down to `id`, as readable steps; the chosen path is preferred where it exists. */
export function story(g: KbGraph, id: string, kb?: KnowledgeBase): Step[] {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const steps: Step[] = [];
  const seen = new Set([id]);
  let cur = id;
  for (let i = 0; i < 12; i++) {
    const inn = g.edges
      .filter((e) => e.to === cur && !seen.has(e.from) && byId.get(e.from)?.kind !== "rule")
      .sort((a, b) => Number(b.path ?? false) - Number(a.path ?? false) || (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9));
    const e = inn[0];
    if (!e) break;
    steps.unshift({ from: nameOf(byId.get(e.from)!, kb), verb: verbOf(e, g), to: nameOf(byId.get(e.to)!, kb) });
    seen.add(e.from);
    cur = e.from;
  }
  return steps;
}

const KEY: Record<string, string> = {
  "churn 12m": "Churn risk (12 months)",
  "CLV €": "Lifetime value",
  "business lines": "Business lines",
  "profiling consent": "Profiling consent",
  "double opt-in": "Double opt-in",
  line_value_eur: "Value",
  is_guest: "Guest order",
};

/** A raw field as a label and a readable value. */
export function fact(key: string, v: unknown): [string, string] {
  const label = KEY[key] ?? key.replace(/_/g, " ").replace(/^./, (x) => x.toUpperCase());
  if (typeof v === "boolean") return [label, v ? "yes" : "no"];
  if (typeof v === "number") {
    if (/eur|€|clv/i.test(key)) return [label, eur(v)];
    if (/churn/i.test(key)) return [label, pct(v, 0)];
    return [label, v.toLocaleString("en-US", { maximumFractionDigits: 2 })];
  }
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}(T|$)/.test(v)) return [label, dateLabel(v.slice(0, 10))];
  if (typeof v === "string") return [label, v.replace(/_/g, " ")];
  return [label, JSON.stringify(v)];
}
