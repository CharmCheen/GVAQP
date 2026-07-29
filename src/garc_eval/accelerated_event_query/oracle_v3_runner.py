"""Fail-closed runner for the sealed AEQ model-relative V3 preflight."""

from __future__ import annotations

import argparse
import fcntl
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import time
from fractions import Fraction
from pathlib import Path

EXPECTED_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
if os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in {None, EXPECTED_CUBLAS_WORKSPACE_CONFIG}:
    raise RuntimeError("conflicting CUBLAS_WORKSPACE_CONFIG was set before oracle startup")
os.environ["CUBLAS_WORKSPACE_CONFIG"] = EXPECTED_CUBLAS_WORKSPACE_CONFIG
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from .oracle_protocol import extract_exact_frames, public_frame_record
from .oracle_v3_manifest import (
    atomic_text,
    canonical_hash,
    load_json,
    sha256_file,
    validate_call_manifest,
    validate_frame_set,
    write_json_once,
)
from .oracle_v3_parser import parse_oracle_v3_response


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
PREREG = BASE / "preflight/V3_SCHEMA_PREFLIGHT_PREREGISTRATION.json"
SEAL = BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_EXECUTION_SEAL.json"
RAW = BASE / "raw"
ATTEMPTS = BASE / "preflight/attempt_ledgers"
LOCKS = BASE / "preflight/locks"
SHARDS = ("DALI", "HANGZHOU", "WUHAN")


def validate_execution_seal(component: str = "runner") -> tuple[dict, dict]:
    seal = load_json(SEAL)
    prereg = load_json(PREREG)
    if seal.get("status") != "FROZEN_AWAITING_EXPLICIT_COMPUTE_APPROVAL":
        raise RuntimeError("V3 execution seal is not awaiting approval")
    if seal.get("preregistration_sha256") != sha256_file(PREREG):
        raise RuntimeError("execution seal/preregistration mismatch")
    sources = seal.get("sources", {})
    path_key = f"{component}_source_path"
    hash_key = f"{component}_source_sha256"
    source_path = ROOT / sources[path_key]
    if sha256_file(source_path) != sources[hash_key]:
        raise RuntimeError(f"execution seal/{component} source mismatch")
    return seal, prereg


def validate_bindings(prereg: dict) -> None:
    for key, relative in prereg["bindings"].items():
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        if hash_key not in prereg["bindings"]:
            continue
        observed = sha256_file(ROOT / relative)
        if observed != prereg["bindings"][hash_key]:
            raise RuntimeError(f"V3 binding mismatch: {relative}")
    model_audit = load_json(ROOT / prereg["bindings"]["model_identity_audit_path"])
    if not all((
        model_audit.get("status") == "PASS",
        model_audit.get("all_current_sha256_values_match_prior_manifest") is True,
        model_audit.get("expected_model_content_hash") == prereg["model"]["model_content_hash"],
    )):
        raise RuntimeError("model identity audit mismatch")


def verify_current_model_files(prereg: dict) -> str:
    manifest_path = ROOT / prereg["bindings"]["model_file_manifest_path"]
    manifest = load_json(manifest_path)
    model_path = ROOT / prereg["model"]["model_path"]
    expected = {row["file"]: row for row in manifest["files"]}
    observed_names = {path.name for path in model_path.iterdir() if path.is_file()}
    if observed_names != set(expected):
        raise RuntimeError("current model file set differs from frozen manifest")
    rows = []
    for name in sorted(expected):
        path = model_path / name
        row = {"file": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        if row != expected[name]:
            raise RuntimeError(f"current model file mismatch: {name}")
        rows.append(row)
    if canonical_hash(rows) != prereg["model"]["model_content_hash"]:
        raise RuntimeError("current canonical model content hash mismatch")
    return sha256_file(manifest_path)


def validate_compute_approval(path: Path, prereg: dict) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(BASE.resolve()):
        raise RuntimeError("compute approval must be stored inside the V3 output root")
    approval = load_json(resolved)
    expected_keys = {
        "status", "experiment_id", "execution_seal_sha256",
        "authorized_call_manifest_sha256", "approved_physical_call_count",
        "approval_scope", "user_approval_evidence",
    }
    expected_scope = (
        "exactly the 11 sealed V3 schema-and-determinism preflight calls; zero retry; "
        "no full-grid or downstream execution"
    )
    if set(approval) != expected_keys or not all((
        approval.get("status") == "APPROVED_BY_USER",
        approval.get("experiment_id") == prereg["experiment_id"],
        approval.get("execution_seal_sha256") == sha256_file(SEAL),
        approval.get("authorized_call_manifest_sha256")
            == prereg["bindings"]["authorized_call_manifest_sha256"],
        approval.get("approved_physical_call_count")
            == prereg["workload"]["total_physical_calls"] == 11,
        approval.get("approval_scope") == expected_scope,
        isinstance(approval.get("user_approval_evidence"), str),
        bool(approval.get("user_approval_evidence", "").strip()),
        "FILL" not in approval.get("user_approval_evidence", ""),
    )):
        raise RuntimeError("approval does not authorize the exact sealed V3 preflight")
    return sha256_file(resolved)


def frozen_context() -> tuple[dict, dict, dict, dict]:
    _, prereg = validate_execution_seal("runner")
    validate_bindings(prereg)
    videos = {
        row["video_id"]: row
        for row in load_json(ROOT / prereg["bindings"]["video_manifest_path"])["videos"]
    }
    frame_manifest = load_json(ROOT / prereg["bindings"]["frame_manifest_path"])
    frame_sets = {}
    for row in frame_manifest["frame_sets"]:
        validate_frame_set(row)
        key = (row["candidate_id"], float(row["sampling_fps"]))
        if key in frame_sets:
            raise RuntimeError("duplicate frame set")
        frame_sets[key] = row
    call_manifest = load_json(ROOT / prereg["bindings"]["authorized_call_manifest_path"])
    validate_call_manifest(call_manifest, prereg["workload"]["total_physical_calls"])
    return prereg, videos, frame_sets, call_manifest


def schedule_for_shard(prereg: dict, frame_sets: dict, call_manifest: dict, shard: str) -> list[dict]:
    rows = []
    for call in call_manifest["calls"]:
        expected_path = str((RAW / call["execution_shard"] / call["artifact_name"]).relative_to(ROOT))
        if call["artifact_path"] != expected_path:
            raise RuntimeError("call artifact path mismatch")
        key = (call["candidate_id"], float(call["sampling_fps"]))
        frame_set = frame_sets.get(key)
        if frame_set is None:
            raise RuntimeError("call has no frozen frame set")
        for field in ("video_id", "start_time", "end_time", "frame_count", "frame_set_sha256"):
            if call[field] != frame_set[field]:
                raise RuntimeError(f"call/frame binding mismatch: {call['artifact_name']}:{field}")
        if call["execution_shard"] == shard:
            rows.append(call)
    expected = prereg["gpu_schedule"][shard]["call_count"]
    if len(rows) != expected:
        raise RuntimeError("shard call-count mismatch")
    return rows


def identity_payload(prereg: dict, call: dict, frame_set: dict) -> dict:
    bindings = prereg["bindings"]
    return {
        "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": sha256_file(SEAL),
        "authorized_call_manifest_sha256": bindings["authorized_call_manifest_sha256"],
        "call_spec_sha256": call["call_spec_sha256"],
        "execution_shard": call["execution_shard"],
        "candidate_id": call["candidate_id"],
        "video_id": call["video_id"],
        "video_sha256": frame_set["source_video_sha256"],
        "start_time": call["start_time"],
        "end_time": call["end_time"],
        "variant": call["variant"],
        "repeat_index": call["repeat_index"],
        "sampling_fps": call["sampling_fps"],
        "frame_set_sha256": call["frame_set_sha256"],
        "prompt_sha256": bindings["prompt_sha256"],
        "schema_sha256": bindings["schema_sha256"],
        "parser_sha256": bindings["parser_source_sha256"],
        "config_sha256": bindings["config_sha256"],
        "model_content_hash": prereg["model"]["model_content_hash"],
        "seed": prereg["workload"]["seed"],
        "generation": prereg["workload"]["generation"],
    }


def model_input_identity(payload: dict, frames: list[dict]) -> str:
    stable = {key: value for key, value in payload.items() if key not in {
        "execution_shard", "variant", "repeat_index", "call_spec_sha256"
    }}
    return canonical_hash({**stable, "frames": [public_frame_record(row) for row in frames]})


def _validate_existing_record(record: dict, payload: dict, frame_set: dict) -> None:
    claimed = record.get("record_sha256")
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    if claimed != canonical_hash(unsigned):
        raise RuntimeError("raw record self-hash mismatch")
    if record.get("identity") != payload:
        raise RuntimeError("raw record identity mismatch")
    if record.get("input_identity_sha256") != canonical_hash(payload):
        raise RuntimeError("raw input identity mismatch")
    if record.get("frames") != frame_set["frames"]:
        raise RuntimeError("raw frame identity mismatch")
    raw = record.get("raw")
    if not isinstance(raw, str) or record.get("raw_response_sha256") != hashlib.sha256(raw.encode()).hexdigest():
        raise RuntimeError("raw response hash mismatch")
    parsed = parse_oracle_v3_response(raw)
    if (
        record.get("parsed"), record.get("parse_status"), record.get("effective_label")
    ) != (parsed.parsed, parsed.parse_status, parsed.effective_label):
        raise RuntimeError("stored parse result mismatch")


def _read_attempts(shard: str) -> list[dict]:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = [load_line(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    previous = None
    states: dict[str, str] = {}
    identities = {}
    processed = {}
    allowed = {
        None: {"PREPARED"},
        "PREPARED": {"INFERENCE_STARTED", "PRE_INFERENCE_ABORTED"},
        "INFERENCE_STARTED": {"INFERENCE_COMPLETED", "GENERATION_FAILED", "UNCERTAIN_INTERRUPTION"},
        "INFERENCE_COMPLETED": {"ACCEPTED", "FAILED_POST_INFERENCE"},
    }
    for row in rows:
        claimed = row.get("event_sha256")
        unsigned = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or claimed != canonical_hash(unsigned):
            raise RuntimeError("attempt ledger hash-chain mismatch")
        previous = claimed
        attempt_id = row.get("attempt_id")
        event = row.get("event")
        if event not in allowed.get(states.get(attempt_id), set()):
            raise RuntimeError("invalid attempt state transition")
        identity = (row.get("artifact"), row.get("call_spec_sha256"), row.get("input_identity_sha256"))
        if attempt_id in identities and identities[attempt_id] != identity:
            raise RuntimeError("attempt identity changed")
        identities[attempt_id] = identity
        if event == "PREPARED":
            if not isinstance(row.get("processed_input_sha256"), str):
                raise RuntimeError("prepared event lacks processed input")
            processed[attempt_id] = row["processed_input_sha256"]
        if event == "INFERENCE_STARTED" and row.get("processed_input_sha256") != processed.get(attempt_id):
            raise RuntimeError("processed input changed before inference")
        states[attempt_id] = event
    return rows


def load_line(line: str) -> dict:
    from .oracle_v3_parser import loads_unique
    value = loads_unique(line)
    if not isinstance(value, dict):
        raise RuntimeError("attempt event is not an object")
    return value


def _append_attempt(shard: str, event: dict) -> None:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = _read_attempts(shard)
    payload = {**event, "previous_event_sha256": rows[-1]["event_sha256"] if rows else None}
    payload["event_sha256"] = canonical_hash(payload)
    atomic_text(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in [*rows, payload]))


def _event_identity(call: dict, input_identity: str, attempt_id: str) -> dict:
    return {
        "attempt_id": attempt_id,
        "artifact": call["artifact_name"],
        "call_spec_sha256": call["call_spec_sha256"],
        "input_identity_sha256": input_identity,
    }


def reconcile_shard(
    schedule: list[dict], prereg: dict, frame_sets: dict, shard: str, approval_sha256: str
) -> list[dict]:
    rows = _read_attempts(shard)
    starts = {}
    for row in rows:
        if row["event"] == "INFERENCE_STARTED":
            starts[row["artifact"]] = starts.get(row["artifact"], 0) + 1
    if any(count > 1 for count in starts.values()):
        raise RuntimeError("physical retry detected")
    pending = []
    for call in schedule:
        frame_set = frame_sets[(call["candidate_id"], float(call["sampling_fps"]))]
        payload = identity_payload(prereg, call, frame_set)
        input_identity = canonical_hash(payload)
        destination = ROOT / call["artifact_path"]
        record = load_json(destination) if destination.exists() else None
        if record is not None:
            _validate_existing_record(record, payload, frame_set)
            if record.get("runtime", {}).get("compute_approval_sha256") != approval_sha256:
                raise RuntimeError("raw record approval mismatch")
        events_by_attempt = {}
        for row in rows:
            if row["artifact"] == call["artifact_name"]:
                events_by_attempt.setdefault(row["attempt_id"], []).append(row)
        for events in events_by_attempt.values():
            last = events[-1]["event"]
            identity = _event_identity(call, input_identity, events[0]["attempt_id"])
            if last == "PREPARED":
                _append_attempt(shard, {"event": "PRE_INFERENCE_ABORTED", **identity,
                                        "reason": "prior process ended before generation"})
            elif last == "INFERENCE_STARTED":
                _append_attempt(shard, {"event": "UNCERTAIN_INTERRUPTION", **identity,
                                        "reason": "durable start lacks completion"})
                raise RuntimeError("uncertain generation; new approval required")
            elif last == "INFERENCE_COMPLETED":
                if record is None:
                    _append_attempt(shard, {"event": "FAILED_POST_INFERENCE", **identity,
                                            "reason": "completed generation lacks raw artifact"})
                    raise RuntimeError("completed generation lost raw artifact")
                _append_attempt(shard, {"event": "ACCEPTED", **identity,
                                        "record_sha256": record["record_sha256"],
                                        "generated_token_ids_sha256": record["generated_token_ids_sha256"],
                                        "recovered_after_crash": True})
            elif last in {"GENERATION_FAILED", "UNCERTAIN_INTERRUPTION", "FAILED_POST_INFERENCE"}:
                raise RuntimeError("failed or uncertain generation cannot be retried")
        rows = _read_attempts(shard)
        accepted = [row for row in rows if row["artifact"] == call["artifact_name"] and row["event"] == "ACCEPTED"]
        if record is not None:
            matching = [row for row in accepted if (
                row["input_identity_sha256"] == input_identity
                and row.get("record_sha256") == record["record_sha256"]
            )]
            if len(matching) != 1:
                raise RuntimeError("raw artifact lacks exactly one accepted attempt")
        elif starts.get(call["artifact_name"], 0):
            raise RuntimeError("refusing physical retry")
        else:
            pending.append(call)
    return pending


def _acquire_lock(shard: str):
    LOCKS.mkdir(parents=True, exist_ok=True)
    handle = (LOCKS / f"{shard}.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("execution shard is already locked")
    return handle


def _verify_video_files(schedule: list[dict], videos: dict) -> None:
    for video_id in sorted({call["video_id"] for call in schedule}):
        video = videos[video_id]
        if sha256_file(ROOT / video["path"]) != video["sha256"]:
            raise RuntimeError(f"video hash mismatch: {video_id}")


def _validate_frames(call: dict, videos: dict, frame_set: dict) -> list[dict]:
    video = videos[call["video_id"]]
    frames = extract_exact_frames(
        ROOT / video["path"], float(call["start_time"]), float(call["end_time"]),
        float(Fraction(video["nominal_fps"])), float(call["sampling_fps"]),
    )
    public = [public_frame_record(row) for row in frames]
    if public != frame_set["frames"] or canonical_hash(public) != frame_set["frame_set_sha256"]:
        raise RuntimeError("decoded frames differ from frozen V3 frame manifest")
    return frames


def validate_only(shard: str) -> dict:
    prereg, videos, frame_sets, call_manifest = frozen_context()
    schedule = schedule_for_shard(prereg, frame_sets, call_manifest, shard)
    _verify_video_files(schedule, videos)
    model_manifest_sha256 = verify_current_model_files(prereg)
    calls = []
    for call in schedule:
        frame_set = frame_sets[(call["candidate_id"], float(call["sampling_fps"]))]
        frames = _validate_frames(call, videos, frame_set)
        payload = identity_payload(prereg, call, frame_set)
        calls.append({
            "artifact_name": call["artifact_name"],
            "frame_count": len(frames),
            "input_identity_sha256": canonical_hash(payload),
            "model_input_identity_sha256": model_input_identity(payload, frames),
        })
    return {
        "status": "PASS",
        "execution_shard": shard,
        "expected_calls": len(schedule),
        "model_file_manifest_sha256": model_manifest_sha256,
        "calls": calls,
    }


def _tensor_bundle_sha256(values) -> str:
    digest = hashlib.sha256()
    for key in sorted(values):
        value = values[key]
        digest.update(key.encode())
        if hasattr(value, "detach"):
            tensor = value.detach().cpu().contiguous()
            digest.update(str(tensor.dtype).encode())
            digest.update(json.dumps(list(tensor.shape)).encode())
            digest.update(tensor.view(dtype=__import__("torch").uint8).numpy().tobytes())
        else:
            digest.update(repr(value).encode())
    return digest.hexdigest()


def _logical_cuda_devices(model) -> list[int]:
    return sorted({int(parameter.device.index) for parameter in model.parameters()
                   if parameter.device.type == "cuda"})


def run_physical(args, approval_path: Path, approval_sha256: str) -> None:
    import numpy as np
    import torch
    import transformers
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    prereg, videos, frame_sets, call_manifest = frozen_context()
    expected_pair = prereg["gpu_schedule"][args.execution_shard]["physical_gpu_ids"]
    declared = [int(token) for token in args.declared_physical_gpus.split(",")]
    if declared != expected_pair or torch.cuda.device_count() != 2:
        raise RuntimeError("declared GPUs differ from sealed two-GPU shard allocation")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != args.declared_physical_gpus:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must exactly match the declared physical GPUs")
    gpu_identities = [subprocess.check_output([
        "nvidia-smi", f"--id={index}", "--query-gpu=index,name,uuid", "--format=csv,noheader",
    ], text=True).strip() for index in declared]
    if any(not identity.startswith(f"{index},") for identity, index in zip(gpu_identities, declared)):
        raise RuntimeError("physical GPU declaration mismatch")
    schedule = schedule_for_shard(prereg, frame_sets, call_manifest, args.execution_shard)
    _verify_video_files(schedule, videos)
    model_manifest_sha256 = verify_current_model_files(prereg)
    schedule = reconcile_shard(
        schedule, prereg, frame_sets, args.execution_shard, approval_sha256
    )
    if not schedule:
        print(json.dumps({"status": "ALREADY_COMPLETE", "execution_shard": args.execution_shard}))
        return
    prompt = (ROOT / prereg["bindings"]["prompt_path"]).read_text(encoding="utf-8")
    model_path = ROOT / prereg["model"]["model_path"]
    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="balanced",
        trust_remote_code=True, local_files_only=True,
    )
    model.to(dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(
        model_path, trust_remote_code=True, local_files_only=True
    )
    model.eval()
    torch.use_deterministic_algorithms(True, warn_only=False)
    seed = int(prereg["workload"]["seed"])
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started
    logical_cuda_devices = _logical_cuda_devices(model)
    parameter_dtypes = sorted({str(parameter.dtype) for parameter in model.parameters()})
    if logical_cuda_devices != [0, 1] or parameter_dtypes != ["torch.bfloat16"]:
        raise RuntimeError("model placement or dtype differs from the sealed execution profile")
    preprocessing_runtime = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": importlib.metadata.version("Pillow"),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils"),
        "processor_class": f"{processor.__class__.__module__}.{processor.__class__.__qualname__}",
    }
    hf_device_map = {
        str(key): str(value) for key, value in sorted(getattr(model, "hf_device_map", {}).items())
    }
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    for call in schedule:
        frame_set = frame_sets[(call["candidate_id"], float(call["sampling_fps"]))]
        payload = identity_payload(prereg, call, frame_set)
        input_identity = canonical_hash(payload)
        destination = ROOT / call["artifact_path"]
        attempt_id = f"{args.execution_shard}:{call['artifact_name']}:{time.time_ns()}"
        attempt_identity = _event_identity(call, input_identity, attempt_id)
        generation_started = generation_completed = False
        try:
            call_started = time.perf_counter()
            frames = _validate_frames(call, videos, frame_set)
            pil_frames = [Image.fromarray(row["rgb"]) for row in frames]
            messages = [{"role": "user", "content": [
                {"type": "video", "video": pil_frames, "fps": call["sampling_fps"]},
                {"type": "text", "text": prompt},
            ]}]
            prompt_text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs, kwargs = process_vision_info(
                messages, return_video_kwargs=True, return_video_metadata=True
            )
            if kwargs != {"do_sample_frames": False}:
                raise RuntimeError(f"unexpected processor sampling kwargs: {kwargs}")
            inputs = processor(
                text=[prompt_text], images=image_inputs, videos=[row[0] for row in video_inputs],
                video_metadata=[row[1] for row in video_inputs], padding=True,
                return_tensors="pt", **kwargs,
            ).to(model.device)
            processed_input_sha256 = _tensor_bundle_sha256(inputs)
            _append_attempt(args.execution_shard, {
                "event": "PREPARED", **attempt_identity,
                "processed_input_sha256": processed_input_sha256,
            })
            torch.cuda.synchronize()
            inference_started = time.perf_counter()
            _append_attempt(args.execution_shard, {
                "event": "INFERENCE_STARTED", **attempt_identity,
                "processed_input_sha256": processed_input_sha256,
            })
            generation_started = True
            try:
                with torch.no_grad():
                    generated = model.generate(
                        **inputs,
                        do_sample=False,
                        max_new_tokens=int(prereg["workload"]["generation"]["max_new_tokens"]),
                    )
            except Exception as exc:
                _append_attempt(args.execution_shard, {
                    "event": "GENERATION_FAILED", **attempt_identity,
                    "error_type": type(exc).__name__, "error": str(exc),
                })
                raise
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            generated_token_ids_sha256 = _tensor_bundle_sha256({"generated": generated})
            _append_attempt(args.execution_shard, {
                "event": "INFERENCE_COMPLETED", **attempt_identity,
                "generated_token_ids_sha256": generated_token_ids_sha256,
            })
            generation_completed = True
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed = parse_oracle_v3_response(raw)
            record = {
                "identity": payload,
                "attempt_id": attempt_id,
                "input_identity_sha256": input_identity,
                "model_input_identity_sha256": model_input_identity(payload, frames),
                "frames": [public_frame_record(row) for row in frames],
                "parse_status": parsed.parse_status,
                "effective_label": parsed.effective_label,
                "parsed": parsed.parsed,
                "raw": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "processed_input_sha256": processed_input_sha256,
                "generated_token_ids_sha256": generated_token_ids_sha256,
                "runtime": {
                    "declared_physical_gpus": declared,
                    "gpu_identities": gpu_identities,
                    "model_load_seconds": load_seconds,
                    "inference_seconds": inference_seconds,
                    "total_call_seconds": time.perf_counter() - call_started,
                    "git_head": git_head,
                    "git_status_sha256": hashlib.sha256(git_status.encode()).hexdigest(),
                    "runner_source_sha256": sha256_file(Path(__file__)),
                    "execution_seal_sha256": sha256_file(SEAL),
                    "compute_approval_path": str(approval_path.relative_to(ROOT)),
                    "compute_approval_sha256": approval_sha256,
                    "model_file_manifest_sha256": model_manifest_sha256,
                    "parameter_dtypes": parameter_dtypes,
                    "logical_cuda_devices": logical_cuda_devices,
                    "hf_device_map": hf_device_map,
                    "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
                    "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
                    "preprocessing_runtime": preprocessing_runtime,
                    "torch": torch.__version__,
                    "transformers": transformers.__version__,
                },
            }
            record["record_sha256"] = canonical_hash(record)
            if destination.exists():
                raise RuntimeError("raw destination appeared during inference")
            write_json_once(destination, record)
            _append_attempt(args.execution_shard, {
                "event": "ACCEPTED", **attempt_identity,
                "record_sha256": record["record_sha256"],
                "generated_token_ids_sha256": generated_token_ids_sha256,
                "recovered_after_crash": False,
            })
            print(json.dumps({
                "artifact": str(destination.relative_to(ROOT)),
                "parse_status": parsed.parse_status,
                "label": parsed.effective_label,
                "inference_seconds": inference_seconds,
            }), flush=True)
            del frames, pil_frames, messages, inputs, generated, trimmed
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
        except Exception as exc:
            if not generation_started:
                rows = _read_attempts(args.execution_shard)
                if rows and rows[-1].get("attempt_id") == attempt_id and rows[-1]["event"] == "PREPARED":
                    _append_attempt(args.execution_shard, {
                        "event": "PRE_INFERENCE_ABORTED", **attempt_identity,
                        "error_type": type(exc).__name__, "error": str(exc),
                    })
            elif generation_completed and not destination.exists():
                _append_attempt(args.execution_shard, {
                    "event": "FAILED_POST_INFERENCE", **attempt_identity,
                    "error_type": type(exc).__name__, "error": str(exc),
                })
            raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-shard", choices=SHARDS, required=True)
    parser.add_argument("--declared-physical-gpus", required=True)
    parser.add_argument("--compute-approval", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_only:
        print(json.dumps(validate_only(args.execution_shard), indent=2, sort_keys=True))
        return
    if args.compute_approval is None:
        raise RuntimeError("physical execution requires exact explicit user approval")
    approval_path = args.compute_approval if args.compute_approval.is_absolute() else ROOT / args.compute_approval
    _, prereg = validate_execution_seal("runner")
    approval_sha256 = validate_compute_approval(approval_path, prereg)
    lock = _acquire_lock(args.execution_shard)
    try:
        run_physical(args, approval_path, approval_sha256)
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
