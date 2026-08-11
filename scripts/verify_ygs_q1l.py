#!/usr/bin/env python3
"""Verify the frozen global low-rate YOLO preview before new experiments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "outputs/multi_fidelity_region_preview_v1"
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def score_metrics(frame: pd.DataFrame, score: np.ndarray) -> dict[str, float]:
    score = np.nan_to_num(np.asarray(score, dtype=float), nan=0.0)
    costs = frame.full_scan_cost_sec.to_numpy(float)
    counts = frame.residual_event_count.to_numpy(float)
    order = np.argsort(-score, kind="stable")
    cumulative_cost = np.cumsum(costs[order])
    cumulative_count = np.cumsum(counts[order])
    total_cost, total_count = float(costs.sum()), float(counts.sum())

    def at(q: float) -> float:
        k = int(np.searchsorted(cumulative_cost, q * total_cost + 1e-12, side="right"))
        return float(cumulative_count[k - 1] / total_count) if k and total_count else 0.0

    curve = [at(float(q)) for q in np.linspace(0.0, 1.0, 101)]
    corr = spearmanr(score, counts).statistic
    binary = frame.binary_positive.astype(int).to_numpy()
    return {
        "recall_at_20": at(0.20),
        "ranking_event_recall_auc": float(np.trapezoid(curve, np.linspace(0.0, 1.0, 101))),
        "spearman_count": float(corr) if np.isfinite(corr) else 0.0,
        "binary_auprc": float(average_precision_score(binary, score)),
    }


def main() -> None:
    contract_path = PARENT / "contracts/preview_contracts/P1_L.json"
    contract = json.loads(contract_path.read_text())
    model_path = ROOT / contract["model_path"]
    deterministic = json.loads((PARENT / "audits/determinism_audit.json").read_text())
    leakage = json.loads((PARENT / "audits/leakage_audit.json").read_text())
    cost = json.loads((PARENT / "audits/preview_cost_audit.json").read_text())["configs"]["P1_L"]
    gate = json.loads((PARENT / "metrics/exploratory_gate.json").read_text())["component_gates"]["P1_L"]

    region1 = PARENT / "preview/p1_l/region_features_run1.parquet"
    region2 = PARENT / "preview/p1_l/region_features_run2.parquet"
    sample1 = PARENT / "preview/p1_l/sample_features_run1.parquet"
    sample2 = PARENT / "preview/p1_l/sample_features_run2.parquet"
    byte_determinism = sha256(region1) == sha256(region2) and sha256(sample1) == sha256(sample2)

    truth = pd.read_parquet(PARENT / "labels/region_table.parquet")
    pred = pd.read_parquet(PARENT / "predictions/nested_lovo_predictions.parquet")
    published = pd.read_csv(PARENT / "metrics/nested_branch_per_video_metrics.csv").query("preview == 'P1_L'")
    recomputed = []
    for video_id, frame in truth.groupby("video_id", sort=True):
        frame = frame.sort_values("region_index").reset_index(drop=True)
        score = pred.query("test_video_id == @video_id").set_index("region_id").loc[frame.region_id, "score"].to_numpy()
        row = {"video_id": video_id, **score_metrics(frame, score)}
        expected = published.query("video_id == @video_id").iloc[0]
        row["published_recall_at_20"] = float(expected.recall_at_20)
        row["published_auc"] = float(expected.ranking_event_recall_auc)
        row["metric_match"] = bool(
            abs(row["recall_at_20"] - row["published_recall_at_20"]) < 1e-12
            and abs(row["ranking_event_recall_auc"] - row["published_auc"]) < 1e-12
        )
        recomputed.append(row)

    implementation = ROOT / "scripts/run_mfrp_previews.py"
    source = implementation.read_text()
    # Parse executable literals, excluding the explanatory module docstring.
    executable = source[source.index("from __future__"):]
    forbidden_literals = [
        token for token in ("reference_events", "candidate_event_map", "scan_outputs", "full_scan_cache")
        if token in executable
    ]
    checks = {
        "contract_operator_exact": contract["operator"] == "YOLOV8N_DETECTION_ONLY_0P2FPS_320",
        "contract_rate_exact": contract["target_rate_fps"] == 0.2,
        "contract_resolution_exact": contract["resolution"] == "320x180_letterbox_to_320",
        "model_hash_match": sha256(model_path) == contract["model_sha256"],
        "two_run_byte_determinism": byte_determinism,
        "parent_canonical_determinism_pass": deterministic["configs"]["P1_L"]["hash_match"],
        "full_timeline_coverage": deterministic["configs"]["P1_L"]["full_timeline_coverage"],
        "no_missing_feature_cells": deterministic["configs"]["P1_L"]["missing_feature_cells"] == 0,
        "leakage_parent_pass": leakage["status"] == "PASS",
        "implementation_forbidden_literal_absent": not forbidden_literals,
        "cost_ratio_le_10pct": cost["preview_cost_ratio"] <= 0.10,
        "metrics_exactly_recomputed": all(row["metric_match"] for row in recomputed),
    }
    if not all(checks.values()):
        raise AssertionError({key: value for key, value in checks.items() if not value})

    result = {
        "hypothesis_id": "YGS-H001",
        "status": "ACCEPTED",
        "decision": "RETAIN_Q1_L_AS_FROZEN_GLOBAL_PREVIEW_BUT_DO_NOT_ADMIT_SCHEDULER",
        "checks": checks,
        "forbidden_literals": forbidden_literals,
        "operator": contract,
        "actual_conservative_cost_sec": cost["deployed_preview_cost_sec"],
        "actual_preview_cost_ratio": cost["preview_cost_ratio"],
        "recomputed_metrics": recomputed,
        "static_gate_all_checks_pass": gate["all_checks_pass"],
        "static_gate_failed_checks": [key for key, value in gate["checks"].items() if not value],
        "interpretation": "Q1-L is legal, deterministic, and cheap, but its Recall@20 is below 0.40 on both videos.",
        "implementation_hash": sha256(implementation),
        "verification_script_hash": sha256(Path(__file__)),
        "asset_hashes": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (contract_path, model_path, region1, region2, sample1, sample2)
        },
    }
    atomic_json(OUT / "hypotheses/YGS-H001.json", result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
