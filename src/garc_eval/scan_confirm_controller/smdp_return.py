from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SMDPReturn:
    """Lexicographic hard-deadline return for one conditioned rollout."""

    final_distinct_events: int
    anytime_auc: float
    elapsed_sec: float
    completed_actions: int
    exact: bool
    stable: bool
    trajectory: tuple[dict[str, Any], ...]
    expanded_states: int = 0
    pruned_states: int = 0
    invalid_transitions: int = 0

    @property
    def objective_key(self) -> tuple[int, float]:
        return self.final_distinct_events, self.anytime_auc
