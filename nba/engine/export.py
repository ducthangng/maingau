"""Small static card view; the runtime/API retain every evaluated channel tuple."""
from __future__ import annotations

from nba.contracts import Alternative, CustomerCard


def export_card(card: CustomerCard) -> CustomerCard:
    """Keep the best channel per offer and detailed proof for the chosen action plus three alternatives.

    Scores and explicit null values are preserved. Dropped channels remain available in
    Runtime/API, and the chosen tuple never changes during this presentation projection.
    """
    chosen = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
    by_offer = {chosen.offer_id: chosen} if chosen else {}
    for candidate in card.candidates:
        by_offer.setdefault(candidate.offer_id, candidate)
    candidates = list(by_offer.values())
    if card.chosen.deferred_until:  # a waiting customer: the planned action and one fallback (API has all)
        candidates = candidates[:2]
    detailed = {c.tuple_id for c in candidates[:4]}
    projected = []
    for position, candidate in enumerate(candidates, 1):
        update = {"rank": position}
        if candidate.tuple_id not in detailed:
            update.update(checks=[], path=[])
        projected.append(candidate.model_copy(update=update))
    alternatives = []
    rules = card.rules
    if rules is not None:  # the full report stays in Runtime/API; the static card keeps tier 2 outcomes
        rules = rules.model_copy(update={"counters": [], "results": [
            r.model_copy(update={"measured": {}, "detail": r.detail if r.result == "defer" else None})
            for r in rules.results if r.tier != "compliance" and r.result in {"block", "defer", "off"}]})
    shown = {c.offer_id for c in projected}
    seen: set[str] = set()
    blocked = []
    for row in card.blocked:  # "waits until" once per offer, and only for offers the card does not show
        if row.until and row.rule_id in {"BUSINESS-RULE", "CONTACT-CAP"} and row.offer_id != "*":
            if row.offer_id in seen or row.offer_id in shown:
                continue
            seen.add(row.offer_id)
        blocked.append(row)
    for candidate in projected[1:4] if chosen else []:
        gap = chosen.valuation.delta_clv - candidate.valuation.delta_clv
        reason = (f"Lower expected ΔCLV by €{gap:.2f}" if gap > 0
                  else "Equal expected ΔCLV; tie broken by probability, contact cost, offer ID and tuple ID")
        alternatives.append(Alternative(tuple_id=candidate.tuple_id, delta_clv=candidate.valuation.delta_clv,
                                        why_lower=reason))
    return card.model_copy(update={"candidates": projected, "alternatives": alternatives, "rules": rules, "blocked": blocked})
