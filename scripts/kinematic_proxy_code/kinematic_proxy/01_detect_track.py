#!/usr/bin/env python3
"""Run YOLO detection/tracking on generated clips."""

import argparse
import os
from pathlib import Path

import cv2

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, read_csv, validate_base_paths, write_csv


def require_ultralytics():
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    try:
        from ultralytics import YOLO
    except ImportError:
        fail("missing dependency ultralytics. Install with: pip install ultralytics")
    return YOLO


def default_device() -> str:
    try:
        import torch
    except Exception:
        return "cpu"
    return "0" if torch.cuda.is_available() else "cpu"


def ultralytics_track_dependencies_available() -> tuple[bool, str]:
    try:
        import lap  # noqa: F401
    except Exception as exc:
        return False, f"missing lap dependency for ultralytics tracker: {exc}"
    return True, "ok"


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


class SimpleIouTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missing: int = 5):
        self.iou_threshold = iou_threshold
        self.max_missing = max_missing
        self.next_id = 1
        self.tracks: dict[int, dict] = {}

    def update(self, detections: list[dict]) -> list[dict]:
        assigned_tracks = set()
        assigned_dets = set()
        pairs = []
        for tid, track in self.tracks.items():
            for didx, det in enumerate(detections):
                pairs.append((iou(track["box"], det["box"]), tid, didx))
        for score, tid, didx in sorted(pairs, reverse=True):
            if score < self.iou_threshold or tid in assigned_tracks or didx in assigned_dets:
                continue
            self.tracks[tid] = {"box": detections[didx]["box"], "missing": 0}
            detections[didx]["track_id"] = tid
            assigned_tracks.add(tid)
            assigned_dets.add(didx)

        for didx, det in enumerate(detections):
            if didx in assigned_dets:
                continue
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = {"box": det["box"], "missing": 0}
            det["track_id"] = tid

        for tid in list(self.tracks):
            if tid not in assigned_tracks and all(det.get("track_id") != tid for det in detections):
                self.tracks[tid]["missing"] += 1
                if self.tracks[tid]["missing"] > self.max_missing:
                    del self.tracks[tid]
        return detections


def result_to_detections(result, names: dict, vehicle_classes: set[str]) -> list[dict]:
    detections = []
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return detections
    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    clss = boxes.cls.cpu().numpy().astype(int)
    ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [None] * len(xyxy)
    for box, conf, cls_id, track_id in zip(xyxy, confs, clss, ids):
        class_name = names.get(int(cls_id), str(cls_id))
        if class_name not in vehicle_classes:
            continue
        x1, y1, x2, y2 = [float(v) for v in box]
        detections.append(
            {
                "box": [x1, y1, x2, y2],
                "class_name": class_name,
                "conf": float(conf),
                "track_id": int(track_id) if track_id is not None else None,
            }
        )
    return detections


def make_row(clip_id: str, frame_idx: int, fps: float, det: dict, frame_w: int, frame_h: int) -> dict:
    x1, y1, x2, y2 = det["box"]
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    return {
        "clip_id": clip_id,
        "frame_idx": frame_idx,
        "time_sec": f"{frame_idx / fps:.6f}" if fps > 0 else "0.000000",
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


def track_clip_with_ultralytics(model, clip_path: Path, clip_id: str, vehicle_classes: set[str], device: str) -> list[dict]:
    cap = cv2.VideoCapture(str(clip_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    rows = []
    results = model.track(source=str(clip_path), stream=True, persist=True, tracker="bytetrack.yaml", device=device, verbose=False)
    for frame_idx, result in enumerate(results):
        names = result.names
        detections = result_to_detections(result, names, vehicle_classes)
        for det in detections:
            if det["track_id"] is None:
                raise RuntimeError("ultralytics track returned detections without track IDs")
            rows.append(make_row(clip_id, frame_idx, fps, det, frame_w, frame_h))
    return rows


def track_clip_with_iou(model, clip_path: Path, clip_id: str, vehicle_classes: set[str], device: str) -> list[dict]:
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        fail(f"failed to open clip: {clip_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    tracker = SimpleIouTracker()
    rows = []
    for frame_idx, result in enumerate(model.predict(source=str(clip_path), stream=True, device=device, verbose=False)):
        detections = result_to_detections(result, result.names, vehicle_classes)
        detections = tracker.update(detections)
        for det in detections:
            rows.append(make_row(clip_id, frame_idx, fps, det, frame_w, frame_h))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect and track vehicles in generated clips.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", type=str, default=None, help="YOLO device, default is 0 when CUDA is available else cpu.")
    parser.add_argument("--force-iou-fallback", action="store_true", help="Skip ultralytics track and use local IoU tracker.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg, need_video=False, need_model=True)
    output_dir = ensure_output_dir(cfg)
    clips_csv = output_dir / "clips.csv"
    clips = read_csv(clips_csv)
    vehicle_classes = set(cfg.get("vehicle_classes") or [])
    if not vehicle_classes:
        fail("vehicle_classes is empty in config")

    YOLO = require_ultralytics()
    model_path = Path(cfg["yolo_model"])
    if model_path != Path("/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt"):
        fail(f"yolo_model must be /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt, got {model_path}")
    model = YOLO(str(model_path))
    device = args.device or default_device()
    print(f"yolo_device={device}", flush=True)
    can_use_ultralytics_track, track_reason = ultralytics_track_dependencies_available()
    if args.force_iou_fallback:
        can_use_ultralytics_track = False
        track_reason = "forced by --force-iou-fallback"
    if not can_use_ultralytics_track:
        print(f"WARN: using IoU fallback for all clips because {track_reason}", flush=True)

    rows = []
    used_fallback = False
    for clip in clips:
        clip_path = Path(clip["clip_path"])
        if not clip_path.is_file():
            fail(f"clip file from clips.csv not found: {clip_path}")
        if can_use_ultralytics_track:
            try:
                clip_rows = track_clip_with_ultralytics(model, clip_path, clip["clip_id"], vehicle_classes, device)
            except Exception as exc:
                print(f"WARN: ultralytics track failed on {clip_path.name}; using IoU fallback. Reason: {exc}", flush=True)
                used_fallback = True
                clip_rows = track_clip_with_iou(model, clip_path, clip["clip_id"], vehicle_classes, device)
        else:
            used_fallback = True
            clip_rows = track_clip_with_iou(model, clip_path, clip["clip_id"], vehicle_classes, device)
        rows.extend(clip_rows)
        print(f"processed {clip['clip_id']}: {len(clip_rows)} track rows", flush=True)

    fieldnames = [
        "clip_id",
        "frame_idx",
        "time_sec",
        "track_id",
        "class_name",
        "conf",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "w",
        "h",
        "area",
        "frame_w",
        "frame_h",
    ]
    out_path = output_dir / "tracks.csv"
    write_csv(out_path, rows, fieldnames)
    print(f"tracks_csv={out_path}")
    print(f"track_rows={len(rows)}")
    print(f"used_iou_fallback={used_fallback}")


if __name__ == "__main__":
    main()
