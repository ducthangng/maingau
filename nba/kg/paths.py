"""Explanation paths through the KG (README §5.4, §6.11). Owner: Agent KG.

Signal tuple:  Customer –EMITTED→ Signal –INDICATES→ Need –ADDRESSED_BY→ Offer –DELIVERED_VIA→ Channel –REQUIRES→ Consent
Service tuple: Customer –EMITTED→ Signal –INDICATES→ Need –ADDRESSED_BY→ Offer –DELIVERED_VIA→ service_agent
Generic tuple: Customer → Offer (generic) –DELIVERED_VIA→ Channel –REQUIRES→ Consent
Every node carries a `ui_ref` so the UI can jump to the matching row of the left card.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nba.contracts import Candidate, PathStep, Signal

if TYPE_CHECKING:
    from nba.kg.policy import Policy
    from nba.state import CustomerState

LINE_OF = {"energy": "energy", "mobile": "mobile", "internet": "internet", "smart_living": "smart_living",
           "shop": "shop", "e_mobility": "autostrom", "service": "service"}


def _node(type_: str, id_: str, label: str | None = None, ui_ref: str | None = None) -> PathStep:
    return PathStep(kind="node", type=type_, id=id_, label=label, ui_ref=ui_ref)


def _edge(type_: str) -> PathStep:
    return PathStep(kind="edge", type=type_)


def explain(state: "CustomerState", candidate: Candidate, policy: "Policy",
            signals: list[Signal] | None = None) -> list[PathStep]:
    if signals is None:
        from nba.kg.signals import extract_signals
        signals = extract_signals(state, policy)
    by_id = {s.id: s for s in signals}
    offer = policy.offers[candidate.offer_id]
    steps = [_node("Customer", state.customer_id, state.customer_id, "header")]

    if candidate.origin in ("signal", "service") and candidate.signals:
        sig = by_id.get(candidate.signals[0])
        need = candidate.need or (sig.needs[0] if sig and sig.needs else None)
        steps += [_edge("EMITTED"),
                  _node("Signal", candidate.signals[0], f"{sig.label}: {sig.detail}" if sig else candidate.signals[0],
                        f"signal:{candidate.signals[0]}")]
        if need:
            steps += [_edge("INDICATES"), _node("Need", need, policy.needs[need]["label_en"])]
        steps.append(_edge("ADDRESSED_BY"))
    else:
        steps.append(PathStep(kind="edge", type="GENERIC_OFFER", label="non-personalised catalog offer"))

    steps += [_node("Offer", offer.id, offer.name, f"product:{LINE_OF.get(offer.business_line, offer.business_line)}"),
              _edge("DELIVERED_VIA")]
    if candidate.channel == policy.service_channel:
        steps.append(_node("Channel", candidate.channel, "service agent (service contact, no marketing consent needed)"))
        return steps
    steps.append(_node("Channel", candidate.channel, candidate.channel.replace("_", " ")))
    consent = policy.channels[candidate.channel].consent
    detail = next((c.detail for c in candidate.checks if c.rule_id == "CONSENT-CHANNEL" and c.passed), "granted")
    steps += [_edge("REQUIRES"), _node("Consent", consent, f"{consent}: {detail} ✓", f"consent:{consent}")]
    return steps
