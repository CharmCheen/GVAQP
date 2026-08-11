from __future__ import annotations

import math
from dataclasses import dataclass, field


def linear_quantile(values: list[float], quantile: float) -> float:
    """NumPy-default-compatible linear quantile for a one-dimensional sample."""
    if not values:
        return float("inf")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


@dataclass
class CausalCostEstimator:
    """Frozen causal cost estimate: q90 of completed costs, global fallback first."""

    fallback_samples: list[float]
    quantile: float = 0.90
    observed: list[float] = field(default_factory=list)

    def estimate(self) -> float:
        source = self.observed if self.observed else self.fallback_samples
        value = linear_quantile(source, self.quantile)
        return value if math.isfinite(value) and value > 0 else float("inf")

    def observe(self, value: float) -> None:
        if math.isfinite(value) and value > 0:
            self.observed.append(float(value))


def action_fits(estimated_cost_sec: float, remaining_budget_sec: float) -> bool:
    """Frozen admission rule: admit iff the estimated complete action fits."""
    return math.isfinite(estimated_cost_sec) and estimated_cost_sec >= 0 and estimated_cost_sec <= remaining_budget_sec
