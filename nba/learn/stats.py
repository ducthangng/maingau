"""Beta–binomial posteriors for treated vs control, computed on a fixed grid (no sampling, deterministic)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

GRID = 100_000  # midpoint grid on (0, 1); a prior shape < 1 stays integrable at 0


@dataclass(frozen=True)
class Arm:
    n: int
    conv: int
    prior_mean: float
    prior_strength: float

    @property
    def a(self) -> float:
        return self.prior_mean * self.prior_strength + self.conv

    @property
    def b(self) -> float:
        return (1 - self.prior_mean) * self.prior_strength + self.n - self.conv

    @property
    def mean(self) -> float:
        return self.a / (self.a + self.b)

    @property
    def var(self) -> float:
        s = self.a + self.b
        return self.a * self.b / (s * s * (s + 1))


@lru_cache(maxsize=1)
def _x() -> np.ndarray:
    return (np.arange(GRID) + 0.5) / GRID


def _pmf(a: float, b: float) -> np.ndarray:
    x = _x()
    log = (a - 1) * np.log(x) + (b - 1) * np.log1p(-x)
    p = np.exp(log - log.max())
    return p / p.sum()


def prob_greater(treated: Arm, control: Arm) -> float:
    """P(rate_treated > rate_control) under independent Beta posteriors."""
    return float(np.dot(_pmf(treated.a, treated.b), np.cumsum(_pmf(control.a, control.b))))


@dataclass(frozen=True)
class Uplift:
    treated: Arm
    control: Arm
    uplift: float  # posterior mean of rate_treated − rate_control
    low: float  # approximate 90% interval (normal approximation of the difference)
    high: float
    p_positive: float

    def as_dict(self) -> dict:
        r = lambda v: round(v, 4)
        return {"n_treated": self.treated.n, "conv_treated": self.treated.conv, "rate_treated": r(self.treated.mean),
                "n_control": self.control.n, "conv_control": self.control.conv, "rate_control": r(self.control.mean),
                "uplift": r(self.uplift), "uplift_90": [r(self.low), r(self.high)], "p_positive": round(self.p_positive, 3)}


def uplift(treated: Arm, control: Arm) -> Uplift:
    diff = treated.mean - control.mean
    sd = math.sqrt(treated.var + control.var)
    return Uplift(treated, control, diff, diff - 1.645 * sd, diff + 1.645 * sd, prob_greater(treated, control))
