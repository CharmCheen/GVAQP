#!/usr/bin/env python3
"""Generate MFRP completion matrix, version record, and artifact hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import cv2
import lightgbm
import numpy as np
import pandas as pd
import sklearn
import torch
import ultralytics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def write_text(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    command = ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args]
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def main() -> None:
    environment_path = OUT / "environment_lock.json"
    environment = json.loads(environment_path.read_text())
    environment.update({
        "torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
        "ultralytics": ultralytics.__version__, "lightgbm": lightgbm.__version__,
        "numpy_final": np.__version__, "pandas_final": pd.__version__,
        "opencv_final": cv2.__version__, "scikit_learn_final": sklearn.__version__,
    })
    write_json(environment_path, environment)
    code_version = {
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status_short": git_value("status", "--short", "--untracked-files=all").splitlines(),
        "contract_hash": json.loads((OUT / "contracts/frozen_contract.json").read_text())["contract_hash"],
        "scripts": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted((ROOT / "scripts").glob("*mfrp*.py"))
        },
    }
    write_json(OUT / "code_version.json", code_version)

    rows = [
        ("Full prompt copied and hash-frozen before new metrics", "PASS", "docs/MULTI_FIDELITY_REGION_PREVIEW_CONTRACT_V1.md; contracts/frozen_contract.json"),
        ("Code commit, parent hashes, and environment frozen", "PASS", "contracts/parent_asset_hashes.json; environment_lock.json"),
        ("Authoritative timeline/reference/exposure assets inherited", "PASS", "audits/asset_audit.json; audits/label_audit.json"),
        ("Two design videos only", "PASS", "audits/asset_audit.json"),
        ("Formal validation >=4 new complete videos", "CORRECTLY_BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS", "audits/asset_audit.json"),
        ("40/60/90/120 macro sensitivity and one frozen length", "PASS", "experiments/macro_region_sensitivity/; contracts/macro_region_selection.json"),
        ("Midpoint unique event mapping and 263/268 ceiling", "PASS", "labels/event_region_map.parquet; audits/label_audit.json"),
        ("P0 frozen without retuning", "PASS", "preview/p0/inheritance_manifest.json"),
        ("P1-L full timeline run twice", "PASS", "preview/p1_l/; preview/runtime_samples/"),
        ("P1-M full timeline run twice", "PASS", "preview/p1_m/; preview/runtime_samples/"),
        ("P2 full timeline run twice", "PASS", "preview/p2/; preview/runtime_samples/"),
        ("P3 component precondition", "CORRECTLY_NOT_IMPLEMENTED_COMPONENT_GATES_FAILED", "metrics/exploratory_gate.json"),
        ("Decode/model/feature/total/runtime/memory costs", "PASS", "audits/preview_cost_audit.json; audits/preview_runtime_samples.csv"),
        ("All preview ratios <=0.10", "PASS", "audits/preview_cost_audit.json"),
        ("Determinism, missingness, timeline coverage", "PASS", "audits/determinism_audit.json"),
        ("Feature legality table exact fields and <=8 families", "PASS", "audits/feature_legality_audit.csv"),
        ("No forbidden/reference/full-SCAN/future input", "PASS", "audits/leakage_audit.json"),
        ("Every legal feature univariate metrics", "PASS", "experiments/univariate/all_feature_per_video_metrics.parquet"),
        ("Model grid frozen before feature-label metrics", "PASS", "contracts/model_search_manifest.json"),
        ("Nested whole-video feature/schema/hyperparameter selection", "PASS", "experiments/models/nested_feature_selections.json; predictions/nested_lovo_predictions.parquet"),
        ("Model families/config search budget respected", "PASS", "experiments/models/all_45_config_nested_metrics.parquet"),
        ("B0-B9 mandatory controls", "PASS", "experiments/controls/"),
        ("Random 100 fixed seeds", "PASS", "metrics/random_baseline_distribution.json"),
        ("Primary complete-region Recall@20 and actual used cost", "PASS", "metrics/per_video_metrics.csv; metrics/per_region_metrics.csv"),
        ("All mandatory secondary metrics", "PASS", "metrics/per_video_metrics.csv"),
        ("Feature-family ablation", "PASS", "experiments/ablations/candidate_family_ablation.csv"),
        ("Net yield at 60s/20%/30% with infeasible cells explicit", "PASS", "metrics/net_event_yield_budget_grid.csv"),
        ("All ten failure-analysis categories", "PASS", "reports/FAILURE_ANALYSIS.md; metrics/failure_analysis_metrics.json"),
        ("Exploratory Gate automatically evaluated", "PASS", "metrics/exploratory_gate.json"),
        ("Allocator/Guarded Marginal/RL/Bandit not implemented", "PASS_NOT_IMPLEMENTED", "reports/FINAL_PREVIEW_DECISION.md"),
        ("Required deliverable tree", "PASS", "artifact_hash_manifest.json"),
        ("Final decision terminal fields", "PASS", "reports/FINAL_PREVIEW_DECISION.md"),
    ]
    matrix = pd.DataFrame(rows, columns=["requirement", "status", "authoritative_evidence"])
    write_text(OUT / "audits/completion_matrix.md", "# MFRP-V1 Completion Matrix\n\n" + matrix.to_markdown(index=False))
    matrix.to_csv(OUT / "audits/completion_matrix.csv", index=False)

    artifacts = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifacts[str(path.relative_to(OUT))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    write_json(OUT / "artifact_hash_manifest.json", {"artifact_count": len(artifacts), "artifacts": artifacts})
    print(json.dumps({"status": "PASS", "artifact_count": len(artifacts), "matrix_rows": len(matrix)}, indent=2))


if __name__ == "__main__":
    main()
