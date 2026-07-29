"""Exact input identity and validation for the V3 1,475-unit full grid.

This module is deliberately independent of the frozen preflight implementation.
It adds one narrowly scoped rule: a truncated final unit uses source-anchored
``k / sampling_fps`` targets that do not exceed the true video endpoint.  It
never pads, repeats, invents an off-grid endpoint, or changes a normal unit.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from .oracle_protocol import rgb_content_hash
from .oracle_v3_manifest import canonical_hash, load_json, sha256_file, validate_payload_hash


EXPERIMENT_ID = "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID"
QUERY_ID = "Q_DRIVER_RESPONSE_V1"
SAMPLING_FPS = 2.0
FULL_UNIT_SECONDS = 10.0
VIDEO_ORDER = ("DALI", "HANGZHOU", "WUHAN")
EXPECTED_UNITS_BY_VIDEO = {"DALI": 567, "HANGZHOU": 561, "WUHAN": 347}
EXPECTED_UNIT_COUNT = 1475
EXPECTED_FRAME_OCCURRENCES = 30932
EXPECTED_TAILS = {
    "DALI_u0566": {"video_id": "DALI", "frame_count": 12},
    "HANGZHOU_u0560": {"video_id": "HANGZHOU", "frame_count": 2},
    "WUHAN_u0346": {"video_id": "WUHAN", "frame_count": 6},
}


def full_grid_sample_indices(
    clip_start: float,
    clip_end: float,
    video_fps: float,
    sampling_fps: float = SAMPLING_FPS,
) -> tuple[str, list[dict[str, int | float]]]:
    """Return the frozen normal or truncated-final sampling grid.

    Normal units retain the V3 endpoint-inclusive rule.  A duration that does
    not contain an integral number of sampling intervals is legal only as a
    shorter final unit and receives all source-anchored targets ``k/fps`` with
    ``k/fps <= duration``.  The true endpoint remains unit/K3 metadata but is
    not converted into an off-grid visual target.
    """

    values = (clip_start, clip_end, video_fps, sampling_fps)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("sampling parameters must be finite")
    if clip_start < 0 or clip_end <= clip_start or video_fps <= 0 or sampling_fps <= 0:
        raise ValueError("invalid sampling interval or rate")
    duration = clip_end - clip_start
    intervals_float = duration * sampling_fps
    rounded = int(round(intervals_float))
    integral = math.isclose(intervals_float, rounded, rel_tol=0.0, abs_tol=1e-6)
    if integral:
        intervals = rounded
        unit_kind = "normal"
        endpoint_included = True
    else:
        if duration >= FULL_UNIT_SECONDS:
            raise ValueError("only a shorter final unit may use the truncated rule")
        intervals = int(math.floor(intervals_float + 1e-12))
        unit_kind = "truncated_final"
        endpoint_included = False
    start_frame = int(clip_start * video_fps)
    rows: list[dict[str, int | float]] = []
    for ordinal in range(intervals + 1):
        relative_target = ordinal / sampling_fps
        if relative_target > duration + 1e-9:
            raise RuntimeError("sampling target exceeds unit duration")
        source_offset = int(math.floor(relative_target * video_fps + 0.5))
        rows.append({
            "ordinal": ordinal,
            "target_relative_seconds": relative_target,
            "target_absolute_seconds": clip_start + relative_target,
            "requested_index": start_frame + source_offset,
        })
    requested = [int(row["requested_index"]) for row in rows]
    if len(set(requested)) != len(requested):
        raise ValueError("sampling rate exceeds unique source-frame support")
    if unit_kind == "normal" and not endpoint_included:
        raise AssertionError("normal unit lost endpoint")
    return unit_kind, rows


def decode_full_grid_unit(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_fps: float,
    sampling_fps: float = SAMPLING_FPS,
    *,
    include_rgb: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """Decode and authenticate the exact requested source frames for one unit."""

    import cv2

    unit_kind, targets = full_grid_sample_indices(
        clip_start, clip_end, video_fps, sampling_fps
    )
    by_index = {int(row["requested_index"]): row for row in targets}
    first = min(by_index)
    last = max(by_index)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    frames: list[dict[str, Any]] = []
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
        row: dict[str, Any] = {
            **by_index[requested_index],
            "decoded_index": decoded_index,
            "decoded_timestamp_seconds": float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0,
            "content_sha256": rgb_content_hash(rgb),
        }
        if include_rgb:
            row["rgb"] = rgb
        frames.append(row)
    cap.release()
    if len(frames) != len(targets):
        raise RuntimeError(f"decoded {len(frames)} of {len(targets)} required frames")
    return unit_kind, frames


def public_frame(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "rgb"}


def load_frozen_grid(unit_grid_path: Path) -> list[dict[str, Any]]:
    with unit_grid_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows:
        result.append({
            "video_id": row["video_id"],
            "unit_index": int(row["unit_id"]),
            "unit_id": row["candidate_id"],
            "start_time": float(row["start_time"]),
            "end_time": float(row["end_time"]),
            "duration_seconds": float(row["duration_seconds"]),
        })
    return result


def video_map(video_manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = load_json(video_manifest_path)
    rows = manifest.get("videos")
    if not isinstance(rows, list):
        raise RuntimeError("video manifest lacks videos")
    return {row["video_id"]: row for row in rows}


def expected_worker(video_id: str) -> str:
    if video_id not in VIDEO_ORDER:
        raise ValueError(f"unknown video: {video_id}")
    return f"V3_FULL_GRID_{video_id}"


def unit_output_path(video_id: str, unit_id: str) -> str:
    return (
        "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/"
        f"full_grid_execution/raw/{video_id}/{unit_id}.json"
    )


def unit_parsed_path(video_id: str, unit_id: str) -> str:
    return (
        "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/"
        f"full_grid_execution/parsed/{video_id}/{unit_id}.json"
    )


def validate_unit_manifest(manifest: dict[str, Any]) -> None:
    validate_payload_hash(manifest, "unit_manifest_payload_sha256")
    units = manifest.get("units")
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("unit-manifest experiment mismatch")
    if not isinstance(units, list) or len(units) != EXPECTED_UNIT_COUNT:
        raise RuntimeError("unit-manifest count mismatch")
    if manifest.get("exact_unit_count") != EXPECTED_UNIT_COUNT:
        raise RuntimeError("unit-manifest declared count mismatch")
    if [row.get("ordinal") for row in units] != list(range(EXPECTED_UNIT_COUNT)):
        raise RuntimeError("unit order is not canonical")
    ids = [row.get("unit_id") for row in units]
    if len(set(ids)) != EXPECTED_UNIT_COUNT or None in ids:
        raise RuntimeError("unit IDs are missing or duplicated")
    counts = Counter(row.get("video_id") for row in units)
    if dict(counts) != EXPECTED_UNITS_BY_VIDEO:
        raise RuntimeError(f"unit video partition mismatch: {dict(counts)}")
    tail_rows = [row for row in units if row.get("unit_kind") == "truncated_final"]
    if {row["unit_id"] for row in tail_rows} != set(EXPECTED_TAILS):
        raise RuntimeError("truncated tail membership mismatch")
    for row in units:
        if row.get("worker_id") != expected_worker(row["video_id"]):
            raise RuntimeError(f"worker binding mismatch: {row.get('unit_id')}")
        expected_frames = (
            EXPECTED_TAILS[row["unit_id"]]["frame_count"]
            if row["unit_id"] in EXPECTED_TAILS else 21
        )
        if row.get("frame_count") != expected_frames:
            raise RuntimeError(f"unit frame count mismatch: {row.get('unit_id')}")
        claimed = row.get("call_spec_sha256")
        unsigned = {key: value for key, value in row.items() if key != "call_spec_sha256"}
        if claimed != canonical_hash(unsigned):
            raise RuntimeError(f"unit call self-hash mismatch: {row.get('unit_id')}")


def validate_frame_manifest(
    manifest: dict[str, Any], unit_manifest: dict[str, Any]
) -> None:
    validate_payload_hash(manifest, "frame_manifest_payload_sha256")
    frames = manifest.get("frames")
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("frame-manifest experiment mismatch")
    if not isinstance(frames, list) or len(frames) != EXPECTED_FRAME_OCCURRENCES:
        raise RuntimeError("frame occurrence count mismatch")
    if manifest.get("exact_frame_occurrence_count") != EXPECTED_FRAME_OCCURRENCES:
        raise RuntimeError("declared frame occurrence count mismatch")
    if [row.get("global_ordinal") for row in frames] != list(
        range(EXPECTED_FRAME_OCCURRENCES)
    ):
        raise RuntimeError("frame order is not canonical")
    units = unit_manifest["units"]
    frame_rows_by_unit: dict[str, list[dict[str, Any]]] = {}
    for row in frames:
        frame_rows_by_unit.setdefault(row.get("unit_id"), []).append(row)
        if row.get("decoded_index") != row.get("requested_index"):
            raise RuntimeError(f"requested/decoded mismatch: {row.get('unit_id')}")
        if not isinstance(row.get("content_sha256"), str) or len(row["content_sha256"]) != 64:
            raise RuntimeError("invalid RGB content hash")
    if set(frame_rows_by_unit) != {row["unit_id"] for row in units}:
        raise RuntimeError("frame-manifest unit membership mismatch")
    for unit in units:
        rows = frame_rows_by_unit[unit["unit_id"]]
        if len(rows) != unit["frame_count"]:
            raise RuntimeError(f"frame count mismatch: {unit['unit_id']}")
        if [row["unit_frame_ordinal"] for row in rows] != list(range(len(rows))):
            raise RuntimeError(f"frame ordinals mismatch: {unit['unit_id']}")
        payload = [{
            "ordinal": row["unit_frame_ordinal"],
            "target_relative_seconds": row["target_relative_seconds"],
            "target_absolute_seconds": row["target_absolute_seconds"],
            "requested_index": row["requested_index"],
            "decoded_index": row["decoded_index"],
            "decoded_timestamp_seconds": row["decoded_timestamp_seconds"],
            "content_sha256": row["content_sha256"],
        } for row in rows]
        if canonical_hash(payload) != unit["frame_set_sha256"]:
            raise RuntimeError(f"unit frame-set hash mismatch: {unit['unit_id']}")
        if max(float(row["target_absolute_seconds"]) for row in rows) > (
            float(unit["end_time"]) + 1e-9
        ):
            raise RuntimeError(f"frame target overruns unit: {unit['unit_id']}")


def validate_worker_schedule(
    schedule: dict[str, Any], unit_manifest: dict[str, Any]
) -> None:
    validate_payload_hash(schedule, "worker_schedule_payload_sha256")
    workers = schedule.get("workers")
    if not isinstance(workers, list) or len(workers) != 3:
        raise RuntimeError("worker schedule must contain three workers")
    units = unit_manifest["units"]
    assigned: list[str] = []
    for worker in workers:
        expected = expected_worker(worker["video_id"])
        if worker.get("worker_id") != expected:
            raise RuntimeError("worker identity mismatch")
        expected_ids = [row["unit_id"] for row in units if row["worker_id"] == expected]
        if worker.get("unit_ids") != expected_ids:
            raise RuntimeError(f"worker unit list mismatch: {expected}")
        if worker.get("exact_call_count") != len(expected_ids):
            raise RuntimeError(f"worker call count mismatch: {expected}")
        assigned.extend(expected_ids)
    if len(assigned) != EXPECTED_UNIT_COUNT or set(assigned) != {
        row["unit_id"] for row in units
    }:
        raise RuntimeError("worker partition is not an exact disjoint union")


def fraction_fps(value: str) -> float:
    return float(Fraction(value))


def canonical_file_bindings(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    return [{
        "path": str(path.relative_to(root)),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    } for path in sorted(paths)]
