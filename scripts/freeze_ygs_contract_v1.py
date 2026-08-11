#!/usr/bin/env python3
"""Freeze YOLO-guided SCAN agentic research contract and parent evidence."""
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
import torch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"
DOC = ROOT / "docs/YOLO_GUIDED_SCAN_AUTONOMOUS_RESEARCH_CONTRACT_V1.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20): digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args],
        text=True, capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def first_line(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else "UNAVAILABLE"


def main() -> None:
    for directory in (
        "contracts", "hypotheses", "preview_experiments", "region_value_experiments",
        "scheduler_experiments", "physical_validation", "controls", "ablations",
        "failures", "metrics", "reports",
    ):
        (OUT / directory).mkdir(parents=True, exist_ok=True)
    parents = [
        "benchmarks/partial_scan_pilot_v1/immutable/immutable_manifest.json",
        "benchmarks/partial_scan_pilot_v1/immutable/videos.csv",
        "benchmarks/partial_scan_pilot_v1/immutable/timeline_units.csv",
        "benchmarks/partial_scan_pilot_v1/immutable/reference_events.csv",
        "benchmarks/partial_scan_pilot_v1/immutable/contracts/event_exposure_contract.yaml",
        "benchmarks/partial_scan_pilot_v1/derived/candidate_event_map.parquet",
        "outputs/scan_optimization_headroom_audit_v1/AUDIT_MANIFEST.json",
        "outputs/scan_optimization_headroom_audit_v1/headroom_decision.json",
        "outputs/scan_optimization_headroom_audit_v1/FINAL_RESEARCH_SYNTHESIS_ZH.md",
        "outputs/macro_region_proxy_optimization_v1/artifact_hash_manifest.json",
        "outputs/multi_fidelity_region_preview_v1/artifact_hash_manifest.json",
        "outputs/multi_fidelity_region_preview_v1/metrics/exploratory_gate.json",
        "outputs/multi_fidelity_region_preview_v1/predictions/nested_lovo_predictions.parquet",
    ]
    parent_hashes = {}
    for relative in parents:
        path = ROOT / relative
        parent_hashes[relative] = {
            "exists": path.exists(), "sha256": sha256(path) if path.exists() else None,
            "bytes": path.stat().st_size if path.exists() else None,
        }
    write_json(OUT / "contracts/parent_asset_hashes.json", parent_hashes)
    contract = {
        "document_id": "YOLO_GUIDED_SCAN_AUTONOMOUS_RESEARCH_V1",
        "contract_hash": sha256(DOC), "contract_bytes": DOC.stat().st_size,
        "code_commit": git_value("rev-parse", "HEAD"),
        "frozen_before_new_experiment_metrics": True,
        "scientific_question": "YOLO_GUIDED_RESIDUAL_VALUE_WITH_RECOVERABLE_COVERAGE",
        "legal_final_states": [
            "SELECTED_YOLO_GUIDED_SCAN_ALGORITHM", "SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST",
            "BLOCKED_BY_INSUFFICIENT_IDENTIFICATION_ASSETS",
        ],
        "design_video_count": 2, "validation_video_count": 0, "test_video_count": 0,
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "scheduler_precondition": "STATIC_OBSERVABILITY_GATE_PASS",
        "max_agentic_cycles": 12, "max_algorithm_hypotheses": 8,
        "max_new_physical_runs": 40,
    }
    contract["frozen_record_hash"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    write_json(OUT / "contracts/frozen_contract.json", contract)
    write_json(OUT / "contracts/search_budget.json", {
        "max_agentic_cycles": 12, "max_algorithm_hypotheses": 8,
        "max_global_preview_configs": 4, "max_escalation_preview_configs": 4,
        "max_feature_families": 10, "max_value_model_families": 5,
        "max_value_model_configs": 80, "max_scheduler_variants": 24,
        "max_batch_size_configs": 3, "max_repair_cycles_per_branch": 1,
        "max_total_repair_cycles": 3, "max_formal_test_evaluations": 1,
        "max_new_physical_runs": 40,
    })
    write_json(OUT / "contracts/static_gate.json", {
        "nested_lovo_recall20_both": 0.40, "nested_lovo_auc_strict_both": 0.55,
        "enrichment_strict_both": 1.5, "beat_p0_both": True,
        "beat_p1l_if_escalated_both": True, "beat_shuffled_both": True,
        "beat_time_index_macro": True, "max_total_preview_cost_ratio": 0.10,
        "net_yield_nonnegative_both": True, "one_common_budget_positive_both": True,
        "leave_best_region_direction_nonnegative": True,
        "best_region_contribution_strict_less_than": 0.50,
        "logic": "ALL_CONDITIONS_REQUIRED",
    })
    write_json(OUT / "contracts/hypothesis_budget.json", {
        "registered_initial": ["YGS-H000", "YGS-H001", "YGS-H002"],
        "registry_path": "docs/SCAN_INNOVATION_HYPOTHESIS_REGISTRY.md",
        "decision_ledger_path": "docs/SCAN_INNOVATION_DECISION_LEDGER.md",
    })
    environment = {
        "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "pandas": pd.__version__, "opencv": cv2.__version__,
        "torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu": first_line(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        "ffmpeg": first_line(["ffmpeg", "-version"]),
        "contract_hash": contract["contract_hash"], "code_commit": contract["code_commit"],
    }
    write_json(OUT / "environment_lock.json", environment)
    write_json(OUT / "repair_log.json", [])
    print(json.dumps({
        "status": "FROZEN", "contract_hash": contract["contract_hash"],
        "code_commit": contract["code_commit"], "parent_assets": len(parent_hashes),
    }, indent=2))


if __name__ == "__main__": main()
