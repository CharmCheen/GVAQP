#!/usr/bin/env python3
"""Run YOLO IoU tracking and proxy scoring for roadclip_budget_v2."""

from __future__ import annotations

import argparse
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import cv2

from common import DEFAULT_CONFIG, clamp01, ensure_output_dir, fail, fmt_float, load_config, read_csv, require_abs_path, to_float, validate_base_paths, write_blocked, write_csv


TRACK_FIELDS = ["clip_id", "frame_idx", "time_sec", "track_id", "class_name", "conf", "x1", "y1", "x2", "y2", "cx", "cy", "w", "h", "area", "frame_w", "frame_h"]
SCORE_FIELDS = [
    "clip_id",
    "video_id",
    "segment_id",
    "start_time",
    "end_time",
    "clip_path",
    "score_count",
    "score_naive",
    "score_kinematic",
    "mean_vehicle_count",
    "max_vehicle_count",
    "max_area_growth",
    "max_center_motion",
    "max_ego_path_overlap",
    "max_predicted_entry",
    "max_lateral_toward_ego_path",
    "max_temporal_persistence",
    "track_count",
    "stable_track_count",
]


def require_yolo():
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    try:
        from ultralytics import YOLO
    except ImportError:
        fail("missing dependency ultralytics")
    return YOLO


def default_device() -> str:
    try:
        import torch
    except Exception:
        return "cpu"
    return "0" if torch.cuda.is_available() else "cpu"


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


class IouTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missing: int = 5):
        self.iou_threshold = iou_threshold
        self.max_missing = max_missing
        self.next_id = 1
        self.tracks: dict[int, dict] = {}

    def update(self, detections: list[dict]) -> list[dict]:
        pairs = []
        for tid, track in self.tracks.items():
            for didx, det in enumerate(detections):
                pairs.append((iou(track["box"], det["box"]), tid, didx))
        assigned_tracks, assigned_dets = set(), set()
        for score, tid, didx in sorted(pairs, reverse=True):
            if score < self.iou_threshold or tid in assigned_tracks or didx in assigned_dets:
                continue
            detections[didx]["track_id"] = tid
            self.tracks[tid] = {"box": detections[didx]["box"], "missing": 0}
            assigned_tracks.add(tid)
            assigned_dets.add(didx)
        for didx, det in enumerate(detections):
            if didx in assigned_dets:
                continue
            tid = self.next_id
            self.next_id += 1
            det["track_id"] = tid
            self.tracks[tid] = {"box": det["box"], "missing": 0}
        for tid in list(self.tracks):
            if tid not in assigned_tracks and all(det.get("track_id") != tid for det in detections):
                self.tracks[tid]["missing"] += 1
                if self.tracks[tid]["missing"] > self.max_missing:
                    del self.tracks[tid]
        return detections


def detections_from_result(result, vehicle_classes: set[str]) -> list[dict]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    clss = boxes.cls.cpu().numpy().astype(int)
    out = []
    for box, conf, cls_id in zip(xyxy, confs, clss):
        class_name = result.names.get(int(cls_id), str(cls_id))
        if class_name not in vehicle_classes:
            continue
        x1, y1, x2, y2 = [float(v) for v in box]
        out.append({"box": [x1, y1, x2, y2], "class_name": class_name, "conf": float(conf)})
    return out


def track_clip(model, clip: dict, vehicle_classes: set[str], device: str) -> list[dict]:
    clip_path = Path(clip["clip_path"])
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open clip: {clip_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    tracker = IouTracker()
    rows = []
    for frame_idx, result in enumerate(model.predict(source=str(clip_path), stream=True, device=device, verbose=False)):
        detections = tracker.update(detections_from_result(result, vehicle_classes))
        for det in detections:
            x1, y1, x2, y2 = det["box"]
            w, h = max(0.0, x2 - x1), max(0.0, y2 - y1)
            rows.append(
                {
                    "clip_id": clip["clip_id"],
                    "frame_idx": frame_idx,
                    "time_sec": f"{frame_idx / fps:.6f}" if fps else "0.000000",
                    "track_id": det["track_id"],
                    "class_name": det["class_name"],
                    "conf": f"{det['conf']:.6f}",
                    "x1": f"{x1:.3f}",
                    "y1": f"{y1:.3f}",
                    "x2": f"{x2:.3f}",
                    "y2": f"{y2:.3f}",
                    "cx": f"{(x1 + x2) / 2.0:.3f}",
                    "cy": f"{(y1 + y2) / 2.0:.3f}",
                    "w": f"{w:.3f}",
                    "h": f"{h:.3f}",
                    "area": f"{w * h:.3f}",
                    "frame_w": frame_w,
                    "frame_h": frame_h,
                }
            )
    return rows


def group_tracks(track_rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    grouped = defaultdict(lambda: defaultdict(list))
    for row in track_rows:
        grouped[row["clip_id"]][str(row["track_id"])].append(row)
    for tracks in grouped.values():
        for rows in tracks.values():
            rows.sort(key=lambda r: int(float(r["frame_idx"])))
    return grouped


def roi_overlap(row: dict, cfg: dict) -> float:
    fw, fh = to_float(row["frame_w"]), to_float(row["frame_h"])
    if fw <= 0 or fh <= 0:
        return 0.0
    rx1, rx2 = float(cfg["roi_x1"]) * fw, float(cfg["roi_x2"]) * fw
    ry1, ry2 = float(cfg["roi_y1"]) * fh, float(cfg["roi_y2"]) * fh
    x1, y1, x2, y2 = to_float(row["x1"]), to_float(row["y1"]), to_float(row["x2"]), to_float(row["y2"])
    inter = max(0.0, min(x2, rx2) - max(x1, rx1)) * max(0.0, min(y2, ry2) - max(y1, ry1))
    area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / area if area > 0 else 0.0


def track_features(rows: list[dict], clip_len: float, cfg: dict) -> dict:
    first, last = rows[0], rows[-1]
    fw, fh = max(to_float(last["frame_w"]), 1.0), max(to_float(last["frame_h"]), 1.0)
    times = [to_float(r["time_sec"]) for r in rows]
    duration = max(times) - min(times) if len(times) > 1 else 0.0
    persistence = clamp01(duration / max(clip_len, 1e-6))
    first_area, last_area = max(to_float(first["area"]), 1.0), max(to_float(last["area"]), 1.0)
    area_growth = clamp01(max(0.0, last_area / first_area - 1.0) / 2.0)
    center_motion = clamp01(math.hypot(to_float(last["cx"]) - to_float(first["cx"]), to_float(last["cy"]) - to_float(first["cy"])) / math.hypot(fw, fh))
    overlap = max(roi_overlap(r, cfg) for r in rows)
    recent = rows[-min(6, len(rows)) :]
    if len(recent) >= 2:
        dt = max(to_float(recent[-1]["time_sec"]) - to_float(recent[0]["time_sec"]), 1e-6)
        vx = (to_float(recent[-1]["cx"]) - to_float(recent[0]["cx"])) / dt
        vy = (to_float(recent[-1]["cy"]) - to_float(recent[0]["cy"])) / dt
    else:
        vx = vy = 0.0
    horizon = float(cfg["prediction_horizon_sec"])
    pred_x, pred_y = to_float(last["cx"]) + vx * horizon, to_float(last["cy"]) + vy * horizon
    rx1, rx2 = float(cfg["roi_x1"]) * fw, float(cfg["roi_x2"]) * fw
    ry1, ry2 = float(cfg["roi_y1"]) * fh, float(cfg["roi_y2"]) * fh
    pred_entry = 1.0 if rx1 <= pred_x <= rx2 and ry1 <= pred_y <= ry2 else clamp01(1.0 - math.hypot((pred_x - (rx1 + rx2) / 2) / fw, (pred_y - (ry1 + ry2) / 2) / fh) / 0.5)
    roi_center_x = (rx1 + rx2) / 2
    direction = math.copysign(1.0, roi_center_x - to_float(last["cx"])) if roi_center_x != to_float(last["cx"]) else 0.0
    lateral = clamp01(max(0.0, vx * direction) / (0.20 * fw))
    frame_indices = [int(float(r["frame_idx"])) for r in rows]
    expected = frame_indices[-1] - frame_indices[0] + 1 if frame_indices else 1
    instability = clamp01(1.0 - len(set(frame_indices)) / max(expected, 1))
    risk = clamp01(0.30 * pred_entry + 0.20 * lateral + 0.20 * area_growth + 0.20 * persistence + 0.10 * overlap - 0.20 * instability)
    return {"area_growth": area_growth, "center_motion": center_motion, "overlap": overlap, "pred_entry": pred_entry, "lateral": lateral, "persistence": persistence, "risk": risk}


def score_clip(clip: dict, tracks: dict[str, list[dict]], cfg: dict) -> dict:
    clip_len = to_float(clip["end_time"]) - to_float(clip["start_time"])
    frame_counts = defaultdict(int)
    for rows in tracks.values():
        for row in rows:
            frame_counts[row["frame_idx"]] += 1
    mean_count = sum(frame_counts.values()) / len(frame_counts) if frame_counts else 0.0
    max_count = max(frame_counts.values()) if frame_counts else 0
    score_count = clamp01(0.6 * mean_count / 8.0 + 0.4 * max_count / 12.0)
    feats = [track_features(rows, clip_len, cfg) for rows in tracks.values() if rows]
    stable = [f for f in feats if f["persistence"] >= 0.30]
    max_area_growth = max((f["area_growth"] for f in feats), default=0.0)
    max_center_motion = max((f["center_motion"] for f in feats), default=0.0)
    max_overlap = max((f["overlap"] for f in feats), default=0.0)
    max_pred_entry = max((f["pred_entry"] for f in feats), default=0.0)
    max_lateral = max((f["lateral"] for f in feats), default=0.0)
    max_persistence = max((f["persistence"] for f in feats), default=0.0)
    score_naive = clamp01(0.25 * max_area_growth + 0.20 * max_center_motion + 0.25 * max_overlap + 0.15 * clamp01(len(stable) / 5.0) + 0.15 * max_persistence)
    score_kinematic = max((f["risk"] for f in feats), default=0.0)
    return {
        "clip_id": clip["clip_id"],
        "video_id": clip["video_id"],
        "segment_id": clip["segment_id"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "clip_path": clip["clip_path"],
        "score_count": fmt_float(score_count),
        "score_naive": fmt_float(score_naive),
        "score_kinematic": fmt_float(score_kinematic),
        "mean_vehicle_count": fmt_float(mean_count),
        "max_vehicle_count": max_count,
        "max_area_growth": fmt_float(max_area_growth),
        "max_center_motion": fmt_float(max_center_motion),
        "max_ego_path_overlap": fmt_float(max_overlap),
        "max_predicted_entry": fmt_float(max_pred_entry),
        "max_lateral_toward_ego_path": fmt_float(max_lateral),
        "max_temporal_persistence": fmt_float(max_persistence),
        "track_count": len(tracks),
        "stable_track_count": len(stable),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run YOLO proxy scoring.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    clips_path = output_dir / "clips.csv"
    if not clips_path.is_file():
        path = write_blocked(output_dir, "BLOCKED_proxy_missing_clips.md", "BLOCKED: Proxy Missing Clips", ["Run `02_make_road_clips.py` first."])
        print(f"blocked_report={path}")
        return
    model_path = require_abs_path(cfg, "yolo_model", True, False)
    clips = read_csv(clips_path)
    proxy_cfg = cfg.get("proxy") or {}
    vehicle_classes = set(proxy_cfg.get("vehicle_classes") or [])
    if not vehicle_classes:
        fail("proxy.vehicle_classes is empty")
    YOLO = require_yolo()
    model = YOLO(str(model_path))
    device = args.device or default_device()
    start = time.time()
    all_rows, failed = [], []
    for i, clip in enumerate(clips, 1):
        try:
            rows = track_clip(model, clip, vehicle_classes, device)
            all_rows.extend(rows)
            print(f"[{i}/{len(clips)}] {clip['clip_id']} track_rows={len(rows)}", flush=True)
        except Exception as exc:
            failed.append({"clip_id": clip["clip_id"], "error": str(exc)})
            print(f"[{i}/{len(clips)}] {clip['clip_id']} FAILED {exc}", flush=True)
    write_csv(output_dir / "tracks.csv", all_rows, TRACK_FIELDS)
    grouped = group_tracks(all_rows)
    scores = [score_clip(clip, grouped.get(clip["clip_id"], {}), proxy_cfg) for clip in clips]
    write_csv(output_dir / "proxy_scores.csv", scores, SCORE_FIELDS)
    if failed:
        write_csv(output_dir / "proxy_failed_clips.csv", failed, ["clip_id", "error"])
    runtime = time.time() - start
    lines = ["# Proxy Scoring Report", "", f"- clips: {len(clips)}", f"- tracks rows: {len(all_rows)}", f"- failed clips: {len(failed)}", f"- runtime sec: {runtime:.3f}", f"- runtime per clip sec: {runtime / len(clips):.3f}" if clips else "- runtime per clip sec: n/a"]
    for col in ["score_count", "score_naive", "score_kinematic"]:
        vals = [float(r[col]) for r in scores]
        mean = sum(vals) / len(vals) if vals else 0.0
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)) if vals else 0.0
        lines.append(f"- {col}: mean={mean:.4f} std={std:.4f} min={min(vals) if vals else 0:.4f} max={max(vals) if vals else 0:.4f}")
    (output_dir / "proxy_scoring_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"proxy_scores={output_dir / 'proxy_scores.csv'}")
    print(f"tracks={output_dir / 'tracks.csv'}")


if __name__ == "__main__":
    main()
