#!/usr/bin/env python3
"""Build the frozen two-video, two-query exhaustive oracle benchmark.

Stages:
  prepare  - freeze V1 units and content-bound frame identities
  infer    - run missing V1 units through the physical frozen oracle
  finalize - project Q1/Q2, materialize references, and audit reconstruction
  verify   - independently re-read and reconstruct every frozen artifact

V0's complete strict oracle is reused byte-for-byte.  V1 calls import the
existing strict builder's frame sampler, parser, RNG routine, and model-input
identity routine instead of reimplementing them.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import gc
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
if os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in {None, EXPECTED_CUBLAS_WORKSPACE_CONFIG}:
    raise RuntimeError("Conflicting CUBLAS_WORKSPACE_CONFIG was set before oracle startup")
os.environ["CUBLAS_WORKSPACE_CONFIG"] = EXPECTED_CUBLAS_WORKSPACE_CONFIG

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_two_video_loop"
DEV = OUT / "dev_benchmark_v1"
RAW_V1 = DEV / "raw_oracle/V1"
PARSED = DEV / "parsed_labels"
REFERENCES = DEV / "reference_events"
STATE = OUT / "state"
VIDEO_MANIFEST_PATH = OUT / "VIDEO_MANIFEST.json"
QUERY_PROTOCOL_PATH = OUT / "QUERY_SELECTION_PROTOCOL.json"
QUERY_MANIFEST_PATH = OUT / "QUERY_MANIFEST.json"
INPUT_GATE_PATH = STATE / "INPUT_GATE_DECISION.json"
QUERY_GATE_PATH = STATE / "QUERY_FREEZE_DECISION.json"
V0_BENCH = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict"
)
STRICT_BUILDER_PATH = V0_BENCH / "scripts/build_strict_oracle.py"
V0_ORACLE_OBSERVATIONS = V0_BENCH / "frozen_inputs/oracle_observations.csv"
V0_REFERENCE = V0_BENCH / "frozen_inputs/event_reference.csv"
V0_RAW_JSONL = V0_BENCH / "oracle/oracle_raw_outputs.jsonl"
V0_ATTEMPT_LEDGER = V0_BENCH / "oracle/VLM_ATTEMPT_EVENT_LOG.jsonl"
V0_ORACLE_CONFIG = V0_BENCH / "oracle/oracle_configuration.json"
ORACLE_PROMPT = V0_BENCH / "oracle/oracle_prompt.txt"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
LOCK = DEV / ".reference_build.lock"
UNITS_V1 = DEV / "units/V1_units.csv"
IDENTITIES_V1 = DEV / "raw_oracle/V1/input_identities.jsonl"
ATTEMPTS_V1 = DEV / "raw_oracle/V1/ATTEMPT_LEDGER.jsonl"
ORACLE_CONFIG_V1 = DEV / "raw_oracle/V1/ORACLE_CONFIG.json"
RUNTIME_V1 = DEV / "raw_oracle/V1/RESOLVED_INFERENCE_RUNTIME.json"
BUILD_STATE_V1 = DEV / "raw_oracle/V1/BUILD_STATE.json"
UNIT_SECONDS = 10.0
HALF_WINDOW_SECONDS = 5.0
BASE_SEED = 20260710
REFERENCE_VERSION = "consecutive_positive_units_v1"
REFERENCE_TYPE = "VLM_DEFINED_PSEUDO_ORACLE"
MAX_ATTEMPTS_PER_UNIT = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_text(path: Path, text: str) -> None:
    atomic_bytes(path, text.encode("utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_text(path, frame.to_csv(index=False, lineterminator="\n"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    """Durably append one ledger event without rewriting prior immutable rows."""

    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    line = (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    with path.open("ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    if created:
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_strict_builder():
    spec = importlib.util.spec_from_file_location("psvr_frozen_strict_oracle_builder", STRICT_BUILDER_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot import frozen strict builder: {STRICT_BUILDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_gates() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    input_gate = json.loads(INPUT_GATE_PATH.read_text(encoding="utf-8"))
    query_gate = json.loads(QUERY_GATE_PATH.read_text(encoding="utf-8"))
    videos = json.loads(VIDEO_MANIFEST_PATH.read_text(encoding="utf-8"))
    queries = json.loads(QUERY_PROTOCOL_PATH.read_text(encoding="utf-8"))
    if input_gate.get("VIDEO_INPUT_GATE") != "PASS":
        raise RuntimeError("VIDEO_INPUT_GATE is not PASS")
    if query_gate.get("QUERY_FREEZE") != "PASS":
        raise RuntimeError("QUERY_FREEZE is not PASS")
    if not videos.get("V0") or not videos.get("V1"):
        raise RuntimeError("VIDEO_MANIFEST does not contain frozen V0 and V1")
    return input_gate, query_gate, videos, queries


def video_info(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    video = next(row for row in payload["streams"] if row.get("codec_type") == "video")
    fmt = payload["format"]
    numerator, denominator = (video.get("avg_frame_rate") or video["r_frame_rate"]).split("/")
    fps = float(numerator) / float(denominator)
    duration = float(fmt.get("duration") or video["duration"])
    frame_count = int(video.get("nb_frames") or round(duration * fps))
    return {"fps": fps, "duration_seconds": duration, "frame_count": frame_count}


def make_units(video_id: str, video_sha256: str, info: dict[str, Any]) -> pd.DataFrame:
    duration = float(info["duration_seconds"])
    fps = float(info["fps"])
    frame_count = int(info["frame_count"])
    rows = []
    for unit_id in range(int(math.ceil(duration / UNIT_SECONDS))):
        anchor_time = unit_id * UNIT_SECONDS + HALF_WINDOW_SECONDS
        if anchor_time > duration:
            anchor_time = duration
        start = max(0.0, anchor_time - HALF_WINDOW_SECONDS)
        end = min(duration, anchor_time + HALF_WINDOW_SECONDS)
        start_frame = min(frame_count - 1, max(0, int(start * fps)))
        end_frame = min(frame_count - 1, max(start_frame, int(math.ceil(end * fps)) - 1))
        rows.append({
            "video_id": video_id,
            "video_sha256": video_sha256,
            "unit_id": unit_id,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "start_time": round(start, 6),
            "end_time": round(end, 6),
            "duration_seconds": round(end - start, 6),
            "split_role": "two_video_development",
            "eligible_for_query": True,
            "anchor_id": f"center10_anchor_{unit_id:04d}",
        })
    return pd.DataFrame(rows)


def frozen_bindings(strict, v0_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "strict_builder_path": str(STRICT_BUILDER_PATH),
        "strict_builder_sha256": sha256_file(STRICT_BUILDER_PATH),
        "frame_sampler_source_sha256": sha256_text(inspect.getsource(strict.frames_for_unit)),
        "extract_frames_source_sha256": sha256_text(inspect.getsource(strict.extract_frames)),
        "parser_source_sha256": sha256_text(inspect.getsource(strict.parse_response)),
        "rng_source_sha256": sha256_text(inspect.getsource(strict.configure_rng)),
        "model_input_manifest_source_sha256": sha256_text(inspect.getsource(strict.model_input_manifest)),
        "model_full_content_hash": v0_config["model_full_content_hash"],
        "prompt_sha256": v0_config["prompt_sha256"],
        "parser_config": v0_config["parser_config"],
        "parser_source_hash_original_config": v0_config["parser_source_hash"],
        "sampling_code_hash": v0_config["sampling_code_hash"],
        "frame_config": v0_config["frame_config"],
        "generation_config": v0_config["generation_config"],
        "model_load_config": v0_config["model_load_config"],
        "processor_files": v0_config["processor_files"],
    }


def stage_prepare() -> None:
    _, _, videos, query_protocol = load_gates()
    strict = load_strict_builder()
    v0_config = json.loads(V0_ORACLE_CONFIG.read_text(encoding="utf-8"))
    if sha256_file(ORACLE_PROMPT) != v0_config["prompt_sha256"]:
        raise RuntimeError("Frozen prompt hash mismatch")
    if sha256_text(inspect.getsource(strict.parse_response)) != v0_config["parser_source_hash"]:
        raise RuntimeError("Frozen parser source hash mismatch")
    sampling_source_hash = sha256_text(
        inspect.getsource(strict.extract_frames) + inspect.getsource(strict.frames_for_unit)
    )
    if sampling_source_hash != v0_config["sampling_code_hash"]:
        raise RuntimeError("Frozen frame-sampling source hash mismatch")
    _, current_model_hash = strict.full_model_manifest()
    if current_model_hash != v0_config["model_full_content_hash"]:
        raise RuntimeError("Frozen oracle model content hash mismatch")
    v1_path = Path(videos["V1"]["absolute_path"])
    if sha256_file(v1_path) != videos["V1"]["sha256"]:
        raise RuntimeError("Frozen V1 bytes changed")
    info = video_info(v1_path)
    units = make_units("V1", videos["V1"]["sha256"], info)
    unit_semantics_hash = canonical_hash(units.to_dict("records"))
    bindings = frozen_bindings(strict, v0_config)
    build_id = "two_video_v1_oracle_" + canonical_hash({
        "video_sha256": videos["V1"]["sha256"],
        "unit_semantics_hash": unit_semantics_hash,
        "bindings": bindings,
        "query_protocol_hash": query_protocol["protocol_hash"],
    })[:20]
    config = {
        "build_id": build_id,
        "prepared_at_utc": utc_now(),
        "video": {
            "absolute_path": str(v1_path),
            "sha256": videos["V1"]["sha256"],
            **info,
        },
        "units": len(units),
        "unit_semantics_hash": unit_semantics_hash,
        "query_protocol_hash": query_protocol["protocol_hash"],
        "bindings": bindings,
        "base_seed": BASE_SEED,
        "preparation_hardware_runtime_identity": strict.hardware_runtime_identity(),
        "raw_reuse_policy": "resume only exact valid raw from this build identity",
        "physical_oracle_only": True,
        "heldout_opened": False,
    }
    if ORACLE_CONFIG_V1.exists():
        existing = json.loads(ORACLE_CONFIG_V1.read_text(encoding="utf-8"))
        immutable_keys = ["build_id", "video", "units", "unit_semantics_hash", "query_protocol_hash", "bindings", "base_seed"]
        if any(existing.get(key) != config.get(key) for key in immutable_keys):
            raise RuntimeError("Existing V1 oracle preparation has a different immutable identity")
        identities = read_jsonl(IDENTITIES_V1)
        if len(identities) != len(units):
            raise RuntimeError("Existing V1 identities are incomplete")
        print(json.dumps({"PREPARE": "EXISTING_VALID", "units": len(identities), "build_id": build_id}, indent=2))
        return

    RAW_V1.mkdir(parents=True, exist_ok=True)
    atomic_csv(UNITS_V1, units)
    strict.VIDEO = v1_path
    identities = []
    cap = cv2.VideoCapture(str(v1_path))
    decode_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    for row in units.to_dict("records"):
        frames = strict.frames_for_unit(float(row["start_time"]), float(row["end_time"]), decode_fps)
        indices = [int(frame["decoded_index"]) for frame in frames]
        contents = [frame["content_sha256"] for frame in frames]
        identity = {
            "anchor_id": row["anchor_id"],
            "build_id": build_id,
            "decoded_frame_content_sha256": canonical_hash(contents),
            "decoded_frame_count": len(frames),
            "decoded_frame_indices": indices,
            "decoded_frame_indices_sha256": canonical_hash(indices),
            "decoded_frame_timestamps_seconds": [
                round(float(frame["decoded_timestamp_seconds"]), 9) for frame in frames
            ],
            "generation_config_hash": canonical_hash(v0_config["generation_config"]),
            "model_full_content_hash": v0_config["model_full_content_hash"],
            "parser_hash": canonical_hash(v0_config["parser_config"]),
            "prompt_hash": v0_config["prompt_sha256"],
            "rng_seed": BASE_SEED + int(row["unit_id"]),
            "sampling_code_hash": v0_config["sampling_code_hash"],
            "start_time": float(row["start_time"]),
            "end_time": float(row["end_time"]),
            "unit_id": int(row["unit_id"]),
            "video_sha256": videos["V1"]["sha256"],
        }
        identity["cache_input_identity_sha256"] = canonical_hash(identity)
        identities.append(identity)
        if (int(row["unit_id"]) + 1) % 25 == 0 or int(row["unit_id"]) + 1 == len(units):
            print(json.dumps({
                "stage": "prepare",
                "content_bound_units": int(row["unit_id"]) + 1,
                "total_units": len(units),
            }), flush=True)
        del frames
    atomic_text(IDENTITIES_V1, "".join(
        json.dumps(identity, sort_keys=True) + "\n" for identity in identities
    ))
    atomic_json(ORACLE_CONFIG_V1, config)
    atomic_json(BUILD_STATE_V1, {
        "build_id": build_id,
        "status": "PREPARED",
        "prepared_units": len(identities),
        "completed_units": 0,
        "physical_attempts": 0,
        "parse_failures": 0,
        "updated_at_utc": utc_now(),
    })
    print(json.dumps({"PREPARE": "PASS", "units": len(identities), "build_id": build_id}, indent=2))


def raw_path(identity: dict[str, Any]) -> Path:
    return RAW_V1 / f"{identity['anchor_id']}.json"


def raw_valid(path: Path, identity: dict[str, Any], strict) -> bool:
    if not path.is_file():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        parsed, parse_status = strict.parse_response(record["raw"])
    except Exception:
        return False
    return bool(
        parse_status == "ok"
        and record.get("build_id") == identity["build_id"]
        and record.get("cache_input_identity_sha256") == identity["cache_input_identity_sha256"]
        and record.get("physical_vlm_call") is True
        and record.get("cache_replay") is False
        and record.get("raw_response_sha256") == sha256_text(record["raw"])
        and record.get("unit_id") == identity["unit_id"]
        and record.get("unit_start") == identity["start_time"]
        and record.get("unit_end") == identity["end_time"]
        and record.get("per_frame_content_sha256")
        and canonical_hash(record["per_frame_content_sha256"]) == identity["decoded_frame_content_sha256"]
        and record.get("decoded_frame_indices") == identity["decoded_frame_indices"]
        and record.get("parse_status") == "ok"
        and record.get("parsed_sha256") == canonical_hash(parsed)
    )


def attempt_count(unit_id: int) -> int:
    return sum(int(row.get("unit_id", -1)) == unit_id and row.get("event") == "STARTED"
               for row in read_jsonl(ATTEMPTS_V1))


def stage_infer(limit: int | None) -> None:
    _, _, videos, _ = load_gates()
    if not ORACLE_CONFIG_V1.exists() or not IDENTITIES_V1.exists():
        raise RuntimeError("Run prepare before infer")
    config = json.loads(ORACLE_CONFIG_V1.read_text(encoding="utf-8"))
    identities = read_jsonl(IDENTITIES_V1)
    strict = load_strict_builder()
    v1_path = Path(videos["V1"]["absolute_path"])
    strict.VIDEO = v1_path
    valid_before = sum(raw_valid(raw_path(identity), identity, strict) for identity in identities)
    if valid_before == len(identities):
        print(json.dumps({"INFER": "ALL_VALID_EXISTING", "completed_units": valid_before}, indent=2))
        return

    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model.eval()
    load_seconds = time.perf_counter() - load_started
    resolved_runtime = strict.resolved_inference_runtime(model, processor)
    if RUNTIME_V1.exists():
        previous = json.loads(RUNTIME_V1.read_text(encoding="utf-8"))
        if previous != resolved_runtime:
            raise RuntimeError("Resolved oracle inference runtime changed across resume")
    else:
        atomic_json(RUNTIME_V1, resolved_runtime)
    cap = cv2.VideoCapture(str(v1_path))
    decode_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    prompt = ORACLE_PROMPT.read_text(encoding="utf-8")
    new_units = 0
    for identity in identities:
        destination = raw_path(identity)
        if raw_valid(destination, identity, strict):
            continue
        if limit is not None and new_units >= limit:
            break
        uid = int(identity["unit_id"])
        successful = False
        for _ in range(attempt_count(uid), MAX_ATTEMPTS_PER_UNIT):
            sequence = attempt_count(uid) + 1
            attempt_id = f"{config['build_id']}_u{uid:04d}_a{sequence:03d}"
            started_utc = utc_now()
            append_jsonl(ATTEMPTS_V1, {
                "attempt_id": attempt_id,
                "event": "STARTED",
                "physical_vlm_call": True,
                "cache_replay": False,
                "unit_id": uid,
                "timestamp_utc": started_utc,
            })
            try:
                frames = strict.frames_for_unit(
                    float(identity["start_time"]), float(identity["end_time"]), decode_fps
                )
                indices = [int(frame["decoded_index"]) for frame in frames]
                contents = [frame["content_sha256"] for frame in frames]
                if indices != identity["decoded_frame_indices"]:
                    raise RuntimeError("decoded frame indices changed from prepared identity")
                if canonical_hash(contents) != identity["decoded_frame_content_sha256"]:
                    raise RuntimeError("decoded frame content changed from prepared identity")
                pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
                messages = [{"role": "user", "content": [
                    {"type": "video", "video": pil_frames, "fps": strict.FRAME_CONFIG["message_fps"]},
                    {"type": "text", "text": prompt},
                ]}]
                prompt_text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(
                    text=[prompt_text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                ).to(model.device)
                input_manifest = strict.model_input_manifest(inputs, prompt_text, torch)
                rng = strict.configure_rng(identity["rng_seed"], torch)
                torch.cuda.reset_peak_memory_stats()
                generation_started = time.perf_counter()
                with torch.no_grad():
                    generated = model.generate(
                        **inputs, do_sample=False,
                        max_new_tokens=strict.GENERATION_CONFIG["max_new_tokens"],
                    )
                torch.cuda.synchronize()
                generation_seconds = time.perf_counter() - generation_started
                trimmed = [
                    output[len(input_ids):]
                    for input_ids, output in zip(inputs.input_ids, generated)
                ]
                raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
                parsed, parse_status = strict.parse_response(raw)
                record = {
                    "anchor_id": identity["anchor_id"],
                    "attempt_id": attempt_id,
                    "build_id": config["build_id"],
                    "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
                    "cache_replay": False,
                    "call_completed_at_utc": utc_now(),
                    "call_started_at_utc": started_utc,
                    "decoded_frame_indices": indices,
                    "decoded_frame_timestamps_seconds": [
                        round(float(frame["decoded_timestamp_seconds"]), 9) for frame in frames
                    ],
                    "generation_config": strict.GENERATION_CONFIG,
                    "generation_runtime_seconds": generation_seconds,
                    "gpu_seconds": generation_seconds,
                    "model_input_manifest": input_manifest,
                    "model_load_seconds": load_seconds if new_units == 0 and sequence == 1 else 0.0,
                    "parse_status": parse_status,
                    "parsed_sha256": canonical_hash(parsed),
                    "peak_gpu_memory_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                    "peak_gpu_memory_reserved_bytes": int(torch.cuda.max_memory_reserved()),
                    "per_frame_content_sha256": contents,
                    "physical_vlm_call": True,
                    "raw": raw,
                    "raw_response_sha256": sha256_text(raw),
                    "resolved_inference_runtime_sha256": resolved_runtime[
                        "resolved_inference_runtime_sha256"
                    ],
                    "rng_identity": rng,
                    "rng_seed": identity["rng_seed"],
                    "unit_end": identity["end_time"],
                    "unit_id": uid,
                    "unit_start": identity["start_time"],
                }
                if parse_status == "ok":
                    atomic_json(destination, record)
                    if not raw_valid(destination, identity, strict):
                        raise RuntimeError("durable raw validation failed")
                    append_jsonl(ATTEMPTS_V1, {
                        "attempt_id": attempt_id,
                        "event": "ACCEPTED",
                        "parse_status": parse_status,
                        "raw_envelope_sha256": sha256_file(destination),
                        "raw_response_sha256": record["raw_response_sha256"],
                        "unit_id": uid,
                        "timestamp_utc": utc_now(),
                    })
                    successful = True
                else:
                    failed_path = RAW_V1 / "failed_attempts" / f"{attempt_id}.json"
                    atomic_json(failed_path, record)
                    append_jsonl(ATTEMPTS_V1, {
                        "attempt_id": attempt_id,
                        "event": "INVALID_PARSE",
                        "parse_status": parse_status,
                        "raw_envelope_sha256": sha256_file(failed_path),
                        "raw_response_sha256": record["raw_response_sha256"],
                        "unit_id": uid,
                        "timestamp_utc": utc_now(),
                    })
            except Exception as exc:
                append_jsonl(ATTEMPTS_V1, {
                    "attempt_id": attempt_id,
                    "event": "FAILED",
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                    "unit_id": uid,
                    "timestamp_utc": utc_now(),
                })
            finally:
                for name in ("inputs", "generated", "frames", "pil_frames"):
                    if name in locals():
                        del locals()[name]
                gc.collect()
                torch.cuda.empty_cache()
            if successful:
                break
        if not successful:
            raise RuntimeError(f"Unit {uid} exhausted {MAX_ATTEMPTS_PER_UNIT} physical attempts")
        new_units += 1
        # Every increment follows a durable write plus an immediate raw_valid
        # check above, so rescanning all prior immutable envelopes here adds
        # quadratic bookkeeping without increasing evidence integrity.
        completed = valid_before + new_units
        attempts = read_jsonl(ATTEMPTS_V1)
        atomic_json(BUILD_STATE_V1, {
            "build_id": config["build_id"],
            "status": "INFERENCE_COMPLETE" if completed == len(identities) else "INFERENCE_IN_PROGRESS",
            "prepared_units": len(identities),
            "completed_units": completed,
            "physical_attempts": sum(row.get("event") == "STARTED" for row in attempts),
            "parse_failures": sum(row.get("event") == "INVALID_PARSE" for row in attempts),
            "runtime_failures": sum(row.get("event") == "FAILED" for row in attempts),
            "updated_at_utc": utc_now(),
        })
        print(json.dumps({
            "stage": "infer",
            "unit_id": uid,
            "generation_runtime_seconds": generation_seconds,
            "completed_units": completed,
            "total_units": len(identities),
        }), flush=True)
    completed = sum(raw_valid(raw_path(item), item, strict) for item in identities)
    print(json.dumps({
        "INFER": "PASS" if completed == len(identities) else "IN_PROGRESS",
        "completed_units": completed,
        "total_units": len(identities),
        "new_units": new_units,
    }, indent=2))


def raw_records_v1(strict) -> list[dict[str, Any]]:
    identities = read_jsonl(IDENTITIES_V1)
    records = []
    for identity in identities:
        path = raw_path(identity)
        if not raw_valid(path, identity, strict):
            raise RuntimeError(f"Missing or invalid V1 raw output: unit {identity['unit_id']}")
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def observations_from_v1(
    records: list[dict[str, Any]], units: pd.DataFrame, strict, config: dict[str, Any]
) -> pd.DataFrame:
    unit_by_id = units.set_index("unit_id")
    rows = []
    for record in records:
        uid = int(record["unit_id"])
        parsed, parse_status = strict.parse_response(record["raw"])
        unit = unit_by_id.loc[uid]
        start = float(unit["start_time"])

        def absolute(value: Any) -> float | None:
            if value in (None, "", "null"):
                return None
            try:
                return start + float(value)
            except (TypeError, ValueError):
                return None

        rows.append({
            "video_id": "V1",
            "unit_id": uid,
            "start_time": start,
            "end_time": float(unit["end_time"]),
            "anchor_id": unit["anchor_id"],
            "raw_output_path": str(raw_path({
                "anchor_id": unit["anchor_id"]
            }).relative_to(DEV)),
            "parsed_label": parsed.get("label", "abstain"),
            "confidence": parsed.get("confidence", "low"),
            "abstain": parsed.get("label") == "abstain",
            "parse_success": parse_status == "ok",
            "parse_status": parse_status,
            "latency_seconds": float(record["generation_runtime_seconds"]),
            "gpu_seconds": float(record["gpu_seconds"]),
            "physical_call": True,
            "cache_hit": False,
            "event_start_absolute": absolute(parsed.get("event_start")),
            "event_end_absolute": absolute(parsed.get("event_end")),
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "ego_relevant": parsed.get("ego_relevant", False),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": parsed.get("complete_event_visible", ""),
            "evidence": parsed.get("evidence", ""),
            "negative_reason": parsed.get("negative_reason"),
            "abstain_reason": parsed.get("abstain_reason"),
            "raw_response_sha256": record["raw_response_sha256"],
            "model_hash": config["bindings"]["model_full_content_hash"],
            "prompt_hash": config["bindings"]["prompt_sha256"],
            "parser_hash": canonical_hash(config["bindings"]["parser_config"]),
            "sampling_code_hash": config["bindings"]["sampling_code_hash"],
            "build_id": config["build_id"],
        })
    return pd.DataFrame(rows).sort_values("unit_id").reset_index(drop=True)


def normalize_v0_observations() -> pd.DataFrame:
    frame = pd.read_csv(V0_ORACLE_OBSERVATIONS)
    frame = frame.rename(columns={"benchmark_id": "parent_benchmark_id"})
    frame["video_id"] = "V0"
    frame["parse_status"] = np.where(frame["parse_success"].astype(bool), "ok", "failed")
    frame["raw_response_sha256"] = ""
    frame["sampling_code_hash"] = json.loads(V0_ORACLE_CONFIG.read_text())["sampling_code_hash"]
    frame["build_id"] = json.loads(V0_ORACLE_CONFIG.read_text())["oracle_build_id"]
    return frame


def project_query(generic: pd.DataFrame, query: dict[str, Any]) -> pd.DataFrame:
    allowed = set(query["frozen_oracle_type_projection"])
    projected = generic.copy()
    projected["oracle_generic_label"] = projected["parsed_label"].astype(str).str.lower()
    projected["oracle_generic_involved_object"] = projected["involved_object"].astype(str).str.lower()

    def label(row: pd.Series) -> str:
        original = str(row["oracle_generic_label"]).lower()
        if original == "abstain":
            return "abstain"
        if original == "positive" and str(row["oracle_generic_involved_object"]).lower() in allowed:
            return "positive"
        return "negative"

    projected["parsed_label"] = projected.apply(label, axis=1)
    projected["query_id"] = query["query_id"]
    projected["query_name"] = query["name"]
    projected["projection_type_set"] = "|".join(sorted(allowed))
    projected["projection_used_text_evidence"] = False
    return projected


def build_reference(
    oracle: pd.DataFrame, benchmark_id: str, task_id: str, video_id: str
) -> pd.DataFrame:
    positive = oracle[oracle["parsed_label"].astype(str).str.lower() == "positive"].sort_values("unit_id")
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous = None
    for row in positive.to_dict("records"):
        uid = int(row["unit_id"])
        if current and previous is not None and uid != previous + 1:
            groups.append(current)
            current = []
        current.append(row)
        previous = uid
    if current:
        groups.append(current)
    rows = []
    for index, group in enumerate(groups):
        starts = [
            float(row["event_start_absolute"])
            for row in group if pd.notna(row.get("event_start_absolute"))
        ]
        ends = [
            float(row["event_end_absolute"])
            for row in group if pd.notna(row.get("event_end_absolute"))
        ]
        start = min(starts) if starts else min(float(row["start_time"]) for row in group)
        end = max(ends) if ends else max(float(row["end_time"]) for row in group)
        rows.append({
            "benchmark_id": benchmark_id,
            "task_id": task_id,
            "video_id": video_id,
            "reference_event_id": f"{task_id}_event_{index:04d}",
            "start_time": start,
            "core_start_time": start,
            "core_end_time": end,
            "end_time": end,
            "canonical_anchor_time": float(group[0]["start_time"]),
            "source_unit_ids": "|".join(str(int(row["unit_id"])) for row in group),
            "event_type": "enter_ego_path",
            "reference_type": REFERENCE_TYPE,
            "reference_version": REFERENCE_VERSION,
            "adjudication_status": "not_human_adjudicated",
        })
    return pd.DataFrame(rows, columns=[
        "benchmark_id", "task_id", "video_id", "reference_event_id", "start_time",
        "core_start_time", "core_end_time", "end_time", "canonical_anchor_time",
        "source_unit_ids", "event_type", "reference_type", "reference_version",
        "adjudication_status",
    ])


def semantic_csv_hash(frame: pd.DataFrame) -> str:
    return sha256_text(frame.to_csv(index=False, lineterminator="\n"))


def copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as handle:
        atomic_bytes(destination, handle.read())


def stage_finalize() -> None:
    _, _, videos, query_protocol = load_gates()
    strict = load_strict_builder()
    config = json.loads(ORACLE_CONFIG_V1.read_text(encoding="utf-8"))
    units_v1 = pd.read_csv(UNITS_V1)
    records = raw_records_v1(strict)
    generic_v1 = observations_from_v1(records, units_v1, strict, config)
    generic_v0 = normalize_v0_observations()
    benchmark_id = "psvr2v_" + canonical_hash({
        "video_manifest": json.loads(VIDEO_MANIFEST_PATH.read_text()),
        "query_protocol_hash": query_protocol["protocol_hash"],
        "oracle_bindings": config["bindings"],
        "v1_unit_semantics_hash": config["unit_semantics_hash"],
    })[:20]
    PARSED.mkdir(parents=True, exist_ok=True)
    REFERENCES.mkdir(parents=True, exist_ok=True)
    atomic_csv(PARSED / "V0_GENERIC_ORACLE.csv", generic_v0)
    atomic_csv(PARSED / "V1_GENERIC_ORACLE.csv", generic_v1)
    task_rows = []
    coverage_rows = []
    reconstruction_rows = []
    task_references: dict[str, pd.DataFrame] = {}
    for video_id, generic in (("V0", generic_v0), ("V1", generic_v1)):
        for query in query_protocol["queries"]:
            task_id = f"{video_id}_{query['query_id']}"
            projected = project_query(generic, query)
            reference = build_reference(projected, benchmark_id, task_id, video_id)
            atomic_csv(PARSED / f"{task_id}.csv", projected)
            atomic_csv(REFERENCES / f"{task_id}.csv", reference)
            reloaded = pd.read_csv(REFERENCES / f"{task_id}.csv")
            rebuilt = build_reference(projected, benchmark_id, task_id, video_id)
            deterministic = semantic_csv_hash(reloaded) == semantic_csv_hash(rebuilt)
            task_references[task_id] = reference
            task_rows.append({
                "task_id": task_id,
                "video_id": video_id,
                "video_sha256": videos[video_id]["sha256"],
                "query_id": query["query_id"],
                "query_name": query["name"],
                "units": len(projected),
                "reference_events": len(reference),
                "positive_units": int((projected["parsed_label"] == "positive").sum()),
                "abstain_units": int((projected["parsed_label"] == "abstain").sum()),
                "parse_failures": int((~projected["parse_success"].astype(bool)).sum()),
                "projected_labels_path": str((PARSED / f"{task_id}.csv").relative_to(DEV)),
                "reference_path": str((REFERENCES / f"{task_id}.csv").relative_to(DEV)),
                "reference_sha256": sha256_file(REFERENCES / f"{task_id}.csv"),
            })
            coverage_rows.append({
                "task_id": task_id,
                "video_id": video_id,
                "query_id": query["query_id"],
                "expected_units": len(projected),
                "parsed_units": int(projected["parse_success"].astype(bool).sum()),
                "parse_failures": int((~projected["parse_success"].astype(bool)).sum()),
                "positive_units": int((projected["parsed_label"] == "positive").sum()),
                "reference_events": len(reference),
                "complete": bool(projected["parse_success"].astype(bool).all()),
            })
            reconstruction_rows.append({
                "task_id": task_id,
                "saved_reference_sha256": semantic_csv_hash(reloaded),
                "rebuilt_reference_sha256": semantic_csv_hash(rebuilt),
                "deterministic_reconstruction": deterministic,
            })

    # Validate that the copied materializer logic reproduces the authoritative
    # unprojected V0 reference before accepting any projected task reference.
    v0_broad = build_reference(generic_v0, "placeholder", "V0_BROAD", "V0")
    v0_saved = pd.read_csv(V0_REFERENCE)
    compare_columns = [
        "start_time", "core_start_time", "core_end_time", "end_time",
        "canonical_anchor_time", "source_unit_ids", "event_type",
        "reference_type", "reference_version", "adjudication_status",
    ]
    v0_broad_equivalent = (
        v0_broad[compare_columns].reset_index(drop=True).fillna("").astype(str).equals(
            v0_saved[compare_columns].reset_index(drop=True).fillna("").astype(str)
        )
    )
    q_counts = {
        query["query_id"]: sum(
            len(task_references[f"{video_id}_{query['query_id']}"])
            for video_id in ("V0", "V1")
        )
        for query in query_protocol["queries"]
    }
    fallback_invoked = any(count == 0 for count in q_counts.values())
    all_complete = all(row["complete"] for row in coverage_rows)
    all_reconstructed = all(row["deterministic_reconstruction"] for row in reconstruction_rows)
    gate_pass = (
        len(task_rows) == 4
        and all_complete
        and all_reconstructed
        and v0_broad_equivalent
        and not fallback_invoked
    )

    task_manifest = {
        "benchmark_id": benchmark_id,
        "created_at_utc": utc_now(),
        "tasks": task_rows,
        "DEV_SOURCE_VIDEOS": 2,
        "DEV_QUERIES": 2,
        "DEV_VIDEO_QUERIES": 4,
        "heldout_opened": False,
    }
    benchmark_manifest = {
        "benchmark_id": benchmark_id,
        "benchmark_version": "PSVR_TWO_VIDEO_DEV_V1",
        "created_at_utc": utc_now(),
        "video_manifest_sha256": sha256_file(VIDEO_MANIFEST_PATH),
        "query_manifest_sha256": sha256_file(QUERY_MANIFEST_PATH),
        "query_protocol_hash": query_protocol["protocol_hash"],
        "tasks": task_rows,
        "oracle": {
            "model_hash": config["bindings"]["model_full_content_hash"],
            "prompt_hash": config["bindings"]["prompt_sha256"],
            "parser_hash": canonical_hash(config["bindings"]["parser_config"]),
            "sampling_code_hash": config["bindings"]["sampling_code_hash"],
            "V0_policy": "reuse existing complete strict physical oracle",
            "V1_policy": "fresh physical oracle, resumable only by exact content-bound identity",
            "V1_build_id": config["build_id"],
            "V1_physical_calls": len(records),
            "V1_cache_replays": 0,
        },
        "reference": {
            "materializer": REFERENCE_VERSION,
            "type": REFERENCE_TYPE,
            "V0_unprojected_equivalence_pass": v0_broad_equivalent,
        },
        "status": "FROZEN_COMPLETE" if gate_pass else "BLOCKED_REFERENCE_INTEGRITY",
        "heldout_opened": False,
    }
    atomic_json(DEV / "BENCHMARK_MANIFEST.json", benchmark_manifest)
    copy_atomic(VIDEO_MANIFEST_PATH, DEV / "VIDEO_MANIFEST.json")
    copy_atomic(QUERY_MANIFEST_PATH, DEV / "QUERY_MANIFEST.json")
    atomic_json(DEV / "TASK_MANIFEST.json", task_manifest)
    atomic_csv(DEV / "REFERENCE_COVERAGE_AUDIT.csv", pd.DataFrame(coverage_rows))
    copy_atomic(OUT / "SOURCE_INDEPENDENCE_AUDIT.json", DEV / "SOURCE_INDEPENDENCE_AUDIT.json")
    atomic_json(DEV / "RECONSTRUCTION_AUDIT.json", {
        "V0_unprojected_reference_equivalent": v0_broad_equivalent,
        "V0_authoritative_reference_sha256": sha256_file(V0_REFERENCE),
        "V0_authoritative_raw_jsonl_sha256": sha256_file(V0_RAW_JSONL),
        "V0_authoritative_attempt_ledger_sha256": sha256_file(V0_ATTEMPT_LEDGER),
        "task_reconstructions": reconstruction_rows,
        "all_task_reconstructions_pass": all_reconstructed,
        "materializer": REFERENCE_VERSION,
    })
    atomic_json(DEV / "raw_oracle/V0/REUSE_MANIFEST.json", {
        "policy": "reuse existing complete strict physical oracle; do not copy or rerun",
        "raw_jsonl": str(V0_RAW_JSONL),
        "raw_jsonl_sha256": sha256_file(V0_RAW_JSONL),
        "attempt_ledger": str(V0_ATTEMPT_LEDGER),
        "attempt_ledger_sha256": sha256_file(V0_ATTEMPT_LEDGER),
        "oracle_observations": str(V0_ORACLE_OBSERVATIONS),
        "oracle_observations_sha256": sha256_file(V0_ORACLE_OBSERVATIONS),
        "physical_calls": len(generic_v0),
        "cache_replay": False,
    })
    decision = {
        "TWO_VIDEO_DEV_BENCHMARK": "PASS" if gate_pass else "BLOCKED_REFERENCE_INTEGRITY",
        "DEV_SOURCE_VIDEOS": 2,
        "DEV_QUERIES": 2,
        "DEV_VIDEO_QUERIES": 4,
        "all_references_complete": all_complete,
        "deterministic_reconstruction_passes": all_reconstructed and v0_broad_equivalent,
        "query_event_counts_across_videos": q_counts,
        "fallback_invoked": fallback_invoked,
        "heldout_opened": False,
        "NEXT_EXACT_COMMAND": (
            "python scripts/freeze_psvr_two_video_deadlines.py profile"
            if gate_pass else
            "python scripts/build_psvr_two_video_references.py verify"
        ),
    }
    atomic_json(DEV / "FINAL_BENCHMARK_DECISION.json", decision)
    atomic_json(STATE / "BENCHMARK_GATE_DECISION.json", decision)
    atomic_json(OUT / "benchmark/BENCHMARK_POINTER.json", {
        "authoritative_directory": str(DEV),
        "benchmark_manifest_sha256": sha256_file(DEV / "BENCHMARK_MANIFEST.json"),
        "decision": decision["TWO_VIDEO_DEV_BENCHMARK"],
    })
    atomic_json(OUT / "references/REFERENCE_POINTER.json", {
        "authoritative_directory": str(REFERENCES),
        "tasks": {
            row["task_id"]: {
                "path": row["reference_path"],
                "sha256": row["reference_sha256"],
            }
            for row in task_rows
        },
    })
    print(json.dumps(decision, indent=2))


def stage_verify() -> None:
    strict = load_strict_builder()
    decision = json.loads((DEV / "FINAL_BENCHMARK_DECISION.json").read_text())
    task_manifest = json.loads((DEV / "TASK_MANIFEST.json").read_text())
    query_protocol = json.loads(QUERY_PROTOCOL_PATH.read_text())
    generic = {
        "V0": pd.read_csv(PARSED / "V0_GENERIC_ORACLE.csv"),
        "V1": pd.read_csv(PARSED / "V1_GENERIC_ORACLE.csv"),
    }
    failures = []
    for task in task_manifest["tasks"]:
        query = next(row for row in query_protocol["queries"] if row["query_id"] == task["query_id"])
        projected = project_query(generic[task["video_id"]], query)
        rebuilt = build_reference(
            projected, task_manifest["benchmark_id"], task["task_id"], task["video_id"]
        )
        saved_labels = pd.read_csv(DEV / task["projected_labels_path"])
        saved_reference = pd.read_csv(DEV / task["reference_path"])
        if semantic_csv_hash(saved_labels) != semantic_csv_hash(projected):
            failures.append(f"{task['task_id']}:projected_labels")
        if semantic_csv_hash(saved_reference) != semantic_csv_hash(rebuilt):
            failures.append(f"{task['task_id']}:reference")
        if sha256_file(DEV / task["reference_path"]) != task["reference_sha256"]:
            failures.append(f"{task['task_id']}:reference_sha256")
    records = raw_records_v1(strict)
    attempts = read_jsonl(ATTEMPTS_V1)
    started = [row for row in attempts if row.get("event") == "STARTED"]
    accepted = [row for row in attempts if row.get("event") == "ACCEPTED"]
    if len(records) != len(pd.read_csv(UNITS_V1)):
        failures.append("V1_raw_coverage")
    if len(accepted) != len(records):
        failures.append("V1_attempt_acceptance")
    if any(record.get("cache_replay") for record in records):
        failures.append("V1_cache_replay")
    verification = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "tasks_verified": len(task_manifest["tasks"]),
        "V1_raw_outputs_verified": len(records),
        "V1_physical_attempts_started": len(started),
        "V1_accepted_attempts": len(accepted),
        "decision_consistent": (
            decision["TWO_VIDEO_DEV_BENCHMARK"] == "PASS" and not failures
        ),
        "heldout_opened": False,
        "verified_at_utc": utc_now(),
    }
    atomic_json(DEV / "INDEPENDENT_VERIFICATION.json", verification)
    print(json.dumps(verification, indent=2))
    if failures:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "infer", "finalize", "verify"])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    DEV.mkdir(parents=True, exist_ok=True)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another two-video reference stage holds the build lock") from exc
        if args.stage == "prepare":
            stage_prepare()
        elif args.stage == "infer":
            stage_infer(args.limit)
        elif args.stage == "finalize":
            stage_finalize()
        else:
            stage_verify()


if __name__ == "__main__":
    main()
