from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import EventStatus, PublicationSnapshot


@dataclass(frozen=True)
class PublicationMetrics:
    verified_count: int
    probable_count: int
    combined_count: int
    probable_precision: float | None
    verified_precision: float | None
    combined_precision: float | None


def score_snapshot(
    snapshot: PublicationSnapshot,
    *,
    matched_reference_event_ids: Iterable[str],
) -> PublicationMetrics:
    matched = set(matched_reference_event_ids)
    probable = [row for row in snapshot.events if row.status is EventStatus.PROBABLE]
    verified = [row for row in snapshot.events if row.status is EventStatus.VERIFIED]

    def precision(rows: list) -> float | None:
        return sum(row.event_id in matched for row in rows) / len(rows) if rows else None

    combined = [*verified, *probable]
    return PublicationMetrics(
        verified_count=len(verified),
        probable_count=len(probable),
        combined_count=len(combined),
        probable_precision=precision(probable),
        verified_precision=precision(verified),
        combined_precision=precision(combined),
    )


def anytime_auc(points: Iterable[tuple[float, float]], *, deadline_sec: float) -> float:
    """Right-continuous normalized area for `(commit_time, utility)` points."""
    if deadline_sec <= 0:
        raise ValueError("deadline_sec must be positive")
    ordered = sorted(points)
    previous_time = 0.0
    previous_value = 0.0
    area = 0.0
    for time_sec, value in ordered:
        if time_sec < previous_time or time_sec > deadline_sec:
            raise ValueError("metric point outside ordered deadline interval")
        area += (time_sec - previous_time) * previous_value
        previous_time = time_sec
        previous_value = value
    area += (deadline_sec - previous_time) * previous_value
    return area / deadline_sec
