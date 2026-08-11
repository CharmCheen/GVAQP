#!/usr/bin/env python3
"""Freeze MFRP-V1 contract and parent evidence before new preview execution."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pandas as pd
import sklearn


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
DOC = ROOT / "docs/MULTI_FIDELITY_REGION_PREVIEW_CONTRACT_V1.md"
MODEL = ROOT / "models/yolo/yolov8n.pt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    command = ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args]
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def command_first_line(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else "UNAVAILABLE"


def main() -> None:
    directories = [
        "contracts/preview_contracts", "audits", "preview/p0", "preview/p1_l",
        "preview/p1_m", "preview/p2", "preview/runtime_samples", "features",
        "labels", "experiments/univariate", "experiments/models",
        "experiments/controls", "experiments/ablations",
        "experiments/macro_region_sensitivity", "predictions", "metrics", "reports",
    ]
    for directory in directories:
        (OUT / directory).mkdir(parents=True, exist_ok=True)

    parent_paths = [
        "benchmarks/partial_scan_pilot_v1/immutable/videos.csv",
        "benchmarks/partial_scan_pilot_v1/immutable/timeline_units.csv",
        "benchmarks/partial_scan_pilot_v1/immutable/reference_events.csv",
        "benchmarks/partial_scan_pilot_v1/derived/candidate_event_map.parquet",
        "outputs/macro_region_proxy_optimization_v1/artifact_hash_manifest.json",
        "outputs/macro_region_proxy_optimization_v1/reports/FINAL_PROXY_DECISION.md",
        "outputs/macro_region_proxy_optimization_v1/preview/region_features/SELECTED.parquet",
        "outputs/macro_region_proxy_optimization_v1/labels/event_region_map.parquet",
        "outputs/scan_optimization_headroom_audit_v1/AUDIT_MANIFEST.json",
        "outputs/scan_optimization_headroom_audit_v1/FINAL_RESEARCH_SYNTHESIS_ZH.md",
        "outputs/scan_optimization_headroom_audit_v1/physical_evidence_manifest.json",
    ]
    parent_hashes = {}
    for relative in parent_paths:
        path = ROOT / relative
        parent_hashes[relative] = {
            "exists": path.exists(),
            "sha256": sha256(path) if path.exists() else None,
            "bytes": path.stat().st_size if path.exists() else None,
        }
    videos = pd.read_csv(ROOT / "benchmarks/partial_scan_pilot_v1/immutable/videos.csv")
    parent_hashes["source_videos"] = {
        row.video_id: {
            "path": row.video_path, "manifest_sha256": row.video_hash,
            "actual_sha256": sha256(Path(row.video_path)),
            "matches_manifest": sha256(Path(row.video_path)) == row.video_hash,
        }
        for row in videos.itertuples(index=False)
    }
    write_json(OUT / "contracts/parent_asset_hashes.json", parent_hashes)

    frozen = {
        "document_id": "MULTI_FIDELITY_REGION_PREVIEW_OBSERVABILITY_AUDIT_V1",
        "contract_path": str(DOC.relative_to(ROOT)),
        "contract_hash": sha256(DOC),
        "contract_bytes": DOC.stat().st_size,
        "code_commit": git_value("rev-parse", "HEAD"),
        "frozen_before_new_preview_execution": True,
        "research_problem": "MULTI_FIDELITY_REGION_PREVIEW_OBSERVABILITY",
        "primary_stage": "STATIC_MACRO_REGION_RANKING",
        "allocator": "PROHIBITED_THIS_STAGE",
        "guarded_marginal_scan": "STOPPED",
        "rl_bandit_mdp_smdp": "PROHIBITED",
        "design_video_ids": list(videos.video_id.astype(str)),
        "design_video_count": 2,
        "validation_video_count": 0,
        "test_video_count": 0,
        "formal_validation_requirement": "AT_LEAST_4_NEW_INDEPENDENT_COMPLETE_VIDEOS",
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "parent_asset_hash_file": "contracts/parent_asset_hashes.json",
    }
    frozen["frozen_record_hash"] = hashlib.sha256(
        json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    write_json(OUT / "contracts/frozen_contract.json", frozen)

    preview_contracts = {
        "P0": {
            "status": "EXISTING_FRAMESTAT_BASELINE_CLOSED_TO_TUNING",
            "source": "outputs/macro_region_proxy_optimization_v1",
            "operator": "P0_KEYFRAME_5S_160X90", "target_rate_fps": 0.2,
            "resolution": "160x90", "dnn": False,
        },
        "P1_L": {
            "operator": "YOLOV8N_DETECTION_ONLY_0P2FPS_320",
            "family": "LOW_RATE_LOW_RESOLUTION_DETECTOR", "target_rate_fps": 0.2,
            "resolution": "320x180_letterbox_to_320", "model_path": str(MODEL.relative_to(ROOT)),
            "model_sha256": sha256(MODEL), "tracking": False,
            "full_scan_cache": False, "repeat_count": 2,
        },
        "P1_M": {
            "operator": "YOLOV8N_DETECTION_ONLY_0P5FPS_320",
            "family": "LOW_RATE_LOW_RESOLUTION_DETECTOR", "target_rate_fps": 0.5,
            "resolution": "320x180_letterbox_to_320", "model_path": str(MODEL.relative_to(ROOT)),
            "model_sha256": sha256(MODEL), "tracking": False,
            "full_scan_cache": False, "repeat_count": 2,
        },
        "P2": {
            "operator": "SPARSE_FRAME_DIFFERENCE_1FPS_160X90",
            "family": "SPARSE_LOW_COST_MOTION_PREVIEW", "target_rate_fps": 1.0,
            "resolution": "160x90", "optical_flow": False, "tracking": False,
            "repeat_count": 2,
        },
        "P3": {
            "status": "NOT_IMPLEMENTED_UNLESS_P1_AND_P2_COMPONENT_GATES_PASS",
        },
        "max_preview_cost_ratio": 0.10,
        "full_timeline_coverage_required": True,
        "cost_fields": [
            "decode_time_sec", "model_time_sec", "feature_time_sec",
            "total_wallclock_sec", "seconds_per_video_hour", "peak_cpu_memory",
            "peak_gpu_memory", "determinism", "missingness",
        ],
    }
    for name in ("P0", "P1_L", "P1_M", "P2", "P3"):
        write_json(OUT / f"contracts/preview_contracts/{name}.json", preview_contracts[name])
    write_json(OUT / "contracts/preview_contracts/index.json", preview_contracts)
    write_json(OUT / "contracts/feature_contract.json", {
        "max_feature_families": 8,
        "families": [
            "F1_OBJECT_OCCUPANCY", "F2_CLASS_COMPOSITION", "F3_BBOX_GEOMETRY",
            "F4_LOW_COST_MOTION_AND_CHANGE", "F5_TEMPORAL_AGGREGATION",
            "F6_SCENE_DIVERSITY_AND_NOVELTY", "F7_PREVIEW_ONLY_WEAK_QUERY_TRIGGERS",
            "F8_SUPPORT_AND_RELIABILITY",
        ],
        "forbidden_inputs": [
            "video_id_as_model_input", "session_id", "source_id", "filename",
            "absolute_region_index", "normalized_absolute_time", "reference_event_count",
            "reference_event_id", "candidate_event_mapping", "full_scan_features",
            "offline_greedy_rank", "future_reward", "future_cost", "test_split", "method_result",
        ],
        "time_index": "NEGATIVE_CONTROL_ONLY",
    })
    write_json(OUT / "contracts/metric_contract.json", {
        "primary": "DISTINCT_EVENT_RECALL_AT_TOP_20_PERCENT_COMPLETE_REGION_COST",
        "secondary_budget_fractions": [0.10, 0.30],
        "net_yield_budgets": ["60_SECONDS", "20_PERCENT_FULL_SCAN_COST", "30_PERCENT_FULL_SCAN_COST"],
        "random_fixed_seeds": list(range(100)),
        "partial_region_execution": False,
        "event_universe": "EXPOSABLE_UNDER_FULL_SCAN_REFERENCE_EVENTS",
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
    })
    write_json(OUT / "contracts/search_budget.json", {
        "max_preview_operator_configs": 4, "max_feature_families": 8,
        "max_model_families": 5, "max_primary_configs": 50,
        "max_repair_cycles": 1, "formal_test_evaluations": 0,
        "allowed_models": [
            "HEURISTIC_SCORE", "LOGISTIC_REGRESSION", "POISSON_REGRESSION",
            "NEGATIVE_BINOMIAL", "SHALLOW_LIGHTGBM",
        ],
        "prohibited_models": ["TCN", "GRU", "LSTM", "TRANSFORMER", "RL", "BANDIT", "MDP", "SMDP"],
    })
    environment = {
        "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "pandas": pd.__version__,
        "opencv": cv2.__version__, "scikit_learn": sklearn.__version__,
        "ffmpeg": command_first_line(["ffmpeg", "-version"]),
        "nvidia_smi": command_first_line(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        "code_commit": frozen["code_commit"], "contract_hash": frozen["contract_hash"],
    }
    try:
        import torch
        environment.update({
            "torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
        })
    except Exception as error:
        environment["torch_import_error"] = repr(error)
    write_json(OUT / "environment_lock.json", environment)
    write_json(OUT / "repair_log.json", [])
    print(json.dumps({
        "status": "FROZEN", "contract_hash": frozen["contract_hash"],
        "code_commit": frozen["code_commit"], "parent_asset_count": len(parent_hashes),
        "environment_lock": environment,
    }, indent=2))


if __name__ == "__main__":
    main()
