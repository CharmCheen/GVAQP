from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicUnit:
    unit_id: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class PublicObservation:
    unit_id: str
    lateral_motion_signal: bool


@dataclass(frozen=True)
class CoverageState:
    """The complete public-state boundary available to a SCAN policy."""

    units: tuple[PublicUnit, ...]
    scanned_unit_ids: tuple[str, ...] = ()
    current_unit_id: str | None = None
    remaining_budget_sec: float = float("inf")
    past_action_costs_sec: tuple[float, ...] = ()
    revealed_candidate_ids: tuple[str, ...] = ()
    revealed_observations: tuple[PublicObservation, ...] = ()

    def remaining_units(self) -> list[PublicUnit]:
        scanned = set(self.scanned_unit_ids)
        return [unit for unit in self.units if unit.unit_id not in scanned]
