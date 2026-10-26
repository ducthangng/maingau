"""Reference customers and sensitivity under both documented probability modes."""
from __future__ import annotations

from nba.contracts import NO_ACTION
from nba.engine.assemble import assemble, evaluate_candidates
from nba.engine.profile_adapter import infer_tone
from nba.kg.rules import generate_candidates
from nba.kg.signals import extract_signals

EXPECTED = {
    "MG-100051": "P-EN-03 (report)", "MG-100060": "P-EN-03 (report)",
    "MG-100096": "P-SV-01", "MG-100186": "P-SV-01", "MG-100068": "competing S1/S3/S4 (report)",
    "MG-100023": "P-AS-01 (strict in rate mode)", "MG-100112": "generic only; economics decide (K11)",
    "MG-100009": "P-SV-01", "MG-100659": "P-SV-01", "MG-100035": "NO_ACTION; no sales",
    "MG-100087": "NO_ACTION; no sales", "MG-100004": "P-SV-01; generic content/Sie",
    "MG-100012": "generic only/Sie",
}


def test_report(states, pop, policy, cfg) -> str:
    lines = ["# NBA reference report", "", "Snapshot mode: provided. Mock data only. Probability comparisons are descriptive, not causal uplift.",
             "", "ΔCLV uses the model basis; displayed CLV remains the supplied snapshot. Service success probability is an assumption.",
             "", "Profile/timeline availability is stated in each card's data_quality. This report covers the 13 reference customers; the tests cover all 750 customers."]
    sensitivity = float(cfg.settings["sensitivity_pct"]) / 100
    for mode in ("rate", "uplift"):
        mode_cfg = cfg.with_mode(mode)
        lines += ["", f"## Mode: {mode}", "", "| Customer | Expected | Chosen tuple | ΔCLV € | p | Confidence |",
                  "|---|---|---|---:|---:|---|"]
        results = {}
        for cid, expected in EXPECTED.items():
            if cid not in states:
                continue
            card = assemble(states[cid], pop, policy, mode_cfg)
            results[cid] = card
            chosen = next((c for c in card.candidates if c.tuple_id == card.chosen.tuple_id), None)
            v = chosen.valuation if chosen else None
            lines.append(f"| {cid} | {expected} | {card.chosen.tuple_id.replace('|', '/')} | {v.delta_clv:.4f} | {v.p_accept:.4%} | {v.confidence} |" if v
                         else f"| {cid} | {expected} | NO_ACTION | n.a. | n.a. | n.a. |")
        for cid, card in results.items():
            lines += ["", f"### {cid}", "", card.chosen.reason_line.replace("|", "/"), "",
                      "| Tuple | CLV shown | CLV model | Accept | Reject | p | Cost | ΔCLV | Level |",
                      "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
            for c in card.candidates[:3]:
                v = c.valuation
                lines.append(f"| {c.tuple_id.replace('|', '/')} | {v.clv_now_shown:.2f} | {v.clv_now_model:.2f} | {v.clv_after_accept:.2f} | {v.clv_after_reject:.2f} | {v.p_accept:.4%} | {v.contact_cost:.2f} | {v.delta_clv:.4f} | {v.p_source.level} |")
            economic = [b for b in card.blocked if b.rule_id == "ECON-NONPOSITIVE"]
            if economic:
                lines += ["", "Non-positive tuples: " + "; ".join(b.reason.replace("|", "/") for b in economic)]
            lines += ["", "Sensitivity: scale each evaluated tuple's p and incremental catalog margin. Re-run tier arbitration; service resolution cost and the existing margin stay unchanged.",
                      "", "| p factor | Margin factor | Best tuple | ΔCLV € | Same as base |", "|---:|---:|---|---:|---|"]
            state = states[cid]
            signals = extract_signals(state, policy)
            candidates, _ = generate_candidates(state, signals, policy, infer_tone(state, policy).value)
            for p_scale in (1 - sensitivity, 1.0, 1 + sensitivity):
                for margin_scale in (1 - sensitivity, 1.0, 1 + sensitivity):
                    winner, _, _ = evaluate_candidates(candidates, state, policy, mode_cfg, p_scale=p_scale, margin_scale=margin_scale)
                    tid = winner.tuple_id if winner else NO_ACTION
                    delta = f"{winner.valuation.delta_clv:.4f}" if winner else "n.a."
                    lines.append(f"| {p_scale:.2f} | {margin_scale:.2f} | {tid.replace('|', '/')} | {delta} | {'yes' if tid == card.chosen.tuple_id else 'no'} |")
    return "\n".join(lines) + "\n"
