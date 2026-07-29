#!/usr/bin/env python3
"""Decode and freeze the exact V3 full-grid inputs without model inference."""

from __future__ import annotations

import json
import math
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from garc_eval.accelerated_event_query.oracle_v3_full_grid_finalizer import (
    EVENT_RELATION_SCHEMA,
    UNIT_LABEL_SCHEMA,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_manifest import (
    EXPECTED_FRAME_OCCURRENCES,
    EXPECTED_TAILS,
    EXPECTED_UNIT_COUNT,
    EXPECTED_UNITS_BY_VIDEO,
    EXPERIMENT_ID,
    QUERY_ID,
    VIDEO_ORDER,
    decode_full_grid_unit,
    expected_worker,
    fraction_fps,
    load_frozen_grid,
    public_frame,
    validate_frame_manifest,
    validate_processed_input_manifest,
    validate_unit_manifest,
    validate_worker_schedule,
    video_map,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_package import (
    BASE,
    PACKAGE,
    ROOT,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner import (
    CALL_RESERVATION_WALL_SECONDS,
    ENVELOPE_A100_GPU_HOURS,
    MODEL_LOAD_RESERVATION_WALL_SECONDS,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_processing import (
    load_frozen_processor,
    prepare_frozen_model_inputs,
    runtime_environment_identity,
    tensor_bundle_sha256,
    tensor_shapes,
)
from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    write_json_once,
)
from garc_eval.accelerated_event_query.oracle_protocol import rgb_content_hash


UNIT_GRID = ROOT / "outputs/accelerated_event_query_v1/video_manifests/frozen_unit_grid_v1.csv"
VIDEO_MANIFEST = ROOT / "outputs/accelerated_event_query_v1/video_manifests/frozen_videos_v1.json"
PROMPT = BASE / "configs/query_prompt_v3_model_relative.txt"
SCHEMA = BASE / "schemas/oracle_v3_output_schema.json"
CONFIG = BASE / "configs/oracle_v3_execution_config.json"
K3 = BASE / "k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json"
MODEL_MANIFEST = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/MODEL_FILE_MANIFEST_V2.json"
MODEL_AUDIT = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/MODEL_IDENTITY_AUDIT_V1.json"


GPU_PAIRS = {"DALI": [1, 2], "HANGZHOU": [3, 5], "WUHAN": [6, 7]}


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = canonical_hash(value)
    return value


def _contact_sheet(frames: list[dict[str, Any]], destination: Path, title: str) -> None:
    from PIL import Image, ImageDraw

    columns = min(4, len(frames))
    thumb_w, thumb_h, label_h, margin = 320, 180, 24, 12
    rows = math.ceil(len(frames) / columns)
    canvas = Image.new(
        "RGB",
        (columns * thumb_w + (columns + 1) * margin,
         44 + rows * (thumb_h + label_h) + (rows + 1) * margin),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 12), title, fill="black")
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        x = margin + column * (thumb_w + margin)
        y = 44 + margin + row * (thumb_h + label_h + margin)
        image = Image.fromarray(frame["rgb"])
        image.thumbnail((thumb_w, thumb_h))
        canvas.paste(image, (x, y))
        draw.text(
            (x, y + thumb_h + 2),
            f"#{frame['ordinal']} target={frame['target_absolute_seconds']:.3f}s "
            f"src={frame['decoded_index']}",
            fill="black",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG", optimize=False)


def _processor_tail_audit(
    processed_rows: dict[str, dict[str, Any]],
    unit_rows: dict[str, dict[str, Any]],
    *,
    processor_class: str,
) -> dict[str, Any]:
    rows = []
    for unit_id in EXPECTED_TAILS:
        processed = processed_rows[unit_id]
        unit = unit_rows[unit_id]
        rows.append({
            "unit_id": unit_id,
            "unit_kind": "truncated_final",
            "true_duration_seconds": unit["duration_seconds"],
            "supplied_frame_count": unit["frame_count"],
            "supplied_sampling_fps": 2.0,
            "model_visible_grid_duration_seconds": (unit["frame_count"] - 1) / 2.0,
            "processor_tensor_shapes": processed["tensor_shapes"],
            "processor_tensor_bundle_sha256": processed["processed_input_sha256"],
            "do_sample_frames": False,
            "padding_or_repeated_source_frame_added_by_protocol": False,
        })
    result = {
        "status": "PASS_PROCESSOR_ONLY_NO_CHECKPOINT_WEIGHTS_LOADED_NO_INFERENCE",
        "processor_class": processor_class,
        "model_path_used_for_processor_assets_only": "models/Qwen3-VL-32B-Instruct-FP8",
        "prompt_sha256": sha256_file(PROMPT),
        "tail_units": rows,
        "checkpoint_weights_loaded": False,
        "model_generate_called": False,
    }
    return self_hash(result, "processor_audit_payload_sha256")


def _video_stream_audit(videos: dict[str, dict[str, Any]]) -> dict[str, Any]:
    import cv2

    rows = []
    for video_id in VIDEO_ORDER:
        video = videos[video_id]
        path = ROOT / video["path"]
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video for stream audit: {video_id}")
        frame_count = int(round(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        decoder_fps = float(cap.get(cv2.CAP_PROP_FPS))
        last_index = frame_count - 1
        cap.set(cv2.CAP_PROP_POS_FRAMES, last_index)
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f"cannot decode final video-stream frame: {video_id}")
        decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        timestamp = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        cap.release()
        if decoded_index != last_index:
            raise RuntimeError(f"final stream index mismatch: {video_id}")
        rows.append({
            "video_id": video_id,
            "path": video["path"],
            "video_sha256": video["sha256"],
            "container_duration_seconds": video["duration_seconds"],
            "nominal_fps": video["nominal_fps"],
            "decoder_reported_fps": decoder_fps,
            "decoded_frame_count": frame_count,
            "last_available_decoded_index": last_index,
            "last_available_decoded_timestamp_seconds": timestamp,
            "last_available_rgb_sha256": rgb_content_hash(rgb),
            "container_duration_may_exceed_video_stream_support": (
                timestamp < float(video["duration_seconds"])
            ),
        })
    return self_hash({
        "status": "FROZEN_VIDEO_STREAM_BOUNDARY_AUDIT",
        "source": "OpenCV decoder frame-count and exact final-frame decode",
        "videos": rows,
    }, "video_stream_audit_payload_sha256")


def _failure_policy() -> str:
    return """# Full-Grid Failure Policy

Status: `FROZEN_BEFORE_FULL_GRID_EXECUTION`

The only production entry point is the sealed three-process supervisor. It
launches exactly the frozen workers, monitors child exit status and operation
leases, and terminates all peers after any nonzero/abrupt death or global stop.
Workers reject direct launch without the supervisor authority and parent PID.

The execution uses one global fail-stop coordinator. Authentication, frame or
processed-input mismatch, an unknown runner/parser, wrong GPU, duplicate or
extra call, retry, fourth load/reload, ledger transition failure, path
collision, cost-shield breach, generation failure, uncertain interruption, or
post-load process fault prevents every worker from issuing another
`INFERENCE_STARTED` event. Already-started calls may terminate and all raw and
ledger evidence is preserved.

The original approval permits exactly three uninterrupted model loads and no
post-load restart. A continuation is a new experiment: authenticated completed
records may be proposed for reuse, but any call with a durable start and no
terminal record remains uncertain and cannot be retried without explicit new
retry authority.

Any missing, failed, uncertain, extra, retried, unauthenticated, or cost-invalid
run is incomplete. It produces `INSUFFICIENT_EVIDENCE` or the higher-priority
frozen abort decision, no formal unit-label table, no formal K3 relation, and no
downstream access. Formal artifacts live in a versioned evaluator-only release;
only the final atomic `FORMAL_REFERENCE_RELEASE.json` pointer makes the release
authoritative.
"""


def _hiding_audit() -> str:
    return """# Full-Grid Label-Hiding Audit

Status: `FROZEN_INTERFACE_IMPLEMENTED_TEST_REQUIRED`

Three layers are separate:

1. `EvaluatorOnlyLabelStore` owns exhaustive full-grid labels and requires an
   opaque evaluator capability. Its controller lookup method fails closed.
2. Runtime VERIFY results are produced causally by the selected runtime action
   and signed with Ed25519. The public runtime history receives only the public
   verification key and completed signed results; it cannot mint results or
   request arbitrary full-grid unit IDs.
3. Public controller state contains public observations plus already completed
   signed VERIFY history only. SCAN, runtime K3, and action selection receive no
   evaluator path, object, event ID, future label, or boundary.

The evaluator reference and runtime K3 use different constructors and process
entry points. Formal evaluator directories are owned by frozen evaluator UID 0
with mode `0700`; files use `0600`. Every later controller/replay process must
run as UID/GID 65534 with zero effective capabilities and with the evaluator
execution root absent from its container mount namespace. A real fork/setuid
test must prove that a guessed absolute evaluator sentinel path raises
`PermissionError`. Import-root nonoverlap alone is explicitly insufficient.

Tests also require hidden-label permutation invariance, rejection of
forged/future results, rejection of direct lookup, path-root non-overlap, and
same-host different-UID guessed-path denial. No replay or controller is run in
this preregistration stage.
"""


def main() -> None:
    if PACKAGE.exists() and any(PACKAGE.iterdir()):
        raise RuntimeError(f"refusing to overwrite existing package: {PACKAGE}")
    PACKAGE.mkdir(parents=True, exist_ok=True)
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    grid = load_frozen_grid(UNIT_GRID)
    videos = video_map(VIDEO_MANIFEST)
    if len(grid) != EXPECTED_UNIT_COUNT:
        raise RuntimeError("frozen grid no longer contains 1475 units")
    if Counter(row["video_id"] for row in grid) != Counter(EXPECTED_UNITS_BY_VIDEO):
        raise RuntimeError("frozen grid video counts changed")
    if list(dict.fromkeys(row["video_id"] for row in grid)) != list(VIDEO_ORDER):
        raise RuntimeError("frozen grid video order changed")
    for video_id, video in videos.items():
        if sha256_file(ROOT / video["path"]) != video["sha256"]:
            raise RuntimeError(f"source video hash mismatch: {video_id}")
    stream_audit = _video_stream_audit(videos)
    model_path = ROOT / "models/Qwen3-VL-32B-Instruct-FP8"
    processor = load_frozen_processor(model_path)
    processor_class = f"{processor.__class__.__module__}.{processor.__class__.__qualname__}"
    processor_environment = runtime_environment_identity()
    prompt = PROMPT.read_text(encoding="utf-8")

    flat_frames: list[dict[str, Any]] = []
    unit_rows: list[dict[str, Any]] = []
    processed_input_rows: list[dict[str, Any]] = []
    tail_frames: dict[str, list[dict[str, Any]]] = {}
    global_frame_ordinal = 0
    for ordinal, grid_row in enumerate(grid):
        video = videos[grid_row["video_id"]]
        kind, decoded = decode_full_grid_unit(
            ROOT / video["path"],
            grid_row["start_time"], grid_row["end_time"],
            fraction_fps(video["nominal_fps"]), include_rgb=True,
        )
        public = [public_frame(row) for row in decoded]
        frame_set_sha = canonical_hash(public)
        processed_inputs = prepare_frozen_model_inputs(
            processor,
            prompt=prompt,
            rgb_frames=[row["rgb"] for row in decoded],
            sampling_fps=2.0,
        )
        processed_sha = tensor_bundle_sha256(processed_inputs)
        shapes = tensor_shapes(processed_inputs)
        if not shapes.get("input_ids"):
            raise RuntimeError(
                f"processor produced no authenticated tensor bundle: {grid_row['unit_id']}"
            )
        worker_id = expected_worker(grid_row["video_id"])
        ledger = f"attempt_ledgers/{worker_id}.jsonl"
        base = {
            "experiment_id": EXPERIMENT_ID,
            "ordinal": ordinal,
            **grid_row,
            "unit_kind": kind,
            "sampling_fps": 2.0,
            "sampling_semantics": (
                "endpoint-inclusive source-anchored exact 2-fps grid"
                if kind == "normal" else
                "truncated-final source-anchored k/2 targets not exceeding true endpoint"
            ),
            "frame_count": len(public),
            "frame_set_sha256": frame_set_sha,
            "expected_processed_input_sha256": processed_sha,
            "source_video_sha256": video["sha256"],
            "worker_id": worker_id,
            "physical_gpu_ids": GPU_PAIRS[grid_row["video_id"]],
            "raw_output_relative_path": f"raw/{grid_row['video_id']}/{grid_row['unit_id']}.json",
            "parsed_output_relative_path": f"parsed/{grid_row['video_id']}/{grid_row['unit_id']}.json",
            "attempt_ledger_relative_path": ledger,
            "model_input_tail_representation": {
                "true_duration_seconds": grid_row["duration_seconds"],
                "supplied_frame_count": len(public),
                "supplied_sampling_fps": 2.0,
                "grid_duration_seconds": (len(public) - 1) / 2.0,
                "prompt_bytes_unchanged": True,
                "finite_stream_boundary_resolution": "retain ideal request and use unique nearest available final video frame only when ideal index exceeds stream support",
            },
        }
        base["call_spec_sha256"] = canonical_hash(base)
        unit_rows.append(base)
        processed_input_rows.append({
            "unit_ordinal": ordinal,
            "unit_id": grid_row["unit_id"],
            "video_id": grid_row["video_id"],
            "unit_kind": kind,
            "frame_count": len(public),
            "frame_set_sha256": frame_set_sha,
            "processed_input_sha256": processed_sha,
            "tensor_shapes": shapes,
        })
        for frame in public:
            flat_frames.append({
                "global_ordinal": global_frame_ordinal,
                "unit_ordinal": ordinal,
                "unit_id": grid_row["unit_id"],
                "video_id": grid_row["video_id"],
                "unit_kind": kind,
                "unit_frame_ordinal": frame["ordinal"],
                **{key: value for key, value in frame.items() if key != "ordinal"},
            })
            global_frame_ordinal += 1
        if kind == "truncated_final":
            tail_frames[grid_row["unit_id"]] = decoded

    if len(flat_frames) != EXPECTED_FRAME_OCCURRENCES:
        raise RuntimeError(f"unexpected frame occurrence count: {len(flat_frames)}")
    if set(tail_frames) != set(EXPECTED_TAILS):
        raise RuntimeError(f"tail membership mismatch: {sorted(tail_frames)}")
    for unit_id, expected in EXPECTED_TAILS.items():
        if len(tail_frames[unit_id]) != expected["frame_count"]:
            raise RuntimeError(f"tail frame count mismatch: {unit_id}")

    unit_manifest = self_hash({
        "status": "FROZEN_EXACT_1475_UNIT_CALL_MANIFEST",
        "experiment_id": EXPERIMENT_ID,
        "query_id": QUERY_ID,
        "exact_unit_count": EXPECTED_UNIT_COUNT,
        "canonical_order": "frozen video-manifest order DALI,HANGZHOU,WUHAN then ascending unit index",
        "unit_grid": binding(UNIT_GRID),
        "video_manifest": binding(VIDEO_MANIFEST),
        "units": unit_rows,
    }, "unit_manifest_payload_sha256")
    frame_manifest = self_hash({
        "status": "FROZEN_EXACT_DECODED_FULL_GRID_FRAMES",
        "experiment_id": EXPERIMENT_ID,
        "exact_unit_count": EXPECTED_UNIT_COUNT,
        "exact_frame_occurrence_count": len(flat_frames),
        "unique_video_frame_identity_count": len({
            (row["video_id"], row["decoded_index"], row["content_sha256"])
            for row in flat_frames
        }),
        "duplicate_occurrences_are_only_explicit_shared_unit_endpoints": True,
        "finite_video_stream_boundary_rule": "ideal CFR request is retained; a right-boundary request beyond stream support resolves to the unique nearest available final frame; repeated-frame padding is forbidden",
        "frames": flat_frames,
    }, "frame_manifest_payload_sha256")
    processed_input_manifest = self_hash({
        "status": "FROZEN_EXPECTED_PROCESSOR_TENSOR_IDENTITY_FOR_ALL_UNITS",
        "experiment_id": EXPERIMENT_ID,
        "exact_unit_count": EXPECTED_UNIT_COUNT,
        "processor_class": processor_class,
        "processor_environment": processor_environment,
        "processor_assets_path": str(model_path.relative_to(ROOT)),
        "processor_assets_manifest": binding(MODEL_MANIFEST),
        "prompt": binding(PROMPT),
        "do_sample_frames": False,
        "sampling_fps": 2.0,
        "checkpoint_weights_loaded": False,
        "model_generate_called": False,
        "units": processed_input_rows,
    }, "processed_input_manifest_payload_sha256")
    validate_unit_manifest(unit_manifest)
    validate_frame_manifest(frame_manifest, unit_manifest)
    validate_processed_input_manifest(processed_input_manifest, unit_manifest)
    write_json_once(PACKAGE / "FULL_GRID_VIDEO_STREAM_AUDIT.json", stream_audit)
    write_json_once(PACKAGE / "FULL_GRID_UNIT_MANIFEST.json", unit_manifest)
    write_json_once(PACKAGE / "FULL_GRID_FRAME_MANIFEST.json", frame_manifest)
    write_json_once(
        PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json", processed_input_manifest
    )

    workers = []
    for video_id in VIDEO_ORDER:
        ids = [row["unit_id"] for row in unit_rows if row["video_id"] == video_id]
        ordinals = [row["ordinal"] for row in unit_rows if row["video_id"] == video_id]
        workers.append({
            "worker_id": expected_worker(video_id),
            "video_id": video_id,
            "physical_gpu_ids": GPU_PAIRS[video_id],
            "unit_ordinal_start": min(ordinals),
            "unit_ordinal_end_inclusive": max(ordinals),
            "unit_ids": ids,
            "exact_call_count": len(ids),
            "raw_output_shard_relative_path": f"raw/{video_id}",
            "parsed_output_shard_relative_path": f"parsed/{video_id}",
            "attempt_ledger_relative_path": f"attempt_ledgers/{expected_worker(video_id)}.jsonl",
            "model_load_events": ["MODEL_LOAD_STARTED", "MODEL_LOAD_COMPLETED"],
            "expected_successful_call_events": 4 * len(ids),
            "dynamic_reassignment": False,
            "direct_launch_allowed": False,
            "required_parent": "sealed_global_supervisor",
        })
    schedule = self_hash({
        "status": "FROZEN_THREE_STATIC_TWO_GPU_WORKERS",
        "experiment_id": EXPERIMENT_ID,
        "exact_worker_count": 3,
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "model_load_count": 3,
        "reload_count": 0,
        "retry_count": 0,
        "global_fail_stop": True,
        "sole_launcher": "scripts/launch_accelerated_event_query_oracle_v3_full_grid.py",
        "abrupt_worker_death_policy": "supervisor records global stop and terminates every live peer before another reservation",
        "workers": workers,
    }, "worker_schedule_payload_sha256")
    validate_worker_schedule(schedule, unit_manifest)
    write_json_once(PACKAGE / "FULL_GRID_WORKER_SCHEDULE.json", schedule)

    mean_call = 19.607711827941237
    observed_loads = {"DALI": 17.88046159595251, "HANGZHOU": 18.119151646271348,
                      "WUHAN": 17.44721078313887}
    estimated = 2 * (EXPECTED_UNIT_COUNT * mean_call + sum(observed_loads.values())) / 3600
    reserved = 2 * (
        EXPECTED_UNIT_COUNT * CALL_RESERVATION_WALL_SECONDS
        + 3 * MODEL_LOAD_RESERVATION_WALL_SECONDS
    ) / 3600
    cost = self_hash({
        "status": "FROZEN_FULL_GRID_COST_AND_RESERVATION_PLAN",
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "estimated_a100_gpu_hours": estimated,
        "estimated_parallel_wall_hours": 3.0931814077885096,
        "authorization_envelope_a100_gpu_hours": ENVELOPE_A100_GPU_HOURS,
        "planned_model_load_count": 3,
        "reload_count": 0,
        "retry_count": 0,
        "mean_2fps_call_wall_seconds": mean_call,
        "observed_preflight_load_seconds": observed_loads,
        "per_call_hard_reservation_wall_seconds": CALL_RESERVATION_WALL_SECONDS,
        "per_load_hard_reservation_wall_seconds": MODEL_LOAD_RESERVATION_WALL_SECONDS,
        "aggregate_reserved_a100_gpu_hours": reserved,
        "reservation_fits_envelope": reserved <= ENVELOPE_A100_GPU_HOURS,
        "cost_shield": "hash-chained actual plus in-flight reservation accounting; no start above envelope; operation above its reservation triggers global fail-stop",
        "unused_envelope_cannot_authorize_extra_calls_reloads_or_retries": True,
    }, "cost_estimate_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_COST_ESTIMATE.json", cost)

    decision_mapping = self_hash({
        "status": "FROZEN_BEFORE_FULL_GRID_EXECUTION",
        "allowed_decisions": [
            "FULL_GRID_PASS_REFERENCE_RELEASED",
            "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE",
            "FULL_GRID_ABORTED_AUTHENTICATION",
            "FULL_GRID_ABORTED_RUNTIME",
            "FULL_GRID_FAILED_PROTOCOL",
            "INSUFFICIENT_EVIDENCE",
        ],
        "priority": [
            {"rank": 1, "condition": "authentication or bound identity failure", "decision": "FULL_GRID_ABORTED_AUTHENTICATION"},
            {"rank": 2, "condition": "reload/retry/duplicate/ledger/GPU/cost/generation/runtime failure", "decision": "FULL_GRID_ABORTED_RUNTIME"},
            {"rank": 3, "condition": "fewer than 1475 authenticated terminal records or incomplete global state", "decision": "INSUFFICIENT_EVIDENCE"},
            {"rank": 4, "condition": "any parse_failure, schema violation, or K3 nondeterminism", "decision": "FULL_GRID_FAILED_PROTOCOL"},
            {"rank": 5, "condition": "global or per-video determined coverage below 0.99", "decision": "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"},
            {"rank": 6, "condition": "all preceding gates pass", "decision": "FULL_GRID_PASS_REFERENCE_RELEASED"},
        ],
        "construct_validity_diagnostics_are_non_gating": True,
    }, "decision_mapping_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_DECISION_MAPPING.json", decision_mapping)

    schemas = self_hash({
        "status": "FROZEN_OUTPUT_SCHEMAS_BEFORE_EXECUTION",
        "unit_labels_parquet": str(UNIT_LABEL_SCHEMA),
        "event_relation_parquet": str(EVENT_RELATION_SCHEMA),
        "coverage_report_required_fields": [
            "status", "oracle_coverage", "per_video_oracle_coverage", "label_counts",
            "parse_status_counts", "coverage_thresholds", "primary_relation_rule",
            "primary_relation_sha256", "determined_only_lower_bound_relation_sha256",
            "unknown_sensitive_upper_bound_diagnostic_relation_sha256",
            "parse_failure_regions_are_unevaluable", "coverage_payload_sha256",
        ],
        "canonical_row_order": {
            "unit_labels": "unit ordinal ascending",
            "event_relation": "video_id,start_time,end_time,event_id ascending",
        },
        "formal_primary_relation_filename": "k3_model_relative_event_relation.parquet",
        "only_release_commit_pointer_confers_formal_status": True,
    }, "output_schemas_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_OUTPUT_SCHEMAS.json", schemas)

    if os.geteuid() != 0:
        raise RuntimeError("evaluator package must be frozen by sealed evaluator UID 0")
    label_access_policy = self_hash({
        "status": "FROZEN_OS_ENFORCED_EVALUATOR_RUNTIME_SEPARATION",
        "evaluator_uid": 0,
        "evaluator_gid": 0,
        "runtime_uid": 65534,
        "runtime_gid": 65534,
        "evaluator_directory_mode": "0700",
        "evaluator_file_mode": "0600",
        "required_runtime_effective_capabilities_hex": "0000000000000000",
        "evaluator_output_root": str((BASE / "full_grid_execution").relative_to(ROOT)),
        "runtime_mount_rule": "the evaluator output root must be absent from the runtime controller container mount namespace",
        "runtime_entry_gate": "assert_runtime_os_isolation must pass under UID/GID 65534 before any later controller/replay episode",
        "same_uid_runtime_forbidden": True,
        "absolute_path_guessing_must_raise_permission_error": True,
    }, "label_access_policy_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_LABEL_ACCESS_POLICY.json", label_access_policy)

    (PACKAGE / "FULL_GRID_FAILURE_POLICY.md").write_text(_failure_policy(), encoding="utf-8")
    (PACKAGE / "FULL_GRID_LABEL_HIDING_AUDIT.md").write_text(_hiding_audit(), encoding="utf-8")

    unit_by_id = {row["unit_id"]: row for row in unit_rows}
    tail_audit_rows = []
    for unit_id, frames in tail_frames.items():
        sheet = PACKAGE / "tail_unit_audits" / f"{unit_id}.png"
        _contact_sheet(frames, sheet, f"{unit_id}: legal truncated final unit, all frozen frames")
        tail_audit_rows.append({
            "unit_id": unit_id,
            "video_id": unit_by_id[unit_id]["video_id"],
            "start_time": unit_by_id[unit_id]["start_time"],
            "end_time": unit_by_id[unit_id]["end_time"],
            "duration_seconds": unit_by_id[unit_id]["duration_seconds"],
            "frame_count": len(frames),
            "first_target_absolute_seconds": frames[0]["target_absolute_seconds"],
            "last_target_absolute_seconds": frames[-1]["target_absolute_seconds"],
            "first_decoded_index": frames[0]["decoded_index"],
            "last_decoded_index": frames[-1]["decoded_index"],
            "last_ideal_requested_index": frames[-1]["ideal_requested_index"],
            "last_requested_index": frames[-1]["requested_index"],
            "last_source_boundary_resolution": frames[-1]["source_boundary_resolution"],
            "first_decoded_timestamp_seconds": frames[0]["decoded_timestamp_seconds"],
            "last_decoded_timestamp_seconds": frames[-1]["decoded_timestamp_seconds"],
            "frame_set_sha256": unit_by_id[unit_id]["frame_set_sha256"],
            "contact_sheet": binding(sheet),
        })
    processor_audit = _processor_tail_audit(
        {row["unit_id"]: row for row in processed_input_rows},
        unit_by_id,
        processor_class=processor_class,
    )
    write_json_once(PACKAGE / "FULL_GRID_TAIL_PROCESSOR_AUDIT.json", processor_audit)
    md = [
        "# Full-Grid Tail Unit Audit", "", "Status: `FROZEN_PASS_NO_MODEL_INFERENCE`", "",
        "The three legal final units use only exact source-anchored `k/2` targets not",
        "exceeding the true endpoint. No target, padding frame, repeated final frame,",
        "or invented off-grid endpoint was added. The unchanged prompt is paired with",
        "model-visible frame count, 2-fps metadata, and true-duration provenance.", "",
        "| Unit | Video | Absolute interval | Frames | Last target | Ideal/resolved/decoded last index | Resolution | Contact SHA |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in tail_audit_rows:
        md.append(
            f"| {row['unit_id']} | {row['video_id']} | {row['start_time']:.6f}–{row['end_time']:.6f} | "
            f"{row['frame_count']} | {row['last_target_absolute_seconds']:.6f} | "
            f"{row['last_ideal_requested_index']}/{row['last_requested_index']}/{row['last_decoded_index']} | "
            f"{row['last_source_boundary_resolution']} | "
            f"`{row['contact_sheet']['sha256']}` |"
        )
    md.extend([
        "", "Processor-only audit:", "",
        f"- Status: `{processor_audit['status']}`.",
        f"- Processor: `{processor_audit['processor_class']}`.",
        "- Checkpoint weights loaded: `false`; `model.generate` called: `false`.",
        "- All 12/2/6-frame inputs produced deterministic tensor bundles without protocol padding.",
        "- Exact tensor shapes and hashes are in `FULL_GRID_TAIL_PROCESSOR_AUDIT.json`.", "",
        "Independent reviewers must inspect each PNG and the corresponding exact frame rows",
        "in `FULL_GRID_FRAME_MANIFEST.json` before returning GO.", "",
    ])
    (PACKAGE / "FULL_GRID_TAIL_UNIT_AUDIT.md").write_text("\n".join(md), encoding="utf-8")

    source_paths = [
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_manifest.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_control.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_hiding.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_package.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_runner.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_processing.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_supervisor.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_analyzer.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_finalizer.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_dry_run.py",
        ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_parser.py",
        ROOT / "src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py",
        ROOT / "src/garc_eval/accelerated_event_query/model_relative_event_relation.py",
        ROOT / "scripts/build_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/freeze_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/run_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/launch_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/analyze_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/finalize_accelerated_event_query_oracle_v3_full_grid.py",
        ROOT / "scripts/dry_run_accelerated_event_query_oracle_v3_full_grid.py",
    ]
    source_bindings = self_hash({
        "status": "FROZEN_SOURCE_BINDINGS",
        "source_commit": git_head,
        "sources": [binding(path) for path in source_paths],
    }, "source_bindings_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_SOURCE_BINDINGS.json", source_bindings)

    analyzer_binding = self_hash({
        "status": "FROZEN_BEFORE_FULL_GRID_EXECUTION",
        "source": binding(ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_analyzer.py"),
        "cli": binding(ROOT / "scripts/analyze_accelerated_event_query_oracle_v3_full_grid.py"),
        "unit_manifest": binding(PACKAGE / "FULL_GRID_UNIT_MANIFEST.json"),
        "frame_manifest": binding(PACKAGE / "FULL_GRID_FRAME_MANIFEST.json"),
        "processed_input_manifest": binding(PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json"),
        "worker_schedule": binding(PACKAGE / "FULL_GRID_WORKER_SCHEDULE.json"),
        "decision_mapping": binding(PACKAGE / "FULL_GRID_DECISION_MAPPING.json"),
        "output_schemas": binding(PACKAGE / "FULL_GRID_OUTPUT_SCHEMAS.json"),
        "checks": [
            "call and ledger accounting", "input/frame/frozen-processed hashes", "worker/GPU/supervisor binding",
            "three model loads and zero reload/retry", "strict parse and distribution",
            "unknown/parse_failure coverage", "runtime/cost", "K3 order and diagnostic independence",
            "staged reference identities and hashes",
        ],
    }, "analyzer_binding_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_ANALYZER_BINDING.json", analyzer_binding)
    finalizer_binding = self_hash({
        "status": "FROZEN_BEFORE_FULL_GRID_EXECUTION",
        "source": binding(ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_finalizer.py"),
        "cli": binding(ROOT / "scripts/finalize_accelerated_event_query_oracle_v3_full_grid.py"),
        "analyzer_binding": binding(PACKAGE / "FULL_GRID_ANALYZER_BINDING.json"),
        "decision_mapping": binding(PACKAGE / "FULL_GRID_DECISION_MAPPING.json"),
        "label_access_policy": binding(PACKAGE / "FULL_GRID_LABEL_ACCESS_POLICY.json"),
        "publication_rule": "versioned evaluator-only release is non-authoritative until the final atomic release pointer; mocks can never publish",
    }, "finalizer_binding_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_FINALIZER_BINDING.json", finalizer_binding)

    bindings = {
        "unit_grid": binding(UNIT_GRID),
        "video_manifest": binding(VIDEO_MANIFEST),
        "prompt": binding(PROMPT),
        "schema": binding(SCHEMA),
        "parser": binding(ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_parser.py"),
        "execution_config": binding(CONFIG),
        "k3_config": binding(K3),
        "model_file_manifest": binding(MODEL_MANIFEST),
        "model_identity_audit": binding(MODEL_AUDIT),
        "unit_manifest": binding(PACKAGE / "FULL_GRID_UNIT_MANIFEST.json"),
        "frame_manifest": binding(PACKAGE / "FULL_GRID_FRAME_MANIFEST.json"),
        "processed_input_manifest": binding(PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json"),
        "worker_schedule": binding(PACKAGE / "FULL_GRID_WORKER_SCHEDULE.json"),
        "cost_estimate": binding(PACKAGE / "FULL_GRID_COST_ESTIMATE.json"),
        "decision_mapping": binding(PACKAGE / "FULL_GRID_DECISION_MAPPING.json"),
        "output_schemas": binding(PACKAGE / "FULL_GRID_OUTPUT_SCHEMAS.json"),
        "tail_unit_audit": binding(PACKAGE / "FULL_GRID_TAIL_UNIT_AUDIT.md"),
        "tail_processor_audit": binding(PACKAGE / "FULL_GRID_TAIL_PROCESSOR_AUDIT.json"),
        "video_stream_audit": binding(PACKAGE / "FULL_GRID_VIDEO_STREAM_AUDIT.json"),
        "failure_policy": binding(PACKAGE / "FULL_GRID_FAILURE_POLICY.md"),
        "label_hiding_audit": binding(PACKAGE / "FULL_GRID_LABEL_HIDING_AUDIT.md"),
        "label_access_policy": binding(PACKAGE / "FULL_GRID_LABEL_ACCESS_POLICY.json"),
        "source_bindings": binding(PACKAGE / "FULL_GRID_SOURCE_BINDINGS.json"),
        "analyzer_binding": binding(PACKAGE / "FULL_GRID_ANALYZER_BINDING.json"),
        "finalizer_binding": binding(PACKAGE / "FULL_GRID_FINALIZER_BINDING.json"),
    }
    prereg = self_hash({
        "status": "FROZEN_BEFORE_FULL_GRID_EXECUTION",
        "experiment_id": EXPERIMENT_ID,
        "query_id": QUERY_ID,
        "source_commit": git_head,
        "scope": "exact 1475-unit model-relative full grid only; no downstream work",
        "ground_truth_definition": "authoritative label emitted for each exact frozen unit by the bound Qwen3-VL-32B checkpoint, unchanged prompt, processor inputs, 2-fps sampling, and deterministic decoding",
        "inherited_preflight_evidence": {
            "decision": "V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED",
            "execution_seal_sha256": "bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61",
            "exact_calls": 11, "strict_parse": "11/11",
            "labels": {"not_relevant": 10, "relevant": 1, "unknown": 0, "parse_failure": 0},
            "failures": 0, "retries": 0,
            "same_process_and_cross_gpu_labels_match": True,
            "processed_input_identity_matches": True,
            "k3_forward_reverse_diagnostic_variant_match": True,
            "actual_a100_gpu_hours": 0.1517243908,
            "test_count": 94,
            "semantic_disagreement_role": "construct-validity diagnostic only; never a model-relative label gate",
            "nonclaims": ["representative three-video adequacy", "human driving accuracy", "full-grid pass", "controller validation"],
        },
        "authoritative_schema": {
            "authoritative_fields": ["label"],
            "diagnostic_fields": ["confidence", "evidence"],
            "labels": ["relevant", "not_relevant", "unknown"],
            "parse_failure_is_distinct": True,
            "event_time_fields_forbidden": True,
        },
        "workload": {
            "exact_call_count": EXPECTED_UNIT_COUNT,
            "exact_frame_occurrence_count": EXPECTED_FRAME_OCCURRENCES,
            "calls_by_video": EXPECTED_UNITS_BY_VIDEO,
            "sampling_fps": 2.0,
            "normal_unit_seconds": 10.0,
            "tail_frame_counts": {key: value["frame_count"] for key, value in EXPECTED_TAILS.items()},
            "finite_stream_boundary_rule": "preserve temporal target and ideal CFR index; resolve an out-of-stream right-boundary request to the unique last available source frame; reject any repeated-frame result",
            "model_load_count": 3, "reload_count": 0, "retry_count": 0,
        },
        "model": {
            "path": "models/Qwen3-VL-32B-Instruct-FP8",
            "content_hash": "3febe26ff0cee468bf48dc733e4bca559c8f13f8fe09f931a1e0808ba7c58873",
            "gpus_per_worker": 2,
            "runtime_dtype": "torch.bfloat16",
        },
        "decoding": {
            "do_sample": False, "max_new_tokens": 192, "seed": 20260729,
            "torch_deterministic_algorithms": True,
            "cublas_workspace_config": ":4096:8",
        },
        "coverage_policy": {
            "formula": "(N_relevant + N_not_relevant) / 1475",
            "minimum_global_determined_fraction": 0.99,
            "minimum_global_determined_count": 1461,
            "minimum_per_video_determined_fraction": 0.99,
            "minimum_determined_count_by_video": {"DALI": 562, "HANGZHOU": 556, "WUHAN": 344},
            "maximum_parse_failure_count_for_release": 0,
            "unknown_reporting": "count and fraction globally and per video; preserve IDs",
            "parse_failure_reporting": "count and fraction globally and per video; preserve IDs and mark regions unevaluable",
            "primary_relation": "frozen K3 four-state relation with at most one short unknown bridge and parse_failure hard barrier",
            "lower_bound_diagnostic": "unknown is a nonnegative barrier by setting maximum_unknown_gap_units=0; labels remain recorded as unknown",
            "upper_bound_diagnostic": "sensitivity-only materialization treating unknown as possible positive; never authoritative",
        },
        "k3": {
            "configuration_hash": load_json(K3)["k3_config_sha256"],
            "reads_only": ["unit_id", "video_id", "start_time", "end_time", "authoritative_label"],
            "formal_output": "k3_model_relative_event_relation.parquet",
            "controller_output_cannot_change_parameters": True,
        },
        "failure_and_publication": {
            "global_fail_stop": True,
            "sole_execution_launcher": "sealed three-worker supervisor with abrupt-death and operation-lease enforcement",
            "formal_release_requires": ["1475/1475 authenticated terminal records", "global integrity pass", "frozen finalizer pass"],
            "partial_raw_preserved": True,
            "partial_formal_reference_forbidden": True,
            "downstream_forbidden_until_release_commit": True,
        },
        "cost": {
            "estimated_a100_gpu_hours": estimated,
            "authorization_envelope_a100_gpu_hours": ENVELOPE_A100_GPU_HOURS,
            "estimated_parallel_wall_hours": 3.0931814077885096,
        },
        "bindings": bindings,
    }, "preregistration_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_PREREGISTRATION.json", prereg)
    print(json.dumps({
        "status": "BUILT_NO_MODEL_INFERENCE",
        "units": len(unit_rows), "frames": len(flat_frames),
        "tails": {key: len(value) for key, value in tail_frames.items()},
        "processor_audit": processor_audit["status"],
        "source_commit": git_head,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
