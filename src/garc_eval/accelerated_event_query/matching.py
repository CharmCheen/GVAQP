from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from .types import EventRecord


@dataclass(frozen=True)
class MatchConfig:
    # Existing project contract: strict temporal overlap is the eligibility
    # rule; cardinality dominates tIoU in the one-to-one assignment.
    minimum_tiou: float = 0.0
    boundary_tolerance_sec: float = 0.0


@dataclass(frozen=True)
class EventMatch:
    predicted_event_id: str
    reference_event_id: str
    temporal_iou: float
    start_error_sec: float
    end_error_sec: float


def temporal_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    intersection = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return intersection / union if union > 0 else 0.0


def match_events(
    predicted: Sequence[EventRecord],
    reference: Sequence[EventRecord],
    config: MatchConfig | None = None,
) -> tuple[EventMatch, ...]:
    cfg = config or MatchConfig()
    if not predicted or not reference:
        return ()
    iou = np.zeros((len(predicted), len(reference)), dtype=float)
    eligible = np.zeros_like(iou, dtype=bool)
    for i, left in enumerate(predicted):
        for j, right in enumerate(reference):
            if left.video_id != right.video_id or left.query_id != right.query_id:
                continue
            value = temporal_iou(left.start_time, left.end_time, right.start_time, right.end_time)
            boundary_ok = (
                abs(left.start_time - right.start_time) <= cfg.boundary_tolerance_sec
                and abs(left.end_time - right.end_time) <= cfg.boundary_tolerance_sec
            )
            eligible[i, j] = value > cfg.minimum_tiou or boundary_ok
            iou[i, j] = value
    score = eligible.astype(float) * 1_000_000.0 + iou
    pred_idx, ref_idx = linear_sum_assignment(-score)
    rows = []
    for i, j in zip(pred_idx, ref_idx):
        if not eligible[i, j]:
            continue
        left, right = predicted[int(i)], reference[int(j)]
        rows.append(EventMatch(
            predicted_event_id=left.event_id,
            reference_event_id=right.event_id,
            temporal_iou=float(iou[i, j]),
            start_error_sec=abs(left.start_time - right.start_time),
            end_error_sec=abs(left.end_time - right.end_time),
        ))
    return tuple(sorted(rows, key=lambda row: (row.predicted_event_id, row.reference_event_id)))


def summarize_matches(
    predicted: Sequence[EventRecord],
    reference: Sequence[EventRecord],
    matches: Sequence[EventMatch],
) -> dict[str, float | int]:
    true_positive = len(matches)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "predicted_events": len(predicted),
        "reference_events": len(reference),
        "matched_events": true_positive,
        "32b_operational_oracle_relative_event_precision": precision,
        "32b_operational_oracle_relative_event_recall": recall,
        "event_f1": f1,
        "mean_event_boundary_tiou": (
            sum(row.temporal_iou for row in matches) / true_positive if true_positive else 0.0
        ),
    }
