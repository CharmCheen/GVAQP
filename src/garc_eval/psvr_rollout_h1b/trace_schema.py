"""Visible-only planner trace; evaluator reference data has a separate schema."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from .types import ActionView

@dataclass(frozen=True)
class PlannerTrace:
    visible_history_hash: str
    candidate_actions: tuple[str, ...]
    base_action: str
    planning_admitted: bool
    planning_budget: int
    samples_used: int
    paired_advantages: dict[str, float]
    lcbs: dict[str, float]
    bias_margin: float
    overhead_margin: int
    selected_action: str
    fallback_reason: str | None
    planning_time: int
    post_planning_remaining_time: int
    post_planning_feasible: bool

    def to_dict(self) -> dict: return asdict(self)
