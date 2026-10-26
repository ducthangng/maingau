"""What would change if a fix option were approved: re-run the engine for every customer who has
the offer as a valued tuple, with the option's p overrides, and diff the chosen action."""
from __future__ import annotations

from dataclasses import replace

from nba.engine.assemble import assemble


def with_overrides(cfg, overrides: dict[str, dict]):
    merged = {**(cfg.settings.get("p_overrides") or {}), **overrides}
    return replace(cfg, settings={**cfg.settings, "p_overrides": merged}, _history_index=cfg._history_index, _versions=None)


def valued_offers(card) -> set[str]:
    """Offers this card actually valued: ranked tuples plus tuples dropped for ΔCLV ≤ 0. Tuples blocked by a
    hard rule are not valued, so no p change can bring them back."""
    return {c.offer_id for c in card.candidates} | {b.offer_id for b in card.blocked if b.rule_id == "ECON-NONPOSITIVE"}


def chosen(card) -> tuple[str, float | None]:
    selected = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
    return card.chosen.tuple_id, (round(selected.valuation.delta_clv, 2) if selected else None)


def backtest(runtime, base_cards: dict, overrides: dict[str, dict], reference=()) -> dict:
    if not overrides:
        return {"applies": False, "note": "No engine change; this option is a rewrite by a human with AI."}
    offers = {key.split("|")[0] for key in overrides}
    cfg = with_overrides(runtime.cfg, overrides)
    affected = sorted(cid for cid, card in base_cards.items() if valued_offers(card) & offers)
    changes = []
    for cid in affected:
        before = chosen(base_cards[cid])
        after = chosen(assemble(runtime.states[cid], runtime.pop, runtime.policy, cfg))
        if before != after:
            changes.append({"customer_id": cid, "before": before[0], "delta_clv_before": before[1],
                            "after": after[0], "delta_clv_after": after[1]})
    moved = [c for c in changes if c["before"] != c["after"]]
    total = lambda k: round(sum(c[k] or 0.0 for c in changes), 2)
    return {"applies": True, "customers_valued": len(affected), "decisions_changed": len(moved),
            "values_changed": len(changes) - len(moved),
            "sum_delta_clv_before": total("delta_clv_before"), "sum_delta_clv_after": total("delta_clv_after"),
            "changes": changes, "reference_changed": sorted(c["customer_id"] for c in moved if c["customer_id"] in set(reference)),
            "note": "ΔCLV after uses the option's p; it is an expectation under the new assumption, not a measured result."}
