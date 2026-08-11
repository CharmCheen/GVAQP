#!/usr/bin/env python3
"""Materialize contract-frozen P0/P1/P2 features without reading Oracle labels."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import psutil

from cutin_p012_common import (
    OUT, P0_FEATURES, P1_INCREMENTAL, P2_INCREMENTAL, ROOT, STAGE,
    read_json, sha256_file, utc_now, write_json,
)

SAMPLE_FPS = 5.0
QUERY_CLASSES = {1, 2, 3, 5, 7}


def load_frozen_proxy():
    path = ROOT / "scripts/run_psvr_two_video_proxy.py"
    spec = importlib.util.spec_from_file_location("frozen_psvr_proxy", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def gpu_memory_mib() -> float:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=False,
    )
    try:
        return float(result.stdout.splitlines()[0])
    except (IndexError, ValueError):
        return math.nan


def finite(values: list[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array[np.isfinite(array)]


def stat(values, kind: str, default: float = 0.0) -> float:
    array = finite(values)
    if not len(array):
        return default
    if kind == "mean": return float(np.mean(array))
    if kind == "std": return float(np.std(array))
    if kind == "max": return float(np.max(array))
    if kind == "q25": return float(np.quantile(array, .25))
    if kind == "q50": return float(np.quantile(array, .50))
    if kind == "q75": return float(np.quantile(array, .75))
    raise KeyError(kind)


def slope(values) -> float:
    array = np.asarray(values, dtype=float)
    mask = np.isfinite(array)
    if mask.sum() < 2:
        return 0.0
    x = np.arange(len(array), dtype=float)[mask] / SAMPLE_FPS
    return float(np.polyfit(x, array[mask], 1)[0])


def motion_between(previous: np.ndarray | None, current: np.ndarray, boxes: np.ndarray) -> dict[str, Any]:
    result = {
        "dx": math.nan, "dy": math.nan, "rotation": math.nan, "scale": math.nan,
        "inlier_ratio": math.nan, "track_count": 0.0, "valid": 0.0,
    }
    if previous is None:
        return result
    height, width = current.shape
    mask = np.full((height, width), 255, dtype=np.uint8)
    for box in boxes:
        x1, y1, x2, y2 = [float(v) for v in box]
        pad_x, pad_y = .1 * (x2 - x1), .1 * (y2 - y1)
        cv2.rectangle(
            mask,
            (max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y))),
            (min(width - 1, int(x2 + pad_x)), min(height - 1, int(y2 + pad_y))),
            0, -1,
        )
    corners = cv2.goodFeaturesToTrack(
        previous, maxCorners=300, qualityLevel=.01, minDistance=7, mask=mask, blockSize=7
    )
    if corners is None or len(corners) < 8:
        return result
    nxt, status, _ = cv2.calcOpticalFlowPyrLK(
        previous, current, corners, None,
        winSize=(21, 21), maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01),
    )
    if nxt is None or status is None:
        return result
    keep = status.reshape(-1).astype(bool)
    source = corners.reshape(-1, 2)[keep]
    target = nxt.reshape(-1, 2)[keep]
    result["track_count"] = float(len(source))
    if len(source) < 8:
        return result
    matrix, inliers = cv2.estimateAffinePartial2D(
        source, target, method=cv2.RANSAC, ransacReprojThreshold=2.0,
        maxIters=2000, confidence=.99, refineIters=10,
    )
    if matrix is None or inliers is None:
        return result
    a, b, tx = matrix[0]
    c, d, ty = matrix[1]
    scale = math.sqrt(max(0.0, a * a + c * c))
    ratio = float(np.mean(inliers))
    if not np.isfinite(scale) or scale < .8 or scale > 1.25 or ratio < .25:
        return result
    result.update({
        "dx": float(tx / width), "dy": float(ty / height),
        "rotation": float(math.atan2(c, a)), "scale": float(scale),
        "inlier_ratio": ratio, "valid": 1.0,
        "matrix": matrix.astype(float).tolist(), "width": float(width), "height": float(height),
    })
    return result


def aggregate_p0(frames: list[dict[str, Any]]) -> dict[str, float]:
    counts = [f["count"] for f in frames]
    conf = [v for f in frames for v in f["conf"]]
    areas = [v for f in frames for v in f["area"]]
    cx = [v for f in frames for v in f["cx"]]
    cy = [v for f in frames for v in f["cy"]]
    bottom = [v for f in frames for v in f["bottom"]]
    max_area = [max(f["area"]) if f["area"] else 0.0 for f in frames]
    centroid_x = [np.mean(f["cx"]) if f["cx"] else math.nan for f in frames]
    centroid_y = [np.mean(f["cy"]) if f["cy"] else math.nan for f in frames]
    nonempty = sum(c > 0 for c in counts)
    values = {
        "frame_count": float(len(frames)),
        "detection_rate": nonempty / max(1, len(frames)),
        "no_detection_fraction": 1 - nonempty / max(1, len(frames)),
        "raw_yolo_score": stat(conf, "max"),
    }
    for key, data, kinds in [
        ("det_count", counts, ["mean", "std", "q25", "q50", "q75", "max"]),
        ("confidence", conf, ["mean", "std", "q25", "q50", "q75", "max"]),
        ("bbox_area", areas, ["mean", "std", "q50", "q75", "max"]),
    ]:
        for kind in kinds:
            values[f"{key}_{kind}"] = stat(data, kind)
    values.update({
        "det_count_slope": slope(counts),
        "confidence_slope": slope([np.mean(f["conf"]) if f["conf"] else 0.0 for f in frames]),
        "max_bbox_area_mean": stat(max_area, "mean"),
        "max_bbox_area_max": stat(max_area, "max"),
        "bbox_area_slope": slope(max_area),
        "center_x_mean": stat(cx, "mean"), "center_x_std": stat(cx, "std"),
        "center_y_mean": stat(cy, "mean"), "bottom_y_mean": stat(bottom, "mean"),
        "bottom_y_q75": stat(bottom, "q75"),
        "left_count_mean": stat([f["left"] for f in frames], "mean"),
        "center_count_mean": stat([f["center"] for f in frames], "mean"),
        "right_count_mean": stat([f["right"] for f in frames], "mean"),
        "central_region_count_mean": stat([f["central"] for f in frames], "mean"),
        "centroid_x_std": stat(centroid_x, "std"), "centroid_y_std": stat(centroid_y, "std"),
        "centroid_x_slope": slope(centroid_x), "centroid_y_slope": slope(centroid_y),
    })
    assert set(values) == set(P0_FEATURES), (set(P0_FEATURES) - set(values), set(values) - set(P0_FEATURES))
    return values


def track_summary(observations: list[dict[str, float]], camera: list[dict[str, Any]]) -> dict[str, float]:
    observations = sorted(observations, key=lambda x: x["step"])
    first, last = observations[0], observations[-1]
    dt = max(1 / SAMPLE_FPS, last["time"] - first["time"])
    dx, dy = last["cx"] - first["cx"], last["cy"] - first["cy"]
    vx, vy, ax, ay, comp_dx, comp_dy = [], [], [], [], [], []
    # Express every observed centre in the first observation's coordinate
    # frame. This makes displacements, acceleration, centre approach, and
    # side-to-centre tests geometrically comparable under rotation and scale.
    common_points: list[np.ndarray | None] = []
    first_step = int(first["step"])
    for observation in observations:
        point = np.array([observation["cx"], observation["cy"]], dtype=float)
        valid_chain = True
        for step in range(int(observation["step"]), first_step, -1):
            cam = camera[step]
            if cam["valid"] <= 0 or "matrix" not in cam:
                valid_chain = False
                break
            width, height = cam["width"], cam["height"]
            pixel = np.array([point[0] * width, point[1] * height, 1.0])
            prior = cv2.invertAffineTransform(np.asarray(cam["matrix"], dtype=float)) @ pixel
            point = np.array([prior[0] / width, prior[1] / height])
        common_points.append(point if valid_chain else None)
    prior_vx = prior_vy = None
    direction_changes = 0
    previous_sign = 0
    for obs_index, (left, right) in enumerate(zip(observations, observations[1:])):
        delta_t = max(1 / SAMPLE_FPS, right["time"] - left["time"])
        this_vx = (right["cx"] - left["cx"]) / delta_t
        this_vy = (right["cy"] - left["cy"]) / delta_t
        vx.append(this_vx); vy.append(this_vy)
        sign = int(np.sign(this_vx))
        if previous_sign and sign and sign != previous_sign:
            direction_changes += 1
        if sign:
            previous_sign = sign
        if prior_vx is not None:
            ax.append((this_vx - prior_vx) / delta_t)
            ay.append((this_vy - prior_vy) / delta_t)
        prior_vx, prior_vy = this_vx, this_vy
        left_common, right_common = common_points[obs_index:obs_index + 2]
        if left_common is not None and right_common is not None:
            comp_dx.append(float(right_common[0] - left_common[0]))
            comp_dy.append(float(right_common[1] - left_common[1]))
        else:
            comp_dx.append(math.nan); comp_dy.append(math.nan)
    comp_vx = [v * SAMPLE_FPS for v in comp_dx]
    comp_vy = [v * SAMPLE_FPS for v in comp_dy]
    comp_ax = np.diff(finite(comp_vx)) * SAMPLE_FPS if len(finite(comp_vx)) > 1 else []
    comp_ay = np.diff(finite(comp_vy)) * SAMPLE_FPS if len(finite(comp_vy)) > 1 else []
    expected = int(round(dt * SAMPLE_FPS)) + 1
    area_growth = math.log(max(last["area"], 1e-9) / max(first["area"], 1e-9)) / dt
    center_approach = (abs(first["cx"] - .5) - abs(last["cx"] - .5)) / dt
    side_to_center = float(abs(first["cx"] - .5) > .2 and abs(last["cx"] - .5) <= .2)
    comp_center_approach = center_approach
    comp_side_to_center = math.nan
    if common_points[-1] is not None:
        comp_last_x = float(common_points[-1][0])
        comp_center_approach = (abs(first["cx"] - .5) - abs(comp_last_x - .5)) / dt
        comp_side_to_center = float(abs(first["cx"] - .5) > .2 and abs(comp_last_x - .5) <= .2)
    comp_net_dx = (
        float(common_points[-1][0] - common_points[0][0])
        if common_points[-1] is not None else math.nan
    )
    comp_net_dy = (
        float(common_points[-1][1] - common_points[0][1])
        if common_points[-1] is not None else math.nan
    )
    stability = 1.0 / (1.0 + stat(ax, "std") + stat(ay, "std"))
    comp_stability = 1.0 / (1.0 + stat(comp_ax, "std") + stat(comp_ay, "std"))
    ttc = max(0.0, (last["height"] - first["height"]) / dt / max(last["height"], 1e-9))
    return {
        "observations": float(len(observations)), "duration": dt,
        "gap_rate": max(0.0, 1 - len(observations) / max(1, expected)),
        "confidence": stat([o["conf"] for o in observations], "mean"),
        "dx_abs": abs(dx), "dy": dy, "speed_x_abs": abs(dx) / dt, "speed_y": dy / dt,
        "accel_x_abs": stat(np.abs(ax), "mean"), "accel_y_abs": stat(np.abs(ay), "mean"),
        "area_growth": area_growth, "center_approach": center_approach,
        "side_to_center": side_to_center,
        "direction_change": direction_changes / max(1, len(observations) - 2),
        "stability": stability, "ttc": ttc,
        "comp_dx_abs": abs(comp_net_dx),
        "comp_dy": comp_net_dy,
        "comp_speed_x_abs": stat(np.abs(comp_vx), "mean", math.nan),
        "comp_speed_y": stat(comp_vy, "mean", math.nan),
        "comp_accel_x_abs": stat(np.abs(comp_ax), "mean", math.nan),
        "comp_accel_y_abs": stat(np.abs(comp_ay), "mean", math.nan),
        "comp_center_approach": comp_center_approach if common_points[-1] is not None else math.nan,
        "comp_side_to_center": comp_side_to_center,
        "comp_stability": comp_stability if len(finite(comp_dx)) else math.nan,
        "score": float(np.mean([
            min(1.0, len(observations) / 25), max(0.0, center_approach),
            max(0.0, area_growth), max(o["bottom"] for o in observations), min(1.0, ttc),
        ])),
    }


def aggregate_p1(tracks: dict[int, list[dict[str, float]]], camera: list[dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    summaries = [track_summary(values, camera) for values in tracks.values() if values]
    def vals(key): return [s[key] for s in summaries]
    p1 = {
        "track_count": float(len(summaries)),
        "track_observations_mean": stat(vals("observations"), "mean"),
        "track_observations_max": stat(vals("observations"), "max"),
        "track_duration_mean_sec": stat(vals("duration"), "mean"),
        "track_duration_max_sec": stat(vals("duration"), "max"),
        "track_gap_rate_mean": stat(vals("gap_rate"), "mean"),
        "track_confidence_mean": stat(vals("confidence"), "mean"),
        "track_confidence_max": stat(vals("confidence"), "max"),
        "track_dx_abs_mean": stat(vals("dx_abs"), "mean"),
        "track_dx_abs_max": stat(vals("dx_abs"), "max"),
        "track_dy_mean": stat(vals("dy"), "mean"), "track_dy_max": stat(vals("dy"), "max"),
        "track_speed_x_abs_mean": stat(vals("speed_x_abs"), "mean"),
        "track_speed_x_abs_max": stat(vals("speed_x_abs"), "max"),
        "track_speed_y_mean": stat(vals("speed_y"), "mean"),
        "track_accel_x_abs_mean": stat(vals("accel_x_abs"), "mean"),
        "track_accel_y_abs_mean": stat(vals("accel_y_abs"), "mean"),
        "track_area_growth_mean": stat(vals("area_growth"), "mean"),
        "track_area_growth_max": stat(vals("area_growth"), "max"),
        "track_center_approach_mean": stat(vals("center_approach"), "mean"),
        "track_center_approach_max": stat(vals("center_approach"), "max"),
        "track_side_to_center_rate": stat(vals("side_to_center"), "mean"),
        "track_direction_change_mean": stat(vals("direction_change"), "mean"),
        "track_stability_mean": stat(vals("stability"), "mean"),
        "relative_distance_closing_max": stat(vals("area_growth"), "max"),
        "approach_speed_proxy_max": stat(vals("speed_y"), "max"),
        "ttc_like_urgency_max": stat(vals("ttc"), "max"),
        "top1_candidate_score": stat(vals("score"), "max"),
        "top3_candidate_score_mean": stat(sorted(vals("score"), reverse=True)[:3], "mean"),
    }
    valid_motion = [m for m in camera if m["valid"] > 0]
    p2 = {
        "camera_dx_mean": stat([m["dx"] for m in valid_motion], "mean", math.nan),
        "camera_dx_std": stat([m["dx"] for m in valid_motion], "std", math.nan),
        "camera_dy_mean": stat([m["dy"] for m in valid_motion], "mean", math.nan),
        "camera_dy_std": stat([m["dy"] for m in valid_motion], "std", math.nan),
        "camera_rotation_mean": stat([m["rotation"] for m in valid_motion], "mean", math.nan),
        "camera_rotation_std": stat([m["rotation"] for m in valid_motion], "std", math.nan),
        "camera_scale_mean": stat([m["scale"] for m in valid_motion], "mean", math.nan),
        "camera_scale_std": stat([m["scale"] for m in valid_motion], "std", math.nan),
        "motion_inlier_ratio_mean": stat([m["inlier_ratio"] for m in valid_motion], "mean", math.nan),
        "motion_track_count_mean": stat([m["track_count"] for m in camera], "mean"),
        "motion_valid_fraction": len(valid_motion) / max(1, len(camera)),
        "motion_valid": float(bool(valid_motion)),
        "motion_missing": float(not bool(valid_motion)),
        "global_motion_magnitude": stat(
            [math.hypot(m["dx"], m["dy"]) for m in valid_motion], "mean", math.nan
        ),
        "comp_track_dx_abs_mean": stat(vals("comp_dx_abs"), "mean", math.nan),
        "comp_track_dx_abs_max": stat(vals("comp_dx_abs"), "max", math.nan),
        "comp_track_dy_mean": stat(vals("comp_dy"), "mean", math.nan),
        "comp_track_speed_x_abs_mean": stat(vals("comp_speed_x_abs"), "mean", math.nan),
        "comp_track_speed_y_mean": stat(vals("comp_speed_y"), "mean", math.nan),
        "comp_track_accel_x_abs_mean": stat(vals("comp_accel_x_abs"), "mean", math.nan),
        "comp_track_accel_y_abs_mean": stat(vals("comp_accel_y_abs"), "mean", math.nan),
        "comp_track_center_approach_mean": stat(vals("comp_center_approach"), "mean", math.nan),
        "comp_track_center_approach_max": stat(vals("comp_center_approach"), "max", math.nan),
        "comp_track_side_to_center_rate": stat(vals("comp_side_to_center"), "mean", math.nan),
        "comp_track_stability_mean": stat(vals("comp_stability"), "mean", math.nan),
    }
    assert set(p1) == set(P1_INCREMENTAL)
    assert set(p2) == set(P2_INCREMENTAL)
    return p1, p2


def extract_one(row: Any, detector: Any, frozen: Any) -> tuple[dict, dict, dict, dict]:
    path = ROOT / row.local_locator
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    interval = max(1, int(round(fps / SAMPLE_FPS)))
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, int(row.start_frame)):
        raise RuntimeError(f"Cannot seek {path}")
    tracker = frozen.make_tracker()
    frames: list[dict[str, Any]] = []
    tracks: dict[int, list[dict[str, float]]] = defaultdict(list)
    camera: list[dict[str, float]] = []
    previous_gray = None
    timings = defaultdict(float)
    peak_gpu = gpu_memory_mib()
    peak_rss = psutil.Process().memory_info().rss / (1024 ** 2)
    started_all = time.perf_counter()
    try:
        step = 0
        for frame_index in range(int(row.start_frame), int(row.end_frame) + 1):
            started = time.perf_counter()
            ok, frame = capture.read()
            timings["decode_seconds"] += time.perf_counter() - started
            if not ok:
                raise RuntimeError(f"decode failure {row.physical_call_id}:{frame_index}")
            if (frame_index - int(row.start_frame)) % interval:
                continue
            boxes, scores, classes, _, detector_seconds = detector.detect(frame)
            timings["detection_seconds"] += float(detector_seconds)
            keep = np.isin(classes.astype(int), list(QUERY_CLASSES))
            boxes, scores, classes = boxes[keep], scores[keep], classes[keep]
            height, width = frame.shape[:2]
            norm_boxes = boxes.copy().astype(float)
            if len(norm_boxes):
                norm_boxes[:, [0, 2]] /= width
                norm_boxes[:, [1, 3]] /= height
            area = ((norm_boxes[:, 2] - norm_boxes[:, 0]) * (norm_boxes[:, 3] - norm_boxes[:, 1])).tolist()
            cx = ((norm_boxes[:, 0] + norm_boxes[:, 2]) / 2).tolist()
            cy = ((norm_boxes[:, 1] + norm_boxes[:, 3]) / 2).tolist()
            bottom = norm_boxes[:, 3].tolist()
            frames.append({
                "count": len(boxes), "conf": scores.astype(float).tolist(), "area": area,
                "cx": cx, "cy": cy, "bottom": bottom,
                "left": sum(v < 1/3 for v in cx), "center": sum(1/3 <= v <= 2/3 for v in cx),
                "right": sum(v > 2/3 for v in cx),
                "central": sum(abs(x - .5) <= .2 and y >= .45 for x, y in zip(cx, bottom)),
            })
            started = time.perf_counter()
            active = tracker.update(frozen.TrackerDetections(boxes, scores, classes))
            timings["tracking_seconds"] += time.perf_counter() - started
            long_side = 320
            ratio = long_side / max(height, width)
            small = cv2.resize(frame, (round(width * ratio), round(height * ratio)), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            small_boxes = boxes.astype(float) * ratio
            started = time.perf_counter()
            motion = motion_between(previous_gray, gray, small_boxes)
            timings["motion_seconds"] += time.perf_counter() - started
            previous_gray = gray
            camera.append(motion)
            timestamp = frame_index / fps
            for track in active:
                box = np.asarray(track[:4], dtype=float)
                class_id = int(track[6])
                if class_id not in QUERY_CLASSES:
                    continue
                x = ((box[0] + box[2]) / 2) / width
                y = ((box[1] + box[3]) / 2) / height
                bw, bh = (box[2] - box[0]) / width, (box[3] - box[1]) / height
                tracks[int(track[4])].append({
                    "step": float(step), "time": timestamp, "cx": x, "cy": y,
                    "area": max(1e-9, bw * bh), "height": max(1e-9, bh),
                    "bottom": box[3] / height, "conf": float(track[5]),
                })
            step += 1
            peak_gpu = max(peak_gpu, gpu_memory_mib())
            peak_rss = max(peak_rss, psutil.Process().memory_info().rss / (1024 ** 2))
    finally:
        capture.release()
    started = time.perf_counter()
    p0 = aggregate_p0(frames)
    p1_inc, p2_inc = aggregate_p1(tracks, camera)
    timings["aggregation_seconds"] = time.perf_counter() - started
    metadata = {
        "candidate_id": f"{row.source_dataset}|{row.session_id}|Q1|{int(row.unit_id)}",
        "physical_call_id": row.physical_call_id, "source_dataset": row.source_dataset,
        "session_id": row.session_id, "query_id": "Q1", "unit_id": int(row.unit_id),
        "window_start": float(row.start_time), "window_end": float(row.end_time),
    }
    runtime = {
        **metadata, **{key: float(value) for key, value in timings.items()},
        "wall_seconds": time.perf_counter() - started_all,
        "sampled_frames": len(frames), "video_seconds": float(row.end_time) - float(row.start_time),
        "peak_gpu_memory_mib": peak_gpu, "peak_cpu_memory_mib": peak_rss,
        "motion_valid_fraction": p2_inc["motion_valid_fraction"],
    }
    return {**metadata, **p0}, {**metadata, **p0, **p1_inc}, {**metadata, **p0, **p1_inc, **p2_inc}, runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    freeze = read_json(OUT / "contract_freeze.json")
    if sha256_file(ROOT / "docs/PSVR_P0_P1_P2_EXPERIMENT_CONTRACT.md") != freeze["contract_sha256"]:
        raise SystemExit("Contract changed after freeze")
    final = OUT / "features/p2.parquet"
    if final.exists() and not args.force and args.limit is None:
        print("Frozen features already exist; use --force to recompute")
        return
    sample = pd.read_csv(STAGE / "STAGE_A_FROZEN_SAMPLE.csv", keep_default_na=False)
    if args.limit:
        sample = sample.head(args.limit)
    frozen = load_frozen_proxy()
    detector = frozen.Y8Detector(ROOT / "models/yolo/yolov8n.pt")
    p0_rows, p1_rows, p2_rows, runtime_rows = [], [], [], []
    for number, row in enumerate(sample.itertuples(index=False), 1):
        p0, p1, p2, runtime = extract_one(row, detector, frozen)
        p0_rows.append(p0); p1_rows.append(p1); p2_rows.append(p2); runtime_rows.append(runtime)
        print(f"[{number:03d}/{len(sample):03d}] {row.physical_call_id} {runtime['wall_seconds']:.3f}s", flush=True)
    repeated = [runtime_rows[0]]
    first = next(sample.head(1).itertuples(index=False))
    for repeat in [2, 3]:
        _, _, _, runtime = extract_one(first, detector, frozen)
        runtime["repeat_index"] = repeat
        repeated.append(runtime)
    repeated[0]["repeat_index"] = 1
    feature_dir = OUT / "features"
    feature_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(p0_rows).to_parquet(feature_dir / "p0.parquet", index=False)
    pd.DataFrame(p1_rows).to_parquet(feature_dir / "p1.parquet", index=False)
    pd.DataFrame(p2_rows).to_parquet(feature_dir / "p2.parquet", index=False)
    pd.DataFrame(runtime_rows).to_csv(feature_dir / "runtime_samples.csv", index=False)
    pd.DataFrame(repeated).to_csv(feature_dir / "runtime_repeated_samples.csv", index=False)
    write_json(feature_dir / "extraction_complete.json", {
        "status": "COMPLETE", "created_at_utc": utc_now(), "candidate_count": len(sample),
        "new_oracle_calls": 0, "labels_read_during_extraction": 0,
        "p0_sha256": sha256_file(feature_dir / "p0.parquet"),
        "p1_sha256": sha256_file(feature_dir / "p1.parquet"),
        "p2_sha256": sha256_file(feature_dir / "p2.parquet"),
        "runtime_samples_sha256": sha256_file(feature_dir / "runtime_samples.csv"),
        "source_sample_sha256": sha256_file(STAGE / "STAGE_A_FROZEN_SAMPLE.csv"),
    })


if __name__ == "__main__":
    main()
