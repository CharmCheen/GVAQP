"""CRAQ-lite interval-event metrics.

These utilities are intentionally small and dependency-light so experiment
wrappers can share one definition for interval IoU, event recall, duplicate
handling, and duration inflation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Interval:
    """Closed-open temporal interval in seconds."""

    t_start: float
    t_end: float
    event_id: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, float(self.t_end) - float(self.t_start))


def interval_iou(a: Interval, b: Interval) -> float:
    """Temporal IoU using the span union."""

    inter = max(0.0, min(a.t_end, b.t_end) - max(a.t_start, b.t_start))
    union = max(a.t_end, b.t_end) - min(a.t_start, b.t_start)
    return float(inter / union) if union > 0 else 0.0


def event_hits(predictions: Iterable[Interval], events: Iterable[Interval], iou_threshold: float) -> dict[str, list[int]]:
    """Return event_id -> prediction indices that hit the event."""

    preds = list(predictions)
    evs = list(events)
    hits: dict[str, list[int]] = {}
    for ev in evs:
        eid = str(ev.event_id)
        hits[eid] = [i for i, pred in enumerate(preds) if interval_iou(pred, ev) >= iou_threshold]
    return hits


def event_recall(predictions: Iterable[Interval], events: Iterable[Interval], iou_threshold: float) -> float:
    """Fraction of events hit by at least one prediction at the IoU threshold."""

    evs = list(events)
    if not evs:
        return 0.0
    hits = event_hits(predictions, evs, iou_threshold)
    return sum(bool(v) for v in hits.values()) / len(evs)


def duplicate_rate(predictions: Iterable[Interval], events: Iterable[Interval], iou_threshold: float = 0.3) -> float:
    """Extra hit predictions per returned interval.

    A duplicate is any additional prediction hitting an event after the first hit
    for that event. The denominator is the number of returned predictions.
    """

    preds = list(predictions)
    if not preds:
        return 0.0
    hits = event_hits(preds, events, iou_threshold)
    duplicate_count = sum(max(0, len(v) - 1) for v in hits.values())
    return duplicate_count / len(preds)


def duration_inflation(predictions: Iterable[Interval], events: Iterable[Interval], iou_threshold: float = 0.3) -> float:
    """Returned duration divided by matched true-event duration.

    If no prediction hits any event, the denominator falls back to total true
    event duration. This makes empty or all-background returns non-infinite while
    still documenting a conservative duration burden.
    """

    preds = list(predictions)
    evs = list(events)
    returned = sum(p.duration for p in preds)
    if not evs:
        return 0.0
    hits = event_hits(preds, evs, iou_threshold)
    matched_ids = {eid for eid, idxs in hits.items() if idxs}
    denom = sum(ev.duration for ev in evs if str(ev.event_id) in matched_ids)
    if denom <= 0:
        denom = sum(ev.duration for ev in evs)
    return float(returned / denom) if denom > 0 else 0.0

