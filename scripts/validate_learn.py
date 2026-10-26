"""Validate the feedback loop against the raw files in data/: python scripts/validate_learn.py

Runs `nba.learn` once, then recomputes its numbers independently from the workbook with plain
pandas/numpy (no nba.learn code) and checks:
  1. raw facts       treated / control counts and conversions match README §3
  2. counts          every pattern's sends and conversions, treated and control
  3. posteriors      posterior means exactly; P(uplift > 0) by seeded Monte Carlo
  4. traffic light   each status recomputed from config/learn.yaml
  5. diagnosis       P-AS-01's signal-matched sends recomputed from shop_orders + autostrom_contracts
  6. hard rules      every fix option re-run on all 750 customers (nba.rules.check): consent,
                     exclusions, profiling, contact cap, ΔCLV > 0
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

WORKBOOK = REPO / "data" / "maingau_nba_mockdata.xlsx"
EVAL_TIME = pd.Timestamp("2026-09-30 23:59:59")
DRAWS = 400_000
MC_TOL = 0.01  # Monte Carlo standard error is about 0.001 at 400k draws

failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(label)


def section(title: str) -> None:
    print(f"\n{title}")


def as_bool(series: pd.Series) -> pd.Series:
    return series.map(lambda v: str(v).strip().lower() in {"1", "true", "yes"})


# ---------------------------------------------------------------- independent recomputation


def history(x: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    h = x["nba_action_history"].copy()
    h["decided_at"] = pd.to_datetime(h["decided_at"])
    h = h[h["decided_at"] <= EVAL_TIME]
    h["conv"] = as_bool(h["converted_within_14d"]).astype(int)
    control = as_bool(h["control_group"])
    return h[~control & (h["delivery_status"] == "delivered")], h[control]


def posterior(n: int, conv: int, mean: float, k: float) -> tuple[float, float]:
    return mean * k + conv, (1 - mean) * k + n - conv


def mc_p_positive(t: tuple, c: tuple, seed: int) -> float:
    rng = np.random.default_rng(seed)
    return float((rng.beta(*t, DRAWS) > rng.beta(*c, DRAWS)).mean())


def status_of(n: int, conv: int, p: float, s: dict) -> str:
    if n < s["min_treated"]:
        return "amber"
    if n >= s["red_zero_response_n"] and conv == 0:
        return "red"
    if p <= s["red_p_positive"]:
        return "red"
    if p >= s["green_p_positive"]:
        return "green"
    return "amber"


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="Where nba.learn writes; default a temporary folder")
    parser.add_argument("--skip-rules", action="store_true", help="Skip the 750-customer hard-rule re-runs (check 6)")
    args = parser.parse_args(argv)

    from nba.engine.assemble import assemble
    from nba.engine.runtime import Runtime
    from nba.learn.__main__ import run
    from nba.learn.backtest import with_overrides
    from nba.rules.check import raw_rules, violations

    out = args.out or Path(tempfile.mkdtemp(prefix="learn-validate-"))
    print(f"Running the loop -> {out}")
    runtime = Runtime.load(WORKBOOK)
    run(runtime, out, with_backtest=False)
    health = json.loads((out / "health.json").read_text(encoding="utf-8"))
    loop = {p["key"]: p for p in health["patterns"]}
    case_files = sorted((out / "cases").glob("*.json"))
    cases = [json.loads(f.read_text(encoding="utf-8")) for f in case_files]

    print(f"Reading raw data independently: {WORKBOOK.relative_to(REPO)}")
    x = pd.read_excel(WORKBOOK, sheet_name=None)
    settings = yaml.safe_load((REPO / "config" / "learn.yaml").read_text(encoding="utf-8"))
    policy_yaml = yaml.safe_load((REPO / "kg" / "policy.yaml").read_text(encoding="utf-8"))
    treated, control = history(x)

    section("1. Raw facts (README §3)")
    check((len(treated), int(treated["conv"].sum())) == (2022, 69), "treated 2022 sends, 69 conversions",
          f"{len(treated)}, {int(treated['conv'].sum())}")
    check((len(control), int(control["conv"].sum())) == (248, 5), "control 248 rows, 5 conversions",
          f"{len(control)}, {int(control['conv'].sum())}")
    check(health["meta"]["n_treated"] == len(treated) and health["meta"]["n_control"] == len(control),
          "loop uses the same treated / control rows")

    k = float(settings["prior_strength"])
    mt, mc = treated["conv"].mean(), control["conv"].mean()
    expected = {}
    for offer, rows in treated.groupby("offer_id"):
        ctrl = control[control["offer_id"] == offer]
        expected[offer] = (rows, ctrl)
        for ch, sub in rows.groupby("channel"):
            expected[f"{offer}|{ch}"] = (sub, ctrl)

    section(f"2. Counts per pattern ({len(expected)} patterns)")
    check(set(expected) == set(loop), "same set of patterns", f"missing {sorted(set(expected) - set(loop))}, "
          f"extra {sorted(set(loop) - set(expected))}")
    bad = [key for key, (t, c) in expected.items() if key in loop and
           (loop[key]["n_treated"], loop[key]["conv_treated"], loop[key]["n_control"], loop[key]["conv_control"])
           != (len(t), int(t["conv"].sum()), len(c), int(c["conv"].sum()))]
    check(not bad, "sends and conversions match for every pattern", ", ".join(bad[:5]))

    section(f"3. Posteriors (Monte Carlo, {DRAWS:,} draws, tolerance {MC_TOL})")
    mean_bad, p_bad, mine = [], [], {}
    for i, (key, (t, c)) in enumerate(sorted(expected.items())):
        at = posterior(len(t), int(t["conv"].sum()), mt, k)
        ac = posterior(len(c), int(c["conv"].sum()), mc, k)
        uplift = at[0] / sum(at) - ac[0] / sum(ac)
        p = mc_p_positive(at, ac, seed=i)
        mine[key] = (len(t), int(t["conv"].sum()), p)
        if key in loop and abs(round(uplift, 4) - loop[key]["uplift"]) > 1e-4:
            mean_bad.append(f"{key} {uplift:.4f} vs {loop[key]['uplift']}")
        if key in loop and abs(p - loop[key]["p_positive"]) > MC_TOL:
            p_bad.append(f"{key} {p:.3f} vs {loop[key]['p_positive']}")
    check(not mean_bad, "posterior mean uplift matches", "; ".join(mean_bad[:5]))
    check(not p_bad, "P(uplift > 0) matches the Monte Carlo estimate", "; ".join(p_bad[:5]))

    section("4. Traffic light")
    s = settings["status"]
    thresholds = (s["red_p_positive"], s["green_p_positive"])
    borderline = [key for key, (_, _, p) in mine.items() if any(abs(p - th) < MC_TOL for th in thresholds)]
    wrong = [f"{key}: {status_of(n, conv, p, s)} vs {loop[key]['status']}" for key, (n, conv, p) in mine.items()
             if key in loop and key not in borderline and status_of(n, conv, p, s) != loop[key]["status"]]
    check(not wrong, "every status recomputed from config/learn.yaml", "; ".join(wrong[:5]))
    counts = {st: sum(p["status"] == st for p in loop.values()) for st in ("green", "amber", "red")}
    print(f"        loop: {counts}; borderline (within MC tolerance of a threshold, not judged): {borderline or 'none'}")
    for key in sorted(loop):
        if loop[key]["status"] != "amber":
            p = loop[key]
            print(f"        {p['status']:5}  {key:28} {p['conv_treated']}/{p['n_treated']} vs {p['conv_control']}/{p['n_control']}"
                  f"  P(>0) {p['p_positive']:.0%}")

    section("5. Diagnosis: P-AS-01 signal-matched sends (S3 = Wallbox 11 kW delivered, no active Autostrom)")
    orders = x["shop_orders"]
    wallbox = set(orders[(orders["order_status"] == "delivered") & (orders["product_name"] == "Wallbox 11 kW")]["customer_id"].dropna())
    autostrom = x["autostrom_contracts"]
    s3 = wallbox - set(autostrom[autostrom["status"] == "active"]["customer_id"])
    as01 = treated[treated["offer_id"] == "P-AS-01"]
    matched = as01[as01["customer_id"].isin(s3)]
    case = next((c for c in cases if c["id"] == "FIX-P-AS-01"), None)
    check(case is not None, "fix case FIX-P-AS-01 exists")
    if case:
        split = next(sp for sp in case["splits"] if sp["dimension"] == "target_signal")
        sub = next(g for g in split["subgroups"] if g["label"] == "with target signal")
        check((sub["n_treated"], sub["conv_treated"]) == (len(matched), int(matched["conv"].sum())),
              "signal-matched sends match the raw tables", f"loop {sub['conv_treated']}/{sub['n_treated']}, "
              f"raw {int(matched['conv'].sum())}/{len(matched)}; {len(s3)} customers have S3 today")
        for sp in case["splits"]:
            total = sum(g["n_treated"] for g in sp["subgroups"])
            check(total == len(as01), f"split '{sp['dimension']}' covers all {len(as01)} sends", str(total))

    if not args.skip_rules:
        section("6. Hard rules on all 750 customers, before and after each fix option")
        kg = yaml.safe_load((REPO / "config" / "kg.yaml").read_text(encoding="utf-8"))
        cap = (int(kg["contact_cap"]["max_contacts"]), int(kg["contact_cap"]["window_days"]))
        rules = raw_rules(x, policy_yaml["channels"], EVAL_TIME, cap)
        base = runtime.cards()
        found = violations(base, rules)
        check(not found, "baseline engine: no consent, exclusion, profiling, contact-cap or ΔCLV violation", "; ".join(found[:3]))
        for c in cases:
            for option in c["options"]:
                if not option["overrides"]:
                    continue
                cfg = with_overrides(runtime.cfg, {key: {**v, "case": c["id"], "approved_by": "validator"}
                                                   for key, v in option["overrides"].items()})
                cards = [assemble(runtime.states[cid], runtime.pop, runtime.policy, cfg) for cid in sorted(runtime.states)]
                found = violations(cards, rules)
                changed = sum(a.chosen.tuple_id != b.chosen.tuple_id for a, b in zip(base, cards))
                check(not found, f"{c['id']} option {option['id']}: no violation ({changed} decisions change)",
                      "; ".join(found[:3]))

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
