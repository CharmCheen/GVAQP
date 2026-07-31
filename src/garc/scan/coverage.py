from __future__ import annotations

from .state import CoverageState


def maximum_gap_units(state: CoverageState) -> int:
    """Return twice the furthest unobserved index distance, matching the replay metric."""
    if not state.units:
        return 0
    if not state.scanned_unit_ids:
        return len(state.units)
    index = {unit.unit_id: i for i, unit in enumerate(state.units)}
    scanned = [index[unit_id] for unit_id in state.scanned_unit_ids]
    unseen = [i for i in range(len(state.units)) if state.units[i].unit_id not in state.scanned_unit_ids]
    return 0 if not unseen else 2 * max(min(abs(i - j) for j in scanned) for i in unseen)


def coverage_fraction(state: CoverageState) -> float:
    return len(set(state.scanned_unit_ids)) / len(state.units) if state.units else 1.0
