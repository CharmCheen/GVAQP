from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class CausalCostEstimator:
    fallback_samples: list[float]
    quantile: float = 0.90
    constant_median: bool = False
    observed: list[float] = field(default_factory=list)

    def estimate(self) -> float:
        source = self.fallback_samples if self.constant_median or not self.observed else self.observed
        q = 0.5 if self.constant_median else self.quantile
        value = float(np.quantile(np.asarray(source, dtype=float), q))
        return value if math.isfinite(value) and value > 0 else float("inf")

    def observe(self, value: float) -> None:
        if math.isfinite(value) and value > 0:
            self.observed.append(float(value))

