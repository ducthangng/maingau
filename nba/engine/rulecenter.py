"""Rule Center tier 2 (docs/rule-center.md): business and custom rules per offer × channel, after valuation.

Owner: Agent NBA. Tier 1 (C-01..C-09) and B-02 / B-07 are KG gates (nba.kg.rules); this module reads their
outcome for the rule report, applies B-01, B-03..B-06, B-08, B-09 and custom rules, and decides
DEFER_UNTIL: a tuple held back only for now (frequency, cooldown, capacity, the contact cap) waits for the
earliest allowed time; a blocked tuple is dropped. Service actions are exempt from every tier 2 rule.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from nba.contracts import NO_ACTION, Blocked, Candidate, ContactCounter, RuleReport, RuleResult
from nba.engine.config import fingerprint
from nba.kg.contacts import check_sources, contact_events, free_from, window
from nba.kg.rules import contact_cap_status

KINDS = {"channel_frequency", "offer_cooldown", "post_ticket_cooldown", "min_delta_clv", "channel_capacity", "condition"}
EFFECTS = {"BLOCK_CHANNEL", "BLOCK_OFFER", "BLOCK_ALL_SALES", "BLOCK_ALL_CONTACT", "DEFER_UNTIL",
           "DOWNGRADE_TO_NON_PERSONALISED", "REQUIRE_APPROVAL", "CANCEL_PENDING"}
OPS = {"=", "!=", ">=", "<=", "within_days"}
MARKETING_CHANNELS = ("newsletter_email", "email", "portal_popup", "app_push", "sms", "outbound_call")
RESPONSES = {"dismissed", "ignored", "viewed", "clicked"}
COUNTER_LABELS = {"B-01": "Email", "B-02": "Total", "B-03": "Call", "B-04": "SMS"}
OFFER_ENTITY = "product_catalog"  # conditions on the offer itself (target of a customized rule)


# ---------------------------------------------------------------- rules from config/nba.yaml


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    tier: str  # business | custom
    kind: str
    effect: str
    active: bool
    params: dict[str, Any]
    reason: str = ""
    hard: bool = False  # custom rules shown under "Hard rules"
    condition: dict[str, Any] | None = None
    children: tuple[Rule, ...] = ()

    def text(self, **values) -> str:
        try:
            return self.reason.format(**values) if self.reason else self.name
        except (KeyError, IndexError, ValueError):
            return self.name


def _positive_int(r: dict, key: str, where: str, problems: list[str]) -> None:
    v = r.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        problems.append(f"{where}: {key} must be a whole number ≥ 1 (got {v!r})")


def _check_condition(cond, where: str, problems: list[str]) -> None:
    if not isinstance(cond, dict) or not cond.get("entity") or not cond.get("column"):
        problems.append(f"{where}: a condition needs entity and column")
    elif cond.get("op") not in OPS:
        problems.append(f"{where}: operator {cond.get('op')!r} is not one of {sorted(OPS)}")
    elif cond["op"] == "within_days" and (isinstance(cond.get("value"), bool) or not isinstance(cond.get("value"), (int, float))):
        problems.append(f"{where}: within_days needs a number of days")


def _business(rid: str, r: dict, problems: list[str]) -> Rule:
    where = f"business_rules.{rid}"
    kind, effect = r.get("kind"), r.get("effect")
    if kind not in KINDS - {"condition"}:
        problems.append(f"{where}: unknown kind {kind!r}")
    if effect not in EFFECTS:
        problems.append(f"{where}: unknown effect {effect!r}")
    if kind == "channel_frequency":
        _positive_int(r, "max", where, problems)
        _positive_int(r, "window_days", where, problems)
        if not r.get("channels") or set(r["channels"]) - set(MARKETING_CHANNELS):
            problems.append(f"{where}: channels must be marketing channels {list(MARKETING_CHANNELS)}")
        try:
            check_sources(r.get("sources") or ())
        except ValueError as exc:
            problems.append(f"{where}: {exc}")
    elif kind == "offer_cooldown":
        _positive_int(r, "min_responses", where, problems)
        _positive_int(r, "cooldown_days", where, problems)
        if not r.get("responses") or set(r["responses"]) - RESPONSES:
            problems.append(f"{where}: responses must be from {sorted(RESPONSES)}")
    elif kind == "post_ticket_cooldown":
        _positive_int(r, "cooldown_days", where, problems)
    elif kind == "min_delta_clv":
        mins = r.get("min_eur") or {}
        if not mins or set(mins) - set(MARKETING_CHANNELS) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 for v in mins.values()):
            problems.append(f"{where}: min_eur maps marketing channels to amounts ≥ 0")
    elif kind == "channel_capacity":
        caps = r.get("per_week") or {}
        if not caps or set(caps) - set(MARKETING_CHANNELS) or any(
                isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in caps.values()):
            problems.append(f"{where}: per_week maps marketing channels to whole numbers ≥ 1")
    params = {k: v for k, v in r.items() if k not in {"name", "active", "kind", "effect", "reason"}}
    try:  # names may quote their numbers, e.g. "Max {max} e-mails in {window_days} days"
        name = (r.get("name") or rid).format(**{k: (v if not isinstance(v, dict) else next(iter(v.values()), ""))
                                                 for k, v in params.items()})
    except (KeyError, IndexError, ValueError):
        name = r.get("name") or rid
    return Rule(id=rid, name=name, tier="business", kind=kind or "", effect=effect or "",
                active=bool(r.get("active", True)), params=params, reason=r.get("reason", ""))


def _custom(r: dict, problems: list[str], where: str = "custom_rules") -> Rule:
    rid = str(r.get("id") or "")
    where = f"{where}.{rid or '?'}"
    if not rid:
        problems.append(f"{where}: needs an id")
    _check_condition(r.get("condition"), where, problems)
    effect = r.get("effect") or "auto"
    if effect != "auto" and effect not in EFFECTS:
        problems.append(f"{where}: unknown effect {effect!r}")
    children = tuple(_custom(c, problems, where) for c in r.get("children") or [])
    params = {k: v for k, v in r.items() if k not in {"id", "name", "active", "effect", "hard", "condition", "children"}}
    return Rule(id=rid, name=r.get("name") or rid, tier="custom", kind="condition", effect=effect,
                active=bool(r.get("active", True)), params=params, hard=bool(r.get("hard")),
                condition=r.get("condition"), children=children)


def load_rules(settings: dict) -> list[Rule]:
    """Business rules (B-xx) and custom rules (U-xx) from config/nba.yaml; raises ValueError on a bad rule."""
    problems: list[str] = []
    rules = [_business(rid, r, problems) for rid, r in (settings.get("business_rules") or {}).items()]
    rules += [_custom(r, problems) for r in settings.get("custom_rules") or []]
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        problems.append("rule IDs must be unique")
    if problems:
        raise ValueError("config/nba.yaml has invalid rule(s):\n- " + "\n- ".join(problems))
    return rules


def rule_set_version(settings: dict, policy) -> str:
    """Version label + fingerprint of every rule that can change a decision (tier 1, B-02 and tier 2)."""
    payload = [settings.get("business_rules"), settings.get("custom_rules"),
               policy.config.get("contact_cap"), policy.compliance]
    return f"{settings.get('rule_set_version', 'rs-1')}:{fingerprint(payload)}"


# ---------------------------------------------------------------- conditions (custom rules)


def _same(actual, value) -> bool:
    if isinstance(value, bool) or isinstance(actual, bool):
        truthy = {"1", "true", "yes"}
        return (str(actual).strip().lower() in truthy) == (str(value).strip().lower() in truthy)
    if isinstance(value, (int, float)) and not isinstance(actual, (str, type(None))):
        return float(actual) == float(value)
    return str(actual) == str(value)


def _number(v) -> float | None:
    try:
        return float(v) if v is not None and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        return None


def value_matches(actual, op: str, value, at: datetime) -> bool:
    if actual is None:
        return op == "!="
    if op == "=":
        return _same(actual, value)
    if op == "!=":
        return not _same(actual, value)
    if op == "within_days":
        return isinstance(actual, datetime) and abs((actual - at).total_seconds()) <= float(value) * 86400
    a, b = _number(actual), _number(value)
    if a is None or b is None:
        return False
    return a >= b if op == ">=" else a <= b


def customer_matches(cond: dict, state, at: datetime) -> bool:
    """Does any row of this customer's `entity` sheet satisfy the condition?"""
    rows = state.rows.get(cond["entity"]) or []
    value = cond.get("value")
    if cond["entity"] == "consent_status" and isinstance(value, str) and ":" in value:  # "<type>:<status>"
        ctype, status = value.split(":", 1)
        hit = any(r.get("consent_type") == ctype and r.get(cond["column"]) == status for r in rows)
        return hit if cond["op"] == "=" else not hit
    return any(value_matches(r.get(cond["column"]), cond["op"], value, at) for r in rows)


def offer_matches(cond: dict, offer: dict) -> bool:
    return value_matches(offer.get(cond["column"]), cond["op"], cond.get("value"), datetime.min)


def _conditions(rule: Rule) -> list[dict]:
    """The rule's condition and those of its active sub-rules: all must hold (sub-rules narrow the parent)."""
    out = [rule.condition] if rule.condition else []
    for child in rule.children:
        if child.active:
            out += _conditions(child)
    return out


def custom_effect(rule: Rule) -> str:
    if rule.effect != "auto":
        return rule.effect
    return "BLOCK_OFFER" if any(c["entity"] == OFFER_ENTITY for c in _conditions(rule)) else "BLOCK_ALL_SALES"


# ---------------------------------------------------------------- per-customer evaluation


@dataclass
class Hit:
    result: str  # block | defer
    detail: str
    until: datetime | None = None
    measured: dict[str, Any] = field(default_factory=dict)
    tuples: int = 0


class Evaluator:
    """Tier 2 for one customer. `capacity` = channel -> time the overflow must wait for (B-09, set by Runtime)."""

    def __init__(self, state, policy, cfg, rules: list[Rule] | None = None, capacity: dict[str, datetime] | None = None):
        self.state, self.policy, self.cfg = state, policy, cfg
        self.rules = rules if rules is not None else cfg.rules
        self.capacity = capacity or {}
        self.at = state.eval_time
        self.cap = contact_cap_status(state, policy)
        self.hits: dict[str, Hit] = {}
        self._events: dict[tuple[str, ...], list] = {}
        self._frequency: dict[str, tuple[int, datetime | None]] = {}
        self._custom = {r.id: self._custom_applies(r) for r in self.rules if r.kind == "condition" and r.active}

    # -- facts

    def events(self, sources) -> list:
        key = tuple(sorted(sources))
        if key not in self._events:
            self._events[key] = contact_events(self.state, key)
        return self._events[key]

    def frequency(self, rule: Rule) -> tuple[int, datetime | None]:
        if rule.id not in self._frequency:
            p = rule.params
            events = self.events(p["sources"])
            n = len(window(events, p["window_days"], self.at, p["channels"]))
            self._frequency[rule.id] = n, free_from(events, p["window_days"], p["max"], self.at, p["channels"])
        return self._frequency[rule.id]

    def offer_cooldown(self, rule: Rule, offer_id: str) -> tuple[int, datetime | None, datetime | None]:
        p = rule.params
        times = sorted(t for r in self.state.rows["nba_action_history"]
                       if r.get("offer_id") == offer_id and r.get("response") in p["responses"]
                       for t in [r.get("response_at") or r.get("decided_at")] if t is not None and t <= self.at)
        if len(times) < p["min_responses"]:
            return len(times), None, None
        until = times[-1] + timedelta(days=p["cooldown_days"])
        return len(times), times[-1], until if until > self.at else None

    def last_ticket(self, rule: Rule):
        resolved = [r for r in self.state.rows["service_interactions"]
                    if r.get("resolved_at") is not None and r["resolved_at"] <= self.at]
        if not resolved:
            return None, None
        t = max(resolved, key=lambda r: r["resolved_at"])
        until = t["resolved_at"] + timedelta(days=rule.params["cooldown_days"])
        return t, until if until > self.at else None

    def _custom_applies(self, rule: Rule) -> bool:
        return all(customer_matches(c, self.state, self.at) for c in _conditions(rule) if c["entity"] != OFFER_ENTITY)

    # -- one tuple

    def verdict(self, c: Candidate) -> tuple[list[tuple[str, str]], list[tuple[str, datetime, str]]]:
        """(blocks, defers) for a marketing tuple; each item names the Rule Center rule."""
        blocks: list[tuple[str, str]] = []
        defers: list[tuple[str, datetime, str]] = []
        if any(k.rule_id == "CONTACT-CAP" and not k.passed for k in c.checks) and self.cap.free_at:
            defers.append(("B-02", self.cap.free_at, f"{self.cap.count}/{self.cap.limit} contacts in {self.cap.days} days"))
        for rule in self.rules:
            if not rule.active:
                continue
            p = rule.params
            if rule.kind == "channel_frequency" and c.channel in p["channels"]:
                n, until = self.frequency(rule)
                if until:
                    defers.append((rule.id, until, rule.text(count=n, **p)))
            elif rule.kind == "offer_cooldown":
                n, last, until = self.offer_cooldown(rule, c.offer_id)
                if until:
                    defers.append((rule.id, until, rule.text(count=n, last=f"{last:%Y-%m-%d}", **p)))
            elif rule.kind == "post_ticket_cooldown":
                ticket, until = self.last_ticket(rule)
                if until:
                    defers.append((rule.id, until, rule.text(ticket=ticket["ticket_id"], resolved=f"{ticket['resolved_at']:%Y-%m-%d}", **p)))
            elif rule.kind == "min_delta_clv" and c.channel in p["min_eur"] and c.valuation is not None:
                floor = float(p["min_eur"][c.channel])
                if c.valuation.delta_clv < floor:
                    blocks.append((rule.id, rule.text(channel=c.channel, min=f"{floor:g}", value=f"{c.valuation.delta_clv:.2f}")))
            elif rule.kind == "channel_capacity" and c.channel in self.capacity and c.channel in p["per_week"]:
                defers.append((rule.id, self.capacity[c.channel],
                               rule.text(channel=c.channel, limit=p["per_week"][c.channel], position="after the limit")))
            elif rule.kind == "condition" and self._custom.get(rule.id):
                self._custom_verdict(rule, c, blocks, defers)
        return blocks, defers

    def _custom_verdict(self, rule: Rule, c: Candidate, blocks, defers) -> None:
        offer = self.cfg.offers.get(c.offer_id, {})
        if not all(offer_matches(cond, offer) for cond in _conditions(rule) if cond["entity"] == OFFER_ENTITY):
            return
        effect, p = custom_effect(rule), rule.params
        why = f"{rule.name} ({rule.id})"
        if effect in {"BLOCK_OFFER", "BLOCK_ALL_SALES", "BLOCK_ALL_CONTACT"}:
            blocks.append((rule.id, why))
        elif effect == "BLOCK_CHANNEL" and c.channel in (p.get("channels") or MARKETING_CHANNELS):
            blocks.append((rule.id, why))
        elif effect == "DOWNGRADE_TO_NON_PERSONALISED" and c.personalised:
            blocks.append((rule.id, f"{why}: only non-personalised offers"))
        elif effect == "DEFER_UNTIL":
            defers.append((rule.id, self.at + timedelta(days=float(p.get("days", 7))), why))

    def record(self, rule_id: str, result: str, detail: str, until: datetime | None = None) -> None:
        hit = self.hits.get(rule_id)
        if hit is None:
            self.hits[rule_id] = Hit(result, detail, until, tuples=1)
            return
        hit.tuples += 1
        if until and (hit.until is None or until > hit.until):
            hit.until = until


def apply_rules(candidates: list[Candidate], ev: Evaluator) -> tuple[list[Candidate], list[Candidate], list[Blocked]]:
    """Split valued tuples into (allowed now, deferred, blocked rows). Service tuples always pass; tuples with
    ΔCLV ≤ 0 pass through too, because the economics row (ECON-NONPOSITIVE) already drops them."""
    allowed, deferred, blocked = [], [], []
    for c in candidates:
        if c.action_type == "service" or (c.valuation is not None and c.valuation.delta_clv <= 0):
            allowed.append(c)
            continue
        blocks, defers = ev.verdict(c)
        if blocks:
            for rid, reason in blocks:
                ev.record(rid, "block", reason)
                blocked.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="BUSINESS-RULE", rule_center_id=rid,
                                       reason=f"{c.tuple_id}: {reason}", src="config/nba.yaml business_rules",
                                       counterfactual_delta_clv=c.valuation.delta_clv if c.valuation else None))
            continue
        if defers:
            until = max(u for _, u, _ in defers)
            for rid, u, reason in defers:
                ev.record(rid, "defer", reason, u)
            ids = ", ".join(sorted({rid for rid, _, _ in defers}))
            deferred.append(c.model_copy(update={
                "deferred_until": until.isoformat(),
                "notes": c.notes + [f"Held back until {until:%Y-%m-%d %H:%M} ({ids}): "
                                    + "; ".join(reason for _, _, reason in defers)]}))
        else:
            allowed.append(c)
    return allowed, deferred, blocked


def deferred_rows(deferred: list[Candidate]) -> list[Blocked]:
    """Blocked-section rows for deferred tuples that were not chosen (they wait, they are not dropped)."""
    out = []
    for c in deferred:
        note = next((n for n in reversed(c.notes) if n.startswith("Held back until")), "held back")
        rid = note.split("(", 1)[1].split(")", 1)[0].split(",")[0] if "(" in note else None
        out.append(Blocked(offer_id=c.offer_id, channel=c.channel, rule_id="CONTACT-CAP" if rid == "B-02" else "BUSINESS-RULE",
                           rule_center_id=rid, reason=f"{c.tuple_id}: {note}", until=c.deferred_until,
                           counterfactual_delta_clv=c.valuation.delta_clv if c.valuation else None))
    return out


# ---------------------------------------------------------------- the rule report on the card


def report(ev: Evaluator, kg_blocked: list[Blocked], chosen_tuple: str, version: str) -> RuleReport:
    results: list[RuleResult] = []
    by_rc = defaultdict(list)
    for b in kg_blocked:
        if b.rule_center_id:
            by_rc[b.rule_center_id].append(b)
    for cid, c in sorted(ev.policy.compliance.items()):
        rows = by_rc.get(cid, [])
        if c.get("kg_rules"):
            channels = sorted({b.channel for b in rows if b.channel})
            results.append(RuleResult(rule_id=cid, tier="compliance", name=c["label"], result="block" if rows else "pass",
                                      detail=rows[0].reason if rows else None, tuples=len(rows),
                                      measured={"channels": channels} if channels else {}))
        else:
            results.append(RuleResult(rule_id=cid, tier="compliance", name=c["label"],
                                      result="n/a" if cid == "C-04" else "pass", detail=c.get("enforced_by")))
    cap = ev.cap
    hit = ev.hits.get("B-02")
    results.append(RuleResult(rule_id="B-02", tier="business", name=f"Max {cap.limit} contacts in {cap.days} days",
                              result="defer" if cap.hit else "pass", until=cap.free_at.isoformat() if cap.free_at else None,
                              measured={"count": cap.count, "limit": cap.limit, "window_days": cap.days},
                              detail=f"{cap.count}/{cap.limit} contacts in {cap.days} days", tuples=hit.tuples if hit else 0))
    owned = by_rc.get("B-07", [])
    results.append(RuleResult(rule_id="B-07", tier="business", name="Never offer what they own",
                              result="block" if owned else "pass", tuples=len(owned),
                              detail=owned[0].reason if owned else None))
    counters = [ContactCounter(rule_id="B-02", label="Total", count=cap.count, limit=cap.limit, window_days=cap.days)]
    for rule in ev.rules:
        hit = ev.hits.get(rule.id)
        measured: dict[str, Any] = {}
        result, detail, until = "pass", None, None
        if rule.kind == "channel_frequency":
            n, free = ev.frequency(rule)
            measured = {"count": n, "limit": rule.params["max"], "window_days": rule.params["window_days"]}
            counters.append(ContactCounter(rule_id=rule.id, label=COUNTER_LABELS.get(rule.id, rule.name), count=n,
                                           limit=rule.params["max"], window_days=rule.params["window_days"]))
            if free:
                result, detail, until = "defer", rule.text(count=n, **rule.params), free
        if not rule.active:
            result, detail, until = "off", None, None
        elif hit:
            result, detail, until = hit.result, hit.detail, hit.until or until
        results.append(RuleResult(rule_id=rule.id, tier=rule.tier, name=rule.name, result=result, detail=detail,
                                  until=until.isoformat() if until else None, measured=measured,
                                  tuples=hit.tuples if hit and rule.active else 0))
    counters.sort(key=lambda k: ["B-01", "B-02", "B-03", "B-04"].index(k.rule_id) if k.rule_id in COUNTER_LABELS else 9)
    line = " · ".join(f"{k.label} {k.count}/{k.limit} ({k.window_days} d)" for k in counters)
    return RuleReport(rule_set_version=version, results=results, counters=counters, counter_line=line)


# ---------------------------------------------------------------- B-09: channel capacity across customers


def capacity_limits(rules: list[Rule]) -> dict[str, int]:
    out: dict[str, int] = {}
    for rule in rules:
        if rule.active and rule.kind == "channel_capacity":
            for ch, n in rule.params["per_week"].items():
                out[ch] = min(n, out.get(ch, n))
    return out


def _send_time(card) -> datetime:
    for v in (card.chosen.deferred_until, card.chosen.send_at):
        try:
            return datetime.fromisoformat(v)
        except (TypeError, ValueError):
            continue
    return datetime.fromisoformat(card.meta.eval_time)


def plan_capacity(cards, limits: dict[str, int]) -> dict[str, dict[str, datetime]]:
    """Customers whose chosen action overflows a channel's weekly capacity -> {channel: wait until}.

    Within a week the highest ΔCLV keeps the slot (ties by customer ID); the rest wait for next Monday 00:00
    or, when another channel is allowed, switch to it (the engine re-decides them with that wait)."""
    weekly: dict[tuple[str, int, int], list[tuple[float, str, datetime]]] = defaultdict(list)
    for card in cards:
        if card.chosen.tuple_id == NO_ACTION:
            continue
        channel = card.chosen.tuple_id.split("|")[1]
        if channel not in limits:
            continue
        chosen = next(c for c in card.candidates if c.tuple_id == card.chosen.tuple_id)
        when = _send_time(card)
        year, week, _ = when.isocalendar()
        weekly[(channel, year, week)].append((chosen.valuation.delta_clv, card.customer_id, when))
    overflow: dict[str, dict[str, datetime]] = defaultdict(dict)
    for (channel, _, _), rows in weekly.items():
        rows.sort(key=lambda r: (-r[0], r[1]))
        for _, cid, when in rows[limits[channel]:]:
            monday = (when - timedelta(days=when.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            overflow[cid][channel] = monday + timedelta(days=7)
    return dict(overflow)
