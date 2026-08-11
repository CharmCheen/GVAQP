from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .controller import ControllerConfig, RCSEMController
from .materialization import MaterializationConfig, RiskControlledMaterializer
from .types import (
    ActionOption,
    ControllerState,
    Decision,
    EventHypothesis,
    PublicationSnapshot,
)


@dataclass(frozen=True)
class RCSEMConfig:
    materialization: MaterializationConfig = field(default_factory=MaterializationConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)


@dataclass(frozen=True)
class RCSEMStep:
    publication: PublicationSnapshot
    decision: Decision


class RCSEMAlgorithm:
    """End-to-end pure decision step over causal runtime inputs.

    Event posterior inference and action-Q inference happen outside this class.
    Their outputs are explicit inputs so the boundary can be audited for hidden
    evaluator labels.  This step performs only deterministic risk admission,
    complete-action safety filtering and conservative action selection.
    """

    def __init__(self, config: RCSEMConfig | None = None) -> None:
        self.config = config or RCSEMConfig()
        self.materializer = RiskControlledMaterializer(self.config.materialization)
        self.controller = RCSEMController(self.config.controller)

    def step(
        self,
        *,
        hypotheses: Iterable[EventHypothesis],
        action_options: Iterable[ActionOption],
        elapsed_sec: float,
        deadline_sec: float,
        frontier_size: int,
    ) -> RCSEMStep:
        if elapsed_sec > deadline_sec:
            raise ValueError("post-deadline state update is forbidden")
        publication = self.materializer.materialize(
            hypotheses,
            elapsed_sec=elapsed_sec,
        )
        state = ControllerState(
            elapsed_sec=elapsed_sec,
            deadline_sec=deadline_sec,
            frontier_size=frontier_size,
            publication=publication,
        )
        return RCSEMStep(
            publication=publication,
            decision=self.controller.choose(state, action_options),
        )
