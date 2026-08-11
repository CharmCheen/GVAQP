#!/usr/bin/env python3
"""Run one authenticated AEQ V2 preflight shard with durable attempt evidence."""

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

from garc_eval.accelerated_event_query.oracle_protocol import (
    canonical_hash,
    extract_exact_frames,
    public_frame_record,
    sha256_file,
)
from garc_eval.accelerated_event_query.oracle_response_protocol import loads_unique, parse_response_strict


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
RAW = OUT / "operational_oracle/preflight_v2/raw"
ATTEMPTS = OUT / "operational_oracle/preflight_v2/attempts"
LOCKS = OUT / "operational_oracle/preflight_v2/locks"
SEAL = OUT / "operational_oracle/preflight_v2/PREFLIGHT_V2_EXECUTION_SEAL.json"
SHARDS = ("DALI", "HANGZHOU", "WUHAN")


def load(path: Path) -> dict:
    return loads_unique(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(
        path,
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
    )


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def validate_execution_seal(component: str = "runner") -> dict:
    seal = load(SEAL)
    if seal.get("status") != "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION":
        raise RuntimeError("execution seal is not frozen")
    if seal.get("preregistration_sha256") != sha256_file(PREREG):
        raise RuntimeError("execution seal/preregistration mismatch")
    source_key = f"{component}_source_sha256"
    source_path = ROOT / seal["sources"][f"{component}_source_path"]
    if Path(__file__).resolve() == source_path.resolve() and sha256_file(source_path) != seal["sources"][source_key]:
        raise RuntimeError(f"execution seal/{component} source mismatch")
    return seal


def validate_bindings(prereg: dict) -> None:
    for key, expected in prereg["bindings"].items():
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        if hash_key not in prereg["bindings"]:
            continue
        path = ROOT / expected
        observed = sha256_file(path)
        if observed != prereg["bindings"][hash_key]:
            raise RuntimeError(f"binding mismatch for {path}: {observed}")
    model_audit = load(ROOT / prereg["bindings"]["model_identity_audit_path"])
    if not all([
        model_audit.get("status") == "PASS",
        model_audit.get("all_current_sha256_values_match_prior_manifest") is True,
        model_audit.get("expected_model_content_hash") == prereg["bindings"]["model_content_hash"],
    ]):
        raise RuntimeError("model audit/content binding mismatch")
    model_manifest = load(ROOT / prereg["bindings"]["model_file_manifest_path"])
    if not all([
        model_manifest.get("status") == "PASS_DIRECT_FULL_REHASH",
        model_manifest.get("file_count") == 19,
        model_manifest.get("model_content_hash") == prereg["bindings"]["model_content_hash"],
        canonical_hash(model_manifest.get("files")) == prereg["bindings"]["model_content_hash"],
    ]):
        raise RuntimeError("full model-file manifest is invalid")


def verify_current_model_files(prereg: dict, config: dict) -> str:
    manifest_path = ROOT / prereg["bindings"]["model_file_manifest_path"]
    manifest = load(manifest_path)
    model_path = ROOT / config["oracle"]["model_path"]
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
    if canonical_hash(rows) != prereg["bindings"]["model_content_hash"]:
        raise RuntimeError("current canonical model hash mismatch")
    return sha256_file(manifest_path)


def validate_compute_approval(path: Path, prereg: dict) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to((OUT / "operational_oracle/preflight_v2").resolve()):
        raise RuntimeError("compute approval must be stored inside the sealed preflight directory")
    approval = load(resolved)
    expected_keys = {
        "status", "experiment_id", "execution_seal_sha256", "authorized_call_manifest_sha256",
        "approved_physical_call_count", "approval_scope", "user_approval_evidence",
    }
    if set(approval) != expected_keys:
        raise RuntimeError("compute approval schema mismatch")
    expected_scope = "exactly the 32 manifest calls; no automatic physical-generation retry; no representative or full oracle"
    if not all([
        approval["status"] == "APPROVED_BY_USER",
        approval["experiment_id"] == prereg["experiment_id"],
        approval["execution_seal_sha256"] == sha256_file(SEAL),
        approval["authorized_call_manifest_sha256"] == prereg["bindings"]["authorized_call_manifest_sha256"],
        approval["approved_physical_call_count"] == prereg["workload"]["total_physical_calls"] == 32,
        approval["approval_scope"] == expected_scope,
        isinstance(approval["user_approval_evidence"], str),
        bool(approval["user_approval_evidence"].strip()),
        "FILL" not in approval["user_approval_evidence"],
    ]):
        raise RuntimeError("compute approval does not authorize this exact sealed 32-call pilot")
    return sha256_file(resolved)


def frozen_context() -> tuple[dict, dict, dict, dict, dict]:
    validate_execution_seal("runner")
    prereg = load(PREREG)
    validate_bindings(prereg)
    config = load(ROOT / prereg["bindings"]["config_path"])
    selection = load(ROOT / prereg["bindings"]["selection_source_path"])
    videos = {
        row["video_id"]: row
        for row in load(ROOT / prereg["bindings"]["video_manifest_path"])["videos"]
    }
    frame_manifest = load(ROOT / prereg["bindings"]["frame_manifest_path"])
    frame_sets = {
        (row["candidate_id"], float(row["sampling_fps"])): row
        for row in frame_manifest["frame_sets"]
    }
    return prereg, config, selection, videos, frame_sets


def schedule_for_shard(prereg: dict, selection: dict, shard: str) -> list[dict]:
    clips = {row["candidate_id"]: row for row in selection["clips"]}
    manifest = load(ROOT / prereg["bindings"]["authorized_call_manifest_path"])
    counts = manifest["counts_by_variant"]
    workload = prereg["workload"]
    required = {
        "total": (manifest["authorized_call_count"], workload["total_physical_calls"], 32),
        "base": (counts.get("base"), workload["same_process_base_calls"], 24),
        "sensitivity": (counts.get("fps_sensitivity"), workload["sampling_sensitivity_calls"], 6),
        "anchor": (counts.get("cross_replica_anchor"), workload["additional_cross_replica_calls"], 2),
    }
    if any(len(set(values)) != 1 for values in required.values()) or not all(manifest["assertions"].values()):
        raise RuntimeError(f"authorized call manifest/prereg arithmetic mismatch: {required}")
    if [row["ordinal"] for row in manifest["calls"]] != list(range(32)):
        raise RuntimeError("authorized call ordinals are not canonical")
    if len({row["artifact_path"] for row in manifest["calls"]}) != 32:
        raise RuntimeError("authorized artifact paths are not unique")
    schedule = []
    for row in manifest["calls"]:
        unsigned = {key: value for key, value in row.items() if key != "call_spec_sha256"}
        if row.get("call_spec_sha256") != canonical_hash(unsigned):
            raise RuntimeError(f"call manifest self-hash mismatch: {row.get('artifact_name')}")
        expected_path = f"outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/raw/{row['execution_shard']}/{row['artifact_name']}"
        if row.get("artifact_path") != expected_path:
            raise RuntimeError(f"call manifest artifact-path mismatch: {row['artifact_name']}")
        if row["execution_shard"] != shard:
            continue
        clip = clips[row["candidate_id"]]
        for field in ("video_id", "start_time", "end_time"):
            if row[field] != clip[field]:
                raise RuntimeError(f"call manifest/selection mismatch: {row['artifact_name']}:{field}")
        call = {"clip": clip, "variant": row["variant"], "repeat_index": row["repeat_index"],
                "sampling_fps": float(row["sampling_fps"]), "execution_shard": shard,
                "call_spec_sha256": row["call_spec_sha256"]}
        if artifact_name(call) != row["artifact_name"]:
            raise RuntimeError("call manifest artifact-name mismatch")
        frame_manifest = load(ROOT / prereg["bindings"]["frame_manifest_path"])
        matched = [item for item in frame_manifest["frame_sets"]
                   if item["candidate_id"] == row["candidate_id"]
                   and float(item["sampling_fps"]) == float(row["sampling_fps"])]
        if len(matched) != 1 or (matched[0]["frame_count"], matched[0]["frame_set_sha256"]) != (
            row["frame_count"], row["frame_set_sha256"]
        ):
            raise RuntimeError(f"call/frame manifest mismatch: {row['artifact_name']}")
        schedule.append(call)
    return schedule


def artifact_name(call: dict) -> str:
    candidate = call["clip"]["candidate_id"]
    if call["variant"] == "base":
        suffix = f"fps2_r{call['repeat_index']}"
    elif call["variant"] == "fps_sensitivity":
        suffix = "fps4_sensitivity"
    else:
        suffix = f"fps2_cross_replica_{call['execution_shard']}"
    return f"{candidate}_{suffix}.json"


def identity_payload(prereg: dict, call: dict, frame_set: dict) -> dict:
    clip = call["clip"]
    return {
        "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": sha256_file(SEAL),
        "authorized_call_manifest_sha256": prereg["bindings"]["authorized_call_manifest_sha256"],
        "call_spec_sha256": call["call_spec_sha256"],
        "execution_shard": call["execution_shard"],
        "candidate_id": clip["candidate_id"],
        "video_id": clip["video_id"],
        "video_sha256": frame_set["source_video_sha256"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "variant": call["variant"],
        "repeat_index": call["repeat_index"],
        "sampling_fps": call["sampling_fps"],
        "frame_set_sha256": frame_set["frame_set_sha256"],
        "prompt_sha256": prereg["bindings"]["prompt_sha256"],
        "config_sha256": prereg["bindings"]["config_sha256"],
        "protocol_source_sha256": prereg["bindings"]["protocol_source_sha256"],
        "model_content_hash": prereg["bindings"]["model_content_hash"],
        "seed": prereg["workload"]["seed"],
        "generation": prereg["workload"]["generation"],
    }


def model_input_identity(payload: dict, frames: list[dict]) -> str:
    stable = {key: value for key, value in payload.items()
              if key not in {"execution_shard", "variant", "repeat_index", "call_spec_sha256"}}
    return canonical_hash({**stable, "frames": [public_frame_record(row) for row in frames]})


def validate_existing_record(
    record: dict, expected_payload: dict, expected_frame_set: dict
) -> None:
    expected_input_identity = canonical_hash(expected_payload)
    claimed = record.get("record_sha256")
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("existing raw record self-hash mismatch")
    if record.get("input_identity_sha256") != expected_input_identity:
        raise RuntimeError("existing raw record input identity mismatch")
    if record.get("identity") != expected_payload or record.get("frames") != expected_frame_set["frames"]:
        raise RuntimeError("existing raw record identity/frame mismatch")
    expected_model_identity = model_input_identity(
        expected_payload, [{**frame, "rgb": None} for frame in expected_frame_set["frames"]]
    )
    if record.get("model_input_identity_sha256") != expected_model_identity:
        raise RuntimeError("existing raw record model-input identity mismatch")
    raw = record.get("raw")
    if not isinstance(raw, str) or record.get("raw_response_sha256") != hashlib.sha256(raw.encode()).hexdigest():
        raise RuntimeError("existing raw response hash mismatch")
    parsed, status = parse_response_strict(raw)
    effective = parsed.get("label") if status == "ok" else "parse_failure"
    if (record.get("parsed"), record.get("parse_status"), record.get("effective_label")) != (
        parsed, status, effective
    ):
        raise RuntimeError("existing raw record stored parse mismatch")


def append_attempt(shard: str, event: dict) -> None:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = read_attempts(shard)
    previous = rows[-1]["event_sha256"] if rows else None
    payload = {**event, "previous_event_sha256": previous}
    payload["event_sha256"] = canonical_hash(payload)
    atomic_text(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in [*rows, payload]))


def read_attempts(shard: str) -> list[dict]:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = [loads_unique(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    previous = None
    states = {}
    identities = {}
    processed_inputs = {}
    for row in rows:
        claimed = row.get("event_sha256")
        payload = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or claimed != canonical_hash(payload):
            raise RuntimeError(f"attempt ledger hash-chain mismatch: {path}")
        previous = claimed
        attempt_id = row.get("attempt_id")
        event = row.get("event")
        prior = states.get(attempt_id)
        allowed = {
            None: {"PREPARED"},
            "PREPARED": {"INFERENCE_STARTED", "PRE_INFERENCE_ABORTED"},
            "INFERENCE_STARTED": {"INFERENCE_COMPLETED", "GENERATION_FAILED", "UNCERTAIN_INTERRUPTION"},
            "INFERENCE_COMPLETED": {"ACCEPTED", "FAILED_POST_INFERENCE"},
        }
        if event not in allowed.get(prior, set()):
            raise RuntimeError(f"invalid attempt transition {prior!r}->{event!r}")
        identity = (row.get("artifact"), row.get("call_spec_sha256"), row.get("input_identity_sha256"))
        if attempt_id in identities and identity != identities[attempt_id]:
            raise RuntimeError("attempt identity changed across events")
        identities[attempt_id] = identity
        if event == "PREPARED":
            processed = row.get("processed_input_sha256")
            if not isinstance(processed, str) or not processed:
                raise RuntimeError("PREPARED event lacks processed-input hash")
            processed_inputs[attempt_id] = processed
        elif event == "INFERENCE_STARTED":
            if row.get("processed_input_sha256") != processed_inputs.get(attempt_id):
                raise RuntimeError("processed-input hash changed before inference")
        states[attempt_id] = event
    return rows


def event_identity(call: dict, input_identity: str, attempt_id: str) -> dict:
    return {
        "attempt_id": attempt_id,
        "artifact": artifact_name(call),
        "call_spec_sha256": call["call_spec_sha256"],
        "input_identity_sha256": input_identity,
    }


def reconcile_shard(
    schedule: list[dict], prereg: dict, frame_sets: dict, shard: str,
    compute_approval_sha256: str | None = None,
) -> list[dict]:
    """Reconcile durable state before model load; never retry a started generation."""
    authorized = {}
    for call in schedule:
        frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
        payload = identity_payload(prereg, call, frame_set)
        authorized[artifact_name(call)] = (call, frame_set, payload, canonical_hash(payload))
    rows = read_attempts(shard)
    by_attempt = {}
    starts_by_artifact = {}
    for row in rows:
        artifact = row.get("artifact")
        if artifact not in authorized:
            raise RuntimeError(f"unauthorized artifact in attempt ledger: {artifact}")
        call, _, _, input_identity = authorized[artifact]
        expected = (call["call_spec_sha256"], input_identity)
        if (row.get("call_spec_sha256"), row.get("input_identity_sha256")) != expected:
            raise RuntimeError(f"attempt identity mismatch: {artifact}")
        by_attempt.setdefault(row["attempt_id"], []).append(row)
        if row["event"] == "INFERENCE_STARTED":
            starts_by_artifact[artifact] = starts_by_artifact.get(artifact, 0) + 1
    if any(count > 1 for count in starts_by_artifact.values()):
        raise RuntimeError("physical generation retry detected")

    pending = []
    for artifact, (call, frame_set, payload, input_identity) in authorized.items():
        destination = RAW / shard / artifact
        record = load(destination) if destination.exists() else None
        if record is not None:
            validate_existing_record(record, payload, frame_set)
            if compute_approval_sha256 is not None and record.get("runtime", {}).get(
                "compute_approval_sha256"
            ) != compute_approval_sha256:
                raise RuntimeError(f"raw/compute-approval mismatch: {artifact}")
        attempts = [events for events in by_attempt.values() if events[0]["artifact"] == artifact]
        for events in attempts:
            last = events[-1]["event"]
            identity = event_identity(call, input_identity, events[0]["attempt_id"])
            if last == "PREPARED":
                append_attempt(shard, {"event": "PRE_INFERENCE_ABORTED", **identity,
                                       "reason": "prior process ended before generation"})
            elif last == "INFERENCE_STARTED":
                append_attempt(shard, {"event": "UNCERTAIN_INTERRUPTION", **identity,
                                       "reason": "generation start was durable but completion was not"})
                raise RuntimeError(f"uncertain prior physical generation; approval required: {artifact}")
            elif last == "INFERENCE_COMPLETED":
                if record is None:
                    append_attempt(shard, {"event": "FAILED_POST_INFERENCE", **identity,
                                           "reason": "generation completed without durable raw"})
                    raise RuntimeError(f"completed generation lost its raw artifact: {artifact}")
                if record.get("attempt_id") != events[0]["attempt_id"]:
                    raise RuntimeError(f"raw/attempt mismatch: {artifact}")
                append_attempt(shard, {"event": "ACCEPTED", **identity,
                                       "record_sha256": record["record_sha256"],
                                       "generated_token_ids_sha256": record["generated_token_ids_sha256"],
                                       "recovered_after_crash": True})
            elif last in {"GENERATION_FAILED", "UNCERTAIN_INTERRUPTION", "FAILED_POST_INFERENCE"}:
                raise RuntimeError(f"prior physical generation failed/uncertain; approval required: {artifact}")
        rows = read_attempts(shard)
        accepted = [row for row in rows if row["event"] == "ACCEPTED" and row["artifact"] == artifact]
        if record is not None:
            triple = (artifact, input_identity, record["record_sha256"])
            matching = [row for row in accepted if (
                row["artifact"], row["input_identity_sha256"], row.get("record_sha256")
            ) == triple and row.get("generated_token_ids_sha256") == record.get("generated_token_ids_sha256")]
            if len(matching) != 1:
                raise RuntimeError(f"raw lacks exactly one accepted artifact/input/hash triple: {artifact}")
            accepted_attempt = matching[0]["attempt_id"]
            input_events = [row for row in rows if row["attempt_id"] == accepted_attempt
                            and row["event"] in {"PREPARED", "INFERENCE_STARTED"}]
            if len(input_events) != 2 or any(
                row.get("processed_input_sha256") != record.get("processed_input_sha256")
                for row in input_events
            ):
                raise RuntimeError(f"ledger/raw processed-input mismatch: {artifact}")
        elif starts_by_artifact.get(artifact, 0):
            raise RuntimeError(f"refusing physical retry: {artifact}")
        else:
            pending.append(call)
    return pending


def acquire_shard_lock(shard: str):
    LOCKS.mkdir(parents=True, exist_ok=True)
    handle = (LOCKS / f"{shard}.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError(f"execution shard is already locked: {shard}")
    return handle


def verify_video_files(schedule: list[dict], videos: dict) -> None:
    for video_id in sorted({call["clip"]["video_id"] for call in schedule}):
        video = videos[video_id]
        observed = sha256_file(ROOT / video["path"])
        if observed != video["sha256"]:
            raise RuntimeError(f"video content hash mismatch: {video_id}")


def validate_frames(call: dict, videos: dict, frame_set: dict) -> list[dict]:
    clip = call["clip"]
    video = videos[clip["video_id"]]
    if video["sha256"] != frame_set["source_video_sha256"]:
        raise RuntimeError("video/frame-manifest identity mismatch")
    frames = extract_exact_frames(
        ROOT / video["path"], float(clip["start_time"]), float(clip["end_time"]),
        float(Fraction(video["nominal_fps"])), float(call["sampling_fps"]),
    )
    public = [public_frame_record(row) for row in frames]
    if public != frame_set["frames"] or canonical_hash(public) != frame_set["frame_set_sha256"]:
        raise RuntimeError(f"exact frame mismatch for {clip['candidate_id']} at {call['sampling_fps']} fps")
    return frames


def validate_only(shard: str) -> dict:
    prereg, config, selection, videos, frame_sets = frozen_context()
    schedule = schedule_for_shard(prereg, selection, shard)
    verify_video_files(schedule, videos)
    model_manifest_sha256 = verify_current_model_files(prereg, config)
    rows = []
    for call in schedule:
        frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
        frames = validate_frames(call, videos, frame_set)
        payload = identity_payload(prereg, call, frame_set)
        rows.append({"artifact": artifact_name(call), "frame_count": len(frames),
                     "input_identity_sha256": canonical_hash(payload),
                     "model_input_identity_sha256": model_input_identity(payload, frames)})
    return {"status": "PASS", "execution_shard": shard, "expected_calls": len(schedule),
            "model_file_manifest_sha256": model_manifest_sha256, "calls": rows}


def tensor_bundle_sha256(values) -> str:
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
    devices = set()
    for parameter in model.parameters():
        if parameter.device.type == "cuda":
            devices.add(int(parameter.device.index))
    return sorted(devices)


def run_physical(args, approval_path: Path, compute_approval_sha256: str) -> None:
    import numpy as np
    import torch
    import transformers
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    declared = [int(token) for token in args.declared_physical_gpus.split(",")]
    if len(declared) != 2 or torch.cuda.device_count() != 2:
        raise RuntimeError("V2 requires exactly two visible GPUs")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != args.declared_physical_gpus:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must exactly match --declared-physical-gpus")
    gpu_identities = [subprocess.check_output([
        "nvidia-smi", f"--id={index}", "--query-gpu=index,name,uuid", "--format=csv,noheader",
    ], text=True).strip() for index in declared]
    if any(not identity.startswith(f"{index},") for identity, index in zip(gpu_identities, declared)):
        raise RuntimeError("physical GPU declaration mismatch")

    prereg, config, selection, videos, frame_sets = frozen_context()
    schedule = schedule_for_shard(prereg, selection, args.execution_shard)
    verify_video_files(schedule, videos)
    model_manifest_sha256 = verify_current_model_files(prereg, config)
    schedule = reconcile_shard(
        schedule, prereg, frame_sets, args.execution_shard, compute_approval_sha256
    )
    if not schedule:
        print(json.dumps({"status": "ALREADY_COMPLETE", "execution_shard": args.execution_shard}))
        return
    prompt = (ROOT / prereg["bindings"]["prompt_path"]).read_text(encoding="utf-8")
    model_path = ROOT / config["oracle"]["model_path"]
    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="balanced",
        trust_remote_code=True, local_files_only=True,
    )
    model.to(dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    model.eval()
    torch.use_deterministic_algorithms(True, warn_only=False)
    random.seed(int(prereg["workload"]["seed"]))
    np.random.seed(int(prereg["workload"]["seed"]))
    torch.manual_seed(int(prereg["workload"]["seed"]))
    torch.cuda.manual_seed_all(int(prereg["workload"]["seed"]))
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started
    logical_cuda_devices = _logical_cuda_devices(model)
    if logical_cuda_devices != [0, 1]:
        raise RuntimeError(f"model parameters do not occupy both visible GPUs: {logical_cuda_devices}")
    parameter_dtypes = sorted({str(parameter.dtype) for parameter in model.parameters()})
    if parameter_dtypes != ["torch.bfloat16"]:
        raise RuntimeError(f"model did not resolve to BF16 parameters: {parameter_dtypes}")
    hf_device_map = {
        str(key): str(value) for key, value in sorted(getattr(model, "hf_device_map", {}).items())
    }
    preprocessing_runtime = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": importlib.metadata.version("Pillow"),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils"),
        "processor_class": f"{processor.__class__.__module__}.{processor.__class__.__qualname__}",
    }

    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    for call in schedule:
        frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
        payload = identity_payload(prereg, call, frame_set)
        input_identity = canonical_hash(payload)
        destination = RAW / args.execution_shard / artifact_name(call)
        attempt_id = f"{args.execution_shard}:{artifact_name(call)}:{time.time_ns()}"
        attempt_identity = event_identity(call, input_identity, attempt_id)
        generation_started = False
        generation_completed = False
        try:
            call_started = time.perf_counter()
            frames = validate_frames(call, videos, frame_set)
            pil_frames = [Image.fromarray(row["rgb"]) for row in frames]
            messages = [{"role": "user", "content": [
                {"type": "video", "video": pil_frames, "fps": call["sampling_fps"]},
                {"type": "text", "text": prompt},
            ]}]
            prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs, kwargs = process_vision_info(
                messages, return_video_kwargs=True, return_video_metadata=True
            )
            if kwargs != {"do_sample_frames": False}:
                raise RuntimeError(f"unexpected sampling kwargs: {kwargs}")
            inputs = processor(
                text=[prompt_text], images=image_inputs, videos=[row[0] for row in video_inputs],
                video_metadata=[row[1] for row in video_inputs], padding=True,
                return_tensors="pt", **kwargs,
            ).to(model.device)
            processed_input_sha256 = tensor_bundle_sha256(inputs)
            append_attempt(args.execution_shard, {"event": "PREPARED", **attempt_identity,
                                                   "processed_input_sha256": processed_input_sha256})
            torch.cuda.synchronize()
            inference_started = time.perf_counter()
            append_attempt(args.execution_shard, {"event": "INFERENCE_STARTED", **attempt_identity,
                                                   "processed_input_sha256": processed_input_sha256})
            generation_started = True
            try:
                with torch.no_grad():
                    generated = model.generate(
                        **inputs, do_sample=False,
                        max_new_tokens=int(prereg["workload"]["generation"]["max_new_tokens"]),
                    )
            except Exception as exc:
                append_attempt(args.execution_shard, {"event": "GENERATION_FAILED", **attempt_identity,
                                                       "error_type": type(exc).__name__, "error": str(exc)})
                raise
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            generated_token_ids_sha256 = tensor_bundle_sha256({"generated": generated})
            append_attempt(args.execution_shard, {"event": "INFERENCE_COMPLETED", **attempt_identity,
                                                   "generated_token_ids_sha256": generated_token_ids_sha256})
            generation_completed = True
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed, parse_status = parse_response_strict(raw)
            record = {
                "identity": payload,
                "attempt_id": attempt_id,
                "input_identity_sha256": input_identity,
                "model_input_identity_sha256": model_input_identity(payload, frames),
                "frames": [public_frame_record(row) for row in frames],
                "parse_status": parse_status,
                "effective_label": parsed.get("label") if parse_status == "ok" else "parse_failure",
                "parsed": parsed,
                "raw": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "processed_input_sha256": processed_input_sha256,
                "generated_token_ids_sha256": generated_token_ids_sha256,
                "runtime": {
                    "declared_physical_gpus": declared, "gpu_identities": gpu_identities,
                    "model_load_seconds": load_seconds, "inference_seconds": inference_seconds,
                    "total_call_seconds": time.perf_counter() - call_started,
                    "git_head": git_head, "git_status_sha256": hashlib.sha256(git_status.encode()).hexdigest(),
                    "runner_source_sha256": sha256_file(Path(__file__)),
                    "execution_seal_sha256": sha256_file(SEAL),
                    "compute_approval_path": str(approval_path.relative_to(ROOT)),
                    "compute_approval_sha256": compute_approval_sha256,
                    "model_file_manifest_sha256": model_manifest_sha256,
                    "parameter_dtypes": parameter_dtypes,
                    "logical_cuda_devices": logical_cuda_devices,
                    "hf_device_map": hf_device_map,
                    "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
                    "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
                    "preprocessing_runtime": preprocessing_runtime,
                    "torch": torch.__version__, "transformers": transformers.__version__,
                },
            }
            record["record_sha256"] = canonical_hash(record)
            if destination.exists():
                raise RuntimeError("destination appeared during inference")
            atomic_json(destination, record)
            append_attempt(args.execution_shard, {"event": "ACCEPTED", "attempt_id": attempt_id,
                                                   **{k: v for k, v in attempt_identity.items() if k != "attempt_id"},
                                                   "record_sha256": record["record_sha256"],
                                                   "generated_token_ids_sha256": generated_token_ids_sha256,
                                                   "recovered_after_crash": False})
            print(json.dumps({"artifact": str(destination.relative_to(ROOT)),
                              "parse_status": parse_status, "label": record["effective_label"],
                              "inference_seconds": inference_seconds}), flush=True)
            del frames, pil_frames, messages, inputs, generated, trimmed
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
        except Exception as exc:
            if not generation_started:
                rows = read_attempts(args.execution_shard)
                if rows and rows[-1].get("attempt_id") == attempt_id and rows[-1]["event"] == "PREPARED":
                    append_attempt(args.execution_shard, {"event": "PRE_INFERENCE_ABORTED", **attempt_identity,
                                                           "error_type": type(exc).__name__, "error": str(exc)})
            elif generation_completed and not destination.exists():
                append_attempt(args.execution_shard, {"event": "FAILED_POST_INFERENCE", **attempt_identity,
                                                       "error_type": type(exc).__name__, "error": str(exc)})
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-shard", choices=SHARDS, required=True)
    parser.add_argument("--declared-physical-gpus", required=True)
    parser.add_argument("--compute-approval", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_only(args.execution_shard), indent=2, sort_keys=True))
        return
    if args.compute_approval is None:
        raise RuntimeError("physical execution requires --compute-approval from explicit user authorization")
    approval_path = args.compute_approval if args.compute_approval.is_absolute() else ROOT / args.compute_approval
    prereg = load(PREREG)
    validate_execution_seal("runner")
    compute_approval_sha256 = validate_compute_approval(approval_path, prereg)
    lock = acquire_shard_lock(args.execution_shard)
    try:
        run_physical(args, approval_path, compute_approval_sha256)
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == "__main__":
    main()
