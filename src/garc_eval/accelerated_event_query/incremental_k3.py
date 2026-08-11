from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .types import CandidateObservation, EventRecord, VerificationRecord


@dataclass(frozen=True)
class K3Config:
    probable_threshold: float = 0.80
    max_neighbor_gap_sec: float = 10.0
    max_core_duration_sec: float = 40.0
    max_event_duration_sec: float = 60.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.probable_threshold <= 1.0:
            raise ValueError("probable_threshold must be in [0, 1]")
        if min(
            self.max_neighbor_gap_sec,
            self.max_core_duration_sec,
            self.max_event_duration_sec,
        ) < 0:
            raise ValueError("K3 temporal parameters must be nonnegative")
        if self.max_core_duration_sec > self.max_event_duration_sec:
            raise ValueError("core duration cannot exceed event duration")


@dataclass(frozen=True)
class K3Update:
    action: str
    accepted: bool
    attempted_after_deadline: bool
    post_deadline_commit: bool
    events: tuple[EventRecord, ...]
    candidate_to_event: tuple[tuple[str, str], ...]
    added_event_ids: tuple[str, ...]
    removed_event_ids: tuple[str, ...]
    promoted_event_ids: tuple[str, ...]


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


class IncrementalK3:
    """Deterministic event reconstruction over causally revealed observations.

    ``apply`` is the sole mutation boundary. An action completing after its hard
    deadline is rejected before candidate, event, or commit state changes.
    """

    def __init__(self, config: K3Config | None = None):
        self.config = config or K3Config()
        self._candidates: dict[str, CandidateObservation] = {}
        self._events: dict[str, EventRecord] = {}
        self._candidate_to_event: dict[str, str] = {}

    @property
    def events(self) -> tuple[EventRecord, ...]:
        return tuple(sorted(self._events.values(), key=lambda row: (row.video_id, row.start_time, row.event_id)))

    @property
    def candidate_to_event(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._candidate_to_event.items()))

    def apply(
        self,
        action: str,
        observations: Iterable[CandidateObservation],
        *,
        elapsed_sec: float,
        deadline_sec: float,
    ) -> K3Update:
        if elapsed_sec > deadline_sec:
            return K3Update(
                action=action,
                accepted=False,
                attempted_after_deadline=True,
                post_deadline_commit=False,
                events=self.events,
                candidate_to_event=self.candidate_to_event,
                added_event_ids=(),
                removed_event_ids=(),
                promoted_event_ids=(),
            )
        incoming = list(observations)
        for row in incoming:
            prior = self._candidates.get(row.candidate_id)
            if prior and (prior.query_id != row.query_id or prior.video_id != row.video_id):
                raise ValueError("candidate identity cannot move between query/video tasks")
        previous = self._events
        for row in incoming:
            self._candidates[row.candidate_id] = row
        materialized, assignments = self._materialize(elapsed_sec)
        previous_ids = set(previous)
        current_ids = set(materialized)
        promoted = sorted(
            event_id
            for event_id in previous_ids & current_ids
            if previous[event_id].evidence_status == "PROBABLE_EVENT"
            and materialized[event_id].evidence_status == "VERIFIED_EVENT"
        )
        self._events = materialized
        self._candidate_to_event = assignments
        return K3Update(
            action=action,
            accepted=True,
            attempted_after_deadline=False,
            post_deadline_commit=False,
            events=self.events,
            candidate_to_event=self.candidate_to_event,
            added_event_ids=tuple(sorted(current_ids - previous_ids)),
            removed_event_ids=tuple(sorted(previous_ids - current_ids)),
            promoted_event_ids=tuple(promoted),
        )

    def _materialize(self, elapsed_sec: float) -> tuple[dict[str, EventRecord], dict[str, str]]:
        events: dict[str, EventRecord] = {}
        assignments: dict[str, str] = {}
        tasks = sorted({(row.video_id, row.query_id) for row in self._candidates.values()})
        for video_id, query_id in tasks:
            task_rows = [
                row for row in self._candidates.values()
                if row.video_id == video_id and row.query_id == query_id
            ]
            negative = [row for row in task_rows if row.evidence_status == "VERIFIED_NEGATIVE"]
            support = sorted(
                (row for row in task_rows if row.evidence_status != "VERIFIED_NEGATIVE"),
                key=lambda row: (row.start_time, row.end_time, row.candidate_id),
            )
            groups: list[list[CandidateObservation]] = []
            for row in support:
                if not groups or not self._can_merge(groups[-1], row, negative):
                    groups.append([row])
                else:
                    groups[-1].append(row)
            for group in groups:
                source_ids = tuple(sorted(row.candidate_id for row in group))
                root = min(group, key=lambda row: (row.start_time, row.candidate_id))
                k3_group = _stable_id("k3", video_id, query_id, root.candidate_id)
                event_id = _stable_id("event", video_id, query_id, root.candidate_id)
                verified = any(row.evidence_status == "VERIFIED_POSITIVE" for row in group)
                score = max(row.calibrated_probability for row in group)
                if verified:
                    status = "VERIFIED_EVENT"
                elif score >= self.config.probable_threshold:
                    status = "PROBABLE_EVENT"
                else:
                    status = "EVENT_HYPOTHESIS"
                old_commit = self._events.get(event_id).commit_time if event_id in self._events else None
                commit_time = old_commit if old_commit is not None else (elapsed_sec if status != "EVENT_HYPOTHESIS" else None)
                history: tuple[VerificationRecord, ...] = tuple(sorted(
                    (item for row in group for item in row.verification_history),
                    key=lambda item: (item.elapsed_sec, item.raw_output_sha256, item.label),
                ))
                event = EventRecord(
                    event_id=event_id,
                    query_id=query_id,
                    video_id=video_id,
                    start_time=min(row.start_time for row in group),
                    end_time=max(row.end_time for row in group),
                    event_score=score,
                    evidence_status=status,
                    source_candidate_ids=source_ids,
                    verification_history=history,
                    k3_group=k3_group,
                    commit_time=commit_time,
                )
                events[event_id] = event
                assignments.update({candidate_id: event_id for candidate_id in source_ids})
        return events, assignments

    def _can_merge(
        self,
        current: list[CandidateObservation],
        right: CandidateObservation,
        negatives: list[CandidateObservation],
    ) -> bool:
        left = current[-1]
        gap = max(0.0, right.start_time - left.end_time)
        start = min(row.start_time for row in current)
        end = max(right.end_time, max(row.end_time for row in current))
        if gap > self.config.max_neighbor_gap_sec:
            return False
        if end - start > min(self.config.max_core_duration_sec, self.config.max_event_duration_sec):
            return False
        return not any(
            barrier.start_time < right.start_time and barrier.end_time > left.end_time
            for barrier in negatives
        )
