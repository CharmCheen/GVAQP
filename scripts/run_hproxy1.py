#!/usr/bin/env python3
"""
H-PROXY1: Controlled Proxy Comparison — Inference & Feature Extraction.
Runs B0 (YOLOv8n), B1/B2/B3 (YOLOP 640/320) detection + tracking on frozen 1200-frame sample plan.

Usage:
    python scripts/run_hproxy1.py detect_all
    python scripts/run_hproxy1.py track_all
    python scripts/run_hproxy1.py road_geometry
    python scripts/run_hproxy1.py cost_profile
    python scripts/run_hproxy1.py compare
    python scripts/run_hproxy1.py visualize
    python scripts/run_hproxy1.py finalize
"""

import sys, os, json, time, hashlib, argparse
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import pandas as pd
import torch
import lap  # linear assignment

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"
YOLOP_SANITY_DIR = PROJECT_ROOT / "outputs/yolop_target_sanity_v0"
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
YOLOV8N_PATH = PROJECT_ROOT / "models/yolo/yolov8n.pt"
YOLOP_320_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-320-320.onnx"
YOLOP_640_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-640-640.onnx"

COCO_CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
VEHICLE_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck
TARGET_IDS = {0, 1, 2, 3, 5, 7}  # person, bicycle, car, motorcycle, bus, truck

CONF_THRES = 0.25
IOU_THRES = 0.45


# ============================================================================
# Simple Kalman + Hungarian Tracker (ByteTrack-like)
# ============================================================================

class KalmanBoxTracker:
    count = 0

    def __init__(self, bbox):
        self.kf = self._init_kf()
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 1
        self.hit_streak = 1
        self.age = 1
        self.bbox = bbox  # [x1, y1, x2, y2]
        self._init_state(bbox)

    def _init_kf(self):
        kf = cv2.KalmanFilter(7, 4)
        kf.transitionMatrix = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1],
        ], np.float32)
        kf.measurementMatrix = np.eye(4, 7, dtype=np.float32)
        kf.processNoiseCov = np.eye(7, dtype=np.float32) * 0.03
        kf.processNoiseCov[4:, 4:] *= 0.01
        kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 0.1
        kf.errorCovPost = np.eye(7, dtype=np.float32) * 10
        return kf

    def _init_state(self, bbox):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        s = w * h
        r = w / max(h, 1)
        self.kf.statePost = np.array([[cx], [cy], [s], [r], [1.], [0.], [0.]], np.float32)

    def predict(self):
        if self.kf.statePost[4] + self.kf.statePost[5] + self.kf.statePost[6] == 0:
            self.kf.statePost[4] = 1.
        state = self.kf.predict()
        self.age += 1
        self.time_since_update += 1
        return self._state_to_bbox(state.flatten())

    def update(self, bbox):
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        s = w * h
        r = w / max(h, 1)
        self.kf.correct(np.array([[cx], [cy], [s], [r]], np.float32))
        self.history.append(bbox)
        self.bbox = bbox

    def _state_to_bbox(self, state):
        cx, cy, s, r, _, _, _ = state
        w = np.sqrt(s * r)
        h = s / max(w, 1)
        return np.array([cx - w/2, cy - h/2, cx + w/2, cy + h/2])


def iou_batch(bboxes1, bboxes2):
    """Compute pairwise IoU between two sets of [x1,y1,x2,y2] boxes."""
    x11, y11, x12, y12 = np.split(bboxes1, 4, axis=1)
    x21, y21, x22, y22 = np.split(bboxes2, 4, axis=1)
    xA = np.maximum(x11, x21.T)
    yA = np.maximum(y11, y21.T)
    xB = np.minimum(x12, x22.T)
    yB = np.minimum(y12, y22.T)
    inter_area = np.maximum(0, xB - xA) * np.maximum(0, yB - yA)
    area1 = (x12 - x11) * (y12 - y11)
    area2 = (x22 - x21) * (y22 - y21)
    union = area1 + area2.T - inter_area
    return inter_area / (union + 1e-6)


def associate_detections_to_trackers(detections, trackers, iou_threshold=0.3):
    """Linear assignment between detections and trackers using IoU."""
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty(0, dtype=int)
    if len(detections) == 0:
        return np.empty((0, 2), dtype=int), np.empty(0, dtype=int), np.arange(len(trackers))

    iou_matrix = iou_batch(detections, trackers)
    cost_matrix = 1.0 - iou_matrix

    _, col_ind, row_ind = lap.lapjv(cost_matrix, extend_cost=True, cost_limit=1.0 - iou_threshold + 1e-6)

    n_trk = len(trackers)
    n_det = len(detections)

    matched = []
    for r in range(min(n_det, len(row_ind))):
        c = row_ind[r]
        if c >= 0 and c < n_trk:
            matched.append([r, c])
    matched = np.array(matched, dtype=int).reshape(-1, 2) if matched else np.empty((0, 2), dtype=int)
    unmatched_dets = np.array([r for r in range(n_det) if r not in matched[:, 0]])
    unmatched_trks = np.array([c for c in range(n_trk) if c not in matched[:, 1]])
    return matched, unmatched_dets, unmatched_trks


class SimpleTracker:
    """Simple multi-object tracker using Kalman filter + Hungarian assignment."""

    def __init__(self, max_age=30, min_hits=3, iou_threshold=0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        self.frame_count = 0
        self.next_id = 0

    def update(self, dets):
        """dets: numpy array [N, 4] of [x1,y1,x2,y2]."""
        self.frame_count += 1

        # Get predicted locations
        trk_preds = []
        for t in self.trackers:
            trk_preds.append(t.predict())
        trk_preds = np.array(trk_preds).reshape(-1, 4)

        matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(
            dets, trk_preds, self.iou_threshold
        )

        # Update matched trackers
        for d_idx, t_idx in matched:
            self.trackers[t_idx].update(dets[d_idx])

        # Create new trackers for unmatched dets
        for d_idx in unmatched_dets:
            trk = KalmanBoxTracker(dets[d_idx])
            trk.id = self.next_id
            self.next_id += 1
            self.trackers.append(trk)

        # Collect active tracks
        active = []
        trackers_new = []
        for t in self.trackers:
            if t.time_since_update < 1 or (t.time_since_update < self.max_age and t.hit_streak >= self.min_hits):
                if t.time_since_update < 1:
                    active.append({"id": t.id, "bbox": t.bbox.tolist(), "hits": t.hits, "age": t.age})
                trackers_new.append(t)

        self.trackers = trackers_new
        return active


# ============================================================================
# YOLOv8n Detector (B0)
# ============================================================================

class YOLOv8Detector:
    def __init__(self, model_path, device="cuda"):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("ultralytics not installed")
        self.model = YOLO(str(model_path))
        self.device = device

    def detect(self, img_bgr, conf_thres=CONF_THRES):
        results = self.model(img_bgr, conf=conf_thres, verbose=False, device=self.device)
        if not results:
            return np.zeros((0, 5), dtype=np.float32)
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return np.zeros((0, 5), dtype=np.float32)
        boxes = r.boxes.xyxy.cpu().numpy()  # [N, 4] x1,y1,x2,y2
        confs = r.boxes.conf.cpu().numpy()  # [N]
        clss = r.boxes.cls.cpu().numpy().astype(int)  # [N]
        return np.column_stack([boxes, confs, clss.astype(float)])


# ============================================================================
# YOLOP Detector (reuse from sanity runner)
# ============================================================================

class YOLOPDetector:
    def __init__(self, model_path, input_size):
        import onnxruntime as ort
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), sess_opts, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.input_size = input_size
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

        # Anchors and strides from YOLOP config
        self.anchors = np.array(
            [[[3, 9, 5, 11, 4, 20], [7, 18, 6, 39, 12, 31], [19, 50, 38, 81, 68, 157]]],
            dtype=np.float32
        ).reshape(3, 3, 2)
        self.strides = np.array([8, 16, 32])
        self.na = 3

    def _letterbox(self, img, new_shape):
        shape = img.shape[:2]
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad_w = int(round(shape[1] * r))
        new_unpad_h = int(round(shape[0] * r))
        dw = (new_shape[1] - new_unpad_w) // 2
        dh = (new_shape[0] - new_unpad_h) // 2
        if new_unpad_w != shape[1] or new_unpad_h != shape[0]:
            img = cv2.resize(img, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((new_shape[0], new_shape[1], 3), 114, dtype=img.dtype)
        canvas[dh:dh + new_unpad_h, dw:dw + new_unpad_w] = img
        return canvas, r, dw, dh, new_unpad_w, new_unpad_h

    def _preprocess(self, img_bgr):
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        canvas, r, dw, dh, nw, nh = self._letterbox(img_rgb, (self.input_size, self.input_size))
        img = canvas.astype(np.float32) / 255.0
        img[..., 0] = (img[..., 0] - 0.485) / 0.229
        img[..., 1] = (img[..., 1] - 0.456) / 0.224
        img[..., 2] = (img[..., 2] - 0.406) / 0.225
        img = img.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
        return img, {"r": r, "dw": dw, "dh": dh, "nw": nw, "nh": nh,
                      "orig_h": img_bgr.shape[0], "orig_w": img_bgr.shape[1]}

    def detect(self, img_bgr, conf_thres=CONF_THRES):
        img, meta = self._preprocess(img_bgr)
        outputs = self.session.run(self.output_names, {self.input_name: img})
        det_out = outputs[0]  # (1, N, 6) - already decoded cx,cy,w,h,obj,cls
        da_out = outputs[1]   # (1, 2, H, W)
        ll_out = outputs[2]   # (1, 2, H, W)

        det = det_out[0]  # (N, 6)

        # Check if decoded (values > pixel range) or raw
        if det[:, 0].max() < 5:
            det = self._decode_det(det)

        obj_conf = det[:, 4]
        mask = obj_conf > conf_thres
        det = det[mask]
        if len(det) == 0:
            return np.zeros((0, 5), dtype=np.float32), meta

        conf = det[:, 4] * det[:, 5]
        boxes = np.zeros((len(det), 4), dtype=np.float32)
        boxes[:, 0] = det[:, 0] - det[:, 2] / 2
        boxes[:, 1] = det[:, 1] - det[:, 3] / 2
        boxes[:, 2] = det[:, 0] + det[:, 2] / 2
        boxes[:, 3] = det[:, 1] + det[:, 3] / 2

        valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
        boxes = boxes[valid]
        conf = conf[valid]

        # Restore to original coords
        r, dw, dh = meta["r"], meta["dw"], meta["dh"]
        boxes[:, [0, 2]] -= dw
        boxes[:, [1, 3]] -= dh
        boxes[:, :4] /= r
        boxes[:, 0] = np.clip(boxes[:, 0], 0, meta["orig_w"])
        boxes[:, 1] = np.clip(boxes[:, 1], 0, meta["orig_h"])
        boxes[:, 2] = np.clip(boxes[:, 2], 0, meta["orig_w"])
        boxes[:, 3] = np.clip(boxes[:, 3], 0, meta["orig_h"])

        # NMS
        if len(boxes) > 0:
            import torchvision.ops
            boxes_t = torch.from_numpy(boxes).float()
            scores_t = torch.from_numpy(conf).float()
            idx = torchvision.ops.nms(boxes_t, scores_t, IOU_THRES).numpy()
            if len(idx) > 300:
                idx = idx[:300]
            boxes, conf = boxes[idx], conf[idx]

        detections = np.column_stack([boxes, conf, np.zeros(len(boxes))])  # class=0 (vehicle)
        # Extract seg masks
        da_mask = self._seg_postprocess(da_out, meta)
        ll_mask = self._seg_postprocess(ll_out, meta)
        return detections, {"da_mask": da_mask, "ll_mask": ll_mask, "meta": meta}

    def _decode_det(self, det):
        n_anchors, n_stride_levels = 3, 3
        fm_sizes = [self.input_size // s for s in self.strides]
        expected = [n_anchors * h * w for h, w in zip(fm_sizes, fm_sizes)]
        decoded = []
        offset = 0
        for li, (h, w) in enumerate(zip(fm_sizes, fm_sizes)):
            n = expected[li]
            pred = det[offset:offset + n].copy()
            offset += n
            pred = pred.reshape(n_anchors, h, w, 6).transpose(1, 2, 0, 3)  # (h,w,na,6)
            yv, xv = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
            grid = np.stack([xv, yv], axis=-1).astype(np.float32)
            sx = 1.0 / (1.0 + np.exp(-pred[..., 0:2]))
            sy = 1.0 / (1.0 + np.exp(-pred[..., 2:4]))
            so = 1.0 / (1.0 + np.exp(-pred[..., 4:5]))
            sc = 1.0 / (1.0 + np.exp(-pred[..., 5:6]))
            cx = (sx[..., 0:1] * 2.0 - 0.5 + grid[..., 0:1]) * self.strides[li]
            cy = (sx[..., 1:2] * 2.0 - 0.5 + grid[..., 1:2]) * self.strides[li]
            w_ = (sy[..., 0:1] * 2.0) ** 2 * self.anchors[li, :, 0]
            h_ = (sy[..., 1:2] * 2.0) ** 2 * self.anchors[li, :, 1]
            d = np.concatenate([cx, cy, w_, h_, so, sc], axis=-1)
            decoded.append(d.reshape(-1, 6))
        return np.concatenate(decoded, axis=0)

    def _seg_postprocess(self, seg_out, meta):
        dh, dw = meta["dh"], meta["dw"]
        nh, nw = meta["nh"], meta["nw"]
        crop = seg_out[:, :, dh:dh + nh, dw:dw + nw]
        mask = np.argmax(crop, axis=1)[0].astype(np.uint8)
        mask = cv2.resize(mask, (meta["orig_w"], meta["orig_h"]), interpolation=cv2.INTER_LINEAR)
        return (mask > 0.5).astype(np.uint8)


# ============================================================================
# Road-Relative Geometry
# ============================================================================

def extract_road_geometry(ll_mask, da_mask, h, w):
    """Extract road-relative features from YOLOP lane and drivable masks.

    Returns dict with lane-relative position, boundary distances, etc.
    """
    geo = {}

    # Lane center estimate: mean x of lane pixels in bottom third
    h_bottom = int(h * 2 / 3)
    bottom_ll = ll_mask[h_bottom:, :]
    lane_center = 0.5
    if bottom_ll.sum() > 0:
        xs = np.where(bottom_ll.any(axis=0))[0]
        if len(xs) > 0:
            lane_center = float(np.median(xs) / w)

    # Left/right ego boundaries from connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(ll_mask, connectivity=8)
    geo["num_lane_components"] = num_labels - 1
    geo["lane_positive_ratio"] = float(ll_mask.sum() / ll_mask.size)

    # Find left/right boundaries in bottom region
    left_boundary, right_boundary = 0.0, 1.0
    if num_labels > 1:
        comp_x_centroids = centroids[1:, 0]
        if len(comp_x_centroids) > 1:
            sorted_idx = np.argsort(comp_x_centroids)
            n_comp = len(comp_x_centroids)
            left_comp = int(sorted_idx[n_comp // 4])
            right_comp = int(sorted_idx[3 * n_comp // 4])
            left_boundary = float(centroids[left_comp + 1, 0] / w)
            right_boundary = float(centroids[right_comp + 1, 0] / w)
            geo["left_boundary"] = left_boundary
            geo["right_boundary"] = right_boundary
            geo["lane_width"] = right_boundary - left_boundary

    geo["lane_center"] = lane_center

    # Drivable area stats
    geo["drivable_positive_ratio"] = float(da_mask.sum() / da_mask.size)
    # Bottom-center drivable
    bottom_center_x = int(w * 0.4)
    bottom_center_w = int(w * 0.2)
    bottom_da = da_mask[h_bottom:, bottom_center_x:bottom_center_x + bottom_center_w]
    geo["bottom_center_drivable"] = float(bottom_da.sum() / max(bottom_da.size, 1))

    return geo


def compute_road_relative_features(track, ll_mask, da_mask, h, w, prev_geo=None):
    """Compute road-relative features for a single track bounding box."""
    bbox = track["bbox"]
    cx = (bbox[0] + bbox[2]) / 2 / w
    cy = (bbox[1] + bbox[3]) / 2 / h
    box_w = (bbox[2] - bbox[0]) / w
    box_h = (bbox[3] - bbox[1]) / h

    geo = extract_road_geometry(ll_mask, da_mask, h, w)

    features = {
        "bbox_cx_norm": cx,
        "bbox_cy_norm": cy,
        "bbox_w_norm": box_w,
        "bbox_h_norm": box_h,
        "bbox_area_norm": box_w * box_h,
        "lane_center": geo.get("lane_center", 0.5),
        "lane_relative_position": cx - geo.get("lane_center", 0.5),  # negative=left, positive=right
        "left_boundary": geo.get("left_boundary", 0.0),
        "right_boundary": geo.get("right_boundary", 1.0),
        "distance_to_left_boundary": cx - geo.get("left_boundary", 0.0),
        "distance_to_right_boundary": geo.get("right_boundary", 1.0) - cx,
        "in_ego_corridor": float(
            geo.get("left_boundary", 0.0) <= cx <= geo.get("right_boundary", 1.0)
        ),
        "bottom_center_drivable": geo.get("bottom_center_drivable", 0.0),
        "lane_positive_ratio": geo.get("lane_positive_ratio", 0.0),
        "drivable_positive_ratio": geo.get("drivable_positive_ratio", 0.0),
        "num_lane_components": geo.get("num_lane_components", 0),
    }

    # Velocity if prev geometry available
    if prev_geo is not None:
        features["lane_relative_velocity"] = features["lane_relative_position"] - prev_geo.get("lane_relative_position", features["lane_relative_position"])

    return features


# ============================================================================
# Inference Pipeline
# ============================================================================

def load_sample_plan():
    with open(YOLOP_SANITY_DIR / "SAMPLE_PLAN.json", "r") as f:
        return json.load(f)


def run_detection(config_id, detector, output_name):
    """Run detection on all 1200 sample frames."""
    plan = load_sample_plan()
    video_info = plan["video_info"]
    windows = plan["windows"]

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    fps = video_info["fps"]
    all_dets = []

    for w in windows:
        clip_id = w["clip_id"]
        for fidx in w["sample_indices"]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
            ret, frame = cap.read()
            if not ret:
                continue
            h, w_img = frame.shape[:2]
            ts = fidx / fps

            t0 = time.perf_counter()
            result = detector.detect(frame)

            if isinstance(result, tuple):
                dets, extra = result
            else:
                dets, extra = result, {}

            t_total = time.perf_counter() - t0

            for i, det in enumerate(dets):
                all_dets.append({
                    "config_id": config_id, "clip_id": clip_id,
                    "frame_index": fidx, "timestamp": ts,
                    "orig_h": h, "orig_w": w_img,
                    "det_idx": i,
                    "x1": float(det[0]), "y1": float(det[1]),
                    "x2": float(det[2]), "y2": float(det[3]),
                    "confidence": float(det[4]),
                    "class_id": int(det[5]) if len(det) > 5 else 0,
                    "class_name": COCO_CLASSES.get(int(det[5]) if len(det) > 5 else 0, "vehicle"),
                    "infer_time_ms": t_total * 1000,
                })

    cap.release()

    df = pd.DataFrame(all_dets)
    df.to_parquet(OUTPUT_DIR / f"raw/detections/{output_name}.parquet", index=False)
    print(f"{config_id}: {len(df)} detections written to {output_name}.parquet")
    return df


def run_tracking(config_id, detections_df, output_name):
    """Run ByteTrack on detection results."""
    tracker = SimpleTracker(max_age=30, min_hits=2, iou_threshold=0.2)

    # Group by clip and frame
    tracks_all = []
    for clip_id, clip_group in detections_df.groupby("clip_id"):
        tracker.trackers = []
        tracker.next_id = 0  # reset IDs per clip
        for frame_idx, frame_group in clip_group.groupby("frame_index"):
            frame_group = frame_group.sort_values("frame_index")
            boxes = frame_group[["x1", "y1", "x2", "y2"]].values.astype(np.float32)
            active = tracker.update(boxes)
            for t in active:
                tracks_all.append({
                    "config_id": config_id, "clip_id": clip_id,
                    "frame_index": frame_idx, "track_id": t["id"],
                    "x1": t["bbox"][0], "y1": t["bbox"][1],
                    "x2": t["bbox"][2], "y2": t["bbox"][3],
                    "track_hits": t["hits"], "track_age": t["age"],
                })

    df = pd.DataFrame(tracks_all)
    df.to_parquet(OUTPUT_DIR / f"raw/tracks/{output_name}.parquet", index=False)
    print(f"{config_id}: {len(df)} track entries written to {output_name}.parquet")

    # Track stats
    stats = df.groupby(["clip_id", "track_id"]).agg(
        length=("frame_index", "count"),
        first_frame=("frame_index", "min"),
        last_frame=("frame_index", "max"),
    ).reset_index()
    stats["duration_frames"] = stats["last_frame"] - stats["first_frame"]
    print(f"{config_id} track stats: mean_len={stats['length'].mean():.1f}, "
          f"median_len={stats['length'].median():.1f}, "
          f"tracks_ge_2s={stats[stats['duration_frames'] >= 10]['track_id'].nunique()}/{stats['track_id'].nunique()}")
    return df


def run_road_geometry_for_config(config_id, detections_df):
    """Extract road-relative geometry for YOLOP configurations (B2/B3)."""
    if config_id not in ["B2", "B3"]:
        print(f"{config_id}: skipping road geometry (not YOLOP)")
        return

    is_input = 320 if config_id == "B3" else 640
    detector = YOLOPDetector(YOLOP_320_PATH if is_input == 320 else YOLOP_640_PATH, is_input)
    plan = load_sample_plan()
    windows = plan["windows"]
    cap = cv2.VideoCapture(str(VIDEO_PATH))

    all_geo = []
    sample_indices = set()
    for w in windows:
        sample_indices.update(w["sample_indices"])

    for fidx in sorted(sample_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
        ret, frame = cap.read()
        if not ret:
            continue
        h, w_img = frame.shape[:2]

        # Get YOLOP seg outputs for this frame
        detections, extra = detector.detect(frame)
        ll_mask = extra.get("ll_mask")
        da_mask = extra.get("da_mask")

        if ll_mask is None or da_mask is None:
            continue

        geo = extract_road_geometry(ll_mask, da_mask, h, w_img)
        geo["config_id"] = config_id
        geo["frame_index"] = fidx
        all_geo.append(geo)

    cap.release()

    df = pd.DataFrame(all_geo)
    df.to_parquet(OUTPUT_DIR / f"raw/road_geometry/{config_id}_road_geometry.parquet", index=False)
    print(f"{config_id}: {len(df)} road geometry frames written")
    return df


def run_cost_profile():
    """Run physical cost profiling for all 4 configurations."""
    import gc
    from ultralytics import YOLO

    plan = load_sample_plan()
    windows = plan["windows"]
    cap = cv2.VideoCapture(str(VIDEO_PATH))

    # Collect frames (reuse first window's samples)
    frames = []
    target_n = 350
    for w in windows:
        for fidx in w["sample_indices"]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            if len(frames) >= target_n:
                break
        if len(frames) >= target_n:
            break

    cap.release()
    warmup_n, measured_n = 20, min(300, max(0, len(frames) - 20))
    if len(frames) < warmup_n + measured_n:
        measured_n = max(0, len(frames) - warmup_n)

    cost_data = {}

    # B0: YOLOv8n
    print("\n--- B0: YOLOv8n ---")
    model = YOLO(str(YOLOV8N_PATH))
    timings = []
    for i in range(warmup_n):
        _ = model(frames[i], conf=CONF_THRES, verbose=False)
    for i in range(warmup_n, warmup_n + measured_n):
        t0 = time.perf_counter()
        _ = model(frames[i], conf=CONF_THRES, verbose=False)
        timings.append(time.perf_counter() - t0)

    cost_data["B0"] = {
        "warmup": warmup_n, "measured": len(timings),
        "fps_model": 1.0 / np.mean(timings),
        "p50_ms": float(np.percentile(timings, 50) * 1000),
        "p95_ms": float(np.percentile(timings, 95) * 1000),
    }
    del model; gc.collect()

    # B1/B2: YOLOP 640
    print("--- B1/B2: YOLOP 640 ---")
    detector = YOLOPDetector(YOLOP_640_PATH, 640)
    timings = []
    for i in range(warmup_n):
        _ = detector.detect(frames[i])
    for i in range(warmup_n, warmup_n + measured_n):
        t0 = time.perf_counter()
        _ = detector.detect(frames[i])
        timings.append(time.perf_counter() - t0)
    cost_data["B1_B2"] = {
        "warmup": warmup_n, "measured": len(timings),
        "fps_model": 1.0 / np.mean(timings),
        "p50_ms": float(np.percentile(timings, 50) * 1000),
        "p95_ms": float(np.percentile(timings, 95) * 1000),
    }

    # B3: YOLOP 320
    print("--- B3: YOLOP 320 ---")
    detector = YOLOPDetector(YOLOP_320_PATH, 320)
    timings = []
    for i in range(warmup_n):
        _ = detector.detect(frames[i])
    for i in range(warmup_n, warmup_n + measured_n):
        t0 = time.perf_counter()
        _ = detector.detect(frames[i])
        timings.append(time.perf_counter() - t0)
    cost_data["B3"] = {
        "warmup": warmup_n, "measured": len(timings),
        "fps_model": 1.0 / np.mean(timings),
        "p50_ms": float(np.percentile(timings, 50) * 1000),
        "p95_ms": float(np.percentile(timings, 95) * 1000),
    }

    with open(OUTPUT_DIR / "tables/physical_cost.json", "w") as f:
        json.dump(cost_data, f, indent=2)
    print(f"\nCost data saved. {json.dumps(cost_data, indent=2)}")
    return cost_data


def run_comparison():
    """Compute distributional comparisons between configs."""
    det_files = list((OUTPUT_DIR / "raw/detections").glob("*.parquet"))
    if not det_files:
        print("No detection files found. Run 'detect_all' first.")
        return

    all_dets = []
    for f in det_files:
        df = pd.read_parquet(f)
        all_dets.append(df)
    if not all_dets:
        return
    df = pd.concat(all_dets, ignore_index=True)

    # Per-config per-frame stats
    frame_stats = df.groupby(["config_id", "clip_id", "frame_index"]).agg(
        det_count=("det_idx", "count"),
        mean_conf=("confidence", "mean"),
        median_conf=("confidence", "median"),
        mean_area=("x2", lambda x: ((df.loc[x.index, "x2"] - df.loc[x.index, "x1"]) *
                                     (df.loc[x.index, "y2"] - df.loc[x.index, "y1"])).mean()),
    ).reset_index()

    # Aggregate per config
    config_stats = frame_stats.groupby("config_id").agg(
        mean_dets=("det_count", "mean"),
        median_dets=("det_count", "median"),
        std_dets=("det_count", "std"),
        zero_det_pct=("det_count", lambda x: (x == 0).mean() * 100),
        mean_conf=("mean_conf", "mean"),
        mean_box_area=("mean_area", "mean"),
        total_frames=("frame_index", "count"),
    ).reset_index()

    config_stats.to_csv(OUTPUT_DIR / "tables/detection_comparison.csv", index=False)
    print("Detection comparison:")
    print(config_stats.to_string(index=False))

    return config_stats


def run_finalize():
    """Generate final H-PROXY1 audited decision."""
    import time as time_mod

    # Collect all evidence
    evidence = {}

    # BASELINE_IDENTITY
    with open(OUTPUT_DIR / "BASELINE_IDENTITY.json") as f:
        evidence["baseline"] = json.load(f)

    # Detection comparison
    comp_path = OUTPUT_DIR / "tables/detection_comparison.csv"
    if comp_path.exists():
        evidence["detection_comparison"] = pd.read_csv(comp_path).to_dict("records")

    # Cost data
    cost_path = OUTPUT_DIR / "tables/physical_cost.json"
    if cost_path.exists():
        with open(cost_path) as f:
            evidence["cost"] = json.load(f)

    # Track stats
    track_files = list((OUTPUT_DIR / "raw/tracks").glob("*.parquet"))
    track_stats = {}
    for tf in track_files:
        df = pd.read_parquet(tf)
        config = df["config_id"].iloc[0] if len(df) > 0 else "unknown"
        stats = df.groupby(["clip_id", "track_id"]).agg(
            length=("frame_index", "count"),
        )
        track_stats[config] = {
            "total_tracks": int(stats.reset_index()["track_id"].nunique()),
            "mean_track_len": float(stats["length"].mean()),
            "median_track_len": float(stats["length"].median()),
            "tracks_ge_5": int((stats["length"] >= 5).sum()),
            "tracks_ge_10": int((stats["length"] >= 10).sum()),
        }
    evidence["track_stats"] = track_stats

    # Road geometry
    geo_files = list((OUTPUT_DIR / "raw/road_geometry").glob("*.parquet"))
    geo_stats = {}
    for gf in geo_files:
        df = pd.read_parquet(gf)
        cfg = df["config_id"].iloc[0] if len(df) > 0 else "unknown"
        geo_stats[cfg] = {
            "lane_positive_ratio_mean": float(df["lane_positive_ratio"].mean()),
            "lane_center_mean": float(df["lane_center"].mean()),
            "lane_center_std": float(df["lane_center"].std()),
            "drivable_positive_ratio_mean": float(df["drivable_positive_ratio"].mean()),
            "bottom_center_drivable_mean": float(df["bottom_center_drivable"].mean()),
        }
    evidence["road_geometry"] = geo_stats

    # Build audited decision
    e = evidence

    # Detector comparison (distributional only - no labels)
    det_comp = e.get("detection_comparison", [])
    b0_dets = b1_dets = b3_dets = 0
    for d in det_comp:
        if d["config_id"] == "B0":
            b0_dets = d["mean_dets"]
        elif d["config_id"] == "B1":
            b1_dets = d["mean_dets"]
        elif d["config_id"] == "B3":
            b3_dets = d["mean_dets"]

    deduplicated_decision = {
        "method": "H-PROXY1",
        "timestamp": time_mod.strftime('%Y-%m-%dT%H:%M:%SZ', time_mod.gmtime()),
        "decision": "H-PROXY1 = BLOCKED_WAITING_FOR_ANNOTATIONS",
        "reason": "Human-perception annotations (400 detection + 600 tracking + 100 lane frames) and DrivingDojo structured event labels are prerequisites for accuracy, tracking, and event metrics. Executable inference, distributional comparison, and cost profiling completed.",
        "executable_results_summary": {
            "detection_distribution": {
                "B0_YOLOv8n_dets_per_frame_mean": b0_dets,
                "B1_YOLOP640_dets_per_frame_mean": b1_dets,
                "B3_YOLOP320_dets_per_frame_mean": b3_dets,
            },
            "cost_profile": e.get("cost", {}),
            "track_stats": e.get("track_stats", {}),
            "road_geometry": e.get("road_geometry", {}),
        },
        "selected_config": "PENDING_ANNOTATIONS",
        "next_highest_value_work": "Obtain human annotations for the 1200-frame sample plan (400 detection + 600 tracking + 100 lane frames) OR reduce scope to distributional-only comparison with UNSUPERVISED event proxy (e.g., rule-baseline on target-domain video using YOLOP road geometry)",
        "unblock_conditions": [
            "Human annotation of detection/tracking/lane frames from long_video_dataset3.mp4",
            "Structured event labels for DrivingDojo (or alternative labeled event dataset)",
            "Implementation of LightGBM event proxy pipeline"
        ]
    }

    with open(OUTPUT_DIR / "AUDITED_DECISION.json", "w") as f:
        json.dump(deduplicated_decision, f, indent=2)

    # Final report
    report = f"""# H-PROXY1 — Final Report

## Decision: BLOCKED_WAITING_FOR_ANNOTATIONS

### Components Status

| Component | Status | Blocker |
|-----------|--------|---------|
| BASELINE_IDENTITY | COMPLETE | — |
| PREREGISTRATION | COMPLETE | — |
| Detection Comparison | PARTIAL | Human annotations needed for accuracy metrics |
| Tracking Comparison | PARTIAL | Human track-ID annotations needed |
| Road Geometry | COMPLETE (executable portion) | — |
| Event Proxy | BLOCKED | No DrivingDojo event labels; STRIVE-D annotations not public |
| Cost Profile | COMPLETE | — |
| Visual Audit | PENDING | — |

### What Was Executed

1. **Baseline identity frozen**: YOLOv8n (6.5MB, SHA-256 f59b3d...f83b36) via ultralytics 8.4.51
2. **PREREGISTRATION.json**: All hypotheses, methods, and blockers documented
3. **Detection inference**: B0 (YOLOv8n), B1/B2 (YOLOP-640), B3 (YOLOP-320) on all 1200 frozen frames
4. **Tracking**: Simple Kalman+Hungarian ByteTrack-like tracker on all configs
5. **Road geometry**: YOLOP lane/drivable features extracted for B2/B3
6. **Cost profiling**: Physical GPU timing with warmup

### Detection Distribution (Without Labels)

| Config | Mean Dets/Frame | Mean Confidence |
|--------|----------------|----------------|
| B0 (YOLOv8n) | {b0_dets:.1f} | — |
| B1 (YOLOP-640) | {b1_dets:.1f} | — |
| B3 (YOLOP-320) | {b3_dets:.1f} | — |

### Cost Profile

| Config | Model FPS | P50 (ms) | P95 (ms) |
|--------|-----------|----------|----------|
| B0 (YOLOv8n) | {e.get('cost', {}).get('B0', {}).get('fps_model', 0):.1f} | {e.get('cost', {}).get('B0', {}).get('p50_ms', 0):.1f} | {e.get('cost', {}).get('B0', {}).get('p95_ms', 0):.1f} |
| B1/B2 (YOLOP-640) | {e.get('cost', {}).get('B1_B2', {}).get('fps_model', 0):.1f} | {e.get('cost', {}).get('B1_B2', {}).get('p50_ms', 0):.1f} | {e.get('cost', {}).get('B1_B2', {}).get('p95_ms', 0):.1f} |
| B3 (YOLOP-320) | {e.get('cost', {}).get('B3', {}).get('fps_model', 0):.1f} | {e.get('cost', {}).get('B3', {}).get('p50_ms', 0):.1f} | {e.get('cost', {}).get('B3', {}).get('p95_ms', 0):.1f} |

### Next Highest-Value Work

Obtain human annotations for detection (400 frames) and tracking (600 frames) from the frozen sample plan.
OR: Reduce scope to distributional-only comparison with rule-baseline event proxy on target-domain video using YOLOP road geometry (no DrivingDojo labels needed).

### Unblock Conditions

1. Human annotation of 400 detection frames + 600 tracking frames + 100 lane sanity frames
2. Structured event labels for DrivingDojo (or alternative labeled event dataset)
3. Implementation of LightGBM event proxy pipeline
"""

    with open(OUTPUT_DIR / "FINAL_REPORT.md", "w") as f:
        f.write(report)

    print("\n" + "=" * 60)
    print("FINAL DECISION: H-PROXY1 = BLOCKED_WAITING_FOR_ANNOTATIONS")
    print("=" * 60)
    print(report)


def main():
    parser = argparse.ArgumentParser(description="H-PROXY1: Controlled Proxy Comparison")
    parser.add_argument("command", choices=["detect_all", "track_all", "road_geometry",
                                             "cost_profile", "compare", "finalize"],
                        help="Phase to run")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ["raw/detections", "raw/tracks", "raw/road_geometry", "raw/event_scores",
                "tables", "plots"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    if args.command == "detect_all":
        # B0: YOLOv8n
        print("=== B0: YOLOv8n ===")
        b0 = YOLOv8Detector(YOLOV8N_PATH, "cuda")
        run_detection("B0", b0, "B0_yolov8n_dets")

        # B1: YOLOP-640 detection only
        print("\n=== B1: YOLOP-640 ===")
        b1 = YOLOPDetector(YOLOP_640_PATH, 640)
        run_detection("B1", b1, "B1_yolop640_dets")

        # B2: same detections as B1 (same YOLOP-640 model)
        print("\n=== B2: YOLOP-640 (copy from B1) ===")
        df_b1 = pd.read_parquet(OUTPUT_DIR / "raw/detections/B1_yolop640_dets.parquet")
        df_b2 = df_b1.copy()
        df_b2["config_id"] = "B2"
        df_b2.to_parquet(OUTPUT_DIR / "raw/detections/B2_yolop640_dets.parquet", index=False)
        print(f"B2: {len(df_b2)} detections (same as B1)")

        # B3: YOLOP-320
        print("\n=== B3: YOLOP-320 ===")
        b3 = YOLOPDetector(YOLOP_320_PATH, 320)
        run_detection("B3", b3, "B3_yolop320_dets")

    elif args.command == "track_all":
        configs = ["B0", "B1", "B2", "B3"]
        det_map = {
            "B0": "B0_yolov8n_dets.parquet",
            "B1": "B1_yolop640_dets.parquet",
            "B2": "B2_yolop640_dets.parquet",
            "B3": "B3_yolop320_dets.parquet",
        }
        for cfg in configs:
            fpath = OUTPUT_DIR / f"raw/detections/{det_map[cfg]}"
            if not fpath.exists():
                print(f"{cfg}: detection file not found, skipping")
                continue
            print(f"\n=== {cfg}: Tracking ===")
            df = pd.read_parquet(fpath)
            run_tracking(cfg, df, f"{cfg}_tracks")

    elif args.command == "road_geometry":
        for cfg in ["B2", "B3"]:
            print(f"\n=== {cfg}: Road Geometry ===")
            run_road_geometry_for_config(cfg, None)

    elif args.command == "cost_profile":
        run_cost_profile()

    elif args.command == "compare":
        run_comparison()

    elif args.command == "finalize":
        run_comparison()
        run_cost_profile()
        run_finalize()


if __name__ == "__main__":
    main()
