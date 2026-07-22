from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ..models import AtomicUnit, MaterializedEvent, OracleObservation


@dataclass(frozen=True)
class IntervalPosterior:
    start_time: float
    end_time: float
    probability: float


@dataclass(frozen=True)
class PosteriorMaterialization:
    event_interval_posterior: tuple[IntervalPosterior, ...]
    same_event_marginal: dict[tuple[str, str], float]
    event_count_posterior: dict[int, float]
    map_event_partition: tuple[MaterializedEvent, ...]
    boundary_marginals: dict[str, tuple[tuple[float, float], ...]]


class PosteriorMaterializer(Protocol):
    def infer(
        self,
        units: Sequence[AtomicUnit],
        observations: Sequence[OracleObservation],
        config: dict,
    ) -> PosteriorMaterialization: ...


# This module defines a contract only. It intentionally contains no HSMM inference.
