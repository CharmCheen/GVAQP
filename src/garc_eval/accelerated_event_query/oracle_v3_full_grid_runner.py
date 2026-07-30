"""Sealed three-worker runner for the V3 1,475-unit full grid.

Importing or validating this module never loads the checkpoint.  Checkpoint
loading is reachable only through :func:`run_worker` after an exact approval
artifact, package validation, initialization audit, and GPU binding check.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import time
from pathlib import Path
from typing import Any

from .oracle_v3_full_grid_control import GlobalFailStopCoordinator, append_hash_chain
from .oracle_v3_full_grid_manifest import (
    EXPECTED_UNIT_COUNT,
    decode_full_grid_unit,
    fraction_fps,
    public_frame,
)
from .oracle_v3_full_grid_package import (
    APPROVAL,
    EXECUTION,
    FRAMES,
    PACKAGE,
    PROCESSED_INPUTS,
    ROOT,
    SCHEDULE,
    SEAL,
    UNITS,
    validate_execution_seal,
)
from .oracle_v3_full_grid_processing import (
    load_frozen_processor,
    prepare_frozen_model_inputs,
    runtime_environment_identity,
    tensor_bundle_sha256,
)
from .oracle_v3_manifest import (
    atomic_text,
    canonical_hash,
    load_json,
    sha256_file,
    validate_payload_hash,
)
from .oracle_v3_parser import parse_oracle_v3_response


# Two formal executions falsified the former 23.579961- and 35-second bounds.
# The latter failure occurred only after all three frozen workers activated,
# providing direct concurrent-load evidence.  This replacement is
# prospectively frozen from the 192-token generation cap, the preserved
# 473-call runtime sample, and a token-cap scaling of the concurrent tail; see
# FULL_GRID_CALL_RESERVATION_DERIVATION.json.  It remains a hard per-call cost
# reservation, not a latency target or permission to retry.
CALL_RESERVATION_WALL_SECONDS = 65.0
MODEL_LOAD_RESERVATION_WALL_SECONDS = 30.0
LOADED_WORKER_IDLE_LEASE_SECONDS = 2.0
LOADED_WORKER_EMERGENCY_RESERVATION_WALL_SECONDS = 8.0
ENVELOPE_A100_GPU_HOURS = 54.0
GPU_IDLE_MAX_MEMORY_MIB = 16
GPU_IDLE_MAX_UTILIZATION_PERCENT = 0
EXPECTED_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
if os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in {
    None, EXPECTED_CUBLAS_WORKSPACE_CONFIG
}:
    raise RuntimeError("conflicting CUBLAS_WORKSPACE_CONFIG was set before runner import")
os.environ["CUBLAS_WORKSPACE_CONFIG"] = EXPECTED_CUBLAS_WORKSPACE_CONFIG
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _worker_map(schedule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["worker_id"]: row for row in schedule["workers"]}


def _coordinator(schedule: dict[str, Any], seal_sha256: str, execution_root: Path) -> GlobalFailStopCoordinator:
    bindings = {
        row["worker_id"]: {
            "physical_gpu_ids": row["physical_gpu_ids"],
            "unit_ids": row["unit_ids"],
        }
        for row in schedule["workers"]
    }
    return GlobalFailStopCoordinator(
        execution_root,
        execution_seal_sha256=seal_sha256,
        worker_bindings=bindings,
        envelope_a100_gpu_hours=ENVELOPE_A100_GPU_HOURS,
        call_reservation_wall_seconds=CALL_RESERVATION_WALL_SECONDS,
        model_load_reservation_wall_seconds=MODEL_LOAD_RESERVATION_WALL_SECONDS,
        loaded_worker_emergency_reservation_wall_seconds=(
            LOADED_WORKER_EMERGENCY_RESERVATION_WALL_SECONDS
        ),
    )


def validate_compute_approval(path: Path = APPROVAL) -> dict[str, Any]:
    approval = load_json(path)
    expected = {
        "status", "experiment_id", "execution_seal_sha256",
        "review_bundle_sha256", "final_package_manifest_sha256",
        "approved_call_count", "estimated_a100_gpu_hours",
        "authorization_envelope_a100_gpu_hours", "parallel_wall_hours",
        "worker_gpu_pairs", "model_load_count", "reload_count", "retry_count",
        "partial_results_are_not_formal_reference", "downstream_not_authorized",
        "fresh_execution_id", "fresh_execution_root",
        "fresh_execution_starts_from_unit_ordinal",
        "prior_completed_labels_reused",
        "project_historical_reexecution_authorized",
        "retry_semantics",
        "prior_failed_run_conservative_usage_upper_bound_a100_gpu_hours",
        "prior_plus_fresh_formal_envelope_a100_gpu_hours",
        "expanded_authorization_a100_gpu_hours",
        "user_approval_evidence",
    }
    review_bundle = PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json"
    final_package = PACKAGE / "FULL_GRID_PACKAGE_MANIFEST.json"
    derivation = load_json(
        PACKAGE / "FULL_GRID_CALL_RESERVATION_DERIVATION.json"
    )
    schedule = load_json(SCHEDULE)
    if set(approval) != expected or not all((
        approval.get("status") == "APPROVED_BY_USER_FOR_EXACT_FULL_GRID_SEAL",
        approval.get("experiment_id") == "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID",
        approval.get("execution_seal_sha256") == sha256_file(SEAL),
        approval.get("review_bundle_sha256") == sha256_file(review_bundle),
        approval.get("final_package_manifest_sha256") == sha256_file(final_package),
        approval.get("approved_call_count") == EXPECTED_UNIT_COUNT,
        approval.get("estimated_a100_gpu_hours") == 16.09712320568816,
        approval.get("authorization_envelope_a100_gpu_hours") == ENVELOPE_A100_GPU_HOURS,
        approval.get("parallel_wall_hours") == 3.0931814077885096,
        approval.get("worker_gpu_pairs") == {
            row["worker_id"]: row["physical_gpu_ids"] for row in schedule["workers"]
        },
        approval.get("model_load_count") == 3,
        approval.get("reload_count") == 0,
        approval.get("retry_count") == 0,
        approval.get("partial_results_are_not_formal_reference") is True,
        approval.get("downstream_not_authorized") is True,
        approval.get("fresh_execution_id")
        == "AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID_FRESH_CONCURRENT_RESERVATION_V3",
        approval.get("fresh_execution_root") == str(EXECUTION.relative_to(ROOT)),
        approval.get("fresh_execution_starts_from_unit_ordinal") == 0,
        approval.get("prior_completed_labels_reused") is False,
        approval.get("project_historical_reexecution_authorized") is True,
        approval.get("retry_semantics")
        == "zero retries within the fresh execution; prior failed-run units are deliberately re-executed from unit zero under a new seal",
        approval.get(
            "prior_failed_run_conservative_usage_upper_bound_a100_gpu_hours"
        ) == derivation[
            "prior_failed_run_conservative_usage_upper_bound_a100_gpu_hours"
        ],
        approval.get("prior_plus_fresh_formal_envelope_a100_gpu_hours")
        == derivation["prior_plus_fresh_formal_envelope_a100_gpu_hours"],
        approval.get("expanded_authorization_a100_gpu_hours") == 64.0,
        isinstance(approval.get("user_approval_evidence"), str),
        bool(approval.get("user_approval_evidence", "").strip()),
        "FILL" not in approval.get("user_approval_evidence", ""),
    )):
        raise RuntimeError("approval does not bind the exact reviewed full-grid package")
    return approval


def _gpu_identity(index: int) -> str:
    value = subprocess.check_output([
        "nvidia-smi", f"--id={index}", "--query-gpu=index,name,uuid",
        "--format=csv,noheader",
    ], text=True).strip()
    if not value.startswith(f"{index},") or "NVIDIA A100-SXM4-80GB" not in value:
        raise RuntimeError(f"unexpected physical GPU identity: {value}")
    return value


def authenticate_gpu_exclusivity(indices: list[int]) -> dict[str, Any]:
    """Require exact target GPUs to be idle and free of compute contexts."""

    requested = set(indices)
    if len(requested) != len(indices):
        raise RuntimeError("duplicate GPU in exclusivity request")
    table = subprocess.check_output([
        "nvidia-smi",
        "--query-gpu=index,uuid,utilization.gpu,memory.used",
        "--format=csv,noheader,nounits",
    ], text=True)
    rows: dict[int, dict[str, Any]] = {}
    for line in table.splitlines():
        tokens = [token.strip() for token in line.split(",")]
        if len(tokens) != 4:
            raise RuntimeError("unparseable GPU telemetry")
        index = int(tokens[0])
        if index in requested:
            rows[index] = {
                "index": index,
                "uuid": tokens[1],
                "utilization_percent": int(tokens[2]),
                "memory_used_mib": int(tokens[3]),
            }
    if set(rows) != requested:
        raise RuntimeError("GPU telemetry lacks a sealed target")
    applications = subprocess.check_output([
        "nvidia-smi",
        "--query-compute-apps=gpu_uuid,pid,used_memory",
        "--format=csv,noheader,nounits",
    ], text=True)
    target_uuids = {row["uuid"] for row in rows.values()}
    contexts = []
    for line in applications.splitlines():
        if not line.strip():
            continue
        tokens = [token.strip() for token in line.split(",")]
        if len(tokens) != 3:
            raise RuntimeError("unparseable GPU process telemetry")
        if tokens[0] in target_uuids:
            contexts.append({
                "gpu_uuid": tokens[0],
                "pid": tokens[1],
                "used_memory_mib": tokens[2],
            })
    idle = all(
        row["utilization_percent"] <= GPU_IDLE_MAX_UTILIZATION_PERCENT
        and row["memory_used_mib"] <= GPU_IDLE_MAX_MEMORY_MIB
        for row in rows.values()
    )
    if contexts or not idle:
        raise RuntimeError(
            f"GPU exclusivity/idleness authentication failed: "
            f"rows={list(rows.values())}:contexts={contexts}"
        )
    return {
        "physical_gpu_ids": sorted(requested),
        "gpus": [rows[index] for index in sorted(rows)],
        "compute_contexts": contexts,
        "maximum_memory_used_mib": GPU_IDLE_MAX_MEMORY_MIB,
        "maximum_utilization_percent": GPU_IDLE_MAX_UTILIZATION_PERCENT,
        "authenticated_exclusive_idle": True,
    }


def _verify_model_files(prereg: dict[str, Any]) -> str:
    binding = prereg["bindings"]["model_file_manifest"]
    manifest = load_json(ROOT / binding["path"])
    model_path = ROOT / prereg["model"]["path"]
    expected = {row["file"]: row for row in manifest["files"]}
    observed_names = {path.name for path in model_path.iterdir() if path.is_file()}
    if observed_names != set(expected):
        raise RuntimeError("current model file set differs from the frozen manifest")
    rows = []
    for name in sorted(expected):
        path = model_path / name
        row = {"file": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        if row != expected[name]:
            raise RuntimeError(f"current model file mismatch: {name}")
        rows.append(row)
    if canonical_hash(rows) != prereg["model"]["content_hash"]:
        raise RuntimeError("current canonical model content hash mismatch")
    return sha256_file(ROOT / binding["path"])


def _verify_processor_environment() -> dict[str, Any]:
    manifest = load_json(PROCESSED_INPUTS)
    observed = runtime_environment_identity()
    if observed != manifest.get("processor_environment"):
        raise RuntimeError("processor runtime environment differs from frozen identity")
    return manifest


def _validate_supervisor_authority(worker_id: str) -> None:
    authority = load_json(EXECUTION / "SUPERVISOR_LAUNCH_AUTHORITY.json")
    validate_payload_hash(authority, "supervisor_authority_payload_sha256")
    declared_parent = os.environ.get("FULL_GRID_SUPERVISOR_PID")
    if not all((
        authority.get("status") == "SUPERVISOR_AUTHORIZED_EXACT_WORKER_LAUNCH",
        authority.get("execution_seal_sha256") == sha256_file(SEAL),
        authority.get("supervisor_pid") == os.getppid(),
        declared_parent == str(os.getppid()),
        worker_id in authority.get("worker_ids", []),
    )):
        raise RuntimeError("worker was not launched by the sealed supervisor")


def install_supervisor_parent_death_signal() -> int:
    """Ask Linux to SIGKILL this worker if its exact supervisor dies."""

    import ctypes
    import signal

    declared = os.environ.get("FULL_GRID_SUPERVISOR_PID")
    if declared is None or not declared.isdigit():
        raise RuntimeError("sealed supervisor PID is not declared")
    expected_parent = int(declared)
    if os.getppid() != expected_parent:
        raise RuntimeError("worker parent differs before PDEATHSIG installation")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        error = ctypes.get_errno()
        raise OSError(error, "PR_SET_PDEATHSIG failed")
    if os.getppid() != expected_parent:
        os.kill(os.getpid(), signal.SIGKILL)
    return expected_parent


def initialize_execution(execution_root: Path = EXECUTION) -> dict[str, Any]:
    """Approval-gated host audit; performs no model load and no inference."""

    _, prereg = validate_execution_seal("runner")
    approval = validate_compute_approval()
    schedule = load_json(SCHEDULE)
    _verify_processor_environment()
    identities = {
        row["worker_id"]: [_gpu_identity(index) for index in row["physical_gpu_ids"]]
        for row in schedule["workers"]
    }
    initial_worker_id = schedule.get("initial_worker_id")
    workers = _worker_map(schedule)
    initial_worker = workers.get(initial_worker_id)
    if schedule.get("activation_mode") != "staged_pair_authentication" or initial_worker is None:
        raise RuntimeError("staged schedule lacks an exact initial worker")
    exclusivity = authenticate_gpu_exclusivity(initial_worker["physical_gpu_ids"])
    model_manifest_sha256 = _verify_model_files(prereg)
    seal_sha = sha256_file(SEAL)
    coordinator = _coordinator(schedule, seal_sha, execution_root)
    coordinator.initialize()
    audit = {
        "status": "INITIALIZED_NO_MODEL_LOAD",
        "execution_seal_sha256": seal_sha,
        "compute_approval_sha256": sha256_file(APPROVAL),
        "model_file_manifest_sha256": model_manifest_sha256,
        "gpu_identities": identities,
        "gpu_exclusivity": exclusivity,
        "gpu_exclusivity_scope": "initial_worker_pair_only",
        "initial_worker_id": initial_worker_id,
        "pending_worker_ids": [
            row["worker_id"] for row in schedule["workers"]
            if row["worker_id"] != initial_worker_id
        ],
        "exact_worker_count": 3,
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "checkpoint_loaded": False,
    }
    audit["initialization_payload_sha256"] = canonical_hash(audit)
    atomic_text(
        execution_root / "INITIALIZATION_AUDIT.json",
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
    )
    return audit


def _frames_by_unit(frame_manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in frame_manifest["frames"]:
        result.setdefault(row["unit_id"], []).append({
            "ordinal": row["unit_frame_ordinal"],
            "target_relative_seconds": row["target_relative_seconds"],
            "target_absolute_seconds": row["target_absolute_seconds"],
            "ideal_requested_index": row["ideal_requested_index"],
            "requested_index": row["requested_index"],
            "source_boundary_resolution": row["source_boundary_resolution"],
            "decoded_index": row["decoded_index"],
            "decoded_timestamp_seconds": row["decoded_timestamp_seconds"],
            "content_sha256": row["content_sha256"],
        })
    return result


def _decode_and_validate_unit(
    unit: dict[str, Any], video: dict[str, Any], expected_frames: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    kind, frames = decode_full_grid_unit(
        ROOT / video["path"],
        unit["start_time"],
        unit["end_time"],
        fraction_fps(video["nominal_fps"]),
        include_rgb=True,
    )
    public = [public_frame(row) for row in frames]
    if kind != unit["unit_kind"] or public != expected_frames:
        raise RuntimeError(f"decoded input differs from frozen manifest: {unit['unit_id']}")
    if canonical_hash(public) != unit["frame_set_sha256"]:
        raise RuntimeError(f"frame-set hash mismatch: {unit['unit_id']}")
    return frames


def validate_worker_inputs(
    worker_id: str, *, redecode: bool = False, reprocess: bool = False
) -> dict[str, Any]:
    """No-checkpoint validation path used by preregistration dry-runs."""

    _, prereg = validate_execution_seal("runner")
    units = load_json(UNITS)
    schedule = load_json(SCHEDULE)
    frames = load_json(FRAMES)
    worker = _worker_map(schedule).get(worker_id)
    if worker is None:
        raise ValueError("unknown worker")
    unit_map = {row["unit_id"]: row for row in units["units"]}
    frame_map = _frames_by_unit(frames)
    videos = {
        row["video_id"]: row
        for row in load_json(ROOT / prereg["bindings"]["video_manifest"]["path"])["videos"]
    }
    processor = None
    prompt = None
    processed_manifest = _verify_processor_environment()
    expected_processed = {
        row["unit_id"]: row["processed_input_sha256"]
        for row in processed_manifest["units"]
    }
    if reprocess:
        processor = load_frozen_processor(ROOT / prereg["model"]["path"])
        processor_class = f"{processor.__class__.__module__}.{processor.__class__.__qualname__}"
        if processor_class != processed_manifest["processor_class"]:
            raise RuntimeError("processor class differs from frozen identity")
        prompt = (ROOT / prereg["bindings"]["prompt"]["path"]).read_text(
            encoding="utf-8"
        )
    checked_frames = 0
    for unit_id in worker["unit_ids"]:
        unit = unit_map[unit_id]
        decoded = None
        if redecode or reprocess:
            decoded = _decode_and_validate_unit(
                unit, videos[unit["video_id"]], frame_map[unit_id]
            )
        if reprocess:
            inputs = prepare_frozen_model_inputs(
                processor,
                prompt=prompt,
                rgb_frames=[row["rgb"] for row in decoded],
                unit_kind=unit["unit_kind"],
                true_duration_seconds=unit["duration_seconds"],
                sampling_fps=2.0,
            )
            observed = tensor_bundle_sha256(inputs)
            if observed != expected_processed[unit_id] or observed != unit[
                "expected_processed_input_sha256"
            ]:
                raise RuntimeError(f"processed-input identity mismatch: {unit_id}")
        checked_frames += len(frame_map[unit_id])
    return {
        "status": "PASS_NO_MODEL_LOAD_NO_INFERENCE",
        "worker_id": worker_id,
        "exact_call_count": len(worker["unit_ids"]),
        "frame_occurrence_count": checked_frames,
        "redecoded": redecode,
        "reprocessed": reprocess,
        "checkpoint_loaded": False,
    }


def run_worker(worker_id: str, declared_physical_gpus: list[int]) -> None:
    """Execute one fixed shard after approval.  Not called during preregistration."""

    install_supervisor_parent_death_signal()
    import numpy as np
    import torch
    import transformers
    from transformers import Qwen3VLForConditionalGeneration

    _, prereg = validate_execution_seal("runner")
    validate_compute_approval()
    _validate_supervisor_authority(worker_id)
    schedule = load_json(SCHEDULE)
    units = load_json(UNITS)
    frame_manifest = load_json(FRAMES)
    processed_manifest = _verify_processor_environment()
    workers = _worker_map(schedule)
    worker = workers.get(worker_id)
    if worker is None or worker["physical_gpu_ids"] != declared_physical_gpus:
        raise RuntimeError("worker/GPU declaration differs from seal")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != ",".join(map(str, declared_physical_gpus)):
        raise RuntimeError("CUDA_VISIBLE_DEVICES differs from sealed GPU pair")
    if torch.cuda.device_count() != 2:
        raise RuntimeError("worker must see exactly two logical CUDA devices")
    identities = [_gpu_identity(index) for index in declared_physical_gpus]
    worker_gpu_exclusivity = authenticate_gpu_exclusivity(declared_physical_gpus)
    initialization = load_json(EXECUTION / "INITIALIZATION_AUDIT.json")
    if initialization.get("execution_seal_sha256") != sha256_file(SEAL):
        raise RuntimeError("missing exact initialization audit")
    coordinator = _coordinator(schedule, sha256_file(SEAL), EXECUTION)
    prompt = (ROOT / prereg["bindings"]["prompt"]["path"]).read_text(encoding="utf-8")
    unit_map = {row["unit_id"]: row for row in units["units"]}
    frame_map = _frames_by_unit(frame_manifest)
    videos = {
        row["video_id"]: row
        for row in load_json(ROOT / prereg["bindings"]["video_manifest"]["path"])["videos"]
    }
    ledger = EXECUTION / worker["attempt_ledger_relative_path"]
    if ledger.exists() or any((EXECUTION / unit_map[unit_id]["raw_output_relative_path"]).exists()
                              for unit_id in worker["unit_ids"]):
        coordinator.trigger_stop("output_path_collision", worker_id)
        raise RuntimeError("in-approval resume or output collision is forbidden")
    coordinator.start_model_load(worker_id, declared_physical_gpus)
    append_hash_chain(ledger, {
        "event": "MODEL_LOAD_STARTED", "worker_id": worker_id,
        "physical_gpu_ids": declared_physical_gpus,
    })
    try:
        load_started = time.perf_counter()
        model_path = ROOT / prereg["model"]["path"]
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, dtype=torch.bfloat16, device_map="balanced",
            trust_remote_code=True, local_files_only=True,
        )
        model.to(dtype=torch.bfloat16)
        processor = load_frozen_processor(model_path)
        processor_class = f"{processor.__class__.__module__}.{processor.__class__.__qualname__}"
        if processor_class != processed_manifest["processor_class"]:
            coordinator.trigger_stop(
                "processed_input_identity_mismatch", "processor_class"
            )
            raise RuntimeError("processor class differs from frozen identity")
        model.eval()
        torch.use_deterministic_algorithms(True, warn_only=False)
        seed = int(prereg["decoding"]["seed"])
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        torch.cuda.synchronize()
        load_seconds = time.perf_counter() - load_started
        coordinator.complete_model_load(worker_id, load_seconds)
        session_id = canonical_hash({
            "worker_id": worker_id, "pid": os.getpid(), "time_ns": time.time_ns(),
            "nonce": hashlib.sha256(os.urandom(32)).hexdigest(),
        })
        append_hash_chain(ledger, {
            "event": "MODEL_LOAD_COMPLETED", "worker_id": worker_id,
            "physical_gpu_ids": declared_physical_gpus,
            "execution_session_id": session_id, "wall_seconds": load_seconds,
        })
        for unit_id in worker["unit_ids"]:
            if coordinator.state()["status"] != "READY":
                raise RuntimeError("global fail-stop is active")
            unit = unit_map[unit_id]
            call_started = time.perf_counter()
            attempt_id = f"{worker_id}:{unit_id}:{time.time_ns()}"
            common = {
                "worker_id": worker_id, "unit_id": unit_id,
                "call_spec_sha256": unit["call_spec_sha256"],
                "attempt_id": attempt_id, "execution_session_id": session_id,
            }
            coordinator.reserve_call(
                worker_id=worker_id, gpu_pair=declared_physical_gpus,
                unit_id=unit_id, call_spec_sha256=unit["call_spec_sha256"],
            )
            frames = _decode_and_validate_unit(unit, videos[unit["video_id"]], frame_map[unit_id])
            inputs = prepare_frozen_model_inputs(
                processor,
                prompt=prompt,
                rgb_frames=[row["rgb"] for row in frames],
                unit_kind=unit["unit_kind"],
                true_duration_seconds=unit["duration_seconds"],
                sampling_fps=2.0,
            ).to(model.device)
            processed_hash = tensor_bundle_sha256(inputs)
            if processed_hash != unit["expected_processed_input_sha256"]:
                coordinator.trigger_stop(
                    "processed_input_identity_mismatch", unit_id
                )
                raise RuntimeError(
                    f"processed input differs from preregistration: {unit_id}"
                )
            append_hash_chain(ledger, {
                "event": "PREPARED", **common,
                "processed_input_sha256": processed_hash,
            })
            append_hash_chain(ledger, {
                "event": "INFERENCE_STARTED", **common,
                "processed_input_sha256": processed_hash,
            })
            inference_started = time.perf_counter()
            with torch.no_grad():
                generated = model.generate(
                    **inputs, do_sample=False,
                    max_new_tokens=int(prereg["decoding"]["max_new_tokens"]),
                )
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            generated_hash = tensor_bundle_sha256({"generated": generated})
            append_hash_chain(ledger, {
                "event": "INFERENCE_COMPLETED", **common,
                "generated_token_ids_sha256": generated_hash,
            })
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed = parse_oracle_v3_response(raw)
            pre_persistence_call_seconds = time.perf_counter() - call_started
            identity = {
                "experiment_id": prereg["experiment_id"],
                "execution_seal_sha256": sha256_file(SEAL),
                "unit_id": unit_id,
                "call_spec_sha256": unit["call_spec_sha256"],
                "frame_set_sha256": unit["frame_set_sha256"],
                "unit_kind": unit["unit_kind"],
                "true_duration_seconds": unit["duration_seconds"],
                "model_visible_frame_count": unit["frame_count"],
                "model_visible_sampling_fps": 2.0,
            }
            record = {
                "status": "AUTHENTICATED_FULL_GRID_RAW_OUTPUT",
                "mock_not_oracle": False,
                "experiment_id": prereg["experiment_id"],
                "execution_seal_sha256": sha256_file(SEAL),
                "unit_id": unit_id,
                "unit_ordinal": unit["ordinal"],
                "video_id": unit["video_id"],
                "worker_id": worker_id,
                "physical_gpu_ids": declared_physical_gpus,
                "call_spec_sha256": unit["call_spec_sha256"],
                "frame_set_sha256": unit["frame_set_sha256"],
                "frame_count": unit["frame_count"],
                "execution_session_id": session_id,
                "attempt_id": attempt_id,
                "input_identity_sha256": canonical_hash(identity),
                "model_input_identity_sha256": canonical_hash({
                    **identity, "frames": frame_map[unit_id]
                }),
                "processed_input_sha256": processed_hash,
                "generated_token_ids_sha256": generated_hash,
                "raw": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "parse_status": parsed.parse_status,
                "authoritative_label": parsed.effective_label,
                "parsed": parsed.parsed,
                "runtime": {
                    "worker_id": worker_id,
                    "physical_gpu_ids": declared_physical_gpus,
                    "gpu_identities": identities,
                    "worker_preload_gpu_exclusivity": worker_gpu_exclusivity,
                    "model_load_seconds": load_seconds,
                    "inference_seconds": inference_seconds,
                    "pre_persistence_call_seconds": pre_persistence_call_seconds,
                    "processor_class": f"{processor.__class__.__module__}.{processor.__class__.__qualname__}",
                    "python": platform.python_version(),
                    "torch": torch.__version__,
                    "transformers": transformers.__version__,
                    "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils"),
                    "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
                },
            }
            record["record_payload_sha256"] = canonical_hash(record)
            destination = EXECUTION / unit["raw_output_relative_path"]
            atomic_text(destination, json.dumps(record, indent=2, sort_keys=True) + "\n")
            append_hash_chain(ledger, {
                "event": "ACCEPTED", **common,
                "record_payload_sha256": record["record_payload_sha256"],
            })
            call_seconds = time.perf_counter() - call_started
            coordinator.complete_call(
                worker_id=worker_id, unit_id=unit_id, wall_seconds=call_seconds
            )
        # End GPU residency before declaring the worker session closed.  A
        # hang anywhere before this point remains covered by the loaded-idle
        # lease; a live process after closure remains covered until exit.
        import gc

        del inputs, generated, trimmed, model
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        coordinator.complete_worker_session(worker_id)
    except Exception as exc:
        try:
            coordinator.trigger_stop(
                "post_load_process_fault",
                f"{worker_id}:{type(exc).__name__}:{exc}",
            )
        finally:
            raise
