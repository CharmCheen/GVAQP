#!/usr/bin/env python3
"""Execute frozen MFRP P1-L, P1-M, and P2 previews over full videos.

The implementation reads only immutable video metadata and source video bytes.
It never reads labels, references, candidate maps, full-SCAN caches, or policy
traces.  Every configuration is independently executed twice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import subprocess
import time

import cv2
import numpy as np
import pandas as pd
import psutil
import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
IMM = ROOT / "benchmarks/partial_scan_pilot_v1/immutable"
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
MODEL_PATH = ROOT / "models/yolo/yolov8n.pt"
REGION_LENGTH = 40.0
TARGET_CLASSES = [0, 1, 2, 3, 5, 7]
CONFIGS = {
    "P1_L": {"operator_id": "P1_L_YOLOV8N_0P2FPS_320", "rate": 0.2, "width": 320, "height": 180, "kind": "detector"},
    "P1_M": {"operator_id": "P1_M_YOLOV8N_0P5FPS_320", "rate": 0.5, "width": 320, "height": 180, "kind": "detector"},
    "P2": {"operator_id": "P2_SPARSE_MOTION_1FPS_160X90", "rate": 1.0, "width": 160, "height": 90, "kind": "motion"},
}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["video_id", "region_index"]).copy()
    numeric = ordered.select_dtypes(include=[np.number]).columns
    ordered[numeric] = ordered[numeric].round(8)
    return hashlib.sha256(ordered.to_csv(index=False, float_format="%.8g").encode()).hexdigest()


def memory_rss_bytes(process: subprocess.Popen | None = None) -> int:
    parent = psutil.Process()
    total = parent.memory_info().rss
    if process is not None:
        try:
            total += psutil.Process(process.pid).memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return int(total)


def aggregate_samples(samples: pd.DataFrame, video_id: str, duration: float,
                      config: dict) -> pd.DataFrame:
    count = int(math.ceil(duration / REGION_LENGTH))
    feature_columns = [
        column for column in samples.columns
        if column not in {"sample_index", "timestamp_sec", "region_index"}
    ]
    rows = []
    for index in range(count):
        start, end = index * REGION_LENGTH, min((index + 1) * REGION_LENGTH, duration)
        group = samples[samples.region_index.eq(index)]
        expected = max(1, int(math.ceil((end - start) * config["rate"])))
        row = {
            "source_preview": config["operator_id"], "video_id": video_id,
            "region_id": f"{video_id}_L040_R{index:04d}", "region_index": index,
            "start_sec": start, "end_sec": end, "actual_duration_sec": end - start,
            "region_duration_fraction": (end - start) / REGION_LENGTH,
            "preview_sample_count": int(len(group)),
            "expected_sample_count": expected,
            "valid_sample_fraction": min(1.0, len(group) / expected),
            "preview_missingness_fraction": 0.0 if len(group) else 1.0,
        }
        for column in feature_columns:
            values = group[column].to_numpy(dtype=float)
            prefix = f"{config['kind']}__{column}"
            if not len(values):
                row.update({
                    f"{prefix}__mean": 0.0, f"{prefix}__max": 0.0,
                    f"{prefix}__std": 0.0, f"{prefix}__q90": 0.0,
                    f"{prefix}__top3mean": 0.0, f"{prefix}__slope": 0.0,
                })
                continue
            x = np.arange(len(values), dtype=float)
            slope = float(np.polyfit(x, values, 1)[0]) if len(values) >= 2 else 0.0
            top = np.sort(values)[-min(3, len(values)):]
            row.update({
                f"{prefix}__mean": float(values.mean()),
                f"{prefix}__max": float(values.max()),
                f"{prefix}__std": float(values.std()),
                f"{prefix}__q90": float(np.quantile(values, 0.90)),
                f"{prefix}__top3mean": float(top.mean()),
                f"{prefix}__slope": slope,
            })
        rows.append(row)
    return pd.DataFrame(rows)


def p1_frame_features(result, previous: dict | None) -> dict:
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        classes = np.empty(0, dtype=int); confidence = np.empty(0)
        xyxyn = np.empty((0, 4))
    else:
        classes = boxes.cls.detach().cpu().numpy().astype(int)
        confidence = boxes.conf.detach().cpu().numpy().astype(float)
        xyxyn = boxes.xyxyn.detach().cpu().numpy().astype(float)
    count_by_class = {class_id: int(np.sum(classes == class_id)) for class_id in TARGET_CLASSES}
    if len(xyxyn):
        widths = np.clip(xyxyn[:, 2] - xyxyn[:, 0], 0, 1)
        heights = np.clip(xyxyn[:, 3] - xyxyn[:, 1], 0, 1)
        areas = widths * heights
        center_x = (xyxyn[:, 0] + xyxyn[:, 2]) / 2
        center_y = (xyxyn[:, 1] + xyxyn[:, 3]) / 2
        bottom_y = xyxyn[:, 3]
        center_mask = (center_x >= 0.25) & (center_x <= 0.75)
        road_center_mask = center_mask & (center_y >= 0.35)
        proportions = np.array([count_by_class[class_id] for class_id in TARGET_CLASSES], dtype=float)
        proportions /= max(proportions.sum(), 1.0)
        positive = proportions[proportions > 0]
        class_entropy = float(-(positive * np.log2(positive)).sum())
        features = {
            "object_count": float(len(classes)),
            "vehicle_count": float(sum(count_by_class[c] for c in (2, 3, 5, 7))),
            "vulnerable_count": float(sum(count_by_class[c] for c in (0, 1))),
            "person_count": float(count_by_class[0]), "bicycle_count": float(count_by_class[1]),
            "car_count": float(count_by_class[2]), "motorcycle_count": float(count_by_class[3]),
            "bus_count": float(count_by_class[5]), "truck_count": float(count_by_class[7]),
            "confidence_mean": float(confidence.mean()), "confidence_max": float(confidence.max()),
            "bbox_area_mean": float(areas.mean()), "bbox_area_max": float(areas.max()),
            "bbox_area_q90": float(np.quantile(areas, 0.9)),
            "bbox_center_x_std": float(center_x.std()), "bbox_center_y_mean": float(center_y.mean()),
            "bbox_bottom_y_mean": float(bottom_y.mean()), "bbox_bottom_y_max": float(bottom_y.max()),
            "center_occupancy_count": float(center_mask.sum()),
            "road_center_occupancy_count": float(road_center_mask.sum()),
            "large_bbox_count": float((areas >= 0.04).sum()), "class_entropy": class_entropy,
        }
    else:
        features = {key: 0.0 for key in (
            "object_count", "vehicle_count", "vulnerable_count", "person_count", "bicycle_count",
            "car_count", "motorcycle_count", "bus_count", "truck_count", "confidence_mean",
            "confidence_max", "bbox_area_mean", "bbox_area_max", "bbox_area_q90",
            "bbox_center_x_std", "bbox_center_y_mean", "bbox_bottom_y_mean", "bbox_bottom_y_max",
            "center_occupancy_count", "road_center_occupancy_count", "large_bbox_count", "class_entropy",
        )}
    previous = previous or features
    features.update({
        "object_count_change_abs": abs(features["object_count"] - previous["object_count"]),
        "vehicle_count_change_abs": abs(features["vehicle_count"] - previous["vehicle_count"]),
        "bbox_area_max_change_abs": abs(features["bbox_area_max"] - previous["bbox_area_max"]),
        "detection_burst": float(features["object_count"] >= previous["object_count"] + 3),
        "empty_frame": float(features["object_count"] == 0),
        "coarse_center_trigger": float(features["road_center_occupancy_count"] > 0 and features["bbox_area_max"] >= 0.01),
    })
    return features


def run_detector(video: pd.Series, config: dict, run_index: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    width, height = config["width"], config["height"]
    command = [
        "ffmpeg", "-v", "error", "-skip_frame", "nokey", "-i", str(video.video_path),
        "-vf", f"fps={config['rate']:g},scale={width}:{height}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    frame_bytes = width * height * 3
    torch.manual_seed(20260726); np.random.seed(20260726)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(20260726); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    wall_start = time.perf_counter()
    model_start = time.perf_counter(); model = YOLO(str(MODEL_PATH)); model_time = time.perf_counter() - model_start
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    decode_time = feature_time = 0.0
    peak_cpu = memory_rss_bytes(process)
    sample_rows = []
    batch_frames, batch_indices = [], []
    sample_index = 0
    previous = None

    def consume_batch() -> None:
        nonlocal model_time, feature_time, previous, peak_cpu
        if not batch_frames:
            return
        start = time.perf_counter()
        results = model.predict(
            source=batch_frames, imgsz=320, conf=0.25, iou=0.7,
            classes=TARGET_CLASSES, device=0 if torch.cuda.is_available() else "cpu",
            half=torch.cuda.is_available(), max_det=100, verbose=False, stream=False,
        )
        model_time += time.perf_counter() - start
        start = time.perf_counter()
        for index, result in zip(batch_indices, results):
            values = p1_frame_features(result, previous)
            previous = dict(values)
            timestamp = index / config["rate"]
            region_count = int(math.ceil(float(video.duration_sec) / REGION_LENGTH))
            sample_rows.append({
                "sample_index": index, "timestamp_sec": timestamp,
                "region_index": min(int(timestamp // REGION_LENGTH), region_count - 1), **values,
            })
        feature_time += time.perf_counter() - start
        peak_cpu = max(peak_cpu, memory_rss_bytes(process))
        batch_frames.clear(); batch_indices.clear()

    assert process.stdout is not None
    while True:
        start = time.perf_counter(); payload = process.stdout.read(frame_bytes); decode_time += time.perf_counter() - start
        if not payload:
            break
        if len(payload) != frame_bytes:
            process.kill(); raise RuntimeError(f"partial detector frame {len(payload)}/{frame_bytes}")
        batch_frames.append(np.frombuffer(payload, dtype=np.uint8).reshape(height, width, 3).copy())
        batch_indices.append(sample_index); sample_index += 1
        if len(batch_frames) >= 64:
            consume_batch()
    consume_batch()
    stderr = process.stderr.read().decode() if process.stderr is not None else ""
    if process.wait() != 0:
        raise RuntimeError(stderr)
    total = time.perf_counter() - wall_start
    samples = pd.DataFrame(sample_rows)
    regions = aggregate_samples(samples, str(video.video_id), float(video.duration_sec), config)
    runtime = {
        "operator_id": config["operator_id"], "video_id": str(video.video_id), "run_index": run_index,
        "source_video_sha256": sha256(Path(video.video_path)), "model_sha256": sha256(MODEL_PATH),
        "target_rate_fps": config["rate"], "resolution": f"{width}x{height}",
        "sample_count": len(samples), "region_count": len(regions),
        "decode_time_sec": decode_time, "model_time_sec": model_time,
        "feature_time_sec": feature_time, "total_wallclock_sec": total,
        "seconds_per_video_hour": total / float(video.duration_sec) * 3600.0,
        "peak_cpu_memory_bytes": peak_cpu,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0,
        "process_lifetime_max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "missing_feature_cells": int(regions.isna().sum().sum()),
        "zero_sample_regions": int(regions.preview_sample_count.eq(0).sum()),
        "ffmpeg_command": command,
    }
    return samples, regions, runtime


def motion_features(gray: np.ndarray, previous_gray: np.ndarray | None,
                    previous_hist: np.ndarray | None, previous_edge: float | None) -> tuple[dict, np.ndarray, np.ndarray, float]:
    hist = cv2.calcHist([gray], [0], None, [32], [0, 256]).reshape(-1)
    hist /= max(float(hist.sum()), 1.0)
    edge = float(np.mean(cv2.Canny(gray, 60, 120) > 0))
    if previous_gray is None:
        values = {key: 0.0 for key in (
            "frame_diff_mean", "frame_diff_std", "frame_diff_max", "active_area_ratio_10",
            "active_area_ratio_25", "center_active_ratio", "horizontal_activity_balance",
            "vertical_activity_balance", "motion_centroid_x", "motion_centroid_y",
            "histogram_l1_change", "edge_density_change", "scene_change", "motion_burst",
        )}
    else:
        diff = cv2.absdiff(gray, previous_gray).astype(float)
        active = diff >= 10
        h, w = gray.shape
        center = active[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
        weights = diff + 1e-6
        x_coordinate = np.linspace(-1, 1, w)[None, :]
        y_coordinate = np.linspace(-1, 1, h)[:, None]
        diff_mean = float(diff.mean())
        hist_change = float(np.abs(hist - previous_hist).sum()) if previous_hist is not None else 0.0
        values = {
            "frame_diff_mean": diff_mean, "frame_diff_std": float(diff.std()),
            "frame_diff_max": float(diff.max()), "active_area_ratio_10": float(active.mean()),
            "active_area_ratio_25": float(np.mean(diff >= 25)), "center_active_ratio": float(center.mean()),
            "horizontal_activity_balance": float((weights * x_coordinate).sum() / weights.sum()),
            "vertical_activity_balance": float((weights * y_coordinate).sum() / weights.sum()),
            "motion_centroid_x": float(((weights * (x_coordinate + 1) / 2).sum() / weights.sum())),
            "motion_centroid_y": float(((weights * (y_coordinate + 1) / 2).sum() / weights.sum())),
            "histogram_l1_change": hist_change,
            "edge_density_change": abs(edge - (previous_edge or 0.0)),
            "scene_change": float(hist_change >= 0.45),
            "motion_burst": float(diff_mean >= 20.0 or np.mean(diff >= 25) >= 0.15),
        }
    return values, gray, hist, edge


def run_motion(video: pd.Series, config: dict, run_index: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    width, height = config["width"], config["height"]
    command = [
        "ffmpeg", "-v", "error", "-i", str(video.video_path),
        "-vf", f"fps={config['rate']:g},scale={width}:{height}",
        "-pix_fmt", "gray", "-f", "rawvideo", "-",
    ]
    frame_bytes = width * height
    wall_start = time.perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    decode_time = feature_time = 0.0
    peak_cpu = memory_rss_bytes(process)
    rows = []
    previous_gray = previous_hist = None; previous_edge = None
    index = 0
    assert process.stdout is not None
    while True:
        start = time.perf_counter(); payload = process.stdout.read(frame_bytes); decode_time += time.perf_counter() - start
        if not payload:
            break
        if len(payload) != frame_bytes:
            process.kill(); raise RuntimeError(f"partial motion frame {len(payload)}/{frame_bytes}")
        start = time.perf_counter()
        gray = np.frombuffer(payload, dtype=np.uint8).reshape(height, width)
        values, previous_gray, previous_hist, previous_edge = motion_features(gray, previous_gray, previous_hist, previous_edge)
        feature_time += time.perf_counter() - start
        timestamp = index / config["rate"]
        region_count = int(math.ceil(float(video.duration_sec) / REGION_LENGTH))
        rows.append({
            "sample_index": index, "timestamp_sec": timestamp,
            "region_index": min(int(timestamp // REGION_LENGTH), region_count - 1), **values,
        })
        index += 1
        if index % 128 == 0:
            peak_cpu = max(peak_cpu, memory_rss_bytes(process))
    stderr = process.stderr.read().decode() if process.stderr is not None else ""
    if process.wait() != 0:
        raise RuntimeError(stderr)
    total = time.perf_counter() - wall_start
    samples = pd.DataFrame(rows)
    regions = aggregate_samples(samples, str(video.video_id), float(video.duration_sec), config)
    runtime = {
        "operator_id": config["operator_id"], "video_id": str(video.video_id), "run_index": run_index,
        "source_video_sha256": sha256(Path(video.video_path)), "model_sha256": None,
        "target_rate_fps": config["rate"], "resolution": f"{width}x{height}",
        "sample_count": len(samples), "region_count": len(regions),
        "decode_time_sec": decode_time, "model_time_sec": 0.0,
        "feature_time_sec": feature_time, "total_wallclock_sec": total,
        "seconds_per_video_hour": total / float(video.duration_sec) * 3600.0,
        "peak_cpu_memory_bytes": peak_cpu, "peak_gpu_memory_bytes": 0,
        "process_lifetime_max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "missing_feature_cells": int(regions.isna().sum().sum()),
        "zero_sample_regions": int(regions.preview_sample_count.eq(0).sum()),
        "ffmpeg_command": command,
    }
    return samples, regions, runtime


def run_config(name: str) -> None:
    config = CONFIGS[name]
    videos = pd.read_csv(IMM / "videos.csv")
    output_directory = OUT / "preview" / name.lower()
    output_directory.mkdir(parents=True, exist_ok=True)
    hashes = []
    for run_index in (1, 2):
        sample_tables, region_tables, runtimes = [], [], []
        for video in videos.itertuples(index=False):
            row = pd.Series(video._asdict())
            if config["kind"] == "detector":
                samples, regions, runtime = run_detector(row, config, run_index)
            else:
                samples, regions, runtime = run_motion(row, config, run_index)
            sample_tables.append(samples.assign(video_id=video.video_id))
            region_tables.append(regions); runtimes.append(runtime)
            write_json(OUT / f"preview/runtime_samples/{name}__{video.video_id}__run{run_index}.json", runtime)
        all_samples = pd.concat(sample_tables, ignore_index=True)
        all_regions = pd.concat(region_tables, ignore_index=True)
        all_samples.to_parquet(output_directory / f"sample_features_run{run_index}.parquet", index=False)
        all_regions.to_parquet(output_directory / f"region_features_run{run_index}.parquet", index=False)
        hashes.append(canonical_hash(all_regions))
        write_json(output_directory / f"run{run_index}_manifest.json", {
            "config": config, "run_index": run_index, "region_feature_hash": hashes[-1],
            "region_count": len(all_regions), "sample_count": len(all_samples),
            "missing_feature_cells": int(all_regions.isna().sum().sum()),
            "zero_sample_regions": int(all_regions.preview_sample_count.eq(0).sum()),
            "runtime_total_sec": sum(row["total_wallclock_sec"] for row in runtimes),
        })
    if hashes[0] != hashes[1]:
        raise RuntimeError(f"{name} determinism failure: {hashes}")
    write_json(output_directory / "operator_manifest.json", {
        "config": config, "run1_hash": hashes[0], "run2_hash": hashes[1],
        "deterministic_hash_match": True, "full_timeline_video_count": len(videos),
        "input_contract": "IMMUTABLE_VIDEOS_CSV_AND_SOURCE_VIDEO_BYTES_ONLY",
        "forbidden_inputs_used": [],
    })
    print(json.dumps({"status": "PASS", "config": name, "hash": hashes[0]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=sorted(CONFIGS), required=True)
    args = parser.parse_args()
    run_config(args.config)


if __name__ == "__main__":
    main()
