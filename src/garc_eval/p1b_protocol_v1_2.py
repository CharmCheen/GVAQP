"""Frozen, outcome-independent P1-B v1.2 protocol primitives."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable


REGION_ATOMIC_WIDTH_SEC = 10.0
REGION_ORIGIN_SEC = 0.0
REGION_BOUNDARY_CONVENTION = "half-open [start,end), except final partial cell ends at video duration"


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def temporal_region_count(candidate_orders: Iterable[int]) -> int:
    """Count maximal connected components on the frozen 10-second candidate lattice."""
    positions = sorted(set(int(value) for value in candidate_orders))
    return 0 if not positions else 1 + sum(right > left + 1 for left, right in zip(positions, positions[1:]))


def assign_positive_units_to_events(
    units: list[dict], events: list[dict], mapping: str = "ANCHOR_ASSIGNED_EVENT"
) -> dict[str, int]:
    """Attribute positive units to human events under a frozen mapping.

    The primary anchor is an existing unit anchor when present, otherwise its
    temporal center. Half-open human intervals are used, with deterministic
    maximum-overlap then lexical event-id tie breaking under overlapping events.
    """
    counts = {str(event["event_id"]): 0 for event in events}
    for unit in units:
        start, end = float(unit["start"]), float(unit["end"])
        if mapping == "OVERLAP_ANY_EVENT":
            candidates = [event for event in events if max(start, float(event["start_time"])) < min(end, float(event["end_time"]))]
        elif mapping == "ANCHOR_ASSIGNED_EVENT":
            anchor = float(unit.get("anchor_time", (start + end) / 2.0))
            candidates = [event for event in events if float(event["start_time"]) <= anchor < float(event["end_time"])]
            if candidates:
                candidates = [sorted(candidates, key=lambda event: (
                    -max(0.0, min(end, float(event["end_time"])) - max(start, float(event["start_time"]))),
                    str(event["event_id"]),
                ))[0]]
        else:
            raise ValueError(f"unknown event-attribution mapping: {mapping}")
        for event in candidates:
            counts[str(event["event_id"])] += 1
    return counts


def reference_quality_decision(case_rows: list[dict]) -> tuple[str, list[str]]:
    """Apply the frozen hard-failure gate before adjudication."""
    reasons: list[str] = []
    existence_disagreements = sum(not bool(row["event_existence_agreement"]) for row in case_rows)
    if existence_disagreements >= 3:
        reasons.append("A: event-existence disagreement in >=3/6 cases")
    large_count_disagreements = 0
    for row in case_rows:
        left, right = int(row["annotator_a_event_count"]), int(row["annotator_b_event_count"])
        if abs(left - right) > max(2.0, 0.5 * max(left, right)):
            large_count_disagreements += 1
    if large_count_disagreements >= 3:
        reasons.append("B: event-count disagreement exceeds max(2,50% larger count) in >=3/6 cases")
    total = sum(int(row["annotator_a_event_count"]) + int(row["annotator_b_event_count"]) for row in case_rows)
    matched = sum(int(row["matched_events_iou_gt_0"]) for row in case_rows)
    matched_fraction = 1.0 if total == 0 else 2.0 * matched / total
    if matched_fraction < 0.50:
        reasons.append("C: global one-to-one matched-event fraction at IoU>0 is <0.50")
    if sum(bool(row.get("systematic_semantic_misunderstanding", False)) for row in case_rows) >= 2:
        reasons.append("D: systematic query-semantic misunderstanding in multiple cases")
    return ("INSUFFICIENT", reasons) if reasons else ("ADJUDICATION_ELIGIBLE", [])


def trace_proxy_metadata(row: dict) -> dict:
    units = json.loads(row["queried_unit_ids"]) if isinstance(row["queried_unit_ids"], str) else row["queried_unit_ids"]
    proxy_dependent = str(row["generator_family"]) in {"StaticProxyRank", "MMR_w025", "MMR_w050", "MMR_w075"}
    return {
        "queried_units_hash": canonical_hash(units),
        "trace_content_hash": canonical_hash({"video_id": row["video_id"], "ordered_queried_unit_ids": units}),
        "proxy_dependent": proxy_dependent,
        "proxy_origin": row["proxy_id"] if proxy_dependent else "SHARED_CONTROL",
    }
