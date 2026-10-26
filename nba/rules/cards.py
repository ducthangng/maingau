"""The marketer rulebook: every rule as a plain-language card, no internal IDs.

Each editable field knows how to read its value from the four rule files and how to write a new
value back, so `diff` / `apply` / the hard-rule check work on the same files as before. Rules a
marketer may not change (consent, exclusions, service first, ...) are shown as text only.
"""
from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml

CHANNEL_NAMES = {"newsletter_email": "Newsletter", "email": "Email", "outbound_call": "Phone call", "sms": "SMS",
                 "portal_popup": "Portal pop-up", "app_push": "App push", "service_agent": "Service agent"}
TONE_NAMES = {"du": "Du", "sie": "Sie"}
CONSENT_NAMES = {"newsletter_email": "newsletter consent", "marketing_email": "email marketing consent",
                 "marketing_phone": "phone marketing consent", "marketing_sms": "SMS marketing consent",
                 "portal_app_personalisation": "portal/app personalisation consent",
                 "profiling_analytics": "profiling consent"}
ACTION_NAMES = {"sales": "New product", "upsell": "Upgrade", "retention": "Keep the customer", "one_off": "Shop product"}
LINE_NAMES = {"energy": "energy", "mobile": "mobile", "internet": "internet", "smart_living": "smart living",
              "shop": "online shop", "e_mobility": "e-mobility"}
ICON = {"green": "🟢 working", "amber": "🟡 not clear yet", "red": "🔴 not working"}
RULEBOOK_CASE = "RULEBOOK"


class CardError(ValueError):
    """The edited rulebook cannot be read (renamed card, unknown choice, wrong type)."""


@dataclass
class Field:
    name: str
    get: Callable[[dict], Any]
    set: Callable[[dict, Any], None]
    kind: str = "bool"  # bool | int | percent | choice | channels | tones | text
    choices: tuple = ()
    hard: bool = False
    note: str = ""


@dataclass
class Card:
    title: str
    lines: list[str] = field(default_factory=list)
    fields: list[Field] = field(default_factory=list)


@dataclass
class Section:
    title: str
    intro: list[str]
    cards: list[Card] = field(default_factory=list)


# ---------------------------------------------------------------- names


class Names:
    def __init__(self, sections: dict, catalog_names: dict[str, str]):
        self.offer = dict(catalog_names)
        self.offer_id = {v: k for k, v in catalog_names.items()}
        self.signal = {sid: s["label"] for sid, s in sections["policy"]["signals"].items()}
        self.need = {nid: n["label_en"] for nid, n in sections["policy"]["needs"].items()}

    def tuple(self, tuple_id: str) -> str:
        if tuple_id in (None, "NO_ACTION"):
            return "No action"
        tuple_id, _, wait = tuple_id.partition("@")  # "@<date>": held back by a Rule Center rule until then
        offer, channel, tone = (tuple_id.split("|") + ["", ""])[:3]
        name = " · ".join(x for x in (self.offer.get(offer, offer), CHANNEL_NAMES.get(channel, channel),
                                      TONE_NAMES.get(tone, tone)) if x)
        return f"{name} (waits until {wait})" if wait else name

    def pattern(self, key: str) -> str:
        offer, _, channel = key.partition("|")
        return self.offer.get(offer, offer) + (f" by {CHANNEL_NAMES.get(channel, channel)}" if channel else "")

    def offer_or_none(self, offer_id: str) -> str:
        return "No action" if offer_id == "NO_ACTION" else self.offer.get(offer_id, offer_id)


# ---------------------------------------------------------------- accessors on the four rule files


def _overrides(s: dict) -> dict:
    return s["nba"].get("p_overrides") or {}


def _off_payload(by: str, what: str) -> dict:
    return {"p": 0.0, "case": RULEBOOK_CASE, "approved_by": by, "basis": f"{what} (marketer rulebook)"}


def _toggle_override(s: dict, key: str, off: bool, by: str, what: str) -> None:
    current = _overrides(s).get(key)
    if off and not (current and float(current["p"]) == 0.0):
        s["nba"].setdefault("p_overrides", {})
        s["nba"]["p_overrides"] = {**(s["nba"]["p_overrides"] or {}), key: _off_payload(by, what)}
    elif not off and current and float(current["p"]) == 0.0:
        s["nba"]["p_overrides"] = {k: v for k, v in _overrides(s).items() if k != key}


def _enabled(s: dict) -> list[str]:
    return list(s["kg"].get("signals", {}).get("enabled") or s["policy"]["signals"])


def _set_enabled(s: dict, sid: str, on: bool) -> None:
    current = set(_enabled(s))
    current = current | {sid} if on else current - {sid}
    s["kg"]["signals"]["enabled"] = [x for x in s["policy"]["signals"] if x in current]


def _set_cap_source(s: dict, source: str, on: bool) -> None:
    current = list(s["kg"]["contact_cap"].get("sources") or ["nba_history"])
    current = current + [source] if on and source not in current else [x for x in current if on or x != source]
    s["kg"]["contact_cap"]["sources"] = current


BUSINESS_TITLES = {"B-01": "E-mails per customer", "B-03": "Calls per customer", "B-04": "SMS per customer",
                   "B-05": "Pause an offer after dismissals", "B-06": "No sales right after a ticket",
                   "B-08": "Minimum value for a call", "B-09": "Calls per week"}


def _set_generic(s: dict, oid: str, on: bool) -> None:
    current = set(s["kg"]["generic"]["offers"])
    current = current | {oid} if on else current - {oid}
    s["kg"]["generic"]["offers"] = [x for x in s["policy"]["offers"] if x in current]


def _path(*keys):
    def get(s):
        node = s
        for k in keys:
            node = node[k]
        return node

    def put(s, value):
        node = s
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return get, put


def _mapped(get, put, mapping: dict):
    back = {v if not isinstance(v, list) else tuple(v): k for k, v in mapping.items()}
    return (lambda s: back[tuple(get(s)) if isinstance(get(s), list) else get(s)],
            lambda s, label: put(s, copy.deepcopy(mapping[label])))


# ---------------------------------------------------------------- the model


def build(sections: dict, names: Names, stats: dict | None, by: str = "preview") -> list[Section]:
    pol, kg = sections["policy"], sections["kg"]
    st = stats or {}
    offers_of_need = defaultdict(list)
    for oid, o in pol["offers"].items():
        for n in o.get("addresses", []):
            offers_of_need[n].append(oid)
    signals_of_offer = defaultdict(list)
    for sid, s in pol["signals"].items():
        for n in s.get("indicates", []):
            for oid in offers_of_need[n]:
                signals_of_offer[oid].append(sid)
    out: list[Section] = []

    # 1. signals
    act = Section("When to act", [
        "Each card is a customer situation the engine reacts to, and the offers it leads to.",
        "active: no  -> the engine ignores this situation (customers can still get the offer another way).",
    ])
    for sid, s in pol["signals"].items():
        if s["purpose"] == "service":
            continue
        card = Card(s["label"])
        if s.get("reinforces"):
            card.lines.append("Evidence only: strengthens " + " and ".join(f"'{names.need[n]}'" for n in s["reinforces"])
                              + " for other situations; never creates an offer by itself.")
        for n in s.get("indicates", []):
            offers = [names.offer[o] for o in offers_of_need[n] if not pol["offers"][o].get("data_missing")]
            card.lines.append(f"Means: {names.need[n]}  ->  offers: {', '.join(offers) or 'none'}")
        shared = sorted({names.signal[o] for oid in (o for n in s.get("indicates", []) for o in offers_of_need[n])
                         for o in signals_of_offer[oid] if o != sid})
        if shared:
            card.lines.append("Also reached through: " + "; ".join(shared))
        card.lines.append(f"Signal strength: {s['strength']}")
        if sid in st.get("signal_customers", {}):
            card.lines.append(f"Today: {st['signal_customers'][sid]} customers show this; it drives the "
                              f"recommendation for {st['signal_chosen'].get(sid, 0)}")
        card.fields.append(Field("active", lambda x, sid=sid: sid in _enabled(x),
                                 lambda x, v, sid=sid: _set_enabled(x, sid, v)))
        act.cards.append(card)
    out.append(act)

    # 2. offers
    sec = Section("Offers", [
        "One card per offer. active: no stops the offer everywhere.",
        "also without a signal: yes  -> it may go out as a non-personalised catalog offer when nothing better fits.",
        "never by / never in tone  -> block single channels (Newsletter, Email, Phone call, SMS, Portal pop-up, App push) or Du / Sie.",
    ])
    for oid, o in pol["offers"].items():
        if oid == "P-SV-01" or o.get("data_missing"):
            continue
        name = names.offer[oid]
        meta = st.get("offers", {}).get(oid, {})
        card = Card(name)
        margin = meta.get("margin")
        kind = ACTION_NAMES.get(meta.get("action_type"), meta.get("action_type", ""))
        line = LINE_NAMES.get(meta.get("business_line"), meta.get("business_line", ""))
        if margin is not None:
            per = "once" if meta.get("action_type") == "one_off" else "a year"
            gain = ("lowers the risk of leaving (no new margin)" if meta.get("action_type") == "retention"
                    else f"about {margin:.0f} € margin {per} if bought")
            card.lines.append(f"{kind} · {line} · {gain}")
        sigs = sorted({names.signal[x] for x in signals_of_offer[oid]})
        generic = oid in sections["kg"]["generic"]["offers"]
        card.lines.append("Triggered by: " + ("; ".join(sigs) if sigs else "no situation; only as a catalog offer"
                                              + ("" if generic else " -> with 'also without a signal: no' it is never recommended")))
        if "loop" in meta:
            lp = meta["loop"]
            card.lines.append(f"Feedback: {ICON[lp['status']]} · {lp['conv']} of {lp['n']} past sends led to a purchase "
                              f"(customers we did not contact: {lp['conv_c']} of {lp['n_c']})")
        elif st:
            card.lines.append("Feedback: never sent before; no evidence yet")
        if st:
            card.lines.append(f"Recommended today to {st.get('chosen_offer', {}).get(oid, 0)} customers")
        ov = _overrides(sections).get(oid)
        if ov and float(ov["p"]) > 0:
            card.lines.append(f"Take-up rate set by review {ov.get('case')}: {float(ov['p']):.1%}")
        card.fields += [
            Field("active", lambda x, oid=oid: not ((_overrides(x).get(oid) or {}).get("p", 1) == 0),
                  lambda x, v, oid=oid, name=name: _toggle_override(x, oid, not v, by, f"{name} turned off")),
            Field("also without a signal", lambda x, oid=oid: oid in x["kg"]["generic"]["offers"],
                  lambda x, v, oid=oid: _set_generic(x, oid, v)),
            Field("never by", lambda x, oid=oid: [CHANNEL_NAMES[c] for c in pol["channels"]
                                                  if (_overrides(x).get(f"{oid}|{c}") or {}).get("p", 1) == 0],
                  lambda x, v, oid=oid, name=name: [
                      _toggle_override(x, f"{oid}|{c}", CHANNEL_NAMES[c] in v, by, f"{name} never by {CHANNEL_NAMES[c]}")
                      for c in pol["channels"]], kind="channels"),
            Field("never in tone", lambda x, oid=oid: [TONE_NAMES[t] for t in TONE_NAMES
                                                       if (_overrides(x).get(f"{oid}|*|{t}") or {}).get("p", 1) == 0],
                  lambda x, v, oid=oid, name=name: [
                      _toggle_override(x, f"{oid}|*|{t}", TONE_NAMES[t] in v, by, f"{name} never in {TONE_NAMES[t]}")
                      for t in TONE_NAMES], kind="tones"),
        ]
        sec.cards.append(card)
    out.append(sec)

    # 3. contact limits and scopes (hard rules: editable with a named sign-off)
    lim = Section("Contact limits and blocks", [
        "🔒 Hard rules. You may change them, but `apply` needs the rule owner's --sign-off NAME.",
    ])
    g1, p1 = _path("kg", "contact_cap", "max_contacts")
    g2, p2 = _path("kg", "contact_cap", "window_days")
    cap = Card("Marketing contact limit", ["Service contacts never count. Offers a service agent mentioned count as a call."],
               [Field("max contacts", g1, p1, "int", hard=True), Field("within days", g2, p2, "int", hard=True),
                Field("newsletters count", lambda x: "newsletter" in (x["kg"]["contact_cap"].get("sources") or []),
                      lambda x, v: _set_cap_source(x, "newsletter", v), hard=True)])
    g, p = _mapped(*_path("kg", "exclusions", "autostrom_cancelled_scope"),
                   {"all sales offers": "all_sales", "only e-mobility offers": "e_mobility"})
    auto = Card("After an Autostrom contract was cancelled", [],
                [Field("block", g, p, "choice", ("all sales offers", "only e-mobility offers"), hard=True)])
    g, p = _mapped(*_path("kg", "consent", "unsubscribe_withdraws"),
                   {"newsletter only": ["newsletter_email"], "newsletter and email marketing": ["newsletter_email", "marketing_email"]})
    unsub = Card("A newsletter unsubscribe stops", [],
                 [Field("stops", g, p, "choice", ("newsletter only", "newsletter and email marketing"), hard=True)])
    lim.cards += [cap, auto, unsub]
    out.append(lim)

    # 3b. Rule Center business rules (docs/rule-center.md tier 2)
    biz = Section("Pauses and limits per channel", [
        "Checked for every offer and channel. A paused action waits for its first allowed day; a blocked one is dropped.",
    ])
    for rid, r in (sections["nba"].get("business_rules") or {}).items():
        card = Card(BUSINESS_TITLES.get(rid, r.get("name", rid)))
        card.fields.append(Field("active", *_path("nba", "business_rules", rid, "active")))
        for key, label in (("max", "at most"), ("window_days", "within days"), ("min_responses", "after dismissals"),
                           ("cooldown_days", "pause days")):
            if key in r:
                card.fields.append(Field(label, *_path("nba", "business_rules", rid, key), "int"))
        for ch in r.get("min_eur") or {}:
            card.fields.append(Field(f"minimum € by {CHANNEL_NAMES[ch]}", *_path("nba", "business_rules", rid, "min_eur", ch), "int"))
        for ch in r.get("per_week") or {}:
            card.fields.append(Field(f"{CHANNEL_NAMES[ch]} per week", *_path("nba", "business_rules", rid, "per_week", ch), "int"))
        biz.cards.append(card)
    out.append(biz)

    # 4. how offers compete
    val = Section("How offers compete", ["The engine ranks allowed offers by expected gain in customer value (€)."])
    g, p = _mapped(*_path("nba", "p_mode"), {"how likely they buy": "rate", "extra buyers we cause": "uplift"})
    gf, pf = _path("kg", "generic", "fallback_for_profiled")
    gs, ps = _path("nba", "p_service_success")
    val.cards += [
        Card("Rank offers by", ["'extra buyers we cause' subtracts customers who would have bought anyway (control group)."],
             [Field("rank by", g, p, "choice", ("how likely they buy", "extra buyers we cause"))]),
        Card("Catalog offers as a fallback", ["For customers with profiling consent: use a non-personalised catalog offer when "
                                              "no situation-based offer pays off."],
             [Field("use fallback", gf, pf)]),
        Card("Service fix success", ["Assumed chance that a proactive service fix resolves the problem (no history yet)."],
             [Field("success chance", gs, ps, "percent")]),
    ]
    out.append(val)

    # 5. timing
    tim = Section("When messages go out", [])
    ge, pe = _path("nba", "send_time", "email_hour")
    gsm, psm = _path("nba", "send_time", "sms_hour")
    gc, pc = _path("nba", "send_time", "call_window")
    tim.cards.append(Card("Send times", ["Next weekday after the decision. Portal and app messages show at the next login."],
                          [Field("email at hour", ge, pe, "int"), Field("SMS at hour", gsm, psm, "int"),
                           Field("calls between", gc, pc, "text")]))
    out.append(tim)

    # 6. feedback loop
    loop = Section("Feedback loop", ["How the loop judges an offer against customers we did not contact (the control group)."])
    gm, pm = _path("learn", "status", "min_treated")
    gg, pg = _path("learn", "status", "green_p_positive")
    gr, pr = _path("learn", "status", "red_p_positive")
    gz, pz = _path("learn", "status", "red_zero_response_n")
    loop.cards.append(Card("Judging an offer", [], [
        Field("judge after sends", gm, pm, "int"),
        Field("working when chance it helps is at least", gg, pg, "percent"),
        Field("not working when chance it helps is at most", gr, pr, "percent"),
        Field("alarm after sends with zero purchases", gz, pz, "int"),
    ]))
    ga, pa = _path("learn", "lookalike", "active")
    gk, pk = _path("learn", "lookalike", "neighbours")
    loop.cards.append(Card("Learn from similar customers", [
        "Offers marked working learn who bought them. Customers who look like the buyers get a higher chance,",
        "customers who look like the non-buyers a lower one. Only customers with profiling consent take part.",
        "See one customer: python -m nba.learn similar MG-100001",
    ], [Field("active", ga, pa, "bool"), Field("similar customers compared", gk, pk, "int")]))
    out.append(loop)
    return out


def fixed_rules(sections: dict, names: Names) -> list[str]:
    pol = sections["policy"]
    lines = ["Consent per channel:"]
    for ch, c in pol["channels"].items():
        extra = " with double opt-in" if c.get("needs_doi") else ""
        need = {"portal_account": " and a portal account", "app_installed": " and the app installed"}.get(c.get("requires_field"), "")
        lines.append(f"  - {CHANNEL_NAMES[ch]} needs {CONSENT_NAMES.get(c['consent'], c['consent'])}{extra}{need}")
    lines.append("No sales, upgrade, retention or shop offer while:")
    lines += [f"  - {e['label']}" for e in pol["exclusions"].values()]
    lines += [
        "Service first: an open ticket, failed charging or dunning gets a service fix, never a sales message.",
        "Without profiling consent: no situation is used; only catalog offers, formal Sie, marked 'nicht personalisiert'.",
        "Nobody is offered a product they already have.",
        "Every action needs human approval; nothing is sent automatically. Payment data is only used to block offers.",
        "Customer messages are in German; no personalised prices and no false urgency.",
    ]
    for oid, o in pol["offers"].items():
        if o.get("data_missing"):
            lines.append(f"{names.offer[oid]} is not offered: {o['data_missing'].lower()}.")
    return lines


# ---------------------------------------------------------------- render and parse


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _show(f: Field, value) -> str:
    if f.kind == "bool":
        return "yes" if value else "no"
    if f.kind == "percent":
        return _q(f"{float(value) * 100:g}%")
    if f.kind in {"channels", "tones"}:
        return "[" + ", ".join(_q(v) for v in value) + "]"
    if f.kind in {"choice", "text"}:
        return _q(value)
    return str(value)


HEADER = """\
# MAINGAU rulebook for marketing: every rule the engine follows, in plain language.
#
#   Change a value after a colon (yes / no, a number, a choice, a list of channels).
#   Then run:  python -m nba.rules diff    -> what would change for our customers, and a safety check
#              python -m nba.rules apply --by "Your name"   -> make it the new rule
#              python -m nba.rules reset   -> throw your changes away
#
#   Do not rename the cards (the names in quotes). Lines starting with # are explanations and today's numbers.
"""


def render(sections: dict, names: Names, stats: dict | None, base: str) -> str:
    lines = [HEADER, f"_base: {base}   # fingerprint of the rules this file was made from; do not edit", ""]
    for sec in build(sections, names, stats):
        lines += ["", "# " + "=" * 96, f"# {sec.title.upper()}"] + [f"# {x}" for x in sec.intro] + ["# " + "=" * 96]
        lines.append(f"{_q(sec.title)}:")
        for card in sec.cards:
            lines.append("")
            lines += [f"  # {x}" for x in card.lines]
            lines.append(f"  {_q(card.title)}:")
            for f in card.fields:
                choices = f"   # one of: {' | '.join(f.choices)}" if f.choices else ""
                lock = "   # 🔒 hard rule" if f.hard and not choices else (choices + "  🔒 hard rule" if f.hard else choices)
                lines.append(f"    {f.name}: {_show(f, f.get(sections))}{lock}")
    lines += ["", "# " + "=" * 96, "# FIXED RULES (not editable here; set by law, consent and the challenge rules)", "# " + "=" * 96]
    lines += [f"# {x}" for x in fixed_rules(sections, names)]
    return "\n".join(lines) + "\n"


def _parse(f: Field, raw, where: str):
    if f.kind == "bool":
        if not isinstance(raw, bool):
            raise CardError(f"{where}: write yes or no (got {raw!r})")
        return raw
    if f.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise CardError(f"{where}: write a whole number (got {raw!r})")
        return raw
    if f.kind == "percent":
        m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*", str(raw))
        if not m:
            raise CardError(f"{where}: write a percentage like 90% (got {raw!r})")
        value = float(m.group(1))
        value = value / 100 if (str(raw).strip().endswith("%") or value > 1) else value
        if not 0 <= value <= 1:
            raise CardError(f"{where}: a percentage must be between 0% and 100%")
        return round(value, 6)
    if f.kind == "choice":
        if raw not in f.choices:
            raise CardError(f"{where}: choose one of {', '.join(f.choices)} (got {raw!r})")
        return raw
    if f.kind in {"channels", "tones"}:
        allowed = list(CHANNEL_NAMES.values())[:6] if f.kind == "channels" else list(TONE_NAMES.values())
        items = [] if raw is None else raw if isinstance(raw, list) else [raw]
        lookup = {a.lower(): a for a in allowed}
        bad = [x for x in items if str(x).strip().lower() not in lookup]
        if bad:
            raise CardError(f"{where}: unknown {', '.join(map(str, bad))}; use {', '.join(allowed)}")
        chosen = {lookup[str(x).strip().lower()] for x in items}
        return [a for a in allowed if a in chosen]
    return str(raw)


@dataclass(frozen=True)
class CardChange:
    section: str
    card: str
    field: str
    before: Any
    after: Any
    hard: bool

    @property
    def where(self) -> str:
        return f"{self.section} › {self.card} › {self.field}"


def compile_cards(text: str, base_sections: dict, names: Names, by: str = "preview") -> tuple[dict, list[CardChange], str]:
    """Edited rulebook text -> (edited rule files, marketer-level changes, the _base fingerprint)."""
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise CardError(f"rules.yaml is not valid: {exc}") from exc
    edited = copy.deepcopy(base_sections)
    found: list[CardChange] = []
    for sec in build(base_sections, names, None, by):
        sec_doc = doc.get(sec.title)
        if not isinstance(sec_doc, dict):
            raise CardError(f"Section '{sec.title}' is missing; do not rename sections")
        unknown = sorted(set(sec_doc) - {c.title for c in sec.cards})
        if unknown:
            raise CardError(f"Unknown card(s) in '{sec.title}': {', '.join(unknown)}; do not rename cards")
        for card in sec.cards:
            card_doc = sec_doc.get(card.title)
            if not isinstance(card_doc, dict):
                raise CardError(f"Card '{card.title}' in '{sec.title}' is missing")
            for f in card.fields:
                where = f"{sec.title} › {card.title} › {f.name}"
                if f.name not in card_doc:
                    raise CardError(f"{where} is missing")
                new, old = _parse(f, card_doc[f.name], where), f.get(base_sections)
                if f.kind == "percent":
                    old = round(float(old), 6)
                if new != old:
                    f.set(edited, new)
                    found.append(CardChange(sec.title, card.title, f.name, old, new, f.hard))
    return edited, found, str(doc.get("_base", ""))


def show_value(change: CardChange, value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(value) or "(none)"
    if isinstance(value, float) and "chance" in change.field:
        return f"{value:.0%}"
    return str(value)


# ---------------------------------------------------------------- live numbers for the explanations


def stats_for(runtime) -> dict:
    from nba.learn.evidence import Evidence
    from nba.learn.health import patterns

    cards = runtime.cards()
    signal_customers, signal_chosen, chosen_offer = Counter(), Counter(), Counter()
    for card in cards:
        signal_customers.update({s.id for s in card.signals})
        chosen = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
        if chosen:
            chosen_offer[chosen.offer_id] += 1
            signal_chosen.update(set(chosen.signals))
    loop = {p.offer_id: p for p in patterns(Evidence.from_runtime(runtime)) if p.channel is None}
    offers = {}
    for oid, o in runtime.cfg.offers.items():
        offers[oid] = {"margin": float(o["annual_margin_if_bought_eur"]), "action_type": o["action_type"],
                       "business_line": o["business_line"]}
        if oid in loop:
            r = loop[oid].result
            offers[oid]["loop"] = {"status": loop[oid].status, "n": r.treated.n, "conv": r.treated.conv,
                                   "n_c": r.control.n, "conv_c": r.control.conv}
    return {"signal_customers": dict(signal_customers), "signal_chosen": dict(signal_chosen),
            "chosen_offer": dict(chosen_offer), "offers": offers}
