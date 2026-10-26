"""Gates and candidate generation (README §6.1–§6.4, §6.12). Owner: Agent KG.

`generate_candidates` returns only tuples that passed every hard rule; Agent NBA values and
ranks them. The consent/channel/exclusion views are shared with Agent CARDS so the profile card
never re-implements a rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from nba.contracts import (
    Blocked, Candidate, ChannelItem, Check, ConsentItem, ExclusionItem, Signal, tuple_id,
)
from nba.kg import predicates as P
from nba.kg.paths import explain
from nba.kg.policy import Policy
from nba.state import CustomerState, contacts

MARKETING_TYPES = {"sales", "upsell", "retention", "one_off"}
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


def _channels(state: CustomerState, policy: Policy, cons: dict[str, ConsentItem]) -> dict[str, _Chan]:
    master = state.one("customer_master") or {}
    out: dict[str, _Chan] = {}
    for c in policy.channels.values():
        ci = cons[c.consent]
        if ci.effective_status != "granted":
            when = f" on {ci.updated_at}" if ci.updated_at else ""
            why = ci.override_reason or f"{c.consent} {ci.effective_status}{when}"
            out[c.id] = _Chan(c.id, False, "CONSENT-CHANNEL", why, c.consent)
        elif c.needs_doi and not ci.doi:
            out[c.id] = _Chan(c.id, False, "CONSENT-CHANNEL", f"{c.consent} granted without double opt-in", c.consent)
        elif c.requires_field and not master.get(c.requires_field):
            out[c.id] = _Chan(c.id, False, "CHANNEL-AVAILABLE", f"no {c.requires_field.replace('_', ' ')}", c.consent)
        else:
            extra = f", DOI {ci.updated_at}" if c.needs_doi else ""
            out[c.id] = _Chan(c.id, True, "", f"{c.consent} granted {ci.updated_at or ''}{extra}".strip(), c.consent)
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
    scope = policy.config.get("exclusions", {}).get("autostrom_cancelled_scope", "all_sales")
    out = []
    for e in policy.exclusions.values():
        if e.id == "EXCL-AUTOSTROM-CANCELLED" and scope != "all_sales":
            continue  # e_mobility scope is applied per offer in _blocking_exclusion
        hit = P.EXCLUSIONS[e.predicate](state)
        if hit:
            out.append((e.id, hit))
    return out


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


# ---------------------------------------------------------------- candidates (§6.12)


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


def generate_candidates(
    state: CustomerState, signals: list[Signal], policy: Policy, tone: str = "sie"
) -> tuple[list[Candidate], list[Blocked]]:
    cons = consents(state, policy)
    profiled = cons["profiling_analytics"].effective_status == "granted"
    tone_used = tone if profiled else "sie"
    chans = _channels(state, policy, cons)
    marketing_channels = list(policy.channels)
    excl = active_exclusions(state, policy)
    cap_max, window = policy.contact_cap
    n_contacts = len(contacts(state, window))
    cap_hit = n_contacts >= cap_max
    blocked: list[Blocked] = []
    cands: dict[str, Candidate] = {}

    for o in policy.offers.values():
        if o.data_missing:
            blocked.append(Blocked(offer_id=o.id, rule_id="DATA-MISSING", reason=f"{o.name}: not enough data ({o.data_missing})"))
    for rule_id, hit in excl:
        blocked.append(Blocked(offer_id="*", rule_id=rule_id, src=hit.src,
                               reason=f"All sales, upsell, retention and one-off offers blocked: {hit.detail}"))
    if cap_hit:
        blocked.append(Blocked(offer_id="*", rule_id="CONTACT-CAP", src="nba_action_history.decided_at",
                               reason=f"{n_contacts} marketing contacts in the last {window} days (cap {cap_max}); marketing paused"))

    base_checks = [Check(rule_id=e, passed=True, detail="not active", src=policy_src(e)) for e in policy.exclusions]
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
    if not profiled:
        for s in marketing_sigs:
            for oid in s.offers:
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
            blocking = [(r, h) for r, h in excl if o.action_type in policy.exclusions[r].blocks]
            if blocking:
                r, h = blocking[0]
                blocked.append(Blocked(offer_id=oid, rule_id=r, src=h.src, reason=f"{o.name} (from {sig_ids}) blocked: {h.detail}"))
                continue
            ok, holding = _holding_check(state, policy, oid, generic=False)
            if not ok:
                blocked.append(Blocked(offer_id=oid, rule_id="HOLDING-PRECONDITION", reason=f"{o.name} (from {sig_ids}): {holding}"))
                continue
            if cap_hit:
                continue  # the customer-level CONTACT-CAP row explains it
            allowed = [ch for ch in marketing_channels if chans[ch].allowed]
            if not allowed:
                reasons = "; ".join(f"{ch}: {chans[ch].reason}" for ch in marketing_channels)
                blocked.append(Blocked(offer_id=oid, rule_id="CONSENT-CHANNEL", reason=f"{o.name}: no allowed channel ({reasons})"))
                continue
            need = next(n for s in sigs for n in s.needs if n in o.addresses)
            why = [f"{s.detail} [{s.id}]" for s in sigs]
            why += [f"also {r.detail} [{r.id}]" for r in reinforcing if set(r.needs) & set(o.addresses)]
            for ch in allowed:
                c = Candidate(
                    tuple_id=tuple_id(oid, ch, tone_used), offer_id=oid, offer_name=o.name, action_type=o.action_type,
                    channel=ch, tone=tone_used, origin="signal", personalised=True, need=need,
                    signals=[s.id for s in sigs] + [r.id for r in reinforcing if set(r.needs) & set(o.addresses)],
                    checks=base_checks + [
                        Check(rule_id="HOLDING-PRECONDITION", passed=True, detail=holding),
                        Check(rule_id="CONSENT-PROFILING", passed=True, detail=f"profiling_analytics granted {prof.updated_at or ''}".strip(), src="consent_status.status"),
                        Check(rule_id="CONSENT-CHANNEL", passed=True, detail=chans[ch].reason, src="consent_status.status"),
                        cap_check,
                    ],
                    why=why,
                )
                cands[c.tuple_id] = c
                signal_offers.add(oid)

    # 3. generic tuples (non-personalised catalog offers, catalog-average p) — §6.12
    gen_cfg = policy.config.get("generic", {})
    gen_allowed = gen_cfg.get("allowed_channels", "all")
    gen_channels = [ch for ch in marketing_channels if chans[ch].allowed and (gen_allowed == "all" or ch in gen_allowed)]
    any_marketing_channel = any(chans[ch].allowed for ch in marketing_channels)
    if not excl and not cap_hit:
        for o in policy.generic_offers:
            if o.id in signal_offers:
                continue
            ok, holding = _holding_check(state, policy, o.id, generic=True)
            if not ok:
                continue  # already owned: removed silently (contract data only)
            for ch in gen_channels:
                c = Candidate(
                    tuple_id=tuple_id(o.id, ch, tone_used), offer_id=o.id, offer_name=o.name, action_type=o.action_type,
                    channel=ch, tone=tone_used, origin="generic", personalised=False, need=None, signals=[],
                    checks=base_checks + [
                        Check(rule_id="HOLDING-PRECONDITION", passed=True, detail=f"not owned: {holding}"),
                        Check(rule_id="CONSENT-PROFILING", passed=True, detail="not needed: generic, non-personalised offer"),
                        Check(rule_id="CONSENT-CHANNEL", passed=True, detail=chans[ch].reason, src="consent_status.status"),
                        cap_check,
                    ],
                    why=[f"Generic catalog offer, the same for every customer; only owned products are removed ({holding})"],
                    notes=["Not personalised: valued with the catalog-average acceptance rate"],
                )
                cands[c.tuple_id] = c
    if not any_marketing_channel and not excl:
        reasons = "; ".join(f"{ch}: {chans[ch].reason}" for ch in marketing_channels)
        blocked.append(Blocked(offer_id="*", rule_id="CONSENT-CHANNEL", reason=f"No consented marketing channel ({reasons})"))

    out = []
    for c in sorted(cands.values(), key=lambda x: ({"service": 0, "signal": 1, "generic": 2}[x.origin], x.offer_id, x.channel)):
        out.append(c.model_copy(update={"path": explain(state, c, policy, signals)}))
    return out, blocked
