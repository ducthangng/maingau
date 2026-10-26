"""Contact history and fatigue (README §4.1 B3)."""

from __future__ import annotations

from collections import Counter

from nba.contracts import Fatigue
from nba.profile.facts import clean, day
from nba.state import contacts

IGNORED = {"ignored", "dismissed"}


def build_fatigue(state) -> Fatigue:
    delivered = [r for r in state.rows.get("nba_action_history", [])
                 if r.get("delivery_status") == "delivered" and not r.get("control_group")]
    responded = [r for r in delivered if r.get("response") == "clicked" or r.get("converted_within_14d")]
    ignored = Counter(r["offer_id"] for r in delivered if r.get("response") in IGNORED)
    feedback = sorted(state.rows.get("service_nba_feedback", []), key=lambda r: (r.get("shown_at") is None, r.get("shown_at")))
    return Fatigue(
        contacts_30d=len(contacts(state, 30)),
        contacts_90d=len(contacts(state, 90)),
        response_rate=round(len(responded) / len(delivered), 3) if delivered else None,
        repeatedly_ignored=sorted(o for o, n in ignored.items() if n >= 2),
        legacy_no_consent_check=sum(1 for r in delivered if r.get("consent_checked") is False),
        agent_feedback=[{
            "date": day(r.get("shown_at")), "ticket_id": r.get("ticket_id"), "offer_id": clean(r.get("suggested_offer_id")),
            "agent_action": clean(r.get("agent_action")), "customer_reaction": clean(r.get("customer_reaction")),
            "dismiss_reason": clean(r.get("dismiss_reason")), "src": "service_nba_feedback",
        } for r in feedback],
    )
