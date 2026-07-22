"""Pure helpers for the MF-PSVR independent training-pool contract.

The frozen oracle is unit-scoped.  These helpers deliberately do not expose a
track-level label: tracks are witnesses for scheduling, while the verification
key remains ``(source, query, unit)``.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass


QUERY_TYPE_PROJECTIONS = {
    "Q1": frozenset({"vehicle", "cyclist"}),
    "Q2": frozenset({"pedestrian", "cyclist"}),
}


@dataclass(frozen=True)
class UnitWindow:
    """One center-anchored oracle unit, including the frozen tail rule."""

    unit_id: int
    anchor_seconds: float
    start_seconds: float
    end_seconds: float


def deterministic_split(source_dataset: str, session_id: str) -> str:
    """Assign a session to a stable 70/15/15 pool role.

    Assignment is independent of query labels and source weak tags.  The
    ``pool_audit`` role is an internal independent-pool audit slice, not the
    unopened paper held-out split.
    """

    identity = f"mf_psvr_cycle1_split_v1|{source_dataset}|{session_id}"
    bucket = int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16], 16) % 100
    if bucket < 70:
        return "model_train"
    if bucket < 85:
        return "model_calibration"
    return "pool_audit"


def unit_windows(duration_seconds: float, unit_seconds: float = 10.0) -> tuple[UnitWindow, ...]:
    """Return the exact center-window unitization used by the two-video oracle.

    Nominal anchors are 5, 15, 25, ... seconds.  When the final nominal anchor
    exceeds the media duration, the duration itself becomes the anchor and the
    final window is the preceding half-window.  It can therefore overlap the
    preceding unit; this is intentional frozen behavior, not a remainder bin.
    """

    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and positive")
    if not math.isfinite(unit_seconds) or unit_seconds <= 0:
        raise ValueError("unit_seconds must be finite and positive")
    count = int(math.ceil(duration_seconds / unit_seconds))
    half_window = unit_seconds / 2.0
    rows = []
    for index in range(count):
        anchor = index * unit_seconds + half_window
        if anchor > duration_seconds:
            anchor = duration_seconds
        rows.append(UnitWindow(
            unit_id=index,
            anchor_seconds=round(anchor, 6),
            start_seconds=round(max(0.0, anchor - half_window), 6),
            end_seconds=round(min(duration_seconds, anchor + half_window), 6),
        ))
    return tuple(rows)


def frame_bounds(
    start_seconds: float,
    end_seconds: float,
    fps: float,
    frame_count: int,
) -> tuple[int, int]:
    """Map a time window to the frozen inclusive, decodable frame domain."""

    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive")
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("frame window must have non-negative start and positive duration")
    start_frame = min(frame_count - 1, max(0, int(start_seconds * fps)))
    end_frame = min(
        frame_count - 1,
        max(start_frame, int(math.ceil(end_seconds * fps)) - 1),
    )
    return start_frame, end_frame


def project_generic_label(generic_label: str, involved_object: str, query_id: str) -> str:
    """Apply the immutable Q1/Q2 type projection without consulting free text."""

    if query_id not in QUERY_TYPE_PROJECTIONS:
        raise ValueError(f"unknown query_id: {query_id}")
    label = str(generic_label).strip().lower()
    actor = str(involved_object).strip().lower()
    if label == "abstain":
        return "abstain"
    if label == "positive" and actor in QUERY_TYPE_PROJECTIONS[query_id]:
        return "positive"
    return "negative"


def verification_key(source_id: str, query_id: str, unit_id: int) -> tuple[str, str, int]:
    """Return the only key on which a physical oracle result may be deduplicated."""

    if query_id not in QUERY_TYPE_PROJECTIONS:
        raise ValueError(f"unknown query_id: {query_id}")
    if unit_id < 0:
        raise ValueError("unit_id must be non-negative")
    return str(source_id), query_id, int(unit_id)
