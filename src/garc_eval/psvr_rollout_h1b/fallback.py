"""Frozen fallback selection; base policy is recomputed after planning."""
from __future__ import annotations
from dataclasses import dataclass
from .types import ActionView

@dataclass(frozen=True)
class OverrideDecision:
    selected: ActionView
    fallback_reason: str | None
    overridden: bool

def select_with_fallback(base: ActionView, alternatives: dict[ActionView, float], threshold: float, mode: str) -> OverrideDecision:
    ranked = sorted(alternatives.items(), key=lambda item: (-item[1], item[0].identifier))
    if not ranked: return OverrideDecision(base, "NO_ALTERNATIVE", False)
    action, value = ranked[0]
    if mode == "UNGATED" and value > 0: return OverrideDecision(action, None, action != base)
    if mode == "UNGATED": return OverrideDecision(base, "BASE_NONINFERIOR", False)
    if mode == "POINT" and value > 0: return OverrideDecision(action, None, action != base)
    if mode == "LCB" and value > threshold: return OverrideDecision(action, None, action != base)
    return OverrideDecision(base, "THRESHOLD_NOT_STRICTLY_EXCEEDED", False)
