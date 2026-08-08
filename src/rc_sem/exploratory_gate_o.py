"""Pure utilities for the explicitly non-confirmatory Guangzhou exploration."""

from __future__ import annotations

from collections.abc import Iterable


POLICIES = (
    "A_CHRONOLOGICAL_FIXED_SCAN1_VERIFY1",
    "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1",
    "C_CHRONOLOGICAL_SCAN_THEN_VERIFY",
)


def temporal_bisection_order(count: int) -> tuple[int, ...]:
    if count <= 0:
        raise ValueError("count must be positive")
    queue = [(0, count - 1)]
    order: list[int] = []
    while queue:
        lo, hi = queue.pop(0)
        if lo <= hi:
            mid = (lo + hi) // 2
            order.append(mid)
            queue.extend(((lo, mid - 1), (mid + 1, hi)))
    return tuple(order)


def event_groups(positive_units: Iterable[int], *, max_gap_units: int = 1) -> tuple[tuple[int, ...], ...]:
    values = sorted(set(map(int, positive_units)))
    if not values:
        return ()
    groups: list[list[int]] = [[values[0]]]
    for unit in values[1:]:
        if unit - groups[-1][-1] <= max_gap_units + 1:
            groups[-1].append(unit)
        else:
            groups.append([unit])
    return tuple(tuple(group) for group in groups)


def event_recall(predicted: Iterable[tuple[int, ...]], reference: Iterable[tuple[int, ...]]) -> float:
    ref = [set(group) for group in reference]
    pred = [set(group) for group in predicted]
    if not ref:
        return 1.0
    return sum(any(left & right for left in pred) for right in ref) / len(ref)


def event_f1(predicted: Iterable[tuple[int, ...]], reference: Iterable[tuple[int, ...]]) -> float:
    ref = [set(group) for group in reference]
    pred = [set(group) for group in predicted]
    if not pred and not ref:
        return 1.0
    matches = 0
    unused = set(range(len(ref)))
    for group in pred:
        choices = [index for index in unused if group & ref[index]]
        if choices:
            unused.remove(min(choices))
            matches += 1
    precision = matches / len(pred) if pred else 0.0
    recall = matches / len(ref) if ref else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def right_continuous_auc(points: Iterable[tuple[float, float]], deadline_seconds: float) -> float:
    if deadline_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")
    previous_time = previous_value = area = 0.0
    for timestamp, value in sorted(points):
        if timestamp < previous_time or timestamp > deadline_seconds:
            raise ValueError("metric point is outside the deadline")
        area += (timestamp - previous_time) * previous_value
        previous_time, previous_value = timestamp, value
    return (area + (deadline_seconds - previous_time) * previous_value) / deadline_seconds
