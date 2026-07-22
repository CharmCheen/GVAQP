from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ..models import AtomicUnit, MaterializedEvent, OracleObservation


@dataclass(frozen=True)
class MaterializerConfig:
    fixed_gap_seconds: float = 12.0
    core_duration_max: float = 40.0
    segment_duration_max: float = 60.0
    expansion_units: int = 1


class Materializer(Protocol):
    name: str

    def materialize(
        self,
        units: Sequence[AtomicUnit],
        observations: Sequence[OracleObservation],
        config: MaterializerConfig,
    ) -> list[MaterializedEvent]: ...
