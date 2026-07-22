"""Stable identities for unit VERIFY opportunities with track witnesses.

The frozen PSVR oracle is unit/clip conditioned.  A track is therefore a
causal feature witness, not a track-specific label target.  Once selected for a
unit VERIFY opportunity, that witness must remain immutable even if online
normalization later changes which track would have the largest proxy score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import MutableMapping


@dataclass(frozen=True, order=True)
class CandidateIdentity:
    video_id: str
    query_id: str
    unit_id: int
    track_id: int

    def __post_init__(self) -> None:
        if not self.video_id or "_" in self.video_id:
            raise ValueError("video_id must be a non-empty underscore-free token")
        if not self.query_id or "_" in self.query_id:
            raise ValueError("query_id must be a non-empty underscore-free token")
        if self.unit_id < 0 or self.track_id < 0:
            raise ValueError("unit_id and track_id must be non-negative")

    @property
    def candidate_id(self) -> str:
        # Keep the unit as the final token for compatibility with the frozen
        # legacy policy services, which recover unit_id from the final token.
        return (
            f"{self.video_id}_{self.query_id}_track_{self.track_id:06d}"
            f"_unit_{self.unit_id:06d}"
        )


def bind_track_witness(
    bindings: MutableMapping[int, int],
    *,
    unit_id: int,
    proposed_track_id: int,
) -> int:
    """Return the unit's immutable track witness, binding it on first sight."""

    if unit_id < 0 or proposed_track_id < 0:
        raise ValueError("unit_id and proposed_track_id must be non-negative")
    if unit_id not in bindings:
        bindings[unit_id] = proposed_track_id
    return int(bindings[unit_id])

