import hashlib

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_manifest import (
    EXPECTED_TAILS,
    EXPECTED_UNITS_BY_VIDEO,
    canonical_hash,
    expected_worker,
    validate_frame_manifest,
    validate_unit_manifest,
    validate_worker_schedule,
)


def synthetic_manifests():
    units = []
    frames = []
    global_ordinal = 0
    ordinal = 0
    for video_id, count in EXPECTED_UNITS_BY_VIDEO.items():
        for index in range(count):
            unit_id = f"{video_id}_u{index:04d}"
            frame_count = EXPECTED_TAILS.get(unit_id, {}).get("frame_count", 21)
            kind = "truncated_final" if unit_id in EXPECTED_TAILS else "normal"
            end = 10.0 * (index + 1) if kind == "normal" else 10.0 * index + (frame_count - 0.9) / 2
            payload = []
            for frame_ordinal in range(frame_count):
                row = {
                    "ordinal": frame_ordinal,
                    "target_relative_seconds": frame_ordinal / 2,
                    "target_absolute_seconds": 10.0 * index + frame_ordinal / 2,
                    "ideal_requested_index": index * 300 + frame_ordinal * 15,
                    "requested_index": index * 300 + frame_ordinal * 15,
                    "source_boundary_resolution": "exact_ideal_cfr_index",
                    "decoded_index": index * 300 + frame_ordinal * 15,
                    "decoded_timestamp_seconds": 10.0 * index + frame_ordinal / 2,
                    "content_sha256": hashlib.sha256(f"{unit_id}:{frame_ordinal}".encode()).hexdigest(),
                }
                payload.append(row)
                frames.append({
                    "global_ordinal": global_ordinal,
                    "unit_ordinal": ordinal,
                    "unit_id": unit_id,
                    "video_id": video_id,
                    "unit_kind": kind,
                    "unit_frame_ordinal": frame_ordinal,
                    **{key: value for key, value in row.items() if key != "ordinal"},
                })
                global_ordinal += 1
            unit = {
                "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID",
                "ordinal": ordinal,
                "unit_id": unit_id,
                "video_id": video_id,
                "start_time": 10.0 * index,
                "end_time": end,
                "unit_kind": kind,
                "frame_count": frame_count,
                "frame_set_sha256": canonical_hash(payload),
                "worker_id": expected_worker(video_id),
            }
            unit["call_spec_sha256"] = canonical_hash(unit)
            units.append(unit)
            ordinal += 1
    unit_manifest = {
        "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID",
        "exact_unit_count": 1475,
        "units": units,
    }
    unit_manifest["unit_manifest_payload_sha256"] = canonical_hash(unit_manifest)
    frame_manifest = {
        "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID",
        "exact_frame_occurrence_count": len(frames),
        "frames": frames,
    }
    frame_manifest["frame_manifest_payload_sha256"] = canonical_hash(frame_manifest)
    workers = []
    for video_id in EXPECTED_UNITS_BY_VIDEO:
        ids = [row["unit_id"] for row in units if row["video_id"] == video_id]
        workers.append({
            "worker_id": expected_worker(video_id),
            "video_id": video_id,
            "unit_ids": ids,
            "exact_call_count": len(ids),
        })
    schedule = {"workers": workers}
    schedule["worker_schedule_payload_sha256"] = canonical_hash(schedule)
    return unit_manifest, frame_manifest, schedule


def test_exact_synthetic_manifests_validate_1475_and_30932():
    units, frames, schedule = synthetic_manifests()
    validate_unit_manifest(units)
    validate_frame_manifest(frames, units)
    validate_worker_schedule(schedule, units)


def test_manifest_validator_rejects_duplicate_unit_identity():
    units, _, _ = synthetic_manifests()
    units["units"][1]["unit_id"] = units["units"][0]["unit_id"]
    units["unit_manifest_payload_sha256"] = canonical_hash({
        key: value for key, value in units.items() if key != "unit_manifest_payload_sha256"
    })
    with pytest.raises(RuntimeError, match="duplicated"):
        validate_unit_manifest(units)
