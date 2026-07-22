"""Frozen normal paired LCB; no multiple-comparison correction is specified."""
from __future__ import annotations
from .advantage import AdvantageEstimate

Z_95 = 1.96

def paired_lcb_95(estimate: AdvantageEstimate) -> float:
    if len(estimate.samples) == 1 or estimate.sample_sd == 0.0:
        return estimate.mean
    return estimate.mean - Z_95 * estimate.sample_sd / len(estimate.samples) ** 0.5
