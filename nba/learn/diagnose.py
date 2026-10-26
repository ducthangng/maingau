"""Find which layer broke for a red pattern, and draft fix options for a human to choose from.

Each split compares subgroups of the treated rows against the same offer-level control group.
The split whose subgroups differ most in P(uplift > 0) names the layer. Options are p overrides,
because the engine already applies every hard rule before p is used: an override can lower or
raise an estimate, never unblock a tuple.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nba.learn.evidence import Evidence
from nba.learn.health import RED, Pattern
from nba.learn.stats import Uplift

LAYERS = {
    "target_signal": "targeting (signal → need)",
    "channel": "channel",
    "tone": "tone",
    "content_variant": "content",
}


@dataclass(frozen=True)
class Subgroup:
    label: str
    result: Uplift

    def as_dict(self) -> dict:
        return {"label": self.label, **self.result.as_dict()}


@dataclass(frozen=True)
class Split:
    dimension: str
    subgroups: list[Subgroup]
    contrast: float  # max − min P(uplift > 0) among usable subgroups

    def as_dict(self) -> dict:
        return {"dimension": self.dimension, "layer": LAYERS[self.dimension], "contrast": round(self.contrast, 3),
                "subgroups": [s.as_dict() for s in self.subgroups]}


@dataclass
class Option:
    id: str
    title: str
    rationale: str
    overrides: dict[str, dict] = field(default_factory=dict)  # empty = no engine change (KG or template work)
    needs_rewrite: str | None = None  # which file a human + AI would rewrite instead

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "rationale": self.rationale, "overrides": self.overrides,
                "needs_rewrite": self.needs_rewrite}


@dataclass
class Case:
    id: str
    pattern: Pattern
    layer: str
    finding: str
    splits: list[Split]
    options: list[Option]
    harm: dict
    human: dict
    backtests: dict[str, dict] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "pattern": self.pattern.as_dict(), "layer": self.layer, "finding": self.finding,
                "splits": [s.as_dict() for s in self.splits], "options": [o.as_dict() for o in self.options],
                "harm": self.harm, "human": self.human, "backtests": self.backtests}


def case_id(key: str) -> str:
    return "FIX-" + key.replace("|", "-")


def _label(ev: Evidence, dimension: str, row: dict) -> str:
    if dimension == "target_signal":
        return "with target signal" if ev.has_target(row) else "without target signal"
    if dimension == "content_variant":
        return f"variant {row['content_variant']}"
    return str(row[{"channel": "channel", "tone": "tonality"}[dimension]])


def splits(ev: Evidence, offer_id: str, rows: list[dict], dimensions) -> list[Split]:
    minimum = ev.settings["diagnosis"]["min_subgroup"]
    out = []
    for dim in dimensions:
        labels = sorted({_label(ev, dim, r) for r in rows})
        subs = [Subgroup(lab, ev.compare([r for r in rows if _label(ev, dim, r) == lab], offer_id)) for lab in labels]
        usable = [s.result.p_positive for s in subs if s.result.treated.n >= minimum]
        contrast = max(usable) - min(usable) if len(usable) >= 2 else 0.0
        out.append(Split(dim, subs, contrast))
    return out


def _payload(result: Uplift, p: float, basis: str) -> dict:
    return {"p": round(p, 4), "basis": basis, "n_treated": result.treated.n, "conv_treated": result.treated.conv,
            "n_control": result.control.n, "conv_control": result.control.conv, "uplift": round(result.uplift, 4)}


def _estimate(result: Uplift, mode: str) -> float:
    """The p the engine would use for this evidence: shrunk treated rate (rate) or uplift floored at 0."""
    return result.treated.mean if mode == "rate" else max(0.0, result.uplift)


def diagnose(ev: Evidence, pattern: Pattern, policy, p_mode: str) -> Case:
    offer = pattern.offer_id
    rows = [r for r in ev.treated if r["offer_id"] == offer and (pattern.channel is None or r["channel"] == pattern.channel)]
    dims = [d for d in LAYERS if (d != "target_signal" or ev.targets.get(offer)) and (d != "channel" or pattern.channel is None)]
    found = splits(ev, offer, rows, dims)
    minimum = ev.settings["diagnosis"]["min_subgroup"]
    best = max(found, key=lambda s: s.contrast, default=None)
    explained = best if best and best.contrast >= ev.settings["diagnosis"]["min_contrast"] else None
    cid = case_id(pattern.key)
    suppress = Option("S", f"Stop {pattern.key}", "Set p to 0 so the tuple never has a positive ΔCLV and drops out of ranking.",
                      {pattern.key: _payload(pattern.result, 0.0, "suppressed by fix case")})
    keep = Option("K", "Keep and measure", "No engine change; keep the holdout and re-run the loop when more outcomes arrive.")
    options: list[Option] = []

    if explained is None:
        layer = "offer (no split explains it)"
        finding = (f"{pattern.key}: {pattern.why}. No subgroup (target signal, channel, tone, content) behaves "
                   "clearly differently, so the offer itself or its p estimate is the problem.")
        options = [suppress, keep]
    else:
        layer = LAYERS[explained.dimension]
        usable = [s for s in explained.subgroups if s.result.treated.n >= minimum]
        good = max(usable, key=lambda s: s.result.p_positive)
        bad = min(usable, key=lambda s: s.result.p_positive)
        finding = (f"{pattern.key}: {pattern.why}. The {layer} layer explains it: '{good.label}' "
                   f"P(uplift > 0) = {good.result.p_positive:.0%} ({good.result.treated.conv}/{good.result.treated.n}) vs "
                   f"'{bad.label}' {bad.result.p_positive:.0%} ({bad.result.treated.conv}/{bad.result.treated.n}).")
        if explained.dimension == "target_signal":
            matched = next((s for s in explained.subgroups if s.label == "with target signal"), None)
            share = matched.result.treated.n if matched else 0
            targets = ", ".join(sorted(ev.targets[offer]))
            finding += (f" Only {share} of {len(rows)} legacy sends went to customers with the target signal ({targets}).")
            if matched and not policy.offers[offer].generic:
                finding += (" The engine already sends this offer only with that signal, so the offer-level history "
                            "measures the legacy engine's targeting, not this engine's.")
                options.append(Option(
                    "A", f"Value {offer} with signal-matched evidence only",
                    f"p from the {matched.result.treated.n} signal-matched sends ({p_mode} mode), shrunk toward the catalog "
                    "prior. Little data: low confidence, label it as exploration and keep the holdout.",
                    {offer: _payload(matched.result, _estimate(matched.result, p_mode), "signal-matched sends only")}))
            else:
                options.append(Option(
                    "A", f"Make {offer} signal-only",
                    f"Stop generic sends of {offer}; only customers with {targets} get it.", {},
                    needs_rewrite="kg/policy.yaml (offers.generic) and config/kg.yaml (generic.offers)"))
        elif explained.dimension in {"channel", "tone"}:
            losers = [s for s in usable if s.result.p_positive < 0.5]
            key = (lambda s: f"{offer}|{s.label}") if explained.dimension == "channel" else (lambda s: f"{offer}|*|{s.label}")
            options.append(Option(
                "A", f"Stop {offer} for {', '.join(s.label for s in losers)}",
                f"Keep the offer where it works ('{good.label}'); set p to 0 only for the {layer} subgroups with "
                "P(uplift > 0) < 50%.",
                {key(s): _payload(s.result, 0.0, f"{layer} '{s.label}' suppressed") for s in losers}))
        elif explained.dimension == "content_variant":
            options.append(Option(
                "A", f"Rewrite the {offer} content after '{good.label}'",
                f"The message, not the targeting, differs: '{good.label}' works better. A human with AI rewrites the "
                "German template and the next cycle measures it.", {},
                needs_rewrite=f"templates/de/{offer}.yaml"))
        options += [suppress, keep]
    return Case(cid, pattern, layer, finding, found, options, ev.harm(offer), ev.human(offer))


def cases(ev: Evidence, found: list[Pattern], policy, p_mode: str) -> list[Case]:
    """One case per red offer; a red channel gets its own case only when its offer is not red."""
    red_offers = {p.offer_id for p in found if p.status == RED and p.channel is None}
    targets = [p for p in found if p.status == RED and (p.channel is None or p.offer_id not in red_offers)]
    return [diagnose(ev, p, policy, p_mode) for p in targets]
