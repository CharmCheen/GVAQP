#!/usr/bin/env python3
"""Cost-charged labeled-support replay and explicit ARC compatibility gate."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cutin_p012_common import OUT, read_json, utc_now, write_json


def main() -> None:
    contract = read_json(OUT / "arc_baseline_contract.json")
    if contract["candidate_universe_match"]:
        raise RuntimeError("This gate is only valid for the audited asset-mismatch state")
    predictions = pd.read_parquet(OUT / "predictions/grouped_oof_predictions.parquet")
    runtime = read_json(OUT / "runtime_profile.json")
    methods = [
        "B-RAW-YOLO", "P0-LIGHTGBM", "P0-LOGISTIC", "P1-LIGHTGBM",
        "P1-LOGISTIC", "P2-LIGHTGBM", "P2-LOGISTIC",
    ]
    representation = {
        "B-RAW-YOLO": "P0", "P0-LIGHTGBM": "P0", "P0-LOGISTIC": "P0",
        "P1-LIGHTGBM": "P1", "P1-LOGISTIC": "P1",
        "P2-LIGHTGBM": "P2", "P2-LOGISTIC": "P2",
    }
    rows = []
    total_positives = int(
        predictions[
            predictions.method.eq("B-RAW-YOLO")
            & predictions.valid_for_confirmatory.astype(str).str.lower().eq("true")
        ].label_binary.sum()
    )
    for method in methods:
        block = predictions[
            predictions.method.eq(method)
            & predictions.valid_for_confirmatory.astype(str).str.lower().eq("true")
        ].sort_values(["score", "candidate_id"], ascending=[False, True])
        feature_cost = runtime["feature_cost_per_candidate"][representation[method]] * 96
        for k in [8, 16, 32]:
            head = block.head(k)
            positives = int(head.label_binary.eq(1).sum())
            confirm = float(head.oracle_latency_sec.sum())
            classifier = float(block.inference_seconds.sum())
            wall = feature_cost + classifier + confirm
            rows.append({
                "method": method, "representation": representation[method],
                "confirm_call_budget": k, "valid_labeled_candidate_universe": len(block),
                "confirmed_positive_candidates": positives,
                "candidate_recall": float(positives / total_positives),
                "feature_extraction_cost_sec": float(feature_cost),
                "classifier_inference_cost_sec": classifier,
                "confirm_generation_cost_sec": confirm,
                "materialization_commit_cost_sec": "NOT_SEPARATELY_AVAILABLE",
                "accounted_wall_sec_lower_bound": wall,
                "positive_candidates_per_accounted_minute_lower_bound": float(positives / wall * 60) if wall else 0.0,
                "status": "RESTRICTED_VALID_LABELED_SUPPORT_CANDIDATE_ONLY_EVENT_SYSTEM_BLOCKED",
            })
    frame = pd.DataFrame(rows)
    path = OUT / "metrics/labeled_support_cost_replay.csv"
    frame.to_csv(path, index=False)
    system = read_json(OUT / "metrics/system_metrics.json")
    system.update({
        "cost_replay_path": str(path.relative_to(OUT.parent.parent)),
        "cost_replay_status": (
            "RESTRICTED_VALID_LABELED_SUPPORT; TIME_LOWER_BOUND_ONLY; CLASSIFIER_INCLUDED; "
            "MATERIALIZATION_COMMIT_NOT_SEPARATELY_AVAILABLE"
        ),
        "ARC_FULL": "EXISTING_STRONG_OFFLINE_RESULT_OTHER_UNIVERSE_NOT_COMPARABLE",
        "ARC_SCHEDULER_plus_RAW_PROXY": "BLOCKED_ASSET_MISMATCH",
        "ARC_SCHEDULER_plus_P0": "BLOCKED_ASSET_MISMATCH",
        "ARC_SCHEDULER_plus_P1": "BLOCKED_ASSET_MISMATCH",
        "ARC_SCHEDULER_plus_P2": "BLOCKED_ASSET_MISMATCH",
        "created_at_utc": utc_now(),
    })
    write_json(OUT / "metrics/system_metrics.json", system)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
