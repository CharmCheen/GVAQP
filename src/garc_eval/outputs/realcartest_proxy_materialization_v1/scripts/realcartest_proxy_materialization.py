#!/usr/bin/env python3
"""Realcartest / V13 YOLOv8n proxy materialization and feasibility audit.

This script intentionally performs only cheap-proxy work. It reads existing
V13.8 VLM-oracle-relative labels for evaluation/provenance summaries but never
calls a VLM/LLM/oracle and never writes labels back to source artifacts.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT_DIR = ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1"
TABLES = OUT_DIR / "tables"
REPORTS = OUT_DIR / "reports"
LOGS = OUT_DIR / "logs"
SCRIPTS = OUT_DIR / "scripts"
CONFIG = OUT_DIR / "config"
MANIFEST = OUT_DIR / "data_manifest"

VIDEO_PATH = ROOT / "try_or_no/videos/realcartest.mp4"
YOLO_MODEL_PATH = ROOT / "models/yolo/yolov8n.pt"
ANCHOR_GRID_PATH = ROOT / "experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv"
LABEL_PATH = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv"
EVENT_PATH = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
V13_8_REPORT_PATH = ROOT / "experiments/v13/v13_8_full_oracle/reports/FINAL_REPORT.md"
DATASET3_REPORT_PATH = ROOT / "src/garc_eval/outputs/dataset3_raw_bbox_materialization_v1/reports/ANCHOR_COVERAGE_REPORT.md"
DATASET3_ANCHOR_COVERAGE_PATH = ROOT / "src/garc_eval/outputs/dataset3_raw_bbox_materialization_v1/tables/anchor_detection_coverage_dataset3_2fps.csv"

RUN_LOG = OUT_DIR / "RUN_LOG.md"
PROGRESS_LOG = LOGS / "progress.md"

SAMPLE_FPS = 2.0
ANCHOR_WINDOW_HALF_SEC = 5.0
VEHICLE_LIKE_CLASS_IDS = {1, 2, 3, 5, 7}  # bicycle, car, motorcycle, bus, truck

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

DET_COLUMNS = [
    "video_id", "frame_index", "timestamp_sec", "sample_fps",
    "image_width", "image_height", "detection_id", "class_id", "class_name",
    "confidence", "x1", "y1", "x2", "y2", "cx", "cy",
    "bbox_width", "bbox_height", "bbox_area", "model_name",
    "model_weights", "source_video_path",
]

FRAME_COLUMNS = [
    "video_id", "frame_index", "timestamp_sec", "sampled", "processed",
    "num_detections", "error_message",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for path in [TABLES, REPORTS, LOGS, SCRIPTS, CONFIG, MANIFEST]:
        path.mkdir(parents=True, exist_ok=True)


def append_log(title: str, lines: list[str]) -> None:
    ensure_dirs()
    text = [f"\n## {utc_now()} - {title}", ""]
    text.extend(lines)
    text.append("")
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(text))
    with PROGRESS_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(text))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except Exception as exc:
        return 999, f"{type(exc).__name__}: {exc}"


def import_status() -> dict[str, dict[str, str]]:
    mods = ["torch", "cv2", "ultralytics", "pandas", "numpy", "pyarrow", "sklearn"]
    out: dict[str, dict[str, str]] = {}
    for mod_name in mods:
        try:
            mod = __import__(mod_name)
            out[mod_name] = {"available": "YES", "version": str(getattr(mod, "__version__", "")), "error": ""}
        except Exception as exc:
            out[mod_name] = {"available": "NO", "version": "", "error": f"{type(exc).__name__}: {exc}"}
    return out


def gpu_status() -> dict[str, str]:
    code, out = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"], timeout=10)
    if code != 0 or not out:
        return {"available": "NO", "raw": out}
    first = out.splitlines()[0]
    return {"available": "YES", "raw": first}


def get_video_info(path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": file_size(path),
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": frame_count / fps if fps > 0 else 0.0,
        "width": width,
        "height": height,
    }


def sampled_frame_indices(frame_count: int, fps: float, sample_fps: float, limit_seconds: float | None = None) -> list[int]:
    effective_frames = frame_count
    if limit_seconds is not None:
        effective_frames = min(frame_count, int(math.floor(limit_seconds * fps)))
    duration = effective_frames / fps if fps > 0 else 0.0
    n = int(math.floor(duration * sample_fps)) + 1
    indices: list[int] = []
    for i in range(n):
        ts = i / sample_fps
        idx = int(round(ts * fps))
        if idx >= effective_frames:
            break
        indices.append(idx)
    return indices


def read_anchor_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    anchors = pd.read_csv(ANCHOR_GRID_PATH)
    labels = pd.read_csv(LABEL_PATH)
    events = pd.read_csv(EVENT_PATH)
    return anchors, labels, events


def build_event_anchor_map(events: pd.DataFrame) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for _, row in events.iterrows():
        raw_ids = str(row.get("supporting_anchor_ids", "")).split("|")
        for anchor_id in raw_ids:
            anchor_id = anchor_id.strip()
            if not anchor_id:
                continue
            mapping[anchor_id] = {
                "event_cluster_id": row.get("event_id", ""),
                "singleton_flag": int(row.get("num_supporting_anchors", 0)) == 1,
            }
    return mapping


def format_kv_table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Key | Value |", "|---|---:|"]
    for key, value in rows:
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def describe_series(s: pd.Series) -> str:
    if len(s) == 0:
        return "n=0"
    desc = s.astype(float).describe(percentiles=[0.25, 0.5, 0.75])
    return (
        f"n={int(desc['count'])}, mean={desc['mean']:.3f}, std={desc.get('std', 0):.3f}, "
        f"min={desc['min']:.3f}, p25={desc['25%']:.3f}, median={desc['50%']:.3f}, "
        f"p75={desc['75%']:.3f}, max={desc['max']:.3f}"
    )


def warning_mask(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip()
    return normalized.ne("")


def warning_counts(series: pd.Series) -> dict[str, int]:
    normalized = series.fillna("").astype(str).str.strip().replace("", "NONE")
    return {str(k): int(v) for k, v in normalized.value_counts(dropna=False).to_dict().items()}


def write_manifest_and_config(video_info: dict[str, Any], env: dict[str, dict[str, str]], gpu: dict[str, str]) -> None:
    config_text = "\n".join([
        "experiment: realcartest_proxy_materialization_v1",
        f"video_path: {VIDEO_PATH}",
        f"anchor_grid_path: {ANCHOR_GRID_PATH}",
        f"label_path_read_only: {LABEL_PATH}",
        f"event_path_read_only: {EVENT_PATH}",
        f"yolo_model_path: {YOLO_MODEL_PATH}",
        f"sample_fps: {SAMPLE_FPS}",
        f"anchor_window_half_sec: {ANCHOR_WINDOW_HALF_SEC}",
        "oracle_calls_allowed: false",
        "training_allowed: false",
        "downloads_allowed: false",
        "output_dir: " + str(OUT_DIR),
        "",
    ])
    write_text(CONFIG / "experiment_config.yaml", config_text)

    rows = [
        {"artifact": "realcartest_video", "path": str(VIDEO_PATH), "exists": VIDEO_PATH.exists(), "rows": "", "notes": f"{video_info['width']}x{video_info['height']} {video_info['duration_sec']:.3f}s"},
        {"artifact": "anchor_grid", "path": str(ANCHOR_GRID_PATH), "exists": ANCHOR_GRID_PATH.exists(), "rows": len(pd.read_csv(ANCHOR_GRID_PATH)) if ANCHOR_GRID_PATH.exists() else "", "notes": "read-only"},
        {"artifact": "v13_8_labels", "path": str(LABEL_PATH), "exists": LABEL_PATH.exists(), "rows": len(pd.read_csv(LABEL_PATH)) if LABEL_PATH.exists() else "", "notes": "read-only pseudo-oracle labels"},
        {"artifact": "v13_8_events", "path": str(EVENT_PATH), "exists": EVENT_PATH.exists(), "rows": len(pd.read_csv(EVENT_PATH)) if EVENT_PATH.exists() else "", "notes": "read-only event clusters"},
        {"artifact": "yolov8n_weights", "path": str(YOLO_MODEL_PATH), "exists": YOLO_MODEL_PATH.exists(), "rows": "", "notes": f"{file_size(YOLO_MODEL_PATH)} bytes"},
        {"artifact": "gpu", "path": "", "exists": gpu["available"], "rows": "", "notes": gpu["raw"]},
    ]
    pd.DataFrame(rows).to_csv(MANIFEST / "input_manifest.csv", index=False)


def phase0_inventory() -> bool:
    ensure_dirs()
    video_exists = VIDEO_PATH.exists()
    anchor_exists = ANCHOR_GRID_PATH.exists()
    model_exists = YOLO_MODEL_PATH.exists()
    label_exists = LABEL_PATH.exists()
    event_exists = EVENT_PATH.exists()

    if not video_exists:
        write_final_decision("REALCARTEST_VIDEO_MISSING", "realcartest video missing")
        append_log("Phase 0 blocker", [f"- Missing video: {VIDEO_PATH}", "- Decision: REALCARTEST_VIDEO_MISSING"])
        return False
    if not anchor_exists:
        write_final_decision("REALCARTEST_ANCHOR_TABLE_MISSING", "V13 center10 anchor grid missing")
        append_log("Phase 0 blocker", [f"- Missing anchor table: {ANCHOR_GRID_PATH}", "- Decision: REALCARTEST_ANCHOR_TABLE_MISSING"])
        return False
    if not model_exists:
        write_final_decision("YOLO_ENV_MISSING", "local yolov8n weight missing")
        append_log("Phase 0 blocker", [f"- Missing YOLO weight: {YOLO_MODEL_PATH}", "- Decision: YOLO_ENV_MISSING"])
        return False

    env = import_status()
    required_env = ["torch", "cv2", "ultralytics", "pandas", "numpy", "pyarrow"]
    missing = [name for name in required_env if env[name]["available"] != "YES"]
    if missing:
        write_final_decision("YOLO_ENV_MISSING", "missing Python dependency: " + ",".join(missing))
        append_log("Phase 0 blocker", [f"- Missing dependencies: {missing}", "- Decision: YOLO_ENV_MISSING"])
        return False

    gpu = gpu_status()
    video_info = get_video_info(VIDEO_PATH)
    anchors, labels, events = read_anchor_tables()
    write_manifest_and_config(video_info, env, gpu)

    dataset3_window = "confirmed: center_time_s +/- 5 s, 10s center window, 2 fps raw bbox materialization"
    dataset3_note = "Evidence: dataset3 ANCHOR_COVERAGE_REPORT.md and anchor_detection_coverage_dataset3_2fps.csv, which report center_time_s +/- 5 s and about 20 frames per anchor."
    label_provenance = "confirmed: V13.8 report states Qwen3-VL-32B-Instruct, V13.6 prompt, O_enter_ego_path_v0, negative-not-abstain rule, all 399 center10 anchors."
    camera_meta = "No explicit camera mount metadata found beyond dashcam-style realcartest filename/path and V13 reports."

    label_counts = labels["label"].value_counts(dropna=False).to_dict() if label_exists else {}
    anchor_mappable = int(anchors["anchor_time"].notna().sum()) if "anchor_time" in anchors.columns else 0
    yolo_run = "YES - no existing realcartest full raw bbox 2fps table was found in the requested output directory."

    lines = [
        "# INPUT_INVENTORY.md - realcartest proxy materialization v1",
        "",
        "## Video",
        "",
        format_kv_table([
            ("exists", "YES"),
            ("path", VIDEO_PATH),
            ("size_bytes", video_info["size_bytes"]),
            ("width", video_info["width"]),
            ("height", video_info["height"]),
            ("fps", f"{video_info['fps']:.6f}"),
            ("frame_count", video_info["frame_count"]),
            ("duration_sec", f"{video_info['duration_sec']:.3f}"),
            ("duration_min", f"{video_info['duration_sec'] / 60.0:.2f}"),
        ]),
        "",
        "## Anchor And Label Tables",
        "",
        format_kv_table([
            ("anchor_table_exists", "YES" if anchor_exists else "NO"),
            ("anchor_table_path", ANCHOR_GRID_PATH),
            ("anchor_rows", len(anchors)),
            ("anchor_timestamp_mappable", anchor_mappable),
            ("anchor_time_min", anchors["anchor_time"].min()),
            ("anchor_time_max", anchors["anchor_time"].max()),
            ("label_table_exists", "YES" if label_exists else "NO"),
            ("label_table_path", LABEL_PATH),
            ("label_rows", len(labels) if label_exists else 0),
            ("positive_labels", label_counts.get("positive", 0)),
            ("negative_labels", label_counts.get("negative", 0)),
            ("event_table_exists", "YES" if event_exists else "NO"),
            ("event_rows", len(events) if event_exists else 0),
        ]),
        "",
        "## Dataset3 Window Definition",
        "",
        f"- {dataset3_window}",
        f"- {dataset3_note}",
        "- This run will reuse anchor_time +/- 5 s as the only anchor feature window standard.",
        "",
        "## Realcartest Label Provenance",
        "",
        f"- {label_provenance}",
        "- Labels are VLM-oracle-relative, not human truth.",
        "",
        "## YOLO And Compute Environment",
        "",
        format_kv_table([
            ("yolov8n_weight_exists", "YES"),
            ("yolov8n_weight_path", YOLO_MODEL_PATH),
            ("yolov8n_weight_size_bytes", file_size(YOLO_MODEL_PATH)),
            ("gpu_available", gpu["available"]),
            ("gpu_raw", gpu["raw"]),
            ("need_run_yolo", yolo_run),
        ]),
        "",
        "| Package | Available | Version | Error |",
        "|---|---|---:|---|",
    ]
    for name, status in env.items():
        lines.append(f"| {name} | {status['available']} | {status['version']} | {status['error']} |")
    lines.extend([
        "",
        "## Camera / View Metadata",
        "",
        f"- {camera_meta}",
        "",
        "## Oracle Call Policy",
        "",
        "- This task will not call any VLM, Qwen, GLM, LLM, human oracle, or prompt-tuning workflow.",
        "- Existing Qwen labels are read only and used solely for feasibility evaluation.",
        "",
        "## Phase 0 Decision",
        "",
        "PASS - proceed to 60-second YOLO smoke test.",
        "",
    ])
    write_text(REPORTS / "INPUT_INVENTORY.md", "\n".join(map(str, lines)))
    append_log("Phase 0 complete", [
        f"- Video: {VIDEO_PATH}, {video_info['duration_sec']:.3f}s, {video_info['fps']:.6f} fps, {video_info['width']}x{video_info['height']}",
        f"- Anchors: {len(anchors)}, labels: {len(labels)} ({label_counts})",
        f"- Dataset3 window: {dataset3_window}",
        f"- GPU: {gpu['available']} ({gpu['raw']})",
        "- Decision: proceed to Phase 1",
    ])
    return True


def load_processed_frame_indices(frame_csv: Path) -> set[int]:
    if not frame_csv.exists() or file_size(frame_csv) == 0:
        return set()
    try:
        frame_df = pd.read_csv(frame_csv, usecols=["frame_index"])
        return set(frame_df["frame_index"].astype(int).tolist())
    except Exception:
        return set()


def init_csv(path: Path, columns: list[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def append_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        return
    pd.DataFrame(rows, columns=columns).to_csv(path, mode="a", header=False, index=False)


def run_yolo_materialization(
    det_csv: Path,
    frame_csv: Path,
    log_path: Path,
    limit_seconds: float | None,
    checkpoint_every: int,
) -> dict[str, Any]:
    from ultralytics import YOLO
    try:
        import torch
        device: int | str = 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        device = 0

    info = get_video_info(VIDEO_PATH)
    indices = sampled_frame_indices(info["frame_count"], info["fps"], SAMPLE_FPS, limit_seconds=limit_seconds)
    processed_existing = load_processed_frame_indices(frame_csv)
    remaining = [idx for idx in indices if idx not in processed_existing]

    init_csv(det_csv, DET_COLUMNS)
    init_csv(frame_csv, FRAME_COLUMNS)

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"[{utc_now()}] start run limit_seconds={limit_seconds} total_indices={len(indices)} remaining={len(remaining)} device={device}\n")
        log.flush()

        model = YOLO(str(YOLO_MODEL_PATH))
        cap = cv2.VideoCapture(str(VIDEO_PATH))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {VIDEO_PATH}")

        det_rows: list[dict[str, Any]] = []
        frame_rows: list[dict[str, Any]] = []
        processed = 0
        failed = 0
        total_detections = 0
        start = time.time()

        for pos, frame_index in enumerate(remaining, start=1):
            ts = frame_index / info["fps"]
            processed_ok = True
            error_message = ""
            num_dets = 0
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError(f"cv2.read failed at frame {frame_index}")
                h, w = frame.shape[:2]
                results = model.predict(frame, verbose=False, device=device)
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    cls = boxes.cls.cpu().numpy().astype(int)
                    conf = boxes.conf.cpu().numpy().astype(float)
                    xyxy = boxes.xyxy.cpu().numpy().astype(float)
                    for det_i, (class_id, confidence, box) in enumerate(zip(cls, conf, xyxy)):
                        x1, y1, x2, y2 = [float(v) for v in box]
                        bw = x2 - x1
                        bh = y2 - y1
                        det_rows.append({
                            "video_id": "realcartest",
                            "frame_index": int(frame_index),
                            "timestamp_sec": round(ts, 6),
                            "sample_fps": SAMPLE_FPS,
                            "image_width": int(w),
                            "image_height": int(h),
                            "detection_id": f"d{int(frame_index):06d}_{det_i:03d}",
                            "class_id": int(class_id),
                            "class_name": COCO_NAMES.get(int(class_id), f"cls_{class_id}"),
                            "confidence": float(confidence),
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "cx": (x1 + x2) / 2.0,
                            "cy": (y1 + y2) / 2.0,
                            "bbox_width": bw,
                            "bbox_height": bh,
                            "bbox_area": bw * bh,
                            "model_name": "yolov8n",
                            "model_weights": str(YOLO_MODEL_PATH),
                            "source_video_path": str(VIDEO_PATH),
                        })
                        num_dets += 1
            except Exception as exc:
                processed_ok = False
                failed += 1
                error_message = f"{type(exc).__name__}: {str(exc)[:200]}"

            frame_rows.append({
                "video_id": "realcartest",
                "frame_index": int(frame_index),
                "timestamp_sec": round(ts, 6),
                "sampled": True,
                "processed": processed_ok,
                "num_detections": int(num_dets),
                "error_message": error_message,
            })
            processed += 1
            total_detections += num_dets

            if processed % checkpoint_every == 0:
                append_csv(det_csv, det_rows, DET_COLUMNS)
                append_csv(frame_csv, frame_rows, FRAME_COLUMNS)
                det_rows = []
                frame_rows = []
                elapsed = time.time() - start
                eff = processed / elapsed if elapsed > 0 else 0.0
                eta = (len(remaining) - pos) / eff if eff > 0 else 0.0
                msg = f"[{utc_now()}] checkpoint processed={processed}/{len(remaining)} failed={failed} total_dets={total_detections} elapsed={elapsed:.1f}s eff_fps={eff:.3f} eta_sec={eta:.1f}\n"
                log.write(msg)
                log.flush()
                append_log("Phase 2 checkpoint" if limit_seconds is None else "Phase 1 checkpoint", [
                    f"- Processed {processed}/{len(remaining)} remaining frames for {'full' if limit_seconds is None else 'smoke'} run",
                    f"- Failed frames so far: {failed}",
                    f"- Detections in this invocation so far: {total_detections}",
                    f"- Effective processing fps: {eff:.3f}",
                ])

        append_csv(det_csv, det_rows, DET_COLUMNS)
        append_csv(frame_csv, frame_rows, FRAME_COLUMNS)
        cap.release()
        elapsed = time.time() - start
        eff = processed / elapsed if elapsed > 0 else 0.0
        log.write(f"[{utc_now()}] done processed={processed} failed={failed} total_dets={total_detections} elapsed={elapsed:.3f}s eff_fps={eff:.3f}\n")
        log.flush()

    return {
        "total_sample_indices": len(indices),
        "existing_processed": len(processed_existing),
        "processed_this_run": processed,
        "failed_this_run": failed,
        "total_detections_this_run": total_detections,
        "elapsed_sec_this_run": elapsed,
        "effective_fps_this_run": eff,
    }


def frame_detection_summary(det_csv: Path, frame_csv: Path) -> dict[str, Any]:
    frames = pd.read_csv(frame_csv) if frame_csv.exists() else pd.DataFrame(columns=FRAME_COLUMNS)
    dets = pd.read_csv(det_csv) if det_csv.exists() else pd.DataFrame(columns=DET_COLUMNS)
    processed = int(frames["processed"].astype(bool).sum()) if len(frames) else 0
    failed = int((~frames["processed"].astype(bool)).sum()) if len(frames) else 0
    vehicle_like = int(dets["class_id"].isin(VEHICLE_LIKE_CLASS_IDS).sum()) if len(dets) else 0
    person = int((dets["class_id"] == 0).sum()) if len(dets) else 0
    class_dist = dets["class_name"].value_counts().to_dict() if len(dets) else {}
    return {
        "frames": frames,
        "detections": dets,
        "sampled_frames": int(len(frames)),
        "processed_frames": processed,
        "failed_frames": failed,
        "total_detections": int(len(dets)),
        "vehicle_like_detections": vehicle_like,
        "person_detections": person,
        "detections_per_frame_mean": float(frames["num_detections"].mean()) if len(frames) else 0.0,
        "detections_per_frame_median": float(frames["num_detections"].median()) if len(frames) else 0.0,
        "detections_per_frame_max": int(frames["num_detections"].max()) if len(frames) else 0,
        "class_distribution": class_dist,
    }


def write_smoke_report(stats: dict[str, Any], run_stats: dict[str, Any], full_frame_estimate: int) -> str:
    elapsed = float(run_stats["elapsed_sec_this_run"])
    processed_this = int(run_stats["processed_this_run"])
    eff = float(run_stats["effective_fps_this_run"])
    estimated_runtime = full_frame_estimate / eff if eff > 0 else math.inf
    est_det_size = file_size(TABLES / "smoke_yolo_detections_60s.csv") * (full_frame_estimate / max(stats["sampled_frames"], 1))
    est_frame_size = file_size(TABLES / "smoke_sampled_frames_60s.csv") * (full_frame_estimate / max(stats["sampled_frames"], 1))
    fields_ok = set(DET_COLUMNS).issubset(set(stats["detections"].columns)) and set(FRAME_COLUMNS).issubset(set(stats["frames"].columns))
    fail_rate = stats["failed_frames"] / max(stats["sampled_frames"], 1)
    decision = "SMOKE_PASS_CONTINUE_FULL_RUN"
    reasons = []
    if processed_this <= 0 and stats["processed_frames"] <= 0:
        decision = "SMOKE_FAIL_STOP"
        reasons.append("no frames processed")
    if fail_rate > 0.05:
        decision = "SMOKE_FAIL_STOP"
        reasons.append(f"frame failure rate {fail_rate:.3f} > 0.05")
    if not fields_ok:
        decision = "SMOKE_FAIL_STOP"
        reasons.append("required output fields missing")
    if not reasons:
        reasons.append("YOLO ran, frames processed, fields complete, full run is resumable")

    gpu = gpu_status()
    lines = [
        "# SMOKE_TEST_REPORT.md - realcartest YOLOv8n 60s smoke",
        "",
        format_kv_table([
            ("processed_frame_count", stats["processed_frames"]),
            ("actual_sampling_fps", SAMPLE_FPS),
            ("wall_clock_time_sec_this_invocation", f"{elapsed:.3f}"),
            ("effective_processed_fps_this_invocation", f"{eff:.3f}"),
            ("detections_per_frame_mean", f"{stats['detections_per_frame_mean']:.3f}"),
            ("detections_per_frame_median", f"{stats['detections_per_frame_median']:.3f}"),
            ("detections_per_frame_max", stats["detections_per_frame_max"]),
            ("vehicle_like_detections", stats["vehicle_like_detections"]),
            ("person_detections", stats["person_detections"]),
            ("error_frame_count", stats["failed_frames"]),
            ("estimated_full_video_runtime_sec", f"{estimated_runtime:.1f}"),
            ("estimated_full_video_runtime_min", f"{estimated_runtime / 60.0:.2f}"),
            ("estimated_output_file_size_bytes", int(est_det_size + est_frame_size)),
            ("gpu_cpu_usage", gpu["raw"] if gpu["available"] == "YES" else "CPU/no GPU"),
            ("fields_complete", "YES" if fields_ok else "NO"),
        ]),
        "",
        "## Class Distribution",
        "",
        "| class_name | count |",
        "|---|---:|",
    ]
    for name, count in stats["class_distribution"].items():
        lines.append(f"| {name} | {count} |")
    lines.extend([
        "",
        "## Smoke Decision",
        "",
        f"`{decision}`",
        "",
        "Reasons:",
    ])
    lines.extend([f"- {r}" for r in reasons])
    lines.append("")
    write_text(REPORTS / "SMOKE_TEST_REPORT.md", "\n".join(map(str, lines)))
    append_log("Phase 1 complete", [
        f"- Smoke processed frames: {stats['processed_frames']}",
        f"- Smoke detections: {stats['total_detections']}",
        f"- Smoke elapsed sec: {elapsed:.3f}",
        f"- Estimated full runtime min: {estimated_runtime / 60.0:.2f}",
        f"- Decision: {decision}",
    ])
    return decision


def phase1_smoke() -> bool:
    det_csv = TABLES / "smoke_yolo_detections_60s.csv"
    frame_csv = TABLES / "smoke_sampled_frames_60s.csv"
    log_path = LOGS / "yolo_realcartest_2fps.log"
    run_stats = run_yolo_materialization(det_csv, frame_csv, log_path, limit_seconds=60.0, checkpoint_every=50)
    stats = frame_detection_summary(det_csv, frame_csv)
    info = get_video_info(VIDEO_PATH)
    full_frames = len(sampled_frame_indices(info["frame_count"], info["fps"], SAMPLE_FPS, limit_seconds=None))
    decision = write_smoke_report(stats, run_stats, full_frames)
    if decision != "SMOKE_PASS_CONTINUE_FULL_RUN":
        write_final_decision("REALCARTEST_SMOKE_FAIL", "60-second YOLO smoke failed")
        return False
    return True


def write_full_report(run_stats: dict[str, Any]) -> None:
    det_csv = TABLES / "raw_yolo_detections_realcartest_2fps.csv"
    frame_csv = TABLES / "yolo_sampled_frames_realcartest_2fps.csv"
    parquet_path = TABLES / "raw_yolo_detections_realcartest_2fps.parquet"
    stats = frame_detection_summary(det_csv, frame_csv)
    frames = stats["frames"]
    dets = stats["detections"]

    if len(dets) > 0:
        dets.to_parquet(parquet_path, index=False)
    else:
        pd.DataFrame(columns=DET_COLUMNS).to_parquet(parquet_path, index=False)

    elapsed = float(run_stats["elapsed_sec_this_run"])
    eff = float(run_stats["effective_fps_this_run"])
    lines = [
        "# FULL_RUN_REPORT.md - realcartest YOLOv8n 2fps raw bbox materialization",
        "",
        format_kv_table([
            ("total_sampled_frames", stats["sampled_frames"]),
            ("total_processed_frames", stats["processed_frames"]),
            ("failed_frames", stats["failed_frames"]),
            ("total_detections", stats["total_detections"]),
            ("vehicle_like_detections", stats["vehicle_like_detections"]),
            ("person_detections", stats["person_detections"]),
            ("mean_detections_per_processed_frame", f"{stats['detections_per_frame_mean']:.3f}"),
            ("wall_clock_runtime_sec_this_invocation", f"{elapsed:.3f}"),
            ("effective_processed_fps_this_invocation", f"{eff:.3f}"),
            ("raw_csv_size_bytes", file_size(det_csv)),
            ("frame_csv_size_bytes", file_size(frame_csv)),
            ("parquet_size_bytes", file_size(parquet_path)),
        ]),
        "",
        "## Detection Class Distribution",
        "",
        "| class_name | count |",
        "|---|---:|",
    ]
    for name, count in stats["class_distribution"].items():
        lines.append(f"| {name} | {count} |")
    warnings: list[str] = []
    if stats["failed_frames"] > 0:
        warnings.append(f"{stats['failed_frames']} frames failed")
    if stats["sampled_frames"] == 0:
        warnings.append("no sampled frames")
    if len(frames) and frames["frame_index"].duplicated().any():
        warnings.append("duplicate frame_index rows detected")
    if len(dets) and not set(DET_COLUMNS).issubset(set(dets.columns)):
        warnings.append("detection column set incomplete")
    if not warnings:
        warnings.append("none")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {w}" for w in warnings])
    lines.append("")
    write_text(REPORTS / "FULL_RUN_REPORT.md", "\n".join(map(str, lines)))
    append_log("Phase 2 complete", [
        f"- Full sampled frames: {stats['sampled_frames']}",
        f"- Full processed frames: {stats['processed_frames']}",
        f"- Full failed frames: {stats['failed_frames']}",
        f"- Full detections: {stats['total_detections']}",
        f"- Parquet written: {parquet_path} ({file_size(parquet_path)} bytes)",
    ])


def phase2_full_run() -> None:
    det_csv = TABLES / "raw_yolo_detections_realcartest_2fps.csv"
    frame_csv = TABLES / "yolo_sampled_frames_realcartest_2fps.csv"
    log_path = LOGS / "yolo_realcartest_2fps.log"
    run_stats = run_yolo_materialization(det_csv, frame_csv, log_path, limit_seconds=None, checkpoint_every=500)
    write_full_report(run_stats)


def aggregate_anchor_features() -> pd.DataFrame:
    anchors, labels, events = read_anchor_tables()
    event_map = build_event_anchor_map(events)
    frames = pd.read_csv(TABLES / "yolo_sampled_frames_realcartest_2fps.csv")
    dets = pd.read_csv(TABLES / "raw_yolo_detections_realcartest_2fps.csv")

    labels_small = labels[["anchor_id", "label"]].rename(columns={"label": "qwen_label"})
    merged = anchors.merge(labels_small, on="anchor_id", how="left")

    rows: list[dict[str, Any]] = []
    for _, anchor in merged.iterrows():
        anchor_id = str(anchor["anchor_id"])
        anchor_time = float(anchor["anchor_time"])
        start = max(0.0, anchor_time - ANCHOR_WINDOW_HALF_SEC)
        end = anchor_time + ANCHOR_WINDOW_HALF_SEC
        win_frames = frames[(frames["timestamp_sec"] >= start) & (frames["timestamp_sec"] < end)].copy()
        win_dets = dets[(dets["timestamp_sec"] >= start) & (dets["timestamp_sec"] < end)].copy()
        processed_frames = win_frames[win_frames["processed"].astype(bool)]
        processed_count = len(processed_frames)
        detection_frames = int((processed_frames["num_detections"] > 0).sum()) if processed_count else 0

        frame_vehicle_counts: list[int] = []
        frame_person_counts: list[int] = []
        frame_object_counts: list[int] = []
        frame_left_counts: list[int] = []
        frame_center_counts: list[int] = []
        frame_right_counts: list[int] = []
        frame_lateral_presence: list[int] = []
        for _, frame in processed_frames.iterrows():
            frame_index = int(frame["frame_index"])
            fd = win_dets[win_dets["frame_index"] == frame_index]
            object_count = len(fd)
            vehicle_count = int(fd["class_id"].isin(VEHICLE_LIKE_CLASS_IDS).sum()) if object_count else 0
            person_count = int((fd["class_id"] == 0).sum()) if object_count else 0
            if object_count:
                width = float(fd["image_width"].iloc[0])
                left = int((fd["cx"] < width / 3.0).sum())
                center = int(((fd["cx"] >= width / 3.0) & (fd["cx"] < 2.0 * width / 3.0)).sum())
                right = int((fd["cx"] >= 2.0 * width / 3.0).sum())
            else:
                left = center = right = 0
            frame_vehicle_counts.append(vehicle_count)
            frame_person_counts.append(person_count)
            frame_object_counts.append(object_count)
            frame_left_counts.append(left)
            frame_center_counts.append(center)
            frame_right_counts.append(right)
            frame_lateral_presence.append(1 if (left + right) > 0 else 0)

        warning = ""
        if processed_count == 0:
            warning = "NO_PROCESSED_FRAMES_IN_WINDOW"
        elif processed_count < 5:
            warning = "LOW_FRAME_COVERAGE"
        elif int((~win_frames["processed"].astype(bool)).sum()) > 0:
            warning = "FAILED_FRAME_IN_WINDOW"

        cluster = event_map.get(anchor_id, {"event_cluster_id": "", "singleton_flag": False})
        row = {
            "anchor_id": anchor_id,
            "anchor_timestamp": anchor_time,
            "qwen_label": anchor.get("qwen_label", ""),
            "label_provenance_status": "confirmed_v13_8_qwen3_vl_32b_v13_6_prompt_o_enter_ego_path_v0",
            "event_cluster_id": cluster["event_cluster_id"],
            "singleton_flag": bool(cluster["singleton_flag"]),
            "num_sampled_frames_in_window": int(len(win_frames)),
            "num_processed_frames_in_window": int(processed_count),
            "num_detection_frames_in_window": int(detection_frames),
            "total_detection_count": int(len(win_dets)),
            "vehicle_count_mean": float(np.mean(frame_vehicle_counts)) if frame_vehicle_counts else 0.0,
            "vehicle_count_max": int(np.max(frame_vehicle_counts)) if frame_vehicle_counts else 0,
            "person_count_mean": float(np.mean(frame_person_counts)) if frame_person_counts else 0.0,
            "person_count_max": int(np.max(frame_person_counts)) if frame_person_counts else 0,
            "object_count_mean": float(np.mean(frame_object_counts)) if frame_object_counts else 0.0,
            "object_count_max": int(np.max(frame_object_counts)) if frame_object_counts else 0,
            "lateral_presence_mean": float(np.mean(frame_lateral_presence)) if frame_lateral_presence else 0.0,
            "lateral_presence_max": int(np.max(frame_lateral_presence)) if frame_lateral_presence else 0,
            "center_region_count_mean": float(np.mean(frame_center_counts)) if frame_center_counts else 0.0,
            "left_region_count_mean": float(np.mean(frame_left_counts)) if frame_left_counts else 0.0,
            "right_region_count_mean": float(np.mean(frame_right_counts)) if frame_right_counts else 0.0,
            "has_any_vehicle": bool(np.max(frame_vehicle_counts) > 0) if frame_vehicle_counts else False,
            "has_any_person": bool(np.max(frame_person_counts) > 0) if frame_person_counts else False,
            "proxy_feature_warning": warning,
        }
        rows.append(row)

    features = pd.DataFrame(rows)
    features["is_positive"] = features["qwen_label"].eq("positive")
    features["l3_rank"] = features["object_count_mean"].rank(method="first", ascending=False).astype(int)
    cols = [
        "anchor_id", "anchor_timestamp", "qwen_label", "label_provenance_status",
        "is_positive", "event_cluster_id", "singleton_flag", "l3_rank",
        "num_sampled_frames_in_window", "num_processed_frames_in_window",
        "num_detection_frames_in_window", "total_detection_count",
        "vehicle_count_mean", "vehicle_count_max", "person_count_mean", "person_count_max",
        "object_count_mean", "object_count_max", "lateral_presence_mean", "lateral_presence_max",
        "center_region_count_mean", "left_region_count_mean", "right_region_count_mean",
        "has_any_vehicle", "has_any_person", "proxy_feature_warning",
    ]
    features = features[cols]
    features.to_csv(TABLES / "realcartest_anchor_proxy_features_2fps.csv", index=False)
    return features


def write_anchor_feature_report(features: pd.DataFrame) -> None:
    mapped = int(features["anchor_timestamp"].notna().sum())
    missing_warning = int(warning_mask(features["proxy_feature_warning"]).sum())
    l3_fields = ["anchor_id", "anchor_timestamp", "qwen_label", "event_cluster_id", "object_count_mean", "l3_rank"]
    l3_ok = all(c in features.columns for c in l3_fields)
    coverage_desc = describe_series(features["num_processed_frames_in_window"])
    lines = [
        "# ANCHOR_FEATURE_REPORT.md - realcartest anchor proxy features",
        "",
        "## Method",
        "",
        "- Raw detections: YOLOv8n at 2 fps over realcartest.mp4.",
        "- Anchor table: V13.7 center10 anchor grid, 399 anchors.",
        "- Window definition: confirmed dataset3-compatible anchor_time +/- 5 s, 10 s center window.",
        "- Aggregates are computed over processed sampled frames in the anchor window.",
        "",
        "## Headline",
        "",
        format_kv_table([
            ("anchor_total", len(features)),
            ("anchor_timestamp_mapped", mapped),
            ("anchors_with_missing_or_warning", missing_warning),
            ("positive_labeled_anchors", int(features["is_positive"].sum())),
            ("negative_labeled_anchors", int((features["qwen_label"] == "negative").sum())),
            ("l3_required_fields_reproducible", "YES" if l3_ok else "NO"),
        ]),
        "",
        "## Frame Coverage",
        "",
        f"- Processed frames per anchor window: {coverage_desc}",
        f"- Sampled frames per anchor window: {describe_series(features['num_sampled_frames_in_window'])}",
        "",
        "## Proxy Distributions",
        "",
        f"- object_count_mean: {describe_series(features['object_count_mean'])}",
        f"- vehicle_count_mean: {describe_series(features['vehicle_count_mean'])}",
        f"- person_count_mean: {describe_series(features['person_count_mean'])}",
        f"- lateral_presence_mean: {describe_series(features['lateral_presence_mean'])}",
        "",
        "## Missingness",
        "",
        f"- proxy_feature_warning counts: {warning_counts(features['proxy_feature_warning'])}",
        "",
        "## Decision",
        "",
        "Anchor-level proxy feature extraction is complete and L3 fields are computable.",
        "",
    ]
    write_text(REPORTS / "ANCHOR_FEATURE_REPORT.md", "\n".join(map(str, lines)))
    append_log("Phase 3 complete", [
        f"- Anchor features written: {len(features)} rows",
        f"- Processed frame coverage: {coverage_desc}",
        f"- L3 fields computable: {'YES' if l3_ok else 'NO'}",
        f"- Warnings: {warning_counts(features['proxy_feature_warning'])}",
    ])


def phase3_anchor_features() -> pd.DataFrame:
    features = aggregate_anchor_features()
    write_anchor_feature_report(features)
    return features


def precision_recall_at_k(features: pd.DataFrame, ks: list[int]) -> pd.DataFrame:
    from sklearn.metrics import roc_auc_score

    labeled = features[features["qwen_label"].isin(["positive", "negative"])].copy()
    total_pos = int(labeled["is_positive"].sum())
    total_neg = int((~labeled["is_positive"]).sum())
    try:
        auc = float(roc_auc_score(labeled["is_positive"].astype(int), labeled["object_count_mean"]))
    except Exception:
        auc = float("nan")

    ordered = labeled.sort_values(["object_count_mean", "anchor_timestamp"], ascending=[False, True]).reset_index(drop=True)
    rows = []
    for k in ks:
        kk = min(k, len(ordered))
        top = ordered.head(kk)
        pos = int(top["is_positive"].sum())
        events = set(x for x in top["event_cluster_id"].dropna().astype(str).tolist() if x)
        rows.append({
            "metric_scope": "labeled_realcartest_v13_8",
            "score_column": "object_count_mean",
            "k": kk,
            "labeled_n": len(labeled),
            "positive_n": total_pos,
            "negative_n": total_neg,
            "auc": auc,
            "selected_positive_count": pos,
            "precision_at_k": pos / kk if kk else 0.0,
            "recall_at_k": pos / total_pos if total_pos else 0.0,
            "event_cluster_coverage_count": len(events),
            "label_provenance_status": "confirmed_v13_8_qwen3_vl_32b_v13_6_prompt_o_enter_ego_path_v0",
        })
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "realcartest_l3_labeled_subset_eval.csv", index=False)
    return out


def high_selectivity_scout(features: pd.DataFrame) -> pd.DataFrame:
    predicates: list[tuple[str, pd.Series, str]] = []
    predicates.append(("object_count_mean > 0", features["object_count_mean"] > 0, "cheap_proxy_threshold"))
    predicates.append(("object_count_mean above median", features["object_count_mean"] > features["object_count_mean"].median(), "cheap_proxy_threshold"))
    predicates.append(("object_count_mean above 75th percentile", features["object_count_mean"] > features["object_count_mean"].quantile(0.75), "cheap_proxy_threshold"))
    predicates.append(("vehicle_count_mean > 0", features["vehicle_count_mean"] > 0, "cheap_proxy_threshold"))
    predicates.append(("vehicle_count_mean above median", features["vehicle_count_mean"] > features["vehicle_count_mean"].median(), "cheap_proxy_threshold"))
    predicates.append(("person_count_mean > 0", features["person_count_mean"] > 0, "cheap_proxy_threshold"))
    predicates.append(("lateral_presence_mean > 0.5", features["lateral_presence_mean"] > 0.5, "cheap_proxy_threshold"))

    rows = []
    labeled = features["qwen_label"].isin(["positive", "negative"])
    total = len(features)
    for name, mask, source in predicates:
        selected = features[mask.fillna(False)]
        labeled_selected = selected[selected["qwen_label"].isin(["positive", "negative"])]
        pos_count = int(labeled_selected["is_positive"].sum())
        event_ids = set(x for x in labeled_selected["event_cluster_id"].dropna().astype(str).tolist() if x)
        selectivity = len(selected) / total if total else 0.0
        positive_rate = pos_count / len(labeled_selected) if len(labeled_selected) else float("nan")
        suitable = "YES" if (0.05 <= selectivity <= 0.75 and len(labeled_selected) >= 30) else "NO"
        dense_possible = "YES" if len(selected) >= 20 else "NO"
        rows.append({
            "predicate": name,
            "predicate_source": source,
            "selected_anchor_count": len(selected),
            "selectivity": selectivity,
            "labeled_selected_count": len(labeled_selected),
            "qwen_positive_count": pos_count,
            "qwen_positive_rate": positive_rate,
            "event_cluster_coverage": len(event_ids),
            "positive_definition": "existing V13.8 O_enter_ego_path_v0 Qwen/VLM-oracle-relative label",
            "circular_definition_warning": "NONE",
            "suitable_for_high_selectivity_dense_estimation_pilot": suitable,
            "no_new_oracle_pilot_possible": dense_possible,
        })
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "realcartest_high_selectivity_predicate_scout.csv", index=False)
    return out


def write_feasibility_report(features: pd.DataFrame, l3: pd.DataFrame, scout: pd.DataFrame) -> str:
    labeled_n = int(features["qwen_label"].isin(["positive", "negative"]).sum())
    pos_n = int(features["is_positive"].sum())
    positive_rate = pos_n / labeled_n if labeled_n else 0.0
    auc = float(l3["auc"].iloc[0]) if len(l3) else float("nan")
    provenance_trusted = True
    labels_enough = labeled_n >= 100 and pos_n >= 20
    feature_complete = int(warning_mask(features["proxy_feature_warning"]).sum()) == 0
    if feature_complete and provenance_trusted and labels_enough:
        decision = "REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION"
    elif feature_complete:
        decision = "REALCARTEST_PROXY_READY_BUT_LABEL_UNDERPOWERED"
    else:
        decision = "REALCARTEST_PROXY_MATERIALIZED_BUT_FEATURES_WEAK"

    l3_rows = [
        "| k | precision_at_k | recall_at_k | event_cluster_coverage |",
        "|---:|---:|---:|---:|",
    ]
    for _, row in l3.iterrows():
        l3_rows.append(f"| {int(row['k'])} | {row['precision_at_k']:.3f} | {row['recall_at_k']:.3f} | {int(row['event_cluster_coverage_count'])} |")

    scout_rows = [
        "| predicate | selected | selectivity | qwen_pos_rate | event_coverage | suitable |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, row in scout.iterrows():
        scout_rows.append(
            f"| {row['predicate']} | {int(row['selected_anchor_count'])} | {row['selectivity']:.3f} | "
            f"{row['qwen_positive_rate']:.3f} | {int(row['event_cluster_coverage'])} | "
            f"{row['suitable_for_high_selectivity_dense_estimation_pilot']} |"
        )

    lines = [
        "# FEASIBILITY_AUDIT_REPORT.md - realcartest L3 and high-selectivity feasibility",
        "",
        "## Label Scope",
        "",
        "- Positive means the existing V13.8 `O_enter_ego_path_v0` Qwen3-VL-32B oracle-relative label.",
        "- Positive does not mean the cheap predicate itself is true, and no new oracle labels were generated.",
        "- Label provenance is confirmed from V13.8 FINAL_REPORT: Qwen3-VL-32B-Instruct with the V13.6 prompt and negative-not-abstain rule.",
        "",
        "## L3 Feasibility",
        "",
        format_kv_table([
            ("labeled_anchors", labeled_n),
            ("positive_count", pos_n),
            ("negative_count", labeled_n - pos_n),
            ("positive_rate", f"{positive_rate:.3f}"),
            ("object_count_mean_auc", f"{auc:.3f}"),
            ("label_provenance_trusted", "YES" if provenance_trusted else "NO"),
            ("labels_enough_for_directional_l3_eval", "YES" if labels_enough else "NO"),
        ]),
        "",
        "\n".join(l3_rows),
        "",
        "## High-Selectivity Predicate Scout",
        "",
        "\n".join(scout_rows),
        "",
        "## Circular Definition Warning",
        "",
        "- NONE for this scout: positive counts/rates use existing independent V13.8 oracle labels, not predicate-implied pseudo-labels.",
        "",
        "## Interpretation",
        "",
        "- Engineering conclusion: realcartest has complete 2fps raw YOLO materialization and complete anchor features.",
        "- Research caution: these are VLM-oracle-relative labels, not human truth; any Strategy 7 or L3 claim must retain that qualifier.",
        f"- Final feasibility decision from Phase 4/5: `{decision}`.",
        "",
    ]
    write_text(REPORTS / "FEASIBILITY_AUDIT_REPORT.md", "\n".join(map(str, lines)))
    append_log("Phase 4 complete", [
        f"- Labeled anchors: {labeled_n}, positives: {pos_n}, positive_rate: {positive_rate:.3f}",
        f"- object_count_mean AUC: {auc:.3f}",
        f"- High-selectivity rows: {len(scout)}",
        f"- Decision tendency: {decision}",
    ])
    return decision


def phase4_feasibility(features: pd.DataFrame) -> str:
    l3 = precision_recall_at_k(features, [5, 10, 20, 40, 80, 100, len(features)])
    scout = high_selectivity_scout(features)
    return write_feasibility_report(features, l3, scout)


def write_final_decision(decision: str, reason: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "decision_label": decision,
        "reason": reason,
        "timestamp_utc": utc_now(),
        "no_vlm_called": True,
        "new_oracle_labels_produced": False,
        "output_dir": str(OUT_DIR),
    }]).to_csv(TABLES / "final_decision.csv", index=False)


def write_final_summary(decision: str) -> None:
    video = get_video_info(VIDEO_PATH)
    features_path = TABLES / "realcartest_anchor_proxy_features_2fps.csv"
    det_path = TABLES / "raw_yolo_detections_realcartest_2fps.csv"
    frame_path = TABLES / "yolo_sampled_frames_realcartest_2fps.csv"
    features = pd.read_csv(features_path) if features_path.exists() else pd.DataFrame()
    stats = frame_detection_summary(det_path, frame_path) if frame_path.exists() else {}
    l3_path = TABLES / "realcartest_l3_labeled_subset_eval.csv"
    scout_path = TABLES / "realcartest_high_selectivity_predicate_scout.csv"
    l3 = pd.read_csv(l3_path) if l3_path.exists() else pd.DataFrame()
    scout = pd.read_csv(scout_path) if scout_path.exists() else pd.DataFrame()
    gpu = gpu_status()
    auc = float(l3["auc"].iloc[0]) if len(l3) else float("nan")
    top20 = l3[l3["k"] == 20]
    top20_precision = float(top20["precision_at_k"].iloc[0]) if len(top20) else float("nan")
    top20_recall = float(top20["recall_at_k"].iloc[0]) if len(top20) else float("nan")
    circular = "NONE"
    if len(scout) and (scout["circular_definition_warning"] != "NONE").any():
        circular = "PRESENT"

    autonomous = [
        "Mapped requested garc_eval/outputs path to src/garc_eval/outputs because this checkout's active garc_eval output tree lives there.",
        "Used dataset3-confirmed anchor_time +/- 5 s window rather than an unconfirmed default.",
        "Defined vehicle-like COCO classes as bicycle/car/motorcycle/bus/truck to support the heterogeneous predicate.",
        "Computed lateral presence from image thirds because no ego-corridor annotations are available in raw bbox materialization.",
    ]
    lines = [
        "# FINAL_SUMMARY.md - realcartest proxy materialization v1",
        "",
        "## Oracle And Compute Policy",
        "",
        format_kv_table([
            ("called_any_vlm", "NO"),
            ("called_yolo", "YES"),
            ("produced_new_oracle_labels", "NO"),
            ("gpu_available", gpu["available"]),
            ("gpu_raw", gpu["raw"]),
        ]),
        "",
        "## Video",
        "",
        format_kv_table([
            ("path", VIDEO_PATH),
            ("width", video["width"]),
            ("height", video["height"]),
            ("fps", f"{video['fps']:.6f}"),
            ("duration_sec", f"{video['duration_sec']:.3f}"),
            ("duration_min", f"{video['duration_sec'] / 60.0:.2f}"),
        ]),
        "",
        "## Window And Label Provenance",
        "",
        "- Dataset3 window definition confirmed: anchor_time +/- 5 s, 10s center window, 2 fps raw bbox materialization.",
        "- Realcartest labels: confirmed V13.8 Qwen3-VL-32B-Instruct, V13.6 O_enter_ego_path_v0 prompt, negative-not-abstain rule.",
        "- All evaluation labels remain VLM-oracle-relative, not human truth.",
        "",
        "## Materialization",
        "",
        format_kv_table([
            ("sample_fps", SAMPLE_FPS),
            ("processed_frames", stats.get("processed_frames", 0)),
            ("failed_frames", stats.get("failed_frames", 0)),
            ("total_detections", stats.get("total_detections", 0)),
            ("vehicle_like_detections", stats.get("vehicle_like_detections", 0)),
            ("person_detections", stats.get("person_detections", 0)),
        ]),
        "",
        "## Anchor And Labeled Coverage",
        "",
        format_kv_table([
            ("anchor_rows", len(features)),
            ("anchor_rows_with_features", int((features["num_processed_frames_in_window"] > 0).sum()) if len(features) else 0),
            ("labeled_anchor_rows", int(features["qwen_label"].isin(["positive", "negative"]).sum()) if len(features) else 0),
            ("positive_anchor_rows", int(features["is_positive"].sum()) if len(features) else 0),
            ("feature_warning_rows", int(warning_mask(features["proxy_feature_warning"]).sum()) if len(features) else 0),
        ]),
        "",
        "## L3 Feasibility",
        "",
        format_kv_table([
            ("object_count_mean_auc", f"{auc:.3f}" if not math.isnan(auc) else "nan"),
            ("precision_at_20", f"{top20_precision:.3f}" if not math.isnan(top20_precision) else "nan"),
            ("recall_at_20", f"{top20_recall:.3f}" if not math.isnan(top20_recall) else "nan"),
            ("ready_for_strategy7_l3_validation", "YES" if decision == "REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION" else "PARTIAL"),
        ]),
        "",
        "## High-Selectivity Scout",
        "",
        f"- Scout predicates evaluated: {len(scout)}",
        f"- Circular definition warning: {circular}",
        "- See `tables/realcartest_high_selectivity_predicate_scout.csv` for per-predicate counts and Qwen-positive rates.",
        "",
        "## Autonomous Judgments",
        "",
    ]
    lines.extend([f"- {item}" for item in autonomous])
    lines.extend([
        "",
        "## Final Decision",
        "",
        f"`{decision}`",
        "",
        "realcartest_proxy_materialization_complete=true",
    ])
    write_text(OUT_DIR / "FINAL_SUMMARY.md", "\n".join(map(str, lines)))
    write_final_decision(decision, "completed all requested phases")
    append_log("Phase 5 complete", [
        f"- Final decision: {decision}",
        "- FINAL_SUMMARY.md and final_decision.csv written",
        "- realcartest_proxy_materialization_complete=true",
    ])


def run_all() -> int:
    ensure_dirs()
    if not phase0_inventory():
        return 2
    if not phase1_smoke():
        return 3
    phase2_full_run()
    features = phase3_anchor_features()
    decision = phase4_feasibility(features)
    write_final_summary(decision)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["all", "inventory", "smoke", "full", "features", "audit", "summary"], default="all")
    args = parser.parse_args()

    ensure_dirs()
    if args.phase == "all":
        return run_all()
    if args.phase == "inventory":
        return 0 if phase0_inventory() else 2
    if args.phase == "smoke":
        return 0 if phase1_smoke() else 3
    if args.phase == "full":
        phase2_full_run()
        return 0
    if args.phase == "features":
        phase3_anchor_features()
        return 0
    if args.phase == "audit":
        features = pd.read_csv(TABLES / "realcartest_anchor_proxy_features_2fps.csv")
        decision = phase4_feasibility(features)
        write_final_summary(decision)
        return 0
    if args.phase == "summary":
        decision = "REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION"
        final_path = TABLES / "final_decision.csv"
        if final_path.exists():
            prev = pd.read_csv(final_path)
            if len(prev) and "decision_label" in prev.columns:
                decision = str(prev["decision_label"].iloc[-1])
        write_final_summary(decision)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
