"""Customer journey for the Customer 360° dashboard: what happened and how the customer reacted.

A separate document next to the card (GET /api/customers/{id}/journey, static journey/<id>.json), so
the card and its timeline stay as they are. It adds what the timeline leaves out: newsletter
deliveries, suggestions shown to service agents, charging per day, portal visits, the tone of past
proposals, order values and how tickets were resolved. Plain facts only: no CLV, scores, warnings or
payment data. Last `months` months plus future contract milestones, newest first.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from nba.contracts import Journey, JourneyEvent
from nba.kg.contacts import _yes
from nba.profile.facts import clean, day, to_datetime

CONSENT_LABELS = {"granted": "granted", "not_given": "not given", "withdrawn": "withdrawn"}
RESPONSES = {"ignored": "no reaction", "dismissed": "dismissed it", "viewed": "viewed it", "clicked": "clicked it"}
TONES = {"du": "Du", "sie": "Sie"}


def _words(code) -> str | None:
    code = clean(code)
    return None if code is None else str(code).replace("_", " ")


def _duration(seconds) -> str | None:
    seconds = clean(seconds)
    if seconds is None:
        return None
    m, s = divmod(int(seconds), 60)
    return f"{m} min {s} s" if m else f"{s} s"


def _eur(v) -> str | None:
    v = clean(v)
    return None if v is None else f"€{v:,.2f}".replace(".00", "")


def _facts(**kv) -> dict:
    return {k: v for k, v in ((k, clean(v)) for k, v in kv.items()) if v not in (None, "", [], False)}


def build_journey(state, offer_names: dict[str, str] | None = None, campaigns: dict[str, dict] | None = None,
                  months: int = 12) -> Journey:
    names, campaigns = offer_names or {}, campaigns or {}
    eval_time = state.eval_time
    start = eval_time - timedelta(days=round(months * 30.44))
    raw: list[dict] = []

    def offer(oid) -> str:
        return names.get(oid) or str(oid)

    def add(when, type_, title, src, ref=None, detail=None, reaction=None, flags=None, facts=None, future_ok=False):
        when = to_datetime(when)
        if when is None:
            return
        future = when > eval_time
        if (future and not future_ok) or (not future and when <= start):
            return
        raw.append({"at": when, "date": day(when), "future": future, "type": type_, "title": title, "detail": detail,
                    "reaction": reaction, "src": src, "ref": ref, "flags": flags or [], "facts": facts or {}})

    rows = state.rows
    # contracts, milestones and consent: the same facts as the card timeline
    for r in rows.get("energy_contracts", []):
        ref, tariff = f"contract:{r['contract_id']}", r.get("tariff")
        add(r.get("start_date"), "contract", f"{tariff} started", "energy_contracts.start_date", ref)
        add(r.get("cancellation_received_at"), "contract", f"{tariff}: cancellation received",
            "energy_contracts.cancellation_received_at", ref, flags=["cancellation"])
        add(r.get("meter_deregistered_at"), "contract", f"{tariff}: gas meter deregistered",
            "energy_contracts.meter_deregistered_at", ref)
        if r.get("status") == "active":
            add(r.get("price_guarantee_until"), "milestone", f"{tariff}: price guarantee ends",
                "energy_contracts.price_guarantee_until", ref, future_ok=True)
    for r in rows.get("mobile_contracts", []):
        ref = f"contract:{r['contract_id']}"
        add(r.get("start_date"), "contract", f"{r.get('plan')} started", "mobile_contracts.start_date", ref)
        if r.get("status") == "active":
            add(r.get("min_term_end"), "milestone", f"{r.get('plan')}: minimum term ends", "mobile_contracts.min_term_end",
                ref, future_ok=True)
    for r in rows.get("autostrom_contracts", []):
        ref = f"contract:{r['contract_id']}"
        add(r.get("start_date"), "contract", "Autostrom started", "autostrom_contracts.start_date", ref)
        add(r.get("cancelled_at"), "contract", "Autostrom cancelled", "autostrom_contracts.cancelled_at", ref,
            flags=["cancellation"])
    for r in rows.get("consent_status", []):
        add(r.get("updated_at"), "consent", f"Consent {_words(r['consent_type'])}: "
            f"{CONSENT_LABELS.get(r.get('status'), r.get('status'))}", "consent_status.updated_at",
            f"consent:{r['consent_type']}", _words(r.get("source")))

    # past proposals of the legacy engine, with the tone of address
    for r in rows.get("nba_action_history", []):
        if r.get("control_group"):
            continue
        tone = TONES.get(r.get("tonality"), r.get("tonality"))
        reaction = RESPONSES.get(r.get("response"), _words(r.get("response")))
        if r.get("converted_within_14d"):
            reaction = f"{reaction or 'no reaction recorded'} · bought within 14 days"
        add(r.get("decided_at"), "proposal", f"Offer {offer(r.get('offer_id'))} via {_words(r.get('channel'))}",
            "nba_action_history.decided_at", f"action:{r['action_id']}", f"tone {tone} · {_words(r.get('delivery_status'))}",
            reaction, facts=_facts(offer_id=r.get("offer_id"), channel=r.get("channel"), tone=r.get("tonality"),
                                   response=r.get("response"), converted_within_14d=r.get("converted_within_14d"),
                                   conversion_value_eur=r.get("conversion_value_eur")))

    # service tickets, with how they were resolved
    transcripts = {r.get("ticket_id") for r in rows.get("call_transcripts", [])}
    for r in rows.get("service_interactions", []):
        flags = (["open"] if r.get("status") == "open" else []) + (["repeat contact"] if clean(r.get("repeat_of_ticket_id")) else [])
        resolution = _words(r.get("resolution_code"))
        csat = clean(r.get("csat_1to5"))
        detail = " · ".join(x for x in (_words(r.get("channel")), r.get("status"),
                                         resolution and f"resolution: {resolution}") if x)
        add(r.get("created_at"), "ticket", f"Ticket: {_words(r.get('category'))}", "service_interactions.created_at",
            f"ticket:{r['ticket_id']}", detail, None if csat is None else f"CSAT {csat}/5", flags,
            _facts(category=r.get("category"), channel=r.get("channel"), status=r.get("status"),
                   resolution_code=r.get("resolution_code"), resolved_on=day(r.get("resolved_at")), csat=csat,
                   first_contact_resolution=r.get("first_contact_resolution"),
                   repeat_of=r.get("repeat_of_ticket_id"), goodwill_eur=r.get("goodwill_eur"),
                   call_transcript=r.get("ticket_id") in transcripts))

    # shop orders with their value (never the payment method)
    for r in rows.get("shop_orders", []):
        qty = clean(r.get("quantity")) or 1
        detail = " · ".join(x for x in (r.get("order_status"), _eur(r.get("line_value_eur")),
                                         f"{qty} pieces" if qty > 1 else None) if x)
        add(r.get("order_created_at"), "order", str(r.get("product_name")), "shop_orders.order_created_at",
            f"order:{r['order_id']}", detail, flags=[] if r.get("order_status") == "delivered" else [str(r.get("order_status"))],
            facts=_facts(product=r.get("product_name"), category=r.get("product_category"), quantity=qty,
                         value_eur=r.get("line_value_eur"), status=r.get("order_status"),
                         order_channel=r.get("order_channel"), newsletter_campaign=r.get("newsletter_attributed_campaign")))

    # newsletter deliveries: an Apple Mail preload is not a real open
    for r in rows.get("newsletter_performance", []):
        if r.get("bounced"):
            reaction, flags = "bounced", ["bounced"]
        elif not r.get("delivered"):
            reaction, flags = "not delivered", ["not delivered"]
        else:
            human = r.get("opened_at") is not None and r.get("open_client_class") != "apple_mpp_prefetch"
            parts = ["opened" if human or r.get("clicked_at") is not None else "not opened"]
            if r.get("clicked_at") is not None:
                parts.append(f"clicked {_words(r.get('click_target')) or 'a link'}")
            if r.get("converted_within_7d"):
                parts.append("bought within 7 days")
            if r.get("unsubscribed"):
                parts.append("unsubscribed")
            reaction, flags = " · ".join(parts), (["unsubscribed"] if r.get("unsubscribed") else [])
        campaign = campaigns.get(r.get("campaign_id"), {})
        subject, tone = clean(campaign.get("subject_line")), campaign.get("tonality")
        add(r.get("campaign_sent_at"), "newsletter", f"Newsletter: {subject or r.get('campaign_id')}",
            "newsletter_performance", f"newsletter:{r.get('campaign_id')}",
            " · ".join(x for x in (_words(campaign.get("product_focus")), tone and f"tone {TONES.get(tone, tone)}") if x) or None,
            reaction, flags,
            _facts(campaign_id=r.get("campaign_id"), subject=subject, delivered=r.get("delivered"), bounced=r.get("bounced"),
                   opened=day(r.get("opened_at")), open_client=r.get("open_client_class"), clicked=day(r.get("clicked_at")),
                   click_target=r.get("click_target"), converted_within_7d=r.get("converted_within_7d"),
                   unsubscribed=r.get("unsubscribed")))

    # offers a service agent saw on screen during a ticket (agent-assist pilot)
    for r in rows.get("service_nba_feedback", []):
        action = r.get("agent_action")
        detail = f"{_words(r.get('channel'))} · agent {action}"
        if clean(r.get("dismiss_reason")):
            detail += f" ({_words(r['dismiss_reason'])})"
        mentioned = _yes(r.get("offer_mentioned_to_customer"))
        reaction = _words(r.get("customer_reaction")) if mentioned else "not mentioned to the customer"
        if r.get("converted_within_14d"):
            reaction = f"{reaction or 'no reaction recorded'} · bought within 14 days"
        add(r.get("shown_at"), "agent_suggestion", f"Agent saw suggestion: {offer(r.get('suggested_offer_id'))}",
            "service_nba_feedback.shown_at", f"feedback:{r.get('feedback_id')}", detail, reaction,
            facts=_facts(offer_id=r.get("suggested_offer_id"), ticket_id=r.get("ticket_id"), agent_action=action,
                         dismiss_reason=r.get("dismiss_reason"), mentioned_to_customer=mentioned,
                         customer_reaction=r.get("customer_reaction"), converted_within_14d=r.get("converted_within_14d")))

    # charging sessions, one event per day
    days: dict[str, list[dict]] = defaultdict(list)
    for r in rows.get("charge_sessions", []):
        when = to_datetime(r.get("started_at"))
        if when is not None:
            days[day(when)].append(r)
    for d, sessions in days.items():
        status = Counter(s.get("session_status") for s in sessions)
        kwh = round(sum(clean(s.get("energy_kwh")) or 0 for s in sessions), 1)
        reasons = sorted({_words(s.get("failure_reason")) for s in sessions if clean(s.get("failure_reason"))})
        detail = " · ".join(f"{n} {k}" for k, n in sorted(status.items()) if n) + (f" · {kwh} kWh" if kwh else "")
        if reasons:
            detail += f" ({', '.join(reasons)})"
        n = len(sessions)
        add(min(to_datetime(s.get("started_at")) for s in sessions), "charging",
            f"Charging: {n} session{'s' if n > 1 else ''}", "charge_sessions.started_at", f"charging:{d}", detail,
            flags=["failed"] if status.get("failed") or status.get("aborted") else [],
            facts=_facts(sessions=n, completed=status.get("completed"), failed=status.get("failed"),
                         aborted=status.get("aborted"), failure_reasons=reasons, energy_kwh=kwh,
                         cities=sorted({str(s.get("location_city")) for s in sessions if clean(s.get("location_city"))})))

    # portal and app visits; the pages are named in the data
    for r in rows.get("portal_sessions", []):
        pages = [p for p in str(clean(r.get("pages_viewed")) or "").split("|") if p]
        banner = _yes(r.get("offer_banner_shown"))
        detail = " · ".join(x for x in (", ".join(_words(p) for p in pages), _duration(r.get("duration_s")),
                                         "offer banner shown" if banner else None) if x)
        add(r.get("session_start"), "portal", f"{'App' if r.get('client') == 'app' else 'Portal'} visit",
            "portal_sessions.session_start", f"portal:{r.get('session_id')}", detail or None,
            facts=_facts(client=r.get("client"), pages=pages, duration_s=r.get("duration_s"), offer_banner_shown=banner))

    raw.sort(key=lambda x: (x["at"], x["type"], x["ref"] or ""), reverse=True)
    events = [JourneyEvent(id=f"jr-{i:03d}", **{k: v for k, v in x.items() if k != "at"}) for i, x in enumerate(raw, start=1)]
    return Journey(customer_id=state.customer_id, eval_time=eval_time.isoformat(), months=months,
                   counts=dict(sorted(Counter(e.type for e in events).items())), events=events)


def lookups(tables, policy) -> dict:
    """Offer names and newsletter campaigns (subject, focus, tone) for build_journey."""
    campaigns = tables.get("newsletter_campaigns")
    return {"offer_names": {oid: o.name for oid, o in policy.offers.items()},
            "campaigns": {} if campaigns is None else {c["campaign_id"]: c for c in campaigns.to_dict("records")}}


def export_journey(journey: Journey) -> Journey:
    """Static export (web/public/data/journey): the text the UI shows, without `src` and `facts`."""
    return journey.model_copy(update={"events": [e.model_copy(update={"src": None, "facts": {}}) for e in journey.events]})
