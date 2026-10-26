"""Traffic light per pattern: green = record and continue, amber = keep collecting, red = fix case."""
from __future__ import annotations

from dataclasses import dataclass

from nba.learn.evidence import Evidence
from nba.learn.stats import Uplift

GREEN, AMBER, RED = "green", "amber", "red"


@dataclass(frozen=True)
class Pattern:
    key: str  # "P-MO-01" or "P-MO-01|sms"
    offer_id: str
    channel: str | None
    result: Uplift
    status: str
    why: str

    def as_dict(self) -> dict:
        return {"key": self.key, "offer_id": self.offer_id, "channel": self.channel, "status": self.status,
                "why": self.why, **self.result.as_dict()}


def classify(result: Uplift, settings: dict) -> tuple[str, str]:
    s = settings["status"]
    n, conv, p = result.treated.n, result.treated.conv, result.p_positive
    if n < s["min_treated"]:
        return AMBER, f"only {n} sends (< {s['min_treated']}): keep collecting"
    if n >= s["red_zero_response_n"] and conv == 0:
        return RED, f"0 conversions in {n} sends"
    if p <= s["red_p_positive"]:
        return RED, f"P(uplift > 0) = {p:.0%} vs control: probably no effect or harmful"
    if p >= s["green_p_positive"]:
        return GREEN, f"P(uplift > 0) = {p:.0%} vs control ({result.uplift:+.1%})"
    return AMBER, f"P(uplift > 0) = {p:.0%}: not clear yet"


def patterns(ev: Evidence) -> list[Pattern]:
    out = []
    for offer in sorted({r["offer_id"] for r in ev.treated}):
        rows = [r for r in ev.treated if r["offer_id"] == offer]
        groups = [(offer, None, rows)] + [(f"{offer}|{ch}", ch, [r for r in rows if r["channel"] == ch])
                                          for ch in sorted({r["channel"] for r in rows})]
        for key, channel, subset in groups:
            result = ev.compare(subset, offer)
            status, why = classify(result, ev.settings)
            out.append(Pattern(key, offer, channel, result, status, why))
    return out


def ledger_entries(found: list[Pattern], ev: Evidence, eval_time: str) -> list[dict]:
    """Green patterns become evidence attached to the offer, never new rules."""
    return [{"recorded_at": eval_time, "learn_version": ev.settings["learn_version"], "pattern": p.key,
             "status": p.status, "why": p.why, **p.result.as_dict()} for p in found if p.status == GREEN]
