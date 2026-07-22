from __future__ import annotations

from typing import Sequence

from ..models import (
    ActionType,
    AtomicUnit,
    MaterializedEvent,
    ObservationOutcome,
    OracleObservation,
    PlannerAction,
)
from .base import BasePlanner


def _queried(observations: Sequence[OracleObservation], action_types: set[ActionType] | None = None) -> set[str]:
    return {
        target
        for obs in observations
        if action_types is None or obs.action_type in action_types
        for target in obs.target_ids
    }


def _positive_anchors(observations: Sequence[OracleObservation], units: Sequence[AtomicUnit]) -> list[str]:
    order = {unit.unit_id: (unit.start_time, unit.unit_id) for unit in units}
    anchors = {
        obs.target_ids[0]
        for obs in observations
        if obs.outcome == ObservationOutcome.POSITIVE
        and obs.action_type in {ActionType.PROBE_CORE, ActionType.EXPLORE_CELL}
        and len(obs.target_ids) == 1
    }
    return sorted(anchors, key=order.get)


def _make(planner: BasePlanner, observations, action_type, targets, reason, cost=1.0) -> PlannerAction:
    return PlannerAction(planner._action_id(observations), action_type, tuple(targets), cost, reason)


class P0Uniform(BasePlanner):
    name = "P0Uniform"

    def choose_action(self, units, observations, events, remaining_budget):
        seen = _queried(observations)
        ordered = sorted(units, key=lambda u: (-u.coverage_prior, u.unit_id))
        unit = next((u for u in ordered if u.unit_id not in seen), None)
        return None if unit is None else _make(self, observations, ActionType.EXPLORE_CELL, [unit.unit_id], "uniform coverage order; GT unavailable")


class P1TopPrior(BasePlanner):
    name = "P1TopPrior"

    def choose_action(self, units, observations, events, remaining_budget):
        seen = _queried(observations)
        unit = next((u for u in sorted(units, key=lambda u: (-u.cheap_score, u.unit_id)) if u.unit_id not in seen), None)
        return None if unit is None else _make(self, observations, ActionType.PROBE_CORE, [unit.unit_id], f"highest cheap_score={unit.cheap_score:.6f}")


class P2ComponentFirst(BasePlanner):
    name = "P2ComponentFirst"

    def choose_action(self, units, observations, events, remaining_budget):
        seen = _queried(observations)
        candidates = []
        for index, unit in enumerate(units):
            left = units[index - 1].cheap_score if index else -1.0
            right = units[index + 1].cheap_score if index + 1 < len(units) else -1.0
            if unit.cheap_score >= left and unit.cheap_score >= right:
                candidates.append(unit)
        candidates.extend(unit for unit in units if unit not in candidates)
        unit = next((u for u in sorted(candidates, key=lambda u: (-u.cheap_score, -u.structural_score, u.unit_id)) if u.unit_id not in seen), None)
        return None if unit is None else _make(self, observations, ActionType.PROBE_CORE, [unit.unit_id], "component-local maximum before residual units")


class P3CoreOnlyGreedy(BasePlanner):
    name = "P3CoreOnlyGreedy"

    def choose_action(self, units, observations, events, remaining_budget):
        seen = _queried(observations)
        unit = next(
            (u for u in sorted(units, key=lambda u: (-(0.7 * u.cheap_score + 0.2 * u.structural_score + 0.1 * u.coverage_prior), u.unit_id)) if u.unit_id not in seen),
            None,
        )
        return None if unit is None else _make(self, observations, ActionType.PROBE_CORE, [unit.unit_id], "greedy public core score")


class P4RelationAwareHeuristic(BasePlanner):
    name = "P4RelationAwareHeuristic"

    def choose_action(self, units, observations, events, remaining_budget):
        anchors = _positive_anchors(observations, units)
        unit_by_id = {unit.unit_id: unit for unit in units}
        queried_pairs = {
            tuple(sorted(obs.target_ids))
            for obs in observations
            if obs.action_type == ActionType.PROBE_RELATION and len(obs.target_ids) == 2
        }
        event_sets = [set(event.anchor_ids) for event in events]
        candidates = []
        for left, right in zip(anchors, anchors[1:]):
            pair = tuple(sorted((left, right)))
            if pair in queried_pairs or not any({left, right}.issubset(anchor_set) for anchor_set in event_sets):
                continue
            expected_overmerge_cost = max(1.0, unit_by_id[right].end_time - unit_by_id[left].start_time)
            unresolved_probability = 1.0
            priority = unresolved_probability * expected_overmerge_cost / 1.0
            candidates.append((priority, left, right))
        if candidates:
            priority, left, right = sorted(candidates, key=lambda x: (-x[0], x[1], x[2]))[0]
            return _make(
                self,
                observations,
                ActionType.PROBE_RELATION,
                [left, right],
                f"heuristic relation_priority={priority:.6f}; unresolved adjacent hypotheses",
            )
        seen = _queried(observations)
        core_candidates = [u for u in sorted(units, key=lambda u: (-u.cheap_score, u.unit_id)) if u.unit_id not in seen]
        positive_count = len(anchors)
        negative_count = sum(obs.outcome == ObservationOutcome.NEGATIVE for obs in observations)
        if negative_count >= 2 and (not core_candidates or core_candidates[0].cheap_score <= 0.0):
            coverage = next((u for u in sorted(units, key=lambda u: (-u.coverage_prior, u.unit_id)) if u.unit_id not in seen), None)
            if coverage:
                return _make(self, observations, ActionType.EXPLORE_CELL, [coverage.unit_id], "open coverage fallback avoids zero-proxy lockout")
        unit = core_candidates[0] if core_candidates else None
        reason = f"acquire anchors before relation; positive_count={positive_count}"
        return None if unit is None else _make(self, observations, ActionType.PROBE_CORE, [unit.unit_id], reason)


class P5NaiveHardGap(BasePlanner):
    name = "P5NaiveHardGap"

    def choose_action(self, units, observations, events, remaining_budget):
        anchors = _positive_anchors(observations, units)
        unit_by_id = {unit.unit_id: unit for unit in units}
        seen = _queried(observations)
        for event in events:
            ordered = sorted(event.anchor_ids, key=lambda x: unit_by_id[x].start_time)
            for left, right in zip(ordered, ordered[1:]):
                midpoint = (unit_by_id[left].end_time + unit_by_id[right].start_time) / 2.0
                gaps = [u for u in units if u.unit_id not in seen and unit_by_id[left].end_time <= u.start_time <= unit_by_id[right].start_time]
                if gaps:
                    target = sorted(gaps, key=lambda u: (abs((u.start_time + u.end_time) / 2 - midpoint), u.unit_id))[0]
                    return _make(
                        self,
                        observations,
                        ActionType.HARD_NEGATIVE_GAP,
                        [target.unit_id],
                        "unsafe counterexample: binary negative gap interpreted as must-not-link",
                    )
        top = next((u for u in sorted(units, key=lambda u: (-u.cheap_score, u.unit_id)) if u.unit_id not in seen), None)
        return None if top is None else _make(self, observations, ActionType.PROBE_CORE, [top.unit_id], f"acquire anchors before naive gap; positive_count={len(anchors)}")
