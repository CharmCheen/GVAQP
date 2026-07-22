#!/usr/bin/env python3
"""H-DS1 physical profile and hard-deadline validation.

Phases are resumable and never remove prior raw observations.  The runtime uses
the cache-free physical OracleAccessor service, physical batch-4 proxy scans,
unchanged isolated K3, and durable snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.psvr_runtime import (
    ActionLedger,
    LatencyObservation,
    RuntimeIdentity,
    TailAwareDeadlineGuard,
    TailLatencyProfile,
    attempt_artifact_indices,
    durable_json,
    materialize_and_commit,
    start_physical_oracle_service,
    start_materializer_service,
    start_selector_service,
    strict_indexed_json_paths,
    verify_action_ledger,
)


BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
OUT = REPO / "outputs/psvr_autonomous_research/stage_1_deadline_safety/h_ds1_tail_guard_v2_persistent_k3"
RAW = OUT / "raw"
TABLES = OUT / "tables"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
ORACLE_MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROXY_MODEL = REPO / "models/yolo/yolov8n.pt"
FROZEN_ORACLE = BENCH / "scripts/build_strict_oracle.py"
IDENTITIES = BENCH / "oracle/input_identities.jsonl"
PROMPT = BENCH / "oracle/oracle_prompt.txt"
MATERIALIZER = BENCH / "scripts/benchmark_lib.py"
FROZEN_SEMANTICS = BENCH / "configs/FROZEN_SEMANTIC_HASHES.json"
BENCH_FILE_MANIFEST = BENCH / "FILE_MANIFEST.csv"
STRICT_MANIFEST = BENCH / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json"
MODEL_MANIFEST = BENCH / "oracle/STRICT_MODEL_FILE_MANIFEST.csv"
UNITS_PATH = BENCH / "frozen_inputs/units.csv"
GATE_PATH = REPO / "outputs/psvr_stage0b_physical_profile/partial_proxy_gate.json"
CAPABILITY_REPORT = REPO / "outputs/psvr_stage0a_oracle_audit/capability_isolation_report.json"
BATCH_SIZE = 4
PROFILE_VERSION = "tail_upper_v1"
PROFILE_MINIMUM_SAMPLES = 10
PROFILE_MAXIMUM_AGE_SECONDS = 86400.0
PROFILE_ALPHA = 0.90
ACTION_EPSILON_SECONDS = 0.50
COMMIT_EPSILON_SECONDS = 0.25
VERIFY_STAGES = ("clip_extraction", "oracle_preprocess", "oracle_inference", "oracle_postprocess", "oracle_parse", "cleanup")
COMMIT_STAGES = ("observation_persist", "materialize", "serialize", "fsync", "atomic_replace")
EXPERIMENT_ID = "h_ds1_tail_guard_v2_persistent_k3"
WORKLOAD_ID = "warm_oracle_cold_proxy:after_coarse:physical_service:persistent_k3:v2"
ORACLE_AWARE_LATENCY_STRESS_UNITS = (50, 57, 60)
FROZEN_SEMANTICS_SHA256 = "cc22d59c0cb2311e44b6c377cf894de80400593b470cfbe923598505f2adb253"
PROXY_PROFILER = REPO / "scripts/psvr_stage0b_physical_profile.py"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def command_output(command: list[str]) -> str:
    return subprocess.run(command, text=True, capture_output=True, check=False).stdout.strip()


def package_versions() -> dict[str, str]:
    names = ("torch", "transformers", "qwen-vl-utils", "ultralytics", "opencv-python", "numpy", "pandas", "scipy")
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    return versions


def implementation_hashes() -> dict[str, str]:
    paths = [Path(__file__).resolve(), MATERIALIZER, FROZEN_ORACLE, PROXY_PROFILER]
    paths.extend(sorted((SRC / "garc_eval/psvr_runtime").glob("*.py")))
    return {str(path.relative_to(REPO)): sha256_file(path) for path in paths}


def verify_frozen_inputs() -> dict:
    """Hash all contract inputs once; later phases require identical stat+hash identity."""

    manifest = json.loads(STRICT_MANIFEST.read_text())
    if sha256_file(FROZEN_SEMANTICS) != FROZEN_SEMANTICS_SHA256:
        raise RuntimeError("frozen semantic-hash manifest changed")
    semantic_manifest = json.loads(FROZEN_SEMANTICS.read_text())
    if semantic_manifest.get("benchmark_id") != "cbbv2_514c0d360fd5b2a4b5fe":
        raise RuntimeError("frozen semantic manifest has the wrong benchmark identity")
    protected = semantic_manifest["protected_file_hashes"]
    file_manifest = pd.read_csv(BENCH_FILE_MANIFEST)
    semantic_rows = file_manifest.loc[file_manifest["path"] == "configs/FROZEN_SEMANTIC_HASHES.json"]
    if len(semantic_rows) != 1 or str(semantic_rows.iloc[0]["sha256"]) != FROZEN_SEMANTICS_SHA256:
        raise RuntimeError("benchmark file manifest does not bind the frozen semantic manifest")
    build = manifest["build_identity"]["configuration"]
    unit_frame = pd.read_csv(UNITS_PATH)
    unit_semantics = [{
        "anchor_id": row.anchor_id, "end_time": float(row.end_time),
        "start_time": float(row.start_time), "unit_id": int(row.unit_id), "video_id": row.video_id,
    } for row in unit_frame.itertuples(index=False)]
    critical = {
        "frozen_oracle_source": sha256_file(FROZEN_ORACLE),
        "input_identities": sha256_file(IDENTITIES),
        "prompt": sha256_file(PROMPT),
        "video": sha256_file(VIDEO),
        "strict_manifest": sha256_file(STRICT_MANIFEST),
        "model_manifest": sha256_file(MODEL_MANIFEST),
        "materializer": sha256_file(MATERIALIZER),
        "units_file": sha256_file(UNITS_PATH),
        "units_semantic": canonical_hash(unit_semantics),
        "proxy_checkpoint": sha256_file(PROXY_MODEL),
        "frozen_semantic_manifest": sha256_file(FROZEN_SEMANTICS),
        "benchmark_file_manifest": sha256_file(BENCH_FILE_MANIFEST),
    }
    expected = {
        "frozen_oracle_source": build["script_sha256"],
        "input_identities": manifest["input_identities_sha256"],
        "prompt": build["prompt_sha256"],
        "video": build["video_sha256"],
        "model_manifest": manifest["artifact_hashes"]["oracle/STRICT_MODEL_FILE_MANIFEST.csv"],
        "units_semantic": manifest["build_identity"]["units_sha256"],
        "materializer": protected["scripts/benchmark_lib.py"],
        "units_file": protected["frozen_inputs/units.csv"],
        "strict_manifest": protected["oracle/STRICT_ORACLE_BUILD_MANIFEST.json"],
    }
    mismatch = {name: {"expected": digest, "observed": critical[name]}
                for name, digest in expected.items() if critical[name] != digest}
    if mismatch:
        raise RuntimeError(f"frozen input integrity failure: {mismatch}")

    integrity_path = OUT / "input_integrity.json"
    model_rows = pd.read_csv(MODEL_MANIFEST)
    expected_files = set(model_rows["file"].astype(str))
    observed_files = {path.name for path in ORACLE_MODEL.iterdir() if path.is_file()}
    if expected_files != observed_files:
        raise RuntimeError("oracle model directory membership differs from its frozen manifest")
    if integrity_path.exists():
        prior = json.loads(integrity_path.read_text())
        if prior.get("critical_hashes") != critical:
            raise RuntimeError("critical frozen-input hashes changed within the experiment")
        prior_files = {row["file"]: row for row in prior["model_files"]}
        for row in model_rows.to_dict("records"):
            path = ORACLE_MODEL / str(row["file"]); stat = path.stat(); old = prior_files[str(row["file"])]
            if int(row["size_bytes"]) != stat.st_size or old["size_bytes"] != stat.st_size or old["mtime_ns"] != stat.st_mtime_ns:
                raise RuntimeError(f"oracle model file changed after integrity freeze: {path.name}")
        return prior

    model_files = []
    for row in model_rows.to_dict("records"):
        path = ORACLE_MODEL / str(row["file"]); stat = path.stat()
        observed_hash = sha256_file(path)
        if stat.st_size != int(row["size_bytes"]) or observed_hash != str(row["sha256"]):
            raise RuntimeError(f"oracle model file differs from frozen manifest: {path.name}")
        model_files.append({"file": path.name, "sha256": observed_hash,
                            "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    integrity = {
        "verified_at_utc": now_utc(), "oracle_build_id": manifest["oracle_build_id"],
        "model_full_content_hash": build["model_full_content_hash"],
        "critical_hashes": critical, "model_files": model_files,
        "verification": "full_sha256_all_model_and_contract_files",
    }
    durable_json(integrity_path, integrity)
    return integrity


def oracle_configuration(integrity: dict) -> dict:
    hashes = integrity["critical_hashes"]
    return {
        "frozen_oracle_source": str(FROZEN_ORACLE),
        "input_identities_path": str(IDENTITIES),
        "prompt_path": str(PROMPT),
        "video_path": str(VIDEO),
        "model_path": str(ORACLE_MODEL),
        "strict_manifest_path": str(STRICT_MANIFEST),
        "model_manifest_path": str(MODEL_MANIFEST),
        "expected_hashes": {name: hashes[name] for name in (
            "frozen_oracle_source", "input_identities", "prompt", "video", "strict_manifest", "model_manifest"
        )},
        "expected_oracle_build_id": integrity["oracle_build_id"],
        "model_file_identity": integrity["model_files"],
    }


def runtime_identity(integrity: dict) -> RuntimeIdentity:
    manifest = json.loads(STRICT_MANIFEST.read_text())
    build = manifest["build_identity"]["configuration"]
    hardware = command_output(["nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader"])
    oracle_contract = {
        "model_hash": integrity["model_full_content_hash"],
        "model_manifest_hash": integrity["critical_hashes"]["model_manifest"],
        "prompt_hash": integrity["critical_hashes"]["prompt"],
        "parser_source_hash": build["parser_source_hash"],
        "sampling_hash": build["sampling_code_hash"],
        "oracle_source_hash": integrity["critical_hashes"]["frozen_oracle_source"],
        "input_identities_hash": integrity["critical_hashes"]["input_identities"],
        "oracle_build_id": integrity["oracle_build_id"],
    }
    proxy_config = {"checkpoint_sha256": integrity["critical_hashes"]["proxy_checkpoint"], "batch_size": BATCH_SIZE,
                    "coarse_grid_start_seconds": 15.0, "coarse_stride_seconds": 30.0,
                    "producer_input": "original_decoded_bgr_frames",
                    "producer_source_sha256": sha256_file(PROXY_PROFILER)}
    serving = {
        "oracle_process": "clean_spawn_physical_service", "proxy_process": "trusted_launcher",
        "selector_process": "persistent_empty_chroot_uid65534", "materializer_process": "persistent_empty_chroot_uid65534",
        "materializer_source_hash": integrity["critical_hashes"]["materializer"],
        "oracle_dtype": "bfloat16", "device": "cuda:0", "after_coarse": True,
        "cleanup_in_action": True, "sync_before_after": True,
        "proxy_warmup": "3x_batch4_[15,45,75,105]", "oracle_warmup_queries": 0,
        "profile_replication": "20_independent_fresh_resident_service_processes_zero_prior_queries",
        "validation_policy": "first_query_tail_bound_conservatively_reused_for_subsequent_queries",
        "candidate_strata": {
            "oracle_aware_latency_stress_only_not_method_utility": ORACLE_AWARE_LATENCY_STRESS_UNITS,
            "remaining_and_all_validation": "ranked_proxy_public_observations_only",
        },
        "action_horizon": 1, "package_versions": package_versions(),
    }
    return RuntimeIdentity(
        workload_id=WORKLOAD_ID,
        hardware_id=hardware,
        oracle_model_id=oracle_contract["model_hash"],
        proxy_model_id=proxy_config["checkpoint_sha256"],
        video_sha256=integrity["critical_hashes"]["video"],
        query_id="enter_ego_path",
        oracle_contract_hash=canonical_hash(oracle_contract),
        proxy_config_hash=canonical_hash(proxy_config),
        batch_size=BATCH_SIZE,
        resident_model_set=("Qwen3-VL-32B-Instruct", "yolov8n"),
        serving_config_hash=canonical_hash(serving),
    )


def prepare_experiment() -> dict:
    RAW.mkdir(parents=True, exist_ok=True); TABLES.mkdir(parents=True, exist_ok=True)
    integrity = verify_frozen_inputs(); identity = runtime_identity(integrity); gate = json.loads(GATE_PATH.read_text())
    capability = json.loads(CAPABILITY_REPORT.read_text())
    if capability.get("RUNTIME_CAPABILITY_ISOLATION") != "PASS":
        raise RuntimeError("capability isolation gate is not PASS")
    config = {
        "experiment_id": EXPERIMENT_ID, "hypothesis": "H-DS1",
        "benchmark_id": "cbbv2_514c0d360fd5b2a4b5fe", "runtime_identity": asdict(identity),
        "runtime_identity_hash": canonical_hash(asdict(identity)),
        "implementation_hashes": implementation_hashes(),
        "input_integrity_sha256": canonical_hash(integrity),
        "profile": {"version": PROFILE_VERSION, "minimum_samples": PROFILE_MINIMUM_SAMPLES,
                    "maximum_age_seconds": PROFILE_MAXIMUM_AGE_SECONDS, "quantile_alpha": PROFILE_ALPHA,
                    "action_epsilon_seconds": ACTION_EPSILON_SECONDS,
                    "commit_epsilon_seconds": COMMIT_EPSILON_SECONDS,
                    "action_required_stages": VERIFY_STAGES, "commit_required_stages": COMMIT_STAGES},
        "deadlines": {"T_short": float(gate["regime_B"]["T_min_B"]) + 1.0,
                      "T_mid": (float(gate["regime_B"]["T_min_B"]) + float(gate["regime_B"]["T_max_B"])) / 2.0},
        "video": str(VIDEO), "oracle_model": str(ORACLE_MODEL), "proxy_model": str(PROXY_MODEL),
        "batch_size": BATCH_SIZE, "materializer": "unchanged_k3_bridge_safe_persistent_service",
        "selector": "empty_chroot_fixed_or_ranked_public_proxy_only",
        "oracle_aware_latency_stress_units_not_for_method_claims": ORACLE_AWARE_LATENCY_STRESS_UNITS,
        "heldout_opened": False, "evidence_scope": "DEVELOPMENT_ONLY_ONE_VIDEO_ONE_QUERY",
    }
    config_path = OUT / "resolved_config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != json.loads(json.dumps(config, default=list)):
        raise RuntimeError("resolved experiment config changed; use a new experiment directory")
    if not config_path.exists():
        durable_json(config_path, config)
    environment = {
        "captured_at_utc": now_utc(), "git_commit": command_output(["git", "rev-parse", "HEAD"]),
        "git_status_short": command_output(["git", "status", "--short"]),
        "nvidia_smi": command_output(["nvidia-smi"]),
        "python": sys.version,
    }
    durable_json(OUT / "environment.json", environment)
    (OUT / "git_commit.txt").write_text(environment["git_commit"] + "\n")
    commands = """#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_deadline_safety_validation.py pilot --runs 1
python scripts/run_deadline_safety_validation.py profile --runs 20
python scripts/run_deadline_safety_validation.py short --runs 10
python scripts/run_deadline_safety_validation.py mid --runs 3
python scripts/run_deadline_safety_validation.py finalize
"""
    (OUT / "commands.sh").write_text(commands)
    return config


def video_grid(profiler) -> tuple[float, int, float, list[float]]:
    fps, frames, duration = profiler.video_info()
    grid = [min(duration - 1 / fps, 15.0 + 30.0 * index) for index in range(int(np.ceil(duration / 30.0)))]
    return fps, frames, duration, grid


def mapped_scores(timestamps: list[float], scores: list[float], unit_count: int) -> dict[int, float]:
    result: dict[int, float] = {}
    for timestamp, score in zip(timestamps, scores):
        unit_id = min(unit_count - 1, int(timestamp // 10.0))
        result[unit_id] = max(float(score), result.get(unit_id, float("-inf")))
    return result


def start_resident_runtime(profiler, config: dict):
    import torch
    from ultralytics import YOLO

    oracle = materializer = selector = None
    try:
        integrity = json.loads((OUT / "input_integrity.json").read_text())
        oracle = start_physical_oracle_service(oracle_configuration(integrity))
        proxy = YOLO(str(PROXY_MODEL))
        materializer = start_materializer_service(MATERIALIZER)
        selector = start_selector_service()
        # All resident services exist before this proxy-only warm-up.  The oracle
        # intentionally receives no query; first-call tail is part of the profile.
        for _ in range(3):
            profiler.run_grid_proxy(proxy, torch, [15.0, 45.0, 75.0, 105.0], BATCH_SIZE, [], "h_ds1_proxy_warmup")
        initialization = {
            "oracle": oracle.initialization,
            "materializer": materializer.initialization,
            "selector": selector.initialization,
            "runtime_identity_hash": config["runtime_identity_hash"],
        }
        return oracle, oracle.runtime_accessor(), proxy, torch, materializer, selector, initialization
    except Exception:
        if selector is not None:
            selector.close()
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()
        raise


def proxy_rows(observed: dict[int, float]) -> list[dict]:
    return [{"unit_id": int(unit_id), "proxy_score": float(score)} for unit_id, score in sorted(observed.items())]


def scan_fixture_unit(profiler, proxy, torch, unit_id: int, label: str) -> tuple[float, list[float], list[float], list[dict]]:
    start = unit_id * 10.0
    timestamps = [start + offset for offset in (1.0, 3.0, 5.0, 7.0)]
    rows: list[dict] = []
    seconds, scores = profiler.run_grid_proxy(proxy, torch, timestamps, BATCH_SIZE, rows, label)
    validate_proxy_call(timestamps, scores, rows, label)
    return seconds, timestamps, scores, rows


def validate_proxy_call(timestamps: list[float], scores: list[float], rows: list[dict], label: str) -> None:
    decode_rows = [row for row in rows if row.get("operator") == "decode_seek"]
    failures = [row for row in decode_rows if row.get("status") != "ok"]
    if len(decode_rows) != len(timestamps) or failures or len(scores) != len(timestamps):
        raise RuntimeError(
            f"incomplete proxy call {label}: requested={len(timestamps)}, decoded={len(decode_rows)}, "
            f"scores={len(scores)}, failures={len(failures)}"
        )
    if any(not math.isfinite(float(score)) for score in scores):
        raise RuntimeError(f"non-finite proxy score in {label}")


def oracle_result_errors(result: dict) -> list[str]:
    errors = []
    expected_true = ("physical_oracle_invocation", "logical_oracle_call",
                     "cuda_synchronized_before_and_after", "frame_identity_verified")
    for key in expected_true:
        if result.get(key) is not True:
            errors.append(f"{key}_not_true")
    if result.get("cache_replay") is not False:
        errors.append("cache_replay_not_false")
    if result.get("parse_status") != "ok":
        errors.append(f"parse_status:{result.get('parse_status')}")
    stages = result.get("stage_seconds", {})
    if set(stages) != set(VERIFY_STAGES):
        errors.append("verify_stage_set_mismatch")
    for name, value in stages.items():
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            errors.append(f"invalid_verify_stage:{name}")
    return errors


def profile_sample_errors(sample: dict, config: dict) -> list[str]:
    errors = []
    if sample.get("runtime_identity_hash") != config["runtime_identity_hash"]:
        errors.append("runtime_identity_hash_mismatch")
    if sample.get("resolved_config_sha256") != canonical_hash(config):
        errors.append("resolved_config_hash_mismatch")
    if sample.get("proxy_decode_failures") != 0:
        errors.append("proxy_decode_failure_or_incomplete_scan")
    if sample.get("prior_oracle_query_count") != 0 or sample.get("post_oracle_query_count") != 1:
        errors.append("profile_is_not_an_independent_first_oracle_query")
    result = sample.get("oracle_result", {})
    errors.extend(oracle_result_errors(result))
    commit = sample.get("commit", {})
    if commit.get("materializer_mode") != "persistent_clean_spawn_predeadline":
        errors.append("wrong_materializer_mode")
    stages = commit.get("stage_seconds", {})
    if not set(COMMIT_STAGES).issubset(stages):
        errors.append("commit_stage_set_incomplete")
    for name in COMMIT_STAGES:
        value = stages.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            errors.append(f"invalid_commit_stage:{name}")
    for path_key, digest_path in (
        ("raw_observation_path", commit.get("raw_observation_commit", {}).get("payload_sha256")),
        ("snapshot_path", commit.get("snapshot_commit", {}).get("payload_sha256")),
    ):
        path = Path(sample.get(path_key, ""))
        if not path.is_file() or digest_path is None or sha256_file(path) != digest_path:
            errors.append(f"durable_artifact_invalid:{path_key}")
    for key in ("query_wall_seconds", "commit_wall_seconds", "query_to_commit_seconds"):
        value = sample.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
            errors.append(f"invalid_duration:{key}")
    try:
        verify_action_ledger(
            RAW / "profile" / f"sample_{int(sample['sample_index']):03d}.jsonl",
            expected_run_start_ns=int(sample["attempt_start_ns"]),
            expected_terminal_event="DURABLE_SNAPSHOT_OBSERVED",
        )
    except Exception as exc:
        errors.append(f"invalid_action_ledger:{type(exc).__name__}")
    return sorted(set(errors))


def recover_orphan_attempts(directory: Path, prefix: str, index_field: str, config: dict) -> None:
    """Reserve crashed sidecar/ledger ids without overwriting any prior artifact."""

    directory.mkdir(parents=True, exist_ok=True)
    summaries = {
        int(path.stem.rsplit("_", 1)[1]) for path in strict_indexed_json_paths(directory, prefix)
    }
    for index in sorted(attempt_artifact_indices(directory, prefix) - summaries):
        artifacts = sorted(path.name for path in directory.glob(f"{prefix}_{index:03d}*"))
        durable_json(directory / f"{prefix}_{index:03d}.json", {
            "status": "orphaned_incomplete_attempt", index_field: index,
            "recorded_at_utc": now_utc(), "runtime_identity_hash": config["runtime_identity_hash"],
            "resolved_config_sha256": canonical_hash(config), "discovered_artifacts": artifacts,
            "error": "attempt artifacts existed without a canonical completed summary; index quarantined",
        })


def validate_profile_lineage(action_profile: TailLatencyProfile, commit_profile: TailLatencyProfile,
                             samples: list[dict], profile_dir: Path) -> None:
    """Bind every serialized profile observation back to one revalidated raw summary."""

    expected_action = {}
    expected_commit = {}
    for row in samples:
        index = int(row["sample_index"])
        source_hash = sha256_file(profile_dir / f"sample_{index:03d}.json")
        common = {"recorded_at_utc": row["recorded_at_utc"], "source_artifact_sha256": source_hash}
        expected_action[f"profile_verify_{index:03d}"] = {
            **common, "duration_seconds": float(row["query_wall_seconds"]),
        }
        expected_commit[f"profile_commit_{index:03d}"] = {
            **common, "duration_seconds": float(row["commit_wall_seconds"]),
        }
    for profile, expected in ((action_profile, expected_action), (commit_profile, expected_commit)):
        observed = {item.observation_id: {
            "recorded_at_utc": item.recorded_at_utc,
            "source_artifact_sha256": item.source_artifact_sha256,
            "duration_seconds": float(item.duration_seconds),
        } for item in profile.observations}
        if observed != expected:
            raise RuntimeError(f"{profile.operator_kind} profile is detached from raw physical summaries")


def validation_record_errors(row: dict, config: dict, action_profile: TailLatencyProfile,
                             commit_profile: TailLatencyProfile, phase_dir: Path) -> list[str]:
    errors = []
    if row.get("runtime_identity_hash") != config["runtime_identity_hash"]:
        errors.append("runtime_identity_hash_mismatch")
    if row.get("resolved_config_sha256") != canonical_hash(config):
        errors.append("resolved_config_hash_mismatch")
    if row.get("action_profile_id") != action_profile.profile_id():
        errors.append("action_profile_id_mismatch")
    if row.get("commit_profile_id") != commit_profile.profile_id():
        errors.append("commit_profile_id_mismatch")
    admission = row.get("admission", {})
    if admission.get("action_profile_id") != action_profile.profile_id() or admission.get("commit_profile_id") != commit_profile.profile_id():
        errors.append("admission_profile_id_mismatch")
    if row.get("proxy_decode_failures") != 0 or not row.get("candidate_was_scanned"):
        errors.append("proxy_scan_or_candidate_invalid")
    if not row.get("selector_boundary_ok") or row.get("future_proxy_accesses") != 0:
        errors.append("selector_capability_or_causality_invalid")
    if row.get("cache_replay_calls") != 0:
        errors.append("cache_replay_detected")
    if row.get("oracle_result_errors"):
        errors.append("physical_oracle_result_invalid")
    admitted = bool(row.get("verify_admitted"))
    if int(row.get("physical_oracle_calls", -1)) != int(admitted):
        errors.append("admission_physical_call_count_mismatch")
    if admitted and row.get("physical_oracle_invocation") is not True:
        errors.append("admitted_call_not_physical")
    commit = row.get("commit", {})
    if commit.get("materializer_mode") != "persistent_clean_spawn_predeadline":
        errors.append("wrong_materializer_mode")
    snapshot_path = Path(row.get("snapshot_path", ""))
    snapshot_hash = commit.get("snapshot_commit", {}).get("payload_sha256")
    if not snapshot_path.is_file() or snapshot_hash is None or sha256_file(snapshot_path) != snapshot_hash:
        errors.append("invalid_durable_snapshot")
    raw_path_value = row.get("raw_observation_path")
    if admitted:
        raw_path = Path(raw_path_value or "")
        raw_hash = commit.get("raw_observation_commit", {}).get("payload_sha256")
        if not raw_path.is_file() or raw_hash is None or sha256_file(raw_path) != raw_hash:
            errors.append("invalid_durable_raw_observation")
    elif raw_path_value is not None:
        errors.append("unadmitted_run_has_raw_observation")
    try:
        verify_action_ledger(
            phase_dir / f"run_{int(row['run_index']):03d}.jsonl",
            expected_run_start_ns=int(row["run_start_ns"]), expected_terminal_event="RUN_COMPLETE",
        )
    except Exception as exc:
        errors.append(f"invalid_action_ledger:{type(exc).__name__}")
    return sorted(set(errors))


def profile_phase(target_runs: int, *, allow_partial: bool = False) -> None:
    config = prepare_experiment(); profiler = load_module("h_ds1_proxy_profiler", REPO / "scripts/psvr_stage0b_physical_profile.py")
    units = pd.read_csv(UNITS_PATH); public_units = units.to_dict("records"); _, _, _, grid = video_grid(profiler)
    profile_dir = RAW / "profile"; profile_dir.mkdir(parents=True, exist_ok=True)
    recover_orphan_attempts(profile_dir, "sample", "sample_index", config)
    existing_paths = strict_indexed_json_paths(profile_dir, "sample")
    existing = [json.loads(path.read_text()) for path in existing_paths]
    used = {int(row["unit_id"]) for row in existing if row.get("unit_id") is not None}
    valid_existing = [row for row in existing if row.get("status") == "ok" and not profile_sample_errors(row, config)]
    reserved_indices = attempt_artifact_indices(profile_dir, "sample")
    next_index = 0 if not reserved_indices else max(reserved_indices) + 1
    while len(valid_existing) < target_runs:
        index = next_index; next_index += 1
        attempt_start_ns = time.perf_counter_ns()
        ledger = ActionLedger(profile_dir / f"sample_{index:03d}.jsonl", attempt_start_ns)
        unit_id = None; oracle = materializer = selector = None
        try:
                ledger.append("PROFILE_INITIALIZATION_STARTED", sample_index=index,
                              runtime_identity_hash=config["runtime_identity_hash"],
                              required_prior_oracle_query_count=0)
                # Every latency replicate starts a fresh resident oracle service.
                # Initialization is outside coarse/action durations but retained
                # in the lifecycle ledger and raw initialization metadata.
                oracle, accessor, proxy, torch, materializer, selector, initialization = start_resident_runtime(profiler, config)
                if accessor.query_count() != 0:
                    raise RuntimeError("fresh profile oracle already has prior queries")
                measurement_start_ns = time.perf_counter_ns()
                ledger.append("PROFILE_MEASUREMENT_STARTED", measurement_start_ns=measurement_start_ns)
                coarse_start = time.perf_counter_ns()
                proxy_operator_rows: list[dict] = []
                coarse_seconds, scores = profiler.run_grid_proxy(
                    proxy, torch, grid, BATCH_SIZE, proxy_operator_rows, "h_ds1_profile_coarse")
                validate_proxy_call(grid, scores, proxy_operator_rows, "h_ds1_profile_coarse")
                observed = mapped_scores(grid, scores, len(units)); fixture_seconds = 0.0
                fixture = next((uid for uid in ORACLE_AWARE_LATENCY_STRESS_UNITS if uid not in used), None)
                if fixture is not None:
                    fixture_seconds, fixture_times, fixture_scores, fixture_rows = scan_fixture_unit(
                        profiler, proxy, torch, fixture, f"h_ds1_profile_fixture_{fixture}")
                    proxy_operator_rows.extend(fixture_rows)
                    observed[fixture] = max(map(float, fixture_scores))
                    policy = {"mode": "fixed_scanned_unit", "unit_id": fixture}
                else:
                    policy = {"mode": "ranked_proxy", "rank_offset": 0}
                selection = selector.select(
                    public_units, proxy_rows(observed), [{"unit_id": uid} for uid in sorted(used)], policy)
                unit_id = int(selection["candidate_unit_id"]); used.add(unit_id)
                scan_end = time.perf_counter_ns()
                ledger.append("SCAN_AND_SELECTOR_COMPLETE", wall_start_ns=coarse_start, wall_end_ns=scan_end,
                              coarse_seconds=coarse_seconds, fixture_seconds=fixture_seconds,
                              visible_units=len(observed), selection=selection)

                prior_oracle_query_count = accessor.query_count()
                query_start = time.perf_counter_ns(); result = accessor.query(unit_id)
                result_errors = oracle_result_errors(result)
                queried_rows = [] if result.get("parse_status") != "ok" else [
                    {"unit_id": unit_id, "parsed_label": result["parsed_label"]}
                ]
                commit_start = time.perf_counter_ns(); query_end = commit_start
                query_wall = (query_end - query_start) / 1e9
                raw_path = profile_dir / f"sample_{index:03d}_oracle.json"
                snapshot_path = profile_dir / f"sample_{index:03d}_snapshot.json"
                events, commit = materialize_and_commit(
                    materializer_path=MATERIALIZER, materializer_service=materializer, units=units,
                    queried_rows=queried_rows, snapshot_path=snapshot_path,
                    run_config={"benchmark_id": config["benchmark_id"], "run_id": f"h_ds1_profile_{index:03d}",
                                "method": "profile", "method_variant": "tail_path_v2", "seed": 0,
                                "horizon_budget": len(queried_rows)},
                    raw_observation={"oracle_result": result}, raw_observation_path=raw_path,
                )
                commit_end = time.perf_counter_ns(); commit_wall = (commit_end - commit_start) / 1e9
                query_to_commit = (commit_end - query_start) / 1e9
                sample = {
                    "status": "pending_validation", "sample_index": index, "unit_id": unit_id,
                    "attempt_start_ns": attempt_start_ns, "measurement_start_ns": measurement_start_ns,
                    "prior_oracle_query_count": prior_oracle_query_count,
                    "post_oracle_query_count": accessor.query_count(),
                    "recorded_at_utc": result["recorded_at_utc"], "runtime_initialization": initialization,
                    "runtime_identity_hash": config["runtime_identity_hash"],
                    "resolved_config_sha256": canonical_hash(config), "selection": selection,
                    "coarse_seconds": coarse_seconds, "fixture_scan_seconds": fixture_seconds,
                    "proxy_operator_rows": proxy_operator_rows,
                    "proxy_decode_failures": sum(
                        row.get("operator") == "decode_seek" and row.get("status") != "ok"
                        for row in proxy_operator_rows),
                    "coarse_wall_start_ns": coarse_start, "scan_wall_end_ns": scan_end,
                    "query_wall_start_ns": query_start, "query_wall_end_ns": query_end,
                    "query_wall_seconds": query_wall, "oracle_result": result,
                    "commit_wall_start_ns": commit_start, "commit_wall_end_ns": commit_end,
                    "commit_wall_seconds": commit_wall, "commit": commit,
                    "raw_observation_path": str(raw_path), "snapshot_path": str(snapshot_path),
                    "query_to_commit_seconds": query_to_commit, "confirmed_events": len(events),
                    "raw_result_errors": result_errors,
                    "physical_oracle_invocation": result.get("physical_oracle_invocation"),
                    "cache_replay": result.get("cache_replay"),
                }
                # Durable audit records occur only after the timed query→snapshot path.
                ledger.append("PHYSICAL_VERIFY_OBSERVED", wall_start_ns=query_start, wall_end_ns=query_end,
                              duration_seconds=query_wall, unit_id=unit_id,
                              service_total_seconds=result.get("service_total_seconds"))
                ledger.append("DURABLE_SNAPSHOT_OBSERVED", wall_start_ns=commit_start, wall_end_ns=commit_end,
                              duration_seconds=commit_wall, query_to_commit_seconds=query_to_commit,
                              confirmed_events=len(events), snapshot_path=commit["snapshot_path"])
                errors = profile_sample_errors(sample, config)
                sample["profile_eligibility_errors"] = errors
                sample["status"] = "ok" if not errors else "invalid_profile_observation"
                durable_json(profile_dir / f"sample_{index:03d}.json", sample)
                if not errors:
                    valid_existing.append(sample)
                print(json.dumps({"phase": "profile", "sample": index, "unit": unit_id,
                                  "status": sample["status"], "verify": query_wall,
                                  "commit": commit_wall, "path": query_to_commit}), flush=True)
        except Exception as exc:
                failure = {
                    "status": "failed_attempt", "sample_index": index, "unit_id": unit_id,
                    "attempt_start_ns": attempt_start_ns,
                    "attempt_elapsed_seconds": (time.perf_counter_ns() - attempt_start_ns) / 1e9,
                    "recorded_at_utc": now_utc(), "runtime_identity_hash": config["runtime_identity_hash"],
                    "resolved_config_sha256": canonical_hash(config),
                    "error": f"{type(exc).__name__}: {exc}", "profile_eligibility_errors": ["attempt_failed"],
                }
                durable_json(profile_dir / f"sample_{index:03d}.json", failure)
                ledger.append("PROFILE_SAMPLE_FAILED", error=failure["error"])
                raise
        finally:
            if selector is not None:
                selector.close()
            if materializer is not None:
                materializer.close()
            if oracle is not None:
                oracle.close()

    samples = [json.loads(path.read_text()) for path in strict_indexed_json_paths(profile_dir, "sample")]
    valid = [row for row in samples if row.get("status") == "ok" and not profile_sample_errors(row, config)]
    if len({row["sample_index"] for row in valid}) != len(valid) or len({row["unit_id"] for row in valid}) != len(valid):
        raise RuntimeError("profile observations are not unique independent physical unit calls")
    if len(valid) < PROFILE_MINIMUM_SAMPLES:
        durable_json(OUT / "PROFILE_PARTIAL_STATUS.json", {
            "status": "PARTIAL_NOT_A_PROFILE", "valid_physical_samples": len(valid),
            "minimum_samples_for_any_tail_profile": PROFILE_MINIMUM_SAMPLES,
            "physical_samples_required_before_validation": 20,
            "p95_reported": False,
        })
        if allow_partial:
            print(json.dumps({"status": "PARTIAL_NOT_A_PROFILE", "valid_samples": len(valid),
                              "p95_reported": False}), flush=True)
            return
        raise RuntimeError(f"only {len(valid)} valid samples; at least {PROFILE_MINIMUM_SAMPLES} required")
    identity = RuntimeIdentity(**{**config["runtime_identity"], "resident_model_set": tuple(config["runtime_identity"]["resident_model_set"])})
    created = now_utc()
    action_observations = tuple(LatencyObservation(
        observation_id=f"profile_verify_{row['sample_index']:03d}", duration_seconds=row["query_wall_seconds"],
        recorded_at_utc=row["recorded_at_utc"],
        physical_execution=bool(row["oracle_result"].get("physical_oracle_invocation")),
        cache_replay=bool(row["oracle_result"].get("cache_replay")),
        cuda_synchronized=bool(row["oracle_result"].get("cuda_synchronized_before_and_after")),
        success=not bool(profile_sample_errors(row, config)),
        stage_names=tuple(row["oracle_result"].get("stage_seconds", {})),
        source_artifact_sha256=sha256_file(profile_dir / f"sample_{row['sample_index']:03d}.json"),
    ) for row in valid)
    commit_observations = tuple(LatencyObservation(
        observation_id=f"profile_commit_{row['sample_index']:03d}", duration_seconds=row["commit_wall_seconds"],
        recorded_at_utc=row["recorded_at_utc"],
        physical_execution=row["commit"].get("materializer_mode") == "persistent_clean_spawn_predeadline",
        cache_replay=bool(row.get("cache_replay")), cuda_synchronized=False,
        success=not bool(profile_sample_errors(row, config)),
        stage_names=tuple(row["commit"].get("stage_seconds", {})),
        source_artifact_sha256=sha256_file(profile_dir / f"sample_{row['sample_index']:03d}.json"),
    ) for row in valid)
    common = dict(profile_version=PROFILE_VERSION, identity=identity, created_at_utc=created,
                  minimum_samples=PROFILE_MINIMUM_SAMPLES, maximum_age_seconds=PROFILE_MAXIMUM_AGE_SECONDS,
                  quantile_alpha=PROFILE_ALPHA)
    action_profile = TailLatencyProfile(operator_kind="physical_verify", epsilon_seconds=ACTION_EPSILON_SECONDS,
                                        require_cuda_sync=True, required_stages=VERIFY_STAGES,
                                        observations=action_observations, **common)
    commit_profile = TailLatencyProfile(operator_kind="materialize_and_durable_snapshot",
                                        epsilon_seconds=COMMIT_EPSILON_SECONDS, require_cuda_sync=False,
                                        required_stages=COMMIT_STAGES, observations=commit_observations, **common)
    validate_profile_lineage(action_profile, commit_profile, valid, profile_dir)
    durable_json(OUT / "action_profile.json", action_profile.to_dict())
    durable_json(OUT / "commit_profile.json", commit_profile.to_dict())
    table = pd.DataFrame([{key: row[key] for key in ["sample_index", "unit_id", "recorded_at_utc", "coarse_seconds",
                                                       "query_wall_seconds", "commit_wall_seconds", "query_to_commit_seconds",
                                                       "confirmed_events"]} for row in valid])
    table.to_csv(TABLES / "verify_to_commit_observations.csv", index=False)
    print(json.dumps({"action_bound": action_profile.tail_bound().__dict__,
                      "commit_bound": commit_profile.tail_bound().__dict__}, indent=2), flush=True)


def load_profiles() -> tuple[TailLatencyProfile, TailLatencyProfile]:
    return (
        TailLatencyProfile.from_dict(json.loads((OUT / "action_profile.json").read_text())),
        TailLatencyProfile.from_dict(json.loads((OUT / "commit_profile.json").read_text())),
    )


def validation_phase(kind: str, target_runs: int) -> None:
    config = prepare_experiment(); profiler = load_module(f"h_ds1_{kind}_proxy", REPO / "scripts/psvr_stage0b_physical_profile.py")
    units = pd.read_csv(UNITS_PATH); public_units = units.to_dict("records"); _, _, _, grid = video_grid(profiler)
    deadline = float(config["deadlines"]["T_short" if kind == "short" else "T_mid"])
    action_profile, commit_profile = load_profiles()
    profile_rows = [json.loads(path.read_text()) for path in strict_indexed_json_paths(RAW / "profile", "sample")]
    valid_profile_rows = [row for row in profile_rows if row.get("status") == "ok" and not profile_sample_errors(row, config)]
    if len(valid_profile_rows) < 20:
        raise RuntimeError("deadline validation requires 20 revalidated workload-matched profile samples")
    validate_profile_lineage(action_profile, commit_profile, valid_profile_rows, RAW / "profile")
    identity = RuntimeIdentity(**{**config["runtime_identity"], "resident_model_set": tuple(config["runtime_identity"]["resident_model_set"])})
    guard = TailAwareDeadlineGuard(identity)
    phase_dir = RAW / kind; phase_dir.mkdir(parents=True, exist_ok=True)
    recover_orphan_attempts(phase_dir, "run", "run_index", config)
    existing_paths = strict_indexed_json_paths(phase_dir, "run")
    existing = [json.loads(path.read_text()) for path in existing_paths]
    reserved_indices = attempt_artifact_indices(phase_dir, "run")
    next_index = 0 if not reserved_indices else max(reserved_indices) + 1
    queried_history = [
        {"unit_id": int(unit_id)} for row in existing for unit_id in row.get("queried_ids", [])
    ]
    oracle = materializer = selector = None
    try:
        if len(existing) < target_runs:
            oracle, accessor, proxy, torch, materializer, selector, initialization = start_resident_runtime(profiler, config)
        while len(existing) < target_runs:
            index = next_index; next_index += 1
            run_start = time.perf_counter_ns(); ledger = ActionLedger(phase_dir / f"run_{index:03d}.jsonl", run_start)
            try:
                ledger.append("RUN_STARTED", run_index=index, deadline_seconds=deadline,
                              runtime_identity_hash=config["runtime_identity_hash"])
                proxy_actions = []
                scan_start = time.perf_counter_ns(); coarse_call_start = scan_start
                proxy_operator_rows: list[dict] = []
                coarse_seconds, scores = profiler.run_grid_proxy(
                    proxy, torch, grid, BATCH_SIZE, proxy_operator_rows, f"h_ds1_{kind}_coarse")
                validate_proxy_call(grid, scores, proxy_operator_rows, f"h_ds1_{kind}_coarse")
                coarse_call_end = time.perf_counter_ns()
                proxy_actions.append({"kind": "coarse_global", "start_ns": coarse_call_start,
                                      "end_ns": coarse_call_end, "timestamps": grid})
                observed = mapped_scores(grid, scores, len(units)); fixture_seconds = 0.0
                # Both T_short and T_mid use the same legal public/proxy-only
                # rule. Oracle-aware positive units exist only in latency stress
                # profiling and never authorize a utility or method claim.
                policy = {"mode": "ranked_proxy", "rank_offset": index}
                selection = selector.select(public_units, proxy_rows(observed), queried_history, policy)
                candidate = int(selection["candidate_unit_id"]); scan_end = time.perf_counter_ns()
                ledger.append("SCAN_AND_SELECTOR_COMPLETE", wall_start_ns=scan_start, wall_end_ns=scan_end,
                              coarse_seconds=coarse_seconds, fixture_seconds=fixture_seconds,
                              visible_units=len(observed), selection=selection)

                # Validate immutable profiles before defining the timed admission point.
                provisional = guard.decide(
                    deadline_seconds=deadline, elapsed_seconds=(time.perf_counter_ns() - run_start) / 1e9,
                    now_utc=now_utc(), action_profile=action_profile, commit_profile=commit_profile)
                admission_ns = time.perf_counter_ns()
                admission_elapsed = (admission_ns - run_start) / 1e9
                remaining = deadline - admission_elapsed
                profile_valid = provisional.required_seconds is not None and not provisional.validation_errors
                admitted = bool(profile_valid and remaining > float(provisional.required_seconds))
                reason = ("admitted" if admitted else
                          (provisional.reason if not profile_valid else "insufficient_tail_reservation"))
                decision = replace(provisional, admitted=admitted, reason=reason, remaining_seconds=remaining)

                queried = []; result = None; query_start = query_end = None; result_errors = []
                if decision.admitted:
                    query_start = time.perf_counter_ns(); result = accessor.query(candidate)
                    result_errors = oracle_result_errors(result)
                    if result.get("parse_status") == "ok":
                        queried = [{"unit_id": candidate, "parsed_label": result["parsed_label"]}]
                    query_end = time.perf_counter_ns()
                commit_start = query_end if query_end is not None else time.perf_counter_ns()
                raw_path = None if result is None else phase_dir / f"run_{index:03d}_oracle.json"
                snapshot_path = phase_dir / f"run_{index:03d}_snapshot.json"
                events, commit = materialize_and_commit(
                    materializer_path=MATERIALIZER, materializer_service=materializer,
                    units=units, queried_rows=queried, snapshot_path=snapshot_path,
                    run_config={"benchmark_id": config["benchmark_id"], "run_id": f"h_ds1_{kind}_{index:03d}",
                                "method": "Coverage-Interleave", "method_variant": "tail_guard_v2_safety_fixture",
                                "seed": 0, "horizon_budget": len(queried)},
                    raw_observation=None if result is None else {"oracle_result": result},
                    raw_observation_path=raw_path,
                )
                commit_end = time.perf_counter_ns(); snapshot_elapsed = (commit_end - run_start) / 1e9
                if result is not None:
                    queried_history.append({"unit_id": candidate})
                actual_remaining_path = (commit_end - admission_ns) / 1e9
                unsafe_admitted = bool(decision.admitted and actual_remaining_path > decision.remaining_seconds)
                tail_exceeded = bool(decision.admitted and actual_remaining_path > float(decision.required_seconds))
                future_proxy = sum(int(action["start_ns"] >= admission_ns) for action in proxy_actions)
                snapshot_ok = snapshot_path.is_file() and sha256_file(snapshot_path) == commit["snapshot_commit"]["payload_sha256"]
                record = {
                    "status": "ok" if not result_errors else "oracle_result_invalid",
                    "run_index": index, "kind": kind, "deadline_seconds": deadline,
                    "runtime_identity_hash": config["runtime_identity_hash"],
                    "resolved_config_sha256": canonical_hash(config), "runtime_initialization": initialization,
                    "action_profile_id": action_profile.profile_id(), "commit_profile_id": commit_profile.profile_id(),
                    "run_start_ns": run_start, "scan_start_ns": scan_start, "scan_end_ns": scan_end,
                    "coarse_seconds": coarse_seconds, "fixture_scan_seconds": fixture_seconds,
                    "proxy_operator_rows": proxy_operator_rows,
                    "proxy_decode_failures": sum(
                        row.get("operator") == "decode_seek" and row.get("status") != "ok"
                        for row in proxy_operator_rows),
                    "proxy_actions": proxy_actions, "proxy_units_visible": len(observed),
                    "candidate_unit_id": candidate, "selection": selection,
                    "admission_wall_ns": admission_ns, "admission_elapsed_seconds": admission_elapsed,
                    "admission": decision.to_dict(), "verify_admitted": decision.admitted,
                    "verify_rejected": not decision.admitted,
                    "query_start_ns": query_start, "query_end_ns": query_end,
                    "physical_oracle_calls": int(result is not None),
                    "physical_oracle_invocation": None if result is None else result.get("physical_oracle_invocation"),
                    "cache_replay_calls": int(bool(result and result.get("cache_replay"))),
                    "queried_ids": [] if result is None else [candidate],
                    "parsed_label": None if result is None else result.get("parsed_label"),
                    "oracle_result_errors": result_errors,
                    "raw_observation_path": None if raw_path is None else str(raw_path),
                    "actual_admission_to_commit_seconds": actual_remaining_path,
                    "prediction_residual_seconds": None if not decision.admitted else actual_remaining_path - float(decision.required_seconds),
                    "tail_bound_exceeded": tail_exceeded,
                    "commit_start_ns": commit_start, "commit_end_ns": commit_end,
                    "commit": commit, "confirmed_events": len(events),
                    "snapshot_complete": snapshot_ok, "snapshot_path": str(snapshot_path),
                    "snapshot_elapsed_seconds": snapshot_elapsed,
                    "deadline_met": snapshot_elapsed <= deadline,
                    "unused_deadline_seconds": deadline - snapshot_elapsed,
                    "unsafe_admitted_action": unsafe_admitted,
                    "result_state": "safe_no_confirmed_event" if not events else "confirmed_event",
                    "future_proxy_accesses": future_proxy,
                    "candidate_was_scanned": bool(selection["candidate_was_scanned"]),
                    "selector_boundary_ok": initialization["selector"].get("worker_uid") == 65534
                                            and initialization["selector"].get("worker_root") == "/",
                }
                durable_json(phase_dir / f"run_{index:03d}.json", record)
                # Audit fsyncs occur after the result snapshot and cannot consume its reservation.
                ledger.append("ADMISSION_OBSERVED", admission_wall_ns=admission_ns, **decision.to_dict())
                if result is not None:
                    ledger.append("PHYSICAL_VERIFY_OBSERVED", wall_start_ns=query_start, wall_end_ns=query_end,
                                  duration_seconds=(query_end - query_start) / 1e9, unit_id=candidate,
                                  physical=result.get("physical_oracle_invocation"), cache_replay=result.get("cache_replay"))
                ledger.append("RUN_COMPLETE", snapshot_elapsed_seconds=snapshot_elapsed,
                              deadline_met=record["deadline_met"], confirmed_events=len(events),
                              unsafe_admitted_action=unsafe_admitted, tail_bound_exceeded=tail_exceeded)
                existing.append(record)
                print(json.dumps({"phase": kind, "run": index, "deadline_met": record["deadline_met"],
                                  "admitted": decision.admitted, "confirmed": len(events),
                                  "wall": snapshot_elapsed, "unused": record["unused_deadline_seconds"]}), flush=True)
            except Exception as exc:
                failure = {
                    "status": "failed_attempt", "run_index": index, "kind": kind,
                    "deadline_seconds": deadline, "run_start_ns": run_start,
                    "runtime_identity_hash": config["runtime_identity_hash"],
                    "resolved_config_sha256": canonical_hash(config),
                    "error": f"{type(exc).__name__}: {exc}", "recorded_at_utc": now_utc(),
                }
                durable_json(phase_dir / f"run_{index:03d}.json", failure)
                ledger.append("RUN_FAILED", error=failure["error"])
                raise
    finally:
        if selector is not None:
            selector.close()
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()


def finalize_phase() -> None:
    config = prepare_experiment()
    short_attempts = [json.loads(path.read_text()) for path in strict_indexed_json_paths(RAW / "short", "run")]
    mid_attempts = [json.loads(path.read_text()) for path in strict_indexed_json_paths(RAW / "mid", "run")]
    short = [row for row in short_attempts if row.get("status") == "ok"]
    mid = [row for row in mid_attempts if row.get("status") == "ok"]
    profile_rows = [json.loads(path.read_text()) for path in strict_indexed_json_paths(RAW / "profile", "sample")]
    valid_profile = [row for row in profile_rows if row.get("status") == "ok" and not profile_sample_errors(row, config)]
    short_ready = len(short) >= 10
    safety_checks = {
        "workload_matched_profile_at_least_20": len(valid_profile) >= 20,
        "short_runs_at_least_10": short_ready,
        "runtime_failures_zero": len(short_attempts) == len(short),
        "deadline_misses_zero": short_ready and sum(not row["deadline_met"] for row in short) == 0,
        "incomplete_snapshots_zero": short_ready and sum(not row["snapshot_complete"] for row in short) == 0,
        "unsafe_admitted_actions_zero": short_ready and sum(row["unsafe_admitted_action"] for row in short) == 0,
        "admitted_tail_exceedances_zero": short_ready and sum(row["tail_bound_exceeded"] for row in short) == 0,
        "selector_capability_boundary_enforced": short_ready and all(
            row["selector_boundary_ok"] and row["candidate_was_scanned"] for row in short),
        "future_proxy_accesses_zero": short_ready and all(row["future_proxy_accesses"] == 0 for row in short),
        "cache_replay_zero": short_ready and sum(row["cache_replay_calls"] for row in short) == 0,
    }
    safety = "PASS" if all(safety_checks.values()) else "FAIL"
    mid_calls = sum(row["physical_oracle_calls"] for row in mid)
    mid_confirmed = sum(row["confirmed_events"] for row in mid)
    utility = "PASS" if mid_calls > 0 and mid_confirmed > 0 else ("WEAK" if mid_calls > 0 else "FAIL")
    def summary(rows):
        return {
            "runs": len(rows), "deadline_misses": sum(not row["deadline_met"] for row in rows),
            "verify_admitted": sum(row["verify_admitted"] for row in rows),
            "verify_rejected": sum(row["verify_rejected"] for row in rows),
            "physical_oracle_calls": sum(row["physical_oracle_calls"] for row in rows),
            "confirmed_events": sum(row["confirmed_events"] for row in rows),
            "confirmed_event_rate": 0.0 if not rows else sum(row["confirmed_events"] > 0 for row in rows) / len(rows),
            "unused_deadline_mean_seconds": None if not rows else float(np.mean([row["unused_deadline_seconds"] for row in rows])),
            "prediction_residuals_seconds": [row["prediction_residual_seconds"] for row in rows if row["prediction_residual_seconds"] is not None],
        }
    mid_checks = {
        "runs_at_least_3": len(mid) >= 3,
        "runtime_failures_zero": len(mid_attempts) == len(mid),
        "deadline_misses_zero": bool(mid) and sum(not row["deadline_met"] for row in mid) == 0,
        "unsafe_admissions_zero": bool(mid) and sum(row["unsafe_admitted_action"] for row in mid) == 0,
        "tail_exceedances_zero": bool(mid) and sum(row["tail_bound_exceeded"] for row in mid) == 0,
        "cache_replay_zero": bool(mid) and sum(row["cache_replay_calls"] for row in mid) == 0,
        "capability_and_causality": bool(mid) and all(
            row["selector_boundary_ok"] and row["candidate_was_scanned"] and row["future_proxy_accesses"] == 0
            for row in mid),
    }
    mid_ready = all(mid_checks.values())
    action_profile, commit_profile = load_profiles()
    validate_profile_lineage(action_profile, commit_profile, valid_profile, RAW / "profile")
    def distribution(values):
        array = np.asarray(values, dtype=float)
        return {"n": int(array.size), "p50": float(np.quantile(array, 0.50)),
                "p90": float(np.quantile(array, 0.90)), "p95": float(np.quantile(array, 0.95)),
                "mean": float(np.mean(array)), "std": float(np.std(array, ddof=1)),
                "min": float(np.min(array)), "max": float(np.max(array))}
    profile_statistics = {
        "physical_verify": distribution([row["query_wall_seconds"] for row in valid_profile]),
        "materialize_and_durable_snapshot": distribution([row["commit_wall_seconds"] for row in valid_profile]),
        "verify_to_commit": distribution([row["query_to_commit_seconds"] for row in valid_profile]),
    }
    decision = {"PSVR_DEADLINE_SAFETY": safety, "PSVR_SHORT_DEADLINE_UTILITY": utility,
                "safety_checks": safety_checks, "T_short": summary(short), "T_mid": summary(mid),
                "profile_valid_samples": len(valid_profile), "profile_total_attempts": len(profile_rows),
                "profile_statistics_seconds": profile_statistics,
                "action_tail_bound": asdict(action_profile.tail_bound()),
                "commit_tail_bound": asdict(commit_profile.tail_bound()),
                "mid_regression_checks": mid_checks, "mid_regression_complete": mid_ready,
                "evidence_scope": "empirical_development_safety_one_video_one_query_one_A800_not_formal_WCET",
                "baseline_scaleout_allowed": safety == "PASS" and mid_ready and utility != "FAIL"}
    durable_json(OUT / "DECISION.json", decision)
    if short: pd.DataFrame(short).drop(columns=["commit", "admission"], errors="ignore").to_csv(TABLES / "short_run_summary.csv", index=False)
    if mid: pd.DataFrame(mid).drop(columns=["commit", "admission"], errors="ignore").to_csv(TABLES / "mid_run_summary.csv", index=False)
    report = f"""# H-DS1 Deadline Safety Validation

`PSVR_DEADLINE_SAFETY = {safety}`

`PSVR_SHORT_DEADLINE_UTILITY = {utility}`

## Physical results

- T_short runs: {len(short)}; misses: {decision['T_short']['deadline_misses']}; admitted/rejected VERIFY: {decision['T_short']['verify_admitted']}/{decision['T_short']['verify_rejected']}; confirmed events: {decision['T_short']['confirmed_events']}.
- T_mid regression runs: {len(mid)}; misses: {decision['T_mid']['deadline_misses']}; physical VERIFY: {decision['T_mid']['physical_oracle_calls']}; confirmed events: {decision['T_mid']['confirmed_events']}.

The guard uses workload-matched, cache-free physical paths and reserves unchanged isolated K3 plus durable snapshot commit independently. Missing, stale, wrong-workload, asynchronous, and cache-contaminated profiles fail closed.

`PSVR_SHORT_DEADLINE_UTILITY` is the preregistered T_mid non-vacuity regression: it does not claim method quality at T_short. The safety result is empirical for one development video/query/A800 workload, not a formal worst-case execution-time guarantee.

Baseline scale-out allowed: `{str(decision['baseline_scaleout_allowed']).lower()}`.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    print(json.dumps(decision, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "profile", "short", "mid", "finalize"])
    parser.add_argument("--runs", type=int)
    args = parser.parse_args()
    if args.phase == "pilot": profile_phase(args.runs or 1, allow_partial=True)
    elif args.phase == "profile": profile_phase(args.runs or 20)
    elif args.phase == "short": validation_phase("short", args.runs or 10)
    elif args.phase == "mid": validation_phase("mid", args.runs or 3)
    else: finalize_phase()


if __name__ == "__main__":
    main()
    attempt_artifact_indices,
