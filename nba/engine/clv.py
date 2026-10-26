"""Present value of ten annual net margins (workbook clv_method)."""
from __future__ import annotations

import math


def clv(margin: float, cost: float, churn: float, r: float = 0.06, years: int = 10) -> float:
    if not all(math.isfinite(x) for x in (margin, cost, churn, r)):
        raise ValueError("CLV inputs must be finite")
    if not 0 <= churn <= 1 or r <= -1 or not isinstance(years, int) or years < 1:
        raise ValueError("Invalid churn, discount rate or horizon")
    return math.fsum((margin - cost) * (1 - churn) ** (t - 1) / (1 + r) ** t
                     for t in range(1, years + 1))
