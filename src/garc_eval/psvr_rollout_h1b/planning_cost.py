"""Planning time is an SMDP horizon transition."""
from __future__ import annotations
from dataclasses import dataclass
from .types import VisibleDecisionState

@dataclass(frozen=True)
class PlanningTransition:
    admitted: bool
    post_state: VisibleDecisionState
    reason: str

def consume_planning_time(state: VisibleDecisionState, ticks: int) -> PlanningTransition:
    if ticks < 0: raise ValueError("planning ticks must be nonnegative")
    if state.remaining_ticks <= ticks:
        return PlanningTransition(False, state, "INSUFFICIENT_REMAINING_TIME")
    return PlanningTransition(True, state.with_remaining(state.remaining_ticks - ticks), "PLANNED")
