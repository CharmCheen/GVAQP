#!/usr/bin/env python3
"""Recompute the missing frozen Stage-A physical-cost artifact.

The frozen oracle runner records all required raw timing/accounting evidence
but does not itself write STAGE_A_PHYSICAL_COST.json.  This independent step is
run after inference and before finalization so the frozen completion marker can
bind the resulting artifact without changing the oracle runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a"
ORACLE = STAGE / "oracle"
RAW_DIR = ORACLE / "raw"
ATTEMPT_LOG = ORACLE / "ATTEMPT_EVENT_LOG.jsonl"
INPUT_IDENTITIES = ORACLE / "INPUT_IDENTITIES.jsonl"
BUILD_CONFIG = ORACLE / "ORACLE_BUILD_CONFIG.json"
MODEL_VALIDATION = ORACLE / "MODEL_CONTENT_VALIDATION.json"
PREPARATION_COMMIT = ORACLE / "PREPARATION_COMPLETE.json"
INFERENCE_RECEIPT = ORACLE / "STAGE_A_INFERENCE_RUN_RECEIPT.json"
RESOLVED_RUNTIME = ORACLE / "RESOLVED_INFERENCE_RUNTIME.json"
RUN_STATE = ORACLE / "STAGE_A_ORACLE_STATE.json"
COST = STAGE / "STAGE_A_PHYSICAL_COST.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
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


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("Cannot take percentile of empty values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def compute() -> dict[str, Any]:
    required = [
        ATTEMPT_LOG, INPUT_IDENTITIES, BUILD_CONFIG, MODEL_VALIDATION,
        PREPARATION_COMMIT, INFERENCE_RECEIPT, RESOLVED_RUNTIME, RUN_STATE,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Cost evidence is incomplete: {missing}")
    events = read_jsonl(ATTEMPT_LOG)
    identities = read_jsonl(INPUT_IDENTITIES)
    config = load_json(BUILD_CONFIG)
    validation = load_json(MODEL_VALIDATION)
    preparation = load_json(PREPARATION_COMMIT)
    receipt = load_json(INFERENCE_RECEIPT)
    state = load_json(RUN_STATE)
    raw_paths = sorted(RAW_DIR.glob("mf_psvr_stage_a_*.json"))
    raws = [load_json(path) for path in raw_paths]
    started = [event for event in events if event.get("event") == "STARTED"]
    accepted = [event for event in events if event.get("event") in {"ACCEPTED", "RECOVERED_ACCEPTED"}]
    uncertain = [event for event in events if event.get("event") == "RECOVERED_UNCERTAIN"]
    if not (
        len(identities) == len(raws) == len(started) == len(accepted) == 96
        and not uncertain
        and state.get("status") == "INFERENCE_COMPLETE"
        and int(state.get("accepted_durable_calls", -1)) == 96
    ):
        raise RuntimeError("Physical cost cannot be finalized before exact 96-call inference completion")
    call_ids = [f"mf_psvr_stage_a_{ordinal:03d}" for ordinal in range(1, 97)]
    if [raw["physical_call_id"] for raw in raws] != call_ids:
        raise RuntimeError("Raw physical-call ordering or identity changed")
    if {event["physical_call_id"] for event in started} != set(call_ids):
        raise RuntimeError("Attempt ledger and raw universe differ")

    generation = [float(raw["generation_runtime_seconds"]) for raw in raws]
    model_load = [float(raw["model_load_seconds"]) for raw in raws]
    if any(not math.isfinite(value) or value < 0 for value in generation + model_load):
        raise RuntimeError("Physical timing contains invalid numeric values")
    if sum(value > 0 for value in model_load) != 1:
        raise RuntimeError("Exactly one resident model load must be charged")
    inference_start = datetime.fromisoformat(receipt["process_start_utc"].replace("Z", "+00:00"))
    inference_complete = datetime.fromtimestamp(ATTEMPT_LOG.stat().st_mtime, tz=timezone.utc)
    inference_wall_seconds = (inference_complete - inference_start).total_seconds()
    if inference_wall_seconds <= 0:
        raise RuntimeError("Inference wall-clock receipt is invalid")
    preparation_seconds = float(config["precommit_preparation_wall_seconds"])
    generation_seconds = sum(generation)
    model_load_seconds = sum(model_load)
    unattributed = inference_wall_seconds - generation_seconds - model_load_seconds
    if unattributed < -1e-6:
        raise RuntimeError("Measured inference components exceed process wall clock")
    peak_allocated = max(int(raw["peak_gpu_memory_allocated_bytes"]) for raw in raws)
    peak_reserved = max(int(raw["peak_gpu_memory_reserved_bytes"]) for raw in raws)
    raw_hashes = {path.name: sha256_file(path) for path in raw_paths}
    value = {
        "cost_id": "MF_PSVR_CYCLE1_STAGE_A_PHYSICAL_COST_V1",
        "status": "COMPLETE_INFERENCE_COST_BEFORE_CPU_FINALIZATION",
        "created_at_utc": utc_now(),
        "oracle_build_id": config["oracle_build_id"],
        "physical_attempts_started": len(started),
        "accepted_durable_calls": len(accepted),
        "uncertain_started_calls": len(uncertain),
        "physical_call_ids": call_ids,
        "preparation_wall_seconds": preparation_seconds,
        "identity_preparation_wall_seconds": float(config["identity_preparation_wall_seconds"]),
        "model_content_validation_wall_seconds": float(config["model_content_validation_wall_seconds"]),
        "model_content_bytes_hashed": int(validation["bytes_hashed"]),
        "inference_process_start_utc": inference_start.isoformat().replace("+00:00", "Z"),
        "inference_attempt_log_completion_utc": inference_complete.isoformat().replace("+00:00", "Z"),
        "inference_process_wall_seconds": inference_wall_seconds,
        "resident_model_load_seconds": model_load_seconds,
        "generation_runtime_seconds_sum": generation_seconds,
        "generation_runtime_seconds_mean": statistics.mean(generation),
        "generation_runtime_seconds_p50": percentile(generation, 0.50),
        "generation_runtime_seconds_p95": percentile(generation, 0.95),
        "generation_runtime_seconds_min": min(generation),
        "generation_runtime_seconds_max": max(generation),
        "inference_unattributed_wall_seconds": max(0.0, unattributed),
        "inference_unattributed_scope": "runner validation/imports, frame re-decode, processor/model-input construction, synchronization, durable serialization, and ledger commits",
        "prepared_decoded_frames": int(config["decoded_frames"]),
        "inference_redecoded_frames": int(config["decoded_frames"]),
        "peak_gpu_memory_allocated_bytes": peak_allocated,
        "peak_gpu_memory_reserved_bytes": peak_reserved,
        "total_physical_cost_seconds": preparation_seconds + inference_wall_seconds,
        "total_physical_cost_scope": "input/model preparation plus the complete resident 96-call inference process; post-inference CPU parse/K3/report finalization excluded",
        "active_gpu_kernel_seconds_measured": False,
        "raw_envelope_hashes": raw_hashes,
        "attempt_log_sha256": sha256_file(ATTEMPT_LOG),
        "input_identities_sha256": sha256_file(INPUT_IDENTITIES),
        "build_config_sha256": sha256_file(BUILD_CONFIG),
        "model_validation_sha256": sha256_file(MODEL_VALIDATION),
        "preparation_commit_sha256": sha256_file(PREPARATION_COMMIT),
        "inference_receipt_sha256": sha256_file(INFERENCE_RECEIPT),
        "resolved_runtime_sha256": sha256_file(RESOLVED_RUNTIME),
        "model_full_content_hash": validation["model_full_content_hash"],
        "heldout_opened": False,
        "limitations": [
            "The frozen runner did not separately time frame re-decode, processor construction, serialization, or active GPU kernels; these remain in inference_unattributed_wall_seconds.",
            "CPU-only parse, K3 grouping, and final report time occur after this artifact must be frozen and are reported separately in STAGE_A_COMPLETION_AUDIT.json.",
        ],
    }
    value["cost_hash"] = canonical_hash(value)
    return value


def write() -> dict[str, Any]:
    value = compute()
    atomic_bytes(COST, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())
    return value


def verify() -> dict[str, Any]:
    if not COST.is_file():
        raise RuntimeError("Stage-A physical cost artifact is absent")
    observed = load_json(COST)
    claimed = observed.get("cost_hash")
    payload = {key: value for key, value in observed.items() if key != "cost_hash"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("Stage-A physical cost self-hash is invalid")
    recomputed = compute()
    for key, value in recomputed.items():
        if key not in {"created_at_utc", "cost_hash"} and observed.get(key) != value:
            raise RuntimeError(f"Stage-A physical cost does not recompute: {key}")
    return observed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["write", "verify"])
    args = parser.parse_args()
    value = write() if args.stage == "write" else verify()
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
