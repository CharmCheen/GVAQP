#!/usr/bin/env python3
"""Run YOLO inference on middle frame of each 5s clip and update proxy_features_5s.csv."""
import csv, os, time, numpy as np, cv2, torch
from ultralytics import YOLO

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4"

print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    # Use the correct attribute name
    mem_bytes = torch.cuda.get_device_properties(0).total_memory
    print(f"GPU: {torch.cuda.get_device_name(0)}, memory: {mem_bytes/1024**3:.1f} GB")

model_path = "/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt"
model = YOLO(model_path)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"YOLO device: {device}")

# Load clips
clips = []
with open(f"{ROOT}/tables/coarse_5s_clip_grid.csv") as f:
    for row in csv.DictReader(f):
        clips.append(row)
print(f"Loaded {len(clips)} clips")

# Load existing proxy features
proxy_rows = {}
with open(f"{ROOT}/tables/proxy_features_5s.csv") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        proxy_rows[row["clip_id"]] = row
print(f"Loaded {len(proxy_rows)} existing proxy rows")

cap = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap.get(cv2.CAP_PROP_FPS)
cap.release()

yolo_count = 0
yolo_skip = 0
yolo_fail = 0
t0 = time.time()

for clip in clips:
    mid_time = (float(clip["start_time"]) + float(clip["end_time"])) / 2.0
    mid_frame = int(mid_time * video_fps)

    cap2 = cv2.VideoCapture(VIDEO_PATH)
    cap2.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
    ret, frame = cap2.read()
    cap2.release()

    cid = clip["clip_id"]
    if not ret:
        yolo_skip += 1
        for k in ["vehicle_count_mean","vehicle_count_max","object_count_mean","object_count_max",
                   "bbox_area_sum_mean","bbox_area_sum_max","max_bbox_area_mean",
                   "center_roi_vehicle_count_mean","bottom_roi_vehicle_count_mean"]:
            proxy_rows[cid][k] = "0.0"
        proxy_rows[cid]["yolo_status"] = "frame_read_failed"
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

            vehicle_mask = np.isin(cls_ids, [2, 3, 5, 7])
            vehicle_count = int(vehicle_mask.sum())
            object_count = len(cls_ids)
            bbox_area_sum = float(areas.sum())
            max_bbox_area = float(areas.max()) if len(areas) > 0 else 0.0

            cx = (xyxy[:, 0] + xyxy[:, 2]) / 2
            cy = (xyxy[:, 1] + xyxy[:, 3]) / 2
            center_mask = (cx > frame_w/3) & (cx < 2*frame_w/3) & (cy > frame_h/3) & (cy < 2*frame_h/3)
            center_vehicle = int((vehicle_mask & center_mask).sum())
            bottom_mask = cy > 2*frame_h/3
            bottom_vehicle = int((vehicle_mask & bottom_mask).sum())

            proxy_rows[cid].update({
                "vehicle_count_mean": str(vehicle_count),
                "vehicle_count_max": str(vehicle_count),
                "object_count_mean": str(object_count),
                "object_count_max": str(object_count),
                "bbox_area_sum_mean": str(bbox_area_sum),
                "bbox_area_sum_max": str(bbox_area_sum),
                "max_bbox_area_mean": str(max_bbox_area),
                "center_roi_vehicle_count_mean": str(center_vehicle),
                "bottom_roi_vehicle_count_mean": str(bottom_vehicle),
                "yolo_status": "ok",
            })
        else:
            for k in ["vehicle_count_mean","vehicle_count_max","object_count_mean","object_count_max",
                       "bbox_area_sum_mean","bbox_area_sum_max","max_bbox_area_mean",
                       "center_roi_vehicle_count_mean","bottom_roi_vehicle_count_mean"]:
                proxy_rows[cid][k] = "0.0"
            proxy_rows[cid]["yolo_status"] = "no_detections"
        yolo_count += 1

    except Exception as e:
        yolo_fail += 1
        for k in ["vehicle_count_mean","vehicle_count_max","object_count_mean","object_count_max",
                   "bbox_area_sum_mean","bbox_area_sum_max","max_bbox_area_mean",
                   "center_roi_vehicle_count_mean","bottom_roi_vehicle_count_mean"]:
            proxy_rows[cid][k] = "0.0"
        proxy_rows[cid]["yolo_status"] = f"error: {str(e)[:80]}"

    if yolo_count % 100 == 0:
        elapsed = time.time() - t0
        print(f"  YOLO: {yolo_count}/{len(clips)}, {yolo_count/elapsed:.1f} clips/s, {elapsed:.0f}s")

yolo_time = time.time() - t0
print(f"YOLO done: {yolo_count} ok, {yolo_skip} skip, {yolo_fail} fail, {yolo_time:.1f}s")

# Write updated proxy features
if "yolo_status" not in fieldnames:
    fieldnames = list(fieldnames) + ["yolo_status"]

with open(f"{ROOT}/tables/proxy_features_5s.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for clip in clips:
        writer.writerow(proxy_rows[clip["clip_id"]])

# Summary
vehicles = [int(proxy_rows[c["clip_id"]]["vehicle_count_mean"]) for c in clips]
objects = [int(proxy_rows[c["clip_id"]]["object_count_mean"]) for c in clips]
print(f"\n=== YOLO SUMMARY ===")
print(f"Clips with vehicles >0: {sum(1 for v in vehicles if v > 0)}/{len(clips)}")
print(f"Mean vehicles/clip: {np.mean(vehicles):.2f}")
print(f"Mean objects/clip: {np.mean(objects):.2f}")
print(f"Max vehicles: {max(vehicles)}, Max objects: {max(objects)}")
print(f"GPU used: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
