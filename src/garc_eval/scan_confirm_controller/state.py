from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PublicState:
    remaining_budget_sec: float
    coverage_fraction: float = 0.0
    maximum_unobserved_gap_sec: float = 0.0
    scan_actions_completed: int = 0
    scan_time_spent_sec: float = 0.0
    frontier_size: int = 0
    frontier_score_min: float = 0.0
    frontier_score_median: float = 0.0
    frontier_score_max: float = 0.0
    frontier_score_quantiles: list[float] = field(default_factory=list)
    oldest_candidate_age_sec: float = 0.0
    newest_candidate_age_sec: float = 0.0
    novel_candidate_clusters_observed: int = 0
    confirmed_distinct_utility_count: int = 0
    recent_scan_novel_yield: float = 0.0
    recent_scan_zero_yield_streak: int = 0
    recent_confirm_success_rate: float = 0.0
    recent_confirm_new_utility_rate: float = 0.0
    recent_confirm_zero_yield_streak: int = 0
    estimated_scan_cost_sec: float = float("inf")
    estimated_confirm_cost_sec: float = float("inf")
    actions_completed: int = 0
    unused_budget_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PUBLIC_FIELDS = frozenset(PublicState(0.0).__dict__)


def validate_public_state(value: dict[str, Any]) -> None:
    extra = set(value) - PUBLIC_FIELDS
    missing = PUBLIC_FIELDS - set(value)
    if extra or missing:
        raise ValueError(f"public state schema mismatch: extra={extra}, missing={missing}")

