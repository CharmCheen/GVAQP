from __future__ import annotations

import math
from dataclasses import dataclass

from .state import CoverageState, PublicUnit


EVALUATION_BASELINES = frozenset({"SEQUENTIAL", "UNIFORM_PREFIX", "MACRO_REGION_LARGEST_GAP"})
POLICY_IDS = EVALUATION_BASELINES | {"ANYTIME_LARGEST_GAP"}


@dataclass(frozen=True)
class SafeCoverageConfig:
    policy_id: str = "ANYTIME_LARGEST_GAP"
    macro_region_size_units: int = 3

    def __post_init__(self) -> None:
        if self.policy_id not in POLICY_IDS:
            raise ValueError(f"unsupported safe coverage policy: {self.policy_id}")
        if self.macro_region_size_units < 2:
            raise ValueError("macro_region_size_units must be >=2")


def _remaining(state: CoverageState) -> list[PublicUnit]:
    remaining = state.remaining_units()
    if not remaining:
        raise StopIteration("all SCAN units are complete")
    return remaining


class SafeCoveragePolicy:
    """Public-state-only SCAN policy; canonical default is AnytimeLargestGap.

    Baselines are opt-in evaluation modes. No video identifier is accepted, so
    historical per-video winner selection is impossible at this boundary.
    """

    def __init__(self, config: SafeCoverageConfig | None = None):
        self.config = config or SafeCoverageConfig()
        self.policy_id = self.config.policy_id
        self._pending: list[str] = []

    def choose_next_unit(self, public_state: CoverageState) -> str:
        if self.policy_id == "SEQUENTIAL":
            return _remaining(public_state)[0].unit_id
        if self.policy_id == "UNIFORM_PREFIX":
            return self._uniform_prefix(public_state)
        if self.policy_id == "MACRO_REGION_LARGEST_GAP":
            return self._macro_largest_gap(public_state)
        return self._largest_gap(public_state)

    @staticmethod
    def _largest_gap(state: CoverageState) -> str:
        remaining = _remaining(state)
        if not state.scanned_unit_ids:
            return remaining[len(remaining) // 2].unit_id
        index = {unit.unit_id: i for i, unit in enumerate(state.units)}
        scanned = [index[unit_id] for unit_id in state.scanned_unit_ids]
        return max(
            remaining,
            key=lambda unit: (min(abs(index[unit.unit_id] - j) for j in scanned), -index[unit.unit_id]),
        ).unit_id

    @staticmethod
    def _uniform_prefix(state: CoverageState) -> str:
        scanned = set(state.scanned_unit_ids)
        count = len(state.units)
        for level in range(math.ceil(math.log2(max(2, count))) + 1):
            stride = max(1, count // (2**level))
            for index in range(0, count, stride):
                candidate = state.units[index].unit_id
                if candidate not in scanned:
                    return candidate
        return _remaining(state)[0].unit_id

    def _macro_largest_gap(self, state: CoverageState) -> str:
        scanned = set(state.scanned_unit_ids)
        while self._pending and self._pending[0] in scanned:
            self._pending.pop(0)
        if self._pending:
            return self._pending.pop(0)
        units = state.units
        remaining = [i for i, unit in enumerate(units) if unit.unit_id not in scanned]
        if not remaining:
            raise StopIteration("all SCAN units are complete")
        if not scanned:
            anchor = len(units) // 2
        else:
            index = {unit.unit_id: i for i, unit in enumerate(units)}
            scanned_indices = [index[unit_id] for unit_id in scanned]
            anchor = max(remaining, key=lambda i: (min(abs(i - j) for j in scanned_indices), -i))
        start = min(max(0, anchor), max(0, len(units) - self.config.macro_region_size_units))
        region = [
            units[i].unit_id
            for i in range(start, min(len(units), start + self.config.macro_region_size_units))
            if units[i].unit_id not in scanned
        ]
        if not region:
            return units[remaining[0]].unit_id
        self._pending = region[1:]
        return region[0]
