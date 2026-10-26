"""Look-alike learning: an offer that works (🟢 against its control group) learns which customers it
works for, and the engine uses that for customers who look like them.

Good outcome = the send converted within 14 days with a positive conversion value (CLV went up).
For a customer and a 🟢 offer, the k most similar customers who were sent that offer vote with their
similarity. Their buying rate, shrunk toward the rate of all recipients so a few peers cannot swing it
far, is compared with that rate; the engine's own chance is scaled by the ratio (the lift):

    peer_rate = (Σ similarity·good + m · pool_rate) / (Σ similarity + m)
    p = p_offer · min(peer_rate / pool_rate, max_ratio)

So the look-alike moves chances between customers; on average it neither raises nor lowers them.

The customer's own past send never counts for itself. Similarity is measured on the snapshot at
evaluation time; it describes who bought, it is not a causal uplift claim. Missing values are left
out of the distance for that pair, never filled in. Hard rules still run before ranking.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd

from nba.engine.config import fingerprint

LABELS = {
    "age": "age", "household_size": "household size", "tenure_years": "years as customer",
    "active_business_lines": "active product lines", "annual_margin_eur": "annual margin €", "clv_eur": "CLV €",
    "churn_prob_12m": "churn risk", "portal_sessions_90d": "portal sessions (90 d)",
    "portal_minutes_avg": "minutes per portal session", "tickets_12m": "service tickets (12 m)",
    "csat_avg": "service rating (1-5)", "consumption_kwh": "electricity use kWh/yr",
}


def customer_features(tables: dict, pop: pd.DataFrame, eval_time) -> pd.DataFrame:
    """One row per customer, the comparison columns of LABELS plus city for display."""
    df = pd.DataFrame(index=pop.index)
    df["city"] = pop["city"]
    df["age"] = eval_time.year - pd.to_numeric(pop["birth_year"], errors="coerce")
    for col in ("household_size", "tenure_years", "active_business_lines", "annual_margin_eur", "clv_eur",
                "churn_prob_12m", "portal_sessions_90d"):
        df[col] = pd.to_numeric(pop[col], errors="coerce")
    ps = tables["portal_sessions"]
    at = pd.to_datetime(ps["session_start"], errors="coerce")
    ps = ps[(at <= eval_time) & (at > eval_time - timedelta(days=90))]
    df["portal_minutes_avg"] = pd.to_numeric(ps["duration_s"], errors="coerce").groupby(ps["customer_id"]).mean() / 60
    si = tables["service_interactions"]
    at = pd.to_datetime(si["created_at"], errors="coerce")
    si = si[(at <= eval_time) & (at > eval_time - timedelta(days=365))]
    df["tickets_12m"] = si.groupby("customer_id").size().reindex(df.index).fillna(0)  # no ticket is a count of 0
    df["csat_avg"] = pd.to_numeric(si["csat_1to5"], errors="coerce").groupby(si["customer_id"]).mean()
    ec = tables["energy_contracts"]
    ec = ec[(ec["commodity"] == "electricity") & (ec["status"] == "active")]
    df["consumption_kwh"] = pd.to_numeric(ec["annual_consumption_kwh"], errors="coerce").groupby(ec["customer_id"]).sum(min_count=1)
    return df


@dataclass(frozen=True)
class Peer:
    customer_id: str
    similarity: float
    good: bool
    value_eur: float | None
    channel: str | None


@dataclass(frozen=True)
class Match:
    offer_id: str
    p: float
    p_offer: float
    lift: float
    pool_rate: float
    peers: tuple[Peer, ...]

    @property
    def n_good(self) -> int:
        return sum(p.good for p in self.peers)

    def evidence(self, show: int = 3) -> str:
        best = [f"{p.customer_id} {p.similarity:.0%}" for p in self.peers if p.good][:show]
        return (f"Look-alike: {self.n_good} of the {len(self.peers)} most similar customers who got this offer bought "
                f"({', '.join(best) or 'none'}) vs {self.pool_rate:.1%} of all recipients; chance ×{self.lift:.2f} = "
                f"{self.p:.1%} instead of {self.p_offer:.1%}; describes who bought, not causal uplift")


@dataclass
class Lookalike:
    features: pd.DataFrame
    weights: dict[str, float]
    settings: dict
    offers: dict[str, dict] = field(default_factory=dict)  # 🟢 offer -> {customer: (good, value, channel)}
    profiled: frozenset = frozenset()  # profiling consent granted: the only customers scored or used as peers
    _z: pd.DataFrame | None = field(default=None, repr=False)

    def __post_init__(self):
        cols = list(self.weights)
        x = self.features[cols].astype(float)
        med = x.median()
        scale = (x.quantile(0.75) - x.quantile(0.25)) / 1.349
        scale = scale.where(scale > 0, x.std()).where(lambda s: s > 0, 1.0)
        self._z = (x - med) / scale

    @property
    def version(self) -> str:
        return fingerprint([self.weights, self.settings, self.offers, sorted(self.profiled)])

    def similarity(self, a: str, b: str) -> float:
        return float(self._sims(a, [b])[0])

    def _sims(self, cid: str, others: list[str]) -> np.ndarray:
        w = np.array([self.weights[c] for c in self._z.columns])
        za, zb = self._z.loc[cid].to_numpy(), self._z.loc[others].to_numpy()
        present = ~np.isnan(za) & ~np.isnan(zb)
        diff = np.where(present, za - zb, 0.0)
        wsum = (present * w).sum(axis=1)
        d2 = np.divide((diff ** 2 * w).sum(axis=1), wsum, out=np.full(len(others), np.inf), where=wsum > 0)
        return np.exp(-d2 / 2)

    def nearest(self, cid: str, pool, k: int) -> list[tuple[str, float]]:
        others = sorted(c for c in pool if c != cid and c in self._z.index)
        if not others or cid not in self._z.index:
            return []
        sims = self._sims(cid, others)
        order = sorted(range(len(others)), key=lambda i: (-sims[i], others[i]))[:k]
        return [(others[i], round(float(sims[i]), 4)) for i in order]

    def score(self, cid: str, offer_id: str, p_offer: float) -> Match | None:
        outcomes = self.offers.get(offer_id)
        if not outcomes or cid not in self.profiled:
            return None
        pool = [c for c in outcomes if c in self.profiled]
        pool_rate = sum(outcomes[c][0] for c in pool) / len(pool) if pool else 0.0
        found = self.nearest(cid, pool, int(self.settings["neighbours"]))
        if not found or pool_rate == 0:
            return None
        peers = tuple(Peer(c, s, *outcomes[c]) for c, s in found)
        m = float(self.settings["prior_strength"])
        peer_rate = (sum(p.similarity for p in peers if p.good) + m * pool_rate) / (sum(p.similarity for p in peers) + m)
        lift = min(peer_rate / pool_rate, float(self.settings["max_ratio"]))
        return Match(offer_id, min(1.0, p_offer * lift), p_offer, round(lift, 4), pool_rate, peers)

    def profile(self, offer_id: str) -> list[dict]:
        """What the buyers of a 🟢 offer have in common: their median vs the other recipients', per feature."""
        outcomes = self.offers.get(offer_id, {})
        good = [c for c, o in outcomes.items() if o[0] and c in self.profiled]
        rest = [c for c, o in outcomes.items() if not o[0] and c in self.profiled]
        rows = []
        for col in self.weights:
            g, r = self.features.loc[good, col].median(), self.features.loc[rest, col].median()
            zg, zr = self._z.loc[good, col].median(), self._z.loc[rest, col].median()
            if not (math.isnan(zg) or math.isnan(zr)):
                rows.append({"feature": col, "label": LABELS[col], "buyers": round(float(g), 2),
                             "others": round(float(r), 2), "gap": round(float(zg - zr), 2)})
        return sorted(rows, key=lambda r: (-abs(r["gap"]), r["feature"]))


def outcomes_by_offer(history: list[dict], offers) -> dict[str, dict]:
    """Treated, delivered sends per offer -> customer: (good, value, channel). Good if any send converted with value > 0."""
    out: dict[str, dict] = {o: {} for o in offers}
    for r in sorted(history, key=lambda r: (str(r.get("decided_at")), str(r.get("action_id")))):
        if r.get("offer_id") not in out or r.get("control_group") or r.get("delivery_status") != "delivered":
            continue
        value = r.get("conversion_value_eur")
        value = float(value) if value is not None and not (isinstance(value, float) and math.isnan(value)) else None
        good = bool(r.get("converted_within_14d")) and (value or 0) > 0
        prev = out[r["offer_id"]].get(r["customer_id"])
        if prev is None or (good and not prev[0]):
            out[r["offer_id"]][r["customer_id"]] = (good, value if good else None, r.get("channel"))
    return out


def green_offers(runtime, learn_settings: dict) -> list[str]:
    from nba.learn.evidence import Evidence
    from nba.learn.health import GREEN, patterns

    return sorted(p.offer_id for p in patterns(Evidence.from_runtime(runtime, learn_settings))
                  if p.channel is None and p.status == GREEN)


def fit(runtime, learn_settings: dict) -> Lookalike | None:
    """The look-alike model for a runtime, or None when switched off. Refit from the history on every load,
    so new outcomes (and offers turning 🟢) are learned without a code change. Comparing customers is
    profiling: only customers with profiling consent are scored or serve as peers."""
    from nba.kg.rules import is_profiled

    s = learn_settings.get("lookalike") or {}
    if not s.get("active"):
        return None
    if int(s["neighbours"]) < 1 or float(s["prior_strength"]) < 0 or float(s["max_ratio"]) < 1:
        raise ValueError("lookalike: neighbours >= 1, prior_strength >= 0 and max_ratio >= 1")
    t = next(iter(runtime.states.values())).eval_time
    feats = customer_features(runtime.tables, runtime.pop, t)
    offers = green_offers(runtime, learn_settings)
    profiled = frozenset(cid for cid, st in runtime.states.items() if is_profiled(st, runtime.policy))
    weights = {k: float(v) for k, v in s["features"].items() if float(v) > 0}
    return Lookalike(feats, weights, s, outcomes_by_offer(runtime.cfg.history, offers), profiled)


def attach(runtime, learn_settings: dict):
    runtime.cfg.lookalike = fit(runtime, learn_settings)
    runtime._cards.clear()
    return runtime


def summary(model: Lookalike | None, names=None) -> dict:
    """What the loop learned per 🟢 offer: who bought, how they differ, how many customers move up or down."""
    if model is None:
        return {"active": False, "offers": {}}
    out = {}
    for oid, outcomes in sorted(model.offers.items()):
        lifts = [m.lift for c in sorted(model.profiled) if (m := model.score(c, oid, 1.0))]
        pool = [c for c in outcomes if c in model.profiled]
        out[oid] = {"name": names.offer_or_none(oid) if names else oid, "recipients": len(pool),
                    "buyers": sum(outcomes[c][0] for c in pool), "profile": model.profile(oid)[:5],
                    "customers_scored": len(lifts), "more_likely": sum(x > 1.2 for x in lifts),
                    "less_likely": sum(x < 0.8 for x in lifts)}
    return {"active": True, "version": model.version, "neighbours": model.settings["neighbours"], "offers": out}


def summary_markdown(found: dict) -> str:
    if not found["active"]:
        return "## Learned from similar customers\n\nSwitched off (config/learn.yaml › lookalike › active).\n"
    lines = ["## Learned from similar customers", "",
             f"Every 🟢 offer learns who bought it; customers who look like the buyers get a higher chance, customers "
             f"who look like the non-buyers a lower one ({found['neighbours']} most similar recipients compared). "
             "Customers without profiling consent are left out.", ""]
    for oid, o in found["offers"].items():
        lines += [f"### {o['name']} ({oid})", "",
                  f"{o['buyers']} of {o['recipients']} recipients bought. Of {o['customers_scored']} customers scored, "
                  f"{o['more_likely']} are clearly more likely (×1.2 or more) and {o['less_likely']} clearly less likely (×0.8 or less).", "",
                  "| Buyers differ in | Buyers (median) | Others (median) |", "|---|---|---|"]
        lines += [f"| {r['label']} | {r['buyers']:,.2f} | {r['others']:,.2f} |" for r in o["profile"]]
        lines.append("")
    return "\n".join(lines)
