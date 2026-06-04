#!/usr/bin/env python3
"""
video_to_supg_csv.py

Convert a real video into per-frame SUPG-style CSV using two YOLO models:
  - cheap YOLO as proxy
  - stronger YOLO as pseudo-oracle

NOT for ARC reproduction. NOT for G-ARC guarantee. This is a preliminary
real-video validation input table for later experiments.

Usage:
    python video_to_supg_csv.py \
        --video /path/to/input.mp4 \
        --proxy-model /path/to/proxy.pt \
        --oracle-model /path/to/oracle.pt \
        --output-csv outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg.csv \
        --output-report outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_report.md
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert video to SUPG-style proxy/oracle CSV using YOLO models."
    )
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument("--proxy-model", required=True, help="Cheap YOLO model path (.pt)")
    parser.add_argument("--oracle-model", required=True, help="Stronger YOLO model path (.pt)")
    parser.add_argument("--output-csv", required=True, help="Output CSV path")
    parser.add_argument("--output-report", required=True, help="Output report path (.md)")
    parser.add_argument("--frame-stride", type=int, default=1, help="Process every N-th frame (default: 1)")
    parser.add_argument("--vehicle-classes", default="car,bus,truck,motorcycle",
                        help="Comma-separated vehicle class names (default: car,bus,truck,motorcycle)")
    parser.add_argument("--k-values", default="5,10,20",
                        help="Comma-separated K values for label_K columns (default: 5,10,20)")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (default: 0.25)")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size (default: 640)")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Max frames to process; 0 = no limit (default: 0)")
    parser.add_argument("--device", default="auto",
                        help="Device: 'auto', 'cpu', 'cuda', 'cuda:0', etc. (default: auto)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_device(device_str: str) -> str:
    """Resolve 'auto' to cuda if available, else cpu."""
    if device_str != "auto":
        return device_str
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def resolve_class_ids(model, vehicle_classes: list[str]) -> dict[str, int]:
    """Map requested vehicle class names to model class IDs.
    Returns {class_name: class_id}. Warns if a class is not found."""
    names = model.names  # {id: name}
    name_to_id = {v: k for k, v in names.items()}
    resolved = {}
    warnings = []
    for vc in vehicle_classes:
        vc_lower = vc.strip().lower()
        if vc_lower in name_to_id:
            resolved[vc_lower] = name_to_id[vc_lower]
        else:
            warnings.append(f"WARNING: vehicle class '{vc}' not found in model classes. Skipping.")
    return resolved, warnings


def count_vehicles(result, class_id_map: dict[str, int], conf_threshold: float) -> dict:
    """Count vehicle detections in a single YOLO result.
    Returns dict with count, conf_max, conf_mean, conf_sum."""
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return {"count": 0, "conf_max": 0.0, "conf_mean": 0.0, "conf_sum": 0.0}

    cls_ids = boxes.cls.cpu().numpy().astype(int)
    confs = boxes.conf.cpu().numpy()

    # Build mask for all requested vehicle class IDs
    target_ids = set(class_id_map.values())
    mask = np.isin(cls_ids, list(target_ids))

    # Also filter by confidence (YOLO already does this, but be explicit)
    mask = mask & (confs >= conf_threshold)
    matched_confs = confs[mask]

    if len(matched_confs) == 0:
        return {"count": 0, "conf_max": 0.0, "conf_mean": 0.0, "conf_sum": 0.0}

    return {
        "count": int(len(matched_confs)),
        "conf_max": float(np.max(matched_confs)),
        "conf_mean": float(np.mean(matched_confs)),
        "conf_sum": float(np.sum(matched_confs)),
    }


def compute_clip_statistics(
    oracle_labels: list[int],
    proxy_labels: list[int],
    tau: int,
    theta: float = 0.5,
) -> dict:
    """Compute clip-level statistics for a given tau (min clip length).

    A "true clip" is a maximal run of consecutive frames where label == 1
    and the run length >= tau.

    Returns:
        oracle_clip_count, proxy_clip_count, clip_recall, clip_precision, mIoU
    """
    def extract_clips(labels: list[int], min_len: int) -> list[tuple[int, int]]:
        """Extract (start, end) clips of consecutive 1s with length >= min_len."""
        clips = []
        start = None
        for i, v in enumerate(labels):
            if v == 1:
                if start is None:
                    start = i
            else:
                if start is not None:
                    length = i - start
                    if length >= min_len:
                        clips.append((start, i - 1))
                    start = None
        # Handle clip at end
        if start is not None:
            length = len(labels) - start
            if length >= min_len:
                clips.append((start, len(labels) - 1))
        return clips

    def clip_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
        """IoU between two clips defined by (start, end) inclusive."""
        inter_start = max(a[0], b[0])
        inter_end = min(a[1], b[1])
        inter = max(0, inter_end - inter_start + 1)
        union = (a[1] - a[0] + 1) + (b[1] - b[0] + 1) - inter
        return inter / union if union > 0 else 0.0

    oracle_clips = extract_clips(oracle_labels, tau)
    proxy_clips = extract_clips(proxy_labels, tau)

    # Match proxy clips to oracle clips via best IoU
    matched_oracle = set()
    matched_proxy = set()
    ious = []

    for pi, pc in enumerate(proxy_clips):
        best_iou = 0.0
        best_oi = -1
        for oi, oc in enumerate(oracle_clips):
            iou = clip_iou(pc, oc)
            if iou > best_iou:
                best_iou = iou
                best_oi = oi
        if best_iou >= theta and best_oi >= 0:
            matched_oracle.add(best_oi)
            matched_proxy.add(pi)
            ious.append(best_iou)

    oracle_count = len(oracle_clips)
    proxy_count = len(proxy_clips)
    recall = len(matched_oracle) / oracle_count if oracle_count > 0 else 0.0
    precision = len(matched_proxy) / proxy_count if proxy_count > 0 else 0.0
    miou = float(np.mean(ious)) if ious else 0.0

    return {
        "oracle_clip_count": oracle_count,
        "proxy_clip_count": proxy_count,
        "clip_recall": recall,
        "clip_precision": precision,
        "mIoU": miou,
    }


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # --- Resolve device ---
    device = resolve_device(args.device)
    print(f"[INFO] Using device: {device}")

    # --- Parse arguments ---
    vehicle_classes = [c.strip().lower() for c in args.vehicle_classes.split(",")]
    k_values = [int(k.strip()) for k in args.k_values.split(",")]
    frame_stride = max(1, args.frame_stride)
    conf_threshold = args.conf
    imgsz = args.imgsz
    max_frames = args.max_frames

    # --- Validate inputs ---
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"[ERROR] Video not found: {video_path}")
        sys.exit(1)

    proxy_path = Path(args.proxy_model)
    oracle_path = Path(args.oracle_model)
    if not proxy_path.exists():
        print(f"[ERROR] Proxy model not found: {proxy_path}")
        sys.exit(1)
    if not oracle_path.exists():
        print(f"[ERROR] Oracle model not found: {oracle_path}")
        sys.exit(1)

    # --- Ensure output directories exist ---
    csv_path = Path(args.output_csv)
    report_path = Path(args.output_report)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Load models ---
    print(f"[INFO] Loading proxy model: {proxy_path}")
    from ultralytics import YOLO
    proxy_model = YOLO(str(proxy_path))
    proxy_model.to(device)

    print(f"[INFO] Loading oracle model: {oracle_path}")
    oracle_model = YOLO(str(oracle_path))
    oracle_model.to(device)

    # --- Resolve class IDs ---
    proxy_class_map, proxy_warnings = resolve_class_ids(proxy_model, vehicle_classes)
    oracle_class_map, oracle_warnings = resolve_class_ids(oracle_model, vehicle_classes)
    all_warnings = proxy_warnings + oracle_warnings
    for w in all_warnings:
        print(f"  {w}")

    if not proxy_class_map and not oracle_class_map:
        print("[ERROR] No vehicle classes resolved in either model. Exiting.")
        sys.exit(1)

    print(f"[INFO] Proxy class map: {proxy_class_map}")
    print(f"[INFO] Oracle class map: {oracle_class_map}")

    # --- Open video ---
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = total_frames / fps if fps > 0 else 0.0

    print(f"[INFO] Video: {video_path}")
    print(f"[INFO] Resolution: {frame_width}x{frame_height}, FPS: {fps:.2f}, "
          f"Total frames: {total_frames}, Duration: {duration_sec:.1f}s")
    print(f"[INFO] Frame stride: {frame_stride}, Max frames: {max_frames or 'unlimited'}")

    # --- Process frames ---
    rows = []
    processed_idx = 0
    frame_idx = 0
    t_start = time.time()
    all_oracle_labels = {k: [] for k in k_values}
    all_proxy_labels = {k: [] for k in k_values}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply stride
        if frame_idx % frame_stride != 0:
            frame_idx += 1
            continue

        # Check max frames
        if max_frames > 0 and processed_idx >= max_frames:
            break

        timestamp_sec = frame_idx / fps if fps > 0 else 0.0

        # Run inference
        proxy_results = proxy_model(frame, conf=conf_threshold, imgsz=imgsz, verbose=False)
        oracle_results = oracle_model(frame, conf=conf_threshold, imgsz=imgsz, verbose=False)

        proxy_stats = count_vehicles(proxy_results[0], proxy_class_map, conf_threshold)
        oracle_stats = count_vehicles(oracle_results[0], oracle_class_map, conf_threshold)

        # Compute scores
        proxy_score = proxy_stats["count"] + 0.01 * proxy_stats["conf_sum"]
        oracle_score = oracle_stats["count"] + 0.01 * oracle_stats["conf_sum"]

        # Build row
        row = {
            "frame_idx": frame_idx,
            "processed_idx": processed_idx,
            "timestamp_sec": round(timestamp_sec, 4),
            "video_path": str(video_path),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "proxy_model": str(proxy_path.name),
            "oracle_model": str(oracle_path.name),
            "proxy_vehicle_count": proxy_stats["count"],
            "oracle_vehicle_count": oracle_stats["count"],
            "proxy_vehicle_conf_max": round(proxy_stats["conf_max"], 6),
            "proxy_vehicle_conf_mean": round(proxy_stats["conf_mean"], 6),
            "proxy_vehicle_conf_sum": round(proxy_stats["conf_sum"], 6),
            "oracle_vehicle_conf_max": round(oracle_stats["conf_max"], 6),
            "oracle_vehicle_conf_mean": round(oracle_stats["conf_mean"], 6),
            "oracle_vehicle_conf_sum": round(oracle_stats["conf_sum"], 6),
            "proxy_score": round(proxy_score, 6),
            "oracle_score": round(oracle_score, 6),
        }

        # K-based columns
        for K in k_values:
            proxy_pos = 1 if proxy_stats["count"] >= K else 0
            oracle_pos = 1 if oracle_stats["count"] >= K else 0
            row[f"proxy_positive_K{K}"] = proxy_pos
            row[f"oracle_positive_K{K}"] = oracle_pos
            all_proxy_labels[K].append(proxy_pos)
            all_oracle_labels[K].append(oracle_pos)

        # SUPG-compatible columns
        row["id"] = frame_idx
        row["proxy_score_supg"] = row["proxy_score"]
        for K in k_values:
            row[f"label_K{K}"] = row[f"oracle_positive_K{K}"]

        rows.append(row)
        processed_idx += 1
        frame_idx += 1

        # Progress logging
        if processed_idx % 100 == 0:
            elapsed = time.time() - t_start
            fps_actual = processed_idx / elapsed if elapsed > 0 else 0
            print(f"[PROGRESS] Processed {processed_idx} frames "
                  f"({elapsed:.1f}s, {fps_actual:.1f} frames/sec)")

    cap.release()
    t_end = time.time()
    runtime_sec = t_end - t_start

    print(f"[INFO] Done. Processed {processed_idx} frames in {runtime_sec:.1f}s")

    if processed_idx == 0:
        print("[WARNING] No frames processed. Check video file.")
        sys.exit(1)

    # --- Write CSV ---
    # Define column order
    base_cols = [
        "id", "frame_idx", "processed_idx", "timestamp_sec", "video_path",
        "frame_width", "frame_height", "proxy_model", "oracle_model",
        "proxy_vehicle_count", "oracle_vehicle_count",
        "proxy_vehicle_conf_max", "proxy_vehicle_conf_mean", "proxy_vehicle_conf_sum",
        "oracle_vehicle_conf_max", "oracle_vehicle_conf_mean", "oracle_vehicle_conf_sum",
        "proxy_score", "oracle_score", "proxy_score_supg",
    ]
    k_cols = []
    for K in k_values:
        k_cols.extend([f"proxy_positive_K{K}", f"oracle_positive_K{K}", f"label_K{K}"])
    all_cols = base_cols + k_cols

    df = pd.DataFrame(rows)
    # Ensure column order
    for col in all_cols:
        if col not in df.columns:
            df[col] = 0
    df = df[all_cols]
    df.to_csv(csv_path, index=False)
    print(f"[INFO] CSV written to: {csv_path}")

    # --- Compute statistics for report ---
    # K statistics
    k_stats = {}
    for K in k_values:
        oracle_labels = all_oracle_labels[K]
        proxy_labels = all_proxy_labels[K]
        oracle_pos_count = sum(oracle_labels)
        proxy_pos_count = sum(proxy_labels)
        oracle_pos_rate = oracle_pos_count / processed_idx if processed_idx > 0 else 0
        proxy_pos_rate = proxy_pos_count / processed_idx if processed_idx > 0 else 0

        # Agreement metrics
        tp = sum(1 for p, o in zip(proxy_labels, oracle_labels) if p == 1 and o == 1)
        fp = sum(1 for p, o in zip(proxy_labels, oracle_labels) if p == 1 and o == 0)
        fn = sum(1 for p, o in zip(proxy_labels, oracle_labels) if p == 0 and o == 1)
        tn = sum(1 for p, o in zip(proxy_labels, oracle_labels) if p == 0 and o == 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Clip statistics
        clips_tau20 = compute_clip_statistics(oracle_labels, proxy_labels, tau=20, theta=0.5)
        clips_tau30 = compute_clip_statistics(oracle_labels, proxy_labels, tau=30, theta=0.5)

        k_stats[K] = {
            "oracle_pos_count": oracle_pos_count,
            "proxy_pos_count": proxy_pos_count,
            "oracle_pos_rate": oracle_pos_rate,
            "proxy_pos_rate": proxy_pos_rate,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "clips_tau20": clips_tau20,
            "clips_tau30": clips_tau30,
        }

    # --- Write report ---
    report_lines = []
    report_lines.append("# Real Video SUPG-style CSV Report\n")
    report_lines.append("")
    report_lines.append("## 1. Purpose\n")
    report_lines.append("This pipeline converts a real video into per-frame proxy/oracle records.")
    report_lines.append("The **proxy** is a cheap YOLO model (YOLOv8n, 6.3 MB).")
    report_lines.append("The **oracle** is a stronger YOLO model (YOLOv8x, 131 MB) used as **pseudo-oracle**, "
                        "not human ground truth.")
    report_lines.append("")
    report_lines.append("This CSV is a preliminary real-video input table for later SUPG/ARC/G-ARC experiments.")
    report_lines.append("It is **not** an ARC reproduction and **not** a G-ARC guarantee.\n")

    report_lines.append("## 2. Data Provenance\n")
    report_lines.append(f"| Item | Value |")
    report_lines.append(f"|------|-------|")
    report_lines.append(f"| Video path | `{video_path}` |")
    report_lines.append(f"| Processed frames | {processed_idx} |")
    report_lines.append(f"| Frame stride | {frame_stride} |")
    report_lines.append(f"| FPS | {fps:.2f} |")
    report_lines.append(f"| Duration | {duration_sec:.1f}s |")
    report_lines.append(f"| Frame dimensions | {frame_width}x{frame_height} |")
    report_lines.append(f"| Proxy model | `{proxy_path}` |")
    report_lines.append(f"| Oracle model | `{oracle_path}` |")
    report_lines.append(f"| Vehicle classes | {vehicle_classes} |")
    report_lines.append(f"| Confidence threshold | {conf_threshold} |")
    report_lines.append(f"| Image size | {imgsz} |")
    report_lines.append(f"| Device | {device} |")
    report_lines.append(f"| Runtime | {runtime_sec:.1f}s |")
    report_lines.append(f"| Processing FPS | {processed_idx / runtime_sec:.1f} |")
    report_lines.append("")

    if all_warnings:
        report_lines.append("### Warnings\n")
        for w in all_warnings:
            report_lines.append(f"- {w}")
        report_lines.append("")

    report_lines.append("## 3. CSV Schema\n")
    report_lines.append("Each row is one processed frame. Key columns:\n")
    report_lines.append("| Column | Description |")
    report_lines.append("|--------|-------------|")
    report_lines.append("| `id` | Frame index (= `frame_idx`), used as SUPG row ID |")
    report_lines.append("| `frame_idx` | Original video frame index |")
    report_lines.append("| `processed_idx` | Sequential processed frame index |")
    report_lines.append("| `timestamp_sec` | Frame timestamp in seconds |")
    report_lines.append("| `proxy_vehicle_count` | Number of vehicle detections by proxy model |")
    report_lines.append("| `oracle_vehicle_count` | Number of vehicle detections by oracle model |")
    report_lines.append("| `proxy_score` | `proxy_vehicle_count + 0.01 * proxy_vehicle_conf_sum` |")
    report_lines.append("| `oracle_score` | `oracle_vehicle_count + 0.01 * oracle_vehicle_conf_sum` |")
    report_lines.append("| `proxy_score_supg` | Same as `proxy_score`, for SUPG compatibility |")
    report_lines.append("| `proxy_positive_K{K}` | 1 if `proxy_vehicle_count >= K`, else 0 |")
    report_lines.append("| `oracle_positive_K{K}` | 1 if `oracle_vehicle_count >= K`, else 0 |")
    report_lines.append("| `label_K{K}` | Same as `oracle_positive_K{K}`, used as pseudo-label |")
    report_lines.append("")

    report_lines.append("## 4. K Statistics\n")
    report_lines.append("| K | Oracle Pos Count | Oracle Pos Rate | Proxy Pos Count | Proxy Pos Rate |")
    report_lines.append("|---|-----------------|-----------------|-----------------|----------------|")
    for K in k_values:
        s = k_stats[K]
        report_lines.append(
            f"| {K} | {s['oracle_pos_count']} | {s['oracle_pos_rate']:.4f} | "
            f"{s['proxy_pos_count']} | {s['proxy_pos_rate']:.4f} |"
        )
    report_lines.append("")

    report_lines.append("## 5. Proxy/Oracle Agreement\n")
    report_lines.append("Frame-level agreement between proxy and oracle positive labels:\n")
    report_lines.append("| K | TP | FP | FN | TN | Precision | Recall | F1 |")
    report_lines.append("|---|----|----|----|----|-----------|--------|----|")
    for K in k_values:
        s = k_stats[K]
        report_lines.append(
            f"| {K} | {s['tp']} | {s['fp']} | {s['fn']} | {s['tn']} | "
            f"{s['precision']:.4f} | {s['recall']:.4f} | {s['f1']:.4f} |"
        )
    report_lines.append("")

    report_lines.append("## 6. Clip Statistics\n")
    report_lines.append("Clips are maximal runs of consecutive positive frames. "
                        "A clip requires length >= tau frames.\n")
    for tau_label, tau_key in [("tau=20", "clips_tau20"), ("tau=30", "clips_tau30")]:
        report_lines.append(f"### {tau_label}, IoU threshold theta=0.5\n")
        report_lines.append(
            "| K | Oracle Clips | Proxy Clips | Clip Recall | Clip Precision | mIoU |"
        )
        report_lines.append(
            "|---|-------------|-------------|-------------|----------------|------|"
        )
        for K in k_values:
            cs = k_stats[K][tau_key]
            report_lines.append(
                f"| {K} | {cs['oracle_clip_count']} | {cs['proxy_clip_count']} | "
                f"{cs['clip_recall']:.4f} | {cs['clip_precision']:.4f} | {cs['mIoU']:.4f} |"
            )
        report_lines.append("")

    report_lines.append("## 7. Limitations\n")
    report_lines.append("1. **Oracle is YOLO pseudo-oracle**, not human ground truth. "
                        "YOLOv8x is stronger than YOLOv8n but still a neural network with its own biases.")
    report_lines.append("2. **Architecture bias**: Both models are YOLOv8 — they share backbone architecture. "
                        "Proxy/oracle disagreements may underestimate true error rates.")
    report_lines.append("3. **No ARC reproduction**: This pipeline does not implement ARC or any adaptive "
                        "resource allocation algorithm.")
    report_lines.append("4. **No G-ARC guarantee**: This CSV is an input table. It does not demonstrate "
                        "G-ARC effectiveness.")
    report_lines.append("5. **COCO classes only**: Both models use COCO-pretrained weights (80 classes). "
                        "Non-COCO vehicle types will not be detected.")
    report_lines.append("6. **No tracking**: This is frame-level detection only. Clip statistics are "
                        "derived from consecutive frame thresholds, not multi-object tracking.")
    report_lines.append("7. **K values are arbitrary**: The choice of K (5, 10, 20) is for exploration. "
                        "Optimal K depends on the video scene and application.")
    report_lines.append("")

    report_text = "\n".join(report_lines)
    report_path.write_text(report_text, encoding="utf-8")
    print(f"[INFO] Report written to: {report_path}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Processed frames: {processed_idx}")
    print(f"  Runtime: {runtime_sec:.1f}s ({processed_idx / runtime_sec:.1f} fps)")
    print(f"  CSV: {csv_path}")
    print(f"  Report: {report_path}")
    for K in k_values:
        s = k_stats[K]
        print(f"  K={K}: oracle_pos={s['oracle_pos_count']} ({s['oracle_pos_rate']:.2%}), "
              f"proxy_pos={s['proxy_pos_count']} ({s['proxy_pos_rate']:.2%}), "
              f"F1={s['f1']:.3f}")


if __name__ == "__main__":
    main()
