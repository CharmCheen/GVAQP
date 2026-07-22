#!/usr/bin/env python3
"""Physically profile the frozen oracle path and freeze four task deadlines."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.psvr_runtime import (
    LatencyObservation,
    RuntimeIdentity,
    TailLatencyProfile,
    durable_json,
    materialize_and_commit,
    start_materializer_service,
    start_two_video_physical_oracle_service,
)


OUT = ROOT / "outputs/psvr_two_video_loop"
DEADLINES = OUT / "deadlines"
RAW = DEADLINES / "raw_profile"
DEV = OUT / "dev_benchmark_v1"
VIDEO_MANIFEST = OUT / "VIDEO_MANIFEST.json"
QUERY_PROTOCOL = OUT / "QUERY_SELECTION_PROTOCOL.json"
BENCHMARK_DECISION = DEV / "FINAL_BENCHMARK_DECISION.json"
TASK_MANIFEST = DEV / "TASK_MANIFEST.json"
V0_BENCH = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict"
)
FROZEN_ORACLE = V0_BENCH / "scripts/build_strict_oracle.py"
PROMPT = V0_BENCH / "oracle/oracle_prompt.txt"
V0_IDENTITIES = V0_BENCH / "oracle/input_identities.jsonl"
V0_STRICT_MANIFEST = V0_BENCH / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json"
V0_UNITS = V0_BENCH / "frozen_inputs/units.csv"
V1_IDENTITIES = DEV / "raw_oracle/V1/input_identities.jsonl"
V1_CONFIG = DEV / "raw_oracle/V1/ORACLE_CONFIG.json"
V1_UNITS = DEV / "units/V1_units.csv"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
MODEL_INTEGRITY = (
    ROOT
    / "outputs/psvr_autonomous_research/stage_1_deadline_safety"
    / "h_ds1_tail_guard_v2_persistent_k3/input_integrity.json"
)
MATERIALIZER = V0_BENCH / "scripts/benchmark_lib.py"
OLD_GATE = ROOT / "outputs/psvr_stage0b_physical_profile/partial_proxy_gate.json"
OLD_TRANSITIONS = (
    ROOT
    / "outputs/psvr_autonomous_research/stage_3_factorization"
    / "TRANSITION_DEADLINES.json"
)
PROFILE_SAMPLES = 10
VERIFY_STAGES = (
    "clip_extraction",
    "oracle_preprocess",
    "oracle_inference",
    "oracle_postprocess",
    "oracle_parse",
    "cleanup",
)
COMMIT_STAGES = (
    "observation_persist",
    "materialize",
    "serialize",
    "fsync",
    "atomic_replace",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def hardware_id() -> str:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,uuid,driver_version",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def oracle_configuration() -> dict[str, Any]:
    videos = json.loads(VIDEO_MANIFEST.read_text(encoding="utf-8"))
    queries = json.loads(QUERY_PROTOCOL.read_text(encoding="utf-8"))
    v0_manifest = json.loads(V0_STRICT_MANIFEST.read_text(encoding="utf-8"))
    v1_config = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
    integrity = json.loads(MODEL_INTEGRITY.read_text(encoding="utf-8"))
    configuration = {
        "frozen_oracle_source": str(FROZEN_ORACLE),
        "frozen_oracle_source_sha256": sha256_file(FROZEN_ORACLE),
        "prompt_path": str(PROMPT),
        "prompt_sha256": sha256_file(PROMPT),
        "model_path": str(MODEL),
        "model_full_content_hash": integrity["model_full_content_hash"],
        "model_file_identity": integrity["model_files"],
        "videos": {
            "V0": {
                "video_path": videos["V0"]["absolute_path"],
                "video_sha256": videos["V0"]["sha256"],
                "input_identities_path": str(V0_IDENTITIES),
                "input_identities_sha256": sha256_file(V0_IDENTITIES),
                "oracle_build_id": v0_manifest["oracle_build_id"],
            },
            "V1": {
                "video_path": videos["V1"]["absolute_path"],
                "video_sha256": videos["V1"]["sha256"],
                "input_identities_path": str(V1_IDENTITIES),
                "input_identities_sha256": sha256_file(V1_IDENTITIES),
                "oracle_build_id": v1_config["build_id"],
            },
        },
        "queries": {
            row["query_id"]: {
                "allowed_involved_objects": sorted(
                    row["frozen_oracle_type_projection"]
                )
            }
            for row in queries["queries"]
        },
    }
    return configuration


def runtime_identity(
    video_id: str, query_id: str, configuration: dict[str, Any]
) -> RuntimeIdentity:
    prereg = json.loads(
        (OUT / "proxy_finalization/H_PROXY_2VIDEO_PREREGISTRATION.json").read_text(
            encoding="utf-8"
        )
    )
    implementation_path = (
        OUT / "proxy_finalization/PROXY_IMPLEMENTATION_FREEZE.json"
    )
    proxy_config_hash = (
        json.loads(implementation_path.read_text(encoding="utf-8"))["freeze_hash"]
        if implementation_path.exists()
        else prereg["preregistration_hash"]
    )
    return RuntimeIdentity(
        workload_id="two_video_warm_oracle_cold_proxy_persistent_model_sessions_v1",
        hardware_id=hardware_id(),
        oracle_model_id=configuration["model_full_content_hash"],
        proxy_model_id=prereg["preregistration_hash"],
        video_sha256=configuration["videos"][video_id]["video_sha256"],
        query_id=query_id,
        oracle_contract_hash=canonical_hash(
            {
                "source": configuration["frozen_oracle_source_sha256"],
                "prompt": configuration["prompt_sha256"],
                "model": configuration["model_full_content_hash"],
                "video": configuration["videos"][video_id],
                "projection": configuration["queries"][query_id],
            }
        ),
        proxy_config_hash=proxy_config_hash,
        batch_size=1,
        resident_model_set=(
            "Qwen3-VL-32B-Instruct",
            "one_frozen_H-PROXY-2VIDEO_candidate",
        ),
        serving_config_hash=canonical_hash(
            {
                "oracle_model": "persistent_across_runs",
                "logical_query_ledger": "fresh_per_run",
                "cache_replay": False,
                "proxy": "cold_per_run",
                "materializer": "persistent_clean_spawn_predeadline",
                "oracle_cleanup_in_action": True,
                "cuda_sync": True,
            }
        ),
    )


def load_units(video_id: str) -> pd.DataFrame:
    path = V0_UNITS if video_id == "V0" else V1_UNITS
    units = pd.read_csv(path)
    if "benchmark_id" not in units.columns:
        benchmark = json.loads((DEV / "TASK_MANIFEST.json").read_text())
        units.insert(0, "benchmark_id", benchmark["benchmark_id"])
    if list(units["unit_id"].astype(int)) != list(range(len(units))):
        raise RuntimeError(f"{video_id} units are not contiguous")
    return units


def profile_unit_ids(unit_count: int) -> list[int]:
    result = [
        min(unit_count - 1, int((index + 0.5) * unit_count / PROFILE_SAMPLES))
        for index in range(PROFILE_SAMPLES)
    ]
    if len(set(result)) != PROFILE_SAMPLES:
        raise RuntimeError("deterministic profile units are not unique")
    return result


def sample_path(video_id: str, index: int) -> Path:
    return RAW / video_id / f"sample_{index:03d}.json"


def archive_orphan_profile_observations() -> list[dict[str, Any]]:
    """Retain physical calls that failed before a valid sample summary."""

    archived = []
    failure_dir = RAW / "failed_attempts"
    for video_id in ("V0", "V1"):
        for index in range(PROFILE_SAMPLES):
            summary = sample_path(video_id, index)
            raw_path = RAW / video_id / f"sample_{index:03d}_oracle.json"
            snapshot = RAW / video_id / f"sample_{index:03d}_snapshot.json"
            if summary.exists() or not raw_path.exists():
                continue
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            result = payload["oracle_result"]
            archived_raw = (
                failure_dir
                / f"{video_id}_sample_{index:03d}_orphan_oracle.json"
            )
            archived_raw.parent.mkdir(parents=True, exist_ok=True)
            os.replace(raw_path, archived_raw)
            archived_snapshot = None
            if snapshot.exists():
                archived_snapshot = (
                    failure_dir
                    / f"{video_id}_sample_{index:03d}_orphan_snapshot.json"
                )
                os.replace(snapshot, archived_snapshot)
            record = {
                "status": "excluded_failed_attempt",
                "video_id": video_id,
                "sample_index": index,
                "unit_id": int(result["unit_id"]),
                "reason": (
                    "physical query completed but no valid profile summary was committed; "
                    "the call is retained and excluded rather than replayed"
                ),
                "physical_oracle_invocation": result[
                    "physical_oracle_invocation"
                ],
                "cache_replay": result["cache_replay"],
                "service_total_seconds": float(
                    result["service_total_seconds"]
                ),
                "oracle_inference_seconds": float(
                    result["stage_seconds"]["oracle_inference"]
                ),
                "archived_raw_path": str(archived_raw),
                "archived_raw_sha256": sha256_file(archived_raw),
                "archived_snapshot_path": (
                    None
                    if archived_snapshot is None
                    else str(archived_snapshot)
                ),
                "retained": True,
                "eligible_profile_sample": False,
            }
            durable_json(
                failure_dir
                / f"{video_id}_sample_{index:03d}_failure.json",
                record,
            )
            archived.append(record)
    return archived


def profile() -> None:
    if not BENCHMARK_DECISION.exists():
        raise RuntimeError("Finalize and verify the two-video benchmark before profiling")
    benchmark = json.loads(BENCHMARK_DECISION.read_text(encoding="utf-8"))
    if benchmark.get("TWO_VIDEO_DEV_BENCHMARK") != "PASS":
        raise RuntimeError("TWO_VIDEO_DEV_BENCHMARK is not PASS")
    configuration = oracle_configuration()
    config_path = DEADLINES / "ORACLE_RUNTIME_CONFIG.json"
    if config_path.exists():
        if json.loads(config_path.read_text(encoding="utf-8")) != configuration:
            raise RuntimeError("Physical oracle runtime configuration changed")
    else:
        durable_json(config_path, configuration)
    archive_orphan_profile_observations()
    existing = [
        sample_path(video_id, index)
        for video_id in ("V0", "V1")
        for index in range(PROFILE_SAMPLES)
    ]
    if all(path.exists() for path in existing):
        build_profiles(configuration)
        return
    oracle = materializer = None
    active_session: str | None = None
    try:
        materializer = start_materializer_service(MATERIALIZER)
        oracle = start_two_video_physical_oracle_service(configuration)
        durable_json(DEADLINES / "PROFILE_INITIALIZATION.json", {
            "oracle": oracle.initialization,
            "materializer": materializer.initialization,
            "started_at_utc": now_utc(),
        })
        for video_id in ("V0", "V1"):
            units = load_units(video_id)
            for index, unit_id in enumerate(profile_unit_ids(len(units))):
                destination = sample_path(video_id, index)
                if destination.exists():
                    continue
                session_id = f"deadline_profile_{video_id}_{index:03d}"
                accessor, session_initialization = oracle.start_session(
                    session_id, video_id, "Q1"
                )
                active_session = session_id
                query_started = time.perf_counter_ns()
                result = accessor.query(unit_id)
                query_seconds = (time.perf_counter_ns() - query_started) / 1e9
                if (
                    result.get("physical_oracle_invocation") is not True
                    or result.get("cache_replay") is not False
                    or result.get("parse_status") != "ok"
                ):
                    raise RuntimeError("Invalid physical oracle profile result")
                raw_path = RAW / video_id / f"sample_{index:03d}_oracle.json"
                snapshot_path = RAW / video_id / f"sample_{index:03d}_snapshot.json"
                commit_started = time.perf_counter_ns()
                events, commit = materialize_and_commit(
                    materializer_path=MATERIALIZER,
                    materializer_service=materializer,
                    units=units,
                    queried_rows=[
                        {
                            "unit_id": unit_id,
                            "parsed_label": result["parsed_label"],
                        }
                    ],
                    snapshot_path=snapshot_path,
                    run_config={
                        "benchmark_id": f"two_video_profile_{video_id}",
                        "run_id": session_id,
                        "method": "deadline_profile",
                        "method_variant": "deadline_profile",
                        "seed": index,
                        "horizon_budget": 1,
                    },
                    raw_observation={"oracle_result": result},
                    raw_observation_path=raw_path,
                )
                commit_seconds = (time.perf_counter_ns() - commit_started) / 1e9
                session_summary = oracle.end_session(session_id)
                active_session = None
                row = {
                    "status": "ok",
                    "video_id": video_id,
                    "sample_index": index,
                    "unit_id": unit_id,
                    "recorded_at_utc": result["recorded_at_utc"],
                    "query_wall_seconds": query_seconds,
                    "service_total_seconds": result["service_total_seconds"],
                    "commit_wall_seconds": commit_seconds,
                    "oracle_result": result,
                    "commit": commit,
                    "confirmed_events": len(events),
                    "session_initialization": session_initialization,
                    "session_summary": session_summary,
                    "physical_oracle_only": True,
                    "cache_replay": False,
                }
                durable_json(destination, row)
                print(json.dumps({
                    "stage": "deadline_profile",
                    "video_id": video_id,
                    "sample": index + 1,
                    "samples": PROFILE_SAMPLES,
                    "unit_id": unit_id,
                    "query_seconds": query_seconds,
                    "commit_seconds": commit_seconds,
                }), flush=True)
    finally:
        if active_session is not None and oracle is not None:
            try:
                oracle.end_session(active_session)
            except Exception:
                pass
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()
    build_profiles(configuration)


def build_profiles(configuration: dict[str, Any]) -> None:
    DEADLINES.mkdir(parents=True, exist_ok=True)
    for video_id in ("V0", "V1"):
        samples = [
            json.loads(sample_path(video_id, index).read_text(encoding="utf-8"))
            for index in range(PROFILE_SAMPLES)
        ]
        for query_id in ("Q1", "Q2"):
            identity = runtime_identity(video_id, query_id, configuration)
            action_observations = []
            commit_observations = []
            for row in samples:
                source = sample_path(video_id, int(row["sample_index"]))
                source_hash = sha256_file(source)
                result = row["oracle_result"]
                action_observations.append(
                    LatencyObservation(
                        observation_id=(
                            f"{video_id}_{query_id}_verify_{int(row['sample_index']):03d}"
                        ),
                        duration_seconds=float(row["query_wall_seconds"]),
                        recorded_at_utc=row["recorded_at_utc"],
                        physical_execution=True,
                        cache_replay=False,
                        cuda_synchronized=True,
                        success=row["status"] == "ok",
                        stage_names=tuple(result["stage_seconds"]),
                        source_artifact_sha256=source_hash,
                    )
                )
                commit_observations.append(
                    LatencyObservation(
                        observation_id=(
                            f"{video_id}_{query_id}_commit_{int(row['sample_index']):03d}"
                        ),
                        duration_seconds=float(row["commit_wall_seconds"]),
                        recorded_at_utc=row["recorded_at_utc"],
                        physical_execution=True,
                        cache_replay=False,
                        cuda_synchronized=False,
                        success=row["status"] == "ok",
                        stage_names=tuple(row["commit"]["stage_seconds"]),
                        source_artifact_sha256=source_hash,
                    )
                )
            common = {
                "profile_version": "tail_upper_v1",
                "identity": identity,
                "created_at_utc": max(row["recorded_at_utc"] for row in samples),
                "minimum_samples": PROFILE_SAMPLES,
                "maximum_age_seconds": 86400.0,
                "quantile_alpha": 0.90,
            }
            action = TailLatencyProfile(
                operator_kind="physical_verify",
                epsilon_seconds=0.5,
                require_cuda_sync=True,
                required_stages=VERIFY_STAGES,
                observations=tuple(action_observations),
                **common,
            )
            commit = TailLatencyProfile(
                operator_kind="materialize_and_durable_snapshot",
                epsilon_seconds=0.25,
                require_cuda_sync=False,
                required_stages=COMMIT_STAGES,
                observations=tuple(commit_observations),
                **common,
            )
            directory = DEADLINES / "profiles" / f"{video_id}_{query_id}"
            durable_json(directory / "action_profile.json", action.to_dict())
            durable_json(directory / "commit_profile.json", commit.to_dict())
    durable_json(DEADLINES / "PROFILE_DECISION.json", {
        "PHYSICAL_ORACLE_PROFILE": "PASS",
        "videos": 2,
        "queries": 2,
        "physical_samples_per_video": PROFILE_SAMPLES,
        "logical_task_profiles": 4,
        "excluded_failed_physical_attempts": len(
            list((RAW / "failed_attempts").glob("*_failure.json"))
        ),
        "persistent_model_across_sessions": True,
        "fresh_query_ledger_per_sample": True,
        "cache_replay_calls": 0,
        "heldout_opened": False,
    })


def freeze() -> None:
    benchmark = json.loads(BENCHMARK_DECISION.read_text(encoding="utf-8"))
    if benchmark.get("TWO_VIDEO_DEV_BENCHMARK") != "PASS":
        raise RuntimeError("TWO_VIDEO_DEV_BENCHMARK is not PASS")
    if any(
        (OUT / "proxy_finalization/raw" / family / video / "EXTRACTION_COMPLETE.json").exists()
        for family in ("Y8", "YP640", "YP320")
        for video in ("V0", "V1")
    ):
        raise RuntimeError("Task deadlines must be frozen before proxy candidate execution")
    profile_decision = json.loads(
        (DEADLINES / "PROFILE_DECISION.json").read_text(encoding="utf-8")
    )
    if profile_decision.get("PHYSICAL_ORACLE_PROFILE") != "PASS":
        raise RuntimeError("Physical oracle profile is incomplete")
    old_gate = json.loads(OLD_GATE.read_text(encoding="utf-8"))
    old_transition = json.loads(OLD_TRANSITIONS.read_text(encoding="utf-8"))
    old_tmin = float(old_gate["regime_B"]["T_min_B"])
    old_tmax = float(old_gate["regime_B"]["T_max_B"])
    old_deadlines = old_transition["deadlines_seconds"]
    low_fraction = (float(old_deadlines["T_low"]) - old_tmin) / (
        old_tmax - old_tmin
    )
    transition_fraction = (
        float(old_deadlines["T_transition"]) - old_tmin
    ) / (old_tmax - old_tmin)
    videos = json.loads(VIDEO_MANIFEST.read_text(encoding="utf-8"))
    v0_duration = float(videos["V0"]["duration_seconds"])
    rows = []
    regimes = {}
    for video_id in ("V0", "V1"):
        action = TailLatencyProfile.from_dict(
            json.loads(
                (
                    DEADLINES
                    / "profiles"
                    / f"{video_id}_Q1"
                    / "action_profile.json"
                ).read_text(encoding="utf-8")
            )
        )
        commit = TailLatencyProfile.from_dict(
            json.loads(
                (
                    DEADLINES
                    / "profiles"
                    / f"{video_id}_Q1"
                    / "commit_profile.json"
                ).read_text(encoding="utf-8")
            )
        )
        action_values = np.asarray(
            [row.duration_seconds for row in action.observations], dtype=float
        )
        commit_values = np.asarray(
            [row.duration_seconds for row in commit.observations], dtype=float
        )
        duration_scale = float(videos[video_id]["duration_seconds"]) / v0_duration
        coarse_p95 = float(old_gate["regime_B"]["coarse_p95"]) * duration_scale
        full_proxy_p50 = float(old_gate["regime_B"]["full_proxy_p50"]) * duration_scale
        verify_p95 = float(np.percentile(action_values, 95))
        commit_p95 = float(np.percentile(commit_values, 95))
        safety_margin = float(old_gate["regime_B"]["safety_margin"])
        t_min = coarse_p95 + verify_p95 + commit_p95 + safety_margin
        t_max = full_proxy_p50
        if not t_min < t_max:
            raise RuntimeError(f"{video_id} has no valid partial-proxy interval")
        t_short = t_min + low_fraction * (t_max - t_min)
        t_transition = t_min + transition_fraction * (t_max - t_min)
        t_high = t_max
        regimes[video_id] = {
            "duration_scale_from_V0": duration_scale,
            "coarse_proxy_p95_seconds": coarse_p95,
            "physical_verify_p95_seconds": verify_p95,
            "k3_snapshot_commit_p95_seconds": commit_p95,
            "safety_margin_seconds": safety_margin,
            "T_min_seconds": t_min,
            "T_max_seconds": t_max,
            "interval_width_seconds": t_max - t_min,
            "normalized_interval_width": (t_max - t_min) / t_max,
            "T_short_seconds": t_short,
            "T_transition_seconds": t_transition,
            "T_high_seconds": t_high,
        }
        for query_id in ("Q1", "Q2"):
            rows.append({
                "task_id": f"{video_id}_{query_id}",
                "video_id": video_id,
                "query_id": query_id,
                "T_short": t_short,
                "T_transition": t_transition,
                "T_high": t_high,
            })
    manifest = {
        "manifest_version": "PSVR_TWO_VIDEO_TASK_DEADLINES_V1",
        "frozen_at_utc": now_utc(),
        "frozen_before_proxy_candidate_runs": True,
        "derivation": {
            "simple_baseline_trace": str(OLD_TRANSITIONS),
            "simple_baseline_trace_sha256": sha256_file(OLD_TRANSITIONS),
            "physical_profile": str(DEADLINES / "PROFILE_DECISION.json"),
            "low_dimensionless_fraction": low_fraction,
            "transition_dimensionless_fraction": transition_fraction,
            "T_high_rule": "runtime-scaled existing simple-baseline full-proxy p50",
            "T_min_rule": "coarse p95 + physical VERIFY p95 + K3/commit p95 + safety",
            "candidate_family_or_method_outcome_used": False,
        },
        "video_regimes": regimes,
        "tasks": rows,
        "formal_deadlines": ["T_transition", "T_high"],
        "T_short_use": "safety/floor diagnostic only",
        "heldout_opened": False,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    destination = DEADLINES / "TASK_DEADLINE_MANIFEST.json"
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        unstable = {"frozen_at_utc", "manifest_hash"}
        stable_existing = {
            key: value for key, value in existing.items() if key not in unstable
        }
        stable_new = {
            key: value for key, value in manifest.items() if key not in unstable
        }
        if stable_existing != stable_new:
            raise RuntimeError("Task deadline manifest changed after freeze")
        manifest = existing
    else:
        durable_json(destination, manifest)
        durable_json(OUT / "state/DEADLINE_FREEZE_DECISION.json", {
            "TASK_DEADLINE_FREEZE": "PASS",
            "manifest_hash": manifest["manifest_hash"],
            "tasks": 4,
            "candidate_outcome_dependence": False,
            "heldout_opened": False,
        })
    print(json.dumps({
        "TASK_DEADLINE_FREEZE": "PASS",
        "manifest_hash": manifest["manifest_hash"],
        "video_regimes": manifest["video_regimes"],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("profile", "freeze"))
    args = parser.parse_args()
    if args.stage == "profile":
        profile()
    else:
        freeze()


if __name__ == "__main__":
    main()
