#!/usr/bin/env python3
"""Run neutral proxy-family and H-EXPOSE2 physical PSVR matrices.

This trusted runtime never opens task references.  Evaluation is a separate
subcommand in ``evaluate_psvr_two_video_physical.py`` after all physical
services have stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.psvr_exposure import start_exposure_policy_service
from garc_eval.mf_psvr import CandidateIdentity, bind_track_witness
from garc_eval.psvr_runtime import (
    ActionLedger,
    TailAwareDeadlineGuard,
    TailLatencyProfile,
    durable_json,
    materialize_and_commit,
    start_materializer_service,
    start_two_video_physical_oracle_service,
)


OUT = ROOT / "outputs/psvr_two_video_loop"
DEV = OUT / "dev_benchmark_v1"
DEADLINE_DIR = OUT / "deadlines"
DEADLINE_MANIFEST = DEADLINE_DIR / "TASK_DEADLINE_MANIFEST.json"
PROXY_DIR = OUT / "proxy_finalization"
PILOT = PROXY_DIR / "neutral_psvr"
EXPOSE = OUT / "h_expose2"
ABLATION = OUT / "h_expose2_ablation"
FINAL_PROXY = OUT / "final_proxy"
MATERIALIZER = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
)
PROXY_SCRIPT = ROOT / "scripts/run_psvr_two_video_proxy.py"
DEADLINE_SCRIPT = ROOT / "scripts/freeze_psvr_two_video_deadlines.py"
PREREG = PROXY_DIR / "H_PROXY_2VIDEO_PREREGISTRATION.json"
IMPLEMENTATION_FREEZE = PROXY_DIR / "PROXY_IMPLEMENTATION_FREEZE.json"
PILOT_CANDIDATES = PILOT / "PILOT_CANDIDATES.json"
VERIFY_EVERY_N_SCANS = 3
CANDIDATE_CAPACITY = 10


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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def proxy_module():
    return load_module("psvr_two_video_proxy_runtime", PROXY_SCRIPT)


def deadline_module():
    return load_module("psvr_two_video_deadline_runtime", DEADLINE_SCRIPT)


def public_units(units: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "unit_id": int(row.unit_id),
            "start_time": float(row.start_time),
            "end_time": float(row.end_time),
            "duration_seconds": float(row.duration_seconds),
        }
        for row in units.itertuples()
    ]


def uniform_temporal_order(unit_count: int) -> list[int]:
    observed: set[int] = set()
    order = []
    while len(order) < unit_count:
        blocks = []
        start = None
        for unit_id in range(unit_count):
            if unit_id not in observed and start is None:
                start = unit_id
            if unit_id in observed and start is not None:
                blocks.append((start, unit_id - 1))
                start = None
        if start is not None:
            blocks.append((start, unit_count - 1))
        left, right = max(
            blocks, key=lambda pair: (pair[1] - pair[0] + 1, -pair[0])
        )
        chosen = (left + right) // 2
        observed.add(chosen)
        order.append(chosen)
    return order


def coverage_recovery_order(units: pd.DataFrame) -> list[int]:
    """Reference-blind farthest-center traversal with frozen midpoint start."""

    centers = {
        int(row.unit_id): 0.5 * (float(row.start_time) + float(row.end_time))
        for row in units.itertuples()
    }
    first = uniform_temporal_order(len(units))[0]
    order = [int(first)]
    unseen = set(centers) - {int(first)}
    while unseen:
        chosen = max(
            unseen,
            key=lambda unit_id: (
                min(
                    abs(centers[unit_id] - centers[observed])
                    for observed in order
                ),
                -centers[unit_id],
                -unit_id,
            ),
        )
        order.append(int(chosen))
        unseen.remove(chosen)
    return order


def stage_conditioned_should_verify(
    *,
    completed_scans: int,
    coarse_cell_count: int,
    persistent_candidate_count: int,
    retained_temporal_cells: int,
) -> bool:
    """Pure observable-state decision used by H-STAGE1 after a durable SCAN."""

    if (
        completed_scans < coarse_cell_count
        and persistent_candidate_count < CANDIDATE_CAPACITY
    ):
        return False
    if retained_temporal_cells <= 1 or persistent_candidate_count == 0:
        return False
    return True


def task_deadline(task_id: str, deadline_name: str) -> float:
    manifest = json.loads(DEADLINE_MANIFEST.read_text(encoding="utf-8"))
    row = next(row for row in manifest["tasks"] if row["task_id"] == task_id)
    return float(row[deadline_name])


def load_profiles(
    video_id: str, query_id: str
) -> tuple[TailLatencyProfile, TailLatencyProfile]:
    directory = DEADLINE_DIR / "profiles" / f"{video_id}_{query_id}"
    return (
        TailLatencyProfile.from_dict(
            json.loads((directory / "action_profile.json").read_text())
        ),
        TailLatencyProfile.from_dict(
            json.loads((directory / "commit_profile.json").read_text())
        ),
    )


def load_units(video_id: str, deadline_runtime) -> pd.DataFrame:
    return deadline_runtime.load_units(video_id)


def proxy_scan_upper_seconds(family: str) -> float:
    report = json.loads(
        (PROXY_DIR / "physical_cost" / f"{family}_PHYSICAL_COST.json").read_text()
    )
    frame_p95 = float(report["p95_latency_ms"]) / 1000
    return max(2.0, 1.5 * frame_p95 * 50 + 1.0)


def planned_scan_actions(
    family: str, task_id: str, deadline_name: str
) -> tuple[int, int]:
    video_id, query_id = task_id.split("_")
    deadline = task_deadline(task_id, deadline_name)
    action, commit = load_profiles(video_id, query_id)
    scan_upper = proxy_scan_upper_seconds(family)
    commit_upper = commit.tail_bound().upper_seconds
    cycle_upper = (
        VERIFY_EVERY_N_SCANS * (scan_upper + commit_upper)
        + action.tail_bound().upper_seconds
        + commit_upper
    )
    usable = (
        deadline
        - commit_upper
        - 1.0
    )
    cycles = max(0, int(math.floor(usable / cycle_upper)))
    if cycles < 1:
        raise RuntimeError(
            f"{family} {task_id} {deadline_name} cannot fit one planned A0 cycle"
        )
    return cycles * VERIFY_EVERY_N_SCANS, cycles


def freeze_pilot_candidates() -> None:
    offline = pd.read_csv(PROXY_DIR / "tables/OFFLINE_MACRO_METRICS.csv").set_index(
        "family"
    )
    costs = {
        family: json.loads(
            (PROXY_DIR / "physical_cost" / f"{family}_PHYSICAL_COST.json").read_text()
        )
        for family in ("Y8", "YP640", "YP320")
    }
    quality_columns = [
        "unit_auprc",
        "unique_event_recall@20",
        "positive_event_exposure_auc",
    ]

    def dominates(left: str, right: str) -> bool:
        quality_no_worse = all(
            float(offline.loc[left, column]) >= float(offline.loc[right, column])
            for column in quality_columns
        )
        cost_no_worse = float(costs[left]["gpu_seconds_per_video_hour"]) <= float(
            costs[right]["gpu_seconds_per_video_hour"]
        )
        strict = any(
            float(offline.loc[left, column]) > float(offline.loc[right, column])
            for column in quality_columns
        ) or float(costs[left]["gpu_seconds_per_video_hour"]) < float(
            costs[right]["gpu_seconds_per_video_hour"]
        )
        return quality_no_worse and cost_no_worse and strict

    yolop = [
        family
        for family in ("YP640", "YP320")
        if not any(
            dominates(other, family)
            for other in ("YP640", "YP320")
            if other != family
        )
    ]
    candidates = ["Y8", *yolop]
    freeze = {
        "freeze_id": "H_PROXY_2VIDEO_NEUTRAL_PILOT_CANDIDATES_V1",
        "frozen_at_utc": now_utc(),
        "offline_metrics_sha256": sha256_file(
            PROXY_DIR / "tables/OFFLINE_MACRO_METRICS.csv"
        ),
        "physical_cost_sha256": {
            family: sha256_file(
                PROXY_DIR / "physical_cost" / f"{family}_PHYSICAL_COST.json"
            )
            for family in ("Y8", "YP640", "YP320")
        },
        "pareto_quality_columns": quality_columns,
        "pareto_cost_column": "gpu_seconds_per_video_hour",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "maximum_allowed": 3,
        "scanner": "Uniform-Temporal-Interleave",
        "scanner_resolution": {
            "rule": "iterative largest-unobserved-gap midpoint; lower midpoint tie",
            "source": str(SRC / "garc_eval/psvr_pilot/policy_service.py"),
            "source_sha256": sha256_file(
                SRC / "garc_eval/psvr_pilot/policy_service.py"
            ),
        },
        "verify_allocator": {
            "name": "A0 Fixed-Periodic",
            "verify_every_n_scanned_units": VERIFY_EVERY_N_SCANS,
            "resolution_source": str(
                ROOT / "scripts/run_psvr_proxy_pilot.py"
            ),
            "resolution_source_sha256": sha256_file(
                ROOT / "scripts/run_psvr_proxy_pilot.py"
            ),
        },
        "frontier": "score_only",
        "candidate_capacity": CANDIDATE_CAPACITY,
        "candidate_capacity_rationale": (
            "10 is the smallest preregistered offline ranking cutoff and is small enough for "
            "retention pressure to become observable under fixed-periodic high-deadline schedules; "
            "it was frozen before task deadlines or any proxy/reference outcome."
        ),
        "reference_outcome_used": False,
        "heldout_opened": False,
    }
    freeze["freeze_hash"] = canonical_hash(freeze)
    PILOT.mkdir(parents=True, exist_ok=True)
    if PILOT_CANDIDATES.exists():
        existing = json.loads(PILOT_CANDIDATES.read_text())
        unstable = {"frozen_at_utc", "freeze_hash"}
        if (
            {k: v for k, v in existing.items() if k not in unstable}
            != {k: v for k, v in freeze.items() if k not in unstable}
        ):
            raise RuntimeError("Neutral proxy pilot candidates changed after freeze")
        freeze = existing
    else:
        durable_json(PILOT_CANDIDATES, freeze)
    print(json.dumps(freeze, indent=2))


def next_attempt(raw: Path, job: dict[str, Any]) -> Path:
    root = raw / (
        f"{job['method']}__{job['family']}__{job['task_id']}__"
        f"{job['deadline_name']}__replicate_{int(job['replicate']):02d}"
    )
    root.mkdir(parents=True, exist_ok=True)
    existing = sorted(root.glob("attempt_*"))
    index = 1 if not existing else max(
        int(path.name.rsplit("_", 1)[1]) for path in existing
    ) + 1
    destination = root / f"attempt_{index:03d}"
    destination.mkdir()
    return destination


def job_completed(raw: Path, job: dict[str, Any]) -> bool:
    pattern = (
        f"{job['method']}__{job['family']}__{job['task_id']}__"
        f"{job['deadline_name']}__replicate_{int(job['replicate']):02d}"
        "/attempt_*/complete.json"
    )
    return any(
        json.loads(path.read_text()).get("status") == "ok"
        for path in raw.glob(pattern)
    )


def build_config(kind: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text())
    deadline = json.loads(DEADLINE_MANIFEST.read_text())
    implementation = json.loads(IMPLEMENTATION_FREEZE.read_text())
    final_proxy_config = (
        json.loads((FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
        if (FINAL_PROXY / "FINAL_PROXY_CONFIG.json").exists()
        else None
    )
    if kind == "H_EXPOSE2_PHYSICAL_V1":
        job_scope = {
            "methods": ["fifo", "score_only", "exposure_aware"],
            "families": sorted({job["family"] for job in jobs}),
            "tasks": ["V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"],
            "deadlines": ["T_transition", "T_high"],
            "replicates": [0, 1, 2],
            "smoke_prefix": "T_transition replicate 0",
        }
    elif kind == "H_PROXY_2VIDEO_NEUTRAL_PHYSICAL_V1":
        frozen = json.loads(PILOT_CANDIDATES.read_text())
        job_scope = {
            "methods": ["score_only"],
            "families": frozen["candidates"],
            "tasks": ["V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"],
            "deadlines": ["T_transition", "T_high"],
            "replicates": [0, 1, 2],
            "smoke_prefix": "T_transition replicate 0",
        }
    else:
        job_scope = {
            "methods": sorted({job["method"] for job in jobs}),
            "families": sorted({job["family"] for job in jobs}),
            "tasks": sorted({job["task_id"] for job in jobs}),
            "deadlines": sorted({job["deadline_name"] for job in jobs}),
            "replicates": sorted({int(job["replicate"]) for job in jobs}),
        }
        if any("scan_policy" in job or "verify_policy" in job for job in jobs):
            job_scope["method_definitions"] = {
                str(method): {
                    "scan_policy": next(
                        str(job["scan_policy"])
                        for job in jobs if job["method"] == method
                    ),
                    "verify_policy": next(
                        str(job["verify_policy"])
                        for job in jobs if job["method"] == method
                    ),
                    "action_policy": next(
                        str(job.get("action_policy", "fixed_periodic"))
                        for job in jobs if job["method"] == method
                    ),
                }
                for method in sorted({job["method"] for job in jobs})
            }
    config = {
        "experiment_id": kind,
        "job_scope": job_scope,
        "oracle": "physical cache-free Qwen3-VL-32B frozen generic prompt plus frozen projection",
        "oracle_model_persistence": "resident across runs",
        "oracle_logical_session": "fresh query ledger per run",
        "proxy": "cold physical detector per run",
        "proxy_preregistration_hash": prereg["preregistration_hash"],
        "proxy_implementation_freeze_hash": implementation["freeze_hash"],
        "final_proxy_config_hash": (
            None
            if final_proxy_config is None
            else final_proxy_config["final_proxy_config_hash"]
        ),
        "deadline_manifest_hash": deadline["manifest_hash"],
        "scanner": "Uniform-Temporal-Interleave",
        "uniform_temporal_order": "iterative largest-unobserved-gap midpoint; lower midpoint tie",
        "verify_allocator": "A0 Fixed-Periodic",
        "verify_every_n_scanned_units": VERIFY_EVERY_N_SCANS,
        "candidate_capacity": CANDIDATE_CAPACITY,
        "K3": "unchanged k3_bridge_safe persistent clean spawn",
        "snapshot_checkpoint": "after every SCAN or VERIFY plus initial empty snapshot",
        "implementation_hashes": {
            "runner": sha256_file(Path(__file__)),
            "proxy": sha256_file(PROXY_SCRIPT),
            "deadline": sha256_file(DEADLINE_SCRIPT),
            "policy": sha256_file(
                SRC / "garc_eval/psvr_exposure/policy_service.py"
            ),
            "oracle_service": sha256_file(
                SRC / "garc_eval/psvr_runtime/two_video_physical_oracle.py"
            ),
            "runtime_runner": sha256_file(
                SRC / "garc_eval/psvr_runtime/runner.py"
            ),
            "materializer": sha256_file(MATERIALIZER),
        },
        "reference_visible_to_runtime": False,
        "heldout_opened": False,
    }
    experiment_hashes = {
        str(job["experiment_preregistration_hash"])
        for job in jobs if "experiment_preregistration_hash" in job
    }
    if experiment_hashes:
        if len(experiment_hashes) != 1:
            raise RuntimeError("multiple experiment preregistration hashes in one matrix")
        config["experiment_preregistration_hash"] = next(iter(experiment_hashes))
    if any("scan_policy" in job for job in jobs):
        config["scanner"] = "H-BOTTLE2 factorial S0/S1"
        config["scan_policy_definitions"] = {
            "S0": "exact frozen uniform-temporal contiguous-block midpoint",
            "S1": "midpoint start then farthest observed-center distance",
        }
    if any("verify_policy" in job for job in jobs):
        config["frontier_policy_definitions"] = {
            "fifo": "oldest candidate creation first",
            "cell_diverse_conservative": (
                "one candidate per frozen unit-cell; within-cell proxy max; "
                "cell FIFO; unit/K3-derived confirmed exclusion"
            ),
        }
    if any(job.get("action_policy") == "stage_conditioned_v1" for job in jobs):
        config["verify_allocator"] = "observable stage-conditioned v1"
        config["stage_conditioned_definition"] = {
            "coarse_cell_count": "ceil(sqrt(frozen unit count))",
            "persistent_candidate": "retained candidate created before current scan",
            "candidate_threshold": CANDIDATE_CAPACITY,
            "verify_inadmissible_fallback": "continue safe max-gap scan",
        }
    config["config_hash"] = canonical_hash(config)
    return config


def causal_unit_candidates(
    *,
    proxy_runtime,
    raw_candidates: list[dict[str, Any]],
    family: str,
    query_id: str,
    units: pd.DataFrame,
    observed_unit_ids: set[int],
    queried_unit_ids: set[int],
    discarded_unit_ids: set[int],
    creation_scan_index: dict[int, int],
    candidate_track_bindings: dict[int, int],
    score_availability_seconds: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not raw_candidates:
        return [], []
    candidates = pd.DataFrame(raw_candidates)
    observed_units = units[units.unit_id.astype(int).isin(observed_unit_ids)].copy()
    scored_candidates, unit_scores = proxy_runtime.score_candidates(
        candidates, family, observed_units
    )
    query_candidates = scored_candidates[
        scored_candidates["query_id"] == query_id
    ].copy()
    candidate_by_identity = {
        (int(row["unit_id"]), int(row["track_id"])): row
        for row in query_candidates.to_dict("records")
    }
    evidence_features = list(proxy_runtime.BASE_FEATURES)
    if family.startswith("YP"):
        evidence_features.extend(proxy_runtime.GEOMETRY_FEATURES)
    scores = unit_scores[unit_scores.query_id == query_id].copy()
    rows = []
    score_history = []
    for row in scores.to_dict("records"):
        unit_id = int(row["unit_id"])
        proposed_track_id = (
            None
            if pd.isna(row["top_track_id"])
            else int(row["top_track_id"])
        )
        bound_track_id = candidate_track_bindings.get(unit_id)
        if bound_track_id is None and proposed_track_id is not None:
            bound_track_id = bind_track_witness(
                candidate_track_bindings,
                unit_id=unit_id,
                proposed_track_id=proposed_track_id,
            )
        bound_candidate = (
            None
            if bound_track_id is None
            else candidate_by_identity.get((unit_id, int(bound_track_id)))
        )
        if bound_track_id is not None and bound_candidate is None:
            raise RuntimeError(
                "bound track witness disappeared from accumulated candidate "
                f"evidence: unit={unit_id}, track={bound_track_id}"
            )
        unit_score = (
            0.0
            if bound_candidate is None
            else float(bound_candidate["candidate_score"])
        )
        evidence_json = (
            "{}"
            if bound_candidate is None
            else json.dumps(
                {
                    feature: float(bound_candidate[feature])
                    for feature in evidence_features
                },
                sort_keys=True,
            )
        )
        score_history.append({
            "unit_id": unit_id,
            "unit_score": unit_score,
            "top_track_id": bound_track_id,
            "instantaneous_top_track_id": proposed_track_id,
            "score_availability_seconds": score_availability_seconds,
            "top_track_evidence_json": evidence_json,
        })
        if (
            unit_id in queried_unit_ids
            or unit_id in discarded_unit_ids
            or bound_track_id is None
        ):
            continue
        creation_scan_index.setdefault(unit_id, len(observed_unit_ids) - 1)
        identity = CandidateIdentity(
            video_id=str(row["video_id"]),
            query_id=query_id,
            unit_id=unit_id,
            track_id=int(bound_track_id),
        )
        rows.append({
            "candidate_id": identity.candidate_id,
            "unit_id": unit_id,
            "track_id": int(bound_track_id),
            "proxy_score": unit_score,
            "creation_scan_index": int(creation_scan_index[unit_id]),
            "score_availability_seconds": score_availability_seconds,
        })
    return rows, score_history


def checkpoint_state(
    units: pd.DataFrame,
    observed: set[int],
    policy_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    observed_duration = float(
        units.loc[
            units.unit_id.astype(int).isin(observed), "duration_seconds"
        ].sum()
    )
    return {
        "observed_units": len(observed),
        "temporal_coverage": observed_duration
        / float(units.duration_seconds.sum()),
        "frontier_candidates": (
            0 if policy_decision is None else policy_decision["frontier_candidates"]
        ),
        "frontier_unique_temporal_cells": (
            0
            if policy_decision is None
            else policy_decision["frontier_unique_temporal_cells"]
        ),
        "frontier_temporal_entropy": (
            0
            if policy_decision is None
            else policy_decision["frontier_temporal_entropy"]
        ),
    }


def run_one(
    *,
    job: dict[str, Any],
    raw: Path,
    config: dict[str, Any],
    oracle,
    materializer,
    policy,
    proxy_runtime,
    deadline_runtime,
    run_start_ns: int | None = None,
    runtime_input_overrides: dict[str, Any] | None = None,
    attempt_override: Path | None = None,
    ledger_override: ActionLedger | None = None,
    initial_checkpoint_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attempt = (
        next_attempt(raw, job)
        if attempt_override is None
        else Path(attempt_override)
    )
    run_id = (
        f"{job['method']}__{job['family']}__{job['task_id']}__"
        f"{job['deadline_name']}__r{int(job['replicate']):02d}__{attempt.name}"
    )
    deadline = float(job["deadline_seconds"])
    durable_json(attempt / "started.json", {
        "status": "started",
        "run_id": run_id,
        "job": job,
        "config_hash": config["config_hash"],
        "started_at_utc": now_utc(),
    })
    video_id, query_id = job["task_id"].split("_")
    units = load_units(video_id, deadline_runtime)
    public = public_units(units)
    videos = json.loads((OUT / "VIDEO_MANIFEST.json").read_text())
    action_profile, commit_profile = load_profiles(video_id, query_id)
    guard = TailAwareDeadlineGuard(action_profile.identity)
    proxy_scan_upper = proxy_scan_upper_seconds(job["family"])
    session_id = run_id
    accessor = None
    oracle_session_initialization = None
    engine = None
    # Publication clock: oracle-session setup, proxy initialization, detector
    # warm-up, all actions, materialization, and durable commit share one hard
    # query deadline.  Historical runs deliberately remain untouched and are
    # invalidated for MF-PSVR publication comparisons by the Cycle-0 audit.
    # Paired physical integrations may start this clock before persistent
    # service/model initialization.  Legacy matrices retain their original
    # boundary when no external start is supplied.
    run_start = (
        time.perf_counter_ns() if run_start_ns is None else int(run_start_ns)
    )
    ledger = None
    active_session = False
    try:
        accessor, oracle_session_initialization = oracle.start_session(
            session_id, video_id, query_id
        )
        active_session = True
        predeadline_start = time.perf_counter_ns()
        input_overrides = runtime_input_overrides or {}
        video_path = Path(
            input_overrides.get("video_paths", {}).get(
                video_id, videos[video_id]["absolute_path"]
            )
        )
        proxy_prereg = json.loads(PREREG.read_text())
        proxy_prereg.update(input_overrides.get("proxy_prereg_overrides", {}))
        engine = proxy_runtime.UnitProxyEngine(
            job["family"],
            video_id,
            video_path,
            proxy_prereg,
        )
        proxy_initialization_seconds = (
            time.perf_counter_ns() - predeadline_start
        ) / 1e9
        warmup_rows = []
        synthetic = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for warmup_index in range(3):
            warmup_start = time.perf_counter_ns()
            *_, detector_gpu_seconds = engine.detector.detect(synthetic)
            warmup_rows.append({
                "warmup_index": warmup_index,
                "synthetic_frame": True,
                "video_frame_access": False,
                "wall_seconds": (
                    time.perf_counter_ns() - warmup_start
                ) / 1e9,
                "detector_gpu_seconds": float(detector_gpu_seconds),
            })
        proxy_predeadline_wall_seconds = (
            time.perf_counter_ns() - predeadline_start
        ) / 1e9
        proxy_warmup_gpu_seconds = sum(
            row["detector_gpu_seconds"] for row in warmup_rows
        )
        if ledger_override is None:
            ledger = ActionLedger(attempt / "ACTION_LEDGER.jsonl", run_start)
            ledger.append(
                "RUN_STARTED",
                run_id=run_id,
                deadline_seconds=deadline,
                config_hash=config["config_hash"],
            )
        else:
            ledger = ledger_override
        queried_rows: list[dict[str, Any]] = []
        queried_results: list[dict[str, Any]] = []
        raw_candidates: list[dict[str, Any]] = []
        observed_units: set[int] = set()
        discarded_units: set[int] = set()
        creation_scan_index: dict[int, int] = {}
        candidate_track_bindings: dict[int, int] = {}
        candidate_lifecycle: dict[int, dict[str, Any]] = {}
        actions: list[dict[str, Any]] = []
        checkpoints: list[dict[str, Any]] = (
            []
            if initial_checkpoint_override is None
            else [dict(initial_checkpoint_override)]
        )
        score_history: list[dict[str, Any]] = []
        proxy_unit_costs: list[dict[str, Any]] = []
        scheduler_cpu_seconds = 0.0
        scan_policy = str(job.get("scan_policy", "S0"))
        if scan_policy == "S0":
            scan_order = uniform_temporal_order(len(units))
        elif scan_policy == "S1":
            scan_order = coverage_recovery_order(units)
        else:
            raise RuntimeError(f"unknown scan policy: {scan_policy}")
        verify_policy = str(job.get("verify_policy", job["method"]))
        action_policy = str(job.get("action_policy", "fixed_periodic"))
        if action_policy not in {"fixed_periodic", "stage_conditioned_v1"}:
            raise RuntimeError(f"unknown action policy: {action_policy}")
        stage_conditioned = action_policy == "stage_conditioned_v1"
        coarse_cell_count = int(math.ceil(math.sqrt(len(units))))
        scan_cursor = 0
        scan_actions = 0
        verify_opportunities = 0
        verify_rejected = 0
        policy_decision = None
        stop_reason = "scan_exhausted"

        if initial_checkpoint_override is None:
            initial_snapshot = attempt / "checkpoint_000_snapshot.json"
            events, _ = materialize_and_commit(
                materializer_path=MATERIALIZER,
                materializer_service=materializer,
                units=units,
                queried_rows=queried_rows,
                snapshot_path=initial_snapshot,
                run_config={
                    "benchmark_id": job["task_id"],
                    "run_id": run_id,
                    "method": job["method"],
                    "method_variant": job["method"],
                    "seed": int(job["replicate"]),
                    "horizon_budget": 0,
                },
            )
            checkpoints.append({
                "checkpoint_index": 0,
                "action": "initial_commit",
                "elapsed_seconds": (time.perf_counter_ns() - run_start) / 1e9,
                "snapshot_path": str(initial_snapshot),
                "confirmed_events": len(events),
                "physical_oracle_calls": 0,
                **checkpoint_state(units, observed_units, None),
            })

        planned_target_scan_actions = int(job["target_scan_actions"])
        target_scan_actions = len(units) if stage_conditioned else planned_target_scan_actions
        while scan_cursor < len(scan_order) and scan_actions < target_scan_actions:
            elapsed = (time.perf_counter_ns() - run_start) / 1e9
            scan_required = (
                proxy_scan_upper + commit_profile.tail_bound().upper_seconds
            )
            if deadline - elapsed <= scan_required:
                stop_reason = "insufficient_scan_and_commit_reservation"
                break
            unit_id = int(scan_order[scan_cursor])
            unit = units.set_index("unit_id").loc[unit_id].to_dict()
            unit["unit_id"] = unit_id
            action_start = time.perf_counter_ns()
            scan_result = engine.scan_unit(unit)
            proxy_processing_end = time.perf_counter_ns()
            proxy_processing_wall = (
                proxy_processing_end - action_start
            ) / 1e9
            evidence_path = attempt / f"scan_{scan_actions:03d}_proxy.json"
            evidence_commit = durable_json(evidence_path, {
                "run_id": run_id,
                "family": job["family"],
                "task_id": job["task_id"],
                "proxy_config_hash": (
                    config["final_proxy_config_hash"]
                    or config["proxy_implementation_freeze_hash"]
                ),
                "proxy_processing_start_seconds": (
                    action_start - run_start
                ) / 1e9,
                "proxy_processing_end_seconds": (
                    proxy_processing_end - run_start
                ) / 1e9,
                "proxy_processing_wall_seconds": proxy_processing_wall,
                "scan_result": scan_result,
            })
            observed_units.add(unit_id)
            raw_candidates.extend(scan_result["candidates"])
            scan_actions += 1
            scan_cursor += 1
            creation_scan_index.setdefault(unit_id, scan_actions - 1)
            availability = (time.perf_counter_ns() - run_start) / 1e9
            candidates, current_scores = causal_unit_candidates(
                proxy_runtime=proxy_runtime,
                raw_candidates=raw_candidates,
                family=job["family"],
                query_id=query_id,
                units=units,
                observed_unit_ids=observed_units,
                queried_unit_ids={int(row["unit_id"]) for row in queried_rows},
                discarded_unit_ids=discarded_units,
                creation_scan_index=creation_scan_index,
                candidate_track_bindings=candidate_track_bindings,
                score_availability_seconds=availability,
            )
            score_path = attempt / f"scan_{scan_actions - 1:03d}_scores.json"
            score_commit = durable_json(score_path, {
                "run_id": run_id,
                "family": job["family"],
                "task_id": job["task_id"],
                "after_scan_action": scan_actions,
                "observed_unit_ids": sorted(observed_units),
                "score_availability_seconds": availability,
                "candidate_rows_visible_to_policy": candidates,
                "unit_score_rows": current_scores,
                "future_proxy_accesses": 0,
                "proxy_config_hash": (
                    config["final_proxy_config_hash"]
                    or config["proxy_implementation_freeze_hash"]
                ),
            })
            proxy_total_unit_wall = (
                time.perf_counter_ns() - action_start
            ) / 1e9
            score_history.extend({
                **row,
                "after_scan_action": scan_actions,
            } for row in current_scores)
            for row in candidates:
                candidate_lifecycle.setdefault(int(row["unit_id"]), {
                    "unit_id": int(row["unit_id"]),
                    "created_scan_index": int(row["creation_scan_index"]),
                    "created_seconds": availability,
                    "terminal_state": None,
                    "terminal_seconds": None,
                })
            policy_started = time.perf_counter_ns()
            policy_decision = policy.decide({
                "method": verify_policy,
                "public_units": public,
                "candidate_rows": candidates,
                "queried_rows": queried_rows,
                "pending_unit_ids": [],
                "candidate_capacity": CANDIDATE_CAPACITY,
                "current_scan_index": scan_actions,
                "parameters": job.get("parameters", {}),
            })
            scheduler_cpu_seconds += (
                time.perf_counter_ns() - policy_started
            ) / 1e9
            for candidate_id in policy_decision["discarded_candidate_ids"]:
                discarded = int(str(candidate_id).split("_")[-1])
                discarded_units.add(discarded)
                lifecycle = candidate_lifecycle.get(discarded)
                if lifecycle and lifecycle["terminal_state"] is None:
                    lifecycle["terminal_state"] = "discarded"
                    lifecycle["terminal_seconds"] = (
                        time.perf_counter_ns() - run_start
                    ) / 1e9
            snapshot_path = attempt / (
                f"checkpoint_{len(checkpoints):03d}_snapshot.json"
            )
            events, _ = materialize_and_commit(
                materializer_path=MATERIALIZER,
                materializer_service=materializer,
                units=units,
                queried_rows=queried_rows,
                snapshot_path=snapshot_path,
                run_config={
                    "benchmark_id": job["task_id"],
                    "run_id": run_id,
                    "method": job["method"],
                    "method_variant": job["method"],
                    "seed": int(job["replicate"]),
                    "horizon_budget": len(queried_rows),
                },
            )
            action_end = time.perf_counter_ns()
            scan_wall = (action_end - action_start) / 1e9
            proxy_scan_upper = max(proxy_scan_upper, 1.5 * scan_wall + 0.5)
            proxy_unit_costs.append({
                **{
                    key: value for key, value in scan_result.items()
                    if key not in {"candidates", "frame_costs"}
                },
                "scan_wall_seconds_including_evidence_and_snapshot": scan_wall,
                "proxy_processing_wall_seconds": proxy_processing_wall,
                "proxy_total_unit_wall_seconds": proxy_total_unit_wall,
                "evidence_path": str(evidence_path),
                "evidence_payload_sha256": evidence_commit["payload_sha256"],
                "score_path": str(score_path),
                "score_payload_sha256": score_commit["payload_sha256"],
            })
            checkpoint_elapsed = (time.perf_counter_ns() - run_start) / 1e9
            checkpoints.append({
                "checkpoint_index": len(checkpoints),
                "action": "scan",
                "elapsed_seconds": checkpoint_elapsed,
                "snapshot_path": str(snapshot_path),
                "confirmed_events": len(events),
                "physical_oracle_calls": len(queried_rows),
                **checkpoint_state(units, observed_units, policy_decision),
            })
            actions.append({
                "action": "scan",
                "unit_id": unit_id,
                "video_timestamp_seconds": 0.5
                * (float(unit["start_time"]) + float(unit["end_time"])),
                "start_seconds": (action_start - run_start) / 1e9,
                "score_availability_seconds": availability,
                "end_seconds": checkpoint_elapsed,
                "policy_decision_sha256": policy_decision["decision_sha256"],
                "frontier_candidate_ids": policy_decision[
                    "retained_candidate_ids"
                ],
                "future_proxy_accesses": 0,
            })
            ledger.append(
                "SCAN_DURABLY_COMMITTED",
                unit_id=unit_id,
                score_availability_seconds=availability,
                snapshot_path=str(snapshot_path),
            )
            retained_units = {
                int(str(candidate_id).split("_")[-1])
                for candidate_id in policy_decision["retained_candidate_ids"]
            }
            persistent_units = {
                candidate_unit
                for candidate_unit in retained_units
                if int(creation_scan_index[candidate_unit]) < scan_actions - 1
            }
            stage_state = {
                "action_policy": action_policy,
                "coarse_cell_count": coarse_cell_count,
                "below_coarse_coverage": scan_actions < coarse_cell_count,
                "persistent_candidate_count": len(persistent_units),
                "candidate_capacity": CANDIDATE_CAPACITY,
                "retained_temporal_cells": len(retained_units),
            }
            actions[-1]["stage_state"] = stage_state
            if stage_conditioned:
                should_verify = stage_conditioned_should_verify(
                    completed_scans=scan_actions,
                    coarse_cell_count=coarse_cell_count,
                    persistent_candidate_count=len(persistent_units),
                    retained_temporal_cells=len(retained_units),
                )
            else:
                should_verify = scan_actions % VERIFY_EVERY_N_SCANS == 0
            if not should_verify:
                continue

            verify_opportunities += 1
            selected = policy_decision.get("selected_unit_id")
            if selected is None:
                continue
            selected_policy_decision = policy_decision
            elapsed = (time.perf_counter_ns() - run_start) / 1e9
            admission = guard.decide(
                deadline_seconds=deadline,
                elapsed_seconds=elapsed,
                now_utc=now_utc(),
                action_profile=action_profile,
                commit_profile=commit_profile,
            )
            if not admission.admitted:
                verify_rejected += 1
                stop_reason = f"verify_not_admitted:{admission.reason}"
                if stage_conditioned:
                    continue
                break
            query_started = time.perf_counter_ns()
            result = accessor.query(int(selected))
            query_ended = time.perf_counter_ns()
            if (
                result.get("physical_oracle_invocation") is not True
                or result.get("cache_replay") is not False
                or result.get("parse_status") != "ok"
            ):
                raise RuntimeError("invalid physical oracle result")
            queried_rows.append({
                "unit_id": int(selected),
                "parsed_label": result["parsed_label"],
            })
            raw_path = attempt / (
                f"query_{len(queried_rows) - 1:03d}_oracle.json"
            )
            snapshot_path = attempt / (
                f"checkpoint_{len(checkpoints):03d}_snapshot.json"
            )
            events, commit = materialize_and_commit(
                materializer_path=MATERIALIZER,
                materializer_service=materializer,
                units=units,
                queried_rows=queried_rows,
                snapshot_path=snapshot_path,
                run_config={
                    "benchmark_id": job["task_id"],
                    "run_id": run_id,
                    "method": job["method"],
                    "method_variant": job["method"],
                    "seed": int(job["replicate"]),
                    "horizon_budget": len(queried_rows),
                },
                raw_observation={"oracle_result": result},
                raw_observation_path=raw_path,
            )
            checkpoint_elapsed = (time.perf_counter_ns() - run_start) / 1e9
            post_candidates, _ = causal_unit_candidates(
                proxy_runtime=proxy_runtime,
                raw_candidates=raw_candidates,
                family=job["family"],
                query_id=query_id,
                units=units,
                observed_unit_ids=observed_units,
                queried_unit_ids={int(row["unit_id"]) for row in queried_rows},
                discarded_unit_ids=discarded_units,
                creation_scan_index=creation_scan_index,
                candidate_track_bindings=candidate_track_bindings,
                score_availability_seconds=checkpoint_elapsed,
            )
            policy_started = time.perf_counter_ns()
            policy_decision = policy.decide({
                "method": verify_policy,
                "public_units": public,
                "candidate_rows": post_candidates,
                "queried_rows": queried_rows,
                "pending_unit_ids": [],
                "candidate_capacity": CANDIDATE_CAPACITY,
                "current_scan_index": scan_actions,
                "parameters": job.get("parameters", {}),
            })
            scheduler_cpu_seconds += (
                time.perf_counter_ns() - policy_started
            ) / 1e9
            for candidate_id in policy_decision["discarded_candidate_ids"]:
                discarded = int(str(candidate_id).split("_")[-1])
                discarded_units.add(discarded)
                discarded_lifecycle = candidate_lifecycle.get(discarded)
                if (
                    discarded_lifecycle
                    and discarded_lifecycle["terminal_state"] is None
                ):
                    discarded_lifecycle["terminal_state"] = "discarded"
                    discarded_lifecycle["terminal_seconds"] = checkpoint_elapsed
            queried_results.append({
                "unit_id": int(selected),
                "candidate_id": selected_policy_decision["selected_candidate_id"],
                "selected_track_id": selected_policy_decision["selected_track_id"],
                "candidate_proxy_score": next(
                    float(row["proxy_score"])
                    for row in candidates
                    if int(row["unit_id"]) == int(selected)
                ),
                "parsed_label": result["parsed_label"],
                "generic_parsed_label": result["generic_parsed_label"],
                "confidence": result["confidence"],
                "query_start_seconds": (query_started - run_start) / 1e9,
                "query_end_seconds": (query_ended - run_start) / 1e9,
                "snapshot_elapsed_seconds": checkpoint_elapsed,
                "raw_observation_path": str(raw_path),
                "oracle_inference_seconds": float(
                    result["stage_seconds"]["oracle_inference"]
                ),
                "service_total_seconds": float(result["service_total_seconds"]),
                "physical_oracle_invocation": True,
                "cache_replay": False,
                "admission": admission.to_dict(),
                "priority": selected_policy_decision["priority_rows"][0],
                "commit": commit,
            })
            lifecycle = candidate_lifecycle.get(int(selected))
            if lifecycle:
                lifecycle["terminal_state"] = "verified"
                lifecycle["terminal_seconds"] = checkpoint_elapsed
                lifecycle["verified_label"] = result["parsed_label"]
            checkpoints.append({
                "checkpoint_index": len(checkpoints),
                "action": "query",
                "elapsed_seconds": checkpoint_elapsed,
                "snapshot_path": str(snapshot_path),
                "confirmed_events": len(events),
                "physical_oracle_calls": len(queried_rows),
                **checkpoint_state(units, observed_units, policy_decision),
            })
            actions.append({
                "action": "query",
                "unit_id": int(selected),
                "start_seconds": (query_started - run_start) / 1e9,
                "end_seconds": (query_ended - run_start) / 1e9,
                "snapshot_elapsed_seconds": checkpoint_elapsed,
                "policy_decision_sha256": selected_policy_decision[
                    "decision_sha256"
                ],
                "candidate_proxy_observed_before_query": True,
                "future_proxy_accesses": 0,
                "admission": admission.to_dict(),
            })
            ledger.append(
                "VERIFY_DURABLY_COMMITTED",
                unit_id=int(selected),
                parsed_label=result["parsed_label"],
                snapshot_path=str(snapshot_path),
            )

        if scan_actions == target_scan_actions and verify_rejected == 0:
            stop_reason = (
                "stage_conditioned_scan_exhausted"
                if stage_conditioned else "planned_fixed_periodic_schedule_complete"
            )

        snapshot_elapsed = float(checkpoints[-1]["elapsed_seconds"])
        for lifecycle in candidate_lifecycle.values():
            if lifecycle["terminal_state"] is None:
                lifecycle["terminal_state"] = "survived_to_stop"
                lifecycle["terminal_seconds"] = snapshot_elapsed
        proxy_operator_gpu = sum(
            float(row["detector_gpu_seconds"]) for row in proxy_unit_costs
        )
        proxy_gpu = proxy_warmup_gpu_seconds + proxy_operator_gpu
        oracle_gpu = sum(
            float(row["oracle_inference_seconds"]) for row in queried_results
        )
        if (runtime_input_overrides or {}).get(
            "require_final_cuda_synchronize", False
        ):
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
        session_summary = oracle.end_session(session_id)
        active_session = False
        if session_summary["physical_calls"] != len(queried_results):
            raise RuntimeError("physical oracle session call count mismatch")
        total_wall = (time.perf_counter_ns() - run_start) / 1e9
        result = {
            "status": "ok",
            "run_id": run_id,
            "job": job,
            "method": job["method"],
            "family": job["family"],
            "task_id": job["task_id"],
            "deadline_name": job["deadline_name"],
            "deadline_seconds": deadline,
            "replicate": int(job["replicate"]),
            "config_hash": config["config_hash"],
            "proxy_config_hash": (
                config["final_proxy_config_hash"]
                or config["proxy_implementation_freeze_hash"]
            ),
            "oracle_session_initialization": oracle_session_initialization,
            "oracle_session_summary": session_summary,
            "proxy_initialization_seconds": proxy_initialization_seconds,
            "proxy_predeadline_warmup": warmup_rows,
            "proxy_predeadline_wall_seconds": proxy_predeadline_wall_seconds,
            "proxy_predeadline_GPU_seconds": proxy_warmup_gpu_seconds,
            "proxy_operator_GPU_seconds": proxy_operator_gpu,
            "snapshot_elapsed_seconds": snapshot_elapsed,
            "total_run_wall_seconds": total_wall,
            "total_service_wall_seconds": total_wall,
            "deadline_met": snapshot_elapsed <= deadline,
            "unused_deadline_seconds": deadline - snapshot_elapsed,
            "stop_reason": stop_reason,
            "scan_actions": scan_actions,
            "scan_order_prefix": scan_order[:scan_actions],
            "verify_opportunities": verify_opportunities,
            "target_scan_actions": target_scan_actions,
            "planned_fixed_target_scan_actions": planned_target_scan_actions,
            "target_verify_opportunities": int(
                job["target_verify_opportunities"]
            ),
            "action_policy": action_policy,
            "coarse_cell_count": coarse_cell_count,
            "verify_rejected": verify_rejected,
            "physical_oracle_calls": len(queried_results),
            "cache_replay_calls": 0,
            "queried_rows": queried_rows,
            "queried_results": queried_results,
            "proxy_unit_costs": proxy_unit_costs,
            "proxy_gpu_seconds": proxy_gpu,
            "oracle_gpu_seconds": oracle_gpu,
            "total_gpu_seconds": proxy_gpu + oracle_gpu,
            "scheduler_cpu_seconds": scheduler_cpu_seconds,
            "score_history": score_history,
            "candidate_lifecycle": list(candidate_lifecycle.values()),
            "discarded_unit_ids": sorted(discarded_units),
            "actions": actions,
            "checkpoints": checkpoints,
            "final_snapshot_path": checkpoints[-1]["snapshot_path"],
            "future_proxy_accesses": 0,
            "candidate_observation_violations": 0,
            "reference_visibility_violations": 0,
            "clock_accounting": {
                "external_run_start": run_start_ns is not None,
                "final_cuda_synchronization": bool(
                    (runtime_input_overrides or {}).get(
                        "require_final_cuda_synchronize", False
                    )
                ),
            },
            "completed_at_utc": now_utc(),
        }
        ledger.append(
            "RUN_COMPLETED",
            snapshot_elapsed_seconds=snapshot_elapsed,
            deadline_met=result["deadline_met"],
            physical_oracle_calls=len(queried_results),
        )
        result["action_ledger_path"] = str(attempt / "ACTION_LEDGER.jsonl")
        result["action_ledger_sha256"] = sha256_file(
            attempt / "ACTION_LEDGER.jsonl"
        )
        durable_json(attempt / "complete.json", result)
        print(json.dumps({
            "run_id": run_id,
            "deadline_met": result["deadline_met"],
            "snapshot_seconds": snapshot_elapsed,
            "scans": scan_actions,
            "calls": len(queried_results),
            "confirmed": checkpoints[-1]["confirmed_events"],
        }), flush=True)
        return result
    except Exception as exc:
        durable_json(attempt / "failed.json", {
            "status": "failed",
            "run_id": run_id,
            "job": job,
            "error": f"{type(exc).__name__}: {exc}",
            "run_elapsed_seconds": (
                None
                if run_start is None
                else (time.perf_counter_ns() - run_start) / 1e9
            ),
            "failed_at_utc": now_utc(),
        })
        raise
    finally:
        if engine is not None:
            engine.close()
        if active_session:
            try:
                oracle.end_session(session_id)
            except Exception:
                pass


def run_jobs(
    *,
    kind: str,
    raw: Path,
    jobs: list[dict[str, Any]],
    physical_cap: int,
    config_jobs: list[dict[str, Any]] | None = None,
) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    pending = [job for job in jobs if not job_completed(raw, job)]
    config = build_config(kind, jobs if config_jobs is None else config_jobs)
    config_path = raw.parent / "RESOLVED_CONFIG.json"
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            raise RuntimeError("Physical matrix configuration changed")
    else:
        durable_json(config_path, config)
    completed = list(raw.glob("*/attempt_*/complete.json"))
    failures = list(raw.glob("*/attempt_*/failed.json"))
    if len(completed) + len(failures) + len(pending) > physical_cap:
        raise RuntimeError("Physical run cap would be exceeded")
    if not pending:
        print(json.dumps({"status": "ALL_JOBS_COMPLETE", "jobs": len(jobs)}))
        return
    proxy_runtime = proxy_module()
    dependency_start = time.perf_counter_ns()
    families = sorted({job["family"] for job in pending})
    if "Y8" in families:
        import torch  # noqa: F401
        from ultralytics import YOLO  # noqa: F401
    if any(family.startswith("YP") for family in families):
        import onnxruntime  # noqa: F401
    durable_json(raw.parent / "DEPENDENCY_INITIALIZATION.json", {
        "families": families,
        "predeadline": True,
        "video_frame_accesses": 0,
        "proxy_scores_materialized": 0,
        "wall_seconds": (
            time.perf_counter_ns() - dependency_start
        ) / 1e9,
        "recorded_at_utc": now_utc(),
    })
    deadline_runtime = deadline_module()
    configuration = deadline_runtime.oracle_configuration()
    oracle = materializer = policy = None
    try:
        print(json.dumps({
            "stage": "runtime_initialization",
            "pending_jobs": len(pending),
            "persistent_oracle_model": True,
        }), flush=True)
        materializer = start_materializer_service(MATERIALIZER)
        policy = start_exposure_policy_service()
        oracle = start_two_video_physical_oracle_service(configuration)
        print(json.dumps({
            "stage": "oracle_ready",
            "initialization_seconds": oracle.initialization[
                "initialization_seconds"
            ],
        }), flush=True)
        for job in pending:
            run_one(
                job=job,
                raw=raw,
                config=config,
                oracle=oracle,
                materializer=materializer,
                policy=policy,
                proxy_runtime=proxy_runtime,
                deadline_runtime=deadline_runtime,
            )
    finally:
        if policy is not None:
            policy.close()
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()


def proxy_pilot_jobs() -> list[dict[str, Any]]:
    freeze = json.loads(PILOT_CANDIDATES.read_text())
    tasks = [row["task_id"] for row in json.loads((DEV / "TASK_MANIFEST.json").read_text())["tasks"]]
    jobs = []
    for family in freeze["candidates"]:
        for task_id in tasks:
            for deadline_name in ("T_transition", "T_high"):
                target_scans, target_verifies = planned_scan_actions(
                    family, task_id, deadline_name
                )
                for replicate in range(3):
                    jobs.append({
            "kind": "proxy_pilot",
            "method": "score_only",
            "family": family,
            "task_id": task_id,
            "deadline_name": deadline_name,
            "deadline_seconds": task_deadline(task_id, deadline_name),
            "replicate": replicate,
            "parameters": {},
                        "target_scan_actions": target_scans,
                        "target_verify_opportunities": target_verifies,
                    })
    return jobs


def proxy_smoke_gate() -> None:
    freeze = json.loads(PILOT_CANDIDATES.read_text())
    expected_jobs = [
        job
        for job in proxy_pilot_jobs()
        if job["deadline_name"] == "T_transition"
        and int(job["replicate"]) == 0
    ]
    rows = []
    for job in expected_jobs:
        pattern = (
            f"{job['method']}__{job['family']}__{job['task_id']}__"
            f"{job['deadline_name']}__replicate_{job['replicate']:02d}"
            "/attempt_*/complete.json"
        )
        matches = list((PILOT / "raw").glob(pattern))
        if matches:
            rows.append(json.loads(matches[-1].read_text()))
    gate = {
        "expected_runs": 4 * len(freeze["candidates"]),
        "completed_runs": len(rows),
        "failures": len(list((PILOT / "raw").glob("*/attempt_*/failed.json"))),
        "deadline_misses": sum(not row["deadline_met"] for row in rows),
        "incomplete_schedules": sum(
            int(row["scan_actions"]) != int(row["target_scan_actions"])
            or int(row["verify_opportunities"])
            != int(row["target_verify_opportunities"])
            for row in rows
        ),
        "cache_replays": sum(row["cache_replay_calls"] for row in rows),
        "future_proxy_accesses": sum(row["future_proxy_accesses"] for row in rows),
        "visibility_violations": sum(
            row["candidate_observation_violations"]
            + row["reference_visibility_violations"]
            for row in rows
        ),
        "complete_snapshots": sum(
            Path(row["final_snapshot_path"]).exists() for row in rows
        ),
    }
    gate["PROXY_PILOT_SMOKE"] = (
        "PASS"
        if (
            gate["completed_runs"] == gate["expected_runs"]
            and gate["failures"] == 0
            and gate["deadline_misses"] == 0
            and gate["incomplete_schedules"] == 0
            and gate["cache_replays"] == 0
            and gate["future_proxy_accesses"] == 0
            and gate["visibility_violations"] == 0
            and gate["complete_snapshots"] == gate["expected_runs"]
        )
        else "FAIL"
    )
    durable_json(PILOT / "SMOKE_GATE.json", gate)
    print(json.dumps(gate, indent=2))


def preregister_expose() -> None:
    selected = json.loads((FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
    prereg = {
        "hypothesis_id": "H-EXPOSE2",
        "revision": 0,
        "status": "REGISTERED_BEFORE_H_EXPOSE2_PHYSICAL_RUNS",
        "registered_at_utc": now_utc(),
        "scientific_question": (
            "Under identical scan and VERIFY opportunities, does explicit candidate age, "
            "temporal diversity, and frontier survival improve cross-video event confirmation?"
        ),
        "frozen_system": {
            "scanner": "Uniform-Temporal-Interleave",
            "scan_order": "iterative largest-unobserved-gap midpoint",
            "verify_allocator": "A0 Fixed-Periodic",
            "verify_every_n_scanned_units": VERIFY_EVERY_N_SCANS,
            "proxy_family": selected["selected_proxy_family"],
            "proxy_config_hash": selected["final_proxy_config_hash"],
            "K3": "frozen k3_bridge_safe",
            "deadline_guard": "tail_upper_v1 task-matched profiles",
            "candidate_capacity": CANDIDATE_CAPACITY,
            "candidate_capacity_rationale": (
                "smallest preregistered ranking cutoff; frozen before physical method outcomes"
            ),
        },
        "methods": {
            "fifo": "candidate creation time ascending",
            "score_only": "current frozen proxy score descending",
            "exposure_aware": (
                "rank-normalized proxy + age + temporal novelty - pending overlap "
                "- confirmed overlap; fixed equal weights"
            ),
        },
        "tie_break": "priority, proxy rank, age rank, novelty, older creation, lower unit, lower track",
        "parameters": {},
        "smoke_matrix": "3 methods x 4 tasks x T_transition x 1",
        "formal_matrix": "3 methods x 4 tasks x 2 deadlines x 3 repeats",
        "acceptance_rule": {
            "task_direction": (
                "At least 3/4 tasks lexicographically improve over that task's best baseline: "
                "higher mean AnytimeAUC_F1; if tied within 1e-12, higher F1; if tied, lower "
                "deadline-censored TTFC."
            ),
            "thresholds": [
                "Macro AnytimeAUC_F1 relative gain >= 10%",
                "Macro TTFC reduction >= 20%",
                "Macro absolute F1 gain >= 0.05",
                "sum over four tasks of mean T_high unique confirmed events gain >= 2",
            ],
            "ttfc_censoring": "no confirmed event maps to that run's frozen deadline",
            "mechanism_alignment": (
                "Exposure-aware must improve macro frontier temporal entropy or unique temporal "
                "cells versus the best baseline, and the gain cannot be confined to V0."
            ),
            "safety": [
                "zero deadline miss",
                "zero replay",
                "zero future access",
                "zero visibility violation",
            ],
        },
        "allowed_single_revisions": {
            "R1": "exposure_minus_age",
            "R2": "exposure_minus_novelty",
            "R3": "exposure_temporal_nms with fixed 10-second window",
        },
        "heldout_opened": False,
    }
    prereg["preregistration_hash"] = canonical_hash(prereg)
    destination = EXPOSE / "H_EXPOSE2_PREREGISTRATION.json"
    EXPOSE.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = json.loads(destination.read_text())
        unstable = {"registered_at_utc", "preregistration_hash"}
        if (
            {k: v for k, v in existing.items() if k not in unstable}
            != {k: v for k, v in prereg.items() if k not in unstable}
        ):
            raise RuntimeError("H-EXPOSE2 preregistration changed")
        prereg = existing
    else:
        durable_json(destination, prereg)
    print(json.dumps(prereg, indent=2))


def expose_jobs(phase: str, method_override: str | None = None) -> list[dict[str, Any]]:
    selected = json.loads((FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
    family = selected["selected_proxy_config"]
    tasks = [row["task_id"] for row in json.loads((DEV / "TASK_MANIFEST.json").read_text())["tasks"]]
    methods = (
        ("fifo", "score_only", method_override)
        if method_override is not None
        else ("fifo", "score_only", "exposure_aware")
    )
    if phase == "smoke":
        cells = [
            (task_id, "T_transition", 0)
            for task_id in tasks
        ]
    else:
        cells = [
            (task_id, deadline_name, replicate)
            for task_id in tasks
            for deadline_name in ("T_transition", "T_high")
            for replicate in range(3)
        ]
    parameters = (
        {"temporal_nms_window_seconds": 10.0}
        if method_override == "exposure_temporal_nms"
        else {}
    )
    return [
        {
            "kind": "h_expose2",
            "method": method,
            "family": family,
            "task_id": task_id,
            "deadline_name": deadline_name,
            "deadline_seconds": task_deadline(task_id, deadline_name),
            "replicate": replicate,
            "parameters": parameters if method == method_override else {},
            "target_scan_actions": planned_scan_actions(
                family, task_id, deadline_name
            )[0],
            "target_verify_opportunities": planned_scan_actions(
                family, task_id, deadline_name
            )[1],
        }
        for method in methods
        for task_id, deadline_name, replicate in cells
    ]


def preregister_ablation() -> None:
    decision = json.loads((EXPOSE / "DECISION.json").read_text())
    source = EXPOSE
    if decision.get("H_EXPOSE2_DECISION") == "REVISE":
        revision = json.loads((EXPOSE / "REVISION_DECISION.json").read_text())
        source = EXPOSE / f"revision_{revision['revision_method']}"
        decision = json.loads((source / "DECISION.json").read_text())
    if decision.get("H_EXPOSE2_DECISION") != "ACCEPT_TWO_VIDEO_SIGNAL":
        raise RuntimeError("H-EXPOSE2 was not accepted; ablation is not authorized")
    frame = pd.read_csv(source / "tables/RUN_METRICS.csv")
    baseline = decision["best_baseline"]
    target = decision["target_method"]
    macro = frame.groupby("method").agg(
        survival=("candidate_survival_time_mean", "mean"),
        conversion=("candidate_to_VERIFY_conversion", "mean"),
        entropy=("frontier_temporal_entropy_mean", "mean"),
        unique_cells=("unique_temporal_cells_in_frontier_mean", "mean"),
        redundant=("redundant_VERIFY", "mean"),
    )
    base = macro.loc[baseline]
    full = macro.loc[target]
    scores = {
        "age": max(
            0.0,
            float(full.survival - base.survival)
            / max(abs(float(base.survival)), 1e-9),
        )
        + max(
            0.0,
            float(full.conversion - base.conversion)
            / max(abs(float(base.conversion)), 1e-9),
        ),
        "temporal_novelty": max(
            0.0,
            float(full.entropy - base.entropy)
            / max(abs(float(base.entropy)), 1e-9),
        )
        + max(
            0.0,
            float(full.unique_cells - base.unique_cells)
            / max(abs(float(base.unique_cells)), 1e-9),
        ),
        "pending_confirmed_suppression": max(
            0.0,
            float(base.redundant - full.redundant)
            / max(abs(float(base.redundant)), 1.0),
        ),
    }
    available_components = {
        "exposure_aware": {
            "age", "temporal_novelty", "pending_confirmed_suppression"
        },
        "exposure_minus_age": {
            "temporal_novelty", "pending_confirmed_suppression"
        },
        "exposure_minus_novelty": {
            "age", "pending_confirmed_suppression"
        },
        "exposure_temporal_nms": {
            "age", "temporal_novelty", "pending_confirmed_suppression"
        },
    }.get(target)
    if not available_components:
        raise RuntimeError(f"Unsupported accepted method for ablation: {target}")
    scores = {
        key: value for key, value in scores.items()
        if key in available_components
    }
    component = max(
        scores,
        key=lambda name: (
            scores[name],
            {"temporal_novelty": 2, "age": 1, "pending_confirmed_suppression": 0}[name],
        ),
    )
    minus_method = {
        ("exposure_aware", "age"): "exposure_minus_age",
        ("exposure_aware", "temporal_novelty"): "exposure_minus_novelty",
        (
            "exposure_aware",
            "pending_confirmed_suppression",
        ): "exposure_minus_suppression",
        (
            "exposure_minus_age",
            "temporal_novelty",
        ): "exposure_minus_age_novelty",
        (
            "exposure_minus_age",
            "pending_confirmed_suppression",
        ): "exposure_minus_age_suppression",
        (
            "exposure_minus_novelty",
            "age",
        ): "exposure_minus_age_novelty",
        (
            "exposure_minus_novelty",
            "pending_confirmed_suppression",
        ): "exposure_minus_novelty_suppression",
        (
            "exposure_temporal_nms",
            "age",
        ): "exposure_temporal_nms_minus_age",
        (
            "exposure_temporal_nms",
            "temporal_novelty",
        ): "exposure_temporal_nms_minus_novelty",
        (
            "exposure_temporal_nms",
            "pending_confirmed_suppression",
        ): "exposure_temporal_nms_minus_suppression",
    }[(target, component)]
    prereg = {
        "hypothesis_id": "H-EXPOSE2-ABLATION",
        "registered_at_utc": now_utc(),
        "selection_rule": (
            "Choose the component with the largest preregistered normalized mechanism-signature "
            "gain versus the accepted comparison's best baseline; deterministic tie favors "
            "novelty, then age, then suppression."
        ),
        "component_scores": scores,
        "selected_component": component,
        "full_method": target,
        "minus_method": minus_method,
        "methods": [target, minus_method, "score_only"],
        "accepted_decision_source": str(source / "DECISION.json"),
        "matrix": "3 methods x 4 tasks x T_transition x 3 physical repeats",
        "acceptance": (
            "Removing the component must reduce Macro AnytimeAUC_F1 by >=10% relative or reduce "
            "the four-task sum of mean unique confirmed events by >=1, and the selected mechanism "
            "signature must deteriorate in its expected direction."
        ),
        "heldout_opened": False,
    }
    prereg["preregistration_hash"] = canonical_hash(prereg)
    ABLATION.mkdir(parents=True, exist_ok=True)
    destination = ABLATION / "PREREGISTRATION.json"
    if destination.exists():
        existing = json.loads(destination.read_text())
        unstable = {"registered_at_utc", "preregistration_hash"}
        if (
            {k: v for k, v in existing.items() if k not in unstable}
            != {k: v for k, v in prereg.items() if k not in unstable}
        ):
            raise RuntimeError("H-EXPOSE2 ablation preregistration changed")
        prereg = existing
    else:
        durable_json(destination, prereg)
    print(json.dumps(prereg, indent=2))


def ablation_jobs() -> list[dict[str, Any]]:
    prereg = json.loads((ABLATION / "PREREGISTRATION.json").read_text())
    selected = json.loads((FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
    family = selected["selected_proxy_config"]
    tasks = [
        row["task_id"]
        for row in json.loads((DEV / "TASK_MANIFEST.json").read_text())["tasks"]
    ]
    jobs = []
    for method in prereg["methods"]:
        for task_id in tasks:
            target_scans, target_verifies = planned_scan_actions(
                family, task_id, "T_transition"
            )
            for replicate in range(3):
                jobs.append({
                    "kind": "h_expose2_ablation",
                    "method": method,
                    "family": family,
                    "task_id": task_id,
                    "deadline_name": "T_transition",
                    "deadline_seconds": task_deadline(
                        task_id, "T_transition"
                    ),
                    "replicate": replicate,
                    "parameters": (
                        {"temporal_nms_window_seconds": 10.0}
                        if method.startswith("exposure_temporal_nms")
                        else {}
                    ),
                    "target_scan_actions": target_scans,
                    "target_verify_opportunities": target_verifies,
                })
    return jobs


def smoke_gate() -> None:
    raw = EXPOSE / "raw"
    expected = expose_jobs("smoke")
    rows = []
    for job in expected:
        pattern = (
            f"{job['method']}__{job['family']}__{job['task_id']}__"
            f"{job['deadline_name']}__replicate_{job['replicate']:02d}"
            "/attempt_*/complete.json"
        )
        matches = list(raw.glob(pattern))
        if matches:
            rows.append(json.loads(matches[-1].read_text()))
    gate = {
        "expected_runs": 12,
        "completed_runs": len(rows),
        "failures": len(list(raw.glob("*/attempt_*/failed.json"))),
        "deadline_misses": sum(not row["deadline_met"] for row in rows),
        "cache_replays": sum(row["cache_replay_calls"] for row in rows),
        "future_proxy_accesses": sum(row["future_proxy_accesses"] for row in rows),
        "visibility_violations": sum(
            row["candidate_observation_violations"]
            + row["reference_visibility_violations"]
            for row in rows
        ),
        "complete_snapshots": sum(
            Path(row["final_snapshot_path"]).exists() for row in rows
        ),
    }
    gate["H_EXPOSE2_SMOKE"] = (
        "PASS"
        if (
            gate["completed_runs"] == 12
            and gate["failures"] == 0
            and gate["deadline_misses"] == 0
            and gate["cache_replays"] == 0
            and gate["future_proxy_accesses"] == 0
            and gate["visibility_violations"] == 0
            and gate["complete_snapshots"] == 12
        )
        else "FAIL"
    )
    durable_json(EXPOSE / "SMOKE_GATE.json", gate)
    print(json.dumps(gate, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=(
            "freeze-pilot-candidates",
            "proxy-pilot-smoke",
            "proxy-pilot-smoke-gate",
            "proxy-pilot",
            "preregister-expose",
            "expose-smoke",
            "expose-smoke-gate",
            "expose-formal",
            "expose-revision",
            "preregister-ablation",
            "ablation",
        ),
    )
    parser.add_argument(
        "--revision-method",
        choices=(
            "exposure_minus_age",
            "exposure_minus_novelty",
            "exposure_temporal_nms",
        ),
    )
    args = parser.parse_args()
    if args.stage == "freeze-pilot-candidates":
        freeze_pilot_candidates()
    elif args.stage == "proxy-pilot-smoke":
        jobs = [
            job
            for job in proxy_pilot_jobs()
            if job["deadline_name"] == "T_transition"
            and int(job["replicate"]) == 0
        ]
        run_jobs(
            kind="H_PROXY_2VIDEO_NEUTRAL_PHYSICAL_V1",
            raw=PILOT / "raw",
            jobs=jobs,
            physical_cap=72,
        )
    elif args.stage == "proxy-pilot-smoke-gate":
        proxy_smoke_gate()
    elif args.stage == "proxy-pilot":
        gate = json.loads((PILOT / "SMOKE_GATE.json").read_text())
        if gate.get("PROXY_PILOT_SMOKE") != "PASS":
            raise RuntimeError("Neutral proxy pilot smoke gate is not PASS")
        jobs = proxy_pilot_jobs()
        run_jobs(
            kind="H_PROXY_2VIDEO_NEUTRAL_PHYSICAL_V1",
            raw=PILOT / "raw",
            jobs=jobs,
            physical_cap=72,
        )
    elif args.stage == "preregister-expose":
        preregister_expose()
    elif args.stage == "expose-smoke":
        jobs = expose_jobs("smoke")
        run_jobs(
            kind="H_EXPOSE2_PHYSICAL_V1",
            raw=EXPOSE / "raw",
            jobs=jobs,
            physical_cap=72,
        )
    elif args.stage == "expose-smoke-gate":
        smoke_gate()
    elif args.stage == "expose-formal":
        gate = json.loads((EXPOSE / "SMOKE_GATE.json").read_text())
        if gate.get("H_EXPOSE2_SMOKE") != "PASS":
            raise RuntimeError("H-EXPOSE2 smoke gate is not PASS")
        jobs = expose_jobs("formal")
        run_jobs(
            kind="H_EXPOSE2_PHYSICAL_V1",
            raw=EXPOSE / "raw",
            jobs=jobs,
            physical_cap=72,
        )
    elif args.stage == "preregister-ablation":
        preregister_ablation()
    elif args.stage == "ablation":
        jobs = ablation_jobs()
        run_jobs(
            kind="H_EXPOSE2_ABLATION_V1",
            raw=ABLATION / "raw",
            jobs=jobs,
            physical_cap=36,
        )
    else:
        if args.revision_method is None:
            raise RuntimeError("--revision-method is required")
        jobs = expose_jobs("formal", args.revision_method)
        destination = EXPOSE / f"revision_{args.revision_method}" / "raw"
        run_jobs(
            kind=f"H_EXPOSE2_REVISION_{args.revision_method}",
            raw=destination,
            jobs=jobs,
            physical_cap=72,
        )


if __name__ == "__main__":
    main()
