"""Gates and candidate generation (README §6.1–§6.4, §6.12). Owner: Agent KG.

`generate_candidates` returns only tuples that passed every hard rule; Agent NBA values and
ranks them. `check_tuple` answers "which hard rules block this exact tuple?" for overrides
and the legacy comparison. The consent/channel/exclusion views are shared with Agent CARDS so
the profile card never re-implements a rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from nba.contracts import (
    Blocked, Candidate, ChannelItem, Check, ConsentItem, ExclusionItem, Signal, tuple_id,
)
from nba.kg import predicates as P
from nba.kg.paths import explain
from nba.kg.policy import OfferDef, Policy
from nba.state import CustomerState, contacts

CONSENT_ORDER = ["newsletter_email", "marketing_email", "marketing_phone", "marketing_sms",
                 "portal_app_personalisation", "profiling_analytics"]
SERVICE_OFFER = "P-SV-01"


def _d(dt) -> str | None:
    return dt.date().isoformat() if dt else None


# ---------------------------------------------------------------- consent and channels (§6.1)


def consents(state: CustomerState, policy: Policy) -> dict[str, ConsentItem]:
    """Consent per type with the effective status after unsubscribe overrides (spec A4)."""
    rows = {r["consent_type"]: r for r in state.rows["consent_status"]}
    unsub = [r for r in state.rows["newsletter_performance"] if r.get("unsubscribed")]
    withdraws = set(policy.config.get("consent", {}).get("unsubscribe_withdraws", ["newsletter_email"]))
    out: dict[str, ConsentItem] = {}
    for ctype in CONSENT_ORDER:
        r = rows.get(ctype) or {}
        status = r.get("status") or "not_given"
        effective, override = status, None
        if status not in ("granted", "not_given", "withdrawn"):  # README §6.1: unknown counts as not allowed
            override = f"unknown status '{status}' treated as not allowed"
            status = effective = "not_given"
        if ctype in withdraws and unsub and status == "granted":
            effective = "withdrawn"
            override = f"unsubscribed via newsletter {unsub[0]['campaign_id']} (newsletter_performance.unsubscribed)"
        out[ctype] = ConsentItem(
            type=ctype, status=status, effective_status=effective,
            doi=bool(r.get("double_opt_in_confirmed_at")) if ctype == "newsletter_email" else None,
            updated_at=_d(r.get("updated_at")), source=r.get("source"), override_reason=override,
        )
    return out


def consent_view(state: CustomerState, policy: Policy) -> list[ConsentItem]:
    return list(consents(state, policy).values())


def is_profiled(state: CustomerState, policy: Policy) -> bool:
    return consents(state, policy)["profiling_analytics"].effective_status == "granted"


@dataclass(frozen=True)
class _Chan:
    channel: str
    allowed: bool
    rule: str  # CONSENT-CHANNEL or CHANNEL-AVAILABLE when blocked
    reason: str
    consent: str
    src: str


def _channels(state: CustomerState, policy: Policy, cons: dict[str, ConsentItem]) -> dict[str, _Chan]:
    master = state.one("customer_master") or {}
    raw = {r["consent_type"]: r for r in state.rows["consent_status"]}
    out: dict[str, _Chan] = {}
    for c in policy.channels.values():
        ci = cons[c.consent]
        src = "consent_status.status"
        if ci.effective_status != "granted":
            when = f" on {ci.updated_at}" if ci.updated_at else ""
            why = ci.override_reason or f"{c.consent} {ci.effective_status}{when}"
            out[c.id] = _Chan(c.id, False, "CONSENT-CHANNEL", why, c.consent, src)
        elif c.needs_doi and not ci.doi:
            out[c.id] = _Chan(c.id, False, "CONSENT-CHANNEL", f"{c.consent} granted without double opt-in", c.consent,
                              "consent_status.double_opt_in_confirmed_at")
        elif c.requires_field and not master.get(c.requires_field):
            out[c.id] = _Chan(c.id, False, "CHANNEL-AVAILABLE", f"no {c.requires_field.replace('_', ' ')}", c.consent,
                              f"customer_master.{c.requires_field}")
        else:
            doi = _d((raw.get(c.consent) or {}).get("double_opt_in_confirmed_at")) if c.needs_doi else None
            extra = f", double opt-in {doi}" if doi else ""
            out[c.id] = _Chan(c.id, True, "", f"{c.consent} granted {ci.updated_at or ''}{extra}".strip(), c.consent, src)
    return out


def channel_view(state: CustomerState, policy: Policy) -> list[ChannelItem]:
    cons = consents(state, policy)
    items = [ChannelItem(channel=ch.channel, allowed=ch.allowed, requires=[ch.consent], reason=ch.reason)
             for ch in _channels(state, policy, cons).values()]
    items.append(ChannelItem(channel=policy.service_channel, allowed=True, requires=[],
                             reason="service contact; no marketing consent needed; never carries sales content"))
    return items


# ---------------------------------------------------------------- exclusions (§6.2)


def active_exclusions(state: CustomerState, policy: Policy) -> list[tuple[str, P.Hit]]:
    """Every active exclusion, whatever its blocking scope (README §6.2, K6)."""
    out = []
    for e in policy.exclusions.values():
        hit = P.EXCLUSIONS[e.predicate](state)
        if hit:
            out.append((e.id, hit))
    return out


def blocks_offer(rule_id: str, offer: OfferDef, policy: Policy) -> bool:
    """Does an active exclusion block this offer? Service is never blocked. K6 scopes Autostrom-cancelled."""
    if offer.action_type not in policy.exclusions[rule_id].blocks:
        return False
    if rule_id == "EXCL-AUTOSTROM-CANCELLED":
        scope = policy.config.get("exclusions", {}).get("autostrom_cancelled_scope", "all_sales")
        return scope == "all_sales" or offer.business_line == "e_mobility"
    return True


def _scope_text(rule_id: str, policy: Policy) -> str:
    if rule_id == "EXCL-AUTOSTROM-CANCELLED" and \
            policy.config.get("exclusions", {}).get("autostrom_cancelled_scope", "all_sales") != "all_sales":
        return "E-mobility offers blocked"
    return "All sales, upsell, retention and one-off offers blocked"


def exclusion_view(state: CustomerState, policy: Policy) -> list[ExclusionItem]:
    active = dict(active_exclusions(state, policy))
    return [ExclusionItem(rule_id=e.id, active=e.id in active, detail=active[e.id].detail if e.id in active else None,
                          src=active[e.id].src if e.id in active else policy_src(e.id))
            for e in policy.exclusions.values()]


def policy_src(rule_id: str) -> str:
    return {
        "EXCL-DUNNING": "energy_contracts.dunning_level",
        "EXCL-CANCELLATION": "energy_contracts.status",
        "EXCL-OPEN-TICKET": "service_interactions.status",
        "EXCL-AUTOSTROM-CANCELLED": "autostrom_contracts.status",
    }[rule_id]


# ---------------------------------------------------------------- holdings (§6.4)


def _holding_check(state: CustomerState, policy: Policy, offer_id: str, generic: bool) -> tuple[bool, str]:
    """REQUIRES / NOT-HELD. Generic offers only drop products the customer already owns (D1)."""
    o = policy.offers[offer_id]
    facts = []
    if not generic:
        for name in o.requires:
            ok, detail = P.HOLDINGS[name](state)
            if not ok:
                return False, f"needs {detail.removeprefix('no ')}" if detail.startswith("no ") else detail
            facts.append(detail)
    for name in o.not_held:
        held, detail = P.HOLDINGS[name](state)
        if held:
            return False, detail
        facts.append(detail)
    return True, "; ".join(facts) or "no holding requirement"


def _exclusion_checks(excl: list[tuple[str, P.Hit]], offer: OfferDef, policy: Policy) -> list[Check]:
    active = dict(excl)
    out = []
    for rule_id in policy.exclusions:
        if rule_id not in active:
            out.append(Check(rule_id=rule_id, passed=True, detail="not active", src=policy_src(rule_id)))
        else:
            # Active but scoped away from this offer (K6); a blocking rule never reaches a candidate.
            out.append(Check(rule_id=rule_id, passed=True, detail=f"active ({active[rule_id].detail}) but does not block this offer",
                             src=active[rule_id].src))
    return out


# ---------------------------------------------------------------- candidates (§6.12)


def generate_candidates(
    state: CustomerState, signals: list[Signal], policy: Policy, tone: str = "sie"
) -> tuple[list[Candidate], list[Blocked]]:
    cons = consents(state, policy)
    profiled = cons["profiling_analytics"].effective_status == "granted"
    tone_used = tone if profiled else "sie"
    chans = _channels(state, policy, cons)
    marketing_channels = list(policy.channels)
    allowed_channels = [ch for ch in marketing_channels if chans[ch].allowed]
    excl = active_exclusions(state, policy)
    cap_max, window = policy.contact_cap
    n_contacts = len(contacts(state, window))
    cap_hit = n_contacts >= cap_max
    blocked: list[Blocked] = []
    cands: dict[str, Candidate] = {}

    def blocking_rule(offer: OfferDef) -> tuple[str, P.Hit] | None:
        return next(((r, h) for r, h in excl if blocks_offer(r, offer, policy)), None)

    # customer-wide rows: data gaps, exclusions, contact cap, blocked channels
    for o in policy.offers.values():
        if o.data_missing:
            blocked.append(Blocked(offer_id=o.id, rule_id="DATA-MISSING", reason=f"{o.name}: not enough data ({o.data_missing})"))
    for rule_id, hit in excl:
        blocked.append(Blocked(offer_id="*", rule_id=rule_id, src=hit.src, reason=f"{_scope_text(rule_id, policy)}: {hit.detail}"))
    if cap_hit:
        blocked.append(Blocked(offer_id="*", rule_id="CONTACT-CAP", src="nba_action_history.decided_at",
                               reason=f"{n_contacts} marketing contacts in the last {window} days (cap {cap_max}); marketing paused"))
    for ch in marketing_channels:
        if not chans[ch].allowed:
            blocked.append(Blocked(offer_id="*", channel=ch, rule_id=chans[ch].rule, src=chans[ch].src,
                                   reason=f"{ch.replace('_', ' ')} not allowed for any offer: {chans[ch].reason}"))
    if not allowed_channels:
        blocked.append(Blocked(offer_id="*", rule_id="CONSENT-CHANNEL", src="consent_status.status",
                               reason="No consented marketing channel: only service contact is possible"))

    cap_check = Check(rule_id="CONTACT-CAP", passed=True, detail=f"{n_contacts}/{cap_max} marketing contacts in {window} days",
                      src="nba_action_history.decided_at")
    prof = cons["profiling_analytics"]

    # 1. service tuples (S2, S12, S13 -> P-SV-01); never blocked by exclusions, consent or the cap
    service_sigs = [s for s in signals if policy.signals[s.id].purpose == "service"]
    if service_sigs:
        o = policy.offers[SERVICE_OFFER]
        c = Candidate(
            tuple_id=tuple_id(o.id, policy.service_channel, tone_used), offer_id=o.id, offer_name=o.name,
            action_type=o.action_type, channel=policy.service_channel, tone=tone_used, origin="service",
            personalised=False, need="N-SERVICE-FIX", signals=[s.id for s in service_sigs],
            checks=[Check(rule_id="CONSENT-CHANNEL", passed=True, detail="service contact; no marketing consent needed"),
                    Check(rule_id="CONTACT-CAP", passed=True, detail="service is exempt from the contact cap")],
            why=[f"{s.detail} [{s.id}]" for s in service_sigs],
            notes=["Service only: apology and resolution, no sales content"],
        )
        cands[c.tuple_id] = c

    # 2. signal tuples (personalised) — only with profiling consent (D1)
    reinforcing = [s for s in signals if policy.signals[s.id].reinforces]
    marketing_sigs = [s for s in signals if policy.signals[s.id].purpose != "service" and not policy.signals[s.id].reinforces]
    signal_offers: set[str] = set()
    signal_blocked: set[str] = set()
    if not profiled:
        for s in marketing_sigs + reinforcing:
            offers = s.offers or sorted({o for n in s.needs for o in policy.offers_for_need(n)})
            for oid in offers:
                blocked.append(Blocked(offer_id=oid, rule_id="CONSENT-PROFILING", src="consent_status.status",
                                       reason=f"{s.id} ignored ({s.detail}): no profiling consent, so no personalisation"))
    else:
        by_offer: dict[str, list[Signal]] = {}
        for s in marketing_sigs:
            for oid in s.offers:
                by_offer.setdefault(oid, []).append(s)
        for oid, sigs in sorted(by_offer.items()):
            o = policy.offers[oid]
            sig_ids = ", ".join(s.id for s in sigs)
            hit = blocking_rule(o)
            if hit:
                r, h = hit
                blocked.append(Blocked(offer_id=oid, rule_id=r, src=h.src, reason=f"{o.name} (from {sig_ids}) blocked: {h.detail}"))
                signal_blocked.add(oid)
                continue
            ok, holding = _holding_check(state, policy, oid, generic=False)
            if not ok:
                blocked.append(Blocked(offer_id=oid, rule_id="HOLDING-PRECONDITION", reason=f"{o.name} (from {sig_ids}): {holding}"))
                signal_blocked.add(oid)
                continue
            if cap_hit or not allowed_channels:
                continue  # the customer-wide rows explain it
            need = next(n for s in sigs for n in s.needs if n in o.addresses)
            extra = [r for r in reinforcing if set(r.needs) & set(o.addresses)]
            why = [f"{s.detail} [{s.id}]" for s in sigs] + [f"also {r.detail} [{r.id}]" for r in extra]
            for ch in allowed_channels:
                c = Candidate(
                    tuple_id=tuple_id(oid, ch, tone_used), offer_id=oid, offer_name=o.name, action_type=o.action_type,
                    channel=ch, tone=tone_used, origin="signal", personalised=True, need=need,
                    signals=[s.id for s in sigs] + [r.id for r in extra],
                    checks=_exclusion_checks(excl, o, policy) + [
                        Check(rule_id="HOLDING-PRECONDITION", passed=True, detail=holding),
                        Check(rule_id="CONSENT-PROFILING", passed=True, detail=f"profiling_analytics granted {prof.updated_at or ''}".strip(), src="consent_status.status"),
                        Check(rule_id="CONSENT-CHANNEL", passed=True, detail=chans[ch].reason, src=chans[ch].src),
                        cap_check,
                    ],
                    why=why,
                )
                cands[c.tuple_id] = c
                signal_offers.add(oid)

    # 3. generic tuples (non-personalised catalog offers, catalog-average p) — §6.12
    gen_allowed = policy.config.get("generic", {}).get("allowed_channels", "all")
    gen_channels = [ch for ch in allowed_channels if gen_allowed == "all" or ch in gen_allowed]
    for o in policy.generic_offers:
        if o.id in signal_offers or o.id in signal_blocked or blocking_rule(o) or cap_hit:
            continue  # exclusion / cap rows above explain it
        ok, holding = _holding_check(state, policy, o.id, generic=True)
        if not ok:
            blocked.append(Blocked(offer_id=o.id, rule_id="HOLDING-PRECONDITION", reason=f"{o.name} not offered: {holding}"))
            continue
        for ch in gen_channels:
            c = Candidate(
                tuple_id=tuple_id(o.id, ch, tone_used), offer_id=o.id, offer_name=o.name, action_type=o.action_type,
                channel=ch, tone=tone_used, origin="generic", personalised=False, need=None, signals=[],
                checks=_exclusion_checks(excl, o, policy) + [
                    Check(rule_id="HOLDING-PRECONDITION", passed=True, detail=f"not owned: {holding}"),
                    Check(rule_id="CONSENT-PROFILING", passed=True, detail="not needed: generic, non-personalised offer"),
                    Check(rule_id="CONSENT-CHANNEL", passed=True, detail=chans[ch].reason, src=chans[ch].src),
                    cap_check,
                ],
                why=[f"Generic catalog offer, the same for every customer; only owned products are removed ({holding})"],
                notes=["Not personalised: valued with the catalog-average acceptance rate"],
            )
            cands[c.tuple_id] = c

    out = []
    for c in sorted(cands.values(), key=lambda x: ({"service": 0, "signal": 1, "generic": 2}[x.origin], x.offer_id, x.channel)):
        out.append(c.model_copy(update={"path": explain(state, c, policy, signals)}))
    return out, blocked


# ---------------------------------------------------------------- single-tuple check (overrides, legacy)


def check_tuple(state: CustomerState, offer_id: str, channel: str, policy: Policy) -> list[Blocked]:
    """Hard rules that block exactly this (offer, channel) for this customer; [] means allowed.

    For the override 409 (README §6.10) and legacy_comparison.blocked_now_by (§7.3). It checks
    hard rules only; whether a signal recommends the offer is a ranking question, not a rule.
    """
    if offer_id not in policy.offers:
        return [Blocked(offer_id=offer_id, channel=None, rule_id="DATA-MISSING", reason=f"unknown offer {offer_id}")]
    o = policy.offers[offer_id]
    out: list[Blocked] = []
    if o.data_missing:
        out.append(Blocked(offer_id=o.id, rule_id="DATA-MISSING", reason=f"{o.name}: not enough data ({o.data_missing})"))
    if o.action_type == "service":
        if channel != policy.service_channel:
            out.append(Blocked(offer_id=o.id, channel=None, rule_id="CONSENT-CHANNEL",
                               reason=f"service is delivered by the {policy.service_channel.replace('_', ' ')} only"))
        return out
    for rule_id, hit in active_exclusions(state, policy):
        if blocks_offer(rule_id, o, policy):
            out.append(Blocked(offer_id=o.id, rule_id=rule_id, src=hit.src, reason=f"{o.name} blocked: {hit.detail}"))
    cons = consents(state, policy)
    profiled = cons["profiling_analytics"].effective_status == "granted"
    generic_ids = {g.id for g in policy.generic_offers}
    if not profiled and o.id not in generic_ids:
        out.append(Blocked(offer_id=o.id, rule_id="CONSENT-PROFILING", src="consent_status.status",
                           reason=f"{o.name} is a personalised offer and the customer has no profiling consent"))
    ok, holding = _holding_check(state, policy, o.id, generic=not profiled and o.id in generic_ids)
    if not ok:
        out.append(Blocked(offer_id=o.id, rule_id="HOLDING-PRECONDITION", reason=f"{o.name}: {holding}"))
    if channel not in policy.channels:
        out.append(Blocked(offer_id=o.id, channel=None, rule_id="CONSENT-CHANNEL", reason=f"{channel} is not a marketing channel"))
    else:
        ch = _channels(state, policy, cons)[channel]
        if not ch.allowed:
            out.append(Blocked(offer_id=o.id, channel=channel, rule_id=ch.rule, src=ch.src, reason=ch.reason))
    cap_max, window = policy.contact_cap
    n = len(contacts(state, window))
    if n >= cap_max:
        out.append(Blocked(offer_id=o.id, rule_id="CONTACT-CAP", src="nba_action_history.decided_at",
                           reason=f"{n} marketing contacts in the last {window} days (cap {cap_max})"))
    return out
