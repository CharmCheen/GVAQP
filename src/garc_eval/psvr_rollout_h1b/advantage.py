"""Paired advantage accounting for fixed CRN samples."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class AdvantageEstimate:
    samples: tuple[float, ...]
    mean: float
    sample_sd: float

def paired_advantage(action_returns: tuple[float, ...], base_returns: tuple[float, ...]) -> AdvantageEstimate:
    if not action_returns or len(action_returns) != len(base_returns):
        raise ValueError("paired samples must be nonempty and aligned")
    samples = tuple(a - b for a, b in zip(action_returns, base_returns))
    mean = sum(samples) / len(samples)
    variance = 0.0 if len(samples) == 1 else sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)
    return AdvantageEstimate(samples, mean, sqrt(variance))
