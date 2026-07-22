from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .models import ActionType, ObservationOutcome, OracleObservation, PlannerAction
from .synthetic import SyntheticTimeline


@dataclass(frozen=True)
class ErrorRates:
    false_positive: float = 0.0
    false_negative: float = 0.0
    abstain: float = 0.0


@dataclass(frozen=True)
class OracleConfig:
    rates: dict[ActionType, ErrorRates] = field(default_factory=lambda: {action: ErrorRates() for action in ActionType})
    costs: dict[ActionType, float] = field(default_factory=lambda: {action: 1.0 for action in ActionType})


class SyntheticOracleSimulator:
    """Typed synthetic oracle. Its latent timeline is never passed to planners."""

    def __init__(self, timeline: SyntheticTimeline, config: OracleConfig | None = None, seed: int | None = None) -> None:
        self._timeline = timeline
        self.config = config or config_from_timeline(timeline)
        self._rng = np.random.default_rng(timeline.config.random_seed if seed is None else seed)
        self._clock = 0.0

    def execute(self, action: PlannerAction) -> OracleObservation:
        self._clock += 1.0
        if action.action_type == ActionType.PROBE_RELATION:
            raw = self._relation_outcome(action.target_ids)
        elif action.action_type == ActionType.EXPLORE_CELL:
            raw = self._coverage_outcome(action.target_ids)
        elif action.action_type == ActionType.HARD_NEGATIVE_GAP:
            raw = self._naive_gap_outcome(action.target_ids)
        else:
            raw = self._core_outcome(action.target_ids)
        outcome = self._corrupt(raw, self.config.rates[action.action_type])
        return OracleObservation(
            action_id=action.action_id,
            action_type=action.action_type,
            target_ids=action.target_ids,
            outcome=outcome,
            confidence=1.0 - self.config.rates[action.action_type].abstain,
            cost=self.config.costs[action.action_type],
            timestamp=self._clock,
            source="SYNTHETIC_ORACLE_SIMULATOR",
        )

    def _core_outcome(self, target_ids: tuple[str, ...]) -> ObservationOutcome:
        target = target_ids[0]
        return ObservationOutcome.POSITIVE if target in self._timeline.positive_evidence_unit_ids else ObservationOutcome.NEGATIVE

    def _coverage_outcome(self, target_ids: tuple[str, ...]) -> ObservationOutcome:
        target = target_ids[0]
        return ObservationOutcome.POSITIVE if self._timeline.latent_unit_event_ids.get(target, ()) else ObservationOutcome.NEGATIVE

    def _naive_gap_outcome(self, target_ids: tuple[str, ...]) -> ObservationOutcome:
        target = target_ids[0]
        return ObservationOutcome.POSITIVE if target in self._timeline.positive_evidence_unit_ids else ObservationOutcome.NEGATIVE

    def _relation_outcome(self, target_ids: tuple[str, ...]) -> ObservationOutcome:
        if len(target_ids) != 2:
            return ObservationOutcome.AMBIGUOUS
        left = set(self._timeline.latent_unit_event_ids.get(target_ids[0], ()))
        right = set(self._timeline.latent_unit_event_ids.get(target_ids[1], ()))
        if not left or not right:
            return ObservationOutcome.AMBIGUOUS
        return ObservationOutcome.SAME if left & right else ObservationOutcome.DISTINCT

    def _corrupt(self, outcome: ObservationOutcome, rates: ErrorRates) -> ObservationOutcome:
        if self._rng.random() < rates.abstain:
            return ObservationOutcome.ABSTAIN
        draw = self._rng.random()
        if outcome == ObservationOutcome.POSITIVE and draw < rates.false_negative:
            return ObservationOutcome.NEGATIVE
        if outcome == ObservationOutcome.NEGATIVE and draw < rates.false_positive:
            return ObservationOutcome.POSITIVE
        if outcome == ObservationOutcome.SAME and draw < rates.false_negative:
            return ObservationOutcome.DISTINCT
        if outcome == ObservationOutcome.DISTINCT and draw < rates.false_positive:
            return ObservationOutcome.SAME
        return outcome


def config_from_timeline(timeline: SyntheticTimeline) -> OracleConfig:
    rates = {
        action: ErrorRates(
            false_positive=timeline.config.oracle_false_positive,
            false_negative=timeline.config.oracle_false_negative,
            abstain=timeline.config.oracle_abstain,
        )
        for action in ActionType
    }
    costs = {action: float(timeline.config.action_specific_cost.get(action.value, 1.0)) for action in ActionType}
    return OracleConfig(rates=rates, costs=costs)
