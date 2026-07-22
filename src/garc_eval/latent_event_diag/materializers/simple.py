from __future__ import annotations

from typing import Sequence

from ..models import ActionType, AtomicUnit, MaterializedEvent, ObservationOutcome, OracleObservation
from .base import MaterializerConfig


class M0SimpleRunMaterializer:
    """Positive-anchor fixed-gap merge with typed relation overrides.

    Ordinary negative core observations are soft. Only DISTINCT relation evidence,
    or the explicitly unsafe HARD_NEGATIVE_GAP baseline, creates a separator.
    """

    name = "M0"

    def materialize(
        self,
        units: Sequence[AtomicUnit],
        observations: Sequence[OracleObservation],
        config: MaterializerConfig,
    ) -> list[MaterializedEvent]:
        by_id = {unit.unit_id: unit for unit in units}
        positive = {
            obs.target_ids[0]: obs
            for obs in observations
            if obs.action_type in {ActionType.PROBE_CORE, ActionType.EXPLORE_CELL}
            and obs.outcome == ObservationOutcome.POSITIVE
            and len(obs.target_ids) == 1
            and obs.target_ids[0] in by_id
        }
        anchors = sorted(positive, key=lambda unit_id: (by_id[unit_id].start_time, unit_id))
        if not anchors:
            return []
        relation = self._relation_map(observations)
        hard_gaps = [
            (by_id[obs.target_ids[0]].start_time, obs.action_id)
            for obs in observations
            if obs.action_type == ActionType.HARD_NEGATIVE_GAP
            and obs.outcome == ObservationOutcome.NEGATIVE
            and len(obs.target_ids) == 1
            and obs.target_ids[0] in by_id
        ]
        groups: list[list[str]] = [[anchors[0]]]
        for anchor in anchors[1:]:
            left = groups[-1][-1]
            pair = tuple(sorted((left, anchor)))
            state = relation.get(pair)
            gap = by_id[anchor].start_time - by_id[left].end_time
            has_unsafe_barrier = any(by_id[left].end_time <= t <= by_id[anchor].start_time for t, _ in hard_gaps)
            merge = state == ObservationOutcome.SAME or (
                state != ObservationOutcome.DISTINCT
                and not has_unsafe_barrier
                and gap <= config.fixed_gap_seconds
                and by_id[anchor].end_time - by_id[groups[-1][0]].start_time <= config.core_duration_max
            )
            if merge:
                groups[-1].append(anchor)
            else:
                groups.append([anchor])
        events = []
        for index, group in enumerate(groups):
            evidence = [positive[x].action_id for x in group]
            for obs in observations:
                if set(obs.target_ids).issubset(set(group)) and obs.action_type in {
                    ActionType.PROBE_RELATION,
                    ActionType.HARD_NEGATIVE_GAP,
                }:
                    evidence.append(obs.action_id)
            events.append(
                MaterializedEvent(
                    event_id=f"m0_event_{index}",
                    start_time=min(by_id[x].start_time for x in group),
                    end_time=max(by_id[x].end_time for x in group),
                    anchor_ids=tuple(group),
                    evidence_ids=tuple(sorted(set(evidence))),
                    confidence=min(0.99, 0.65 + 0.08 * len(group)),
                )
            )
        return events

    @staticmethod
    def _relation_map(observations: Sequence[OracleObservation]) -> dict[tuple[str, str], ObservationOutcome]:
        result = {}
        for obs in observations:
            if obs.action_type != ActionType.PROBE_RELATION or len(obs.target_ids) != 2:
                continue
            if obs.outcome in {ObservationOutcome.SAME, ObservationOutcome.DISTINCT}:
                result[tuple(sorted(obs.target_ids))] = obs.outcome
        return result
