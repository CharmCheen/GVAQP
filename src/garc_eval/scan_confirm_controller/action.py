from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Action(str, Enum):
    SCAN = "SCAN"
    CONFIRM = "CONFIRM"
    STOP = "STOP"


@dataclass(frozen=True)
class ActionResult:
    action: Action
    estimated_cost_sec: float
    actual_cost_sec: float
    completed: bool
    new_candidate_clusters: int = 0
    new_distinct_utility: int = 0
    score_bucket: str | None = None
    coverage_bucket: str | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["action"] = self.action.value
        return value

