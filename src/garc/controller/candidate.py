from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .frontier import Candidate


class CandidateGenerationError(ValueError):
    """Raised when a replay SCAN outcome violates the frozen candidate contract."""


class FrozenCandidateGenerator:
    """Bind one deterministic top-track witness per visible unit.

    Replay manifests provide the public candidate rows produced by the frozen
    detector/tracker/scorer.  On first visibility this adapter binds the row
    with highest score, then ascending ``track_id`` and ``candidate_id``.  The
    binding and creation time remain stable and all bound visible witnesses are
    re-emitted after each completed SCAN, matching the frozen prefix behavior.
    """

    def __init__(self) -> None:
        self.bound_track_by_unit: dict[int, int] = {}
        self._visible: dict[int, Candidate] = {}

    @staticmethod
    def _normalize(unit_id: int, raw: Mapping[str, Any], elapsed_sec: float,
                   scan_index: int, created_elapsed_sec: float | None = None) -> Candidate:
        try:
            track_id = int(raw.get("track_id", 0))
            score = float(raw["score"])
        except (KeyError, TypeError, ValueError) as error:
            raise CandidateGenerationError(f"invalid candidate for unit {unit_id}: {error}") from error
        candidate_id = str(raw.get("candidate_id", f"unit_{unit_id:04d}_track_{track_id:04d}"))
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise CandidateGenerationError(f"candidate payload for unit {unit_id} must be a mapping")
        return Candidate(candidate_id, unit_id, track_id, score,
                         elapsed_sec if created_elapsed_sec is None else created_elapsed_sec,
                         scan_index, dict(payload))

    def observe_scan(self, unit_id: int, raw_candidates: Sequence[Mapping[str, Any]],
                     *, elapsed_sec: float, scan_index: int) -> list[Candidate]:
        if isinstance(raw_candidates, (str, bytes)) or not isinstance(raw_candidates, Sequence):
            raise CandidateGenerationError("candidates must be a sequence of mappings")
        normalized = [self._normalize(unit_id, raw, elapsed_sec, scan_index) for raw in raw_candidates]
        if unit_id in self.bound_track_by_unit and not any(
            row.track_id == self.bound_track_by_unit[unit_id] for row in normalized
        ):
            raise CandidateGenerationError(
                f"bound track {self.bound_track_by_unit[unit_id]} disappeared for unit {unit_id}"
            )
        if normalized:
            if unit_id not in self.bound_track_by_unit:
                selected = min(normalized, key=lambda row: (-row.score, row.track_id, row.candidate_id))
                self.bound_track_by_unit[unit_id] = selected.track_id
            bound_track = self.bound_track_by_unit[unit_id]
            matching = [row for row in normalized if row.track_id == bound_track]
            if matching:
                previous = self._visible.get(unit_id)
                selected = min(matching, key=lambda row: (-row.score, row.candidate_id))
                self._visible[unit_id] = Candidate(
                    selected.candidate_id, selected.unit_id, selected.track_id, selected.score,
                    previous.created_elapsed_sec if previous else selected.created_elapsed_sec,
                    previous.creation_scan_index if previous else selected.creation_scan_index,
                    selected.payload,
                )
        return self.visible()

    def visible(self) -> list[Candidate]:
        return [self._visible[unit_id] for unit_id in sorted(self._visible)]
