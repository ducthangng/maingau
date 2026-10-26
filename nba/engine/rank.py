"""Rank eligible tuples by euros; urgency is a separate worklist measure."""
from __future__ import annotations


def rank(candidates):
    if any(c.valuation is None for c in candidates):
        raise ValueError("Every ranked candidate must have a valuation")
    ordered = sorted((c for c in candidates if c.valuation.delta_clv > 0), key=lambda c: (
        -c.valuation.delta_clv, -c.valuation.p_accept, c.valuation.contact_cost, c.offer_id, c.tuple_id,
    ))
    ordered = [c.model_copy(update={"rank": i}) for i, c in enumerate(ordered, 1)]
    return (ordered[0] if ordered else None), ordered
