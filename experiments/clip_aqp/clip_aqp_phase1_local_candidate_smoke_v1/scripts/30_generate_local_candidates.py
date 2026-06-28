#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from local_candidate_common import CANDIDATE_COLUMNS, OUT, YOLO_N, append_progress, candidate_df, write_json


VEHICLE_CLASS_IDS = {2, 3, 5, 7}


def write_candidate(name: str, rows: list[dict]) -> pd.DataFrame:
    df = candidate_df(name, rows)
    df.to_csv(OUT / "candidates" / f"{name}.csv", index=False)
    return df


def fixed_windows(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for row in units.itertuples(index=False):
        rows.append(
            {
                "candidate_name": "fixed_sliding_window",
                "video_id": row.video_id,
                "returned_clip_id": row.unit_id,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "score": 1.0,
                "rank": 0,
                "generation_rule": "existing 5s clip units as fixed windows; no label access",
                "uses_oracle_annotation": False,
                "uses_video_content": False,
                "model_name": "none",
                "runtime_seconds": time.time() - t0,
                "notes": "debug baseline over local clip units",
            }
        )
    return write_candidate("fixed_sliding_window", rows)


def random_baseline(units: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260621)
    rows = []
    t0 = time.time()
    for row, score in zip(units.itertuples(index=False), rng.random(len(units))):
        rows.append(
            {
                "candidate_name": "random",
                "video_id": row.video_id,
                "returned_clip_id": row.unit_id,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "score": float(score),
                "rank": 0,
                "generation_rule": "fixed random seed random ranking",
                "uses_oracle_annotation": False,
                "uses_video_content": False,
                "model_name": "numpy_rng_seed_20260621",
                "runtime_seconds": time.time() - t0,
                "notes": "random baseline",
            }
        )
    return write_candidate("random", rows)


def motion_energy(units: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for unit in units.itertuples(index=False):
        group = frames[frames["unit_id"].astype(str) == str(unit.unit_id)].sort_values("timestamp")
        prev = None
        diffs = []
        for frame_path in group["frame_path"]:
            img = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            img = cv2.resize(img, (160, 90))
            if prev is not None:
                diffs.append(float(np.mean(cv2.absdiff(img, prev))) / 255.0)
            prev = img
        score = float(np.mean(diffs)) if diffs else 0.0
        rows.append(
            {
                "candidate_name": "motion_energy",
                "video_id": unit.video_id,
                "returned_clip_id": unit.unit_id,
                "start_time": unit.start_time,
                "end_time": unit.end_time,
                "score": score,
                "rank": 0,
                "generation_rule": "mean grayscale absolute frame difference over extracted clip frames",
                "uses_oracle_annotation": False,
                "uses_video_content": True,
                "model_name": "opencv_absdiff",
                "runtime_seconds": time.time() - t0,
                "notes": "low-cost CPU motion proxy",
            }
        )
    return write_candidate("motion_energy", rows)


def existing_proxy(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for unit in units.itertuples(index=False):
        rows.append(
            {
                "candidate_name": "existing_proxy_score",
                "video_id": unit.video_id,
                "returned_clip_id": unit.unit_id,
                "start_time": unit.start_time,
                "end_time": unit.end_time,
                "score": float(unit.proxy_score_existing) if str(unit.proxy_score_existing) != "" else 0.0,
                "rank": 0,
                "generation_rule": "reuse existing kinematic proxy score for debugging comparison",
                "uses_oracle_annotation": False,
                "uses_video_content": True,
                "model_name": "existing_kinematic_proxy",
                "runtime_seconds": time.time() - t0,
                "notes": "existing local proxy, not trained here",
            }
        )
    return write_candidate("existing_proxy_score", rows)


def yolo_count_proxy(units: pd.DataFrame, frames: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    dep = importlib.util.find_spec("ultralytics") is not None
    gpu = {"gpu_visible": False, "gpu_used": False, "gpu_model": "", "notes": ""}
    try:
        import torch

        gpu["gpu_visible"] = bool(torch.cuda.is_available())
        if gpu["gpu_visible"]:
            gpu["gpu_model"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    if not dep or not YOLO_N.exists():
        pd.DataFrame(columns=CANDIDATE_COLUMNS).to_csv(OUT / "candidates/yolo_count_proxy.csv", index=False)
        return pd.DataFrame(columns=CANDIDATE_COLUMNS), {**gpu, "status": "missing_dependency_or_model"}
    from ultralytics import YOLO

    t0 = time.time()
    model = YOLO(str(YOLO_N))
    device = 0 if gpu["gpu_visible"] else "cpu"
    gpu["gpu_used"] = bool(gpu["gpu_visible"])
    rows = []
    feature_rows = []
    frames_processed = 0
    for unit in units.itertuples(index=False):
        group = frames[frames["unit_id"].astype(str) == str(unit.unit_id)].sort_values("timestamp")
        vehicle_counts = []
        object_counts = []
        max_areas = []
        sum_areas = []
        for frame in group.itertuples(index=False):
            try:
                results = model.predict(str(frame.frame_path), imgsz=640, device=device, verbose=False)
            except Exception as exc:
                gpu["notes"] = f"prediction_error: {type(exc).__name__}: {exc}"
                continue
            frames_processed += 1
            h_img = 1.0
            w_img = 1.0
            img = cv2.imread(str(frame.frame_path))
            if img is not None:
                h_img, w_img = img.shape[:2]
            boxes = results[0].boxes if results else []
            obj_count = len(boxes)
            vehicle_count = 0
            areas = []
            for box in boxes:
                cls = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                xyxy = box.xyxy.cpu().numpy()[0]
                area = max(0.0, float(xyxy[2] - xyxy[0])) * max(0.0, float(xyxy[3] - xyxy[1])) / max(1.0, float(w_img * h_img))
                areas.append(area)
                if cls in VEHICLE_CLASS_IDS:
                    vehicle_count += 1
            object_counts.append(obj_count)
            vehicle_counts.append(vehicle_count)
            max_areas.append(max(areas) if areas else 0.0)
            sum_areas.append(sum(areas))
        count_change = float(max(vehicle_counts) - min(vehicle_counts)) if vehicle_counts else 0.0
        area_growth = float(max(sum_areas) - min(sum_areas)) if sum_areas else 0.0
        score = float(np.mean(vehicle_counts) + np.max(sum_areas) + count_change + area_growth) if vehicle_counts else 0.0
        feature_rows.append(
            {
                "unit_id": unit.unit_id,
                "object_count": float(np.mean(object_counts)) if object_counts else 0.0,
                "vehicle_count": float(np.mean(vehicle_counts)) if vehicle_counts else 0.0,
                "max_bbox_area": float(max(max_areas)) if max_areas else 0.0,
                "sum_bbox_area": float(max(sum_areas)) if sum_areas else 0.0,
                "count_change": count_change,
                "area_growth_proxy": area_growth,
            }
        )
        rows.append(
            {
                "candidate_name": "yolo_count_proxy",
                "video_id": unit.video_id,
                "returned_clip_id": unit.unit_id,
                "start_time": unit.start_time,
                "end_time": unit.end_time,
                "score": score,
                "rank": 0,
                "generation_rule": "YOLOv8n object/vehicle count and bbox area proxy over extracted frames",
                "uses_oracle_annotation": False,
                "uses_video_content": True,
                "model_name": str(YOLO_N),
                "runtime_seconds": time.time() - t0,
                "notes": "GPU used if CUDA visible; no training",
            }
        )
    pd.DataFrame(feature_rows).to_csv(OUT / "features/yolo_count_proxy_features.csv", index=False)
    df = write_candidate("yolo_count_proxy", rows)
    runtime = time.time() - t0
    return df, {**gpu, "status": "completed", "runtime_seconds": runtime, "frames_processed": frames_processed, "throughput_fps": frames_processed / runtime if runtime > 0 else 0.0}


def clip_siglip_placeholder() -> None:
    pd.DataFrame(columns=CANDIDATE_COLUMNS).to_csv(OUT / "candidates/optional_clip_or_siglip_score.csv", index=False)
    pd.DataFrame([{"candidate_name": "optional_clip_or_siglip_score", "status": "skipped_no_local_model_assets", "notes": "transformers import exists but no local CLIP/SigLIP model path was configured; no download allowed"}]).to_csv(OUT / "tables/optional_embedding_status.csv", index=False)


def main() -> int:
    units = pd.read_csv(OUT / "tables/local_smoke_units.csv")
    frames = pd.read_csv(OUT / "tables/local_frame_index.csv")
    fixed_windows(units)
    random_baseline(units)
    motion_energy(units, frames)
    existing_proxy(units)
    yolo_df, yolo_status = yolo_count_proxy(units, frames)
    clip_siglip_placeholder()
    write_json(OUT / "logs/gpu_usage.json", yolo_status)
    status_rows = [
        {"candidate_name": "fixed_sliding_window", "status": "completed", "uses_oracle_annotation": False},
        {"candidate_name": "random", "status": "completed", "uses_oracle_annotation": False},
        {"candidate_name": "motion_energy", "status": "completed", "uses_oracle_annotation": False},
        {"candidate_name": "existing_proxy_score", "status": "completed", "uses_oracle_annotation": False},
        {"candidate_name": "yolo_count_proxy", "status": yolo_status.get("status", ""), "uses_oracle_annotation": False},
        {"candidate_name": "optional_clip_or_siglip_score", "status": "skipped_no_local_model_assets", "uses_oracle_annotation": False},
    ]
    pd.DataFrame(status_rows).to_csv(OUT / "tables/local_candidate_generation_status.csv", index=False)
    append_progress("generate_candidates", "python scripts/30_generate_local_candidates.py", f"candidates=5, yolo_status={yolo_status.get('status')}", next_action="evaluate candidates")
    print(f"yolo_status={yolo_status.get('status')} gpu_used={yolo_status.get('gpu_used')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

