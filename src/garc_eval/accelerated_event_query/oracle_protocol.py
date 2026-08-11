"""Strict, deterministic input and output protocol for the AEQ operational oracle."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


RESPONSE_KEYS = {
    "label",
    "event_start_sec",
    "event_end_sec",
    "required_response",
    "cause",
    "confidence",
    "evidence",
    "unknown_reason",
}
LABELS = {"relevant", "not_relevant", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
RESPONSES = {"slowdown", "brake", "avoid"}


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def rgb_content_hash(rgb: Any) -> str:
    """Match the established strict-oracle RGB identity convention."""
    digest = hashlib.sha256()
    digest.update(str(rgb.shape).encode("ascii"))
    digest.update(str(rgb.dtype).encode("ascii"))
    digest.update(rgb.tobytes(order="C"))
    return digest.hexdigest()


def exact_sample_indices(
    clip_start: float,
    clip_end: float,
    video_fps: float,
    sampling_fps: float,
) -> list[dict]:
    """Return nearest source frames for an endpoint-inclusive exact-rate grid.

    The temporal targets, not a floored frame interval, define the requested
    sampling rate. A 10-second unit therefore has 21 targets at 2 fps and 41
    targets at 4 fps, including both 0 and 10 seconds.
    """
    values = (clip_start, clip_end, video_fps, sampling_fps)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("sampling parameters must be finite")
    if clip_start < 0 or clip_end <= clip_start or video_fps <= 0 or sampling_fps <= 0:
        raise ValueError("invalid sampling interval or rate")
    duration = clip_end - clip_start
    intervals_float = duration * sampling_fps
    intervals = int(round(intervals_float))
    if not math.isclose(intervals_float, intervals, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("clip duration must contain an integral number of sampling intervals")
    start_frame = int(clip_start * video_fps)
    rows = []
    for ordinal in range(intervals + 1):
        relative_target = ordinal / sampling_fps
        source_offset = int(math.floor(relative_target * video_fps + 0.5))
        rows.append({
            "ordinal": ordinal,
            "target_relative_seconds": relative_target,
            "target_absolute_seconds": clip_start + relative_target,
            "requested_index": start_frame + source_offset,
        })
    requested = [row["requested_index"] for row in rows]
    if len(set(requested)) != len(requested):
        raise ValueError("sampling rate exceeds unique source-frame support")
    return rows


def extract_exact_frames(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_fps: float,
    sampling_fps: float,
) -> list[dict]:
    """Decode exactly the source frames selected by :func:`exact_sample_indices`."""
    import cv2

    targets = exact_sample_indices(clip_start, clip_end, video_fps, sampling_fps)
    by_index = {row["requested_index"]: row for row in targets}
    first = targets[0]["requested_index"]
    last = targets[-1]["requested_index"]
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    frames = []
    for requested_index in range(first, last + 1):
        ok, frame = cap.read()
        if not ok:
            break
        if requested_index not in by_index:
            continue
        decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        if decoded_index != requested_index:
            cap.release()
            raise RuntimeError(
                f"decoder index mismatch: requested {requested_index}, decoded {decoded_index}"
            )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        target = by_index[requested_index]
        frames.append({
            **target,
            "decoded_index": decoded_index,
            "decoded_timestamp_seconds": float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0,
            "content_sha256": rgb_content_hash(rgb),
            "rgb": rgb,
        })
    cap.release()
    if len(frames) != len(targets):
        raise RuntimeError(f"decoded {len(frames)} of {len(targets)} required frames")
    return frames


def parse_response_strict(raw: str) -> tuple[dict, str]:
    """Parse one whole JSON object and enforce all label-conditional invariants."""
    if not isinstance(raw, str):
        return {}, "response_not_string"
    try:
        parsed = json.loads(raw.strip())
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"
    if not isinstance(parsed, dict):
        return {}, "json_not_object"
    if set(parsed) != RESPONSE_KEYS:
        return parsed, "schema_mismatch"
    label = parsed["label"]
    confidence = parsed["confidence"]
    if not isinstance(label, str) or label not in LABELS:
        return parsed, "invalid_label"
    if not isinstance(confidence, str) or confidence not in CONFIDENCES:
        return parsed, "invalid_confidence"
    evidence = parsed["evidence"]
    if not isinstance(evidence, str) or not evidence.strip():
        return parsed, "invalid_evidence"
    cause = parsed["cause"]
    if cause is not None and (not isinstance(cause, str) or not cause.strip()):
        return parsed, "invalid_cause"
    unknown_reason = parsed["unknown_reason"]
    if unknown_reason is not None and (
        not isinstance(unknown_reason, str) or not unknown_reason.strip()
    ):
        return parsed, "invalid_unknown_reason"
    responses = parsed["required_response"]
    if not isinstance(responses, list) or any(
        not isinstance(response, str) or response not in RESPONSES for response in responses
    ):
        return parsed, "invalid_required_response"
    if len(set(responses)) != len(responses):
        return parsed, "duplicate_required_response"

    start = parsed["event_start_sec"]
    end = parsed["event_end_sec"]
    if label == "relevant":
        if not responses:
            return parsed, "missing_relevant_response"
        if not isinstance(cause, str) or not cause.strip():
            return parsed, "missing_relevant_cause"
        if unknown_reason is not None:
            return parsed, "relevant_has_unknown_reason"
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(float(start))
            or not math.isfinite(float(end))
            or not 0.0 <= float(start) <= float(end) <= 10.0
        ):
            return parsed, "invalid_relevant_boundary"
    elif label == "not_relevant":
        if start is not None or end is not None:
            return parsed, "not_relevant_has_boundary"
        if responses:
            return parsed, "not_relevant_has_response"
        if cause is not None:
            return parsed, "not_relevant_has_cause"
        if unknown_reason is not None:
            return parsed, "not_relevant_has_unknown_reason"
    else:
        if start is not None or end is not None:
            return parsed, "unknown_has_boundary"
        if responses:
            return parsed, "unknown_has_response"
        if not isinstance(unknown_reason, str) or not unknown_reason.strip():
            return parsed, "unknown_missing_reason"
    return parsed, "ok"


def public_frame_record(frame: dict) -> dict:
    return {key: value for key, value in frame.items() if key != "rgb"}
