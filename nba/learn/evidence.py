"""Outcome evidence: history rows split into treated and control, plus agent feedback and the
target signals each customer has at evaluation time."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from nba.data import REPO
from nba.kg.signals import extract_signals
from nba.learn.stats import Arm, Uplift, uplift

CONFIG_PATH = REPO / "config" / "learn.yaml"


def load_settings(path: str | Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def target_signals(policy) -> dict[str, set[str]]:
    """Offer -> signals that indicate a need the offer addresses (the KG's own targeting)."""
    return {o.id: {s.id for s in policy.signals.values() if set(s.indicates) & set(o.addresses)}
            for o in policy.offers.values()}


@dataclass
class Evidence:
    treated: list[dict]
    control: list[dict]
    feedback: list[dict]
    signals: dict[str, set[str]]  # customer -> signal IDs at eval time
    targets: dict[str, set[str]]  # offer -> target signal IDs
    settings: dict
    decisions: list[dict] = field(default_factory=list)  # human decisions exported from the UI or API

    @classmethod
    def from_runtime(cls, runtime, settings=None, decisions=None):
        t = next(iter(runtime.states.values())).eval_time
        rows = [r for r in runtime.tables["nba_action_history"].to_dict("records")
                if r.get("decided_at") and r["decided_at"] <= t]
        feedback = [r for r in runtime.tables["service_nba_feedback"].to_dict("records")
                    if r.get("shown_at") and r["shown_at"] <= t]
        signals = {cid: {s.id for s in extract_signals(st, runtime.policy)} for cid, st in runtime.states.items()}
        return cls(
            treated=[r for r in rows if not r.get("control_group") and r.get("delivery_status") == "delivered"],
            control=[r for r in rows if r.get("control_group")],
            feedback=feedback, signals=signals, targets=target_signals(runtime.policy),
            settings=settings or load_settings(), decisions=list(decisions or []),
        )

    @property
    def prior_strength(self) -> float:
        return float(self.settings["prior_strength"])

    def global_rates(self) -> tuple[float, float]:
        conv = lambda rows: sum(bool(r.get("converted_within_14d")) for r in rows)
        return conv(self.treated) / len(self.treated), conv(self.control) / len(self.control)

    def compare(self, treated_rows, offer_id) -> Uplift:
        """Treated subgroup vs the offer's control group. Control rows were never sent, so the
        planned channel or tone cannot change their outcome; the offer-level control is the baseline."""
        mt, mc = self.global_rates()
        control = [r for r in self.control if r.get("offer_id") == offer_id]
        k = self.prior_strength
        arm = lambda rows, m: Arm(len(rows), sum(bool(r.get("converted_within_14d")) for r in rows), m, k)
        return uplift(arm(treated_rows, mt), arm(control, mc))

    def has_target(self, row) -> bool:
        return bool(self.signals.get(row["customer_id"], set()) & self.targets.get(row["offer_id"], set()))

    def harm(self, offer_id) -> dict:
        rows = [r for r in self.feedback if r.get("suggested_offer_id") == offer_id]
        upset = sum(r.get("dismiss_reason") == "customer_upset" or r.get("customer_reaction") == "annoyed" for r in rows)
        rate = upset / len(rows) if rows else None
        cfg = self.settings["harm"]
        return {"n_feedback": len(rows), "upset": upset, "rate": round(rate, 3) if rate is not None else None,
                "watch": bool(rows) and len(rows) >= cfg["min_feedback"] and rate >= cfg["watch_rate"]}

    def human(self, offer_id) -> dict:
        """Reviewer reactions to the engine's proposals for this offer (approve / override / reject)."""
        mine = [d for d in self.decisions if str(d.get("from_tuple", "")).startswith(offer_id + "|")]
        counts = defaultdict(int)
        reasons = defaultdict(int)
        for d in mine:
            counts[d.get("action")] += 1
            if d.get("action") in {"rejected", "overridden"} and d.get("reason"):
                reasons[d["reason"]] += 1
        return {"n": len(mine), **dict(sorted(counts.items())), "reasons": dict(sorted(reasons.items()))}
