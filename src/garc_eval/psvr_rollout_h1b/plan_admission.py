"""Visible-only post-planning override admission statuses."""
from __future__ import annotations
from dataclasses import dataclass
from .types import ActionView, VisibleDecisionState

@dataclass(frozen=True)
class Admission:
    status: str  # PLAN, SKIP_TO_PI0, STOP
    base_action: ActionView | None

def planning_admission(state: VisibleDecisionState, planning_ticks: int, base_action: ActionView | None) -> Admission:
    if base_action is not None and base_action not in state.legal_actions: raise ValueError("base action must be currently legal")
    if base_action is None: return Admission("STOP", None)
    if state.remaining_ticks <= planning_ticks:
        return Admission("STOP" if base_action is None else "SKIP_TO_PI0", base_action)
    return Admission("PLAN", base_action)
