"""Evaluator-only diagnostics from already-separated action values."""
from __future__ import annotations
def incorrect_override(selected_value: float, base_value: float, overridden: bool) -> bool:
    return overridden and selected_value < base_value
def paired_regret(exact_value: float, selected_value: float) -> float:
    return max(0.0, exact_value - selected_value)
