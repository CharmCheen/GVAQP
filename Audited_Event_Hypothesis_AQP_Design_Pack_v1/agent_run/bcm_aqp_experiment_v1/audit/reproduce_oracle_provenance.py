#!/usr/bin/env python3
"""Reproduce the cached-oracle OpenCV sampling path without loading/calling a VLM.

This is blocker-mode audit instrumentation.  The extraction loop intentionally
matches the P1 and Stage-2 cache-generation scripts.  Extra bookkeeping after
``cap.read()`` records requested/decoded indices, timestamps, and RGB hashes;
it does not change frame selection.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2


REPO = Path(__file__).resolve().parents[4]
TARGET = Path(__file__).resolve().parent
BENCHMARK = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
PROMPT = REPO / "test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt"
MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
P1_ROOT = REPO / "src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1"
FULL_ROOT = REPO / "src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
P1_RAW = P1_ROOT / "oracle_outputs/raw_per_anchor"
FULL_RAW = FULL_ROOT / "oracle_outputs/raw_per_anchor_full"
P1_SCRIPT = P1_ROOT / "scripts/run_pilot_oracle.py"
FULL_SCRIPT = FULL_ROOT / "scripts/stage2_full_center10_oracle.py"
ANCHOR_SCRIPT = P1_ROOT / "scripts/build_anchor_plan.py"
ORIGINAL_GRID = P1_ROOT / "metadata/center10_anchor_grid.csv"
UNIT_TABLE = BENCHMARK / "frozen_inputs/unit_table.csv"
CACHE_MANIFEST = BENCHMARK / "oracle/oracle_cache_manifest.csv"
MODEL_MANIFEST = BENCHMARK / "oracle/oracle_model_manifest.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(payload)


def sequence_hash(values: list[str | int | float]) -> str:
    return canonical_hash(values)


def source_for(anchor_id: str) -> tuple[str, Path, Path, str]:
    full = FULL_RAW / f"{anchor_id}.json"
    p1 = P1_RAW / f"{anchor_id}.json"
    if full.exists() and not p1.exists():
        return "stage2_full", full, FULL_SCRIPT, "greedy_outer_json_object"
    if p1.exists() and not full.exists():
        return "p1_reused", p1, P1_SCRIPT, "flat_json_object_no_nested_braces"
    raise RuntimeError(f"Expected exactly one original raw source for {anchor_id}: full={full.exists()} p1={p1.exists()}")


def extract_frames(clip_start: float, clip_end: float, video_fps: float, fps: float = 2.0) -> list[dict]:
    """Exact original selection/loader loop plus non-mutating audit metadata."""
    frames: list[dict] = []
    cap = cv2.VideoCapture(str(VIDEO))
    start_frame = int(clip_start * video_fps)
    end_frame = int(clip_end * video_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_interval = max(1, int(video_fps / fps))
    for fi in range(start_frame, end_frame + 1):
        ret, frame = cap.read()
        if not ret:
            break
        decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        decoded_timestamp_ms = float(cap.get(cv2.CAP_PROP_POS_MSEC))
        if (fi - start_frame) % frame_interval == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_hash = hashlib.sha256()
            frame_hash.update(str(rgb.shape).encode("ascii"))
            frame_hash.update(str(rgb.dtype).encode("ascii"))
            frame_hash.update(rgb.tobytes(order="C"))
            frames.append({
                "requested_index": fi,
                "decoded_index": decoded_index,
                "decoded_timestamp_seconds": decoded_timestamp_ms / 1000.0,
                "content_sha256": frame_hash.hexdigest(),
            })
    cap.release()
    return frames


def frame_summary(frames: list[dict]) -> dict:
    requested = [int(frame["requested_index"]) for frame in frames]
    decoded = [int(frame["decoded_index"]) for frame in frames]
    timestamps = [round(float(frame["decoded_timestamp_seconds"]), 9) for frame in frames]
    content = [str(frame["content_sha256"]) for frame in frames]
    return {
        "requested_indices": requested,
        "decoded_indices": decoded,
        "timestamps": timestamps,
        "content_hashes": content,
        "requested_indices_hash": sequence_hash(requested),
        "decoded_indices_hash": sequence_hash(decoded),
        "timestamps_hash": sequence_hash(timestamps),
        "content_hash": sequence_hash(content),
        "count": len(frames),
    }


def read_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def model_manifest_hash() -> str:
    with MODEL_MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # Mirrors semantic_csv_hash: CSV with no benchmark_id column and LF endings.
    fieldnames = list(rows[0]) if rows else []
    from io import StringIO
    buf = StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return sha256_text(buf.getvalue())


def main() -> None:
    units = read_csv_index(UNIT_TABLE, "unit_id")
    original = read_csv_index(ORIGINAL_GRID, "anchor_id")
    cache = read_csv_index(CACHE_MANIFEST, "unit_id")
    if len(units) != 347 or len(original) != 347 or len(cache) != 347:
        raise RuntimeError(f"Expected 347 records; units={len(units)} original_grid={len(original)} cache={len(cache)}")

    cap = cv2.VideoCapture(str(VIDEO))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if not video_fps or not frame_count:
        raise RuntimeError("OpenCV could not read source video metadata")

    video_hash = sha256_file(VIDEO)
    prompt_hash = sha256_file(PROMPT)
    current_model_hash = model_manifest_hash()
    processor_config_hash = canonical_hash({
        name: sha256_file(MODEL / name)
        for name in ["preprocessor_config.json", "tokenizer_config.json", "chat_template.json"]
    })
    video_processor_config_hash = canonical_hash({
        "loader": "cv2.VideoCapture",
        "cv2_version_current_reproduction": cv2.__version__,
        "video_fps_runtime": video_fps,
        "selection_fps": 2.0,
        "frame_interval_expression": "max(1,int(video_fps/fps))",
        "start_index_expression": "int(clip_start*video_fps)",
        "end_index_expression": "int(clip_end*video_fps)",
        "end_inclusive": True,
        "color_conversion": "cv2.COLOR_BGR2RGB",
        "message_video_fps": 2.0,
    })
    generation_config_hash = canonical_hash({
        "explicit_generate_kwargs": {"max_new_tokens": 256, "temperature": 0.1},
        "model_generation_config_sha256": sha256_file(MODEL / "generation_config.json"),
        "do_sample_not_explicit": True,
    })
    parser_hashes = {
        "p1_reused": sha256_file(P1_SCRIPT),
        "stage2_full": sha256_file(FULL_SCRIPT),
    }

    interval_rows: list[dict] = []
    unit346_pairs: list[dict] = []
    source_counts = {"p1_reused": 0, "stage2_full": 0}

    for uid in range(347):
        unit = units[str(uid)]
        anchor_id = unit["anchor_id"]
        raw_kind, source_raw, source_script, parser_semantics = source_for(anchor_id)
        source_counts[raw_kind] += 1
        raw_obj = json.loads(source_raw.read_text(encoding="utf-8"))
        frozen_raw = BENCHMARK / cache[str(uid)]["raw_output_path"]
        frozen_raw_obj = json.loads(frozen_raw.read_text(encoding="utf-8"))

        original_row = original[anchor_id]
        cache_start = float(raw_obj.get("start_time", original_row["start_time"]))
        cache_end = float(raw_obj.get("end_time", original_row["end_time"]))
        frozen_start = float(unit["start_time"])
        frozen_end = float(unit["end_time"])

        cache_frames = extract_frames(cache_start, cache_end, video_fps)
        # The paths are byte-for-byte the same computation when intervals match;
        # do not duplicate expensive decoding in that case.
        if frozen_start == cache_start and frozen_end == cache_end:
            frozen_frames = cache_frames
        else:
            frozen_frames = extract_frames(frozen_start, frozen_end, video_fps)
        csum = frame_summary(cache_frames)
        fsum = frame_summary(frozen_frames)
        same_indices = fsum["decoded_indices"] == csum["decoded_indices"]
        same_content = fsum["content_hashes"] == csum["content_hashes"]

        source_raw_envelope_hash = sha256_file(source_raw)
        frozen_raw_envelope_hash = sha256_file(frozen_raw)
        source_response = raw_obj.get("raw")
        frozen_response = frozen_raw_obj.get("raw")
        source_response_hash = sha256_text(source_response) if isinstance(source_response, str) else ""
        frozen_response_hash = sha256_text(frozen_response) if isinstance(frozen_response, str) else ""
        manifest_row = cache[str(uid)]
        raw_envelope_hash_present = bool(manifest_row.get("raw_sha256")) and source_raw.exists() and frozen_raw.exists()
        raw_envelope_hash_match = source_raw_envelope_hash == frozen_raw_envelope_hash == manifest_row.get("raw_sha256")
        raw_response_hash_present = bool(source_response_hash and frozen_response_hash)
        raw_response_hash_match = raw_response_hash_present and source_response_hash == frozen_response_hash
        model_path_lineage_match = manifest_row.get("model_hash") == current_model_hash
        prompt_match = manifest_row.get("prompt_hash") == prompt_hash

        if not same_indices or not same_content:
            decision = "ORACLE_PROVENANCE_BLOCKED_REQUIRES_BENCHMARK_V2"
        else:
            # Generation-time model/package/config hashes were not recorded, so
            # matching current files and paths cannot prove contemporaneous identity.
            decision = "ORACLE_PROVENANCE_UNRESOLVED"

        interval_rows.append({
            "unit_id": uid,
            "anchor_id": anchor_id,
            "video_sha256": video_hash,
            "video_sha256_match": str(video_hash == unit["video_sha256"] == manifest_row["video_sha256"]),
            "raw_source_kind": raw_kind,
            "raw_source_path": str(source_raw),
            "cache_generation_script": str(source_script),
            "cache_generation_script_sha256": sha256_file(source_script),
            "frozen_start": f"{frozen_start:.6f}",
            "frozen_end": f"{frozen_end:.6f}",
            "cache_start": f"{cache_start:.6f}",
            "cache_end": f"{cache_end:.6f}",
            "frozen_requested_clip_interval": f"[{frozen_start:.6f},{frozen_end:.6f}]",
            "cache_requested_clip_interval": f"[{cache_start:.6f},{cache_end:.6f}]",
            "start_delta_seconds": f"{frozen_start - cache_start:.6f}",
            "end_delta_seconds": f"{frozen_end - cache_end:.6f}",
            "video_fps_runtime": f"{video_fps:.12f}",
            "video_frame_count": frame_count,
            "frame_interval": max(1, int(video_fps / 2.0)),
            "frozen_requested_frame_indices": "|".join(map(str, fsum["requested_indices"])),
            "cache_requested_frame_indices": "|".join(map(str, csum["requested_indices"])),
            "frozen_decoded_frame_indices": "|".join(map(str, fsum["decoded_indices"])),
            "cache_decoded_frame_indices": "|".join(map(str, csum["decoded_indices"])),
            "frozen_decoded_frame_timestamps": "|".join(f"{x:.9f}" for x in fsum["timestamps"]),
            "cache_decoded_frame_timestamps": "|".join(f"{x:.9f}" for x in csum["timestamps"]),
            "frozen_num_frames": fsum["count"],
            "cache_num_frames": csum["count"],
            "frozen_frame_indices_hash": fsum["decoded_indices_hash"],
            "cache_frame_indices_hash": csum["decoded_indices_hash"],
            "frozen_frame_timestamps_hash": fsum["timestamps_hash"],
            "cache_frame_timestamps_hash": csum["timestamps_hash"],
            "frozen_frame_content_hash": fsum["content_hash"],
            "cache_frame_content_hash": csum["content_hash"],
            "same_frame_indices": str(same_indices),
            "same_frame_content": str(same_content),
            "model_hash": manifest_row.get("model_hash", ""),
            "reproduced_current_model_manifest_hash": current_model_hash,
            "model_hash_match": "UNVERIFIED_SAME_PATH_AND_CURRENT_MANIFEST_NO_GENERATION_TIME_HASH" if model_path_lineage_match else "False",
            "processor_configuration_hash": processor_config_hash,
            "processor_hash_match": "UNVERIFIED_NOT_RECORDED_AT_GENERATION",
            "video_processor_configuration_hash": video_processor_config_hash,
            "video_processor_hash_match": "UNVERIFIED_PACKAGE_VERSION_NOT_RECORDED_AT_GENERATION",
            "generation_configuration_hash": generation_config_hash,
            "generation_hash_match": "UNVERIFIED_NOT_RECORDED_AT_GENERATION",
            "prompt_hash": prompt_hash,
            "prompt_hash_match": str(prompt_match),
            "parser_declared_hash": manifest_row.get("parser_hash", ""),
            "parser_source_file_hash": parser_hashes[raw_kind],
            "parser_semantics": parser_semantics,
            "parser_hash_match": "UNVERIFIED_DECLARATIVE_HASH_NOT_SOURCE_HASH",
            "raw_response_hash": source_response_hash,
            "frozen_raw_response_hash": frozen_response_hash,
            "raw_response_hash_present": str(raw_response_hash_present),
            "raw_response_hash_match": str(raw_response_hash_match),
            "raw_json_envelope_hash": source_raw_envelope_hash,
            "frozen_raw_json_envelope_hash": frozen_raw_envelope_hash,
            "raw_json_envelope_manifest_hash": manifest_row.get("raw_sha256", ""),
            "raw_json_envelope_hash_present": str(raw_envelope_hash_present),
            "raw_json_envelope_hash_match": str(raw_envelope_hash_match),
            "decision": decision,
        })

        if uid == 346:
            pair_count = max(len(cache_frames), len(frozen_frames))
            for position in range(pair_count):
                cf = cache_frames[position] if position < len(cache_frames) else None
                ff = frozen_frames[position] if position < len(frozen_frames) else None
                unit346_pairs.append({
                    "sample_position": position,
                    "cache_requested_index": "" if cf is None else cf["requested_index"],
                    "cache_decoded_index": "" if cf is None else cf["decoded_index"],
                    "cache_decoded_timestamp_seconds": "" if cf is None else f"{cf['decoded_timestamp_seconds']:.9f}",
                    "cache_frame_content_sha256": "" if cf is None else cf["content_sha256"],
                    "frozen_requested_index": "" if ff is None else ff["requested_index"],
                    "frozen_decoded_index": "" if ff is None else ff["decoded_index"],
                    "frozen_decoded_timestamp_seconds": "" if ff is None else f"{ff['decoded_timestamp_seconds']:.9f}",
                    "frozen_frame_content_sha256": "" if ff is None else ff["content_sha256"],
                    "same_decoded_index": str(bool(cf and ff and cf["decoded_index"] == ff["decoded_index"])),
                    "same_decoded_timestamp": str(bool(cf and ff and cf["decoded_timestamp_seconds"] == ff["decoded_timestamp_seconds"])),
                    "same_frame_content": str(bool(cf and ff and cf["content_sha256"] == ff["content_sha256"])),
                })

        if uid % 25 == 0 or uid == 346:
            print(f"audited unit {uid}/346", flush=True)

    interval_path = TARGET / "oracle_cache_interval_audit.csv"
    with interval_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(interval_rows[0]))
        writer.writeheader()
        writer.writerows(interval_rows)

    equivalence_path = TARGET / "unit346_frame_equivalence.csv"
    with equivalence_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(unit346_pairs[0]))
        writer.writeheader()
        writer.writerows(unit346_pairs)

    run_manifest = {
        "purpose": "blocker_mode_oracle_cache_frame_provenance_audit",
        "vlm_loaded": False,
        "vlm_calls": 0,
        "formal_experiment": False,
        "video": str(VIDEO),
        "video_sha256": video_hash,
        "opencv_version_current_reproduction": cv2.__version__,
        "opencv_reported_fps": video_fps,
        "opencv_reported_frame_count": frame_count,
        "source_counts": source_counts,
        "source_hashes": {
            "p1_script": sha256_file(P1_SCRIPT),
            "stage2_script": sha256_file(FULL_SCRIPT),
            "anchor_builder": sha256_file(ANCHOR_SCRIPT),
            "original_grid": sha256_file(ORIGINAL_GRID),
            "frozen_unit_table": sha256_file(UNIT_TABLE),
        },
        "configuration_hashes": {
            "model_manifest_current": current_model_hash,
            "processor_current": processor_config_hash,
            "video_processor_reconstructed": video_processor_config_hash,
            "generation_reconstructed": generation_config_hash,
            "prompt": prompt_hash,
            "p1_parser_source_file": parser_hashes["p1_reused"],
            "stage2_parser_source_file": parser_hashes["stage2_full"],
        },
        "outputs": {
            interval_path.name: sha256_file(interval_path),
            equivalence_path.name: sha256_file(equivalence_path),
        },
    }
    (TARGET / "provenance_reproduction_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
