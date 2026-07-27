"""Frozen causal SCAN policies that consume only :class:`PublicScanState`.

These policies are trusted in-repository research code.  They make no claim of
containing arbitrary third-party code; the narrow contract makes causal input
use directly auditable.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random


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
class PublicScanState:
    units: tuple[PublicUnit, ...]
    scanned_unit_ids: tuple[str, ...]
    current_unit_id: str | None
    remaining_budget_sec: float
    past_action_costs_sec: tuple[float, ...]
    revealed_candidate_ids: tuple[str, ...] = ()
    revealed_observations: tuple[PublicObservation, ...] = ()


class TrustedPolicy:
    policy_id = "ABSTRACT"

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        raise NotImplementedError


def _remaining(public_state: PublicScanState) -> list[PublicUnit]:
    scanned = set(public_state.scanned_unit_ids)
    return [unit for unit in public_state.units if unit.unit_id not in scanned]


class SequentialPolicy(TrustedPolicy):
    policy_id = "SEQUENTIAL"

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        return _remaining(public_state)[0].unit_id


class RandomWithoutReplacementPolicy(TrustedPolicy):
    policy_id = "RANDOM_WITHOUT_REPLACEMENT"

    def __init__(self, seed: int):
        self._rng = random.Random(seed)

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        remaining = _remaining(public_state)
        return remaining[self._rng.randrange(len(remaining))].unit_id


class UniformPrefixPolicy(TrustedPolicy):
    policy_id = "UNIFORM_PREFIX"

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        scanned = set(public_state.scanned_unit_ids)
        count = len(public_state.units)
        for level in range(math.ceil(math.log2(max(2, count))) + 1):
            stride = max(1, count // (2**level))
            for index in range(0, count, stride):
                candidate = public_state.units[index].unit_id
                if candidate not in scanned:
                    return candidate
        return _remaining(public_state)[0].unit_id


class AnytimeLargestGapPolicy(TrustedPolicy):
    policy_id = "ANYTIME_LARGEST_GAP"

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        remaining = _remaining(public_state)
        if not public_state.scanned_unit_ids:
            return remaining[len(remaining) // 2].unit_id
        index_by_id = {
            unit.unit_id: index for index, unit in enumerate(public_state.units)
        }
        scanned_indices = [
            index_by_id[unit_id] for unit_id in public_state.scanned_unit_ids
        ]
        return max(
            remaining,
            key=lambda unit: (
                min(
                    abs(index_by_id[unit.unit_id] - scanned_index)
                    for scanned_index in scanned_indices
                ),
                -index_by_id[unit.unit_id],
            ),
        ).unit_id


class MacroRegionLargestGapPolicy(TrustedPolicy):
    """Largest-gap region selection with contiguous execution within a region."""

    policy_id = "MACRO_REGION_LARGEST_GAP"

    def __init__(self, region_size: int = 3):
        if region_size < 2:
            raise ValueError("region_size must be at least two")
        self._region_size = int(region_size)
        self._pending: list[str] = []

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        scanned = set(public_state.scanned_unit_ids)
        while self._pending and self._pending[0] in scanned:
            self._pending.pop(0)
        if self._pending:
            return self._pending.pop(0)

        units = public_state.units
        remaining_indices = [
            index for index, unit in enumerate(units) if unit.unit_id not in scanned
        ]
        if not scanned:
            anchor = len(units) // 2
        else:
            index_by_id = {unit.unit_id: i for i, unit in enumerate(units)}
            scanned_indices = [index_by_id[unit_id] for unit_id in scanned]
            anchor = max(
                remaining_indices,
                key=lambda index: (
                    min(abs(index - value) for value in scanned_indices), -index
                ),
            )
        region_start = min(
            max(0, anchor), max(0, len(units) - self._region_size)
        )
        region = [
            units[index].unit_id
            for index in range(
                region_start, min(len(units), region_start + self._region_size)
            )
            if units[index].unit_id not in scanned
        ]
        if not region:
            return units[remaining_indices[0]].unit_id
        self._pending = region[1:]
        return region[0]


def make_policy(policy_id: str, seed: int = 0) -> TrustedPolicy:
    if policy_id == "SEQUENTIAL":
        return SequentialPolicy()
    if policy_id == "RANDOM_WITHOUT_REPLACEMENT":
        return RandomWithoutReplacementPolicy(seed)
    if policy_id == "UNIFORM_PREFIX":
        return UniformPrefixPolicy()
    if policy_id == "ANYTIME_LARGEST_GAP":
        return AnytimeLargestGapPolicy()
    if policy_id == "MACRO_REGION_LARGEST_GAP":
        return MacroRegionLargestGapPolicy(region_size=3)
    raise KeyError(policy_id)


class LateralRefinementPolicy(TrustedPolicy):
    """Largest-gap coverage plus bounded forward-neighbor refinement."""

    def __init__(self, mode: str):
        allowed = {
            "LG_ONE_NEIGHBOR", "LG_TWO_NEIGHBOR", "C75_R25",
            "C50_R50", "TWO_STAGE_COVER_THEN_REFINE",
        }
        if mode not in allowed:
            raise ValueError(mode)
        self.policy_id = mode
        self._mode = mode
        self._processed_triggers: set[str] = set()
        self._pending: list[str] = []
        self._initial_budget: float | None = None

    def _update_pending(self, public_state: PublicScanState) -> None:
        index_by_id = {
            unit.unit_id: index for index, unit in enumerate(public_state.units)
        }
        radius = 2 if self._mode == "LG_TWO_NEIGHBOR" else 1
        for observation in public_state.revealed_observations:
            if (
                observation.unit_id in self._processed_triggers
                or not observation.lateral_motion_signal
            ):
                continue
            self._processed_triggers.add(observation.unit_id)
            index = index_by_id[observation.unit_id]
            for distance in range(1, radius + 1):
                neighbor = index + distance
                if neighbor < len(public_state.units):
                    self._pending.append(public_state.units[neighbor].unit_id)

    def _refinement_allowed(self, public_state: PublicScanState) -> bool:
        action_count = len(public_state.scanned_unit_ids)
        if self._mode in {"LG_ONE_NEIGHBOR", "LG_TWO_NEIGHBOR"}:
            return True
        if self._mode == "C75_R25":
            return action_count % 4 == 3
        if self._mode == "C50_R50":
            return action_count % 2 == 1
        if self._initial_budget is None:
            self._initial_budget = public_state.remaining_budget_sec
        used = self._initial_budget - public_state.remaining_budget_sec
        return used >= 0.5 * self._initial_budget

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        if self._initial_budget is None:
            self._initial_budget = public_state.remaining_budget_sec
        self._update_pending(public_state)
        scanned = set(public_state.scanned_unit_ids)
        while self._pending and self._pending[0] in scanned:
            self._pending.pop(0)
        if self._pending and self._refinement_allowed(public_state):
            return self._pending.pop(0)
        return AnytimeLargestGapPolicy().choose_next_unit(public_state)


def make_refinement_policy(policy_id: str) -> TrustedPolicy:
    return LateralRefinementPolicy(policy_id)


REFINEMENT_POLICY_IDS = (
    "LG_ONE_NEIGHBOR",
    "LG_TWO_NEIGHBOR",
    "C75_R25",
    "C50_R50",
    "TWO_STAGE_COVER_THEN_REFINE",
)


CAUSAL_POLICY_IDS = (
    "SEQUENTIAL",
    "RANDOM_WITHOUT_REPLACEMENT",
    "UNIFORM_PREFIX",
    "ANYTIME_LARGEST_GAP",
    "MACRO_REGION_LARGEST_GAP",
)
