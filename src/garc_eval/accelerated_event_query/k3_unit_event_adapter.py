"""Deterministic K3 adapter from V3 unit outcomes to EventRelation.

The existing online :class:`IncrementalK3` remains unchanged. This adapter is
the exhaustive-reference path: only 32B-relative ``relevant`` units supply
event support, while ``unknown`` and ``parse_failure`` remain explicit.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Iterable

from .model_relative_event_relation import ModelRelativeEventRelation, canonical_hash
from .model_relative_labels import ModelRelativeUnitLabel
from .types import EventRecord


@dataclass(frozen=True)
class K3UnitEventConfig:
    protocol_id: str = "AEQ_MODEL_RELATIVE_K3_V3_1"
    unit_duration_seconds: float = 10.0
    unit_stride_seconds: float = 10.0
    merge_adjacent_positive_units: bool = True
    maximum_unknown_gap_units: int = 1
    maximum_merge_gap_seconds: float = 10.0
    maximum_core_duration_seconds: float = 40.0
    maximum_event_duration_seconds: float = 60.0
    boundary_rule: str = "min_positive_unit_start_to_max_positive_unit_end"
    negative_gap_rule: str = "hard_barrier"
    parse_failure_gap_rule: str = "indeterminate_hard_barrier_not_negative"
    unknown_gap_rule: str = "bridge_one_fully_covering_unknown_unit_within_maximum_gap"
    adjacent_distinct_event_rule: str = (
        "merge_observationally_indistinguishable_adjacent_positives_until_duration_cap"
    )
    overlap_rule: str = "merge_overlapping_positive_windows"
    dedup_rule: str = "deduplicate_exact_unit_id_then_canonical_temporal_grouping"
    event_identity_rule: str = "sha256(query,video,earliest_positive_unit,k3_config)"

    def __post_init__(self) -> None:
        if self.unit_duration_seconds <= 0 or self.unit_stride_seconds <= 0:
            raise ValueError("unit duration and stride must be positive")
        if self.maximum_unknown_gap_units < 0:
            raise ValueError("maximum unknown gap units must be nonnegative")
        if min(
            self.maximum_merge_gap_seconds,
            self.maximum_core_duration_seconds,
            self.maximum_event_duration_seconds,
        ) < 0:
            raise ValueError("K3 temporal limits must be nonnegative")
        if self.maximum_core_duration_seconds > self.maximum_event_duration_seconds:
            raise ValueError("core duration cannot exceed event duration")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def sha256(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class K3UnitEventUpdate:
    action: str
    accepted: bool
    attempted_after_deadline: bool
    post_deadline_commit: bool
    relation: ModelRelativeEventRelation
    added_event_ids: tuple[str, ...]
    removed_event_ids: tuple[str, ...]


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


class K3UnitEventAdapter:
    """Stateful, deadline-safe materializer over authoritative unit outcomes."""

    def __init__(self, query_id: str, config: K3UnitEventConfig | None = None):
        if not query_id:
            raise ValueError("query_id must be nonempty")
        self.query_id = query_id
        self.config = config or K3UnitEventConfig()
        self._units: dict[str, ModelRelativeUnitLabel] = {}
        self._relation = self._materialize(())

    @property
    def relation(self) -> ModelRelativeEventRelation:
        return self._relation

    def apply(
        self,
        action: str,
        units: Iterable[ModelRelativeUnitLabel],
        *,
        elapsed_sec: float,
        deadline_sec: float,
    ) -> K3UnitEventUpdate:
        if elapsed_sec > deadline_sec:
            return K3UnitEventUpdate(
                action=action,
                accepted=False,
                attempted_after_deadline=True,
                post_deadline_commit=False,
                relation=self._relation,
                added_event_ids=(),
                removed_event_ids=(),
            )
        incoming = list(units)
        next_units = dict(self._units)
        for row in incoming:
            if row.query_id != self.query_id:
                raise ValueError("unit belongs to a different query")
            prior = next_units.get(row.unit_id)
            if prior is not None:
                prior_core = (
                    prior.query_id, prior.video_id, prior.start_time, prior.end_time, prior.outcome
                )
                row_core = (
                    row.query_id, row.video_id, row.start_time, row.end_time, row.outcome
                )
                if prior_core != row_core:
                    raise ValueError("unit identity or authoritative outcome changed")
            next_units[row.unit_id] = row
        next_relation = self._materialize(next_units.values())
        previous_ids = {event.event_id for event in self._relation.events}
        next_ids = {event.event_id for event in next_relation.events}
        self._units = next_units
        self._relation = next_relation
        return K3UnitEventUpdate(
            action=action,
            accepted=True,
            attempted_after_deadline=False,
            post_deadline_commit=False,
            relation=next_relation,
            added_event_ids=tuple(sorted(next_ids - previous_ids)),
            removed_event_ids=tuple(sorted(previous_ids - next_ids)),
        )

    def materialize(self, units: Iterable[ModelRelativeUnitLabel]) -> ModelRelativeEventRelation:
        return self._materialize(units)

    def _materialize(
        self, units: Iterable[ModelRelativeUnitLabel]
    ) -> ModelRelativeEventRelation:
        canonical: dict[str, ModelRelativeUnitLabel] = {}
        for row in units:
            if row.query_id != self.query_id:
                raise ValueError("unit belongs to a different query")
            prior = canonical.get(row.unit_id)
            if prior is not None:
                prior_core = (
                    prior.query_id, prior.video_id, prior.start_time, prior.end_time, prior.outcome
                )
                row_core = (
                    row.query_id, row.video_id, row.start_time, row.end_time, row.outcome
                )
                if prior_core != row_core:
                    raise ValueError("conflicting duplicate unit")
                continue
            canonical[row.unit_id] = row.without_diagnostics()
        rows = tuple(sorted(
            canonical.values(), key=lambda row: (row.video_id, row.start_time, row.end_time, row.unit_id)
        ))
        events: list[EventRecord] = []
        tasks = sorted({row.video_id for row in rows})
        for video_id in tasks:
            task_rows = [row for row in rows if row.video_id == video_id]
            positives = [row for row in task_rows if row.outcome == "relevant"]
            groups: list[list[ModelRelativeUnitLabel]] = []
            for row in positives:
                if not groups or not self._can_merge(groups[-1], row, task_rows):
                    groups.append([row])
                else:
                    groups[-1].append(row)
            for group in groups:
                root = min(group, key=lambda row: (row.start_time, row.end_time, row.unit_id))
                identity_parts = (self.query_id, video_id, root.unit_id, self.config.sha256)
                source_ids = tuple(sorted(row.unit_id for row in group))
                events.append(EventRecord(
                    event_id=_stable_id("event32b", *identity_parts),
                    query_id=self.query_id,
                    video_id=video_id,
                    start_time=min(row.start_time for row in group),
                    end_time=max(row.end_time for row in group),
                    event_score=1.0,
                    evidence_status="VERIFIED_EVENT",
                    source_candidate_ids=source_ids,
                    verification_history=(),
                    k3_group=_stable_id("k3v3", *identity_parts),
                    commit_time=None,
                ))
        return ModelRelativeEventRelation(
            query_id=self.query_id,
            k3_config_sha256=self.config.sha256,
            events=tuple(sorted(events, key=lambda row: (
                row.video_id, row.start_time, row.end_time, row.event_id
            ))),
            negative_unit_ids=tuple(sorted(
                row.unit_id for row in rows if row.outcome == "not_relevant"
            )),
            unknown_unit_ids=tuple(sorted(
                row.unit_id for row in rows if row.outcome == "unknown"
            )),
            parse_failure_unit_ids=tuple(sorted(
                row.unit_id for row in rows if row.outcome == "parse_failure"
            )),
        )

    def _can_merge(
        self,
        current: list[ModelRelativeUnitLabel],
        right: ModelRelativeUnitLabel,
        task_rows: list[ModelRelativeUnitLabel],
    ) -> bool:
        left = current[-1]
        gap = max(0.0, right.start_time - left.end_time)
        start = min(row.start_time for row in current)
        end = max(right.end_time, max(row.end_time for row in current))
        if end - start > min(
            self.config.maximum_core_duration_seconds,
            self.config.maximum_event_duration_seconds,
        ):
            return False
        if gap == 0.0:
            return self.config.merge_adjacent_positive_units
        if gap > self.config.maximum_merge_gap_seconds:
            return False
        between = [row for row in task_rows if (
            row.unit_id not in {left.unit_id, right.unit_id}
            and row.start_time >= left.end_time
            and row.end_time <= right.start_time
            and row.end_time > left.end_time
            and row.start_time < right.start_time
        )]
        if not between or len(between) > self.config.maximum_unknown_gap_units:
            return False
        if any(row.outcome != "unknown" for row in between):
            return False
        bridge_start = min(row.start_time for row in between)
        bridge_end = max(row.end_time for row in between)
        return bridge_start <= left.end_time and bridge_end >= right.start_time
