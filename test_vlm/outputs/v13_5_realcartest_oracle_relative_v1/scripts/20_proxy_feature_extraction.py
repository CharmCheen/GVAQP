#!/usr/bin/env python3
"""Stage 2: Full-video cheap proxy feature extraction.

Computes motion_energy and YOLO-based features for every 5s coarse clip.
No VLM labels. No oracle labels. No event boundaries.
"""
import csv
import json
import os
import time
import sys

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4"
VIDEO_DURATION = 3987.104

os.makedirs(f"{ROOT}/tables", exist_ok=True)
os.makedirs(f"{ROOT}/logs", exist_ok=True)

# Load coarse clip grid
clips = []
with open(f"{ROOT}/tables/coarse_5s_clip_grid.csv") as f:
    for row in csv.DictReader(f):
        clips.append(row)
print(f"Loaded {len(clips)} clips from coarse_5s_clip_grid.csv")

# ── Motion Energy Computation ──
print("\n=== Computing motion energy ===")
import cv2
import numpy as np

cap = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {total_frames} frames, {video_fps:.2f} fps, {VIDEO_DURATION:.1f}s")

# Sample frames at 2fps, resize to 320x180 for motion computation
sample_interval = max(1, int(video_fps / 2))  # every 12 frames at 24fps = 2fps
print(f"Motion sampling: every {sample_interval} frames (~2fps), resize to 320x180")

frame_data = []  # (frame_idx, timestamp, gray_frame_small)
prev_gray = None

t0 = time.time()
frame_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    if frame_count % sample_interval == 0:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (320, 180))
        timestamp = frame_count / video_fps
        motion = 0.0
        if prev_gray is not None:
            diff = cv2.absdiff(gray_small, prev_gray)
            motion = float(np.mean(diff))
        frame_data.append({
            "frame_idx": frame_count,
            "timestamp": timestamp,
            "gray_small": gray_small,
            "motion_from_prev": motion,
        })
        prev_gray = gray_small
    frame_count += 1
    if frame_count % 5000 == 0:
        print(f"  Processed {frame_count}/{total_frames} frames ({frame_count/total_frames*100:.1f}%)")

cap.release()
motion_time = time.time() - t0
print(f"Motion extraction: {len(frame_data)} frames sampled, {motion_time:.1f}s")

# Aggregate motion per 5s clip
clip_motion = {}
for clip in clips:
    clip_start = float(clip["start_time"])
    clip_end = float(clip["end_time"])
    motions = []
    for fd in frame_data:
        if clip_start <= fd["timestamp"] < clip_end:
            motions.append(fd["motion_from_prev"])
    if motions:
        clip_motion[clip["clip_id"]] = {
            "motion_energy_mean": float(np.mean(motions)),
            "motion_energy_max": float(np.max(motions)),
            "motion_energy_std": float(np.std(motions)),
            "motion_frames_sampled": len(motions),
        }
    else:
        clip_motion[clip["clip_id"]] = {
            "motion_energy_mean": 0.0,
            "motion_energy_max": 0.0,
            "motion_energy_std": 0.0,
            "motion_frames_sampled": 0,
        }

# ── YOLO Inference ──
print("\n=== YOLO inference ===")
yolo_features = {}
yolo_status = "NOT_ATTEMPTED"

try:
    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB")

    from ultralytics import YOLO
    model_path = "/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt"
    if not os.path.exists(model_path):
        print(f"YOLO model not found: {model_path}")
        yolo_status = "MODEL_NOT_FOUND"
    else:
        model = YOLO(model_path)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"YOLO device: {device}")

        t0 = time.time()
        yolo_count = 0
        yolo_skip = 0
        yolo_fail = 0

        # Sample middle frame of each 5s clip for YOLO
        for clip in clips:
            mid_time = (float(clip["start_time"]) + float(clip["end_time"])) / 2.0
            mid_frame = int(mid_time * video_fps)
            cap2 = cv2.VideoCapture(VIDEO_PATH)
            cap2.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            ret, frame = cap2.read()
            cap2.release()

            if not ret:
                yolo_skip += 1
                yolo_features[clip["clip_id"]] = dict.fromkeys([
                    "vehicle_count_mean", "vehicle_count_max", "object_count_mean", "object_count_max",
                    "bbox_area_sum_mean", "bbox_area_sum_max", "max_bbox_area_mean",
                    "center_roi_vehicle_count_mean", "bottom_roi_vehicle_count_mean",
                ], 0.0)
                yolo_features[clip["clip_id"]]["yolo_status"] = "frame_read_failed"
                continue

            try:
                results = model(frame, device=device, verbose=False)
                r = results[0]
                boxes = r.boxes
                if boxes is not None and len(boxes) > 0:
                    cls_ids = boxes.cls.cpu().numpy()
                    xyxy = boxes.xyxy.cpu().numpy()
                    areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
                    frame_h, frame_w = frame.shape[:2]

                    # Vehicle classes for COCO: car=2, motorcycle=3, bus=5, truck=7
                    vehicle_mask = np.isin(cls_ids, [2, 3, 5, 7])
                    vehicle_count = int(vehicle_mask.sum())
                    object_count = len(cls_ids)
                    bbox_area_sum = float(areas.sum())
                    max_bbox_area = float(areas.max()) if len(areas) > 0 else 0.0

                    # Center ROI (middle third horizontally, middle third vertically)
                    cx = (xyxy[:, 0] + xyxy[:, 2]) / 2
                    cy = (xyxy[:, 3] + xyxy[:, 3]) / 2  # bottom of bbox
                    center_mask = (cx > frame_w/3) & (cx < 2*frame_w/3) & (cy > frame_h/3) & (cy < 2*frame_h/3)
                    center_vehicle = int((vehicle_mask & center_mask).sum())

                    # Bottom ROI (lower third)
                    bottom_mask = cy > 2*frame_h/3
                    bottom_vehicle = int((vehicle_mask & bottom_mask).sum())

                    yolo_features[clip["clip_id"]] = {
                        "vehicle_count_mean": float(vehicle_count),
                        "vehicle_count_max": float(vehicle_count),
                        "object_count_mean": float(object_count),
                        "object_count_max": float(object_count),
                        "bbox_area_sum_mean": bbox_area_sum,
                        "bbox_area_sum_max": bbox_area_sum,
                        "max_bbox_area_mean": max_bbox_area,
                        "center_roi_vehicle_count_mean": float(center_vehicle),
                        "bottom_roi_vehicle_count_mean": float(bottom_vehicle),
                        "yolo_status": "ok",
                    }
                else:
                    yolo_features[clip["clip_id"]] = dict.fromkeys([
                        "vehicle_count_mean", "vehicle_count_max", "object_count_mean", "object_count_max",
                        "bbox_area_sum_mean", "bbox_area_sum_max", "max_bbox_area_mean",
                        "center_roi_vehicle_count_mean", "bottom_roi_vehicle_count_mean",
                    ], 0.0)
                    yolo_features[clip["clip_id"]]["yolo_status"] = "no_detections"

                yolo_count += 1
                if yolo_count % 100 == 0:
                    elapsed = time.time() - t0
                    fps_infer = yolo_count / elapsed
                    print(f"  YOLO: {yolo_count}/{len(clips)} clips, {fps_infer:.1f} clips/s, {elapsed:.0f}s elapsed")

            except Exception as e:
                yolo_fail += 1
                yolo_features[clip["clip_id"]] = dict.fromkeys([
                    "vehicle_count_mean", "vehicle_count_max", "object_count_mean", "object_count_max",
                    "bbox_area_sum_mean", "bbox_area_sum_max", "max_bbox_area_mean",
                    "center_roi_vehicle_count_mean", "bottom_roi_vehicle_count_mean",
                ], 0.0)
                yolo_features[clip["clip_id"]]["yolo_status"] = f"error: {str(e)[:80]}"

        yolo_time = time.time() - t0
        yolo_status = f"COMPLETE_{yolo_count}_ok_{yolo_skip}_skip_{yolo_fail}_fail"
        print(f"YOLO complete: {yolo_count} ok, {yolo_skip} skip, {yolo_fail} fail, {yolo_time:.1f}s")

except ImportError as e:
    yolo_status = f"IMPORT_ERROR: {e}"
    print(f"YOLO not available: {e}")
except Exception as e:
    yolo_status = f"RUNTIME_ERROR: {e}"
    print(f"YOLO error: {e}")

# ── Merge and write proxy_features_5s.csv ──
print("\n=== Writing proxy_features_5s.csv ===")

fieldnames = [
    "clip_id", "video_id", "start_time", "end_time",
    "motion_energy_mean", "motion_energy_max", "motion_energy_std", "motion_frames_sampled",
    "vehicle_count_mean", "vehicle_count_max",
    "object_count_mean", "object_count_max",
    "bbox_area_sum_mean", "bbox_area_sum_max",
    "max_bbox_area_mean",
    "center_roi_vehicle_count_mean",
    "bottom_roi_vehicle_count_mean",
    "yolo_status",
]

with open(f"{ROOT}/tables/proxy_features_5s.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for clip in clips:
        cid = clip["clip_id"]
        row = {
            "clip_id": cid,
            "video_id": "realcartest",
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
        }
        # Motion features
        if cid in clip_motion:
            row.update(clip_motion[cid])
        else:
            row.update({k: 0.0 for k in ["motion_energy_mean", "motion_energy_max", "motion_energy_std", "motion_frames_sampled"]})
        # YOLO features
        if cid in yolo_features:
            row.update(yolo_features[cid])
        else:
            row.update(dict.fromkeys([
                "vehicle_count_mean", "vehicle_count_max", "object_count_mean", "object_count_max",
                "bbox_area_sum_mean", "bbox_area_sum_max", "max_bbox_area_mean",
                "center_roi_vehicle_count_mean", "bottom_roi_vehicle_count_mean",
            ], 0.0))
            row["yolo_status"] = "not_attempted"
        writer.writerow(row)

n_clips = len(clips)
print(f"Written {n_clips} rows to proxy_features_5s.csv")

# ── Summary ──
with open(f"{ROOT}/tables/proxy_features_5s.csv") as f:
    reader = csv.DictReader(f)
    motions = [float(r["motion_energy_mean"]) for r in reader]
print(f"\n=== PROXY FEATURE SUMMARY ===")
print(f"Clips: {n_clips}")
print(f"Motion energy: mean={np.mean(motions):.3f}, max={np.max(motions):.3f}, median={np.median(motions):.3f}")
print(f"YOLO status: {yolo_status}")

# Hard invariant check
print("\n=== HARD INVARIANT CHECK ===")
has_vlm = any("vlm" in f.lower() or "oracle" in f.lower() or "event_start" in f.lower() or "event_end" in f.lower() or "label" in f.lower() for f in fieldnames)
print(f"VLM/oracle/event fields in proxy table: {has_vlm}")
print(f"INVARIANT: {'PASS' if not has_vlm else 'FAIL - CONTAINS FORBIDDEN FIELDS'}")

# Save metadata
meta = {
    "video_path": VIDEO_PATH,
    "video_duration_s": VIDEO_DURATION,
    "n_clips": n_clips,
    "motion_fps": 2,
    "motion_scale": "320x180",
    "yolo_model": "/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt",
    "yolo_status": yolo_status,
    "yolo_frames_per_clip": 1,
    "yolo_frame_position": "midpoint",
    "fieldnames": fieldnames,
    "has_forbidden_fields": has_vlm,
}
with open(f"{ROOT}/tables/proxy_features_meta.json", "w") as f:
    json.dump(meta, f, indent=2)
