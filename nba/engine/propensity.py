"""Deterministic empirical acceptance rates with explicit backoff and control evidence."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from nba.contracts import PSource
from nba.engine.config import EngineConfig, MissingDataError


@dataclass(frozen=True)
class Propensity:
    p_accept: float
    confidence: str
    source: PSource
    rate_treated: float
    uplift: float
    baseline_level: str
    k: float | None = None  # calibration factor applied (None = not calibrated)
    k_actual: int = 0  # buys observed in the offer × channel × tone group
    k_expected: float = 0.0  # buys the model expected for the same sends


class HistoryIndex:
    def __init__(self, history):
        self.treated = defaultdict(lambda: [0, 0])
        self.control = defaultdict(lambda: [0, 0])
        rows = history.to_dict("records") if hasattr(history, "to_dict") else history
        for r in rows:
            converted = int(bool(r.get("converted_within_14d")))
            if r.get("control_group"):
                for key in ((), (r.get("offer_id"),)):
                    self.control[key][0] += 1
                    self.control[key][1] += converted
            elif r.get("delivery_status") == "delivered":
                offer, channel, tone = r.get("offer_id"), r.get("channel"), r.get("tonality")
                for key in ((), (offer,), (offer, channel), (offer, channel, tone)):
                    self.treated[key][0] += 1
                    self.treated[key][1] += converted


def override_for(offer_id, channel, tone, cfg: EngineConfig):
    """A reviewer-approved p from a feedback-loop fix case (config/nba.yaml p_overrides), most specific first."""
    overrides = cfg.settings.get("p_overrides") or {}
    for key in (f"{offer_id}|{channel}|{tone}", f"{offer_id}|*|{tone}", f"{offer_id}|{channel}", offer_id):
        if key in overrides:
            return key, overrides[key]
    return None


def calibration_factor(actual: float, expected: float, settings: dict) -> float:
    """k = buys observed / buys the model expected for one offer × channel × tone group (whiteboard 27 Oct:
    p_new = p × k). Pulled toward 1 by `prior_buys` pseudo-buys, so a group with little evidence keeps k ≈ 1,
    and kept within [min_k, max_k]. Example: 3 bought where 10 were expected gives 0.3 with no prior, 0.53 with 5."""
    m = float(settings.get("prior_buys", 5))
    k = (actual + m) / (expected + m) if expected + m > 0 else 1.0
    return min(float(settings.get("max_k", 3.0)), max(float(settings.get("min_k", 0.2)), k))


def _index(history, cfg: EngineConfig) -> HistoryIndex:
    if isinstance(history, HistoryIndex):
        return history
    if history is cfg.history:
        if cfg._history_index is None:
            cfg._history_index = HistoryIndex(history)
        return cfg._history_index
    return HistoryIndex(history)


def p_accept(offer_id, channel, tone, history, cfg: EngineConfig, *, generic=False) -> Propensity:
    """The engine's chance to buy, then calibrated by its own track record for this offer × channel × tone
    (config/nba.yaml `calibration`). Catalog offers keep the catalog average (D1); reviewed overrides and the
    service assumption are not calibrated."""
    prop = _estimate(offer_id, channel, tone, history, cfg, generic=generic)
    cal = cfg.settings.get("calibration") or {}
    if generic or not cal.get("active") or prop.source.mode == "assumption":
        return prop
    index = _index(history, cfg)
    n, conv = index.treated[(offer_id, channel, tone)]
    if not n:
        return prop
    rate_p = prop.p_accept if cfg.p_mode == "rate" else _estimate(offer_id, channel, tone, index, cfg, mode="rate").p_accept
    expected = n * rate_p
    k = calibration_factor(conv, expected, cal)
    if cfg.p_mode == "rate":
        p = min(1.0, prop.p_accept * k)
    else:  # uplift: calibrate the buying rate, then subtract the control baseline again
        p = max(0.0, prop.rate_treated * k - (prop.source.baseline_control or 0.0))
    return replace(prop, p_accept=p, k=k, k_actual=conv, k_expected=expected,
                   source=prop.source.model_copy(update={"k": round(k, 4)}))


def _estimate(offer_id, channel, tone, history, cfg: EngineConfig, *, generic=False, mode=None) -> Propensity:
    found = override_for(offer_id, channel, tone, cfg)
    if found:
        key, o = found
        p = float(o["p"])
        return Propensity(p, "low", PSource(mode="assumption", level="assumption", n_treated=int(o.get("n_treated", 0)),
                                           conv_treated=int(o.get("conv_treated", 0)), n_control=int(o.get("n_control", 0)),
                                           conv_control=int(o.get("conv_control", 0))),
                          p, float(o.get("uplift", 0.0)), f"override:{key}:{o.get('case', '')}")
    if offer_id == "P-SV-01":
        p = float(cfg.settings["p_service_success"])
        return Propensity(p, "low", PSource(mode="assumption", level="assumption"), p, 0.0, "assumption")
    index = _index(history, cfg)
    ng, cg = index.treated[()]
    ncg, ccg = index.control[()]
    if not ng or not ncg:
        raise MissingDataError("Not enough data: nba_action_history treated/control observations")
    mode, n_min = mode or cfg.p_mode, int(cfg.settings["n_min"])
    key, level = (), "global"
    if not generic:
        for candidate_key, candidate_level in (
            ((offer_id, channel, tone), "offer_channel_tone"),
            ((offer_id, channel), "offer_channel"), ((offer_id,), "offer"),
        ):
            if index.treated[candidate_key][0] >= n_min:
                key, level = candidate_key, candidate_level
                break
    n, conv = index.treated[key]
    nc, cc = index.control[(offer_id,)] if level != "global" else (ncg, ccg)
    own_baseline = level != "global" and nc >= n_min
    baseline = cc / nc if own_baseline else ccg / ncg
    rate = conv / n
    uplift = max(0.0, rate - baseline)
    prior_strength = float(cfg.settings["rate_prior_strength"])
    shrunk = (conv + float(cfg.settings["rate_prior_mean"]) * prior_strength) / (n + prior_strength)
    p = (rate if level == "global" else shrunk) if mode == "rate" else uplift
    thresholds = cfg.settings["confidence"]
    confidence = "low"
    if level == "offer_channel_tone":
        confidence = "high" if n >= thresholds["high_min_n"] else "medium" if n >= thresholds["medium_min_n"] else "low"
    return Propensity(p, confidence, PSource(mode=mode, level=level, n_treated=n, conv_treated=conv,
                                           n_control=nc, conv_control=cc, baseline_control=baseline),
                      rate, uplift, "offer" if own_baseline else "global")


def personalise(p: Propensity, offer_id, customer_id, cfg: EngineConfig):
    """Look-alike chance for an offer that works (cfg.lookalike): the engine's chance at whatever level it
    chose (catalog-wide for a generic candidate) times the lift from similar customers. Reviewed overrides
    and assumptions win. -> (propensity, match or None)."""
    model = cfg.lookalike
    if model is None or p.source.mode == "assumption" or p.baseline_level.startswith("override:"):
        return p, None
    base = p.p_accept if cfg.p_mode == "rate" else p.rate_treated
    match = model.score(customer_id, offer_id, base)
    if match is None:
        return p, None
    value = match.p if cfg.p_mode == "rate" else max(0.0, match.p - (p.source.baseline_control or 0.0))
    return replace(p, p_accept=value, baseline_level=f"lookalike:{p.baseline_level}"), match
