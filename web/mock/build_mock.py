"""Mock data for the CARDS UI (M0): web/public/data/{manifest,index,summary}.json + customers/<id>.json.

- REAL: the left card and timeline (nba.profile) and everything Agent KG delivers through
  nba.kg.bundle.kg_bundle(): signals, gated candidates, blocked items, triage, explanation paths,
  consent/channel/exclusion views and data-quality flags; sources via source_info().
- MOCK: Agent NBA's part (README §6.5–§6.7, §6.10, §7.3): p_accept, ΔCLV, ranking, reason line,
  alternatives, legacy ΔCLV and German content. Simplified, rate mode only.
- Every file is validated with nba.contracts, the source of docs/schema/.
- `python -m nba.build --export web/public/data` replaces this folder once it exists (manifest.json goes too).
- It only rewrites web/public/data when that folder holds mock data (manifest.json source "mock"), so a
  real export is never overwritten.

Run from the repo root: .venv/bin/python web/mock/build_mock.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from nba.contracts import (  # noqa: E402
    NO_ACTION, Alternative, Blocked, Candidate, ChecklistItem, Chosen, Content, CustomerCard, DecisionLogEntry,
    IndexRow, LegacyComparison, Meta, PathStep, PSource, Signal, SourceInfo, Summary, Valuation, Versions,
)
from nba.data import load_workbook  # noqa: E402
from nba.kg.bundle import COLUMN_SRC, KGBundle, kg_bundle, source_info  # noqa: E402
from nba.kg.policy import load_policy  # noqa: E402
from nba.kg.rules import active_exclusions, is_profiled  # noqa: E402
from nba.profile import build_profile, build_timeline, profile_population  # noqa: E402
from nba.profile.facts import clean, day  # noqa: E402
from nba.state import build_states, owns, population  # noqa: E402

OUT = REPO / "web" / "public" / "data"
VERSIONS = Versions(policy="kg-0.1", value_model="clv_simple_v1", propensity="mock-p-0.1", templates="mock-t-0.1")

REPRESENTATIVES = ["MG-100325", "MG-100001"]
TEST_CUSTOMERS = ["MG-100051", "MG-100060", "MG-100096", "MG-100186", "MG-100068", "MG-100023", "MG-100112",
                  "MG-100009", "MG-100659", "MG-100035", "MG-100087", "MG-100004", "MG-100012"]
N_TOTAL = 40
MARKETING_TYPES = {"sales", "upsell", "retention", "one_off"}

CONTACT_COST = {"newsletter_email": 0.01, "email": 0.01, "sms": 0.08, "portal_popup": 0.0, "app_push": 0.0,
                "outbound_call": 6.0, "service_agent": 0.0}
SERVICE_DRIVER_PREFIXES = ("open complaint", "low CSAT", "dunning level")
SERVICE_DRIVER_SUFFIXES = ("tickets in 12m", "failed charges in 30d")

# German copy (README §7.3 content rules): subject + offer sentence + closing; personalised adds one fact.
COPY = {
    "P-EN-01": ("StromAktiv: Ökostrom für Zuhause",
                "Mit StromAktiv beziehen Sie Ökostrom von MAINGAU auch für Ihren Haushalt.",
                "Mit StromAktiv bekommst du Ökostrom von MAINGAU auch für deinen Haushalt."),
    "P-EN-02": ("StromGarant: planbare Strompreise",
                "Mit StromGarant sichern Sie sich für die nächste Laufzeit eine Preisgarantie.",
                "Mit StromGarant sicherst du dir für die nächste Laufzeit eine Preisgarantie."),
    "P-EN-03": ("StromWärme: der Tarif für Wärmepumpen",
                "StromWärme ist auf den Strombedarf von Wärmepumpen und elektrischen Heizungen abgestimmt.",
                "StromWärme ist auf den Strombedarf von Wärmepumpen und elektrischen Heizungen abgestimmt."),
    "P-EN-05": ("Dynamischer Stromtarif: flexibel Strom nutzen",
                "Mit dem dynamischen Tarif nutzen Sie günstige Stunden, ideal mit Smart Meter und steuerbaren Geräten.",
                "Mit dem dynamischen Tarif nutzt du günstige Stunden, ideal mit Smart Meter und steuerbaren Geräten."),
    "P-MO-01": ("MAINGAU Mobil S, M oder L",
                "Ergänzen Sie Ihre Energieverträge um einen Mobilfunktarif von MAINGAU.",
                "Ergänze deine Energieverträge um einen Mobilfunktarif von MAINGAU."),
    "P-MO-02": ("Mehr Datenvolumen mit dem Mobil Upgrade",
                "Mit dem Upgrade erhalten Sie mehr Datenvolumen in Ihrem bestehenden Tarif.",
                "Mit dem Upgrade bekommst du mehr Datenvolumen in deinem bestehenden Tarif."),
    "P-MO-03": ("Zusatz-SIM für den ganzen Haushalt",
                "Mit einer Zusatz-SIM nutzen weitere Personen in Ihrem Haushalt denselben Vertrag.",
                "Mit einer Zusatz-SIM nutzen weitere Personen in deinem Haushalt denselben Vertrag."),
    "P-SL-01": ("HEMS Starter-Set: eigenen Strom besser nutzen",
                "Das HEMS Starter-Set hilft Ihnen, selbst erzeugten Strom im Haushalt besser zu nutzen.",
                "Das HEMS Starter-Set hilft dir, selbst erzeugten Strom im Haushalt besser zu nutzen."),
    "P-SL-02": ("Mehr aus dem Heimspeicher holen",
                "Die Speicher-Optimierung steuert Ihren Batteriespeicher passend zu Erzeugung und Verbrauch.",
                "Die Speicher-Optimierung steuert deinen Batteriespeicher passend zu Erzeugung und Verbrauch."),
    "P-SL-03": ("Wallbox-Integration: smarter laden zu Hause",
                "Binden Sie Ihre Wallbox in Ihr Energiemanagement ein und laden Sie bevorzugt mit eigenem Strom.",
                "Binde deine Wallbox in dein Energiemanagement ein und lade bevorzugt mit eigenem Strom."),
    "P-SH-01": ("Balkonkraftwerk 800 W im MAINGAU Shop",
                "Mit einem Balkonkraftwerk erzeugen Sie einen Teil Ihres Stroms selbst.",
                "Mit einem Balkonkraftwerk erzeugst du einen Teil deines Stroms selbst."),
    "P-SH-02": ("Wallbox 11 kW für Zuhause",
                "Mit einer eigenen Wallbox laden Sie Ihr E-Auto bequem zu Hause.",
                "Mit einer eigenen Wallbox lädst du dein E-Auto bequem zu Hause."),
    "P-SH-03": ("Smarte Thermostate im MAINGAU Shop",
                "Smarte Thermostate helfen Ihnen, Ihre Räume bedarfsgerecht zu heizen.",
                "Smarte Thermostate helfen dir, deine Räume bedarfsgerecht zu heizen."),
    "P-SH-04": ("Smart Plug 4er-Set",
                "Mit smarten Steckdosen behalten Sie den Verbrauch einzelner Geräte im Blick.",
                "Mit smarten Steckdosen behältst du den Verbrauch einzelner Geräte im Blick."),
    "P-AS-01": ("MAINGAU Autostrom: laden unterwegs",
                "Mit MAINGAU Autostrom laden Sie Ihr E-Auto an vielen öffentlichen Ladepunkten mit einer Karte und App.",
                "Mit MAINGAU Autostrom lädst du dein E-Auto an vielen öffentlichen Ladepunkten mit einer Karte und App."),
    "P-SV-01": ("Ihr Anliegen bei MAINGAU",
                "Es tut uns leid, dass es Probleme gab. Wir kümmern uns um Ihr Anliegen und melden uns mit den nächsten Schritten.",
                "Es tut uns leid, dass es Probleme gab. Wir kümmern uns um dein Anliegen und melden uns mit den nächsten Schritten."),
}
CLOSING = {"sie": "Alle Details finden Sie in Ihrem MAINGAU Kundenportal.",
           "du": "Alle Details findest du in deinem MAINGAU Kundenportal."}
SERVICE_CLOSING = {"sie": "Bei Fragen erreichen Sie uns jederzeit im Kundenservice.",
                   "du": "Bei Fragen erreichst du uns jederzeit im Kundenservice."}
LEAD = {  # personalised fact sentence per signal; S13 is payment data and never appears in content
    "S1": ("Ihr Gaszähler wurde am {date} abgemeldet.", "Dein Gaszähler wurde am {date} abgemeldet."),
    "S3": ("Sie haben bei uns eine Wallbox gekauft.", "Du hast bei uns eine Wallbox gekauft."),
    "S4": ("Ihre Preisgarantie endet am {date}.", "Deine Preisgarantie endet am {date}."),
    "S5": ("Ihr Datenvolumen war in den letzten Monaten mehrfach aufgebraucht.",
           "Dein Datenvolumen war in den letzten Monaten mehrfach aufgebraucht."),
    "S6": ("In Ihrem Haushalt leben mehr Personen, als SIM-Karten im Vertrag sind.",
           "In deinem Haushalt leben mehr Personen, als SIM-Karten im Vertrag sind."),
    "S7": ("Sie erzeugen bereits eigenen Strom.", "Du erzeugst bereits eigenen Strom."),
    "S8": ("Sie nutzen bereits ein HEMS von MAINGAU.", "Du nutzt bereits ein HEMS von MAINGAU."),
    "S9": ("Sie haben bereits einen Smart Meter.", "Du hast bereits einen Smart Meter."),
    "S11": ("Sie laden Ihr E-Auto bereits mit MAINGAU Autostrom.", "Du lädst dein E-Auto bereits mit MAINGAU Autostrom."),
}


# ---------------------------------------------------------------- small helpers


def de_date(iso: str | None) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else ""


def clamp(x: float) -> float:
    return min(0.95, max(0.0, x))


def clv(margin: float, cost: float, churn: float, r: float = 0.06, years: int = 10) -> float:
    return sum((margin - cost) * (1 - churn) ** (t - 1) / (1 + r) ** t for t in range(1, years + 1))


def next_weekday(t: datetime, hour: int) -> datetime:
    d = (t + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def send_at(channel: str, eval_time: datetime) -> str:
    if channel in ("portal_popup", "app_push"):
        return "next login"
    if channel == "service_agent":
        return "immediately, with the open ticket"
    return next_weekday(eval_time, 18 if channel == "sms" else 10).isoformat(timespec="seconds")


# ---------------------------------------------------------------- mock propensity (README §6.6, rate mode)


class Propensity:
    def __init__(self, history):
        treated = [r for r in history if not r.get("control_group") and r.get("delivery_status") == "delivered"]
        control = [r for r in history if r.get("control_group")]
        self.levels = defaultdict(lambda: [0, 0])
        for r in treated:
            for key in ((r["offer_id"], r["channel"], r["tonality"]), (r["offer_id"], r["channel"]), (r["offer_id"],), ()):
                self.levels[key][0] += 1
                self.levels[key][1] += bool(r.get("converted_within_14d"))
        self.control = defaultdict(lambda: [0, 0])
        for r in control:
            for key in ((r["offer_id"],), ()):
                self.control[key][0] += 1
                self.control[key][1] += bool(r.get("converted_within_14d"))
        n0, c0 = self.levels[()]
        self.prior = c0 / n0

    def __call__(self, offer: str, channel: str, tone: str, generic: bool) -> tuple[float, PSource, str]:
        if offer == "P-SV-01":
            return 0.5, PSource(mode="assumption", level="assumption"), "low"
        levels = [("offer_channel_tone", (offer, channel, tone)), ("offer_channel", (offer, channel)),
                  ("offer", (offer,)), ("global", ())]
        for name, key in levels[3 if generic else 0:]:
            n, conv = self.levels[key]
            if n >= 30 or key == ():
                own = self.control[(offer,)]
                nc, cc = own if own[0] >= 30 else self.control[()]
                p = (conv + self.prior * 30) / (n + 30) if key else conv / n
                conf = "high" if name == "offer_channel_tone" and n >= 100 else (
                    "medium" if name == "offer_channel_tone" else "low")
                return p, PSource(mode="rate", level=name, n_treated=n, conv_treated=conv, n_control=own[0],
                                  conv_control=own[1], baseline_control=round(cc / nc, 4)), conf
        raise AssertionError("unreachable")


# ---------------------------------------------------------------- mock valuation and ranking (README §6.5, §6.12)


def value(offer: str, channel: str, state, profile, catalog, p: float, src: PSource, conf: str) -> Valuation:
    cv = state.one("customer_value")
    m, c, churn = float(cv["annual_margin_eur"]), float(cv["cost_to_serve_12m_eur"]), float(cv["churn_prob_12m"])
    now = clv(m, c, churn)
    o = catalog[offer]
    margin_if = float(clean(o["annual_margin_if_bought_eur"]) or 0)
    effect = float(clean(o["churn_effect_if_bought"]) or 0)
    if offer == "P-SV-01":
        cut = sum(d.delta or 0 for d in profile.value_risk.churn_drivers
                  if d.label.startswith(SERVICE_DRIVER_PREFIXES) or d.label.endswith(SERVICE_DRIVER_SUFFIXES))
        pending = any(r.get("status") == "cancellation_pending" for r in state.rows["energy_contracts"])
        accept = clv(m, c, churn if pending else clamp(churn - cut)) - 15
    elif offer == "P-EN-02":
        accept = clv(m, c, clamp(churn - 0.10))
    elif o["action_type"] == "one_off":
        accept = clv(m, c, clamp(churn + effect)) + margin_if
    else:
        accept = clv(m + margin_if, c, clamp(churn + effect))
    cost = CONTACT_COST[channel]
    delta = p * (accept - now) - cost
    return Valuation(clv_now_shown=float(cv["clv_eur"]), clv_now_model=round(now, 2), clv_after_accept=round(accept, 2),
                     clv_after_reject=round(now, 2), p_accept=round(p, 4), p_source=src, contact_cost=cost,
                     delta_clv=round(delta, 2), confidence=conf)


def rank(state, profile, bundle: KGBundle, policy, catalog, prop) -> tuple[list[Candidate], list[Blocked], bool]:
    cands, blocked = bundle.candidates, list(bundle.blocked)
    profiled = is_profiled(state, policy)

    def val(c: Candidate) -> Valuation:
        p, src, conf = prop(c.offer_id, c.channel, c.tone, c.origin == "generic")
        return value(c.offer_id, c.channel, state, profile, catalog, p, src, conf)

    valued = [(c, val(c)) for c in cands if c.origin != "generic"]
    if not profiled or not any(v.delta_clv > 0 for _, v in valued):  # generic tier (§6.12, K12)
        valued += [(c, val(c)) for c in cands if c.origin == "generic"]
    ranked: list[Candidate] = []
    for c, v in sorted(valued, key=lambda x: (-x[1].delta_clv, -x[1].p_accept, x[1].contact_cost, x[0].offer_id, x[0].channel)):
        if v.delta_clv <= 0:
            blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="ECON-NONPOSITIVE", src="valuation",
                                   reason=f"{c.offer_name} via {c.channel}: expected ΔCLV €{v.delta_clv:.2f} ≤ 0",
                                   counterfactual_delta_clv=v.delta_clv))
            continue
        ps = v.p_source
        if ps.mode == "assumption":
            evidence = "p = 50% is an editable assumption: P-SV-01 has no history (K2)"
        else:
            evidence = (f"{c.offer_id} converted {ps.conv_treated}/{ps.n_treated} at level {ps.level} "
                        f"(control {ps.conv_control}/{ps.n_control}); p shrunk toward the 3.4% catalog average")
        notes = list(c.notes)
        if v.confidence == "low":
            notes.append("Low confidence: " + ("assumption" if ps.mode == "assumption" else f"n = {ps.n_treated} at level {ps.level}"))
        if ps.level == "global" and c.origin != "generic":
            notes.append(f"No usable history for {c.offer_id}: p is the catalog average")
        ranked.append(c.model_copy(update={"valuation": v, "rank": len(ranked) + 1, "why": c.why + [evidence], "notes": notes}))
    return ranked, blocked, profiled


# ---------------------------------------------------------------- content


def content_for(c: Candidate, signals: dict[str, Signal]) -> Content:
    subject, sie, du = COPY[c.offer_id]
    t = 0 if c.tone == "sie" else 1
    if c.offer_id == "P-SV-01" and c.tone == "du":
        subject = "Dein Anliegen bei MAINGAU"
    parts = []
    lead_sig = next((signals[s] for s in c.signals if s in LEAD and s in signals), None)
    if c.personalised and lead_sig is not None:
        parts.append(LEAD[lead_sig.id][t].format(date=de_date(lead_sig.date)))
    parts.append((sie, du)[t])
    parts.append((SERVICE_CLOSING if c.offer_id == "P-SV-01" else CLOSING)[c.tone])
    variant = "service" if c.offer_id == "P-SV-01" else ("p" if c.personalised else "g")
    return Content(language="de", tone=c.tone, personalised=c.personalised,
                   template_id=f"{c.offer_id}.{c.tone}.{variant}", subject=subject, body=" ".join(parts))


def agent_script(state, tone: str) -> str:
    open_t = sorted((t for t in state.rows["service_interactions"] if t.get("status") == "open"),
                    key=lambda t: (t.get("category") != "complaint", t["created_at"]))
    you = "Ihnen" if tone == "sie" else "dir"
    lines = ["1. Entschuldigen: „Es tut mir leid, dass es Ärger gab. Ich kümmere mich jetzt darum.“"]
    if open_t:
        lines.append(f"2. Offenes Ticket {open_t[0]['ticket_id']} ({open_t[0].get('category')}) klären und den nächsten Schritt nennen.")
    else:
        lines.append("2. Ursache klären und den nächsten Schritt mit Datum nennen.")
    lines.append(f"3. Abschließen: „Ich melde mich bei {you}, sobald das erledigt ist.“ Kein Verkaufsangebot in diesem Gespräch.")
    return "\n".join(lines)


# ---------------------------------------------------------------- card assembly


def checklist_for(top: Candidate, dq) -> list[ChecklistItem]:
    checks = {k.rule_id: k for k in top.checks}
    service = top.offer_id == "P-SV-01"
    excl = [k for k in top.checks if k.rule_id.startswith("EXCL-")]
    warns = [d.detail for d in dq if d.level == "warn"]
    return [
        ChecklistItem(item="consent_for_channel", passed=True, src="consent_status",
                      detail=checks["CONSENT-CHANNEL"].detail if "CONSENT-CHANNEL" in checks else None),
        ChecklistItem(item="profiling_consent", passed=True, src="consent_status.profiling_analytics",
                      detail=checks["CONSENT-PROFILING"].detail if "CONSENT-PROFILING" in checks
                      else "not needed: service content"),
        ChecklistItem(item="no_exclusion", passed=all(k.passed for k in excl),
                      detail="service action: exclusions never block service" if service else "no active exclusion",
                      src="energy_contracts.dunning_level, energy_contracts.status, service_interactions.status"),
        ChecklistItem(item="not_owned", passed=True,
                      detail=checks["HOLDING-PRECONDITION"].detail if "HOLDING-PRECONDITION" in checks else "not applicable"),
        ChecklistItem(item="contact_cap", passed=True, src="nba_action_history.decided_at",
                      detail=checks["CONTACT-CAP"].detail if "CONTACT-CAP" in checks else None),
        ChecklistItem(item="data_fresh", passed=not warns, detail="; ".join(warns) or "all sources within latency"),
    ]


def legacy_for(state, profile, policy, catalog, prop) -> LegacyComparison | None:
    hist = sorted((r for r in state.rows["nba_action_history"] if not r.get("control_group")), key=lambda r: r["decided_at"])
    if not hist:
        return None
    h = hist[-1]
    offer, channel = h["offer_id"], h["channel"]
    by_now = []
    if offer in policy.offers and policy.offers[offer].action_type in MARKETING_TYPES:
        by_now += [rule for rule, _ in active_exclusions(state, policy)]
    if not any(c.channel == channel and c.allowed for c in profile.channels):
        by_now.append("CONSENT-CHANNEL")
    if not is_profiled(state, policy):
        by_now.append("CONSENT-PROFILING")
    if owns(state, offer):
        by_now.append("HOLDING-PRECONDITION")
    delta = None
    if offer in policy.offers and channel in CONTACT_COST and offer not in ("P-IN-01", "P-EN-04"):
        p, src, conf = prop(offer, channel, h.get("tonality") or "sie", False)
        delta = value(offer, channel, state, profile, catalog, p, src, conf).delta_clv
    return LegacyComparison(rule_id=h.get("rule_id"), offer_id=offer, channel=channel, decided_at=day(h["decided_at"]),
                            delta_clv_our_model=delta, blocked_now_by=by_now)


def build_card(state, policy, catalog, pop, kg_pop, prop, sources) -> CustomerCard:
    profile = build_profile(state, pop)
    bundle = kg_bundle(state, policy, kg_pop, tone=profile.header.tone.value)
    signals, tri, dq = bundle.signals, bundle.triage, bundle.data_quality
    sig = {s.id: s for s in signals}
    cands, blocked, _ = rank(state, profile, bundle, policy, catalog, prop)
    excl = [e for e in profile.exclusions if e.active]
    open_ticket = any(t.get("status") == "open" for t in state.rows["service_interactions"])

    if cands:
        top = cands[0]
        v = top.valuation
        s = next((sig[i] for i in top.signals if i in sig), None)
        lead = f"{s.detail} [{s.id}] → " if s else ("Generic catalog offer → " if top.origin == "generic" else "")
        reason = (f"{lead}{top.offer_name} via {top.channel}, +€{v.delta_clv:.2f} expected CLV "
                  f"(p {v.p_accept * 100:.1f}%, {v.confidence} confidence)")
        service = top.offer_id == "P-SV-01"
        chosen = Chosen(tuple_id=top.tuple_id, status="proposed", send_at=send_at(top.channel, state.eval_time),
                        reason_line=reason, service_mode=service or open_ticket,
                        agent_script=agent_script(state, top.tone) if service else None, content=content_for(top, sig))
        explanation, checklist = top.path, checklist_for(top, dq)
    else:
        if any(b.rule_id == "ECON-NONPOSITIVE" for b in blocked):
            reason = "No action: no candidate has expected ΔCLV > 0"
            if any(e.rule_id == "EXCL-CANCELLATION" for e in excl):
                reason += " (service cannot lower churn 0.95 during a pending cancellation)"
        elif excl:
            reason = f"No action: all sales blocked ({excl[0].detail})"
        else:
            reason = "No action: every candidate is blocked by consent, holdings or the contact cap"
        chosen = Chosen(tuple_id=NO_ACTION, status="proposed", reason_line=reason, service_mode=open_ticket)
        explanation = [PathStep(kind="node", type="Customer", id=state.customer_id, ui_ref="header")]
        checklist = []

    alternatives, seen = [], {cands[0].offer_id} if cands else set()
    for c in cands[1:]:
        if c.offer_id in seen or len(alternatives) == 3:
            continue
        seen.add(c.offer_id)
        best = cands[0].valuation
        why = f"lower expected ΔCLV (−€{best.delta_clv - c.valuation.delta_clv:.2f})"
        if c.valuation.p_accept < best.p_accept:
            why += f"; lower p ({c.valuation.p_accept * 100:.1f}% vs {best.p_accept * 100:.1f}%)"
        alternatives.append(Alternative(tuple_id=c.tuple_id, delta_clv=c.valuation.delta_clv, why_lower=why))

    top_v = cands[0].valuation if cands else None
    log = [DecisionLogEntry(
        ts=state.eval_time.isoformat(timespec="seconds"), actor="engine", action="proposed", tuple_id=chosen.tuple_id,
        reason=chosen.reason_line, state_revision=state.revision, versions=VERSIONS.model_dump(),
        rules_applied=sorted({b.rule_id for b in blocked}),
        scores={"delta_clv": top_v.delta_clv, "p_accept": top_v.p_accept} if top_v else {},
    )]
    return CustomerCard(
        customer_id=state.customer_id,
        meta=Meta(eval_time=state.eval_time.isoformat(timespec="seconds"), snapshot_mode="provided",
                  mode_default="service" if chosen.service_mode else "marketing", versions=VERSIONS,
                  state_revision=state.revision),
        sources=sources, triage=tri, profile=profile, timeline=build_timeline(state), signals=signals,
        candidates=cands, blocked=blocked, chosen=chosen, alternatives=alternatives,
        legacy_comparison=legacy_for(state, profile, policy, catalog, prop), explanation_path=explanation,
        checklist=checklist, data_quality=dq, decision_log=log,
    )


def index_row(card: CustomerCard) -> IndexRow:
    p = card.profile
    top = card.candidates[0] if card.candidates else None
    v = top.valuation if top else None
    return IndexRow(
        customer_id=card.customer_id, age_band=p.header.age_band.v, city=p.header.city.v,
        lines=p.value_risk.active_business_lines.v, clv_eur=p.value_risk.clv_eur.v, churn=p.value_risk.churn_prob_12m.v,
        archetype=card.triage.archetype.id, archetype_name=card.triage.archetype.name,
        urgency_tier=card.triage.urgency_tier, urgency_score=card.triage.urgency_score,
        top_reason=card.triage.urgency_reasons[0] if card.triage.urgency_reasons else None,
        flags=[f.id for f in card.triage.flags], outlier=card.triage.outlier, triggers=[s.id for s in card.signals],
        chosen_offer=top.offer_id if top else NO_ACTION, chosen_tuple=card.chosen.tuple_id,
        channel=top.channel if top else None, tone=top.tone if top else None,
        delta_clv=v.delta_clv if v else None, p_accept=v.p_accept if v else None,
        contact_cost=v.contact_cost if v else None, confidence=v.confidence if v else None,
        checklist_failed=[i.item for i in card.checklist if not i.passed],
        service_mode=card.chosen.service_mode, personalised=top.personalised if top else None,
        n_signals=len(card.signals), n_candidates=len(card.candidates), n_blocked=len(card.blocked),
        exclusions=[e.rule_id for e in p.exclusions if e.active],
    )


def summary(cards: list[CustomerCard], sources: dict[str, SourceInfo]) -> Summary:
    chosen: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum_delta_clv": 0.0})
    blocked, no_action, signals, arch, tiers, flags = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for c in cards:
        if c.candidates:
            top = c.candidates[0]
            chosen[top.offer_id]["count"] += 1
            chosen[top.offer_id]["sum_delta_clv"] = round(chosen[top.offer_id]["sum_delta_clv"] + top.valuation.delta_clv, 2)
        else:
            no_action[c.chosen.reason_line.removeprefix("No action: ").split(" (")[0]] += 1
        blocked.update(b.rule_id for b in c.blocked)
        signals.update(s.id for s in c.signals)
        arch[c.triage.archetype.id] += 1
        tiers[c.triage.urgency_tier] += 1
        flags.update(f.id for f in c.triage.flags)
    return Summary(eval_time=cards[0].meta.eval_time, n_customers=len(cards), chosen_by_offer=dict(sorted(chosen.items())),
                   blocked_by_rule=dict(sorted(blocked.items())), no_action_by_reason=dict(sorted(no_action.items())),
                   signal_counts=dict(sorted(signals.items())), archetype_counts=dict(sorted(arch.items())),
                   urgency_counts=dict(sorted(tiers.items())), flag_counts=dict(sorted(flags.items())),
                   sources=sources, column_src=COLUMN_SRC,
                   value_date=cards[0].profile.value_risk.clv_eur.updated_at)


# ---------------------------------------------------------------- customer selection


def features(card: CustomerCard) -> set[str]:
    out = {f"arch:{card.triage.archetype.id}", f"tier:{card.triage.urgency_tier}",
           f"tone:{card.profile.header.tone.method}", f"offer:{card.chosen.tuple_id.split('|')[0]}"}
    out |= {f"flag:{f.id}" for f in card.triage.flags}
    out |= {f"origin:{c.origin}" for c in card.candidates[:1]}
    out |= {f"conf:{c.valuation.confidence}" for c in card.candidates[:1]}
    out |= {f"dq:{d.code}" for d in card.data_quality}
    out |= {f"block:{b.rule_id}" for b in card.blocked}
    if card.profile.trends.hems:
        out.add("trend:hems")
    if any(c.override_reason for c in card.profile.consent):
        out.add("consent:override")
    if any(not i.passed for i in card.checklist):
        out.add("checklist:fail")
    return out


def select(cards: dict[str, CustomerCard]) -> list[str]:
    chosen = list(dict.fromkeys(REPRESENTATIVES + TEST_CUSTOMERS))
    # Bulk demo: the two most common marketing tuples get 4–6 members, with an outlier and a failing checklist if possible.
    tuples = Counter(c.chosen.tuple_id for c in cards.values() if c.chosen.tuple_id != NO_ACTION and not c.chosen.service_mode)
    for t, _ in tuples.most_common(2):
        members = sorted(cid for cid, c in cards.items() if c.chosen.tuple_id == t and cid not in chosen)
        outlier = [m for m in members if cards[m].triage.outlier][:1]
        failing = [m for m in members if m not in outlier and any(not i.passed for i in cards[m].checklist)][:1]
        plain = [m for m in members if m not in outlier + failing and not cards[m].triage.outlier][:4]
        chosen += outlier + failing + plain
    covered = set().union(*(features(cards[c]) for c in chosen))
    while len(chosen) < N_TOTAL:
        rest = sorted(set(cards) - set(chosen))
        best = max(rest, key=lambda cid: len(features(cards[cid]) - covered))
        if not features(cards[best]) - covered:
            per_tier = Counter(cards[c].triage.urgency_tier for c in chosen)
            best = min(rest, key=lambda cid: (per_tier[cards[cid].triage.urgency_tier], cid))
        chosen.append(best)
        covered |= features(cards[best])
    return chosen


# ---------------------------------------------------------------- main


def dump(path: Path, data, compact: bool = False) -> None:
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, **({"separators": (",", ":")} if compact else {"indent": 1}))
    path.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default web/public/data)")
    ap.add_argument("--force", action="store_true", help="replace a folder that does not hold mock data")
    args = ap.parse_args()
    out = args.out.resolve()
    tables = load_workbook()
    states = build_states(tables)
    policy = load_policy()
    pop, kg_pop = profile_population(states), population(tables)
    prop = Propensity(tables["nba_action_history"].to_dict("records"))
    catalog = {r["product_id"]: r for r in tables["product_catalog"].to_dict("records")}
    sources = source_info(tables)

    cards = {cid: build_card(s, policy, catalog, pop, kg_pop, prop, sources) for cid, s in sorted(states.items())}
    picked = [cards[cid] for cid in select(cards)]

    if out.exists():
        manifest = out / "manifest.json"
        is_mock = manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")).get("source") == "mock"
        if not is_mock and not args.force:
            # A real export (Agent KG / `nba.build --export`) lives here; never overwrite it with mock data.
            sys.exit(f"{out} holds a non-mock export; not overwriting (pass --force to replace it)")
        shutil.rmtree(out)
    (out / "customers").mkdir(parents=True)
    for card in picked:
        dump(out / "customers" / f"{card.customer_id}.json",
             CustomerCard.model_validate(card.model_dump()).model_dump(mode="json"), compact=True)
    rows = sorted((index_row(c) for c in picked), key=lambda r: (r.urgency_tier, -r.urgency_score, r.customer_id))
    dump(out / "index.json", [r.model_dump(mode="json") for r in rows])
    dump(out / "summary.json", summary(picked, sources).model_dump(mode="json"))
    dump(out / "manifest.json", {
        "source": "mock",
        "generator": "web/mock/build_mock.py",
        "snapshot": "data/maingau_nba_mockdata.xlsx at 2026-09-30T23:59:59",
        "real": ["profile (nba.profile)", "timeline", "sources", "signals, candidates, blocked, triage, paths, "
                 "consent/channels/exclusions, data_quality (nba.kg.bundle.kg_bundle)"],
        "mock": ["valuation", "rank", "chosen", "content", "alternatives",
                 "legacy_comparison.delta_clv_our_model", "decision_log scores"],
        "customers": len(picked),
    })
    tiers = Counter(c.triage.urgency_tier for c in picked)
    print(f"wrote {len(picked)} cards to {out}; tiers {dict(sorted(tiers.items()))}")


if __name__ == "__main__":
    main()
