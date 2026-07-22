"""Reconstruct the failed v1 physical timeline from preserved artifacts.

This module never changes prior sprint files.  It reads the frozen task
manifest, started/complete checkpoints, raw responses, warning log, and exact
local processor source, then writes a derived audit into the v2 directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SPRINT = ROOT / "AQP_Algorithm_Invention_Sprint_v1"
OLD_PHYSICAL = SPRINT / "physical"
OUTPUT = SPRINT / "operator_validation/event_enumerate_v2"
AUDIT = OUTPUT / "audit"

TRANSFORMERS = Path(
    "/qiuyeqing/tools/miniconda3/envs/garc/lib/python3.10/site-packages/transformers"
)
QWEN_UTILS = Path(
    "/qiuyeqing/tools/miniconda3/envs/garc/lib/python3.10/site-packages/qwen_vl_utils"
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reconstruct_old_processor(
    frame_indices: list[int], source_fps: float
) -> dict[str, Any]:
    """Mirror the exact qwen-vl-utils/Transformers v1 temporal path."""

    decoded_count = len(frame_indices)
    padded_count = int(math.ceil(decoded_count / 2) * 2)
    qwen_tensor_to_decoded_position = list(range(decoded_count))
    qwen_tensor_to_decoded_position.extend(
        [decoded_count - 1] * (padded_count - decoded_count)
    )

    # Qwen3VLVideoProcessor defaults: do_sample_frames=True, target fps=2,
    # missing source fps -> 24, min_frames=4, max_frames=768.
    assumed_source_fps = 24.0
    target_fps = 2.0
    processor_count = int(padded_count / assumed_source_fps * target_fps)
    processor_count = min(max(processor_count, 4), 768, padded_count)
    positions = (
        np.linspace(0, padded_count - 1, processor_count)
        .round()
        .astype(int)
        .tolist()
    )
    selected_decoded_positions = [qwen_tensor_to_decoded_position[x] for x in positions]
    selected_source_indices = [frame_indices[x] for x in selected_decoded_positions]

    temporal_positions = list(positions)
    temporal_source_indices = list(selected_source_indices)
    if len(temporal_positions) % 2:
        temporal_positions.append(temporal_positions[-1])
        temporal_source_indices.append(temporal_source_indices[-1])
    processor_patch_timestamps = [
        ((temporal_positions[i] / assumed_source_fps)
         + (temporal_positions[i + 1] / assumed_source_fps))
        / 2.0
        for i in range(0, len(temporal_positions), 2)
    ]
    actual_patch_timestamps = [
        ((temporal_source_indices[i] / source_fps)
         + (temporal_source_indices[i + 1] / source_fps))
        / 2.0
        for i in range(0, len(temporal_source_indices), 2)
    ]
    return {
        "decoded_count": decoded_count,
        "qwen_utils_padded_count": padded_count,
        "missing_metadata_assumed_source_fps": assumed_source_fps,
        "processor_target_fps": target_fps,
        "processor_selected_tensor_positions": positions,
        "processor_selected_decoded_positions": selected_decoded_positions,
        "processor_selected_source_frame_indices": selected_source_indices,
        "processor_frame_count": processor_count,
        "processor_patch_count": len(processor_patch_timestamps),
        "processor_patch_timestamps": processor_patch_timestamps,
        "processor_timestamp_texts": [f"{x:.1f}" for x in processor_patch_timestamps],
        "actual_patch_timestamps": actual_patch_timestamps,
    }


def _coordinate_warp_boundary(
    generated_relative: float,
    old_input_start: float,
    visible_timestamps: list[float],
    actual_timestamps: list[float],
) -> dict[str, Any]:
    old_absolute = old_input_start + generated_relative
    if not (
        visible_timestamps[0] - 1e-12
        <= generated_relative
        <= visible_timestamps[-1] + 1e-12
    ):
        return {
            "generated_relative": generated_relative,
            "old_mapped_absolute": old_absolute,
            "coordinate_implied_absolute": None,
            "old_minus_coordinate_seconds": None,
            "status": "outside_processor_visible_timeline",
            "is_semantic_ground_truth": False,
        }
    implied = float(
        np.interp(generated_relative, visible_timestamps, actual_timestamps)
    )
    return {
        "generated_relative": generated_relative,
        "old_mapped_absolute": old_absolute,
        "coordinate_implied_absolute": implied,
        "old_minus_coordinate_seconds": old_absolute - implied,
        "status": "piecewise_linear_between_exact_patch_centers",
        "is_semantic_ground_truth": False,
    }


def timeline_rows() -> list[dict[str, Any]]:
    sample = _load(OLD_PHYSICAL / "SAMPLE_MANIFEST.json")
    source_fps = float(sample["video"]["fps"])
    rows: list[dict[str, Any]] = []
    tasks = [
        task
        for task in sample["execution_order"]
        if task["operator"] == "EVENT_ENUMERATE"
    ]
    for task in tasks:
        attempt_id = task["planned_attempt_id"]
        started_path = OLD_PHYSICAL / "attempts" / f"{attempt_id}.started.json"
        complete_path = OLD_PHYSICAL / "attempts" / f"{attempt_id}.complete.json"
        raw_path = OLD_PHYSICAL / "raw" / f"{attempt_id}.txt"
        started, complete = _load(started_path), _load(complete_path)
        frame_indices = [int(x) for x in task["frame_indices"]]
        observed_frame_indices = [
            int(row["frame_index"]) for row in started["frame_identities"]
        ]
        if observed_frame_indices != frame_indices:
            raise RuntimeError(f"saved frame identities mismatch: {attempt_id}")
        if complete["task"] != task:
            raise RuntimeError(f"complete checkpoint task mismatch: {attempt_id}")
        if sha256_file(raw_path) != complete["raw_response_sha256"]:
            raise RuntimeError(f"raw response hash mismatch: {attempt_id}")

        reconstruction = reconstruct_old_processor(frame_indices, source_fps)
        real_timestamps = [x / source_fps for x in frame_indices]
        events = (complete.get("parsed_response") or {}).get("events", [])
        generated_intervals = [
            [float(event["event_start"]), float(event["event_end"])]
            for event in events
        ]
        mapped_intervals = [
            [
                float(task["input_start"]) + interval[0],
                float(task["input_start"]) + interval[1],
            ]
            for interval in generated_intervals
        ]
        coordinate_warp_diagnostics = []
        for event_index, interval in enumerate(generated_intervals):
            coordinate_warp_diagnostics.append(
                {
                    "event_index": event_index,
                    "start": _coordinate_warp_boundary(
                        interval[0],
                        float(task["input_start"]),
                        reconstruction["processor_patch_timestamps"],
                        reconstruction["actual_patch_timestamps"],
                    ),
                    "end": _coordinate_warp_boundary(
                        interval[1],
                        float(task["input_start"]),
                        reconstruction["processor_patch_timestamps"],
                        reconstruction["actual_patch_timestamps"],
                    ),
                }
        )
        actual_span = real_timestamps[-1] - real_timestamps[0]
        visible_start = reconstruction["processor_patch_timestamps"][0]
        visible_end = reconstruction["processor_patch_timestamps"][-1]
        actual_patch_start = reconstruction["actual_patch_timestamps"][0]
        actual_patch_end = reconstruction["actual_patch_timestamps"][-1]
        rows.append(
            {
                "attempt_id": attempt_id,
                "is_nominal_60_second_call": math.isclose(
                    float(task["input_end"]) - float(task["input_start"]), 60.0
                ),
                "nominal_input_start": task["input_start"],
                "nominal_input_end": task["input_end"],
                "nominal_duration": float(task["input_end"])
                - float(task["input_start"]),
                "core_start": task["core_start"],
                "core_end": task["core_end"],
                "actual_sampled_start": real_timestamps[0],
                "actual_sampled_end": real_timestamps[-1],
                "actual_sampled_span": actual_span,
                "decoded_frame_count": len(frame_indices),
                "decoded_frame_indices_json": _json(frame_indices),
                "real_timestamp_sequence_json": _json(real_timestamps),
                "saved_frame_identity_match": True,
                "qwen_utils_padded_frame_count": reconstruction[
                    "qwen_utils_padded_count"
                ],
                "processor_source_fps": reconstruction[
                    "missing_metadata_assumed_source_fps"
                ],
                "processor_target_fps": reconstruction["processor_target_fps"],
                "processor_selected_tensor_positions_json": _json(
                    reconstruction["processor_selected_tensor_positions"]
                ),
                "processor_selected_source_frame_indices_json": _json(
                    reconstruction["processor_selected_source_frame_indices"]
                ),
                "processor_consumed_frame_count": reconstruction[
                    "processor_frame_count"
                ],
                "processor_temporal_patch_count": reconstruction[
                    "processor_patch_count"
                ],
                "processor_visible_timestamps_json": _json(
                    reconstruction["processor_patch_timestamps"]
                ),
                "processor_visible_timestamp_texts_json": _json(
                    reconstruction["processor_timestamp_texts"]
                ),
                "processor_patch_actual_source_timestamps_json": _json(
                    reconstruction["actual_patch_timestamps"]
                ),
                "processor_visible_start": visible_start,
                "processor_visible_end": visible_end,
                "coordinate_warp_error_at_visible_start_seconds": (
                    float(task["input_start"]) + visible_start - actual_patch_start
                ),
                "coordinate_warp_error_at_visible_end_seconds": (
                    float(task["input_start"]) + visible_end - actual_patch_end
                ),
                "actual_to_visible_end_ratio": actual_span / visible_end,
                "prompt_declared_duration": task["perceived_clip_duration"],
                "input_token_count": complete.get("input_token_count"),
                "generated_event_count": len(events),
                "generated_relative_intervals_json": _json(generated_intervals),
                "old_mapped_absolute_intervals_json": _json(mapped_intervals),
                "coordinate_warp_diagnostic_json": _json(
                    coordinate_warp_diagnostics
                ),
                "raw_response_path": str(raw_path.relative_to(ROOT)),
                "raw_response_sha256": complete["raw_response_sha256"],
                "model_input_tensor_hash_status": "NOT_PRESERVED_IN_V1",
            }
        )
    if len(rows) != 70 or sum(row["is_nominal_60_second_call"] for row in rows) != 68:
        raise RuntimeError("unexpected old enumeration call population")
    return rows


def coordinate_warp_rows(
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize the label-independent coordinate diagnostic per boundary."""

    rows: list[dict[str, Any]] = []
    for call in timeline:
        diagnostics = json.loads(call["coordinate_warp_diagnostic_json"])
        for event in diagnostics:
            for boundary in ("start", "end"):
                diagnostic = event[boundary]
                rows.append(
                    {
                        "attempt_id": call["attempt_id"],
                        "event_index": event["event_index"],
                        "boundary": boundary,
                        "generated_relative": diagnostic["generated_relative"],
                        "old_mapped_absolute": diagnostic[
                            "old_mapped_absolute"
                        ],
                        "coordinate_implied_absolute": diagnostic[
                            "coordinate_implied_absolute"
                        ],
                        "old_minus_coordinate_seconds": diagnostic[
                            "old_minus_coordinate_seconds"
                        ],
                        "status": diagnostic["status"],
                        "is_semantic_ground_truth": False,
                    }
                )
    return rows


def write_coordinate_warp_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    path = AUDIT / "OLD_COORDINATE_WARP_DIAGNOSTICS.csv"
    _write_csv(path, rows)
    statuses: dict[str, int] = {}
    for row in rows:
        status = str(row["status"])
        statuses[status] = statuses.get(status, 0) + 1
    supported = [
        float(row["old_minus_coordinate_seconds"])
        for row in rows
        if row["old_minus_coordinate_seconds"] is not None
    ]
    summary = {
        "schema_version": "event_enumerate_v2_coordinate_warp_summary_v1",
        "source": "audit/OLD_CALL_TIMELINE_RECONSTRUCTION.csv",
        "diagnostic": "piecewise-linear coordinate mapping between exact processor patch centers",
        "boundary_rows": len(rows),
        "status_counts": statuses,
        "interpolation_supported_boundaries": len(supported),
        "outside_processor_visible_timeline_boundaries": statuses.get(
            "outside_processor_visible_timeline", 0
        ),
        "old_minus_coordinate_seconds": {
            "minimum": min(supported) if supported else None,
            "maximum": max(supported) if supported else None,
            "mean": float(np.mean(supported)) if supported else None,
            "median": float(np.median(supported)) if supported else None,
        },
        "is_semantic_ground_truth": False,
        "semantic_localization_metric": "NOT_MEASURED",
    }
    (AUDIT / "OLD_COORDINATE_WARP_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_manifest_rows() -> list[dict[str, Any]]:
    paths_and_roles = [
        (ROOT / "src/garc_eval/aqp_invention_v1/contract.py", "old parser and ownership"),
        (ROOT / "src/garc_eval/aqp_invention_v1/prepare_physical.py", "old frame/call manifest construction"),
        (ROOT / "src/garc_eval/aqp_invention_v1/run_physical.py", "old decode and processor invocation"),
        (ROOT / "src/garc_eval/aqp_invention_v1/evaluate_physical.py", "old relative-to-absolute mapping and evaluator"),
        (ROOT / "src/garc_eval/aqp_invention_v1/prompts/event_enumerate_v1.txt", "frozen prompt"),
        (TRANSFORMERS / "models/qwen3_vl/processing_qwen3_vl.py", "timestamp token construction"),
        (TRANSFORMERS / "models/qwen3_vl/video_processing_qwen3_vl.py", "default resampling"),
        (TRANSFORMERS / "video_processing_utils.py", "base video preprocessing"),
        (TRANSFORMERS / "video_utils.py", "VideoMetadata semantics"),
        (QWEN_UTILS / "vision_process.py", "preprocessor helper and metadata return path"),
        (ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct/video_preprocessor_config.json", "local video processor config"),
        (ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct/chat_template.json", "serialized chat template"),
    ]
    rows = []
    for path, role in paths_and_roles:
        rows.append(
            {
                "path": str(path if path.is_absolute() and not str(path).startswith(str(ROOT)) else path.relative_to(ROOT)),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else "",
                "sha256": sha256_file(path) if path.exists() else "",
                "role": role,
                "source_scope": "prior sprint" if str(path).startswith(str(ROOT)) else "installed dependency",
                "modified_by_v2": False,
            }
        )
    return rows


def input_manifest_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(OLD_PHYSICAL.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if "/attempts/" in f"/{relative}":
            artifact_class = "request_checkpoint_or_response_metadata"
        elif "/raw/" in f"/{relative}":
            artifact_class = "raw_model_response"
        elif path.name.endswith("LEDGER.csv"):
            artifact_class = "runtime_ledger"
        elif path.name == "SAMPLE_MANIFEST.json":
            artifact_class = "frame_and_call_manifest"
        elif "/logs/" in f"/{relative}":
            artifact_class = "runtime_log"
        else:
            artifact_class = "physical_configuration_or_summary"
        rows.append(
            {
                "path": str(relative),
                "artifact_class": artifact_class,
                "availability": "PRESERVED",
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "used_by_v2": True,
                "note": "read-only prior sprint artifact",
            }
        )
    for name, note in [
        (
            "NOT_PRESERVED/v1_serialized_chat_requests",
            "chat text is deterministically reconstructable, but was not saved per call",
        ),
        (
            "NOT_PRESERVED/v1_processor_video_metadata",
            "metadata omission is evidenced by the saved warning; no metadata object was saved",
        ),
        (
            "NOT_PRESERVED/v1_model_input_tensors",
            "only token counts were saved; tensor values and hashes were not preserved",
        ),
        (
            "NOT_PRESERVED/v1_temporal_position_ids",
            "not materialized or saved by the runner",
        ),
    ]:
        rows.append(
            {
                "path": name,
                "artifact_class": "missing_v1_evidence",
                "availability": "NOT_PRESERVED",
                "size_bytes": "",
                "sha256": "",
                "used_by_v2": False,
                "note": note,
            }
        )
    return rows


def write_forensics_report(
    rows: list[dict[str, Any]], coordinate_summary: dict[str, Any]
) -> None:
    nominal = [row for row in rows if row["is_nominal_60_second_call"]]
    counts = sorted({row["processor_consumed_frame_count"] for row in nominal})
    visible_ends = sorted({round(row["processor_visible_end"], 9) for row in nominal})
    event_count = sum(int(row["generated_event_count"]) for row in rows)
    report = f"""# Failed pipeline forensics

## Strongest supported conclusion

The v1 runner transported the correct scheduled source frames into
`qwen-vl-utils`, but it did not transport their temporal metadata into the
Qwen3-VL processor.  The exact responsible invocation is
`src/garc_eval/aqp_invention_v1/run_physical.py:153-157`: it calls
`process_vision_info(messages)` without `return_video_kwargs=True` or
`return_video_metadata=True`, then calls `processor(...)` without
`video_metadata` and without `do_sample_frames=False`.  The `fps` field at
line 148 is merely message data and is absent from the processor call.

## Observed evidence

- The preserved runtime log records the installed processor warning that no
  metadata was provided and source FPS was defaulted to 24.
- All 70 started checkpoints contain exact decoded frame identities matching
  the frozen schedules; 68 calls have a nominal 60-second input and 121
  decoded frames.
- The 70 complete checkpoints and raw-response hashes verify; they contain
  {event_count} parsed event reports in total.
- The old runner saved token counts but did **not** save per-call processor
  metadata, serialized chat text, input tensors, tensor hashes, or temporal
  position IDs.  Those absences are explicit in `INPUT_MANIFEST.csv`.

## Reconstructed mechanism

For a nominal 60-second call, `qwen-vl-utils` first pads 121 frames to 122.
Because processor metadata is missing, `Qwen3VLVideoProcessor.sample_frames`
sets source FPS to 24 and applies its default target of 2 FPS:
`int(122 / 24 * 2) = 10`.  It selects 10 tensor positions and the Qwen3-VL
processor averages each pair for five temporal patches.  The timestamp tokens
therefore end at {visible_ends} seconds rather than approximately 60 seconds;
the consumed-frame counts across nominal calls are {counts}.

The prompt still declares 60.0 seconds.  Thus prompt prose, visual content,
and processor timestamp tokens disagree.  The exact per-call schedules,
visible timestamps, actual source patch timestamps, generated timestamps, old
absolute mapping, and a label-independent coordinate-warp diagnostic are in
`OLD_CALL_TIMELINE_RECONSTRUCTION.csv`.  Its normalized boundary table is
`OLD_COORDINATE_WARP_DIAGNOSTICS.csv`: it contains
{coordinate_summary['boundary_rows']} generated boundaries,
{coordinate_summary['interpolation_supported_boundaries']} inside the exact
processor-visible coordinate span and
{coordinate_summary['outside_processor_visible_timeline_boundaries']} outside.

## Derived conclusion and uncertainty

The temporal compression itself is artifact/source-supported under the pinned
current dependencies and is reproduced by `test_old_compression_regression.py`.
That suite now includes a processor-only sentinel through the exact old helper
and processor call signature, plus a check over all 68 nominal saved calls.
It does not rerun old model generation.  The coordinate-warp columns are **not
semantic ground truth**: they linearly map generated coordinates between exact
processor patch centers to quantify the coordinate contradiction.  A model
could instead follow the contradictory 60-second prose, so the diagnostic is
excluded from event-localization accuracy.

The exact dependency versions were not written into the old run metadata.
The current local source is `transformers 5.10.0.dev0` at commit
`effde20942e3f82a1b97449f60b3a48c5ff96145` and `qwen-vl-utils 0.0.14`;
its behavior matches the preserved warning and token/frame evidence.  This is
strong reproduction evidence, but not a saved v1 environment image.

## Mapping and ownership path

The old evaluator adds `task.input_start` to model-relative event boundaries
in `evaluate_physical.py`, then applies midpoint ownership to half-open cores.
Because the coordinate system was compressed before inference, this mapping
could shift model-visible content far outside its true source time and reject
otherwise reported fragments at the ownership gate.  No v1 artifact is
modified or reinterpreted as a corrected physical cost measurement.
"""
    (AUDIT / "FAILED_PIPELINE_FORENSICS.md").write_text(report, encoding="utf-8")


def generate() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    rows = timeline_rows()
    _write_csv(AUDIT / "OLD_CALL_TIMELINE_RECONSTRUCTION.csv", rows)
    coordinate_summary = write_coordinate_warp_artifacts(
        coordinate_warp_rows(rows)
    )
    _write_csv(AUDIT / "SOURCE_MANIFEST.csv", source_manifest_rows())
    _write_csv(AUDIT / "INPUT_MANIFEST.csv", input_manifest_rows())
    write_forensics_report(rows, coordinate_summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    generate()


if __name__ == "__main__":
    main()
