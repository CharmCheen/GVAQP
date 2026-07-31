#!/usr/bin/env python3
"""Audit or execute the preregistered paired ARC physical smoke.

Preflight is intentionally fail-closed and occurs before importing torch,
opening a video, or starting either model.  The only registered cell is
V0_Q1 / T_transition / replicate 0 / Y8, paired with the latest executable
accelerated policy, H-STAGE1 (``ST1``).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.arc_cached_replay import ARCConfig
from garc_eval.arc_physical import (
    ARC_PHYSICAL_METHOD,
    CURRENT_ACCELERATED_METHOD,
    ARCPhysicalPolicy,
    ARCPhysicalRuntime,
    audit_shared_contract,
    load_deployable_calibrator,
)
from garc_eval.psvr_runtime import (
    ActionLedger,
    TailAwareDeadlineGuard,
    durable_json,
    materialize_and_commit,
    start_materializer_service,
    start_two_video_physical_oracle_service,
)


CURRENT_RUNNER = ROOT / "scripts/run_psvr_two_video_physical.py"
CURRENT_METHOD_RUNNER = ROOT / "scripts/run_psvr_stage1_physical.py"
ORIGINAL_REPO = Path("/root/charm/GVAQP")
OUTPUT = ROOT / "outputs/arc_unit_inspired_phys_v1"
MATERIALIZER = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
)
READINESS = (
    ROOT
    / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a"
    / "modeling/STAGE_A_MODEL_READINESS_DECISION.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str, identity: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"missing immutable {identity}: {path}")
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError(
            f"immutable {identity} hash mismatch: expected {expected}, got {observed}"
        )
    return path


def resolve_physical_inputs(contract: dict[str, Any], current) -> dict[str, Any]:
    """Resolve immutable bytes only by their frozen hashes, never by outcome."""

    deadline_runtime = current.deadline_module()
    action_profile, commit_profile = current.load_profiles("V0", "Q1")
    observed_hardware = deadline_runtime.hardware_id()
    if observed_hardware != action_profile.identity.hardware_id:
        raise RuntimeError(
            "current GPU hardware identity does not match the frozen deadline "
            f"profile: observed={observed_hardware!r}, "
            f"required={action_profile.identity.hardware_id!r}"
        )
    profile_admission = TailAwareDeadlineGuard(action_profile.identity).decide(
        deadline_seconds=float(contract["smoke_cell"]["deadline_seconds"]),
        elapsed_seconds=0.0,
        now_utc=current.now_utc(),
        action_profile=action_profile,
        commit_profile=commit_profile,
    )
    if profile_admission.reason == "profile_invalid":
        raise RuntimeError(
            "frozen deadline profiles are not currently admissible: "
            + ",".join(profile_admission.validation_errors)
        )

    video_candidates = {
        "V0": ORIGINAL_REPO / "data/realcam/wuhan.mp4",
        "V1": ORIGINAL_REPO / "data/realcam/dali.mp4",
    }
    videos = {
        video_id: _require_hash(
            path, contract["video_sha256"][video_id], f"{video_id} video"
        )
        for video_id, path in video_candidates.items()
    }
    prereg = json.loads(current.PREREG.read_text())
    declared_weight = prereg["candidates"]["Y8"]
    weight_candidates = [
        Path(declared_weight["weight_path"]),
        ORIGINAL_REPO / "models/yolo/yolov8n.pt",
    ]
    weight = next((path for path in weight_candidates if path.is_file()), None)
    if weight is None:
        raise RuntimeError(
            "missing immutable Y8 checkpoint with frozen hash "
            + declared_weight["weight_sha256"]
        )
    _require_hash(weight, declared_weight["weight_sha256"], "Y8 checkpoint")

    oracle_configuration = deadline_runtime.oracle_configuration()
    declared_model = Path(oracle_configuration["model_path"])
    model_candidates = [
        declared_model,
        ORIGINAL_REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct",
    ]
    model = next((path for path in model_candidates if path.is_dir()), None)
    if model is None:
        raise RuntimeError(
            "missing exact frozen Qwen3-VL-32B-Instruct model directory; "
            "the available FP8 directory has a different identity"
        )
    oracle_configuration["model_path"] = str(model)
    for video_id, path in videos.items():
        oracle_configuration["videos"][video_id]["video_path"] = str(path)
    return {
        "video_paths": {key: str(value) for key, value in videos.items()},
        "proxy_weight": str(weight),
        "proxy_prereg_overrides": {
            "candidates": {
                **prereg["candidates"],
                "Y8": {**declared_weight, "weight_path": str(weight)},
            }
        },
        "oracle_configuration": oracle_configuration,
        "deadline_runtime": deadline_runtime,
    }


def preregistered_job(
    current,
    contract: dict[str, Any],
    method: str,
    *,
    current_method_runner=None,
) -> dict[str, Any]:
    cell = contract["smoke_cell"]
    if method == CURRENT_ACCELERATED_METHOD:
        if current_method_runner is None:
            raise RuntimeError("the frozen ST1 runner is required for the current leg")
        matches = [
            job
            for job in current_method_runner.jobs(current)
            if job["method"] == CURRENT_ACCELERATED_METHOD
            and job["task_id"] == cell["task_id"]
            and job["deadline_name"] == cell["deadline_name"]
            and int(job["replicate"]) == int(cell["replicate"])
        ]
        if len(matches) != 1:
            raise RuntimeError("frozen ST1 runner did not resolve one smoke cell")
        return matches[0]
    scans, verifies = current.planned_scan_actions(
        cell["proxy_family"], cell["task_id"], cell["deadline_name"]
    )
    return {
        "kind": "arc_physical_paired_smoke",
        "method": method,
        "family": cell["proxy_family"],
        "task_id": cell["task_id"],
        "deadline_name": cell["deadline_name"],
        "deadline_seconds": cell["deadline_seconds"],
        "replicate": cell["replicate"],
        "parameters": (
            {"temporal_nms_window_seconds": 10.0}
            if method == CURRENT_ACCELERATED_METHOD
            else {}
        ),
        "target_scan_actions": scans,
        "target_verify_opportunities": verifies,
    }


def _new_output_root() -> Path:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite existing physical output: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    return OUTPUT


def run_arc_leg(
    *,
    current,
    contract: dict[str, Any],
    inputs: dict[str, Any],
    calibrator,
    destination: Path,
) -> dict[str, Any]:
    """Wire the ARC plugin to the same physical runtime capabilities."""

    job = preregistered_job(current, contract, ARC_PHYSICAL_METHOD)
    task_id = str(job["task_id"])
    video_id, query_id = task_id.split("_")
    units = inputs["deadline_runtime"].load_units(video_id)
    raw_dir = destination / "raw"
    attempt = current.next_attempt(raw_dir, job)
    run_id = (
        f"{ARC_PHYSICAL_METHOD}__Y8__{task_id}__"
        f"{job['deadline_name']}__r00__{attempt.name}"
    )
    run_start_ns = time.perf_counter_ns()
    ledger = ActionLedger(attempt / "ACTION_LEDGER.jsonl", run_start_ns)
    ledger.append(
        "RUN_STARTED",
        run_id=run_id,
        deadline_seconds=job["deadline_seconds"],
        clock_boundary="before_service_and_model_initialization",
    )
    materializer = oracle = engine = None
    active_session = False
    queried_results: list[dict[str, Any]] = []
    raw_candidates: list[dict[str, Any]] = []
    final_score_rows: list[dict[str, Any]] = []
    proxy_unit_costs: list[dict[str, Any]] = []
    scan_index = 0
    checkpoint_index = 0
    try:
        materializer = start_materializer_service(MATERIALIZER)
        initial_snapshot_path = attempt / "checkpoint_000_snapshot.json"
        initial_events, initial_commit = materialize_and_commit(
            materializer_path=MATERIALIZER,
            materializer_service=materializer,
            units=units,
            queried_rows=[],
            snapshot_path=initial_snapshot_path,
            run_config={
                "benchmark_id": task_id,
                "run_id": run_id,
                "method": ARC_PHYSICAL_METHOD,
                "method_variant": ARC_PHYSICAL_METHOD,
                "seed": 0,
                "horizon_budget": 0,
            },
        )
        initial_checkpoint = {
            "checkpoint_index": 0,
            "action": "initial_commit",
            "elapsed_seconds": (time.perf_counter_ns() - run_start_ns) / 1e9,
            "physical_oracle_calls": 0,
            "confirmed_events": len(initial_events),
            "snapshot_path": str(initial_snapshot_path),
            "commit": initial_commit,
            "frontier_candidates": 0,
            "frontier_unique_temporal_cells": 0,
            "frontier_temporal_entropy": 0.0,
        }
        ledger.append(
            "INITIAL_SNAPSHOT_DURABLY_COMMITTED",
            snapshot_path=str(initial_snapshot_path),
        )
        checkpoint_index = 1
        oracle = start_two_video_physical_oracle_service(
            inputs["oracle_configuration"]
        )
        accessor, oracle_initialization = oracle.start_session(
            run_id, video_id, query_id
        )
        active_session = True
        proxy_runtime = current.proxy_module()
        prereg = json.loads(current.PREREG.read_text())
        prereg.update(inputs["proxy_prereg_overrides"])
        engine = proxy_runtime.UnitProxyEngine(
            "Y8", video_id, Path(inputs["video_paths"][video_id]), prereg
        )
        synthetic = np.zeros((1080, 1920, 3), dtype=np.uint8)
        warmups = []
        for warmup_index in range(3):
            started = time.perf_counter_ns()
            *_, gpu_seconds = engine.detector.detect(synthetic)
            warmups.append({
                "warmup_index": warmup_index,
                "wall_seconds": (time.perf_counter_ns() - started) / 1e9,
                "detector_gpu_seconds": float(gpu_seconds),
            })

        policy = ARCPhysicalPolicy(
            units.unit_id.astype(int).tolist(),
            query_id=query_id,
            seed=int(job["replicate"]),
            calibrator=calibrator,
            config=ARCConfig(),
        )
        action_profile, commit_profile = current.load_profiles(video_id, query_id)
        guard = TailAwareDeadlineGuard(action_profile.identity)

        def scan_unit(unit: dict[str, Any]) -> dict[str, Any]:
            nonlocal scan_index
            result = engine.scan_unit(unit)
            raw_candidates.extend(result["candidates"])
            durable_json(attempt / f"scan_{scan_index:03d}_proxy.json", {
                "run_id": run_id,
                "scan_result": result,
                "future_proxy_accesses": 0,
            })
            proxy_unit_costs.append({
                key: value
                for key, value in result.items()
                if key not in {"candidates", "frame_costs"}
            })
            scan_index += 1
            return result

        def finalize_proxy_scores(scans: list[dict[str, Any]]) -> list[float]:
            nonlocal final_score_rows
            del scans
            candidates = pd.DataFrame(raw_candidates)
            if candidates.empty:
                candidates = pd.DataFrame(columns=[
                    "video_id", "query_id", "unit_id", "track_id", "class_id",
                    "observations", *proxy_runtime.BASE_FEATURES,
                    *proxy_runtime.GEOMETRY_FEATURES,
                ])
            _, score_frame = proxy_runtime.score_candidates(candidates, "Y8", units)
            rows = score_frame[score_frame.query_id == query_id].sort_values("unit_id")
            final_score_rows = rows.astype(object).where(pd.notna(rows), None).to_dict(
                "records"
            )
            durable_json(attempt / "COMPLETE_PROXY_SCORES.json", {
                "run_id": run_id,
                "unit_scores": rows.to_dict("records"),
                "complete_online_pass": True,
                "future_proxy_accesses": 0,
            })
            return rows.unit_score.astype(float).tolist()

        def query_oracle(unit_id: int) -> dict[str, Any]:
            started = time.perf_counter_ns()
            result = accessor.query(int(unit_id))
            ended = time.perf_counter_ns()
            queried_results.append({
                "unit_id": int(unit_id),
                "parsed_label": result.get("parsed_label", "unusable"),
                "generic_parsed_label": result.get("generic_parsed_label", "unusable"),
                "confidence": result.get("confidence", "unknown"),
                "parse_status": result.get("parse_status", "missing"),
                "query_start_seconds": (started - run_start_ns) / 1e9,
                "query_end_seconds": (ended - run_start_ns) / 1e9,
                "oracle_inference_seconds": float(
                    result.get("stage_seconds", {}).get("oracle_inference", 0.0)
                ),
                "service_total_seconds": float(result.get("service_total_seconds", 0.0)),
                "physical_oracle_invocation": result.get("physical_oracle_invocation"),
                "cache_replay": result.get("cache_replay"),
            })
            return result

        def commit_snapshot(
            queried_rows: list[dict[str, Any]],
            action: str,
            raw_observation: dict[str, Any] | None,
        ) -> dict[str, Any]:
            nonlocal checkpoint_index
            snapshot = attempt / f"checkpoint_{checkpoint_index:03d}_snapshot.json"
            raw_path = (
                attempt / f"query_{len(queried_results) - 1:03d}_oracle.json"
                if raw_observation is not None
                else None
            )
            events, commit = materialize_and_commit(
                materializer_path=MATERIALIZER,
                materializer_service=materializer,
                units=units,
                queried_rows=queried_rows,
                snapshot_path=snapshot,
                run_config={
                    "benchmark_id": task_id,
                    "run_id": run_id,
                    "method": ARC_PHYSICAL_METHOD,
                    "method_variant": ARC_PHYSICAL_METHOD,
                    "seed": 0,
                    "horizon_budget": len(queried_rows),
                },
                raw_observation=(
                    None if raw_observation is None else {"oracle_result": raw_observation}
                ),
                raw_observation_path=raw_path,
            )
            checkpoint_index += 1
            return {
                "snapshot_path": str(snapshot),
                "confirmed_events": len(events),
                "commit": commit,
                "frontier_candidates": 0,
                "frontier_unique_temporal_cells": 0,
                "frontier_temporal_entropy": 0.0,
                "action_detail": action,
            }

        def admit_verify(elapsed: float) -> dict[str, Any]:
            return guard.decide(
                deadline_seconds=float(job["deadline_seconds"]),
                elapsed_seconds=float(elapsed),
                now_utc=current.now_utc(),
                action_profile=action_profile,
                commit_profile=commit_profile,
            ).to_dict()

        def synchronize() -> None:
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()

        runtime = ARCPhysicalRuntime(
            policy=policy,
            units=units.to_dict("records"),
            deadline_seconds=float(job["deadline_seconds"]),
            run_start_ns=run_start_ns,
            scan_upper_seconds=current.proxy_scan_upper_seconds("Y8"),
            commit_upper_seconds=commit_profile.tail_bound().upper_seconds,
            scan_unit=scan_unit,
            finalize_proxy_scores=finalize_proxy_scores,
            query_oracle=query_oracle,
            commit_snapshot=commit_snapshot,
            admit_verify=admit_verify,
            final_synchronize=synchronize,
            record_event=lambda event, fields: ledger.append(event, **fields),
            initial_checkpoint=initial_checkpoint,
        )
        arc_result = runtime.run().to_dict()
        for stored, normalized in zip(
            queried_results, policy.diagnostics()["physical_observations"]
        ):
            stored["parsed_label"] = normalized["outcome"]
        session_summary = oracle.end_session(run_id)
        active_session = False
        result = {
            "status": "ok",
            "run_id": run_id,
            "job": job,
            "method": ARC_PHYSICAL_METHOD,
            "family": "Y8",
            "task_id": task_id,
            "deadline_name": job["deadline_name"],
            "deadline_seconds": float(job["deadline_seconds"]),
            "replicate": 0,
            "oracle_session_initialization": oracle_initialization,
            "oracle_session_summary": session_summary,
            "proxy_predeadline_warmup": warmups,
            "snapshot_elapsed_seconds": arc_result["snapshot_elapsed_seconds"],
            "total_run_wall_seconds": arc_result["total_elapsed_seconds"],
            "deadline_met": arc_result["deadline_met"],
            "stop_reason": arc_result["stop_reason"],
            "scan_actions": arc_result["scan_actions"],
            "scan_order_prefix": list(range(arc_result["scan_actions"])),
            "verify_opportunities": arc_result["logical_oracle_calls"],
            "target_scan_actions": len(units),
            "target_verify_opportunities": arc_result["logical_oracle_calls"],
            "verify_rejected": int("verify_not_admitted" in arc_result["stop_reason"]),
            "physical_oracle_calls": arc_result["logical_oracle_calls"],
            "cache_replay_calls": 0,
            "queried_rows": policy.comparable_queried_rows(),
            "queried_results": queried_results,
            "proxy_unit_costs": proxy_unit_costs,
            "proxy_gpu_seconds": sum(
                float(row["detector_gpu_seconds"]) for row in warmups
            ) + sum(
                float(action.get("detector_gpu_seconds", 0.0))
                for action in proxy_unit_costs
            ),
            "oracle_gpu_seconds": sum(
                float(row["oracle_inference_seconds"]) for row in queried_results
            ),
            "total_gpu_seconds": sum(
                float(row["detector_gpu_seconds"]) for row in warmups
            ) + sum(
                float(action.get("detector_gpu_seconds", 0.0))
                for action in proxy_unit_costs
            ) + sum(float(row["oracle_inference_seconds"]) for row in queried_results),
            "scheduler_cpu_seconds": 0.0,
            "score_history": [
                {
                    "unit_id": int(row["unit_id"]),
                    "unit_score": float(probability),
                    "raw_proxy_score": float(row["unit_score"]),
                    "top_track_id": row.get("top_track_id"),
                }
                for row, probability in zip(
                    final_score_rows,
                    [] if arc_result["proxy_summary"] is None else arc_result[
                        "proxy_summary"
                    ]["calibrated_probabilities"],
                )
            ],
            "candidate_lifecycle": [],
            "actions": arc_result["actions"],
            "checkpoints": arc_result["checkpoints"],
            "final_snapshot_path": arc_result["checkpoints"][-1]["snapshot_path"],
            "future_proxy_accesses": 0,
            "candidate_observation_violations": 0,
            "reference_visibility_violations": 0,
            "arc_physical": arc_result,
            "clock_accounting": {
                "boundary": "before materializer/oracle/proxy initialization",
                "charged": [
                    "service/model loading", "video open/decode", "warm-up", "SCAN",
                    "complete scoring", "calibration", "Jensen-Shannon clustering",
                    "ARC controller", "VERIFY", "K3", "serialization", "fsync",
                    "atomic commit", "final CUDA synchronization",
                ],
            },
        }
        result["action_ledger_path"] = str(attempt / "ACTION_LEDGER.jsonl")
        result["action_ledger_sha256"] = sha256_file(attempt / "ACTION_LEDGER.jsonl")
        durable_json(attempt / "complete.json", result)
        return result
    except Exception as exc:
        durable_json(attempt / "failed.json", {
            "status": "failed",
            "run_id": run_id,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": (time.perf_counter_ns() - run_start_ns) / 1e9,
        })
        raise
    finally:
        if engine is not None:
            engine.close()
        if active_session:
            try:
                oracle.end_session(run_id)
            except Exception:
                pass
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()


def run_current_leg(
    *,
    current,
    current_method_runner,
    contract: dict[str, Any],
    inputs: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    """Execute exactly H-STAGE1 through its selected wrapper and base runtime."""

    job = preregistered_job(
        current,
        contract,
        CURRENT_ACCELERATED_METHOD,
        current_method_runner=current_method_runner,
    )
    raw = destination / "raw"
    config = current.build_config("ARC_PHYSICAL_PAIRED_SMOKE_CURRENT", [job])
    run_start_ns = time.perf_counter_ns()
    materializer = policy = oracle = None
    try:
        materializer = start_materializer_service(MATERIALIZER)
        video_id, _ = str(job["task_id"]).split("_")
        units = inputs["deadline_runtime"].load_units(video_id)
        attempt = current.next_attempt(raw, job)
        run_id = (
            f"{job['method']}__{job['family']}__{job['task_id']}__"
            f"{job['deadline_name']}__r{int(job['replicate']):02d}__{attempt.name}"
        )
        ledger = ActionLedger(attempt / "ACTION_LEDGER.jsonl", run_start_ns)
        ledger.append(
            "RUN_STARTED",
            run_id=run_id,
            deadline_seconds=job["deadline_seconds"],
            config_hash=config["config_hash"],
            clock_boundary="before_service_and_model_initialization",
        )
        initial_snapshot_path = attempt / "checkpoint_000_snapshot.json"
        initial_events, _ = materialize_and_commit(
            materializer_path=MATERIALIZER,
            materializer_service=materializer,
            units=units,
            queried_rows=[],
            snapshot_path=initial_snapshot_path,
            run_config={
                "benchmark_id": job["task_id"],
                "run_id": run_id,
                "method": job["method"],
                "method_variant": job["method"],
                "seed": int(job["replicate"]),
                "horizon_budget": 0,
            },
        )
        initial_checkpoint = {
            "checkpoint_index": 0,
            "action": "initial_commit",
            "elapsed_seconds": (time.perf_counter_ns() - run_start_ns) / 1e9,
            "snapshot_path": str(initial_snapshot_path),
            "confirmed_events": len(initial_events),
            "physical_oracle_calls": 0,
            "observed_units": 0,
            "temporal_coverage": 0.0,
            "frontier_candidates": 0,
            "frontier_unique_temporal_cells": 0,
            "frontier_temporal_entropy": 0.0,
        }
        ledger.append(
            "INITIAL_SNAPSHOT_DURABLY_COMMITTED",
            snapshot_path=str(initial_snapshot_path),
        )
        policy = current.start_exposure_policy_service()
        oracle = start_two_video_physical_oracle_service(
            inputs["oracle_configuration"]
        )
        return current.run_one(
            job=job,
            raw=raw,
            config=config,
            oracle=oracle,
            materializer=materializer,
            policy=policy,
            proxy_runtime=current.proxy_module(),
            deadline_runtime=inputs["deadline_runtime"],
            run_start_ns=run_start_ns,
            runtime_input_overrides={
                "video_paths": inputs["video_paths"],
                "proxy_prereg_overrides": inputs["proxy_prereg_overrides"],
                "require_final_cuda_synchronize": True,
            },
            attempt_override=attempt,
            ledger_override=ledger,
            initial_checkpoint_override=initial_checkpoint,
        )
    finally:
        if policy is not None:
            policy.close()
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()


def paired_smoke(calibrator_manifest: Path) -> None:
    contract = audit_shared_contract(ROOT)
    final_proxy = json.loads(Path(contract["proxy_config"]).read_text())
    # This gate must precede GPU imports, model loading, and video access.
    calibrator = load_deployable_calibrator(
        calibrator_manifest,
        expected_proxy_family="Y8",
        expected_proxy_config_hash=final_proxy["final_proxy_config_hash"],
    )
    current = load_module("arc_phys_current_runner", CURRENT_RUNNER)
    current_method_runner = load_module(
        "arc_phys_current_method_runner", CURRENT_METHOD_RUNNER
    )
    inputs = resolve_physical_inputs(contract, current)
    destination = _new_output_root()
    durable_json(destination / "SHARED_CONTRACT.json", contract)
    arc = run_arc_leg(
        current=current,
        contract=contract,
        inputs=inputs,
        calibrator=calibrator,
        destination=destination / "arc",
    )
    current_result = run_current_leg(
        current=current,
        current_method_runner=current_method_runner,
        contract=contract,
        inputs=inputs,
        destination=destination / "current",
    )
    evaluator = load_module(
        "arc_phys_shared_evaluator",
        ROOT / "scripts/evaluate_psvr_two_video_physical.py",
    )
    arc_metrics = evaluator.evaluate_raw(
        destination / "arc/raw", destination / "arc/tables"
    )
    current_metrics = evaluator.evaluate_raw(
        destination / "current/raw", destination / "current/tables"
    )
    if len(arc_metrics) != 1 or len(current_metrics) != 1:
        raise RuntimeError("paired smoke evaluator did not return exactly one row per method")
    paired_metrics = {
        "evaluator": contract["evaluator"],
        "evaluator_sha256": contract["evaluator_sha256"],
        "task_id": contract["smoke_cell"]["task_id"],
        "deadline_name": contract["smoke_cell"]["deadline_name"],
        "arc": arc_metrics.iloc[0].astype(object).where(
            pd.notna(arc_metrics.iloc[0]), None
        ).to_dict(),
        "current": current_metrics.iloc[0].astype(object).where(
            pd.notna(current_metrics.iloc[0]), None
        ).to_dict(),
    }
    durable_json(destination / "PAIRED_SMOKE_METRICS.json", paired_metrics)
    checks = {
        "task_identity_equal": arc["task_id"] == current_result["task_id"],
        "deadline_identity_equal": (
            arc["deadline_name"], arc["deadline_seconds"]
        ) == (current_result["deadline_name"], current_result["deadline_seconds"]),
        "zero_reference_visibility": (
            arc["reference_visibility_violations"]
            + current_result["reference_visibility_violations"] == 0
        ),
        "zero_duplicate_calls": (
            len({row["unit_id"] for row in arc["queried_results"]})
            == len(arc["queried_results"])
            and len({row["unit_id"] for row in current_result["queried_results"]})
            == len(current_result["queried_results"])
        ),
        "durable_snapshots_exist": all(
            Path(row["final_snapshot_path"]).is_file() for row in (arc, current_result)
        ),
        "same_evaluator": (
            paired_metrics["evaluator_sha256"] == contract["evaluator_sha256"]
        ),
    }
    checks["paired_smoke_pass"] = all(checks.values())
    durable_json(destination / "PAIRED_SMOKE_CHECKS.json", checks)
    print(json.dumps(checks, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("audit-contract")
    smoke = sub.add_parser("paired-smoke")
    smoke.add_argument("--calibrator-manifest", type=Path, default=READINESS)
    args = parser.parse_args()
    if args.stage == "audit-contract":
        print(json.dumps(audit_shared_contract(ROOT), indent=2, sort_keys=True))
    else:
        paired_smoke(args.calibrator_manifest)


if __name__ == "__main__":
    main()
