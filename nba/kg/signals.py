"""Signal extraction S1–S13 (README §6.3). Owner: Agent KG."""

from __future__ import annotations

from nba.contracts import Signal
from nba.kg import predicates as P
from nba.kg.policy import Policy
from nba.state import CustomerState


def extract_signals(state: CustomerState, policy: Policy) -> list[Signal]:
    """Every enabled signal that fires, in policy order, with plain-language detail and evidence refs."""
    out: list[Signal] = []
    for sdef in policy.enabled_signals:
        hit = P.SIGNALS[sdef.predicate](state, policy.params)
        if hit is None:
            continue
        needs = hit.needs or list(sdef.indicates or sdef.reinforces)
        offers = [] if sdef.reinforces else sorted({o for n in needs for o in policy.offers_for_need(n)})
        out.append(Signal(
            id=sdef.id,
            label=sdef.label,
            date=hit.date.date().isoformat() if hit.date else None,
            strength=sdef.strength,
            purpose=sdef.purpose,
            src=hit.src,
            evidence=hit.evidence,
            needs=needs,
            offers=offers,
            detail=hit.detail,
        ))
    return out
