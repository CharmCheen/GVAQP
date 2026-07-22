#!/usr/bin/env python3
"""
Export annotation tasks from H-PROXY1 detection/tracking results.

Generates:
  - annotations/tasks/detection/detection_tasks.json  (COCO format, 400 frames)
  - annotations/tasks/tracking/{clip_id}.csv           (MOT format, 6 clips)
  - annotations/tasks/SAMPLE_MANIFEST.csv              (all selected frames)
  - annotations/tasks/lane/lane_frame_candidates.csv   (100 lane frame candidates)

Usage:
  python scripts/export_proxy_annotation_tasks.py
"""

import sys, os, json, time, uuid
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"
ANNO_DIR = OUTPUT_DIR / "annotations"
RAW_DIR = OUTPUT_DIR / "raw"
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"

CLASS_MAP = {"car": 0, "truck": 1, "bus": 2, "motorcycle": 3, "bicycle": 4, "person": 5}
CLASS_NAMES = {0: "car", 1: "truck", 2: "bus", 3: "motorcycle", 4: "bicycle", 5: "person"}
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}


def iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return inter / (a1 + a2 - inter + 1e-6)


def merge_detections(det_dfs, iou_thresh=0.7):
    """Merge detections from multiple models with IoU deduplication."""
    all_dets = []
    for df in det_dfs:
        for _, row in df.iterrows():
            all_dets.append({
                "frame_index": row["frame_index"],
                "clip_id": row["clip_id"],
                "x1": row["x1"], "y1": row["y1"], "x2": row["x2"], "y2": row["y2"],
                "confidence": row.get("confidence", 0.5),
                "class_name": row.get("class_name", "car"),
            })

    df_all = pd.DataFrame(all_dets)
    
    # Deduplicate per frame
    merged = []
    for (fidx, cid), group in df_all.groupby(["frame_index", "clip_id"]):
        boxes = group[["x1", "y1", "x2", "y2"]].values
        confs = group["confidence"].values
        classes = group["class_name"].values
        kept = set()
        
        for i in range(len(boxes)):
            is_dup = False
            for j in kept:
                if iou(boxes[i], boxes[j]) > iou_thresh:
                    is_dup = True
                    break
            if not is_dup:
                kept.add(i)
        
        for i in kept:
            merged.append({
                "frame_index": fidx, "clip_id": cid,
                "x1": float(boxes[i][0]), "y1": float(boxes[i][1]),
                "x2": float(boxes[i][2]), "y2": float(boxes[i][3]),
                "confidence": float(confs[i]), "class_name": str(classes[i]),
            })
    
    df_merged = pd.DataFrame(merged)
    return df_merged.sample(frac=1, random_state=42).reset_index(drop=True)


def export_detection_tasks():
    """Export 400 detection frames in COCO format."""
    print("=== Exporting Detection Tasks ===")
    
    # Load all detection parquets
    det_files = list((OUTPUT_DIR / "raw/detections").glob("*.parquet"))
    det_dfs = [pd.read_parquet(f) for f in det_files]
    
    # Merge and deduplicate
    df_merged = merge_detections(det_dfs)
    
    # Load sample plan
    with open(PROJECT_ROOT / "outputs/yolop_target_sanity_v0/SAMPLE_PLAN.json") as f:
        plan = json.load(f)
    
    windows = plan["windows"]
    video_info = plan["video_info"]
    
    # Select 400 frames: evenly from 12 windows (~33 per window)
    frames_per_window = 400 // len(windows)
    selected_frames = []
    for w in windows:
        clip_indices = sorted(w["sample_indices"])
        n_sel = min(frames_per_window, len(clip_indices))
        step = max(1, len(clip_indices) // n_sel)
        picks = clip_indices[::step][:n_sel]
        for fidx in picks:
            selected_frames.append({
                "frame_index": fidx, "clip_id": w["clip_id"],
                "timestamp_sec": fidx / video_info["fps"] if video_info["fps"] > 0 else 0,
            })
    
    # Ensure exactly 400 (pad if needed)
    if len(selected_frames) < 400:
        remaining = [f for f in windows[0]["sample_indices"] 
                     if f not in [s["frame_index"] for s in selected_frames]][:400 - len(selected_frames)]
        for fidx in remaining:
            selected_frames.append({"frame_index": fidx, "clip_id": windows[0]["clip_id"],
                                     "timestamp_sec": fidx / video_info["fps"]})
    selected_frames = selected_frames[:400]
    
    # Build COCO JSON
    coco = {
        "info": {"description": "H-PROXY1 Detection Annotation Tasks", "version": "1.0",
                 "year": 2026, "date_created": time.strftime("%Y-%m-%d")},
        "images": [],
        "annotations": [],
        "categories": [{"id": i, "name": n, "supercategory": "vehicle" if n in VEHICLE_CLASSES else "person"}
                       for i, n in CLASS_NAMES.items()],
    }
    
    frame_id_map = {}
    selected_frame_set = {(s["frame_index"], s["clip_id"]) for s in selected_frames}
    
    for i, sf in enumerate(selected_frames):
        img_id = i + 1
        frame_id_map[(sf["frame_index"], sf["clip_id"])] = img_id
        coco["images"].append({
            "id": img_id,
            "file_name": f"frames/{sf['clip_id']}_f{sf['frame_index']:06d}.jpg",
            "width": 1920, "height": 1080,
            "clip_id": sf["clip_id"],
            "frame_index": sf["frame_index"],
            "timestamp_sec": sf["timestamp_sec"],
        })
    
    ann_id = 1
    for _, row in df_merged.iterrows():
        key = (row["frame_index"], row["clip_id"])
        if key not in frame_id_map:
            continue
        img_id = frame_id_map[key]
        w = row["x2"] - row["x1"]
        h = row["y2"] - row["y1"]
        
        class_id = CLASS_MAP.get(row["class_name"], 0)
        
        coco["annotations"].append({
            "id": ann_id,
            "image_id": img_id,
            "category_id": class_id,
            "bbox": [float(row["x1"]), float(row["y1"]), float(w), float(h)],
            "area": float(w * h),
            "iscrowd": 0,
            "confidence": float(row["confidence"]),
            "attributes": {
                "small_or_distant": False, "partially_occluded": False,
                "adjacent_lane": False, "near_ego_path": False,
                "interaction_relevant": False,
            },
            "review_status": "pre_annotation",
        })
        ann_id += 1
    
    tasks_dir = ANNO_DIR / "tasks/detection"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    with open(tasks_dir / "detection_tasks.json", "w") as f:
        json.dump(coco, f, indent=2)
    
    print(f"  Exported {len(coco['images'])} frames, {len(coco['annotations'])} pre-annotations")
    return selected_frames, coco


def export_tracking_tasks(selected_frames):
    """Export tracking tasks for 6 clips in MOT format."""
    print("\n=== Exporting Tracking Tasks ===")
    
    # Load tracking parquets
    track_files = list((OUTPUT_DIR / "raw/tracks").glob("*.parquet"))
    all_tracks = pd.concat([pd.read_parquet(f) for f in track_files], ignore_index=True)
    
    # Select 6 clips (first 6 from sample plan windows)
    with open(PROJECT_ROOT / "outputs/yolop_target_sanity_v0/SAMPLE_PLAN.json") as f:
        plan = json.load(f)
    
    tracking_clips = [w["clip_id"] for w in plan["windows"][:6]]
    
    tasks_dir = ANNO_DIR / "tasks/tracking"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    
    clip_summaries = []
    for clip_id in tracking_clips:
        clip_tracks = all_tracks[all_tracks["clip_id"] == clip_id].copy()
        if len(clip_tracks) == 0:
            print(f"  {clip_id}: no tracks found, skipping")
            continue
        
        # Re-index: (config_id, original_track_id) -> new contiguous ID
        # config_id prefixes track_id to make them unique across models
        unique_pairs = clip_tracks[["config_id", "track_id"]].drop_duplicates()
        pair_to_new = {}
        for new_id, (_, row) in enumerate(unique_pairs.iterrows()):
            pair_to_new[(row["config_id"], row["track_id"])] = new_id + 1
        
        rows = []
        for _, trk in clip_tracks.iterrows():
            new_id = pair_to_new[(trk["config_id"], trk["track_id"])]
            rows.append({
                "frame_index": int(trk["frame_index"]),
                "track_id": new_id,
                "x1": float(trk["x1"]), "y1": float(trk["y1"]),
                "x2": float(trk["x2"]), "y2": float(trk["y2"]),
                "class_id": 0,
                "confidence": 0.8,
                "visibility": 1.0,
                "track_state": "active",
                "annotator_flags": "pre_annotation",
            })
        
        df_out = pd.DataFrame(rows)
        df_out = df_out.sort_values(["frame_index", "track_id"])
        out_path = tasks_dir / f"gt_tracks_{clip_id}.csv"
        df_out.to_csv(out_path, index=False)
        
        clip_summaries.append({
            "clip_id": clip_id,
            "num_tracks": len(unique_pairs),
            "num_frames": df_out["frame_index"].nunique(),
            "total_boxes": len(df_out),
            "file": str(out_path.relative_to(ANNO_DIR)),
        })
        print(f"  {clip_id}: {len(unique_pairs)} tracks, {df_out['frame_index'].nunique()} frames, {len(df_out)} boxes")
    
    with open(tasks_dir / "tracking_clip_summary.json", "w") as f:
        json.dump(clip_summaries, f, indent=2)
    
    return clip_summaries


def export_sample_manifest(selected_frames, tracking_clips):
    """Export unified SAMPLE_MANIFEST.csv."""
    print("\n=== Exporting Sample Manifest ===")
    
    rows = []
    for sf in selected_frames:
        is_tracking = sf["clip_id"] in [tc["clip_id"] if isinstance(tc, dict) else tc for tc in tracking_clips]
        rows.append({
            "frame_index": sf["frame_index"],
            "clip_id": sf["clip_id"],
            "timestamp_sec": sf["timestamp_sec"],
            "task_type": "detection+tracking" if is_tracking else "detection",
            "lane_candidate": False,  # to be filled later
            "annotation_status": "pending",
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(ANNO_DIR / "SAMPLE_MANIFEST.csv", index=False)
    print(f"  Exported {len(df)} rows to SAMPLE_MANIFEST.csv")
    return df


def export_lane_candidates():
    """Generate lane annotation frame candidates."""
    print("\n=== Exporting Lane Candidates ===")
    
    with open(PROJECT_ROOT / "outputs/yolop_target_sanity_v0/SAMPLE_PLAN.json") as f:
        plan = json.load(f)
    
    windows = plan["windows"]
    
    # Select 100 frames across all windows
    candidates = []
    frames_per_window = 100 // len(windows) + 1
    
    for w in windows:
        indices = sorted(w["sample_indices"])
        n_sel = min(frames_per_window, len(indices))
        picks = indices[::max(1, len(indices) // n_sel)][:n_sel]
        for fidx in picks:
            candidates.append({
                "frame_index": fidx, "clip_id": w["clip_id"],
                "window_position": w["position"],
                "scene_type": "TO_BE_DETERMINED",
                "lane_visibility": "TO_BE_DETERMINED",
                "selected": False,
            })
    
    candidates = candidates[:100]
    
    tasks_dir = ANNO_DIR / "tasks/lane"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(candidates)
    df.to_csv(tasks_dir / "lane_frame_candidates.csv", index=False)
    print(f"  Exported {len(df)} lane frame candidates")
    
    # Create empty pre-annotation templates
    for _, row in df.iterrows():
        template = {
            "frame_index": int(row["frame_index"]),
            "clip_id": row["clip_id"],
            "image_width": 1920, "image_height": 1080,
            "left_boundary": {"type": "LineString", "coordinates": []},
            "right_boundary": {"type": "LineString", "coordinates": []},
            "lane_visibility": "TO_BE_DETERMINED",
            "scene_type": "TO_BE_DETERMINED",
            "annotator_notes": "",
            "pre_annotation_note": "No pre-annotation available. Draw boundaries from scratch.",
        }
        tmpl_path = tasks_dir / f"lane_tmpl_{int(row['frame_index']):06d}.json"
        with open(tmpl_path, "w") as f:
            json.dump(template, f, indent=2)
    
    return df


def extract_frames(video_path, selected_frames, output_dir):
    """Extract selected frames as JPEG images."""
    print("\n=== Extracting Frames ===")
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("  ERROR: Cannot open video")
        return
    
    unique_frames = {(sf["frame_index"], sf["clip_id"]): sf for sf in selected_frames}
    extracted = 0
    for (fidx, cid) in sorted(unique_frames.keys()):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
        ret, frame = cap.read()
        if not ret:
            continue
        fname = f"{cid}_f{fidx:06d}.jpg"
        cv2.imwrite(str(frames_dir / fname), frame)
        extracted += 1
    
    cap.release()
    print(f"  Extracted {extracted} frames to {frames_dir}")


def main():
    print("H-PROXY1 Annotation Task Exporter")
    print("=" * 60)
    
    # 1. Export detection tasks
    selected_frames, coco = export_detection_tasks()
    
    # 2. Export tracking tasks
    clip_summaries = export_tracking_tasks(selected_frames)
    tracking_clip_ids = [cs["clip_id"] if isinstance(cs, dict) else cs for cs in clip_summaries]
    
    # 3. Export sample manifest
    export_sample_manifest(selected_frames, tracking_clip_ids)
    
    # 4. Export lane candidates
    export_lane_candidates()
    
    # 5. Extract frames
    extract_frames(VIDEO_PATH, selected_frames, ANNO_DIR / "tasks")
    
    print("\n" + "=" * 60)
    print("Export complete. Deliverables:")
    print(f"  {ANNO_DIR}/tasks/detection/detection_tasks.json")
    print(f"  {ANNO_DIR}/tasks/tracking/")
    print(f"  {ANNO_DIR}/tasks/lane/")
    print(f"  {ANNO_DIR}/SAMPLE_MANIFEST.csv")
    print(f"  {ANNO_DIR}/tasks/frames/  ({len(selected_frames)} JPEG images)")


if __name__ == "__main__":
    main()
