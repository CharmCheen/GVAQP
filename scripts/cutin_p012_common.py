#!/usr/bin/env python3
"""Shared constants and audit-safe I/O for the frozen Stage-A Q1 P0/P1/P2 study."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/cutin_p012_contract"
STAGE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a"
POOL = STAGE.parent
MODELING = STAGE / "modeling"
CONTRACT = ROOT / "docs/PSVR_P0_P1_P2_EXPERIMENT_CONTRACT.md"
QUERY_ID = "Q1"
CONTRACT_ID = "PSVR_CUTIN_P012_STAGE_A_Q1_V1"
ORACLE_CONTRACT_ID = "MF_PSVR_STAGE_A_ORACLE_V1"
EVENT_CONTRACT_ID = "consecutive_positive_units_v1"
SEED = 20260723


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


P0_FEATURES = [
    "frame_count", "detection_rate", "no_detection_fraction",
    "det_count_mean", "det_count_std", "det_count_q25", "det_count_q50",
    "det_count_q75", "det_count_max", "det_count_slope",
    "confidence_mean", "confidence_std", "confidence_q25", "confidence_q50",
    "confidence_q75", "confidence_max", "confidence_slope",
    "bbox_area_mean", "bbox_area_std", "bbox_area_q50", "bbox_area_q75",
    "bbox_area_max", "max_bbox_area_mean", "max_bbox_area_max",
    "bbox_area_slope", "center_x_mean", "center_x_std", "center_y_mean",
    "bottom_y_mean", "bottom_y_q75", "left_count_mean", "center_count_mean",
    "right_count_mean", "central_region_count_mean", "centroid_x_std",
    "centroid_y_std", "centroid_x_slope", "centroid_y_slope",
    "raw_yolo_score",
]

P1_INCREMENTAL = [
    "track_count", "track_observations_mean", "track_observations_max",
    "track_duration_mean_sec", "track_duration_max_sec", "track_gap_rate_mean",
    "track_confidence_mean", "track_confidence_max", "track_dx_abs_mean",
    "track_dx_abs_max", "track_dy_mean", "track_dy_max", "track_speed_x_abs_mean",
    "track_speed_x_abs_max", "track_speed_y_mean", "track_accel_x_abs_mean",
    "track_accel_y_abs_mean", "track_area_growth_mean", "track_area_growth_max",
    "track_center_approach_mean", "track_center_approach_max",
    "track_side_to_center_rate", "track_direction_change_mean",
    "track_stability_mean", "relative_distance_closing_max",
    "approach_speed_proxy_max", "ttc_like_urgency_max",
    "top1_candidate_score", "top3_candidate_score_mean",
]

P2_INCREMENTAL = [
    "camera_dx_mean", "camera_dx_std", "camera_dy_mean", "camera_dy_std",
    "camera_rotation_mean", "camera_rotation_std", "camera_scale_mean",
    "camera_scale_std", "motion_inlier_ratio_mean", "motion_track_count_mean",
    "motion_valid_fraction", "motion_valid", "motion_missing",
    "global_motion_magnitude",
    "comp_track_dx_abs_mean", "comp_track_dx_abs_max", "comp_track_dy_mean",
    "comp_track_speed_x_abs_mean", "comp_track_speed_y_mean",
    "comp_track_accel_x_abs_mean", "comp_track_accel_y_abs_mean",
    "comp_track_center_approach_mean", "comp_track_center_approach_max",
    "comp_track_side_to_center_rate", "comp_track_stability_mean",
]

PROHIBITED_MODEL_FIELDS = [
    "candidate_id", "video_id", "session_id", "source_dataset_id", "filename",
    "absolute_timestamp", "query_id", "oracle_label", "oracle_version",
    "oracle_latency_sec", "reference_event_id", "split", "split_group_id",
]

