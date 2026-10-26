"""Reproducible pitch evidence on mock data, with explicit cohorts and limitations."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from nba.contracts import NO_ACTION
from nba.engine.assemble import assemble
from nba.kg.signals import extract_signals

LABEL = "model-based, mock data, not causal uplift"


def chosen_delta(card):
    if card.chosen.tuple_id == NO_ACTION:
        return 0.0  # No intervention has zero incremental value; no missing estimate is imputed.
    return next(c.valuation.delta_clv for c in card.candidates if c.tuple_id == card.chosen.tuple_id)


def impact_metrics(cards, states):
    offers, archetypes = defaultdict(list), defaultdict(list)
    legacy_rows, legacy_rules = [], Counter()
    for card in cards:
        selected = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
        delta = chosen_delta(card)
        offers[selected.offer_id if selected else NO_ACTION].append(delta)
        archetypes[card.triage.archetype.id].append(delta)
        state = states[card.customer_id]
        history = [r for r in state.rows.get("nba_action_history", [])
                   if r.get("decided_at") and r["decided_at"] <= state.eval_time]
        if not history or card.legacy_comparison is None:
            continue
        row = max(history, key=lambda r: (r["decided_at"], r["action_id"]))
        if row.get("decision_source") != "rule_engine_v1":
            continue
        legacy = card.legacy_comparison
        rules = set(legacy.blocked_now_by)
        legacy_rules.update(rules)
        legacy_rows.append({"customer_id": card.customer_id, "rules": sorted(rules),
                            "delivered": not row.get("control_group") and row.get("delivery_status") == "delivered",
                            "legacy_delta": legacy.delta_clv_our_model, "our_delta": delta})

    def grouped(groups):
        return {k: {"customers": len(values), "sum_delta_clv": math.fsum(values)}
                for k, values in sorted(groups.items())}

    valued = [r for r in legacy_rows if r["legacy_delta"] is not None]
    delivered = [r for r in valued if r["delivered"]]
    comparisons = {}
    for name, rows in (("all_latest", valued), ("delivered_latest", delivered)):
        old, new = math.fsum(r["legacy_delta"] for r in rows), math.fsum(r["our_delta"] for r in rows)
        comparisons[name] = {"customers": len(rows), "legacy_sum": old, "our_sum": new, "difference": new - old}
    return {"n_customers": len(cards), "sum_delta_clv": math.fsum(chosen_delta(c) for c in cards),
            "by_offer": grouped(offers), "by_archetype": grouped(archetypes),
            "legacy": {"latest_proposals": len(legacy_rows), "latest_delivered": sum(r["delivered"] for r in legacy_rows),
                       "blocked": sum(bool(r["rules"]) for r in legacy_rows),
                       "non_economic_blocked": sum(bool(set(r["rules"]) - {"ECON-NONPOSITIVE"}) for r in legacy_rows),
                       "missing_valuation": len(legacy_rows) - len(valued),
                       "by_rule": dict(sorted(legacy_rules.items())), "comparisons": comparisons}}


def need_first_metrics(states, policy, history):
    """Compare offers with an implemented trigger, using signal presence at the snapshot.

    This deliberately does not invent target predicates for generic/unsupported offers,
    and does not pretend the snapshot reconstructs what was known when a past action ran.
    """
    supported = {oid for signal in policy.enabled_signals for need in signal.indicates
                 for oid in policy.offers_for_need(need)}
    matches = {cid: {oid for signal in extract_signals(state, policy) for oid in signal.offers}
               for cid, state in states.items()}
    by_offer = defaultdict(lambda: {"with_n": 0, "with_conversions": 0, "without_n": 0, "without_conversions": 0})
    excluded, treated = Counter(), 0
    for row in history:
        if row.get("control_group") or row.get("delivery_status") != "delivered" or row["customer_id"] not in states:
            continue
        treated += 1
        oid = row["offer_id"]
        if oid not in supported:
            excluded[oid] += 1
            continue
        group = "with" if oid in matches[row["customer_id"]] else "without"
        by_offer[oid][group + "_n"] += 1
        by_offer[oid][group + "_conversions"] += int(bool(row.get("converted_within_14d")))
    counts = {k: sum(row[k] for row in by_offer.values()) for k in
              ("with_n", "with_conversions", "without_n", "without_conversions")}
    comparable = [row for row in by_offer.values() if row["with_n"] and row["without_n"]]
    denominator = sum(row["with_n"] + row["without_n"] for row in comparable)
    standardised = {}
    for group in ("with", "without"):
        standardised[group] = (math.fsum((row["with_n"] + row["without_n"]) / denominator
                                         * row[group + "_conversions"] / row[group + "_n"] for row in comparable)
                               if denominator else None)
    ratio = (standardised["with"] / standardised["without"] if standardised["without"] else None)
    return {**counts, "treated_n": treated, "excluded_n": sum(excluded.values()), "excluded_by_offer": dict(sorted(excluded.items())),
            "by_offer": dict(sorted(by_offer.items())), "standardised_rates": standardised,
            "standardised_ratio": ratio, "standardised_offers": len(comparable)}


def history_audit(history):
    result = {name: {"treated_n": 0, "treated_conversions": 0, "control_n": 0, "control_conversions": 0}
              for name in ("all", "checked", "unchecked")}
    for row in history:
        group = "control" if row.get("control_group") else "treated" if row.get("delivery_status") == "delivered" else None
        if group is None:
            continue
        checked = "checked" if row.get("consent_checked") else "unchecked"
        for key in ("all", checked):
            result[key][group + "_n"] += 1
            result[key][group + "_conversions"] += int(bool(row.get("converted_within_14d")))
    return result


def fraction(conversions, n):
    return f"{conversions}/{n} ({conversions / n:.2%})" if n else "n.a. (0 observations)"


def impact_report(cards, states, pop, policy, cfg):
    states = {card.customer_id: states[card.customer_id] for card in cards}
    times = sorted({state.eval_time.isoformat() for state in states.values()})
    lines = ["# NBA impact report", "", f"**{LABEL}.**", "",
             f"Scope: {len(states)} customers; provided state at {', '.join(times)}. One proposal per customer; NO_ACTION contributes zero incremental value.",
             "All euro amounts are expected changes in the workbook's ten-year CLV, not realised sales or annual revenue. "
             "No actions have been sent. Service success probability is an assumption.", "",
             f"Inputs: customer_value, product_catalog and value_assumptions for valuation; nba_action_history for probabilities and legacy proposals; "
             f"implemented KG signals for the need-first comparison. Value model {cfg.settings['value_model']}, policy {policy.version}; "
             f"assumed service success probability {cfg.settings['p_service_success']:.0%}."]
    for mode in ("rate", "uplift"):
        mode_cfg = cfg.with_mode(mode)
        current = cards if mode == cfg.p_mode else [assemble(state, pop, policy, mode_cfg) for state in states.values()]
        metric = impact_metrics(current, states)
        lines += ["", f"## Mode: {mode}", "", f"Total expected ΔCLV: **€{metric['sum_delta_clv']:,.2f}** ({LABEL}).",
                  "", "### By offer", "", "| Offer | Customers | Σ expected ΔCLV (€) |", "|---|---:|---:|"]
        for oid, row in metric["by_offer"].items():
            name = cfg.offers[oid]["product_name"] if oid in cfg.offers else "No action"
            lines.append(f"| {oid} — {name} | {row['customers']} | {row['sum_delta_clv']:,.2f} |")
        lines += ["", "### By archetype", "", "| Archetype | Customers | Σ expected ΔCLV (€) |", "|---|---:|---:|"]
        for aid, row in metric["by_archetype"].items():
            lines.append(f"| {aid} — {policy.archetypes[aid]} | {row['customers']} | {row['sum_delta_clv']:,.2f} |")
        legacy = metric["legacy"]
        lines += ["", "### Latest legacy proposals under today's state", "",
                  f"{legacy['latest_proposals']} customers have a latest rule_engine_v1 proposal; {legacy['latest_delivered']} were delivered. "
                  "Control/not-sent rows are proposals, not customer contacts.", "",
                  f"{legacy['blocked']} latest proposals would now be blocked by at least one recorded rule; "
                  f"{legacy['non_economic_blocked']} have a non-economic gate blocker. Rule counts below are non-exclusive and use legacy_comparison.blocked_now_by.",
                  "", "| Rule | Latest proposals blocked |", "|---|---:|"]
        lines += [f"| {rule} | {n} |" for rule, n in legacy["by_rule"].items()]
        lines += ["", "| Aligned comparison cohort | Customers with both values | Legacy expected ΔCLV (€) | Our expected ΔCLV (€) | Difference (€) |",
                  "|---|---:|---:|---:|---:|"]
        for cohort, values in legacy["comparisons"].items():
            lines.append(f"| {cohort} | {values['customers']} | {values['legacy_sum']:,.2f} | {values['our_sum']:,.2f} | {values['difference']:,.2f} |")
        lines += ["", f"Missing legacy valuations excluded from both aligned sums: {legacy['missing_valuation']}. "
                  "Legacy values are counterfactuals under the current state and model, including blocked tuples; "
                  "the difference is not an experimentally measured benefit or causal uplift."]

    need = need_first_metrics(states, policy, cfg.history)
    lines += ["", "## Need-first history check (Q-NBA-09)", "", f"**{LABEL}.**", "",
              "Method: extract the implemented S1–S13 signals from each supplied customer state and use signal.offers to match a delivered legacy offer. "
              "S10 only reinforces evidence and creates no offer. Signal presence is measured at the snapshot, not at send time; "
              "contract, device and service facts may postdate a past contact. This is a cross-sectional proxy, not a historical replay or a causal estimate.", "",
              f"Restrict the comparison to offers with an implemented trigger: {need['with_n'] + need['without_n']} of {need['treated_n']} treated/delivered observations. "
              f"Excluded: {need['excluded_n']} observations for offers without an implemented trigger ({need['excluded_by_offer']}). "
              "No missing predicate is invented, and a signal match does not imply current consent or eligibility.", "",
              "| Snapshot target signal | Conversions / observations |", "|---|---:|",
              f"| Present | {fraction(need['with_conversions'], need['with_n'])} |",
              f"| Absent | {fraction(need['without_conversions'], need['without_n'])} |", "",
              "| Offer | Signal present | Signal absent |", "|---|---:|---:|"]
    for oid, row in need["by_offer"].items():
        lines.append(f"| {oid} | {fraction(row['with_conversions'], row['with_n'])} | {fraction(row['without_conversions'], row['without_n'])} |")
    if need["standardised_ratio"] is not None:
        rates = need["standardised_rates"]
        lines += ["", f"Using the same offer weights in both groups gives {rates['with']:.2%} vs {rates['without']:.2%} "
                  f"(descriptive ratio {need['standardised_ratio']:.2f}× over {need['standardised_offers']} offers). "
                  "Each offer's weight is its treated observation count divided by the count across offers with both groups. "
                  "This adjusts offer mix only; small samples, timing leakage and selection remain."]
    lines += ["", "The README's earlier 38/558 vs 27/1,280 (6.8% vs 2.1%) and roughly 2.3× within-offer statistic "
              "is not reproduced by the implemented signal definitions and this explicit cohort. Do not reuse those figures as results of S1–S13. "
              "Use the table above with its denominators and snapshot-proxy limitation; this mock history cannot prove causal uplift."]

    audit = history_audit(cfg.history)
    lines += ["", "## Propensity observation policy (Q-NBA-10)", "",
              "Decision: retain checked and unchecked legacy observations for descriptive probability calibration, using README §6.6's treated/control definitions. "
              "consent_checked is audit metadata; it is never permission for a current contact. All current actions must pass today's KG gates. "
              "Dropping unchecked observations would select a different calibration cohort; its counts are exposed below rather than silently discarding conversions.", "",
              "| Training cohort | Treated conversions / n | Control conversions / n |", "|---|---:|---:|"]
    for key, row in audit.items():
        lines.append(f"| {key} | {fraction(row['treated_conversions'], row['treated_n'])} | {fraction(row['control_conversions'], row['control_n'])} |")
    lines += ["", f"**{LABEL}.** A controlled holdout with at-send signal logging is required to estimate causal uplift."]
    return "\n".join(lines) + "\n"
