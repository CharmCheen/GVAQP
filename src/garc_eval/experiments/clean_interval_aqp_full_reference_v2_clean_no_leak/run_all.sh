#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."
python src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_clean_no_leak/pipeline.py all
python - <<'PY'
from pathlib import Path
import pandas as pd

out = Path("src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak")
features = pd.read_csv(out / "interval_lattice_features_only.csv", nrows=0)
forbidden = {
    "label_event",
    "label_available",
    "event_id",
    "matched_event_id",
    "answer_positive",
    "discovery_positive",
    "answer_iou_0_3",
    "answer_iou_0_5",
    "answer_overlap_purity",
    "event_hit_iou_0_3",
    "event_hit_iou_0_5",
    "positive_unit_fraction",
    "event_overlap_ratio",
    "interval_purity",
    "duration_inflation",
    "oracle_positive",
    "reference_event",
    "is_reference",
    "best_iou",
    "any_overlap",
    "center_hit",
    "oracle_upper_bound_score",
}
bad = sorted(set(features.columns) & forbidden)
if bad:
    raise SystemExit(f"BLOCKER: features-only leakage columns found: {bad}")
print("feature-only no-leak check PASS")
PY
