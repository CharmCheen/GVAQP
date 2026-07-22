"""Implementation-only invariant checks."""
from __future__ import annotations
from .trace_schema import PlannerTrace
def assert_trace_safe(trace: PlannerTrace) -> None:
    forbidden=("exact_action", "exact_q", "future_truth", "execution_random_tape", "latent_world")
    rendered=str(trace.to_dict())
    if any(token in rendered for token in forbidden): raise AssertionError("forbidden evaluator data in planner trace")
    if trace.post_planning_remaining_time < 0 or trace.planning_time < 0: raise AssertionError("invalid planning horizon")
