"""Frozen identity map for the paired ARC/current physical smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ARC_PHYSICAL_METHOD = "ARC-UNIT-INSPIRED-PHYS-v1"
CURRENT_ACCELERATED_METHOD = "ST1"
SMOKE_CELL = {
    "task_id": "V0_Q1",
    "deadline_name": "T_transition",
    "replicate": 0,
    "proxy_family": "Y8",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def audit_shared_contract(repo: Path) -> dict[str, Any]:
    """Resolve and cross-check all identities without opening task references."""

    repo = Path(repo).resolve()
    out = repo / "outputs/psvr_two_video_loop"
    tasks = json.loads((out / "dev_benchmark_v1/TASK_MANIFEST.json").read_text())
    queries = json.loads((out / "QUERY_MANIFEST.json").read_text())
    videos = json.loads((out / "VIDEO_MANIFEST.json").read_text())
    deadlines_path = out / "deadlines/TASK_DEADLINE_MANIFEST.json"
    deadlines = json.loads(deadlines_path.read_text())
    task_ids = [str(row["task_id"]) for row in tasks["tasks"]]
    if task_ids != ["V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"]:
        raise RuntimeError("frozen task universe changed")
    deadline_row = next(
        row for row in deadlines["tasks"] if row["task_id"] == SMOKE_CELL["task_id"]
    )
    final_proxy_path = out / "final_proxy/FINAL_PROXY_CONFIG.json"
    final_proxy = json.loads(final_proxy_path.read_text())
    if final_proxy.get("selected_proxy_config") != SMOKE_CELL["proxy_family"]:
        raise RuntimeError("smoke proxy family is not the frozen selected configuration")
    runner = repo / "scripts/run_psvr_stage1_physical.py"
    base_runner = repo / "scripts/run_psvr_two_video_physical.py"
    evaluator = repo / "scripts/evaluate_psvr_two_video_physical.py"
    materializer = (
        repo
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
        / "agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    shared = {
        "baseline_id": ARC_PHYSICAL_METHOD,
        "current_method": CURRENT_ACCELERATED_METHOD,
        "current_runner": str(runner),
        "current_runner_sha256": sha256_file(runner),
        "shared_base_runner": str(base_runner),
        "shared_base_runner_sha256": sha256_file(base_runner),
        "evaluator": str(evaluator),
        "evaluator_sha256": sha256_file(evaluator),
        "materializer": str(materializer),
        "materializer_sha256": sha256_file(materializer),
        "K3": {"mode": "k3_bridge_safe", "g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
        "benchmark_id": tasks["benchmark_id"],
        "task_ids": task_ids,
        "query_manifest_hash": queries["manifest_hash"],
        "query_protocol_hash": queries["query_protocol_hash"],
        "video_sha256": {key: videos[key]["sha256"] for key in ("V0", "V1")},
        "deadline_manifest": str(deadlines_path),
        "deadline_manifest_sha256": sha256_file(deadlines_path),
        "deadline_manifest_hash": deadlines["manifest_hash"],
        "smoke_cell": {
            **SMOKE_CELL,
            "deadline_seconds": float(deadline_row[SMOKE_CELL["deadline_name"]]),
        },
        "proxy_config": str(final_proxy_path),
        "proxy_config_sha256": sha256_file(final_proxy_path),
        "proxy_config_hash": final_proxy["final_proxy_config_hash"],
        "runtime_components": {
            relative: sha256_file(repo / relative)
            for relative in (
                "src/garc_eval/psvr_runtime/runner.py",
                "src/garc_eval/psvr_runtime/deadline_guard.py",
                "src/garc_eval/psvr_runtime/two_video_physical_oracle.py",
                "src/garc_eval/psvr_exposure/policy_service.py",
                "scripts/run_psvr_two_video_proxy.py",
                "scripts/freeze_psvr_two_video_deadlines.py",
                "scripts/run_psvr_stage1_physical.py",
            )
        },
        "reference_visible_to_runtime": False,
    }
    shared["contract_hash"] = canonical_hash(shared)
    return shared
