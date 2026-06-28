#!/usr/bin/env python3
"""Raw YOLOv8n bbox extraction at 2fps for dataset3."""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
VIDEO_PATH = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
YOLO_MODEL_PATH = ROOT / "models/yolo/yolov8n.pt"
OUT_DIR = ROOT / "garc_eval/outputs/dataset3_raw_bbox_materialization_v1"
TABLES = OUT_DIR / "tables"
LOGS = OUT_DIR / "logs"

COCO_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat",
    35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket",
    39: "bottle", 40: "wine glass", 41: "cup", 42: "fork", 43: "knife",
    44: "spoon", 45: "bowl", 46: "banana", 47: "apple", 48: "sandwich",
    49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
    54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant",
    59: "bed", 60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
    64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
    69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
    74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier",
    79: "toothbrush",
}


def log(msg, fh=None):
    line = "[" + time.strftime("%H:%M:%S") + "] " + str(msg)
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


def get_video_info(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("FAILED to open video: " + str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": fps,
        "nb_frames": nb_frames,
        "duration_s": nb_frames / max(fps, 1e-9),
    }
    cap.release()
    return info


def get_sampled_frame_indices(nb_frames, fps, sample_fps):
    """Deterministic 2fps sampling: frame_idx = round(t * fps) for t = 0.0, 0.5, 1.0, ..."""
    duration = nb_frames / fps
    n_samples = int(np.floor(duration * sample_fps)) + 1
    indices = []
    for i in range(n_samples):
        t = i / sample_fps
        idx = int(round(t * fps))
        if idx >= nb_frames:
            break
        indices.append(idx)
    return indices


def load_existing_frame_indices(path):
    if not path.exists():
        return set()
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path, columns=["frame_index"])
        else:
            df = pd.read_csv(path, usecols=["frame_index"])
        return set(df["frame_index"].unique().tolist())
    except Exception:
        return set()


def extract_raw_bbox(
    video_path,
    model_path,
    sample_fps=2.0,
    out_parquet=None,
    out_csv=None,
    out_frames_csv=None,
    limit_frames=None,
    limit_seconds=None,
    checkpoint_every=50,
    log_path=None,
):
    if out_parquet is None and out_csv is None:
        raise ValueError("Must provide at least one of out_parquet or out_csv")
    if out_parquet is not None:
        out_parquet = Path(out_parquet)
    if out_csv is not None:
        out_csv = Path(out_csv)
    if out_frames_csv is not None:
        out_frames_csv = Path(out_frames_csv)

    logfh = open(log_path, "a") if log_path else None
    try:
        log("=== extract_raw_bbox start ===", logfh)
        log("video: " + str(video_path), logfh)
        log("model: " + str(model_path), logfh)
        log("sample_fps: " + str(sample_fps), logfh)

        info = get_video_info(video_path)
        log("video info: w=" + str(info["width"]) + " h=" + str(info["height"]) +
            " fps=" + str(info["fps"]) + " nb_frames=" + str(info["nb_frames"]) +
            " duration=" + str(round(info["duration_s"], 2)) + "s", logfh)

        if limit_seconds is not None:
            limit_frames_eff = int(limit_seconds * info["fps"])
        else:
            limit_frames_eff = info["nb_frames"]

        all_sample_indices = get_sampled_frame_indices(limit_frames_eff, info["fps"], sample_fps)
        log("total sampled indices: " + str(len(all_sample_indices)), logfh)

        existing_indices = set()
        if out_parquet is not None and out_parquet.exists():
            existing_indices = load_existing_frame_indices(out_parquet)
        elif out_csv is not None and out_csv.exists():
            existing_indices = load_existing_frame_indices(out_csv)

        if existing_indices:
            log("resume: " + str(len(existing_indices)) + " already-processed frame indices", logfh)

        remaining_indices = [i for i in all_sample_indices if i not in existing_indices]
        log("frames to process: " + str(len(remaining_indices)), logfh)

        if limit_frames is not None:
            remaining_indices = remaining_indices[:limit_frames]
            log("smoke: limited to first " + str(len(remaining_indices)) + " frames", logfh)

        if len(remaining_indices) == 0:
            log("nothing to process", logfh)
            return {"processed": 0, "failed": 0, "total_detections": 0,
                    "elapsed_s": 0, "effective_fps": 0}

        from ultralytics import YOLO
        model = YOLO(str(model_path))
        log("YOLO model loaded", logfh)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError("cannot open video: " + str(video_path))

        detections_buffer = []
        frames_buffer = []
        processed = 0
        failed = 0
        total_detections = 0
        t_start = time.time()

        det_cols = [
            "video_id", "frame_index", "timestamp_sec", "sample_fps",
            "image_width", "image_height",
            "detection_id", "class_id", "class_name",
            "confidence", "x1", "y1", "x2", "y2",
            "cx", "cy", "bbox_width", "bbox_height", "bbox_area",
            "model_name", "model_weights", "source_video_path",
        ]
        frame_cols = [
            "video_id", "frame_index", "timestamp_sec", "sampled",
            "processed", "num_detections", "error_message",
        ]

        if out_csv is not None and not out_csv.exists():
            pd.DataFrame(columns=det_cols).to_csv(out_csv, index=False)
        if out_frames_csv is not None and not out_frames_csv.exists():
            pd.DataFrame(columns=frame_cols).to_csv(out_frames_csv, index=False)

        for idx_pos, frame_idx in enumerate(remaining_indices):
            ts_sec = frame_idx / info["fps"]
            processed_ok = True
            num_dets = 0
            err_msg = ""

            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    raise RuntimeError("cv2.read failed at frame " + str(frame_idx))

                results = model.predict(frame, verbose=False, device=0)
                boxes = results[0].boxes
                h, w = frame.shape[:2]
                if boxes is not None and len(boxes) > 0:
                    cls = boxes.cls.cpu().numpy().astype(int)
                    conf = boxes.conf.cpu().numpy().astype(float)
                    xyxy = boxes.xyxy.cpu().numpy().astype(float)
                    for di, (c, cf, box) in enumerate(zip(cls, conf, xyxy)):
                        x1, y1, x2, y2 = box
                        bbox_w = x2 - x1
                        bbox_h = y2 - y1
                        bbox_area = bbox_w * bbox_h
                        cx = (x1 + x2) / 2.0
                        cy = (y1 + y2) / 2.0
                        det = {
                            "video_id": "dataset3",
                            "frame_index": int(frame_idx),
                            "timestamp_sec": round(ts_sec, 6),
                            "sample_fps": float(sample_fps),
                            "image_width": int(w),
                            "image_height": int(h),
                            "detection_id": "d" + str(frame_idx).zfill(6) + "_" + str(di).zfill(3),
                            "class_id": int(c),
                            "class_name": COCO_NAMES.get(int(c), "cls_" + str(c)),
                            "confidence": float(cf),
                            "x1": float(x1), "y1": float(y1),
                            "x2": float(x2), "y2": float(y2),
                            "cx": float(cx), "cy": float(cy),
                            "bbox_width": float(bbox_w),
                            "bbox_height": float(bbox_h),
                            "bbox_area": float(bbox_area),
                            "model_name": "yolov8n",
                            "model_weights": str(model_path),
                            "source_video_path": str(video_path),
                        }
                        detections_buffer.append(det)
                        num_dets += 1
                        total_detections += 1
            except Exception as e:
                processed_ok = False
                failed += 1
                err_msg = type(e).__name__ + ": " + str(e)[:200]
                log("  FAILED frame " + str(frame_idx) + ": " + err_msg, logfh)

            frames_buffer.append({
                "video_id": "dataset3",
                "frame_index": int(frame_idx),
                "timestamp_sec": round(ts_sec, 6),
                "sampled": True,
                "processed": processed_ok,
                "num_detections": num_dets,
                "error_message": err_msg,
            })
            processed += 1

            if processed % checkpoint_every == 0:
                if detections_buffer:
                    new_df = pd.DataFrame(detections_buffer)
                    if out_csv is not None:
                        new_df.to_csv(out_csv, mode="a", header=False, index=False)
                    if out_parquet is not None:
                        if out_parquet.exists():
                            existing = pd.read_parquet(out_parquet)
                            combined = pd.concat([existing, new_df], ignore_index=True)
                        else:
                            combined = new_df
                        combined.to_parquet(out_parquet, index=False)
                    detections_buffer = []
                if frames_buffer and out_frames_csv is not None:
                    new_df = pd.DataFrame(frames_buffer)
                    new_df.to_csv(out_frames_csv, mode="a", header=False, index=False)
                    frames_buffer = []

                elapsed = time.time() - t_start
                effective_fps = processed / elapsed if elapsed > 0 else 0
                remaining = len(remaining_indices) - idx_pos - 1
                eta_sec = remaining / effective_fps if effective_fps > 0 else 0
                log("  checkpoint @ " + str(processed) + "/" + str(len(remaining_indices)) +
                    " elapsed=" + str(round(elapsed, 1)) + "s" +
                    " eff_fps=" + str(round(effective_fps, 2)) +
                    " eta=" + str(round(eta_sec, 0)) + "s" +
                    " total_dets=" + str(total_detections), logfh)

        if detections_buffer:
            new_df = pd.DataFrame(detections_buffer)
            if out_csv is not None:
                new_df.to_csv(out_csv, mode="a", header=False, index=False)
            if out_parquet is not None:
                if out_parquet.exists():
                    existing = pd.read_parquet(out_parquet)
                    combined = pd.concat([existing, new_df], ignore_index=True)
                else:
                    combined = new_df
                combined.to_parquet(out_parquet, index=False)
            detections_buffer = []
        if frames_buffer and out_frames_csv is not None:
            new_df = pd.DataFrame(frames_buffer)
            new_df.to_csv(out_frames_csv, mode="a", header=False, index=False)
            frames_buffer = []

        cap.release()

        elapsed = time.time() - t_start
        effective_fps = processed / elapsed if elapsed > 0 else 0
        log("=== extract done: processed=" + str(processed) +
            " failed=" + str(failed) +
            " total_detections=" + str(total_detections) +
            " elapsed=" + str(round(elapsed, 1)) + "s" +
            " eff_fps=" + str(round(effective_fps, 2)) + " ===", logfh)

        return {
            "processed": processed, "failed": failed,
            "total_detections": total_detections,
            "elapsed_s": elapsed, "effective_fps": effective_fps,
        }
    finally:
        if logfh is not None:
            logfh.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "full"], required=True)
    ap.add_argument("--limit-seconds", type=float, default=None)
    ap.add_argument("--limit-frames", type=int, default=None)
    ap.add_argument("--sample-fps", type=float, default=2.0)
    args = ap.parse_args()

    TABLES.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    out_csv = TABLES / "raw_yolo_detections_dataset3_2fps.csv"
    out_parquet = TABLES / "raw_yolo_detections_dataset3_2fps.parquet"
    out_frames_csv = TABLES / "yolo_sampled_frames_dataset3_2fps.csv"
    log_path = LOGS / "yolo_dataset3_2fps.log"

    extract_raw_bbox(
        video_path=VIDEO_PATH,
        model_path=YOLO_MODEL_PATH,
        sample_fps=args.sample_fps,
        out_parquet=out_parquet,
        out_csv=out_csv,
        out_frames_csv=out_frames_csv,
        limit_frames=args.limit_frames,
        limit_seconds=args.limit_seconds,
        checkpoint_every=50,
        log_path=log_path,
    )


if __name__ == "__main__":
    main()
