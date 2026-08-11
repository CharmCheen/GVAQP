from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from garc.controller.frontier import Candidate


class MaterializationError(ValueError):
    """Raised when a CONFIRM request or parsed result cannot be materialized."""

    def __init__(self, message: str, *, actual_cost_sec: float = 0.0):
        super().__init__(message)
        self.actual_cost_sec = float(actual_cost_sec)


def materialize_candidate(candidate: Candidate) -> dict[str, Any]:
    """Create the stable CONFIRM request without adding hidden information."""
    if not candidate.candidate_id:
        raise MaterializationError("candidate_id must be non-empty")
    if candidate.payload is not None and not isinstance(candidate.payload, Mapping):
        raise MaterializationError("candidate payload must be a mapping")
    return {
        "candidate_id": candidate.candidate_id,
        "unit_id": candidate.unit_id,
        "track_id": candidate.track_id,
        "payload": dict(candidate.payload or {}),
    }


def materialize_confirm_result(positive: bool, distinct_utility_ids: Sequence[Any]) -> tuple[str, ...]:
    """Materialize frozen replay output into canonical distinct event IDs."""
    if isinstance(distinct_utility_ids, (str, bytes)) or not isinstance(distinct_utility_ids, Sequence):
        raise MaterializationError("distinct_utility_ids must be a sequence")
    if not positive:
        return ()
    return tuple(sorted({str(value) for value in distinct_utility_ids}))
