from __future__ import annotations

from collections import Counter
from typing import Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from .models import ActionType, AtomicUnit, GroundTruthEvent, MaterializedEvent, OracleObservation


def temporal_iou(left_start: float, left_end: float, right_start: float, right_end: float) -> float:
    intersection = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    union = max(left_end, right_end) - min(left_start, right_start)
    return intersection / union if union > 0 else 0.0


def overlap_seconds(pred: MaterializedEvent, truth: GroundTruthEvent) -> float:
    return max(0.0, min(pred.end_time, truth.end_time) - max(pred.start_time, truth.start_time))


def one_to_one_event_matching(
    predictions: Sequence[MaterializedEvent],
    truths: Sequence[GroundTruthEvent],
    minimum_iou: float = 0.0,
) -> list[tuple[int, int, float]]:
    if not predictions or not truths:
        return []
    scores = np.array(
        [
            [temporal_iou(pred.start_time, pred.end_time, truth.start_time, truth.end_time) for truth in truths]
            for pred in predictions
        ],
        dtype=float,
    )
    pred_indices, truth_indices = linear_sum_assignment(-scores)
    return [
        (int(pi), int(ti), float(scores[pi, ti]))
        for pi, ti in zip(pred_indices, truth_indices)
        if scores[pi, ti] > minimum_iou
    ]


def canonical_anchor_matching(
    predictions: Sequence[MaterializedEvent], truths: Sequence[GroundTruthEvent]
) -> list[tuple[int, int]]:
    candidates = []
    for pi, pred in enumerate(predictions):
        for ti, truth in enumerate(truths):
            if pred.start_time <= truth.canonical_anchor_time < pred.end_time:
                candidates.append((abs((pred.start_time + pred.end_time) / 2 - truth.canonical_anchor_time), pi, ti))
    used_pred: set[int] = set()
    used_truth: set[int] = set()
    matches = []
    for _, pi, ti in sorted(candidates):
        if pi not in used_pred and ti not in used_truth:
            used_pred.add(pi)
            used_truth.add(ti)
            matches.append((pi, ti))
    return matches


def returned_seconds(events: Sequence[MaterializedEvent]) -> float:
    return float(sum(max(0.0, event.end_time - event.start_time) for event in events))


def evaluate(
    predictions: Sequence[MaterializedEvent],
    truths: Sequence[GroundTruthEvent],
    observations: Sequence[OracleObservation] = (),
    units: Sequence[AtomicUnit] = (),
) -> dict[str, float]:
    matches = one_to_one_event_matching(predictions, truths)
    precision = len(matches) / len(predictions) if predictions else 0.0
    recall = len(matches) / len(truths) if truths else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    pred_overlap_counts = [sum(overlap_seconds(pred, truth) > 0 for truth in truths) for pred in predictions]
    truth_overlap_counts = [sum(overlap_seconds(pred, truth) > 0 for pred in predictions) for truth in truths]
    boundary_errors = [
        (abs(predictions[pi].start_time - truths[ti].start_time) + abs(predictions[pi].end_time - truths[ti].end_time)) / 2.0
        for pi, ti, _ in matches
    ]
    action_cost = Counter()
    units_by_id = {unit.unit_id: unit for unit in units}
    queried_seconds = 0.0
    for obs in observations:
        action_cost[obs.action_type.value] += obs.cost
        if obs.action_type != ActionType.PROBE_RELATION:
            queried_seconds += sum(
                max(0.0, units_by_id[target].end_time - units_by_id[target].start_time)
                for target in obs.target_ids
                if target in units_by_id
            )
    metrics: dict[str, float] = {
        "event_precision": precision,
        "event_recall": recall,
        "event_f1": f1,
        "matched_event_count": float(len(matches)),
        "canonical_anchor_match_count": float(len(canonical_anchor_matching(predictions, truths))),
        "event_count_error": float(abs(len(predictions) - len(truths))),
        "overmerge_multiplicity": float(np.mean(pred_overlap_counts)) if pred_overlap_counts else 0.0,
        "oversplit_rate": sum(count > 1 for count in truth_overlap_counts) / len(truths) if truths else 0.0,
        "returned_seconds": returned_seconds(predictions),
        "boundary_error": float(np.mean(boundary_errors)) if boundary_errors else 0.0,
        "oracle_calls": float(len(observations)),
        "queried_seconds": queried_seconds,
    }
    for action in ActionType:
        metrics[f"cost_{action.value}"] = float(action_cost[action.value])
        metrics[f"calls_{action.value}"] = float(sum(obs.action_type == action for obs in observations))
    return metrics
