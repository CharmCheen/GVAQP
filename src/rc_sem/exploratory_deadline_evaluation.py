"""Completion-time-safe evaluator for persisted exploratory action traces."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .exploratory_gate_o import event_f1, event_groups, event_recall, right_continuous_auc


def completion_time_seconds(row: Mapping[str, object]) -> float:
    """The only persisted durable visibility surrogate in these raw traces."""
    return float(row["timestamp_seconds"]) + float(row["physical_cost_seconds"])


def deadline_safe_summary(trace: Iterable[Mapping[str, object]], reference_labels: Mapping[int, str], deadline_seconds: float) -> dict[str, object]:
    rows = list(trace)
    visible = [row for row in rows if completion_time_seconds(row) <= deadline_seconds]
    reference_events = event_groups(unit for unit, label in reference_labels.items() if label == "positive")
    recall_points: list[tuple[float, float]] = []
    f1_points: list[tuple[float, float]] = []
    for row in visible:
        groups = tuple(tuple(map(int, group)) for group in row["current_event_relation"])
        completed = completion_time_seconds(row)
        recall_points.append((completed, event_recall(groups, reference_events)))
        f1_points.append((completed, event_f1(groups, reference_events)))
    final_groups = tuple(tuple(map(int, group)) for group in visible[-1]["current_event_relation"]) if visible else ()
    positive_completions = [
        completion_time_seconds(row) for row in visible
        if row["action_type"] == "VERIFY" and row["outcome"].get("label") == "positive"
    ]
    return {
        "evaluation_mode": "STRICT_HARD_DEADLINE_COMPLETION",
        "deadline_seconds": deadline_seconds,
        "event_recall_auc": right_continuous_auc(recall_points, deadline_seconds),
        "event_recall_at_deadline": event_recall(final_groups, reference_events),
        "event_f1_auc": right_continuous_auc(f1_points, deadline_seconds),
        "event_f1_at_deadline": event_f1(final_groups, reference_events),
        "distinct_confirmed_events_at_deadline": len(final_groups),
        "first_positive_completion_time_at_deadline": min(positive_completions) if positive_completions else None,
        "scan_actions_completed_at_deadline": sum(row["action_type"] == "SCAN" for row in visible),
        "verify_actions_completed_at_deadline": sum(row["action_type"] == "VERIFY" for row in visible),
        "post_deadline_completed_actions": len(rows) - len(visible),
        "total_trace_scan_actions": sum(row["action_type"] == "SCAN" for row in rows),
        "total_trace_verify_actions": sum(row["action_type"] == "VERIFY" for row in rows),
        "final_physical_trace_completion_time": max(map(completion_time_seconds, rows), default=0.0),
        "deadline_overrun_seconds": max(0.0, max(map(completion_time_seconds, rows), default=0.0) - deadline_seconds),
    }
