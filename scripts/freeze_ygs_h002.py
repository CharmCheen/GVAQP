#!/usr/bin/env python3
"""Freeze H002 selective high-rate YOLO escalation before execution."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "outputs/multi_fidelity_region_preview_v1"
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20): h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def main() -> None:
    truth = pd.read_parquet(PARENT / "labels/region_table.parquet")
    pred = pd.read_parquet(PARENT / "predictions/nested_lovo_predictions.parquet")
    selected_rows = []
    for video_id, regions in truth.groupby("video_id", sort=True):
        # Only public geometry/cost and cross-fitted Q1 predictions influence selection.
        public = regions.drop(columns=["residual_event_count", "binary_positive"]).copy()
        scores = pred.query("test_video_id == @video_id")[["region_id", "score", "binary_probability"]]
        public = public.merge(scores, on="region_id", validate="one_to_one")
        ranked = public.sort_values(["score", "region_id"], ascending=[False, True]).reset_index(drop=True)
        cumulative = ranked.full_scan_cost_sec.cumsum()
        boundary = int((cumulative <= 0.20 * ranked.full_scan_cost_sec.sum() + 1e-12).sum())
        ranked["rank_position"] = range(len(ranked))
        ranked["allocation_boundary_rank"] = boundary
        ranked["boundary_rank_distance"] = (ranked.rank_position - boundary + 0.5).abs()
        ranked["probability_uncertainty"] = (ranked.binary_probability - 0.5).abs()
        ranked = ranked.sort_values(
            ["boundary_rank_distance", "probability_uncertainty", "region_id"],
            ascending=[True, True, True],
        )
        duration_cap = 0.10 * float(public.actual_duration_sec.sum())
        used = 0.0
        for row in ranked.itertuples(index=False):
            if used + float(row.actual_duration_sec) <= duration_cap + 1e-12:
                used += float(row.actual_duration_sec)
                selected_rows.append({
                    "video_id": video_id, "region_id": row.region_id,
                    "region_index": int(row.region_index), "start_sec": float(row.start_sec),
                    "end_sec": float(row.end_sec), "actual_duration_sec": float(row.actual_duration_sec),
                    "q1_score": float(row.score), "q1_binary_probability": float(row.binary_probability),
                    "rank_position": int(row.rank_position), "allocation_boundary_rank": boundary,
                    "boundary_rank_distance": float(row.boundary_rank_distance),
                    "probability_uncertainty": float(row.probability_uncertainty),
                    "selection_reason": "Q1_20PCT_COST_BOUNDARY_UNCERTAINTY",
                })
    selection = pd.DataFrame(selected_rows).sort_values(["video_id", "region_index"])
    selection_path = OUT / "preview_experiments/YGS-H002/selected_regions.csv"
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection.to_csv(selection_path, index=False)
    summary = selection.groupby("video_id").agg(
        selected_regions=("region_id", "size"), selected_duration_sec=("actual_duration_sec", "sum")
    ).reset_index()
    totals = truth.groupby("video_id").actual_duration_sec.sum()
    summary["selected_duration_ratio"] = summary.apply(
        lambda row: row.selected_duration_sec / totals.loc[row.video_id], axis=1
    )
    contract = {
        "hypothesis_id": "YGS-H002",
        "frozen_before_q2_execution": True,
        "single_changed_mechanism": "selected-region 2-FPS YOLO detection escalation",
        "selection": {
            "source": "cross-fitted frozen Q1-L predictions plus public region geometry/cost",
            "allocation_boundary_cost_fraction": 0.20,
            "priority": ["boundary_rank_distance", "abs(binary_probability-0.5)", "region_id"],
            "per_video_duration_cap_fraction": 0.10,
            "high_score_only_selection": False,
            "label_access": False,
        },
        "operator": {
            "model": "models/yolo/yolov8n.pt", "model_sha256": sha256(ROOT / "models/yolo/yolov8n.pt"),
            "rate_fps": 2.0, "decoded_resolution": "320x180", "inference_imgsz": 320,
            "confidence": 0.25, "iou": 0.7, "classes": [0, 1, 2, 3, 5, 7],
            "tracking": False, "repeat_count": 2, "region_state_reset": True,
        },
        "value_models": {
            "families": ["LOGISTIC_REGRESSION", "POISSON_REGRESSION", "SHALLOW_LIGHTGBM"],
            "feature_selection": "train-fold-only, max two features per feature family",
            "nested_protocol": "leave-one-complete-video-out",
            "complexity_tie_rule": "prefer Logistic when primary difference <0.02",
        },
        "static_gate": "outputs/scan_innovation_agentic_loop_v1/contracts/static_gate.json",
        "selection_summary": summary.to_dict("records"),
        "input_hashes": {
            "q1_predictions": sha256(PARENT / "predictions/nested_lovo_predictions.parquet"),
            "region_table": sha256(PARENT / "labels/region_table.parquet"),
            "q1_features": sha256(PARENT / "features/region_features.parquet"),
            "selection_csv": sha256(selection_path),
        },
    }
    contract["freeze_script_hash"] = sha256(Path(__file__))
    atomic_json(OUT / "contracts/YGS-H002.json", contract)
    print(json.dumps(contract, indent=2, allow_nan=False))


if __name__ == "__main__": main()
