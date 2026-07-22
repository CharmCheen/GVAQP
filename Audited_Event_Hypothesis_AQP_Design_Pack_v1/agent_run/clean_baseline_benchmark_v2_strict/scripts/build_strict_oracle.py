#!/usr/bin/env python3
"""Build a fresh, fully identified 347-unit oracle for strict benchmark v2.

No legacy response is eligible for reuse.  Each generation is atomically saved
before parsing, and a valid saved generation is the only unit of resumability.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import inspect
import json
import os
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata
from io import StringIO
from pathlib import Path

EXPECTED_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
if os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in {None, EXPECTED_CUBLAS_WORKSPACE_CONFIG}:
    raise RuntimeError("Conflicting CUBLAS_WORKSPACE_CONFIG was set before strict oracle startup")
os.environ["CUBLAS_WORKSPACE_CONFIG"] = EXPECTED_CUBLAS_WORKSPACE_CONFIG

import cv2
import numpy as np


REPO = Path(__file__).resolve().parents[4]
PACK = Path(__file__).resolve().parents[1]
V1 = PACK.parent / "clean_baseline_benchmark_v1"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
UNITS_SOURCE = V1 / "frozen_inputs/unit_table.csv"
PROMPT_SOURCE = V1 / "oracle/oracle_prompt.txt"
PROMPT_TARGET = PACK / "oracle/oracle_prompt.txt"
RAW_DIR = PACK / "oracle/raw"
PARSED_DIR = PACK / "oracle/parsed"
IDENTITIES = PACK / "oracle/input_identities.jsonl"
CONFIG_PATH = PACK / "oracle/oracle_configuration.json"
BUILD_MANIFEST = PACK / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json"
MODEL_MANIFEST = PACK / "oracle/STRICT_MODEL_FILE_MANIFEST.csv"
PACKAGE_MANIFEST = PACK / "oracle/STRICT_RUNTIME_PACKAGE_MANIFEST.csv"
ATTEMPT_LEDGER = PACK / "oracle/VLM_ATTEMPT_EVENT_LOG.jsonl"
INFERENCE_RUNTIME = PACK / "oracle/RESOLVED_INFERENCE_RUNTIME.json"
INFER_LOCK = PACK / "oracle/.strict_inference.lock"
COMPLETE_MARKER = PACK / "oracle/STRICT_ORACLE_COMPLETE.json"
PARSED_MANIFEST = PACK / "oracle/STRICT_PARSED_OUTPUT_MANIFEST.csv"
STATE_UPDATER = PACK / "scripts/atomic_run_state.py"

UNIT_COUNT = 347
BASE_SEED = 20260710
PARSER_VERSION = "presence_json_parser_v1_stage2_compatible"
PARSER_CONFIG = {
    "confidence_domain": ["high", "low", "medium"],
    "label_domain": ["abstain", "negative", "positive"],
    "parser_version": PARSER_VERSION,
    "required_keys": ["label", "confidence"],
}
GENERATION_CONFIG = {
    "do_sample": False,
    "max_new_tokens": 256,
    "randomness_policy": "greedy_with_per_unit_rng_identity_recorded",
    "temperature": None,
}
MODEL_LOAD_CONFIG = {
    "device_map": "auto",
    "torch_dtype": "bfloat16",
    "trust_remote_code": True,
}
FRAME_CONFIG = {
    "color": "cv2.COLOR_BGR2RGB",
    "decoded_end_inclusive": True,
    "fallback_decode_fps": 4.0,
    "message_fps": 2.0,
    "minimum_frames_before_fallback": 5,
    "primary_decode_fps": 2.0,
}
CRITICAL_DISTRIBUTIONS = [
    "accelerate",
    "av",
    "numpy",
    "opencv-python",
    "pillow",
    "qwen-vl-utils",
    "safetensors",
    "tokenizers",
    "torch",
    "torchvision",
    "transformers",
]


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


def canonical_hash(value: object) -> str:
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl_atomic(path: Path, row: dict) -> None:
    rows = read_jsonl(path)
    rows.append(row)
    atomic_write_text(path, "".join(json.dumps(item, sort_keys=True) + "\n" for item in rows))


def read_attempt_events() -> list[dict]:
    events = read_jsonl(ATTEMPT_LEDGER)
    previous = None
    for event in events:
        claimed = event.get("event_sha256")
        payload = {key: value for key, value in event.items() if key != "event_sha256"}
        if payload.get("previous_event_sha256") != previous or claimed != canonical_hash(payload):
            raise RuntimeError("VLM attempt event-log hash chain is invalid")
        previous = claimed
    validate_attempt_event_sequence(events)
    return events


def validate_attempt_event_sequence(events: list[dict]) -> None:
    started: dict[str, dict] = {}
    terminal: set[str] = set()
    for event in events:
        event_type = event.get("event")
        attempt_id = event.get("attempt_id")
        if not isinstance(attempt_id, str):
            raise RuntimeError("VLM attempt event lacks a string attempt_id")
        if event_type == "STARTED":
            if attempt_id in started:
                raise RuntimeError(f"Duplicate STARTED event: {attempt_id}")
            for field in [
                "cache_input_identity_sha256", "model_input_identity_sha256",
                "resolved_inference_runtime_sha256", "rng_state_identity_sha256",
            ]:
                if not is_sha256(event.get(field)):
                    raise RuntimeError(f"STARTED event has invalid {field}: {attempt_id}")
            started[attempt_id] = event
        elif event_type in {"ACCEPTED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}:
            if attempt_id not in started:
                raise RuntimeError(f"Orphan terminal attempt event: {attempt_id}")
            if attempt_id in terminal:
                raise RuntimeError(f"Duplicate terminal attempt event: {attempt_id}")
            if event.get("unit_id") != started[attempt_id].get("unit_id"):
                raise RuntimeError(f"Attempt terminal unit mismatch: {attempt_id}")
            if event_type in {"ACCEPTED", "RECOVERED_ACCEPTED"} and (
                not is_sha256(event.get("raw_envelope_sha256"))
                or not is_sha256(event.get("raw_response_sha256"))
            ):
                raise RuntimeError(f"Accepted attempt lacks raw hashes: {attempt_id}")
            terminal.add(attempt_id)
        else:
            raise RuntimeError(f"Unknown VLM attempt event type: {event_type}")


def append_attempt_event(event: dict) -> dict:
    events = read_attempt_events()
    record = {**event, "previous_event_sha256": events[-1]["event_sha256"] if events else None}
    record["event_sha256"] = canonical_hash(record)
    validate_attempt_event_sequence([*events, record])
    atomic_write_text(ATTEMPT_LEDGER, "".join(json.dumps(item, sort_keys=True) + "\n" for item in [*events, record]))
    return record


def attempt_summary() -> dict:
    events = read_attempt_events()
    started = [event for event in events if event.get("event") == "STARTED"]
    terminals = {
        event["attempt_id"]: event
        for event in events
        if event.get("event") in {"ACCEPTED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}
    }
    unresolved = [event for event in started if event["attempt_id"] not in terminals]
    accepted = [event for event in terminals.values() if event["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED"}]
    return {
        "accepted_attempts": len(accepted),
        "physical_attempts_started": len(started),
        "unresolved_attempt_ids": [event["attempt_id"] for event in unresolved],
        "uncertain_attempts": sum(event["event"] == "RECOVERED_UNCERTAIN" for event in terminals.values()),
    }


def update_state(*args: str) -> None:
    subprocess.run([os.environ.get("PYTHON", "python3"), str(STATE_UPDATER), *args], check=True)


def update_oracle_state(phase: str, phase_status: str, completed_units: int, attempts: dict) -> None:
    args = [
        "--phase", phase,
        "--phase-status", phase_status,
        "--completed-units", str(completed_units),
        "--physical-attempts-started", str(attempts["physical_attempts_started"]),
        "--uncertain-attempts", str(attempts["uncertain_attempts"]),
    ]
    exact_known = (
        not attempts["unresolved_attempt_ids"]
        and attempts["uncertain_attempts"] == 0
        and attempts["accepted_attempts"] == attempts["physical_attempts_started"]
    )
    if exact_known:
        args.extend(["--physical-vlm-calls", str(attempts["accepted_attempts"])])
    else:
        args.append("--physical-vlm-calls-unknown")
    update_state(*args)


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def hardware_runtime_identity() -> dict:
    import torch

    devices = []
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        devices.append({
            "compute_capability": f"{properties.major}.{properties.minor}",
            "index": index,
            "name": properties.name,
            "total_memory_bytes": int(properties.total_memory),
            "uuid": str(getattr(properties, "uuid", "UNAVAILABLE")),
        })
    try:
        driver = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=True, capture_output=True, text=True,
        ).stdout.strip().splitlines()
    except Exception:
        driver = ["UNAVAILABLE"]
    return {
        "cuda_available": torch.cuda.is_available(),
        "cudnn_version": torch.backends.cudnn.version(),
        "devices": devices,
        "nvidia_driver_versions": driver,
        "platform": platform.platform(),
        "python": sys.version,
        "torch_cuda_version": torch.version.cuda,
        "torch_version": torch.__version__,
    }


def parse_response(raw_text: str) -> tuple[dict, str]:
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return {}, "no_json_object"
        parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            return {}, "json_not_object"
        missing = [key for key in PARSER_CONFIG["required_keys"] if key not in parsed]
        if missing:
            return parsed, "missing_required_keys:" + "|".join(missing)
        if not isinstance(parsed["label"], str) or parsed["label"].lower() not in PARSER_CONFIG["label_domain"]:
            return parsed, "invalid_label"
        if not isinstance(parsed["confidence"], str) or parsed["confidence"].lower() not in PARSER_CONFIG["confidence_domain"]:
            return parsed, "invalid_confidence"
        parsed["label"] = parsed["label"].lower()
        parsed["confidence"] = parsed["confidence"].lower()
        return parsed, "ok"
    except Exception:
        return {}, "parse_error"


def extract_frames(clip_start: float, clip_end: float, video_fps: float, fps: float = 2.0) -> list[dict]:
    frames: list[dict] = []
    cap = cv2.VideoCapture(str(VIDEO))
    start_frame = int(clip_start * video_fps)
    end_frame = int(clip_end * video_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_interval = max(1, int(video_fps / fps))
    for requested_index in range(start_frame, end_frame + 1):
        ok, frame = cap.read()
        if not ok:
            break
        decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        timestamp = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
        if (requested_index - start_frame) % frame_interval == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            digest = hashlib.sha256()
            digest.update(str(rgb.shape).encode("ascii"))
            digest.update(str(rgb.dtype).encode("ascii"))
            digest.update(rgb.tobytes(order="C"))
            frames.append({
                "content_sha256": digest.hexdigest(),
                "decoded_index": decoded_index,
                "decoded_timestamp_seconds": timestamp,
                "requested_index": requested_index,
                "rgb": rgb,
            })
    cap.release()
    return frames


def frames_for_unit(start: float, end: float, video_fps: float) -> list[dict]:
    frames = extract_frames(start, end, video_fps, FRAME_CONFIG["primary_decode_fps"])
    if len(frames) < FRAME_CONFIG["minimum_frames_before_fallback"]:
        frames = extract_frames(start, end, video_fps, FRAME_CONFIG["fallback_decode_fps"])
    if not frames:
        raise RuntimeError(f"No frames decoded for [{start}, {end}]")
    return frames


def full_model_manifest() -> tuple[list[dict], str]:
    rows = []
    for path in sorted(MODEL.iterdir(), key=lambda item: item.name):
        if path.is_file():
            rows.append({
                "file": path.name,
                "model_path": str(MODEL),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            })
            print(json.dumps({"hashed_model_file": path.name, "size_bytes": path.stat().st_size}), flush=True)
    if not rows or not any(row["file"].endswith(".safetensors") for row in rows):
        raise RuntimeError("Model manifest does not include weight shards")
    return rows, canonical_hash(rows)


def full_runtime_package_manifest(progress: bool = False) -> tuple[list[dict], str]:
    rows: list[dict] = []
    for distribution_name in CRITICAL_DISTRIBUTIONS:
        distribution = metadata.distribution(distribution_name)
        files = sorted(distribution.files or [], key=str)
        for relative in files:
            path = Path(distribution.locate_file(relative))
            if not path.is_file():
                continue
            rows.append({
                "distribution": distribution_name,
                "file": str(relative),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "version": distribution.version,
            })
        if progress:
            print(json.dumps({
                "hashed_distribution": distribution_name,
                "manifest_files": sum(row["distribution"] == distribution_name for row in rows),
                "version": distribution.version,
            }, sort_keys=True), flush=True)
    return rows, canonical_hash(rows)


def units_semantic_rows() -> list[dict]:
    rows = read_csv(UNITS_SOURCE)
    if len(rows) != UNIT_COUNT:
        raise RuntimeError(f"Expected {UNIT_COUNT} source units, got {len(rows)}")
    result = []
    for expected, row in enumerate(rows):
        uid = int(row["unit_id"])
        if uid != expected:
            raise RuntimeError(f"Non-canonical unit ordering at {expected}: {uid}")
        result.append({
            "anchor_id": row["anchor_id"],
            "end_time": float(row["end_time"]),
            "start_time": float(row["start_time"]),
            "unit_id": uid,
            "video_id": row["video_id"],
        })
    return result


def stage_prepare() -> None:
    INFER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with INFER_LOCK.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another strict oracle prepare/infer/finalize process holds the lock") from exc
        _stage_prepare_locked()


def _stage_prepare_locked() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    if (
        any(RAW_DIR.glob("*.json"))
        or (ATTEMPT_LEDGER.exists() and ATTEMPT_LEDGER.stat().st_size)
        or INFERENCE_RUNTIME.exists()
        or COMPLETE_MARKER.exists()
    ):
        raise RuntimeError("Refusing to prepare over an oracle build with existing raw outputs or attempt history")
    prompt_hash = sha256_file(PROMPT_SOURCE)
    if prompt_hash != "12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33":
        raise RuntimeError("Frozen oracle prompt changed")
    atomic_write_bytes(PROMPT_TARGET, PROMPT_SOURCE.read_bytes())

    model_rows, model_hash = full_model_manifest()
    atomic_write_csv(MODEL_MANIFEST, model_rows)
    package_rows, package_hash = full_runtime_package_manifest(progress=True)
    atomic_write_csv(PACKAGE_MANIFEST, package_rows)
    video_hash = sha256_file(VIDEO)
    units = units_semantic_rows()
    cap = cv2.VideoCapture(str(VIDEO))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if video_fps <= 0 or frame_count <= 0:
        raise RuntimeError("Video metadata could not be decoded")

    config = {
        "base_seed": BASE_SEED,
        "frame_config": FRAME_CONFIG,
        "generation_config": GENERATION_CONFIG,
        "hardware_runtime_identity": hardware_runtime_identity(),
        "model_file_manifest_sha256": sha256_file(MODEL_MANIFEST),
        "model_full_content_hash": model_hash,
        "model_load_config": MODEL_LOAD_CONFIG,
        "parser_config": PARSER_CONFIG,
        "parser_source_hash": sha256_text(inspect.getsource(parse_response)),
        "processor_files": {
            name: sha256_file(MODEL / name)
            for name in [
                "chat_template.json", "config.json", "generation_config.json", "merges.txt",
                "preprocessor_config.json", "tokenizer.json", "tokenizer_config.json",
                "video_preprocessor_config.json", "vocab.json",
            ]
        },
        "prompt_sha256": prompt_hash,
        "rng_policy": {
            "cublas_workspace_config": ":4096:8",
            "deterministic_algorithms": True,
            "numpy_seed": "BASE_SEED + unit_id",
            "python_seed": "BASE_SEED + unit_id",
            "torch_cuda_seed_all": "BASE_SEED + unit_id",
            "torch_seed": "BASE_SEED + unit_id",
            "warn_only": False,
        },
        "runtime_package_content_hash": package_hash,
        "runtime_package_manifest_sha256": sha256_file(PACKAGE_MANIFEST),
        "runtime_versions": {
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "opencv_python": package_version("opencv-python"),
            "pillow": package_version("pillow"),
            "qwen_vl_utils": package_version("qwen-vl-utils"),
            "torch": package_version("torch"),
            "transformers": package_version("transformers"),
        },
        "sampling_code_hash": sha256_text(inspect.getsource(extract_frames) + inspect.getsource(frames_for_unit)),
        "script_sha256": sha256_file(Path(__file__)),
        "video_fps": video_fps,
        "video_frame_count": frame_count,
        "video_sha256": video_hash,
    }
    build_identity = {
        "configuration": json.loads(json.dumps(config)),
        "oracle_policy": "347_FRESH_PHYSICAL_CALLS_NO_LEGACY_RAW_REUSE",
        "unit_count": UNIT_COUNT,
        "units_sha256": canonical_hash(units),
    }
    oracle_build_id = "strict_oracle_" + canonical_hash(build_identity)[:20]
    config["oracle_build_id"] = oracle_build_id
    atomic_write_json(CONFIG_PATH, config)

    identities = []
    for unit in units:
        frames = frames_for_unit(unit["start_time"], unit["end_time"], video_fps)
        seed = BASE_SEED + unit["unit_id"]
        identity = {
            **unit,
            "decoded_frame_content_sha256": canonical_hash([frame["content_sha256"] for frame in frames]),
            "decoded_frame_count": len(frames),
            "decoded_frame_indices": [int(frame["decoded_index"]) for frame in frames],
            "decoded_frame_indices_sha256": canonical_hash([int(frame["decoded_index"]) for frame in frames]),
            "generation_config_hash": canonical_hash(GENERATION_CONFIG),
            "model_full_content_hash": model_hash,
            "oracle_build_id": oracle_build_id,
            "parser_hash": canonical_hash(PARSER_CONFIG),
            "processor_hash": canonical_hash(config["processor_files"]),
            "prompt_hash": prompt_hash,
            "rng_seed": seed,
            "sampling_code_hash": config["sampling_code_hash"],
            "video_sha256": video_hash,
        }
        identity["cache_input_identity_sha256"] = canonical_hash(identity)
        identities.append(identity)
        if (unit["unit_id"] + 1) % 25 == 0:
            print(json.dumps({"prepared_frame_identities": unit["unit_id"] + 1}), flush=True)
    atomic_write_text(IDENTITIES, "".join(json.dumps(row, sort_keys=True) + "\n" for row in identities))
    manifest = {
        "build_identity": build_identity,
        "created_at_utc": utc_now(),
        "input_identities_sha256": sha256_file(IDENTITIES),
        "model_file_manifest_sha256": sha256_file(MODEL_MANIFEST),
        "oracle_build_id": oracle_build_id,
        "physical_calls_required": UNIT_COUNT,
        "raw_reuse_policy": "ONLY_RESUME_THIS_BUILD_BY_EXACT_INPUT_IDENTITY",
        "status": "PREPARED",
        "strict_fresh_calls_required": True,
        "units_prepared": len(identities),
    }
    atomic_write_json(BUILD_MANIFEST, manifest)
    atomic_write_text(ATTEMPT_LEDGER, "")
    update_state(
        "--phase", "strict_oracle_prepared", "--phase-status", "completed",
        "--completed-units", "0", "--physical-vlm-calls", "0",
        "--physical-attempts-started", "0", "--uncertain-attempts", "0",
    )
    print(json.dumps({"oracle_build_id": oracle_build_id, "prepared_units": len(identities)}, sort_keys=True), flush=True)


def load_identities() -> tuple[list[dict], dict, dict]:
    identities = [json.loads(line) for line in IDENTITIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    if len(identities) != UNIT_COUNT or manifest["oracle_build_id"] != config["oracle_build_id"]:
        raise RuntimeError("Strict oracle preparation is incomplete or inconsistent")
    if sha256_file(IDENTITIES) != manifest["input_identities_sha256"]:
        raise RuntimeError("Input identities changed after preparation")
    config_without_id = {key: value for key, value in config.items() if key != "oracle_build_id"}
    build_identity = manifest.get("build_identity", {})
    if build_identity.get("configuration") != config_without_id:
        raise RuntimeError("Configuration is detached from the frozen build identity")
    units = units_semantic_rows()
    if build_identity.get("units_sha256") != canonical_hash(units) or build_identity.get("unit_count") != UNIT_COUNT:
        raise RuntimeError("Unit source is detached from the frozen build identity")
    expected_build_id = "strict_oracle_" + canonical_hash(build_identity)[:20]
    if expected_build_id != config["oracle_build_id"]:
        raise RuntimeError("Oracle-build ID does not recompute from the frozen build identity")
    if sha256_file(MODEL_MANIFEST) != config["model_file_manifest_sha256"]:
        raise RuntimeError("Model manifest bytes changed after preparation")
    if sha256_file(PACKAGE_MANIFEST) != config["runtime_package_manifest_sha256"]:
        raise RuntimeError("Runtime package manifest bytes changed after preparation")
    model_rows = [{
        "file": row["file"], "model_path": row["model_path"], "sha256": row["sha256"],
        "size_bytes": int(row["size_bytes"]),
    } for row in read_csv(MODEL_MANIFEST)]
    package_rows = [{
        "distribution": row["distribution"], "file": row["file"], "sha256": row["sha256"],
        "size_bytes": int(row["size_bytes"]), "version": row["version"],
    } for row in read_csv(PACKAGE_MANIFEST)]
    if canonical_hash(model_rows) != config["model_full_content_hash"]:
        raise RuntimeError("Model content hash does not recompute")
    if canonical_hash(package_rows) != config["runtime_package_content_hash"]:
        raise RuntimeError("Runtime package content hash does not recompute")
    expected_by_uid = {unit["unit_id"]: unit for unit in units}
    for expected_uid, identity in enumerate(identities):
        if identity.get("unit_id") != expected_uid:
            raise RuntimeError(f"Identity ordering mismatch at unit {expected_uid}")
        stored_hash = identity.get("cache_input_identity_sha256")
        unhashed = {key: value for key, value in identity.items() if key != "cache_input_identity_sha256"}
        if stored_hash != canonical_hash(unhashed):
            raise RuntimeError(f"Input identity hash does not recompute for unit {expected_uid}")
        expected_fields = {
            **expected_by_uid[expected_uid],
            "generation_config_hash": canonical_hash(config["generation_config"]),
            "model_full_content_hash": config["model_full_content_hash"],
            "oracle_build_id": config["oracle_build_id"],
            "parser_hash": canonical_hash(config["parser_config"]),
            "processor_hash": canonical_hash(config["processor_files"]),
            "prompt_hash": config["prompt_sha256"],
            "rng_seed": config["base_seed"] + expected_uid,
            "sampling_code_hash": config["sampling_code_hash"],
            "video_sha256": config["video_sha256"],
        }
        if any(identity.get(key) != value for key, value in expected_fields.items()):
            raise RuntimeError(f"Input identity fields are detached from config for unit {expected_uid}")
        indices = identity.get("decoded_frame_indices", [])
        if identity.get("decoded_frame_count") != len(indices) or identity.get("decoded_frame_indices_sha256") != canonical_hash(indices):
            raise RuntimeError(f"Frame-index identity is inconsistent for unit {expected_uid}")
    return identities, config, manifest


def verify_pre_inference_files(config: dict) -> None:
    if sha256_file(Path(__file__)) != config["script_sha256"]:
        raise RuntimeError("Strict oracle builder changed after preparation; rerun prepare before inference")
    if sha256_file(PROMPT_TARGET) != config["prompt_sha256"]:
        raise RuntimeError("Prompt changed after preparation")
    if sha256_file(VIDEO) != config["video_sha256"]:
        raise RuntimeError("Video changed after preparation")
    if hardware_runtime_identity() != config["hardware_runtime_identity"]:
        raise RuntimeError("GPU/runtime identity changed after preparation")
    if sha256_text(inspect.getsource(parse_response)) != config["parser_source_hash"]:
        raise RuntimeError("Parser source changed after preparation")
    recorded = read_csv(MODEL_MANIFEST)
    current_paths = sorted(path for path in MODEL.iterdir() if path.is_file())
    if [row["file"] for row in recorded] != [path.name for path in current_paths]:
        raise RuntimeError("Model file universe changed after preparation")
    verified_rows = []
    for row, path in zip(recorded, current_paths):
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != int(row["size_bytes"]) or digest != row["sha256"]:
            raise RuntimeError(f"Model file changed after preparation: {path.name}")
        verified_rows.append({
            "file": row["file"],
            "model_path": row["model_path"],
            "sha256": row["sha256"],
            "size_bytes": int(row["size_bytes"]),
        })
    if canonical_hash(verified_rows) != config["model_full_content_hash"]:
        raise RuntimeError("Verified full model manifest hash disagrees with prepared configuration")
    package_rows, package_hash = full_runtime_package_manifest(progress=True)
    if package_hash != config["runtime_package_content_hash"]:
        raise RuntimeError("Runtime package content changed after preparation")
    recorded_packages = [{
        "distribution": row["distribution"], "file": row["file"], "sha256": row["sha256"],
        "size_bytes": int(row["size_bytes"]), "version": row["version"],
    } for row in read_csv(PACKAGE_MANIFEST)]
    if package_rows != recorded_packages:
        raise RuntimeError("Runtime package manifest changed after preparation")


def validated_inference_runtime() -> dict:
    if not INFERENCE_RUNTIME.exists():
        raise RuntimeError("Resolved inference runtime artifact is absent")
    runtime = json.loads(INFERENCE_RUNTIME.read_text(encoding="utf-8"))
    claimed = runtime.get("resolved_inference_runtime_sha256")
    payload = {key: value for key, value in runtime.items() if key != "resolved_inference_runtime_sha256"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("Resolved inference runtime self-hash is invalid")
    return runtime


def validate_raw(path: Path, identity: dict) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    raw = record.get("raw")
    rng = record.get("rng_identity", {})
    frame_contents = record.get("per_frame_content_sha256", [])
    input_manifest = record.get("model_input_manifest", {})
    input_tensors = input_manifest.get("tensors", [])
    runtime_hash = None
    if INFERENCE_RUNTIME.exists():
        try:
            runtime_hash = validated_inference_runtime()["resolved_inference_runtime_sha256"]
        except RuntimeError:
            return False
    return bool(
        record.get("anchor_id") == identity["anchor_id"]
        and isinstance(record.get("attempt_id"), str)
        and record["attempt_id"].startswith(identity["oracle_build_id"] + f"_u{identity['unit_id']:04d}_a")
        and record.get("cache_input_identity_sha256") == identity["cache_input_identity_sha256"]
        and record.get("decoded_frame_indices") == identity["decoded_frame_indices"]
        and canonical_hash(frame_contents) == identity["decoded_frame_content_sha256"]
        and record.get("generation_config") == GENERATION_CONFIG
        and input_manifest.get("model_input_identity_sha256") == canonical_hash({
            key: value for key, value in input_manifest.items() if key != "model_input_identity_sha256"
        })
        and any(tensor.get("name") == "input_ids" and is_sha256(tensor.get("sha256")) for tensor in input_tensors)
        and any("pixel" in str(tensor.get("name")) and is_sha256(tensor.get("sha256")) for tensor in input_tensors)
        and any("grid" in str(tensor.get("name")) and is_sha256(tensor.get("sha256")) for tensor in input_tensors)
        and record.get("oracle_build_id") == identity["oracle_build_id"]
        and record.get("physical_vlm_call") is True
        and record.get("rng_seed") == identity["rng_seed"]
        and runtime_hash is not None
        and record.get("resolved_inference_runtime_sha256") == runtime_hash
        and rng.get("deterministic_algorithms_enabled") is True
        and rng.get("cublas_workspace_config") == EXPECTED_CUBLAS_WORKSPACE_CONFIG
        and rng.get("numpy_seed") == identity["rng_seed"]
        and rng.get("python_seed") == identity["rng_seed"]
        and rng.get("torch_cuda_seed_all") == identity["rng_seed"]
        and rng.get("torch_seed") == identity["rng_seed"]
        and rng.get("warn_only") is False
        and rng.get("rng_state_identity_sha256") == canonical_hash({
            key: value for key, value in rng.items() if key != "rng_state_identity_sha256"
        })
        and is_sha256(rng.get("python_rng_state_sha256"))
        and is_sha256(rng.get("torch_cpu_rng_state_sha256"))
        and len(rng.get("cuda_rng_state_sha256", [])) == len(json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["hardware_runtime_identity"]["devices"])
        and all(is_sha256(value) for value in rng.get("cuda_rng_state_sha256", []))
        and record.get("unit_end") == identity["end_time"]
        and record.get("unit_id") == identity["unit_id"]
        and record.get("unit_start") == identity["start_time"]
        and isinstance(raw, str)
        and raw.strip()
        and record.get("raw_response_sha256") == sha256_text(raw)
    )


def configure_rng(seed: int, torch_module) -> dict:
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != EXPECTED_CUBLAS_WORKSPACE_CONFIG:
        raise RuntimeError("CUBLAS determinism setting changed before generation")
    random.seed(seed)
    np.random.seed(seed)
    torch_module.manual_seed(seed)
    torch_module.cuda.manual_seed_all(seed)
    torch_module.use_deterministic_algorithms(True, warn_only=False)
    numpy_state = np.random.get_state()
    record = {
        "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "cuda_rng_state_sha256": [
            sha256_bytes(state.detach().cpu().contiguous().view(torch_module.uint8).numpy().tobytes())
            for state in torch_module.cuda.get_rng_state_all()
        ],
        "deterministic_algorithms_enabled": torch_module.are_deterministic_algorithms_enabled(),
        "numpy_rng_state": {
            "bit_generator": numpy_state[0],
            "cached_gaussian": float(numpy_state[4]),
            "has_gaussian": int(numpy_state[3]),
            "position": int(numpy_state[2]),
            "state_sha256": sha256_bytes(numpy_state[1].tobytes()),
        },
        "numpy_seed": seed,
        "python_rng_state_sha256": canonical_hash(random.getstate()),
        "python_seed": seed,
        "torch_cpu_rng_state_sha256": sha256_bytes(
            torch_module.get_rng_state().detach().cpu().contiguous().view(torch_module.uint8).numpy().tobytes()
        ),
        "torch_cuda_seed_all": seed,
        "torch_initial_seed": int(torch_module.initial_seed()),
        "torch_seed": seed,
        "warn_only": False,
    }
    record["rng_state_identity_sha256"] = canonical_hash(record)
    return record


def resolved_inference_runtime(model, processor) -> dict:
    device_map = {
        str(key): str(value) for key, value in sorted(getattr(model, "hf_device_map", {}).items())
    }
    parameter_dtypes = sorted({str(parameter.dtype) for parameter in model.parameters()})
    value = {
        "explicit_generation_overrides": GENERATION_CONFIG,
        "hf_device_map": device_map,
        "model_class": f"{model.__class__.__module__}.{model.__class__.__name__}",
        "model_config_sha256": canonical_hash(model.config.to_dict()),
        "model_generation_config": model.generation_config.to_dict(),
        "parameter_dtypes": parameter_dtypes,
        "processor_class": f"{processor.__class__.__module__}.{processor.__class__.__name__}",
        "processor_repr": repr(processor),
    }
    value["resolved_inference_runtime_sha256"] = canonical_hash(value)
    return value


def tensor_bytes(tensor, torch_module) -> bytes:
    return tensor.detach().cpu().contiguous().view(torch_module.uint8).numpy().tobytes()


def model_input_manifest(inputs, prompt_text: str, torch_module) -> dict:
    tensors = []
    for name, value in sorted(inputs.items()):
        if not torch_module.is_tensor(value):
            continue
        tensors.append({
            "dtype": str(value.dtype),
            "name": str(name),
            "sha256": sha256_bytes(tensor_bytes(value, torch_module)),
            "shape": list(value.shape),
        })
    result = {"prompt_text_sha256": sha256_text(prompt_text), "tensors": tensors}
    result["model_input_identity_sha256"] = canonical_hash(result)
    return result


def reconcile_attempt_log(identities: list[dict]) -> None:
    by_uid = {identity["unit_id"]: identity for identity in identities}
    events = read_attempt_events()
    terminal_ids = {
        event["attempt_id"] for event in events
        if event.get("event") in {"ACCEPTED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}
    }
    for event in events:
        if event.get("event") != "STARTED" or event["attempt_id"] in terminal_ids:
            continue
        identity = by_uid[int(event["unit_id"])]
        raw_path = RAW_DIR / f"{identity['anchor_id']}.json"
        accepted = validate_raw(raw_path, identity)
        if accepted:
            record = json.loads(raw_path.read_text(encoding="utf-8"))
            accepted = record.get("attempt_id") == event["attempt_id"]
        recovery_event = {
            "attempt_id": event["attempt_id"],
            "event": "RECOVERED_ACCEPTED" if accepted else "RECOVERED_UNCERTAIN",
            "reason": "durable_exact_raw_found" if accepted else "no_durable_exact_raw_at_recovery",
            "timestamp": utc_now(),
            "unit_id": identity["unit_id"],
        }
        if accepted:
            recovery_event["raw_envelope_sha256"] = sha256_file(raw_path)
            recovery_event["raw_response_sha256"] = record["raw_response_sha256"]
        append_attempt_event(recovery_event)


def verify_raw_attempt_links(identities: list[dict]) -> None:
    events = read_attempt_events()
    started_events = {event["attempt_id"]: event for event in events if event.get("event") == "STARTED"}
    accepted_events = {
        event["attempt_id"]: event for event in events
        if event.get("event") in {"ACCEPTED", "RECOVERED_ACCEPTED"}
    }
    for identity in identities:
        path = RAW_DIR / f"{identity['anchor_id']}.json"
        if not validate_raw(path, identity):
            continue
        attempt_id = json.loads(path.read_text(encoding="utf-8"))["attempt_id"]
        if attempt_id not in accepted_events:
            raise RuntimeError(f"Raw output lacks an accepted attempt event: unit {identity['unit_id']}")
        event = accepted_events[attempt_id]
        record = json.loads(path.read_text(encoding="utf-8"))
        if event.get("raw_envelope_sha256") != sha256_file(path) or event.get("raw_response_sha256") != record["raw_response_sha256"]:
            raise RuntimeError(f"Accepted attempt event disagrees with raw output: unit {identity['unit_id']}")
        started = started_events[attempt_id]
        expected_started = {
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "model_input_identity_sha256": record["model_input_manifest"]["model_input_identity_sha256"],
            "resolved_inference_runtime_sha256": record["resolved_inference_runtime_sha256"],
            "rng_state_identity_sha256": record["rng_identity"]["rng_state_identity_sha256"],
            "unit_id": identity["unit_id"],
        }
        if any(started.get(key) != value for key, value in expected_started.items()):
            raise RuntimeError(f"STARTED event identity disagrees with raw output: unit {identity['unit_id']}")


def stage_infer(limit: int | None) -> None:
    INFER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with INFER_LOCK.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another strict oracle inference process holds the exclusive lock") from exc
        _stage_infer_locked(limit)


def _stage_infer_locked(limit: int | None) -> None:
    identities, config, manifest = load_identities()
    verify_pre_inference_files(config)
    reconcile_attempt_log(identities)
    invalid = [identity["unit_id"] for identity in identities if (RAW_DIR / f"{identity['anchor_id']}.json").exists() and not validate_raw(RAW_DIR / f"{identity['anchor_id']}.json", identity)]
    if invalid:
        raise RuntimeError(f"Invalid existing strict raw outputs require audit, refusing overwrite: {invalid[:10]}")
    verify_raw_attempt_links(identities)
    completed = sum(validate_raw(RAW_DIR / f"{identity['anchor_id']}.json", identity) for identity in identities)
    attempts = attempt_summary()
    if completed == UNIT_COUNT:
        update_oracle_state("strict_oracle_inference", "completed", UNIT_COUNT, attempts)
        print(json.dumps({"status": "ALL_VALID_EXISTING_STRICT_RAW", "units": completed, **attempts}), flush=True)
        return

    update_oracle_state("strict_oracle_inference", "in_progress", completed, attempts)
    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    load_started = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model.eval()
    load_seconds = time.time() - load_started
    resolved_runtime = resolved_inference_runtime(model, processor)
    if INFERENCE_RUNTIME.exists():
        if validated_inference_runtime() != resolved_runtime:
            raise RuntimeError("Resolved inference runtime changed across resume")
    else:
        atomic_write_json(INFERENCE_RUNTIME, resolved_runtime)

    cap = cv2.VideoCapture(str(VIDEO))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    new_calls = 0
    for identity in identities:
        output_path = RAW_DIR / f"{identity['anchor_id']}.json"
        if validate_raw(output_path, identity):
            continue
        if limit is not None and new_calls >= limit:
            break
        frames = frames_for_unit(identity["start_time"], identity["end_time"], video_fps)
        indices = [int(frame["decoded_index"]) for frame in frames]
        contents = [frame["content_sha256"] for frame in frames]
        if canonical_hash(indices) != identity["decoded_frame_indices_sha256"] or canonical_hash(contents) != identity["decoded_frame_content_sha256"]:
            raise RuntimeError(f"Frame identity changed before inference for unit {identity['unit_id']}")

        pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
        messages = [{"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": FRAME_CONFIG["message_fps"]},
            {"type": "text", "text": PROMPT_TARGET.read_text(encoding="utf-8")},
        ]}]
        prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[prompt_text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt"
        ).to(model.device)
        input_manifest = model_input_manifest(inputs, prompt_text, torch)
        torch.cuda.reset_peak_memory_stats()
        rng_record = configure_rng(identity["rng_seed"], torch)
        prior_unit_attempts = sum(
            event.get("event") == "STARTED" and int(event.get("unit_id", -1)) == identity["unit_id"]
            for event in read_attempt_events()
        )
        attempt_id = f"{config['oracle_build_id']}_u{identity['unit_id']:04d}_a{prior_unit_attempts + 1:03d}"
        started_at = utc_now()
        append_attempt_event({
            "attempt_id": attempt_id,
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "event": "STARTED",
            "model_input_identity_sha256": input_manifest["model_input_identity_sha256"],
            "resolved_inference_runtime_sha256": resolved_runtime["resolved_inference_runtime_sha256"],
            "rng_state_identity_sha256": rng_record["rng_state_identity_sha256"],
            "timestamp": started_at,
            "unit_id": identity["unit_id"],
        })
        attempts = attempt_summary()
        update_oracle_state("strict_oracle_inference", "in_progress", completed, attempts)
        started = time.time()
        with torch.no_grad():
            generated_ids = model.generate(**inputs, do_sample=False, max_new_tokens=GENERATION_CONFIG["max_new_tokens"])
        torch.cuda.synchronize()
        runtime = time.time() - started
        trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated_ids)]
        raw_text = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        record = {
            "anchor_id": identity["anchor_id"],
            "attempt_id": attempt_id,
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "call_completed_at_utc": utc_now(),
            "call_started_at_utc": started_at,
            "decoded_frame_indices": indices,
            "decoded_frame_timestamps_seconds": [round(float(frame["decoded_timestamp_seconds"]), 9) for frame in frames],
            "generation_config": GENERATION_CONFIG,
            "generation_runtime_seconds": runtime,
            "model_load_seconds": load_seconds if new_calls == 0 else 0.0,
            "model_input_manifest": input_manifest,
            "oracle_build_id": config["oracle_build_id"],
            "peak_gpu_memory_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_gpu_memory_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "per_frame_content_sha256": contents,
            "physical_vlm_call": True,
            "raw": raw_text,
            "raw_response_sha256": sha256_text(raw_text),
            "resolved_inference_runtime_sha256": resolved_runtime["resolved_inference_runtime_sha256"],
            "rng_identity": rng_record,
            "rng_seed": identity["rng_seed"],
            "unit_end": identity["end_time"],
            "unit_id": identity["unit_id"],
            "unit_start": identity["start_time"],
        }
        atomic_write_json(output_path, record)
        if not validate_raw(output_path, identity):
            raise RuntimeError(f"Atomic strict raw validation failed for unit {identity['unit_id']}")
        append_attempt_event({
            "attempt_id": attempt_id,
            "event": "ACCEPTED",
            "raw_envelope_sha256": sha256_file(output_path),
            "raw_response_sha256": record["raw_response_sha256"],
            "timestamp": utc_now(),
            "unit_id": identity["unit_id"],
        })
        new_calls += 1
        completed = sum(validate_raw(RAW_DIR / f"{item['anchor_id']}.json", item) for item in identities)
        attempts = attempt_summary()
        update_oracle_state("strict_oracle_inference", "in_progress", completed, attempts)
        print(json.dumps({
            "completed_units": completed,
            "generation_runtime_seconds": runtime,
            "raw_response_sha256": record["raw_response_sha256"],
            "unit_id": identity["unit_id"],
        }, sort_keys=True), flush=True)

    completed = sum(validate_raw(RAW_DIR / f"{identity['anchor_id']}.json", identity) for identity in identities)
    verify_raw_attempt_links(identities)
    attempts = attempt_summary()
    status = "completed" if completed == UNIT_COUNT else "in_progress"
    update_oracle_state("strict_oracle_inference", status, completed, attempts)
    manifest["completed_units"] = completed
    manifest["physical_attempts_started"] = attempts["physical_attempts_started"]
    manifest["accepted_attempts"] = attempts["accepted_attempts"]
    manifest["uncertain_attempts"] = attempts["uncertain_attempts"]
    manifest["status"] = "INFERENCE_COMPLETE" if completed == UNIT_COUNT else "INFERENCE_IN_PROGRESS"
    manifest["updated_at_utc"] = utc_now()
    atomic_write_json(BUILD_MANIFEST, manifest)
    print(json.dumps({"completed_units": completed, "new_calls": new_calls, "status": status, **attempts}), flush=True)


def stage_finalize() -> None:
    INFER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with INFER_LOCK.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Cannot finalize while strict oracle inference holds the exclusive lock") from exc
        _stage_finalize_locked()


def _stage_finalize_locked() -> None:
    if COMPLETE_MARKER.exists():
        stage_verify()
        committed_attempts = attempt_summary()
        update_oracle_state("strict_oracle_cache", "completed", UNIT_COUNT, committed_attempts)
        return
    identities, config, manifest = load_identities()
    verify_pre_inference_files(config)
    reconcile_attempt_log(identities)
    verify_raw_attempt_links(identities)
    attempts = attempt_summary()
    units = {int(row["unit_id"]): row for row in read_csv(UNITS_SOURCE)}
    if not all(validate_raw(RAW_DIR / f"{identity['anchor_id']}.json", identity) for identity in identities):
        raise RuntimeError("Cannot finalize before all 347 strict raw calls validate")
    if attempts["accepted_attempts"] != UNIT_COUNT or attempts["unresolved_attempt_ids"]:
        raise RuntimeError(f"Attempt log does not support 347 accepted outputs: {attempts}")
    manifest["status"] = "FINALIZING"
    manifest["finalizing_started_at_utc"] = utc_now()
    atomic_write_json(BUILD_MANIFEST, manifest)
    cache_rows: list[dict] = []
    ledger_rows: list[dict] = []
    observations: list[dict] = []
    raw_jsonl = []
    parse_failures = 0
    for identity in identities:
        uid = int(identity["unit_id"])
        raw_path = RAW_DIR / f"{identity['anchor_id']}.json"
        raw_record = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_text = raw_record["raw"]
        raw_jsonl.append(raw_record)
        parsed, parse_status = parse_response(raw_text)
        if parse_status != "ok":
            parse_failures += 1
        label = str(parsed.get("label", "abstain")).lower()
        unit = units[uid]
        start = float(unit["start_time"])

        def absolute(value: object) -> str:
            if value in (None, "", "null"):
                return ""
            try:
                return str(start + float(value))
            except (TypeError, ValueError):
                return ""

        parsed_record = {
            "anchor_id": identity["anchor_id"],
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "oracle_build_id": config["oracle_build_id"],
            "parse_status": parse_status,
            "parsed": parsed,
            "parsed_sha256": canonical_hash(parsed),
            "parser_hash": identity["parser_hash"],
            "unit_id": uid,
        }
        parsed_path = PARSED_DIR / f"{identity['anchor_id']}.json"
        atomic_write_json(parsed_path, parsed_record)
        attempt_id = raw_record["attempt_id"]
        cache_rows.append({
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "cache_source": "STRICT_FRESH_VLM_RESPONSE",
            "cache_valid": parse_status == "ok",
            "decoded_frame_content_sha256": identity["decoded_frame_content_sha256"],
            "decoded_frame_count": identity["decoded_frame_count"],
            "decoded_frame_indices": "|".join(map(str, identity["decoded_frame_indices"])),
            "decoded_frame_indices_sha256": identity["decoded_frame_indices_sha256"],
            "generation_config_hash": identity["generation_config_hash"],
            "model_full_content_hash": identity["model_full_content_hash"],
            "oracle_build_id": config["oracle_build_id"],
            "physical_attempt_id": attempt_id,
            "parsed_observation_path": str(parsed_path.relative_to(PACK)),
            "parsed_observation_sha256": parsed_record["parsed_sha256"],
            "parser_hash": identity["parser_hash"],
            "physical_vlm_call": True,
            "processor_hash": identity["processor_hash"],
            "prompt_hash": identity["prompt_hash"],
            "raw_envelope_sha256": sha256_file(raw_path),
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_record["raw_response_sha256"],
            "reuse_basis": "EXACT_SAME_STRICT_BUILD_RESUME_ONLY",
            "rng_seed": identity["rng_seed"],
            "sampling_code_hash": identity["sampling_code_hash"],
            "unit_end": identity["end_time"],
            "unit_id": uid,
            "unit_start": identity["start_time"],
            "video_sha256": identity["video_sha256"],
        })
        ledger_rows.append({
            "anchor_id": identity["anchor_id"],
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "cache_source": "STRICT_FRESH_VLM_RESPONSE",
            "generation_runtime_seconds": raw_record["generation_runtime_seconds"],
            "logical_method_budget_charged": False,
            "oracle_build_id": config["oracle_build_id"],
            "physical_attempt_id": attempt_id,
            "physical_call_count": 1,
            "physical_vlm_call": True,
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_record["raw_response_sha256"],
            "rng_seed": identity["rng_seed"],
            "status": "VALID" if parse_status == "ok" else "INVALID_PARSE",
            "unit_id": uid,
        })
        observations.append({
            "anchor_id": identity["anchor_id"],
            "abstain_reason": parsed.get("abstain_reason", "null"),
            "anchor_time": min(start + 5.0, float(unit["end_time"])),
            "boundary_reliable": False,
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": parsed.get("complete_event_visible", ""),
            "confidence": parsed.get("confidence", "low"),
            "duration": float(unit["duration_seconds"]),
            "ego_relevant": parsed.get("ego_relevant", ""),
            "end_time": float(unit["end_time"]),
            "event_end": "" if parsed.get("event_end") is None else parsed.get("event_end"),
            "event_end_absolute": absolute(parsed.get("event_end")),
            "event_start": "" if parsed.get("event_start") is None else parsed.get("event_start"),
            "event_start_absolute": absolute(parsed.get("event_start")),
            "event_type": parsed.get("event_type", "none"),
            "evidence": parsed.get("evidence", ""),
            "involved_object": parsed.get("involved_object", "none"),
            "label": label,
            "negative_reason": parsed.get("negative_reason", "null"),
            "oracle_build_id": config["oracle_build_id"],
            "parse_status": parse_status,
            "parsed_observation_sha256": parsed_record["parsed_sha256"],
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_record["raw_response_sha256"],
            "runtime_seconds": raw_record["generation_runtime_seconds"],
            "start_time": start,
            "unit_id": uid,
            "video_id": "long_video_dataset3",
        })
    cache_path = PACK / "oracle/oracle_cache_manifest.csv"
    call_ledger_path = PACK / "oracle/VLM_CALL_LEDGER.csv"
    observations_path = PARSED_DIR / "oracle_observations_source.csv"
    raw_jsonl_path = PACK / "oracle/oracle_raw_outputs.jsonl"
    atomic_write_csv(cache_path, cache_rows)
    atomic_write_csv(call_ledger_path, ledger_rows)
    atomic_write_csv(observations_path, observations)
    atomic_write_text(raw_jsonl_path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in raw_jsonl))
    parsed_manifest_rows = [{
        "anchor_id": identity["anchor_id"],
        "path": str((PARSED_DIR / f"{identity['anchor_id']}.json").relative_to(PACK)),
        "sha256": sha256_file(PARSED_DIR / f"{identity['anchor_id']}.json"),
        "unit_id": identity["unit_id"],
    } for identity in identities]
    atomic_write_csv(PARSED_MANIFEST, parsed_manifest_rows)
    if parse_failures:
        manifest["parse_failures"] = parse_failures
        manifest["status"] = "FINALIZE_FAILED_PARSE"
        atomic_write_json(BUILD_MANIFEST, manifest)
        raise RuntimeError(f"Strict parser rejected {parse_failures} oracle outputs")
    exact_attempts = (
        attempts["physical_attempts_started"]
        if attempts["uncertain_attempts"] == 0 and not attempts["unresolved_attempt_ids"]
        else None
    )
    report = f"""# Strict Benchmark v2 Oracle Build Report

- Status: `COMPLETE_COMMITTED`
- Oracle-build ID: `{config['oracle_build_id']}`
- Units: {UNIT_COUNT}
- Accepted durable fresh outputs: {attempts['accepted_attempts']}
- Physical attempts started (upper bound if interrupted): {attempts['physical_attempts_started']}
- Exact physical generate invocations: {exact_attempts if exact_attempts is not None else 'UNKNOWN_WITHIN_RECORDED_BOUNDS'}
- Uncertain interrupted attempts: {attempts['uncertain_attempts']}
- Legacy raw responses reused: 0
- Parse failures/invalid labels: {parse_failures}
- Full model-content hash: `{config['model_full_content_hash']}`
- Model file manifest SHA256: `{config['model_file_manifest_sha256']}`
- Prompt SHA256: `{config['prompt_sha256']}`
- Generation-config hash: `{canonical_hash(GENERATION_CONFIG)}`
- Input-identities SHA256: `{manifest['input_identities_sha256']}`

Every raw response was atomically saved before parsing. Each call binds the
full model-file content manifest, prompt, parser, sampler, decoded frame
indices/content, explicit greedy generation configuration, and per-unit RNG
identity. Existing output reuse is allowed only to resume this exact strict
oracle-build ID and exact input identity.
"""
    report_path = PACK / "oracle/STRICT_ORACLE_BUILD_REPORT.md"
    atomic_write_text(report_path, report)
    artifact_paths = [
        ATTEMPT_LEDGER,
        cache_path,
        call_ledger_path,
        observations_path,
        raw_jsonl_path,
        PARSED_MANIFEST,
        report_path,
        INFERENCE_RUNTIME,
        IDENTITIES,
        CONFIG_PATH,
        MODEL_MANIFEST,
        PACKAGE_MANIFEST,
    ]
    artifact_hashes = {str(path.relative_to(PACK)): sha256_file(path) for path in artifact_paths}
    manifest.update({
        "accepted_durable_outputs": attempts["accepted_attempts"],
        "artifact_hashes": artifact_hashes,
        "completed_at_utc": utc_now(),
        "completed_units": UNIT_COUNT,
        "exact_physical_generate_invocations": exact_attempts,
        "legacy_raw_responses_reused": 0,
        "parse_failures": 0,
        "physical_attempts_started": attempts["physical_attempts_started"],
        "physical_vlm_calls": exact_attempts,
        "status": "COMPLETE",
        "uncertain_attempts": attempts["uncertain_attempts"],
    })
    atomic_write_json(BUILD_MANIFEST, manifest)
    marker = {
        "artifact_hashes": artifact_hashes,
        "benchmark_phase": "STRICT_ORACLE_BUILD",
        "committed_at_utc": utc_now(),
        "manifest_sha256": sha256_file(BUILD_MANIFEST),
        "oracle_build_id": config["oracle_build_id"],
        "status": "COMPLETE_COMMIT",
    }
    atomic_write_json(COMPLETE_MARKER, marker)
    update_oracle_state("strict_oracle_cache", "completed", UNIT_COUNT, attempts)
    print(json.dumps({
        "accepted_durable_outputs": attempts["accepted_attempts"],
        "exact_physical_generate_invocations": exact_attempts,
        "oracle_build_id": config["oracle_build_id"],
        "parse_failures": parse_failures,
        "physical_attempts_started": attempts["physical_attempts_started"],
        "status": "COMPLETE_COMMIT",
    }, sort_keys=True), flush=True)


def stage_verify() -> None:
    identities, config, manifest = load_identities()
    verify_pre_inference_files(config)
    if not COMPLETE_MARKER.exists():
        raise RuntimeError("Strict oracle COMPLETE commit marker is absent")
    marker = json.loads(COMPLETE_MARKER.read_text(encoding="utf-8"))
    if marker.get("status") != "COMPLETE_COMMIT" or marker.get("oracle_build_id") != config["oracle_build_id"]:
        raise RuntimeError("Strict oracle COMPLETE marker identity/status is invalid")
    if marker.get("manifest_sha256") != sha256_file(BUILD_MANIFEST):
        raise RuntimeError("Strict oracle manifest changed after COMPLETE commit")
    if manifest.get("status") != "COMPLETE" or manifest.get("parse_failures") != 0:
        raise RuntimeError("Strict oracle manifest is not a zero-parse-failure COMPLETE state")
    for relative, digest in marker.get("artifact_hashes", {}).items():
        path = PACK / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"Committed strict artifact changed or disappeared: {relative}")
    verify_raw_attempt_links(identities)
    attempts = attempt_summary()
    if attempts["unresolved_attempt_ids"] or attempts["accepted_attempts"] != UNIT_COUNT:
        raise RuntimeError(f"Strict attempt-log invariants failed: {attempts}")
    valid = sum(validate_raw(RAW_DIR / f"{identity['anchor_id']}.json", identity) for identity in identities)
    if valid != UNIT_COUNT:
        raise RuntimeError(f"Only {valid}/{UNIT_COUNT} strict raw outputs validate")
    cache_rows = read_csv(PACK / "oracle/oracle_cache_manifest.csv")
    call_rows = read_csv(PACK / "oracle/VLM_CALL_LEDGER.csv")
    observations = read_csv(PARSED_DIR / "oracle_observations_source.csv")
    parsed_rows = read_csv(PARSED_MANIFEST)
    raw_rows = read_jsonl(PACK / "oracle/oracle_raw_outputs.jsonl")
    frames = [cache_rows, call_rows, observations, parsed_rows, raw_rows]
    if any(len(frame) != UNIT_COUNT for frame in frames):
        raise RuntimeError(f"Finalized strict row counts are not all 347: {[len(frame) for frame in frames]}")
    if any(len({int(row["unit_id"]) for row in frame}) != UNIT_COUNT for frame in frames):
        raise RuntimeError("A finalized strict artifact has duplicate or missing unit IDs")
    if not all(row["cache_valid"].lower() == "true" for row in cache_rows):
        raise RuntimeError("Strict cache manifest contains an invalid entry")
    if not all(row["status"] == "VALID" and row["physical_vlm_call"].lower() == "true" for row in call_rows):
        raise RuntimeError("Strict VLM call ledger contains a non-valid/non-physical entry")
    if not all(row["parse_status"] == "ok" for row in observations):
        raise RuntimeError("Strict observations contain a parser failure")
    for row in parsed_rows:
        path = PACK / row["path"]
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if sha256_file(path) != row["sha256"] or parsed.get("parse_status") != "ok":
            raise RuntimeError(f"Parsed output failed verification: {row['path']}")
    for identity, raw_row in zip(identities, raw_rows):
        path_row = json.loads((RAW_DIR / f"{identity['anchor_id']}.json").read_text(encoding="utf-8"))
        if raw_row != path_row:
            raise RuntimeError(f"Raw JSONL disagrees with per-unit envelope at unit {identity['unit_id']}")
    expected_artifacts = manifest.get("artifact_hashes", {})
    if expected_artifacts != marker.get("artifact_hashes"):
        raise RuntimeError("Manifest and COMPLETE marker artifact sets disagree")
    result = {
        **attempts,
        "complete_marker_sha256": sha256_file(COMPLETE_MARKER),
        "input_identities_sha256": sha256_file(IDENTITIES),
        "manifest_status": manifest["status"],
        "model_file_manifest_sha256": sha256_file(MODEL_MANIFEST),
        "oracle_build_id": config["oracle_build_id"],
        "strict_raw_valid": valid,
        "strict_raw_expected": UNIT_COUNT,
        "verified": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["prepare", "infer", "finalize", "verify", "all"])
    parser.add_argument("--limit", type=int, help="Maximum new physical calls for this invocation (resumability smoke only).")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.stage in {"prepare", "all"}:
        stage_prepare()
    if args.stage in {"infer", "all"}:
        stage_infer(args.limit)
    if args.stage in {"finalize", "all"}:
        stage_finalize()
    if args.stage == "verify":
        stage_verify()


if __name__ == "__main__":
    main()
