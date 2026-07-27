#!/usr/bin/env python3
"""Freeze the bounded Phase-3 model grid before feature-label inspection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"


def main() -> None:
    configs = []
    for preview in ("P1_L", "P1_M", "P2"):
        configs.append({"preview": preview, "family": "HEURISTIC_SCORE"})
        for c in (0.01, 0.1, 1.0, 10.0):
            for class_weight in (None, "balanced"):
                configs.append({
                    "preview": preview, "family": "LOGISTIC_REGRESSION",
                    "C": c, "class_weight": class_weight, "penalty": "l2",
                })
        for alpha in (0.01, 0.1, 1.0, 10.0):
            configs.append({"preview": preview, "family": "POISSON_REGRESSION", "alpha": alpha})
        for depth in (2, 3):
            configs.append({
                "preview": preview, "family": "SHALLOW_LIGHTGBM", "max_depth": depth,
                "num_leaves": 2 ** depth, "min_child_samples": 10, "n_estimators": 100,
                "learning_rate": 0.05,
            })
    for index, config in enumerate(configs):
        config["config_id"] = f"MFRP_CFG_{index:02d}"
    assert len(configs) == 45
    payload = {
        "status": "FROZEN_BEFORE_UNIVARIATE_LABEL_METRICS",
        "config_count": len(configs), "model_family_count": len({row["family"] for row in configs}),
        "preview_branches": ["P1_L", "P1_M", "P2"],
        "feature_selection_per_training_fold": {
            "rule": "TOP_TRAIN_UNIVARIATE_RECALL20_THEN_AUC",
            "max_columns_per_feature_family": 2,
            "max_feature_families": 8,
            "metadata_and_time_columns": "EXCLUDED",
        },
        "nested_lovo": {
            "split_unit": "COMPLETE_VIDEO",
            "macro_length_rule": "TRAIN_VIDEO_LEAST_LABEL_SATURATION_THEN_MAX_REGION_COUNT",
            "schema_hyperparameters_selected_on_test": False,
        },
        "selection_rule": "MAX_MIN_TRAIN_RECALL20_THEN_MACRO_RECALL20_THEN_AUC_WITH_LOGISTIC_PREFERENCE_WITHIN_0P02",
        "configs": configs,
    }
    payload["manifest_hash"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = OUT / "contracts/model_search_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "config_count": len(configs), "hash": payload["manifest_hash"]}, indent=2))


if __name__ == "__main__":
    main()
