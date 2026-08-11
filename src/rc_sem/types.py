from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Action(str, Enum):
    SCAN = "SCAN"
    VERIFY = "VERIFY"
    STOP = "STOP"


class EventStatus(str, Enum):
    VERIFIED = "VERIFIED_EVENT"
    PROBABLE = "PROBABLE_EVENT"
    HYPOTHESIS = "EVENT_HYPOTHESIS"


@dataclass(frozen=True)
class EventHypothesis:
    event_id: str
    start_time: float
    end_time: float
    probability_mean: float
    probability_uncertainty: float
    source_candidate_ids: tuple[str, ...] = field(default_factory=tuple)
    authoritative_positive_support: int = 0
    boundary_uncertainty_sec: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be nonempty")
        if not math.isfinite(self.start_time) or not math.isfinite(self.end_time):
            raise ValueError("event boundaries must be finite")
        if self.start_time < 0 or self.end_time <= self.start_time:
            raise ValueError("event boundaries must have positive duration")
        if not 0.0 <= self.probability_mean <= 1.0:
            raise ValueError("probability_mean must be in [0, 1]")
        if not math.isfinite(self.probability_uncertainty) or self.probability_uncertainty < 0:
            raise ValueError("probability_uncertainty must be finite and nonnegative")
        if self.authoritative_positive_support < 0:
            raise ValueError("authoritative_positive_support must be nonnegative")
        if not math.isfinite(self.boundary_uncertainty_sec) or self.boundary_uncertainty_sec < 0:
            raise ValueError("boundary_uncertainty_sec must be finite and nonnegative")


@dataclass(frozen=True)
class PublishedEvent:
    event_id: str
    start_time: float
    end_time: float
    status: EventStatus
    probability_mean: float
    probability_lower_bound: float
    probability_uncertainty: float
    boundary_uncertainty_sec: float
    source_candidate_ids: tuple[str, ...]
    authoritative_positive_support: int
    materialized_at_sec: float
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class PublicationSnapshot:
    events: tuple[PublishedEvent, ...]
    verified_count: int
    probable_count: int
    hypothesis_count: int
    probable_precision_lower_bound: float
    risk_adjusted_utility: float


@dataclass(frozen=True)
class ActionOption:
    action: Action
    target_id: str
    cost_upper_sec: float
    value_mean: float
    value_uncertainty: float
    can_directly_materialize: bool = False

    def __post_init__(self) -> None:
        if self.action is Action.STOP:
            raise ValueError("STOP is implicit and must not be an ActionOption")
        if not self.target_id:
            raise ValueError("target_id must be nonempty")
        for name, value in (
            ("cost_upper_sec", self.cost_upper_sec),
            ("value_mean", self.value_mean),
            ("value_uncertainty", self.value_uncertainty),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.cost_upper_sec <= 0:
            raise ValueError("cost_upper_sec must be positive")
        if self.value_uncertainty < 0:
            raise ValueError("value_uncertainty must be nonnegative")


@dataclass(frozen=True)
class ControllerState:
    elapsed_sec: float
    deadline_sec: float
    frontier_size: int
    publication: PublicationSnapshot

    def __post_init__(self) -> None:
        if not math.isfinite(self.elapsed_sec) or self.elapsed_sec < 0:
            raise ValueError("elapsed_sec must be finite and nonnegative")
        if not math.isfinite(self.deadline_sec) or self.deadline_sec <= 0:
            raise ValueError("deadline_sec must be finite and positive")
        if self.frontier_size < 0:
            raise ValueError("frontier_size must be nonnegative")

    @property
    def remaining_sec(self) -> float:
        return max(0.0, self.deadline_sec - self.elapsed_sec)


@dataclass(frozen=True)
class Decision:
    action: Action
    target_id: str | None
    reason: str
    safe_actions: tuple[Action, ...]
    delta_mean: float | None = None
    delta_uncertainty: float | None = None


FORBIDDEN_RUNTIME_FIELDS = frozenset(
    {
        "full_grid_labels",
        "reference_events",
        "unverified_oracle_labels",
        "future_action_costs",
        "future_k3_results",
        "final_recall",
        "final_precision",
    }
)


def validate_runtime_payload(payload: Mapping[str, Any]) -> None:
    leaked: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            leaked.update(FORBIDDEN_RUNTIME_FIELDS.intersection(value))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                visit(nested)

    visit(payload)
    if leaked:
        raise ValueError(f"evaluator-only fields leaked into runtime payload: {sorted(leaked)}")
