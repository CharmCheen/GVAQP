#!/usr/bin/env python3
"""Prepare, execute, finalize, and verify the frozen MF-PSVR Stage-A oracle.

`freeze-spec` and `preflight` are safe and perform no semantic frame decode or
model loading. `prepare` decodes and hashes every frozen input before call 1;
`infer` performs the physically charged calls. Both require explicit authority.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.util
import inspect
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.mf_psvr.stage_a_oracle import (  # noqa: E402
    append_hash_chain,
    canonical_hash,
    evaluate_support_gates,
    execution_spec,
    k3_bridge_safe_groups,
    projected_label,
    seed_for_call,
    validate_attempt_events,
)


CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
STAGE_A = CYCLE / "stage_a"
ORACLE_OUT = STAGE_A / "oracle"
RAW_DIR = ORACLE_OUT / "raw"
PARSED_DIR = ORACLE_OUT / "parsed"
EXECUTION_SPEC = STAGE_A / "STAGE_A_ORACLE_EXECUTION_SPEC.json"
SAMPLE = STAGE_A / "STAGE_A_FROZEN_SAMPLE.csv"
QUERY_OPPORTUNITIES = STAGE_A / "STAGE_A_QUERY_OPPORTUNITIES.csv"
SELECTION_FREEZE = STAGE_A / "STAGE_A_FREEZE_MANIFEST.json"
INPUT_IDENTITIES = ORACLE_OUT / "INPUT_IDENTITIES.jsonl"
BUILD_CONFIG = ORACLE_OUT / "ORACLE_BUILD_CONFIG.json"
PREPARATION_COMMIT = ORACLE_OUT / "PREPARATION_COMPLETE.json"
MODEL_VALIDATION = ORACLE_OUT / "MODEL_CONTENT_VALIDATION.json"
RESOLVED_RUNTIME = ORACLE_OUT / "RESOLVED_INFERENCE_RUNTIME.json"
ATTEMPT_LOG = ORACLE_OUT / "ATTEMPT_EVENT_LOG.jsonl"
RUN_STATE = ORACLE_OUT / "STAGE_A_ORACLE_STATE.json"
COMPLETE_MARKER = ORACLE_OUT / "STAGE_A_ORACLE_COMPLETE.json"
SUPPORT_REPORT = STAGE_A / "STAGE_A_SUPPORT_GATE_REPORT.json"
EVENT_GROUPS = STAGE_A / "STAGE_A_K3_EVENT_GROUPS.csv"
PHYSICAL_COST = STAGE_A / "STAGE_A_PHYSICAL_COST.json"
CALL_MANIFEST = CYCLE / "ORACLE_CALL_MANIFEST.csv"
LABEL_MANIFEST = CYCLE / "ORACLE_LABEL_MANIFEST.csv"
STAGE_STATE = CYCLE / "STAGE_STATE.json"
SELECTION_STATE = STAGE_A / "STAGE_A_STATE.json"
PREINFERENCE_AUDIT_COPY = ORACLE_OUT / "PREINFERENCE_AUDIT_MANIFEST.json"

AUDIT_MANIFEST = CYCLE / "AUDIT_MANIFEST.json"
PROTOCOL = CYCLE / "ORACLE_ACQUISITION_PROTOCOL.json"
PROXY_CONFIG = CYCLE / "TRAINING_POOL_PROXY_CONFIG.json"
ORACLE_CONFIG = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/raw_oracle/V1/ORACLE_CONFIG.json"
ORACLE_RUNTIME = ROOT / "outputs/psvr_two_video_loop/deadlines/ORACLE_RUNTIME_CONFIG.json"
UNIT_SCORES = CYCLE / "candidates/UNIT_SCORES.csv"
UNIT_MANIFEST = CYCLE / "candidates/UNIT_MANIFEST.csv"
CANDIDATE_PLAN = CYCLE / "candidates/CANDIDATE_EXTRACTION_PLAN.json"
CANDIDATE_STATE = CYCLE / "candidates/CANDIDATE_EXTRACTION_STATE.json"
FROZEN_BUILDER = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
    "clean_baseline_benchmark_v2_strict/scripts/build_strict_oracle.py"
)
CORE_SOURCE = ROOT / "src/garc_eval/mf_psvr/stage_a_oracle.py"
PROJECTION_SOURCE = ROOT / "src/garc_eval/mf_psvr/training_pool.py"
SELECTOR_SOURCE = ROOT / "src/garc_eval/mf_psvr/stage_a.py"
FREEZER_SOURCE = ROOT / "scripts/freeze_mf_psvr_stage_a_sample.py"
LOCK = ORACLE_OUT / ".stage_a_oracle.lock"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode(),
    )


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    from io import StringIO

    if fields is None:
        fields = list(rows[0]) if rows else []
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, buffer.getvalue().encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    atomic_bytes(
        path,
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows).encode(),
    )


def load_frozen_builder():
    runtime = load_json(ORACLE_RUNTIME)
    if sha256_file(FROZEN_BUILDER) != runtime["frozen_oracle_source_sha256"]:
        raise RuntimeError("Frozen strict-oracle implementation changed")
    spec = importlib.util.spec_from_file_location("mf_stage_a_frozen_oracle", FROZEN_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen oracle implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_empty_authoritative_manifests() -> None:
    for path in (CALL_MANIFEST, LABEL_MANIFEST):
        if len(pd.read_csv(path, keep_default_na=False)) != 0:
            raise RuntimeError(f"Pre-call authoritative manifest is not empty: {path}")


def frozen_bindings() -> dict[str, Any]:
    oracle = load_json(ORACLE_CONFIG)
    runtime = load_json(ORACLE_RUNTIME)
    protocol = load_json(PROTOCOL)
    prompt_path = Path(runtime["prompt_path"])
    if not prompt_path.is_file() or sha256_file(prompt_path) != runtime["prompt_sha256"]:
        raise RuntimeError("Frozen oracle prompt content changed")
    return {
        "audit_manifest_sha256": sha256_file(AUDIT_MANIFEST),
        "acquisition_protocol_sha256": sha256_file(PROTOCOL),
        "acquisition_protocol_hash": protocol["protocol_hash"],
        "oracle_runtime_config_sha256": sha256_file(ORACLE_RUNTIME),
        "oracle_config_sha256": sha256_file(ORACLE_CONFIG),
        "runner_source_sha256": sha256_file(Path(__file__)),
        "core_source_sha256": sha256_file(CORE_SOURCE),
        "projection_source_sha256": sha256_file(PROJECTION_SOURCE),
        "frozen_builder_path": str(FROZEN_BUILDER),
        "frozen_builder_sha256": sha256_file(FROZEN_BUILDER),
        "model_path": runtime["model_path"],
        "model_full_content_hash": runtime["model_full_content_hash"],
        "prompt_path": runtime["prompt_path"],
        "prompt_sha256": runtime["prompt_sha256"],
        "parser_schema_hash": protocol["frozen_oracle"]["parser_schema_hash"],
        "parser_source_hash": protocol["frozen_oracle"]["parser_source_hash"],
        "sampling_code_hash": protocol["frozen_oracle"]["sampling_code_hash"],
        "generation_config": protocol["frozen_oracle"]["generation_config"],
        "frame_config": protocol["frozen_oracle"]["frame_config"],
        "model_file_count": len(runtime["model_file_identity"]),
        "heldout_opened": False,
    }


def validate_spec() -> dict[str, Any]:
    if not EXECUTION_SPEC.exists():
        raise RuntimeError("Stage-A oracle execution spec is not frozen")
    value = load_json(EXECUTION_SPEC)
    claimed = value["execution_spec_hash"]
    payload = {key: item for key, item in value.items() if key != "execution_spec_hash"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("Stage-A oracle execution spec self-hash is invalid")
    if value != execution_spec(frozen_bindings()):
        raise RuntimeError("Stage-A oracle execution bindings changed after freeze")
    if PREINFERENCE_AUDIT_COPY.exists() and (
        sha256_file(PREINFERENCE_AUDIT_COPY) != value["bindings"]["audit_manifest_sha256"]
    ):
        raise RuntimeError("Preserved pre-inference audit snapshot changed")
    return value


def ensure_preinference_audit_copy(spec: dict[str, Any]) -> None:
    expected = spec["bindings"]["audit_manifest_sha256"]
    if sha256_file(AUDIT_MANIFEST) != expected:
        raise RuntimeError("Current audit manifest no longer matches the frozen execution spec")
    if PREINFERENCE_AUDIT_COPY.exists():
        if sha256_file(PREINFERENCE_AUDIT_COPY) != expected:
            raise RuntimeError("Preserved pre-inference audit snapshot is invalid")
        return
    atomic_bytes(PREINFERENCE_AUDIT_COPY, AUDIT_MANIFEST.read_bytes())
    if sha256_file(PREINFERENCE_AUDIT_COPY) != expected:
        raise RuntimeError("Could not durably preserve the pre-inference audit snapshot")


def freeze_spec() -> dict[str, Any]:
    if EXECUTION_SPEC.exists():
        value = validate_spec()
        ensure_preinference_audit_copy(value)
        return value
    validate_empty_authoritative_manifests()
    candidate_state = load_json(CANDIDATE_STATE)
    if int(candidate_state.get("physical_y8_frames", 0)) != 0:
        raise RuntimeError("Execution spec must be frozen before pool Y8 inference")
    stage = load_json(STAGE_STATE)
    if int(stage["physical_oracle_calls"]) != 0 or stage["heldout_opened"] is not False:
        raise RuntimeError("Execution spec must be frozen before any oracle/held-out access")
    value = execution_spec(frozen_bindings())
    atomic_json(EXECUTION_SPEC, value)
    value = validate_spec()
    ensure_preinference_audit_copy(value)
    return value


def validate_selection() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not all(path.exists() for path in (SAMPLE, QUERY_OPPORTUNITIES, SELECTION_FREEZE)):
        raise RuntimeError("Stage-A selection identities are not frozen")
    freeze = load_json(SELECTION_FREEZE)
    sample = pd.read_csv(SAMPLE, keep_default_na=False)
    opportunities = pd.read_csv(QUERY_OPPORTUNITIES, keep_default_na=False)
    if freeze["status"] != "FROZEN_ORACLE_NOT_RUN":
        raise RuntimeError("Stage-A selection freeze is not in the pre-oracle state")
    claimed_freeze_hash = freeze.get("freeze_hash")
    freeze_payload = {key: value for key, value in freeze.items() if key != "freeze_hash"}
    if claimed_freeze_hash != canonical_hash(freeze_payload):
        raise RuntimeError("Stage-A selection freeze self-hash is invalid")
    frozen_artifacts = {
        PROTOCOL: "protocol_sha256",
        PROXY_CONFIG: "proxy_config_sha256",
        CANDIDATE_PLAN: "candidate_plan_sha256",
        CANDIDATE_STATE: "candidate_state_sha256",
        UNIT_MANIFEST: "unit_manifest_sha256",
        UNIT_SCORES: "unit_scores_sha256",
    }
    for path, field in frozen_artifacts.items():
        if not path.exists() or sha256_file(path) != freeze[field]:
            raise RuntimeError(f"Stage-A selection input changed after freeze: {path}")
    if sha256_file(SELECTOR_SOURCE) != freeze["selector_source_sha256"]:
        raise RuntimeError("Stage-A selector source changed after selection freeze")
    pilot = load_json(PROTOCOL)["stage_a_support_pilot"]
    if sha256_file(FREEZER_SOURCE) != pilot["freeze_runner_sha256"]:
        raise RuntimeError("Stage-A sample freezer source changed after protocol freeze")
    if int(freeze["physical_oracle_calls_at_freeze"]) != 0:
        raise RuntimeError("Stage-A selection was not frozen before physical calls")
    if sha256_file(SAMPLE) != freeze["sample_sha256"]:
        raise RuntimeError("Stage-A sample changed after freeze")
    if sha256_file(QUERY_OPPORTUNITIES) != freeze["query_opportunities_sha256"]:
        raise RuntimeError("Stage-A query opportunities changed after freeze")
    expected_calls = [f"mf_psvr_stage_a_{index:03d}" for index in range(1, 97)]
    if len(sample) != 96 or sample["physical_call_id"].tolist() != expected_calls:
        raise RuntimeError("Stage-A physical-call ordering is not canonical")
    identity_keys = ["source_dataset", "session_id", "unit_id"]
    if sample.duplicated(identity_keys).any():
        raise RuntimeError("Stage-A sample contains a duplicate physical unit")
    source_counts = sample.groupby(["source_dataset", "session_id"]).size()
    if len(source_counts) < 48 or int(source_counts.max()) > 2:
        raise RuntimeError("Stage-A provider-video diversity/cap invariant changed")
    expected_split_counts = {"model_train": 64, "model_calibration": 16, "pool_audit": 16}
    if sample["model_split_role"].value_counts().to_dict() != expected_split_counts:
        raise RuntimeError("Stage-A frozen split quotas changed")
    if len(opportunities) != 192 or opportunities["verification_key"].duplicated().any():
        raise RuntimeError("Stage-A query opportunity keys are not 192 unique rows")
    if opportunities.groupby("physical_call_id")["query_id"].agg(set).to_dict() != {
        call_id: {"Q1", "Q2"} for call_id in expected_calls
    }:
        raise RuntimeError("Each Stage-A call must map to exactly Q1 and Q2")
    expected_verification = opportunities.apply(
        lambda row: (
            f"{row['source_dataset']}|{row['session_id']}|"
            f"{row['query_id']}|{int(row['unit_id'])}"
        ),
        axis=1,
    )
    if not expected_verification.equals(opportunities["verification_key"]):
        raise RuntimeError("Stage-A query verification-key serialization changed")
    shared = ["source_dataset", "session_id", "source_sha256", "model_split_role", "unit_id"]
    expected_opportunities = sample[["physical_call_id", *shared]].merge(
        pd.DataFrame({"query_id": ["Q1", "Q2"]}), how="cross"
    ).sort_values(["physical_call_id", "query_id"]).reset_index(drop=True)
    observed_opportunities = opportunities[["physical_call_id", *shared, "query_id"]].sort_values(
        ["physical_call_id", "query_id"]
    ).reset_index(drop=True)
    if not expected_opportunities.equals(observed_opportunities):
        raise RuntimeError("Stage-A query opportunities are detached from the frozen sample")
    return sample, opportunities, freeze


def preflight() -> dict[str, Any]:
    spec = validate_spec()
    if not PREINFERENCE_AUDIT_COPY.exists():
        raise RuntimeError("Frozen pre-inference audit snapshot is absent")
    validate_empty_authoritative_manifests()
    result = {
        "status": "WAITING_FOR_FULL_POOL_CANDIDATES_AND_SELECTION",
        "execution_spec_hash": spec["execution_spec_hash"],
        "physical_oracle_calls": 0,
        "semantic_frames_decoded_by_preflight": 0,
        "model_loaded": False,
        "heldout_opened": False,
    }
    if SAMPLE.exists() or SELECTION_FREEZE.exists():
        sample, opportunities, freeze = validate_selection()
        result.update({
            "status": "READY_TO_PREPARE_INPUT_IDENTITIES",
            "selected_physical_calls": len(sample),
            "query_verification_keys": len(opportunities),
            "selection_freeze_hash": freeze["freeze_hash"],
        })
    return result


def validate_frozen_sources(frozen: Any, spec: dict[str, Any]) -> None:
    bindings = spec["bindings"]
    if sha256_text(inspect.getsource(frozen.parse_response)) != bindings["parser_source_hash"]:
        raise RuntimeError("Frozen oracle parser source changed")
    if canonical_hash(frozen.PARSER_CONFIG) != bindings["parser_schema_hash"]:
        raise RuntimeError("Frozen oracle parser schema changed")
    sampling_hash = sha256_text(
        inspect.getsource(frozen.extract_frames) + inspect.getsource(frozen.frames_for_unit)
    )
    if sampling_hash != bindings["sampling_code_hash"]:
        raise RuntimeError("Frozen oracle sampling implementation changed")
    if frozen.GENERATION_CONFIG != bindings["generation_config"]:
        raise RuntimeError("Frozen oracle generation configuration changed")
    if frozen.FRAME_CONFIG != bindings["frame_config"]:
        raise RuntimeError("Frozen oracle frame configuration changed")


def build_identity_config(
    spec: dict[str, Any],
    freeze: dict[str, Any],
) -> dict[str, Any]:
    build_identity = {
        "execution_spec_hash": spec["execution_spec_hash"],
        "selection_freeze_hash": freeze["freeze_hash"],
        "sample_sha256": sha256_file(SAMPLE),
        "query_opportunities_sha256": sha256_file(QUERY_OPPORTUNITIES),
        "physical_calls": 96,
        "query_rows": 192,
        "model_full_content_hash": spec["bindings"]["model_full_content_hash"],
        "prompt_sha256": spec["bindings"]["prompt_sha256"],
        "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
        "parser_source_hash": spec["bindings"]["parser_source_hash"],
    }
    return {
        "oracle_build_id": "mf_psvr_stage_a_oracle_" + canonical_hash(build_identity)[:20],
        "build_identity": build_identity,
        "created_at_utc": utc_now(),
        "status": "PREPARING_INPUT_IDENTITIES",
        "heldout_opened": False,
    }


def compute_model_content_validation(spec: dict[str, Any], build_id: str) -> dict[str, Any]:
    validation_started = time.perf_counter()
    runtime = load_json(ORACLE_RUNTIME)
    model_path = Path(runtime["model_path"])
    expected = runtime["model_file_identity"]
    current_paths = sorted(path for path in model_path.iterdir() if path.is_file())
    if [path.name for path in current_paths] != [row["file"] for row in expected]:
        raise RuntimeError("Frozen model file universe changed")
    rows = []
    for path, expected_row in zip(current_paths, expected):
        stat = path.stat()
        if stat.st_size != int(expected_row["size_bytes"]):
            raise RuntimeError(f"Frozen model file size changed: {path.name}")
        digest = sha256_file(path)
        if digest != expected_row["sha256"]:
            raise RuntimeError(f"Frozen model file content changed: {path.name}")
        rows.append({
            "file": path.name,
            "model_path": str(model_path),
            "sha256": digest,
            "size_bytes": stat.st_size,
        })
    full_hash = canonical_hash(rows)
    if full_hash != spec["bindings"]["model_full_content_hash"]:
        raise RuntimeError("Full frozen model content hash changed")
    value = {
        "status": "PASS",
        "oracle_build_id": build_id,
        "model_path": str(model_path),
        "files": len(rows),
        "bytes_hashed": sum(int(row["size_bytes"]) for row in rows),
        "model_full_content_hash": full_hash,
        "validation_wall_seconds": time.perf_counter() - validation_started,
        "validated_at_utc": utc_now(),
        "file_stat_identity": [
            {"file": path.name, "size_bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
            for path in current_paths
        ],
    }
    return value


def validate_model_receipt(spec: dict[str, Any], build_id: str) -> dict[str, Any]:
    if not MODEL_VALIDATION.exists():
        raise RuntimeError("Full model content validation receipt is absent")
    value = load_json(MODEL_VALIDATION)
    if (
        value["status"] != "PASS"
        or value["oracle_build_id"] != build_id
        or value["model_full_content_hash"] != spec["bindings"]["model_full_content_hash"]
    ):
        raise RuntimeError("Full model content validation receipt is detached")
    model_path = Path(value["model_path"])
    current = [
        {"file": path.name, "size_bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
        for path in sorted(model_path.iterdir())
        if path.is_file()
    ]
    if current != value["file_stat_identity"]:
        raise RuntimeError("Model file stat identity changed after full content validation")
    return value


def prepare() -> dict[str, Any]:
    spec = validate_spec()
    sample, _, freeze = validate_selection()
    validate_empty_authoritative_manifests()
    frozen = load_frozen_builder()
    validate_frozen_sources(frozen, spec)
    if PREPARATION_COMMIT.exists():
        identities, config = validate_prepared()
        return {"status": "VALID_EXISTING_PREPARATION", "identities": len(identities), **config}
    partial_paths = (BUILD_CONFIG, INPUT_IDENTITIES, MODEL_VALIDATION, ATTEMPT_LOG, RUN_STATE)
    if any(path.exists() for path in partial_paths):
        partial_events = read_jsonl(ATTEMPT_LOG) if ATTEMPT_LOG.exists() else []
        physical_evidence = (
            bool(partial_events)
            or RESOLVED_RUNTIME.exists()
            or any(RAW_DIR.glob("*.json"))
            or any(PARSED_DIR.glob("*.json"))
        )
        if physical_evidence:
            raise RuntimeError(
                "Incomplete preparation has physical-attempt evidence; automatic repair is prohibited"
            )

    preparation_started = time.perf_counter()
    identity_started = time.perf_counter()
    config = build_identity_config(spec, freeze)
    build_id = config["oracle_build_id"]
    identities = []
    content_cache: dict[tuple[str, str, str], str] = {}
    for row in sample.to_dict("records"):
        video_path = ROOT / row["local_locator"]
        session_id = str(row["session_id"])
        source_key = (str(row["source_dataset"]), session_id, str(row["local_locator"]))
        observed_sha = content_cache.get(source_key)
        if observed_sha is None:
            observed_sha = sha256_file(video_path)
            content_cache[source_key] = observed_sha
        if observed_sha != row["source_sha256"]:
            raise RuntimeError(f"Selected source video changed: {session_id}")
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open selected source video: {session_id}")
        video_fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        if video_fps <= 0 or frame_count <= 0:
            raise RuntimeError(f"Selected source metadata invalid: {session_id}")
        frozen.VIDEO = video_path
        frames = frozen.frames_for_unit(float(row["start_time"]), float(row["end_time"]), video_fps)
        frame_indices = [int(frame["decoded_index"]) for frame in frames]
        frame_contents = [str(frame["content_sha256"]) for frame in frames]
        identity = {
            "physical_call_id": row["physical_call_id"],
            "source_dataset": row["source_dataset"],
            "session_id": session_id,
            "source_sha256": observed_sha,
            "unit_id": int(row["unit_id"]),
            "unit_start_seconds": float(row["start_time"]),
            "unit_end_seconds": float(row["end_time"]),
            "anchor_id": row["anchor_id"],
            "local_locator": row["local_locator"],
            "video_fps": video_fps,
            "video_frame_count": frame_count,
            "decoded_frame_count": len(frames),
            "decoded_frame_indices": frame_indices,
            "decoded_frame_indices_sha256": canonical_hash(frame_indices),
            "decoded_frame_content_sha256": canonical_hash(frame_contents),
            "rng_seed": seed_for_call(row["physical_call_id"]),
            "oracle_build_id": build_id,
            "generation_config_hash": canonical_hash(spec["bindings"]["generation_config"]),
            "model_full_content_hash": spec["bindings"]["model_full_content_hash"],
            "prompt_sha256": spec["bindings"]["prompt_sha256"],
            "parser_schema_hash": spec["bindings"]["parser_schema_hash"],
            "parser_source_hash": spec["bindings"]["parser_source_hash"],
            "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
        }
        identity["cache_input_identity_sha256"] = canonical_hash(identity)
        identities.append(identity)
    if len(identities) != 96:
        raise RuntimeError("Stage-A input preparation did not produce 96 identities")
    identity_preparation_seconds = time.perf_counter() - identity_started
    model_validation = compute_model_content_validation(spec, build_id)
    config.update({
        "status": "PREPARED_INPUT_IDENTITIES",
        "input_identities_sha256": canonical_hash(identities),
        "input_identity_rows": len(identities),
        "decoded_frames": sum(int(row["decoded_frame_count"]) for row in identities),
        "identity_preparation_wall_seconds": identity_preparation_seconds,
        "model_content_validation_wall_seconds": model_validation["validation_wall_seconds"],
        "precommit_preparation_wall_seconds": time.perf_counter() - preparation_started,
        "prepared_at_utc": utc_now(),
    })
    atomic_jsonl(INPUT_IDENTITIES, identities)
    atomic_json(BUILD_CONFIG, config)
    atomic_json(MODEL_VALIDATION, model_validation)
    atomic_jsonl(ATTEMPT_LOG, [])
    atomic_json(RUN_STATE, {
        "status": "PREPARED_ORACLE_NOT_RUN",
        "physical_attempts_started": 0,
        "accepted_durable_calls": 0,
        "uncertain_started_calls": 0,
        "physical_oracle_calls_exact": 0,
        "heldout_opened": False,
    })
    immutable_artifacts = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in (INPUT_IDENTITIES, BUILD_CONFIG, MODEL_VALIDATION)
    }
    preparation_commit = {
        "status": "PREPARED_COMMIT",
        "oracle_build_id": build_id,
        "artifacts": immutable_artifacts,
        "attempt_log_initialized_empty_sha256": sha256_file(ATTEMPT_LOG),
        "prepared_at_utc": utc_now(),
        "heldout_opened": False,
    }
    preparation_commit["preparation_commit_hash"] = canonical_hash(preparation_commit)
    atomic_json(PREPARATION_COMMIT, preparation_commit)
    validate_prepared()
    return {"status": "PREPARED_ORACLE_NOT_RUN", "identities": len(identities), **config}


def validate_prepared() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = validate_spec()
    sample, _, freeze = validate_selection()
    if not all(path.exists() for path in (
        INPUT_IDENTITIES, BUILD_CONFIG, MODEL_VALIDATION, ATTEMPT_LOG, PREPARATION_COMMIT,
    )):
        raise RuntimeError("Stage-A oracle input preparation is incomplete")
    preparation_commit = load_json(PREPARATION_COMMIT)
    claimed_commit = preparation_commit.get("preparation_commit_hash")
    commit_payload = {
        key: value for key, value in preparation_commit.items()
        if key != "preparation_commit_hash"
    }
    if (
        preparation_commit.get("status") != "PREPARED_COMMIT"
        or claimed_commit != canonical_hash(commit_payload)
    ):
        raise RuntimeError("Stage-A preparation commit is invalid")
    expected_immutable = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in (INPUT_IDENTITIES, BUILD_CONFIG, MODEL_VALIDATION)
    }
    if preparation_commit.get("artifacts") != expected_immutable:
        raise RuntimeError("Stage-A immutable preparation artifact changed")
    identities = read_jsonl(INPUT_IDENTITIES)
    config = load_json(BUILD_CONFIG)
    expected_config = build_identity_config(spec, freeze)
    expected_build_id = expected_config["oracle_build_id"]
    if (
        config["oracle_build_id"] != expected_build_id
        or config.get("build_identity") != expected_config["build_identity"]
        or config.get("status") != "PREPARED_INPUT_IDENTITIES"
        or int(config.get("input_identity_rows", -1)) != 96
        or len(identities) != 96
    ):
        raise RuntimeError("Stage-A oracle preparation build identity changed")
    if preparation_commit["oracle_build_id"] != expected_build_id:
        raise RuntimeError("Stage-A preparation commit has the wrong build identity")
    if config["input_identities_sha256"] != canonical_hash(identities):
        raise RuntimeError("Stage-A input identity manifest changed")
    sample_by_call = sample.set_index("physical_call_id").to_dict("index")
    for ordinal, identity in enumerate(identities, start=1):
        if identity["physical_call_id"] != f"mf_psvr_stage_a_{ordinal:03d}":
            raise RuntimeError("Stage-A prepared call ordering changed")
        selected = sample_by_call[identity["physical_call_id"]]
        claimed = identity["cache_input_identity_sha256"]
        payload = {key: value for key, value in identity.items() if key != "cache_input_identity_sha256"}
        if (
            claimed != canonical_hash(payload)
            or identity["rng_seed"] != seed_for_call(identity["physical_call_id"])
            or identity["source_dataset"] != selected["source_dataset"]
            or identity["session_id"] != selected["session_id"]
            or identity["source_sha256"] != selected["source_sha256"]
            or int(identity["unit_id"]) != int(selected["unit_id"])
            or float(identity["unit_start_seconds"]) != float(selected["start_time"])
            or float(identity["unit_end_seconds"]) != float(selected["end_time"])
            or identity["anchor_id"] != selected["anchor_id"]
            or identity["local_locator"] != selected["local_locator"]
            or int(identity["decoded_frame_count"]) != len(identity["decoded_frame_indices"])
            or identity["decoded_frame_indices_sha256"]
            != canonical_hash(identity["decoded_frame_indices"])
            or identity["oracle_build_id"] != expected_build_id
            or identity["generation_config_hash"]
            != canonical_hash(spec["bindings"]["generation_config"])
            or identity["model_full_content_hash"] != spec["bindings"]["model_full_content_hash"]
            or identity["prompt_sha256"] != spec["bindings"]["prompt_sha256"]
            or identity["parser_schema_hash"] != spec["bindings"]["parser_schema_hash"]
            or identity["parser_source_hash"] != spec["bindings"]["parser_source_hash"]
            or identity["sampling_code_hash"] != spec["bindings"]["sampling_code_hash"]
        ):
            raise RuntimeError("Stage-A prepared input identity does not recompute")
    events = read_jsonl(ATTEMPT_LOG)
    validate_attempt_events(events)
    if not events and sha256_file(ATTEMPT_LOG) != preparation_commit["attempt_log_initialized_empty_sha256"]:
        raise RuntimeError("Stage-A empty attempt-log initialization changed")
    validate_model_receipt(spec, expected_build_id)
    return identities, config


def read_events() -> list[dict[str, Any]]:
    events = read_jsonl(ATTEMPT_LOG)
    validate_attempt_events(events)
    return events


def append_event(event: dict[str, Any]) -> dict[str, Any]:
    events = read_events()
    record = append_hash_chain(events, event)
    atomic_jsonl(ATTEMPT_LOG, [*events, record])
    return record


def raw_path(identity: dict[str, Any]) -> Path:
    return RAW_DIR / f"{identity['physical_call_id']}.json"


def parsed_path(identity: dict[str, Any]) -> Path:
    return PARSED_DIR / f"{identity['physical_call_id']}.json"


def final_artifact_paths(
    identities: list[dict[str, Any]],
    spec: dict[str, Any],
) -> list[Path]:
    fixed = [
        EXECUTION_SPEC,
        SAMPLE,
        QUERY_OPPORTUNITIES,
        SELECTION_FREEZE,
        INPUT_IDENTITIES,
        BUILD_CONFIG,
        PREPARATION_COMMIT,
        MODEL_VALIDATION,
        RESOLVED_RUNTIME,
        ATTEMPT_LOG,
        RUN_STATE,
        CALL_MANIFEST,
        LABEL_MANIFEST,
        SUPPORT_REPORT,
        EVENT_GROUPS,
        PHYSICAL_COST,
        STAGE_STATE,
        SELECTION_STATE,
        PREINFERENCE_AUDIT_COPY,
        AUDIT_MANIFEST,
        PROTOCOL,
        PROXY_CONFIG,
        ORACLE_CONFIG,
        ORACLE_RUNTIME,
        UNIT_MANIFEST,
        UNIT_SCORES,
        CANDIDATE_PLAN,
        CANDIDATE_STATE,
        CORE_SOURCE,
        PROJECTION_SOURCE,
        SELECTOR_SOURCE,
        FREEZER_SOURCE,
        FROZEN_BUILDER,
        Path(__file__),
        Path(spec["bindings"]["prompt_path"]),
    ]
    paths = [*fixed]
    paths.extend(raw_path(identity) for identity in identities)
    paths.extend(parsed_path(identity) for identity in identities)
    unique = {path.resolve(): path for path in paths}
    ordered = sorted(unique.values(), key=lambda path: str(path.relative_to(ROOT)))
    missing = [path for path in ordered if not path.is_file()]
    if missing:
        raise RuntimeError(f"Stage-A final artifact is absent: {missing[0]}")
    return ordered


def runtime_hash() -> str | None:
    if not RESOLVED_RUNTIME.exists():
        return None
    value = load_json(RESOLVED_RUNTIME)
    claimed = value.get("resolved_inference_runtime_sha256")
    payload = {key: item for key, item in value.items() if key != "resolved_inference_runtime_sha256"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("Resolved inference runtime self-hash is invalid")
    return str(claimed)


def validate_raw(path: Path, identity: dict[str, Any], spec: dict[str, Any]) -> bool:
    try:
        record = load_json(path)
        resolved_hash = runtime_hash()
    except Exception:
        return False
    raw = record.get("raw")
    rng = record.get("rng_identity", {})
    model_input = record.get("model_input_manifest", {})
    expected_attempt_id = (
        f"{identity['oracle_build_id']}__{identity['physical_call_id']}__a001"
    )
    runtime_seconds = record.get("generation_runtime_seconds")
    model_load_seconds = record.get("model_load_seconds")
    timestamps = record.get("decoded_frame_timestamps_seconds", [])
    return bool(
        record.get("physical_call_id") == identity["physical_call_id"]
        and record.get("attempt_id") == expected_attempt_id
        and record.get("oracle_build_id") == identity["oracle_build_id"]
        and record.get("cache_input_identity_sha256") == identity["cache_input_identity_sha256"]
        and record.get("decoded_frame_indices") == identity["decoded_frame_indices"]
        and canonical_hash(record.get("per_frame_content_sha256", []))
        == identity["decoded_frame_content_sha256"]
        and record.get("generation_config") == spec["bindings"]["generation_config"]
        and record.get("physical_vlm_call") is True
        and record.get("rng_seed") == identity["rng_seed"]
        and resolved_hash is not None
        and record.get("resolved_inference_runtime_sha256") == resolved_hash
        and model_input.get("model_input_identity_sha256") == canonical_hash({
            key: value for key, value in model_input.items() if key != "model_input_identity_sha256"
        })
        and rng.get("rng_state_identity_sha256") == canonical_hash({
            key: value for key, value in rng.items() if key != "rng_state_identity_sha256"
        })
        and rng.get("numpy_seed") == identity["rng_seed"]
        and rng.get("python_seed") == identity["rng_seed"]
        and rng.get("torch_seed") == identity["rng_seed"]
        and rng.get("torch_cuda_seed_all") == identity["rng_seed"]
        and rng.get("torch_initial_seed") == identity["rng_seed"]
        and rng.get("deterministic_algorithms_enabled") is True
        and rng.get("warn_only") is False
        and rng.get("cublas_workspace_config") == ":4096:8"
        and record.get("unit_id") == identity["unit_id"]
        and record.get("unit_start_seconds") == identity["unit_start_seconds"]
        and record.get("unit_end_seconds") == identity["unit_end_seconds"]
        and record.get("source_sha256") == identity["source_sha256"]
        and len(record.get("per_frame_content_sha256", [])) == identity["decoded_frame_count"]
        and len(timestamps) == identity["decoded_frame_count"]
        and all(isinstance(value, (int, float)) and math.isfinite(value) for value in timestamps)
        and isinstance(runtime_seconds, (int, float))
        and not isinstance(runtime_seconds, bool)
        and math.isfinite(runtime_seconds)
        and runtime_seconds >= 0
        and isinstance(model_load_seconds, (int, float))
        and not isinstance(model_load_seconds, bool)
        and math.isfinite(model_load_seconds)
        and model_load_seconds >= 0
        and record.get("model_loaded_this_invocation") is (model_load_seconds > 0)
        and isinstance(record.get("call_started_at_utc"), str)
        and isinstance(record.get("call_completed_at_utc"), str)
        and isinstance(raw, str) and raw.strip()
        and record.get("raw_response_sha256") == sha256_text(raw)
    )


def raw_links_started_event(
    path: Path,
    identity: dict[str, Any],
    spec: dict[str, Any],
    started: dict[str, Any],
) -> bool:
    if not validate_raw(path, identity, spec):
        return False
    try:
        record = load_json(path)
    except Exception:
        return False
    return bool(
        started.get("event") == "STARTED"
        and started.get("attempt_id") == record.get("attempt_id")
        and started.get("physical_call_id") == identity["physical_call_id"]
        and started.get("cache_input_identity_sha256")
        == record.get("cache_input_identity_sha256")
        and started.get("model_input_identity_sha256")
        == record.get("model_input_manifest", {}).get("model_input_identity_sha256")
        and started.get("resolved_inference_runtime_sha256")
        == record.get("resolved_inference_runtime_sha256")
        and started.get("rng_state_identity_sha256")
        == record.get("rng_identity", {}).get("rng_state_identity_sha256")
        and started.get("timestamp") == record.get("call_started_at_utc")
    )


def reconcile_attempts(identities: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    events = read_events()
    terminals = {
        event["attempt_id"] for event in events
        if event["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}
    }
    by_call = {identity["physical_call_id"]: identity for identity in identities}
    for event in list(events):
        if event["event"] != "STARTED" or event["attempt_id"] in terminals:
            continue
        if event["physical_call_id"] not in by_call:
            raise RuntimeError("Attempt log references a call outside the frozen sample")
        identity = by_call[event["physical_call_id"]]
        path = raw_path(identity)
        accepted = raw_links_started_event(path, identity, spec, event)
        raw_record = load_json(path) if accepted else {}
        append_event({
            "event": "RECOVERED_ACCEPTED" if accepted else "RECOVERED_UNCERTAIN",
            "attempt_id": event["attempt_id"],
            "physical_call_id": event["physical_call_id"],
            "timestamp": utc_now(),
            "reason": "durable_exact_raw_found" if accepted else "no_durable_exact_raw_at_recovery",
            **({
                "raw_envelope_sha256": sha256_file(path),
                "raw_response_sha256": raw_record["raw_response_sha256"],
            } if accepted else {}),
        })
    summary = validate_attempt_events(read_events())
    if summary["unresolved_attempt_ids"]:
        raise RuntimeError("Stage-A attempt reconciliation left unresolved events")
    if summary["uncertain_started_calls"]:
        atomic_json(RUN_STATE, {
            "status": "BLOCKED_UNCERTAIN_PHYSICAL_CALL_COUNT_NO_RETRY",
            **summary,
            "physical_oracle_calls_exact": None,
            "heldout_opened": False,
        })
        raise RuntimeError(
            "An uncertain started call has no durable raw output; retry is prohibited without amendment"
        )
    return summary


def verified_accepted_calls(identities: list[dict[str, Any]], spec: dict[str, Any]) -> set[str]:
    events = read_events()
    by_call = {identity["physical_call_id"]: identity for identity in identities}
    started_by_attempt = {
        event["attempt_id"]: event for event in events if event["event"] == "STARTED"
    }
    accepted_terminals = [
        event for event in events if event["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED"}
    ]
    accepted: set[str] = set()
    for terminal in accepted_terminals:
        call_id = terminal["physical_call_id"]
        if call_id not in by_call:
            raise RuntimeError("Accepted attempt references a call outside the frozen sample")
        identity = by_call[call_id]
        path = raw_path(identity)
        started = started_by_attempt[terminal["attempt_id"]]
        if not raw_links_started_event(path, identity, spec, started):
            raise RuntimeError("Accepted Stage-A raw envelope is detached from its STARTED event")
        record = load_json(path)
        if (
            terminal.get("raw_envelope_sha256") != sha256_file(path)
            or terminal.get("raw_response_sha256") != record["raw_response_sha256"]
        ):
            raise RuntimeError("Accepted Stage-A terminal event has invalid raw-output hashes")
        accepted.add(call_id)
    for identity in identities:
        path = raw_path(identity)
        if path.exists() and identity["physical_call_id"] not in accepted:
            raise RuntimeError("Unlinked or invalid Stage-A raw output exists; refusing overwrite")
    observed_raw_paths = set(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else set()
    expected_raw_paths = {raw_path(by_call[call_id]) for call_id in accepted}
    if observed_raw_paths != expected_raw_paths:
        raise RuntimeError("Stage-A raw-output file universe contains an unaccounted artifact")
    return accepted


def infer(limit: int | None) -> dict[str, Any]:
    spec = validate_spec()
    identities, config = validate_prepared()
    frozen = load_frozen_builder()
    validate_frozen_sources(frozen, spec)
    validate_model_receipt(spec, config["oracle_build_id"])
    summary = reconcile_attempts(identities, spec)
    accepted = verified_accepted_calls(identities, spec)
    if len(accepted) == 96:
        return {"status": "ALL_VALID_EXISTING_RAW", **summary}

    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    model_path = Path(spec["bindings"]["model_path"])
    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    model.eval()
    load_seconds = time.perf_counter() - load_started
    resolved = frozen.resolved_inference_runtime(model, processor)
    if RESOLVED_RUNTIME.exists():
        if load_json(RESOLVED_RUNTIME) != resolved:
            raise RuntimeError("Resolved model/processor runtime changed across resume")
    else:
        atomic_json(RESOLVED_RUNTIME, resolved)

    new_calls = 0
    prompt_text_source = Path(spec["bindings"]["prompt_path"]).read_text(encoding="utf-8")
    for identity in identities:
        call_id = identity["physical_call_id"]
        if call_id in accepted:
            continue
        if limit is not None and new_calls >= limit:
            break
        video_path = ROOT / identity["local_locator"]
        frozen.VIDEO = video_path
        frames = frozen.frames_for_unit(
            identity["unit_start_seconds"], identity["unit_end_seconds"], identity["video_fps"]
        )
        indices = [int(frame["decoded_index"]) for frame in frames]
        contents = [str(frame["content_sha256"]) for frame in frames]
        if (
            canonical_hash(indices) != identity["decoded_frame_indices_sha256"]
            or canonical_hash(contents) != identity["decoded_frame_content_sha256"]
        ):
            raise RuntimeError(f"Prepared frame identity changed before {call_id}")

        pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
        messages = [{"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": spec["bindings"]["frame_config"]["message_fps"]},
            {"type": "text", "text": prompt_text_source},
        ]}]
        prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[prompt_text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        ).to(model.device)
        input_manifest = frozen.model_input_manifest(inputs, prompt_text, torch)
        torch.cuda.reset_peak_memory_stats()
        rng_record = frozen.configure_rng(identity["rng_seed"], torch)
        attempt_id = f"{config['oracle_build_id']}__{call_id}__a001"
        started_at_utc = utc_now()
        append_event({
            "event": "STARTED",
            "attempt_id": attempt_id,
            "physical_call_id": call_id,
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "model_input_identity_sha256": input_manifest["model_input_identity_sha256"],
            "resolved_inference_runtime_sha256": resolved["resolved_inference_runtime_sha256"],
            "rng_state_identity_sha256": rng_record["rng_state_identity_sha256"],
            "timestamp": started_at_utc,
        })
        started = time.perf_counter()
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=spec["bindings"]["generation_config"]["max_new_tokens"],
            )
        torch.cuda.synchronize()
        runtime_seconds = time.perf_counter() - started
        trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated_ids)]
        raw_text = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        record = {
            "physical_call_id": call_id,
            "attempt_id": attempt_id,
            "oracle_build_id": config["oracle_build_id"],
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "source_sha256": identity["source_sha256"],
            "unit_id": identity["unit_id"],
            "unit_start_seconds": identity["unit_start_seconds"],
            "unit_end_seconds": identity["unit_end_seconds"],
            "decoded_frame_indices": indices,
            "decoded_frame_timestamps_seconds": [
                round(float(frame["decoded_timestamp_seconds"]), 9) for frame in frames
            ],
            "per_frame_content_sha256": contents,
            "generation_config": spec["bindings"]["generation_config"],
            "generation_runtime_seconds": runtime_seconds,
            "model_load_seconds": load_seconds if new_calls == 0 else 0.0,
            "model_loaded_this_invocation": new_calls == 0,
            "model_input_manifest": input_manifest,
            "resolved_inference_runtime_sha256": resolved["resolved_inference_runtime_sha256"],
            "rng_identity": rng_record,
            "rng_seed": identity["rng_seed"],
            "physical_vlm_call": True,
            "peak_gpu_memory_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_gpu_memory_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "call_started_at_utc": started_at_utc,
            "call_completed_at_utc": utc_now(),
            "raw": raw_text,
            "raw_response_sha256": sha256_text(raw_text),
        }
        output_path = raw_path(identity)
        atomic_json(output_path, record)
        if not validate_raw(output_path, identity, spec):
            raise RuntimeError(f"Durable raw validation failed for {call_id}")
        append_event({
            "event": "ACCEPTED",
            "attempt_id": attempt_id,
            "physical_call_id": call_id,
            "raw_envelope_sha256": sha256_file(output_path),
            "raw_response_sha256": record["raw_response_sha256"],
            "timestamp": utc_now(),
        })
        accepted.add(call_id)
        new_calls += 1
        summary = validate_attempt_events(read_events())
        atomic_json(RUN_STATE, {
            "status": "INFERENCE_COMPLETE" if len(accepted) == 96 else "INFERENCE_IN_PROGRESS",
            **summary,
            "physical_oracle_calls_exact": summary["accepted_durable_calls"],
            "heldout_opened": False,
        })
        print(json.dumps({
            "physical_call_id": call_id,
            "accepted_durable_calls": len(accepted),
            "generation_runtime_seconds": runtime_seconds,
        }, sort_keys=True), flush=True)
    summary = validate_attempt_events(read_events())
    return {"status": "INFERENCE_COMPLETE" if len(accepted) == 96 else "INFERENCE_IN_PROGRESS", **summary}


def finalize() -> dict[str, Any]:
    if COMPLETE_MARKER.exists():
        return verify()
    spec = validate_spec()
    identities, config = validate_prepared()
    sample, opportunities, _ = validate_selection()
    frozen = load_frozen_builder()
    validate_frozen_sources(frozen, spec)
    summary = reconcile_attempts(identities, spec)
    accepted = verified_accepted_calls(identities, spec)
    if len(accepted) != 96 or summary["accepted_durable_calls"] != 96:
        raise RuntimeError("Cannot finalize before all 96 frozen physical calls are durable")
    ensure_preinference_audit_copy(spec)

    sample_by_call = sample.set_index("physical_call_id").to_dict("index")
    opportunity_by_key = opportunities.set_index(
        ["physical_call_id", "query_id"]
    ).to_dict("index")
    identity_by_call = {row["physical_call_id"]: row for row in identities}
    call_fields = next(csv.reader(CALL_MANIFEST.open(newline="", encoding="utf-8")))
    label_fields = next(csv.reader(LABEL_MANIFEST.open(newline="", encoding="utf-8")))
    call_rows = []
    label_rows = []
    for call_id in [f"mf_psvr_stage_a_{index:03d}" for index in range(1, 97)]:
        selected = sample_by_call[call_id]
        identity = identity_by_call[call_id]
        raw_file = raw_path(identity)
        raw = load_json(raw_file)
        parsed, parse_status = frozen.parse_response(raw["raw"])
        generic_label = str(parsed.get("label", "")).lower() if parse_status == "ok" else ""
        actor = str(parsed.get("involved_object", "none")).lower() if parse_status == "ok" else ""
        confidence = str(parsed.get("confidence", "")).lower() if parse_status == "ok" else ""
        parsed_record = {
            "physical_call_id": call_id,
            "oracle_build_id": config["oracle_build_id"],
            "parse_status": parse_status,
            "parsed": parsed,
            "parsed_sha256": canonical_hash(parsed),
            "raw_envelope_sha256": sha256_file(raw_file),
            "raw_response_sha256": raw["raw_response_sha256"],
        }
        parsed_file = parsed_path(identity)
        atomic_json(parsed_file, parsed_record)
        raw_relative = str(raw_file.relative_to(ROOT))
        call_rows.append({
            "physical_call_id": call_id,
            "source_dataset": selected["source_dataset"],
            "session_id": selected["session_id"],
            "source_sha256": selected["source_sha256"],
            "model_split_role": selected["model_split_role"],
            "unit_id": int(selected["unit_id"]),
            "unit_start_seconds": float(selected["start_time"]),
            "unit_end_seconds": float(selected["end_time"]),
            "anchor_id": selected["anchor_id"],
            "selection_stage": "STAGE_A_SUPPORT_PILOT",
            "sampling_stratum": selected["sampling_stratum"],
            "raw_response_path": raw_relative,
            "raw_response_sha256": raw["raw_response_sha256"],
            "oracle_generic_label": generic_label,
            "oracle_generic_involved_object": actor,
            "confidence": confidence,
            "parse_status": parse_status,
            "physical_call": True,
            "generation_runtime_seconds": raw["generation_runtime_seconds"],
            "model_hash": spec["bindings"]["model_full_content_hash"],
            "prompt_hash": spec["bindings"]["prompt_sha256"],
            "parser_schema_hash": spec["bindings"]["parser_schema_hash"],
            "parser_source_hash": spec["bindings"]["parser_source_hash"],
            "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
            "call_status": "VALID" if parse_status == "ok" else "INVALID_PARSE_RETAINED_NO_RETRY",
            "notes": "One charged generic call; Q1/Q2 projections are separate label rows.",
        })
        for query_id in ("Q1", "Q2"):
            opportunity = opportunity_by_key[(call_id, query_id)]
            query_label = projected_label(generic_label, actor, query_id, parse_status)
            label_rows.append({
                "label_row_id": f"{call_id}__{query_id}",
                "physical_call_id": call_id,
                "source_dataset": selected["source_dataset"],
                "session_id": selected["session_id"],
                "source_sha256": selected["source_sha256"],
                "model_split_role": selected["model_split_role"],
                "unit_id": int(selected["unit_id"]),
                "unit_start_seconds": float(selected["start_time"]),
                "unit_end_seconds": float(selected["end_time"]),
                "anchor_id": selected["anchor_id"],
                "selection_stage": "STAGE_A_SUPPORT_PILOT",
                "sampling_stratum": selected["sampling_stratum"],
                "query_id": query_id,
                "verification_key": opportunity["verification_key"],
                "witness_track_id": opportunity["witness_track_id"],
                "projected_label": query_label,
                "projection_actor_set": "|".join(sorted(spec["projection_policy"][query_id])),
                "oracle_generic_label": generic_label,
                "oracle_generic_involved_object": actor,
                "raw_response_path": raw_relative,
                "raw_response_sha256": raw["raw_response_sha256"],
                "confidence": confidence,
                "parse_status": parse_status,
                "model_hash": spec["bindings"]["model_full_content_hash"],
                "prompt_hash": spec["bindings"]["prompt_sha256"],
                "parser_schema_hash": spec["bindings"]["parser_schema_hash"],
                "parser_source_hash": spec["bindings"]["parser_source_hash"],
                "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
                "label_status": "VALID" if parse_status == "ok" else "INVALID_PARSE_RETAINED_NO_RETRY",
                "notes": "Unit outcome; track ID is a pre-label scheduling witness only.",
            })
    atomic_csv(CALL_MANIFEST, call_rows, call_fields)
    atomic_csv(LABEL_MANIFEST, label_rows, label_fields)
    labels = pd.read_csv(LABEL_MANIFEST, keep_default_na=False)
    scores = pd.read_csv(UNIT_SCORES, keep_default_na=False)
    support = evaluate_support_gates(labels, scores, load_json(PROTOCOL))
    support.update({
        "status": "EVALUATED_FROZEN_STAGE_A",
        "oracle_build_id": config["oracle_build_id"],
        "physical_attempt_accounting": summary,
        "call_manifest_sha256": sha256_file(CALL_MANIFEST),
        "label_manifest_sha256": sha256_file(LABEL_MANIFEST),
    })
    atomic_json(SUPPORT_REPORT, support)
    groups = k3_bridge_safe_groups(labels)
    group_fields = list(groups[0]) if groups else [
        "event_group_id", "source_dataset", "session_id", "query_id", "unit_ids",
        "unit_count", "start_seconds", "end_seconds",
    ]
    for row in groups:
        row["unit_ids"] = "|".join(map(str, row["unit_ids"]))
    atomic_csv(EVENT_GROUPS, groups, group_fields)
    state_status = (
        "STAGE_A_FAIL_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE"
        if support["decision"].startswith("STOP_")
        else "STAGE_A_PASS_STAGE_B_UNAUTHORIZED"
    )
    atomic_json(STAGE_STATE, {
        "stage": "cycle_01_training_pool",
        "status": state_status,
        "cycle_complete": False,
        "candidate_pipeline_run": True,
        "physical_oracle_calls": 96,
        "frozen_oracle_labels": sum(row["label_status"] == "VALID" for row in label_rows),
        "Q1_support": support["per_query"]["Q1"]["support_existence_pass"],
        "Q2_support": support["per_query"]["Q2"]["support_existence_pass"],
        "stage_b_authorized": False,
        "heldout_opened": False,
        "next_high_information_action": (
            "Acquire a directly licensed query-enriched source."
            if support["decision"].startswith("STOP_")
            else "Review Stage-A coverage; Stage B requires separate explicit authority."
        ),
    })
    atomic_json(SELECTION_STATE, {
        "status": state_status,
        "physical_oracle_calls": 96,
        "projected_labels": len(label_rows),
        "support_decision": support["decision"],
        "heldout_opened": False,
    })
    atomic_json(RUN_STATE, {
        "status": "FINALIZED_OUTPUTS_COMMITTED",
        **summary,
        "physical_oracle_calls_exact": summary["accepted_durable_calls"],
        "parse_failures": sum(row["parse_status"] != "ok" for row in call_rows),
        "support_decision": support["decision"],
        "heldout_opened": False,
    })
    artifacts = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in final_artifact_paths(identities, spec)
    }
    marker = {
        "status": "COMPLETE_COMMIT",
        "oracle_build_id": config["oracle_build_id"],
        "physical_attempts_started": summary["physical_attempts_started"],
        "accepted_durable_calls": summary["accepted_durable_calls"],
        "uncertain_started_calls": summary["uncertain_started_calls"],
        "parse_failures": sum(row["parse_status"] != "ok" for row in call_rows),
        "support_decision": support["decision"],
        "artifacts": artifacts,
        "committed_at_utc": utc_now(),
        "heldout_opened": False,
    }
    marker["complete_hash"] = canonical_hash(marker)
    atomic_json(COMPLETE_MARKER, marker)
    return marker


def _optional_int_text(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return str(int(float(value)))


def validate_finalized_outputs(
    identities: list[dict[str, Any]],
    config: dict[str, Any],
    spec: dict[str, Any],
    sample: pd.DataFrame,
    opportunities: pd.DataFrame,
    calls: pd.DataFrame,
    labels: pd.DataFrame,
    frozen: Any,
) -> int:
    expected_calls = [f"mf_psvr_stage_a_{ordinal:03d}" for ordinal in range(1, 97)]
    expected_parsed_paths = {parsed_path(identity) for identity in identities}
    observed_parsed_paths = set(PARSED_DIR.glob("*.json")) if PARSED_DIR.exists() else set()
    if observed_parsed_paths != expected_parsed_paths:
        raise RuntimeError("Stage-A parsed-output file universe is incomplete or contains extras")
    if calls["physical_call_id"].tolist() != expected_calls:
        raise RuntimeError("Final call manifest ordering/identity changed")
    expected_label_ids = [
        f"{call_id}__{query_id}"
        for call_id in expected_calls
        for query_id in ("Q1", "Q2")
    ]
    if labels["label_row_id"].tolist() != expected_label_ids:
        raise RuntimeError("Final query-label manifest ordering/identity changed")

    by_identity = {row["physical_call_id"]: row for row in identities}
    by_sample = sample.set_index("physical_call_id").to_dict("index")
    by_opportunity = opportunities.set_index(["physical_call_id", "query_id"]).to_dict("index")
    by_call = calls.set_index("physical_call_id").to_dict("index")
    by_label = labels.set_index(["physical_call_id", "query_id"]).to_dict("index")
    parse_failures = 0
    for call_id in expected_calls:
        identity = by_identity[call_id]
        selected = by_sample[call_id]
        raw_file = raw_path(identity)
        raw = load_json(raw_file)
        parsed, parse_status = frozen.parse_response(raw["raw"])
        generic_label = str(parsed.get("label", "")).lower() if parse_status == "ok" else ""
        actor = str(parsed.get("involved_object", "none")).lower() if parse_status == "ok" else ""
        confidence = str(parsed.get("confidence", "")).lower() if parse_status == "ok" else ""
        parse_failures += parse_status != "ok"
        expected_parsed = {
            "physical_call_id": call_id,
            "oracle_build_id": config["oracle_build_id"],
            "parse_status": parse_status,
            "parsed": parsed,
            "parsed_sha256": canonical_hash(parsed),
            "raw_envelope_sha256": sha256_file(raw_file),
            "raw_response_sha256": raw["raw_response_sha256"],
        }
        if load_json(parsed_path(identity)) != expected_parsed:
            raise RuntimeError(f"Parsed artifact does not recompute for {call_id}")

        raw_relative = str(raw_file.relative_to(ROOT))
        call = by_call[call_id]
        call_text = {
            "source_dataset": selected["source_dataset"],
            "session_id": selected["session_id"],
            "source_sha256": selected["source_sha256"],
            "model_split_role": selected["model_split_role"],
            "anchor_id": selected["anchor_id"],
            "selection_stage": "STAGE_A_SUPPORT_PILOT",
            "sampling_stratum": selected["sampling_stratum"],
            "raw_response_path": raw_relative,
            "raw_response_sha256": raw["raw_response_sha256"],
            "oracle_generic_label": generic_label,
            "oracle_generic_involved_object": actor,
            "confidence": confidence,
            "parse_status": parse_status,
            "model_hash": spec["bindings"]["model_full_content_hash"],
            "prompt_hash": spec["bindings"]["prompt_sha256"],
            "parser_schema_hash": spec["bindings"]["parser_schema_hash"],
            "parser_source_hash": spec["bindings"]["parser_source_hash"],
            "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
            "call_status": "VALID" if parse_status == "ok" else "INVALID_PARSE_RETAINED_NO_RETRY",
        }
        if any(str(call[key]) != str(value) for key, value in call_text.items()):
            raise RuntimeError(f"Call manifest does not recompute for {call_id}")
        if (
            int(call["unit_id"]) != int(selected["unit_id"])
            or float(call["unit_start_seconds"]) != float(selected["start_time"])
            or float(call["unit_end_seconds"]) != float(selected["end_time"])
            or float(call["generation_runtime_seconds"]) != float(raw["generation_runtime_seconds"])
            or str(call["physical_call"]).lower() != "true"
        ):
            raise RuntimeError(f"Call manifest numeric/physical fields changed for {call_id}")

        for query_id in ("Q1", "Q2"):
            opportunity = by_opportunity[(call_id, query_id)]
            label = by_label[(call_id, query_id)]
            query_label = projected_label(generic_label, actor, query_id, parse_status)
            label_text = {
                "label_row_id": f"{call_id}__{query_id}",
                "source_dataset": selected["source_dataset"],
                "session_id": selected["session_id"],
                "source_sha256": selected["source_sha256"],
                "model_split_role": selected["model_split_role"],
                "anchor_id": selected["anchor_id"],
                "selection_stage": "STAGE_A_SUPPORT_PILOT",
                "sampling_stratum": selected["sampling_stratum"],
                "verification_key": opportunity["verification_key"],
                "projected_label": query_label,
                "projection_actor_set": "|".join(sorted(spec["projection_policy"][query_id])),
                "oracle_generic_label": generic_label,
                "oracle_generic_involved_object": actor,
                "raw_response_path": raw_relative,
                "raw_response_sha256": raw["raw_response_sha256"],
                "confidence": confidence,
                "parse_status": parse_status,
                "model_hash": spec["bindings"]["model_full_content_hash"],
                "prompt_hash": spec["bindings"]["prompt_sha256"],
                "parser_schema_hash": spec["bindings"]["parser_schema_hash"],
                "parser_source_hash": spec["bindings"]["parser_source_hash"],
                "sampling_code_hash": spec["bindings"]["sampling_code_hash"],
                "label_status": "VALID" if parse_status == "ok" else "INVALID_PARSE_RETAINED_NO_RETRY",
            }
            if any(str(label[key]) != str(value) for key, value in label_text.items()):
                raise RuntimeError(f"Label manifest does not recompute for {call_id}/{query_id}")
            if (
                int(label["unit_id"]) != int(selected["unit_id"])
                or float(label["unit_start_seconds"]) != float(selected["start_time"])
                or float(label["unit_end_seconds"]) != float(selected["end_time"])
                or _optional_int_text(label["witness_track_id"])
                != _optional_int_text(opportunity["witness_track_id"])
            ):
                raise RuntimeError(f"Label manifest numeric/witness fields changed for {call_id}/{query_id}")
    return parse_failures


def validate_event_groups(labels: pd.DataFrame) -> None:
    expected = k3_bridge_safe_groups(labels)
    for row in expected:
        row["unit_ids"] = "|".join(map(str, row["unit_ids"]))
    observed_frame = pd.read_csv(EVENT_GROUPS, keep_default_na=False)
    observed = []
    for row in observed_frame.to_dict("records"):
        observed.append({
            "event_group_id": str(row["event_group_id"]),
            "source_dataset": str(row["source_dataset"]),
            "session_id": str(row["session_id"]),
            "query_id": str(row["query_id"]),
            "unit_ids": str(row["unit_ids"]),
            "unit_count": int(row["unit_count"]),
            "start_seconds": float(row["start_seconds"]),
            "end_seconds": float(row["end_seconds"]),
        })
    if observed != expected:
        raise RuntimeError("Stage-A K3 event-group artifact does not recompute")


def verify() -> dict[str, Any]:
    if not COMPLETE_MARKER.exists():
        raise RuntimeError("Stage-A oracle COMPLETE marker is absent")
    marker = load_json(COMPLETE_MARKER)
    claimed = marker["complete_hash"]
    payload = {key: value for key, value in marker.items() if key != "complete_hash"}
    if claimed != canonical_hash(payload) or marker["status"] != "COMPLETE_COMMIT":
        raise RuntimeError("Stage-A oracle COMPLETE marker is invalid")
    for relative, digest in marker["artifacts"].items():
        path = ROOT / relative
        if not path.exists() or sha256_file(path) != digest:
            raise RuntimeError(f"Committed Stage-A artifact changed: {relative}")
    spec = validate_spec()
    identities, config = validate_prepared()
    expected_artifact_keys = {
        str(path.relative_to(ROOT)) for path in final_artifact_paths(identities, spec)
    }
    if set(marker["artifacts"]) != expected_artifact_keys:
        raise RuntimeError("Stage-A completion marker artifact universe is incomplete")
    summary = reconcile_attempts(identities, spec)
    accepted = verified_accepted_calls(identities, spec)
    sample, opportunities, _ = validate_selection()
    calls = pd.read_csv(CALL_MANIFEST, keep_default_na=False)
    labels = pd.read_csv(LABEL_MANIFEST, keep_default_na=False)
    frozen = load_frozen_builder()
    validate_frozen_sources(frozen, spec)
    parse_failures = validate_finalized_outputs(
        identities, config, spec, sample, opportunities, calls, labels, frozen
    )
    validate_event_groups(labels)
    support = evaluate_support_gates(
        labels,
        pd.read_csv(UNIT_SCORES, keep_default_na=False),
        load_json(PROTOCOL),
    )
    stored_support = load_json(SUPPORT_REPORT)
    for key in (
        "decision", "support_existence_all_queries_pass",
        "frozen_evaluation_splits_all_queries_pass", "model_train_initial_all_queries_pass",
        "per_query", "physical_call_ids", "query_verification_keys", "label_domain_counts",
    ):
        if stored_support[key] != support[key]:
            raise RuntimeError(f"Stage-A support report does not recompute: {key}")
    if (
        stored_support.get("oracle_build_id") != config["oracle_build_id"]
        or stored_support.get("physical_attempt_accounting") != summary
        or stored_support.get("call_manifest_sha256") != sha256_file(CALL_MANIFEST)
        or stored_support.get("label_manifest_sha256") != sha256_file(LABEL_MANIFEST)
    ):
        raise RuntimeError("Stage-A support report provenance/accounting changed")
    if len(calls) != 96 or len(labels) != 192 or len(accepted) != 96:
        raise RuntimeError("Stage-A finalized row/call counts changed")
    if (
        marker["oracle_build_id"] != config["oracle_build_id"]
        or marker["physical_attempts_started"] != summary["physical_attempts_started"]
        or marker["accepted_durable_calls"] != summary["accepted_durable_calls"]
        or marker["uncertain_started_calls"] != summary["uncertain_started_calls"]
        or marker["parse_failures"] != parse_failures
        or marker["support_decision"] != support["decision"]
    ):
        raise RuntimeError("Stage-A completion-marker accounting does not recompute")
    return {
        "status": "VERIFIED_COMPLETE_COMMIT",
        **summary,
        "call_rows": len(calls),
        "label_rows": len(labels),
        "support_decision": support["decision"],
        "complete_hash": marker["complete_hash"],
        "heldout_opened": False,
    }


def locked(action):
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Stage-A oracle process holds the execution lock") from exc
        return action()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["freeze-spec", "preflight", "prepare", "infer", "finalize", "verify"])
    parser.add_argument("--confirm-oracle", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.stage == "freeze-spec":
        result = freeze_spec()
    elif args.stage == "preflight":
        result = preflight()
    elif args.stage in {"prepare", "infer"}:
        if not args.confirm_oracle:
            raise SystemExit(
                "Semantic frame preparation / physical oracle execution is not authorized. "
                "Use --confirm-oracle only after explicit authority."
            )
        result = locked(lambda: prepare() if args.stage == "prepare" else infer(args.limit))
    elif args.stage == "finalize":
        result = locked(finalize)
    else:
        result = locked(verify)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
