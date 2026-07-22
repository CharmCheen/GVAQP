from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from ..models import AtomicUnit, MaterializedEvent, OracleObservation, PlannerAction


class BasePlanner(ABC):
    """Planner contract intentionally excludes latent GT and oracle internals."""

    name = "base"

    @abstractmethod
    def choose_action(
        self,
        units: Sequence[AtomicUnit],
        observations: Sequence[OracleObservation],
        events: Sequence[MaterializedEvent],
        remaining_budget: float,
    ) -> PlannerAction | None: ...

    def _action_id(self, observations: Sequence[OracleObservation]) -> str:
        return f"{self.name}_a{len(observations):03d}"
