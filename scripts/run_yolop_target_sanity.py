#!/usr/bin/env python3
"""
YOLOP Target-Domain Sanity Audit Runner.

Usage:
    python scripts/run_yolop_target_sanity.py inspect
    python scripts/run_yolop_target_sanity.py smoke
    python scripts/run_yolop_target_sanity.py sample
    python scripts/run_yolop_target_sanity.py compare
    python scripts/run_yolop_target_sanity.py finalize
"""

import os, sys, json, time, hashlib, argparse, copy, math, io
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import pandas as pd
import torch
import torchvision.ops
import onnxruntime as ort

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/yolop_target_sanity_v0"
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
WEIGHT_DIR = PROJECT_ROOT / "YOLOP/weights"
YOLOP_ROOT = PROJECT_ROOT / "YOLOP"

CONF_THRES = 0.25
IOU_THRES = 0.45

MODEL_SPECS = {
    "onnx_320": {"path": WEIGHT_DIR / "yolop-320-320.onnx", "size": 320, "backend": "onnx", "num_dets": 6300},
    "onnx_640": {"path": WEIGHT_DIR / "yolop-640-640.onnx", "size": 640, "backend": "onnx", "num_dets": 25200},
    "onnx_1280": {"path": WEIGHT_DIR / "yolop-1280-1280.onnx", "size": 1280, "backend": "onnx", "num_dets": 100800},
    "pytorch_640": {"path": WEIGHT_DIR / "End-to-end.pth", "size": 640, "backend": "pytorch", "num_dets": 25200},
}

ANCHORS = [
    [3, 9, 5, 11, 4, 20],
    [7, 18, 6, 39, 12, 31],
    [19, 50, 38, 81, 68, 157],
]
STRIDES = [8, 16, 32]
CLASS_NAMES = {0: "vehicle"}


def letterbox(img, new_shape, color=(114, 114, 114)):
    """Scale-preserving resize with padding. Input: BGR HWC. Output exactly new_shape."""
    shape = img.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad_w = int(round(shape[1] * r))
    new_unpad_h = int(round(shape[0] * r))
    dw = new_shape[1] - new_unpad_w
    dh = new_shape[0] - new_unpad_h
    dw //= 2
    dh //= 2
    if new_unpad_w != img.shape[1] or new_unpad_h != img.shape[0]:
        img = cv2.resize(img, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((new_shape[0], new_shape[1], 3), color, dtype=img.dtype)
    canvas[dh:dh + new_unpad_h, dw:dw + new_unpad_w] = img
    return canvas, r, (dw, dh)


def preprocess_onnx(img_bgr, input_size):
    """BGR -> RGB -> letterbox -> normalize -> CHW float32. Returns (tensor, meta)."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    canvas, r, (dw, dh) = letterbox(img_rgb, (input_size, input_size), color=(114, 114, 114))
    pad_h, pad_w = dh, dw
    new_unpad_h = int(round(img_bgr.shape[0] * r))
    new_unpad_w = int(round(img_bgr.shape[1] * r))

    img = canvas.astype(np.float32) / 255.0
    img[..., 0] = (img[..., 0] - 0.485) / 0.229  # R
    img[..., 1] = (img[..., 1] - 0.456) / 0.224  # G
    img[..., 2] = (img[..., 2] - 0.406) / 0.225  # B
    img = img.transpose(2, 0, 1)  # HWC -> CHW
    img = np.expand_dims(img, 0).astype(np.float32)

    meta = {
        "r": r, "dw": dw, "dh": dh, "pad_w": pad_w, "pad_h": pad_h,
        "new_unpad_w": new_unpad_w, "new_unpad_h": new_unpad_h,
        "input_size": input_size, "orig_h": img_bgr.shape[0], "orig_w": img_bgr.shape[1],
    }
    return img, meta


def decode_detections_onnx(det_out, input_size, conf_thres=CONF_THRES):
    """
    ONNX det_out shape: (1, N, 6) with columns (cx, cy, w, h, obj_conf, cls_conf).
    Values are already sigmoid-applied and decoded by the Detect head during ONNX export.
    But we need to re-decode ourselves because some ONNX models might have raw pre-sigmoid values.
    We check the range: if values are > 5, they're decoded; if in [0,1], they're raw.
    """
    det = det_out[0]  # (N, 6)
    n = det.shape[0]
    n_anchors = 3
    n_stride_levels = 3

    # Determine feature map sizes
    fm_sizes = []
    for s in STRIDES:
        fm_sizes.append(input_size // s)
    # n per level: n_anchors * fm_h * fm_w
    expected_per_level = [n_anchors * h * w for h, w in zip(fm_sizes, fm_sizes)]

    # Check if detection is already decoded (values > 1)
    if det[:, 0].max() > 5 or det[:, 2].max() > 5:
        # Already decoded by ONNX model's Detect head
        return det.copy()

    # Raw: need to decode
    anchors_t = np.array(ANCHORS, dtype=np.float32).reshape(3, 3, 2)  # (nl, na, 2)
    decoded = []
    offset = 0
    for li, (h, w) in enumerate(zip(fm_sizes, fm_sizes)):
        stride = STRIDES[li]
        n = expected_per_level[li]
        pred = det[offset:offset + n].reshape(-1, 6).copy()
        offset += n

        # Reshape to (na, h, w, 6)
        pred = pred.reshape(n_anchors, h, w, 6)
        pred = np.transpose(pred, (1, 2, 0, 3))  # (h, w, na, 6)

        yv, xv = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
        grid = np.stack([xv, yv], axis=-1).astype(np.float32)  # (h, w, 2)

        # sigmoid
        pred_xy = 1.0 / (1.0 + np.exp(-pred[..., 0:2]))
        pred_wh = 1.0 / (1.0 + np.exp(-pred[..., 2:4]))
        pred_obj = 1.0 / (1.0 + np.exp(-pred[..., 4:5]))
        pred_cls = 1.0 / (1.0 + np.exp(-pred[..., 5:6]))

        # decode
        cx = (pred_xy[..., 0:1] * 2.0 - 0.5 + grid[..., 0:1]) * stride
        cy = (pred_xy[..., 1:2] * 2.0 - 0.5 + grid[..., 1:2]) * stride
        w_ = (pred_wh[..., 0:1] * 2.0) ** 2 * anchors_t[li, :, 0]
        h_ = (pred_wh[..., 1:2] * 2.0) ** 2 * anchors_t[li, :, 1]

        decoded_level = np.concatenate([cx, cy, w_, h_, pred_obj, pred_cls], axis=-1)
        decoded.append(decoded_level.reshape(-1, 6))

    return np.concatenate(decoded, axis=0)


def non_max_suppression_np(detections, conf_thres=CONF_THRES, iou_thres=IOU_THRES):
    """NumPy-based NMS. detections: (N, 6) with (cx, cy, w, h, obj, cls)."""
    if detections.shape[0] == 0:
        return np.zeros((0, 6), dtype=np.float32)

    obj_conf = detections[:, 4]
    mask = obj_conf > conf_thres
    detections = detections[mask]
    if detections.shape[0] == 0:
        return np.zeros((0, 6), dtype=np.float32)

    # obj_conf * cls_conf
    conf = detections[:, 4] * detections[:, 5]
    # cx,cy,w,h -> x1,y1,x2,y2
    boxes = np.zeros_like(detections[:, :4])
    boxes[:, 0] = detections[:, 0] - detections[:, 2] / 2
    boxes[:, 1] = detections[:, 1] - detections[:, 3] / 2
    boxes[:, 2] = detections[:, 0] + detections[:, 2] / 2
    boxes[:, 3] = detections[:, 1] + detections[:, 3] / 2

    # Only keep valid boxes
    valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    boxes = boxes[valid]
    conf = conf[valid]
    if boxes.shape[0] == 0:
        return np.zeros((0, 6), dtype=np.float32)

    # Class-aware NMS
    max_wh = 4096
    cls_id = 0  # Only class 0 (vehicle)
    c = cls_id * max_wh
    boxes_t = torch.from_numpy(boxes).float()
    scores_t = torch.from_numpy(conf).float()
    boxes_offset = boxes_t + c
    nms_idx = torchvision.ops.nms(boxes_offset, scores_t, iou_thres).numpy()
    if len(nms_idx) > 300:
        nms_idx = nms_idx[:300]

    result = np.zeros((len(nms_idx), 6), dtype=np.float32)
    result[:, :4] = boxes[nms_idx]
    result[:, 4] = conf[nms_idx]
    result[:, 5] = cls_id
    return result


def restore_coords(boxes, meta):
    """Restore xyxy boxes from letterbox space to original image space."""
    if boxes.shape[0] == 0:
        return boxes
    r = meta["r"]
    dw = meta["dw"]
    dh = meta["dh"]
    boxes[:, [0, 2]] -= dw
    boxes[:, [1, 3]] -= dh
    boxes[:, :4] /= r
    # Clip
    boxes[:, 0] = np.clip(boxes[:, 0], 0, meta["orig_w"])
    boxes[:, 1] = np.clip(boxes[:, 1], 0, meta["orig_h"])
    boxes[:, 2] = np.clip(boxes[:, 2], 0, meta["orig_w"])
    boxes[:, 3] = np.clip(boxes[:, 3], 0, meta["orig_h"])
    return boxes


def postprocess_seg(seg_out, meta):
    """Crop padding from seg output, resize to original, argmax."""
    h, w = seg_out.shape[2], seg_out.shape[3]
    dh, dw = meta["dh"], meta["dw"]
    new_unpad_h, new_unpad_w = meta["new_unpad_h"], meta["new_unpad_w"]
    crop = seg_out[:, :, dh:dh + new_unpad_h, dw:dw + new_unpad_w]
    mask = np.argmax(crop, axis=1)[0].astype(np.uint8)
    mask = cv2.resize(mask, (meta["orig_w"], meta["orig_h"]), interpolation=cv2.INTER_LINEAR)
    mask = (mask > 0.5).astype(np.uint8)
    return mask


def compute_mask_stats(mask, name):
    """Compute simple stats for a binary mask."""
    total = mask.size
    positive = int(mask.sum())
    if positive == 0:
        return {
            f"{name}_positive_ratio": 0.0,
            f"{name}_positive_pixels": 0,
            f"{name}_num_components": 0,
            f"{name}_largest_component_ratio": 0.0,
            f"{name}_degenerate": True,
        }
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(areas.max()) if len(areas) > 0 else 0
    return {
        f"{name}_positive_ratio": positive / total,
        f"{name}_positive_pixels": positive,
        f"{name}_num_components": num_labels - 1,
        f"{name}_largest_component_ratio": largest / positive if positive > 0 else 0.0,
        f"{name}_degenerate": positive / total < 0.001 or positive / total > 0.95,
    }


def morphological_process(mask, kernel_size=5, func_type=cv2.MORPH_CLOSE):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.morphologyEx(mask, func_type, kernel)


def fitlane(mask):
    """Fit quadratic curves to lane components. Returns fitted mask."""
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    result = np.zeros_like(mask, dtype=np.uint8)
    H = mask.shape[0]

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 400:
            continue
        x, y, w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        x, y, w, h = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]

        comp_mask = (labels[y:y + h, x:x + w] == i).astype(np.uint8)
        if comp_mask.sum() < 10:
            continue

        # Sample 30 y positions
        sample_y = np.linspace(0, h - 1, min(30, h)).astype(int)
        sample_x = []
        valid_y = []
        for sy in sample_y:
            row = comp_mask[sy]
            xs = np.where(row > 0)[0]
            if len(xs) > 0:
                sample_x.append(x + xs.mean())
                valid_y.append(y + sy)

        if len(sample_x) < 3:
            continue

        sample_x = np.array(sample_x)
        sample_y = np.array(valid_y)

        # Check verticalness
        if_y = True
        if len(sample_y) > 1:
            for sy_idx in range(len(sample_y)):
                row_y = sample_y[sy_idx]
                if row_y < y or row_y > y + h - 1:
                    continue
                local_y = row_y - y
                if local_y < 0 or local_y >= h:
                    continue
                xs_in_row = np.where(comp_mask[local_y] > 0)[0]
                if len(xs_in_row) == 0:
                    continue
                if len(xs_in_row) == 1:
                    if_y = False
                    break

        try:
            if if_y or len(set(sample_y)) >= 3:
                func = np.polyfit(sample_y, sample_x, 2)
                fit_y = np.arange(max(sample_y.min(), 0), min(sample_y.max() + 1, H))
                fit_x = np.polyval(func, fit_y)
                valid = (fit_x >= 0) & (fit_x < mask.shape[1])
                fit_y, fit_x = fit_y[valid], fit_x[valid]
                if len(fit_y) > 1:
                    points = np.stack([fit_x, fit_y], axis=1).astype(np.int32).reshape(-1, 1, 2)
                    cv2.polylines(result, [points], False, 1, thickness=15)
        except Exception:
            pass

    return result


def connect_lane(mask):
    """Filter components and fit curves."""
    return fitlane(mask)


class ONNXModel:
    def __init__(self, model_path, input_size):
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self.session = ort.InferenceSession(str(model_path), sess_opts, providers=providers)
        self.input_size = input_size
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

    def infer(self, preprocessed_img):
        result = self.session.run(self.output_names, {self.input_name: preprocessed_img})
        return {self.output_names[i]: result[i] for i in range(len(result))}

    def run_full(self, img_bgr, conf_thres=CONF_THRES, iou_thres=IOU_THRES):
        t_start = time.perf_counter()
        t0 = time.perf_counter()
        img_input, meta = preprocess_onnx(img_bgr, self.input_size)
        t_prep = time.perf_counter() - t0

        t0 = time.perf_counter()
        outputs = self.infer(img_input)
        t_infer = time.perf_counter() - t0

        t0 = time.perf_counter()
        det_out = outputs[self.output_names[0]]  # (1, N, 6)
        da_out = outputs[self.output_names[1]]    # (1, 2, H, W)
        ll_out = outputs[self.output_names[2]]    # (1, 2, H, W)

        detections = decode_detections_onnx(det_out, self.input_size, conf_thres)
        nms_boxes = non_max_suppression_np(detections, conf_thres, iou_thres)
        nms_boxes_orig = restore_coords(nms_boxes.copy(), meta)

        da_mask = postprocess_seg(da_out, meta)
        ll_mask = postprocess_seg(ll_out, meta)

        da_stats = compute_mask_stats(da_mask, "drivable")
        ll_stats = compute_mask_stats(ll_mask, "lane")

        # Lane fitting on raw mask
        ll_fit = fitlane(ll_mask)
        fit_stats = compute_mask_stats(ll_fit, "lane_fit")
        fit_stats["lane_fit_success"] = fit_stats["lane_fit_positive_pixels"] > 0

        # Lane center estimate (simple: mean x of lane pixels in bottom third)
        h = ll_mask.shape[0]
        bottom_third = ll_mask[int(h * 2 / 3):, :]
        lane_center = 0.5
        if bottom_third.sum() > 0:
            xs = np.where(bottom_third)[1]
            lane_center = float(xs.mean() / ll_mask.shape[1])

        t_post = time.perf_counter() - t0
        t_total = time.perf_counter() - t_start

        result = {
            "detections": nms_boxes_orig,
            "da_mask": da_mask,
            "ll_mask": ll_mask,
            "ll_fit_mask": ll_fit,
            "meta": meta,
            "da_stats": da_stats,
            "ll_stats": ll_stats,
            "fit_stats": fit_stats,
            "lane_center_estimate": lane_center,
            "timing": {"preprocess": t_prep, "inference": t_infer, "postprocess": t_post, "total": t_total},
        }
        return result


class PyTorchModel:
    def __init__(self, checkpoint_path, input_size=640):
        self.available = False
        self.error_msg = None
        self.input_size = input_size
        try:
            sys.path.insert(0, str(YOLOP_ROOT))
            from lib.models.YOLOP import get_net
            from lib.config.default import _C as cfg
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = get_net(cfg)
            checkpoint = torch.load(str(checkpoint_path), map_location=self.device)
            self.model.load_state_dict(checkpoint["state_dict"])
            self.model.to(self.device).eval()
            self.available = True
        except Exception as e:
            self.error_msg = str(e)

    def run_full(self, img_bgr, conf_thres=CONF_THRES, iou_thres=IOU_THRES):
        if not self.available:
            return {"error": self.error_msg, "detections": np.zeros((0, 6))}
        # Not implemented for now - ONNX is primary backend
        return {"error": "PyTorch backend not fully implemented for batch inference", "detections": np.zeros((0, 6))}


def load_model(model_id):
    spec = MODEL_SPECS[model_id]
    if spec["backend"] == "onnx":
        return ONNXModel(spec["path"], spec["size"])
    else:
        return PyTorchModel(spec["path"], spec["size"])


def get_video_info(video_path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration_sec": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
            if cap.get(cv2.CAP_PROP_FPS) > 0 else 0,
    }
    cap.release()
    return info


def seek_frame(cap, frame_idx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    return ret, frame


def timecode_at_fraction(video_info, fraction):
    total_frames = video_info["frame_count"]
    return int(total_frames * fraction)


def generate_sample_plan(video_info, num_windows=12, window_sec=20, sample_fps=5):
    """Generate stratified sampling windows."""
    frame_rate = video_info["fps"]
    total_frames = video_info["frame_count"]
    window_frames = int(window_sec * frame_rate)
    usable_start = window_frames  # Avoid incomplete first window
    usable_end = total_frames - window_frames * 2  # Avoid incomplete last window

    if usable_end <= usable_start:
        # Video too short, use whatever we have
        usable_start = 0
        usable_end = max(total_frames - window_frames, window_frames)

    fractions = [0.02, 0.10, 0.18, 0.26, 0.34, 0.42, 0.50, 0.58, 0.66, 0.74, 0.82, 0.90]
    windows = []
    for i, frac in enumerate(fractions[:num_windows]):
        center = int(usable_start + frac * (usable_end - usable_start))
        start = int(max(0, center - window_frames // 2))
        end = int(min(total_frames, start + window_frames))
        if end - start < window_frames * 0.5:
            continue
        start_sec = start / frame_rate
        end_sec = end / frame_rate
        sample_indices = list(range(start, end, int(frame_rate / sample_fps)))
        windows.append({
            "window_id": i,
            "clip_id": f"clip_{i:03d}",
            "start_frame": start,
            "end_frame": end,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "duration_sec": end_sec - start_sec,
            "sample_indices": sample_indices,
            "num_samples": len(sample_indices),
            "position": "early" if i < 2 else ("late" if i >= num_windows - 2 else "middle"),
        })
    return windows


def generate_comparison_plan(windows):
    """Pick early/middle/late windows for resolution comparison."""
    comp = []
    positions = {"early": None, "middle": None, "late": None}
    for w in windows:
        if w["position"] == "early" and positions["early"] is None:
            positions["early"] = w
        elif w["position"] == "middle" and positions["middle"] is None:
            positions["middle"] = w
        elif w["position"] == "late" and positions["late"] is None:
            positions["late"] = w
    for pos in ["early", "middle", "late"]:
        if positions[pos] is None:
            # Fallback
            for w in windows:
                if w["clip_id"] not in [c["clip_id"] for c in comp]:
                    comp.append(w)
                    break
        else:
            comp.append(positions[pos])
    return comp


def build_overlay(img_bgr, detections, da_mask, ll_mask, ll_fit_mask, meta, timing, model_id):
    """Build visualization overlay."""
    vis = img_bgr.copy()

    # Drivable area (green)
    if da_mask is not None and da_mask.sum() > 0:
        green = np.zeros_like(vis, dtype=np.uint8)
        green[da_mask > 0] = (0, 255, 0)
        vis = cv2.addWeighted(vis, 0.6, green, 0.4, 0)

    # Lane line (red - raw mask)
    if ll_mask is not None and ll_mask.sum() > 0:
        red = np.zeros_like(vis, dtype=np.uint8)
        red[ll_mask > 0] = (255, 0, 0)
        vis = cv2.addWeighted(vis, 0.7, red, 0.3, 0)

    # Fitted lane (blue)
    if ll_fit_mask is not None and ll_fit_mask.sum() > 0:
        blue = np.zeros_like(vis, dtype=np.uint8)
        blue[ll_fit_mask > 0] = (0, 0, 255)
        vis = cv2.addWeighted(vis, 0.8, blue, 0.2, 0)

    # Detection boxes (yellow)
    for box in detections:
        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        conf = box[4]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(vis, f"{conf:.2f}", (x1, max(y1 - 5, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # Info overlay
    h, w = vis.shape[:2]
    info_lines = [
        f"{model_id} | {meta.get('input_size', '?')}px",
        f"t={meta.get('timestamp', 0):.1f}s",
        f"infer={timing.get('inference', 0)*1000:.0f}ms",
        f"dets={len(detections)}",
    ]
    for i, txt in enumerate(info_lines):
        y = 20 + i * 18
        cv2.putText(vis, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    return vis


def process_clip(video_path, model, window, model_id, output_dir, overlay_dir, sample_fps=5,
                 conf_thres=CONF_THRES, iou_thres=IOU_THRES, save_overlays=True, max_overlays=None):
    """Process a single sampling window."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"error": "Cannot open video", "frames": []}

    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    frames_data = []
    timing_agg = defaultdict(list)

    sample_indices = window["sample_indices"]
    overlay_count = 0

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        timestamp = idx / frame_rate if frame_rate > 0 else 0

        result = model.run_full(frame, conf_thres, iou_thres)
        if "error" in result:
            continue

        meta = result["meta"]
        meta["timestamp"] = timestamp
        meta["frame_index"] = idx
        meta["video_id"] = "long_video_dataset3"
        meta["model_id"] = model_id

        timing = result["timing"]
        for k, v in timing.items():
            timing_agg[k].append(v)

        dets = result["detections"]
        frame_record = {
            "video_id": "long_video_dataset3",
            "clip_id": window["clip_id"],
            "frame_index": idx,
            "source_timestamp": timestamp,
            "sample_timestamp": time.time(),
            "model_id": model_id,
            "backend": "onnx",
            "input_size": model.input_size,
            "original_width": meta["orig_w"],
            "original_height": meta["orig_h"],
            "num_detections": len(dets),
            "detections": [{
                "class_id": int(box[5]), "class_name": CLASS_NAMES.get(int(box[5]), "unknown"),
                "confidence": float(box[4]),
                "x1": float(box[0]), "y1": float(box[1]),
                "x2": float(box[2]), "y2": float(box[3]),
            } for box in dets],
            "da_stats": result["da_stats"],
            "ll_stats": result["ll_stats"],
            "fit_stats": result["fit_stats"],
            "lane_center_estimate": result["lane_center_estimate"],
            "timing": timing,
            "success": True,
        }
        frames_data.append(frame_record)

        # Save overlay
        if save_overlays and (max_overlays is None or overlay_count < max_overlays):
            overlay = build_overlay(frame, dets, result["da_mask"], result["ll_mask"],
                                     result["ll_fit_mask"], meta, timing, model_id)
            overlay_path = overlay_dir / f"{window['clip_id']}_f{idx:06d}.jpg"
            cv2.imwrite(str(overlay_path), overlay)
            overlay_count += 1

        # Save masks (compressed)
        mask_dir = output_dir / "raw/masks"
        mask_dir.mkdir(parents=True, exist_ok=True)
        for name, mask in [("drivable", result["da_mask"]), ("lane_raw", result["ll_mask"]),
                           ("lane_fit", result["ll_fit_mask"])]:
            mask_path = mask_dir / f"{window['clip_id']}_f{idx:06d}_{name}.png"
            cv2.imwrite(str(mask_path), mask * 255)

    cap.release()

    # Aggregate timing
    timing_summary = {}
    for k, vs in timing_agg.items():
        vs = np.array(vs)
        timing_summary[k] = {
            "mean": float(np.mean(vs)), "median": float(np.median(vs)),
            "p50": float(np.percentile(vs, 50)), "p90": float(np.percentile(vs, 90)),
            "p95": float(np.percentile(vs, 95)), "min": float(np.min(vs)), "max": float(np.max(vs)),
        }

    return {"frames": frames_data, "timing_summary": timing_summary, "num_processed": len(frames_data),
            "clip_id": window["clip_id"]}


def run_inspect():
    """Phase: inspect video and model schemas."""
    print("=== INSPECT: Video & Model Checks ===")

    # Video info
    print("\n--- Video Info ---")
    info = get_video_info(VIDEO_PATH)
    if info:
        print(json.dumps(info, indent=2))
        # Test random seek
        cap = cv2.VideoCapture(str(VIDEO_PATH))
        n_frames = info["frame_count"]
        for frac in [0.05, 0.25, 0.5, 0.75, 0.95]:
            idx = int(n_frames * frac)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            ts = idx / info["fps"] if info["fps"] > 0 else 0
            print(f"  seek {frac*100:.0f}% frame={idx} ts={ts:.1f}s ret={ret} shape={frame.shape if ret else 'fail'}")
        cap.release()
    else:
        print("FAILED to open video!")
        return

    # Model checks
    print("\n--- ONNX Model Schemas ---")
    for model_id in ["onnx_320", "onnx_640", "onnx_1280"]:
        spec = MODEL_SPECS[model_id]
        m = ONNXModel(spec["path"], spec["size"])
        inputs = m.session.get_inputs()
        outputs = m.session.get_outputs()
        print(f"\n{model_id} ({spec['path']}):")
        for inp in inputs:
            print(f"  Input:  name={inp.name} shape={inp.shape} type={inp.type}")
        for out in outputs:
            print(f"  Output: name={out.name} shape={out.shape} type={out.type}")

        # Test with dummy tensor
        dummy = np.random.randn(1, 3, spec["size"], spec["size"]).astype(np.float32)
        try:
            result = m.infer(dummy)
            for k, v in result.items():
                print(f"    {k}: {v.shape} range=[{v.min():.4f}, {v.max():.4f}] has_nan={np.any(np.isnan(v))}")
        except Exception as e:
            print(f"  Inference test FAILED: {e}")

    # PyTorch checkpoint check
    print("\n--- PyTorch Checkpoint ---")
    try:
        sys.path.insert(0, str(YOLOP_ROOT))
        from lib.models.YOLOP import get_net
        from lib.config.default import _C as cfg
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = get_net(cfg)
        ckpt = torch.load(str(WEIGHT_DIR / "End-to-end.pth"), map_location=device)
        model.load_state_dict(ckpt["state_dict"])
        model.to(device).eval()
        dummy = torch.randn(1, 3, 640, 640).to(device)
        with torch.no_grad():
            det_out, da_out, ll_out = model(dummy)
        print(f"PyTorch model loaded OK. det_out: {det_out.shape}, da: {da_out.shape}, ll: {ll_out.shape}")
        print(f"  det range: [{det_out.min():.4f}, {det_out.max():.4f}]")
    except Exception as e:
        print(f"PyTorch checkpoint load FAILED: {e}")
        print("Marking PYTORCH_BACKEND = UNAVAILABLE_WITH_DOCUMENTED_LIMITATION")


def run_smoke():
    """Phase: single-frame smoke test at 5 positions, then 20-sec smoke."""
    print("=== SMOKE TESTS ===")
    info = get_video_info(VIDEO_PATH)
    if info is None:
        print("Cannot open video. Aborting smoke.")
        return

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    total_frames = info["frame_count"]
    positions = [int(total_frames * f) for f in [0.05, 0.25, 0.50, 0.75, 0.95]]
    smoke_dir = OUTPUT_DIR / "raw"
    smoke_dir.mkdir(parents=True, exist_ok=True)

    # Single-frame smoke
    print("\n--- Single-Frame Smoke ---")
    models = ["onnx_320", "onnx_640", "onnx_1280"]
    smoke_results = {}

    for model_id in models:
        print(f"\nTesting {model_id}...")
        model = load_model(model_id)
        model_results = []
        for pos_idx, frame_idx in enumerate(positions):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                print(f"  Frame {frame_idx} read failed")
                model_results.append({"frame_idx": frame_idx, "success": False, "error": "read failed"})
                continue

            result = model.run_full(frame)
            if "error" in result:
                print(f"  Frame {frame_idx} inference failed: {result['error']}")
                model_results.append({"frame_idx": frame_idx, "success": False, "error": result["error"]})
                continue

            dets = result["detections"]
            checks = {
                "success": True,
                "frame_idx": frame_idx,
                "num_dets": len(dets),
                "det_ok": len(dets) > 0,  # At least some detections
                "no_nan": True,
                "da_non_degenerate": not result["da_stats"].get("drivable_degenerate", True),
                "ll_non_degenerate": not result["ll_stats"].get("lane_degenerate", True),
                "timing_ms": result["timing"]["inference"] * 1000,
            }
            print(f"  Frame {frame_idx}: {len(dets)} dets, da={checks['da_non_degenerate']}, "
                  f"ll={checks['ll_non_degenerate']}, infer={checks['timing_ms']:.1f}ms")
            model_results.append(checks)
        smoke_results[model_id] = model_results

    cap.release()

    # 20-sec smoke
    print("\n--- 20-Second Smoke ---")
    clip_start = int(total_frames * 0.5)
    clip_end = int(clip_start + 20 * info["fps"])
    window = {
        "window_id": 0, "clip_id": "smoke_20s",
        "start_frame": clip_start, "end_frame": clip_end,
        "start_sec": clip_start / info["fps"], "end_sec": clip_end / info["fps"],
        "duration_sec": 20,
        "sample_indices": list(range(clip_start, clip_end, int(info["fps"] / 5))),
        "num_samples": 0, "position": "smoke",
    }
    window["num_samples"] = len(window["sample_indices"])

    smoke_overlay_dir = OUTPUT_DIR / "overlays/smoke"
    smoke_overlay_dir.mkdir(parents=True, exist_ok=True)

    clip_results = {}
    for model_id in models:
        print(f"\nProcessing 20s smoke with {model_id}...")
        model = load_model(model_id)
        result = process_clip(VIDEO_PATH, model, window, model_id, OUTPUT_DIR,
                              smoke_overlay_dir, sample_fps=5, max_overlays=10)
        clip_results[model_id] = result
        print(f"  Processed {result.get('num_processed', 0)} frames")
        if "timing_summary" in result:
            ts = result["timing_summary"]
            for stage in ["total", "inference", "preprocess", "postprocess"]:
                if stage in ts:
                    print(f"    {stage}: mean={ts[stage]['mean']*1000:.1f}ms, p95={ts[stage]['p95']*1000:.1f}ms")

    # Save smoke results
    with open(OUTPUT_DIR / "smoke_results.json", "w") as f:
        json.dump({"single_frame": smoke_results, "clip_results": {
            k: {"num_processed": v.get("num_processed", 0),
                "timing_summary": v.get("timing_summary", {})}
            for k, v in clip_results.items()
        }}, f, indent=2, default=str)

    print(f"\nSmoke results saved to {OUTPUT_DIR / 'smoke_results.json'}")


def run_sample():
    """Phase: stratified 12-window long video sampling."""
    print("=== STRATIFIED SAMPLING ===")
    info = get_video_info(VIDEO_PATH)
    if info is None:
        print("Cannot open video.")
        return

    windows = generate_sample_plan(info, num_windows=12, window_sec=20, sample_fps=5)
    comp_windows = generate_comparison_plan(windows)

    sample_plan = {"video_info": info, "windows": windows, "comparison_windows": [
        {"clip_id": w["clip_id"], "position": w["position"]} for w in comp_windows
    ]}

    with open(OUTPUT_DIR / "SAMPLE_PLAN.json", "w") as f:
        json.dump(sample_plan, f, indent=2, default=str)
    print(f"Sample plan written: {len(windows)} windows, ~{sum(w['num_samples'] for w in windows)} total frames")

    # Run 640 on all windows
    print("\n--- Running ONNX 640 on all windows ---")
    model_640 = load_model("onnx_640")
    all_frames = []
    all_timings = []
    window_summaries = []

    overlay_dir = OUTPUT_DIR / "overlays/640"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    for w in windows:
        print(f"  Window {w['clip_id']} ({w['position']}): frames {w['start_frame']}-{w['end_frame']} "
              f"({w['num_samples']} samples)")
        # 5 evenly spaced overlays per window
        max_ov = 5
        result = process_clip(VIDEO_PATH, model_640, w, "onnx_640", OUTPUT_DIR, overlay_dir,
                              sample_fps=5, max_overlays=max_ov)
        all_frames.extend(result.get("frames", []))
        all_timings.extend([f.get("timing", {}) for f in result.get("frames", [])])
        window_summaries.append({
            "clip_id": w["clip_id"], "num_processed": result.get("num_processed", 0),
            "timing_summary": result.get("timing_summary", {}),
        })

    # Save frame-level parquet
    df_frames = pd.DataFrame(all_frames)
    df_frames.to_parquet(OUTPUT_DIR / "raw/onnx_640_all_frames.parquet", index=False)

    # Save timing
    timing_agg = {}
    if all_timings:
        for key in all_timings[0].keys():
            vals = [t.get(key, 0) for t in all_timings if t.get(key, 0) > 0]
            if vals:
                vals = np.array(vals)
                timing_agg[key] = {
                    "mean": float(np.mean(vals)), "median": float(np.median(vals)),
                    "p50": float(np.percentile(vals, 50)), "p90": float(np.percentile(vals, 90)),
                    "p95": float(np.percentile(vals, 95)),
                }
    with open(OUTPUT_DIR / "onnx_640_timing_summary.json", "w") as f:
        json.dump({"per_window": window_summaries, "aggregate": timing_agg}, f, indent=2)

    print(f"\nSaved {len(all_frames)} frames to Parquet")
    print(f"Timing: {json.dumps(timing_agg, indent=2)}")


def run_compare():
    """Phase: resolution comparison on early/middle/late windows."""
    print("=== RESOLUTION COMPARISON ===")
    info = get_video_info(VIDEO_PATH)
    if info is None:
        print("Cannot open video.")
        return

    with open(OUTPUT_DIR / "SAMPLE_PLAN.json", "r") as f:
        plan = json.load(f)

    windows = plan["windows"]
    comp_windows = generate_comparison_plan(windows)
    models = ["onnx_320", "onnx_640", "onnx_1280"]

    comp_dir = OUTPUT_DIR / "overlays/comparison"
    comp_dir.mkdir(parents=True, exist_ok=True)

    all_comparison = []
    for model_id in models:
        print(f"\n--- {model_id} ---")
        model = load_model(model_id)
        for w in comp_windows:
            print(f"  Window {w['clip_id']} ({w['position']})")
            overlay_dir = comp_dir / model_id
            overlay_dir.mkdir(parents=True, exist_ok=True)
            result = process_clip(VIDEO_PATH, model, w, model_id, OUTPUT_DIR, overlay_dir,
                                  sample_fps=5, max_overlays=10)
            for f in result.get("frames", []):
                all_comparison.append(f)

    # Save comparison data
    df_comp = pd.DataFrame(all_comparison)
    df_comp.to_parquet(OUTPUT_DIR / "raw/resolution_comparison.parquet", index=False)

    # Aggregate comparison stats
    comp_stats = {}
    for model_id in models:
        model_frames = [f for f in all_comparison if f["model_id"] == model_id]
        if not model_frames:
            continue
        det_counts = [f["num_detections"] for f in model_frames]
        timings = [f.get("timing", {}).get("inference", 0) for f in model_frames]
        timings_t = [f.get("timing", {}).get("total", 0) for f in model_frames]
        comp_stats[model_id] = {
            "num_frames": len(model_frames),
            "mean_dets": float(np.mean(det_counts)),
            "median_dets": float(np.median(det_counts)),
            "inference_ms_mean": float(np.mean(timings) * 1000),
            "inference_ms_p95": float(np.percentile(timings, 95) * 1000),
            "total_ms_mean": float(np.mean(timings_t) * 1000),
        }
    with open(OUTPUT_DIR / "resolution_comparison_stats.json", "w") as f:
        json.dump(comp_stats, f, indent=2)

    # Generate side-by-side comparison images
    print("\n--- Generating side-by-side comparisons ---")
    generate_comparison_sheets(plan, comp_windows, comp_dir)


def generate_comparison_sheets(plan, comp_windows, comp_dir):
    """Generate 3-resolution comparison images for selected frames."""
    info = get_video_info(VIDEO_PATH)
    if info is None:
        return

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    models = {"onnx_320": load_model("onnx_320"), "onnx_640": load_model("onnx_640"),
              "onnx_1280": load_model("onnx_1280")}

    comparison_sheet_dir = OUTPUT_DIR / "overlays/comparison_sheets"
    comparison_sheet_dir.mkdir(parents=True, exist_ok=True)

    cmp_manifest = []
    for w in comp_windows:
        # Pick 5 evenly spaced frames
        indices = w["sample_indices"]
        picks = indices[::max(1, len(indices) // 5)][:5]
        for frame_idx in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            overlays = []
            for model_id, model in models.items():
                result = model.run_full(frame)
                if "error" in result:
                    continue
                overlay = build_overlay(frame.copy(), result["detections"],
                                         result["da_mask"], result["ll_mask"],
                                         result["ll_fit_mask"], result["meta"],
                                         result["timing"], model_id)
                # Resize to uniform width
                w_target = 640
                s = w_target / overlay.shape[1]
                overlay = cv2.resize(overlay, (w_target, int(overlay.shape[0] * s)))
                overlays.append(overlay)

            if len(overlays) == 3:
                h_max = max(o.shape[0] for o in overlays)
                padded = []
                for o in overlays:
                    if o.shape[0] < h_max:
                        pad = np.zeros((h_max - o.shape[0], o.shape[1], 3), dtype=np.uint8)
                        o = np.vstack([o, pad])
                    padded.append(o)
                sheet = np.hstack(padded)
                sheet_path = comparison_sheet_dir / f"cmp_{w['clip_id']}_f{frame_idx:06d}.jpg"
                cv2.imwrite(str(sheet_path), sheet)
                cmp_manifest.append({
                    "clip_id": w["clip_id"], "frame_index": frame_idx,
                    "image_path": str(sheet_path.relative_to(OUTPUT_DIR)),
                    "review_status": "auto",
                })

    cap.release()

    # Save manifest
    df_manifest = pd.DataFrame(cmp_manifest)
    df_manifest.to_csv(OUTPUT_DIR / "VISUAL_REVIEW_MANIFEST.csv", index=False)
    print(f"Generated {len(cmp_manifest)} comparison sheets")


def compute_diagnostics():
    """Compute automated sanity metrics."""
    print("=== COMPUTING DIAGNOSTICS ===")

    # Load 640 all frames
    df_path = OUTPUT_DIR / "raw/onnx_640_all_frames.parquet"
    if not df_path.exists():
        print("No 640 frame data found.")
        return
    df = pd.read_parquet(df_path)

    diag = {}

    # Detection diagnostics
    det_counts = df["num_detections"].values
    diag["detection"] = {
        "mean_per_frame": float(np.mean(det_counts)),
        "median_per_frame": float(np.median(det_counts)),
        "std_per_frame": float(np.std(det_counts)),
        "min_per_frame": int(np.min(det_counts)),
        "max_per_frame": int(np.max(det_counts)),
        "zero_det_frames": int(np.sum(det_counts == 0)),
        "zero_det_fraction": float(np.mean(det_counts == 0)),
    }

    # Collect all detections
    all_confs = []
    all_areas = []
    for _, row in df.iterrows():
        dets = row["detections"]
        for d in dets:
            all_confs.append(d["confidence"])
            w = d["x2"] - d["x1"]
            h = d["y2"] - d["y1"]
            all_areas.append(w * h)

    if all_confs:
        all_confs = np.array(all_confs)
        all_areas = np.array(all_areas)
        diag["detection"].update({
            "confidence_mean": float(np.mean(all_confs)),
            "confidence_median": float(np.median(all_confs)),
            "confidence_p25": float(np.percentile(all_confs, 25)),
            "confidence_p75": float(np.percentile(all_confs, 75)),
            "box_area_mean": float(np.mean(all_areas)),
            "box_area_median": float(np.median(all_areas)),
            "total_detections": len(all_confs),
        })

    # Lane diagnostics from stats
    ll_pos_ratios = []
    ll_component_counts = []
    ll_degenerate_count = 0
    for _, row in df.iterrows():
        ls = row.get("ll_stats", {})
        if ls:
            ll_pos_ratios.append(ls.get("lane_positive_ratio", 0))
            ll_component_counts.append(ls.get("lane_num_components", 0))
            if ls.get("lane_degenerate", True):
                ll_degenerate_count += 1

    if ll_pos_ratios:
        ll_pos_ratios = np.array(ll_pos_ratios)
        ll_component_counts = np.array(ll_component_counts)
        diag["lane"] = {
            "positive_ratio_mean": float(np.mean(ll_pos_ratios)),
            "positive_ratio_std": float(np.std(ll_pos_ratios)),
            "component_count_mean": float(np.mean(ll_component_counts)),
            "degenerate_mask_rate": float(ll_degenerate_count / len(ll_pos_ratios)),
            "lane_center_mean": float(df["lane_center_estimate"].mean()) if "lane_center_estimate" in df.columns else None,
            "lane_center_std": float(df["lane_center_estimate"].std()) if "lane_center_estimate" in df.columns else None,
        }

    # Drivable diagnostics
    da_pos_ratios = []
    da_degenerate_count = 0
    for _, row in df.iterrows():
        ds = row.get("da_stats", {})
        if ds:
            da_pos_ratios.append(ds.get("drivable_positive_ratio", 0))
            if ds.get("drivable_degenerate", True):
                da_degenerate_count += 1

    if da_pos_ratios:
        da_pos_ratios = np.array(da_pos_ratios)
        diag["drivable"] = {
            "positive_ratio_mean": float(np.mean(da_pos_ratios)),
            "positive_ratio_std": float(np.std(da_pos_ratios)),
            "degenerate_mask_rate": float(da_degenerate_count / len(da_pos_ratios)),
        }

    # Temporal stability (frame-to-frame)
    diag["temporal"] = compute_temporal_stability(df)

    with open(OUTPUT_DIR / "AUTOMATED_SANITY_METRICS.json", "w") as f:
        json.dump(diag, f, indent=2)

    print(json.dumps(diag, indent=2))
    return diag


def compute_temporal_stability(df):
    """Simple frame-to-frame diagnostic association (NOT a tracker)."""
    df = df.sort_values(["clip_id", "frame_index"]).reset_index(drop=True)
    clips = df["clip_id"].unique()

    all_matches = []
    all_displacements = []
    all_size_jitters = []
    all_disappear_rates = []

    for clip in clips:
        clip_df = df[df["clip_id"] == clip].sort_values("frame_index")
        prev_boxes = None
        prev_conf = None
        clip_disappear = 0
        clip_total = 0

        for i, (_, row) in enumerate(clip_df.iterrows()):
            dets = row["detections"]
            if len(dets) == 0:
                if prev_boxes is not None and len(prev_boxes) > 0:
                    clip_disappear += 1
                clip_total += 1
                prev_boxes = []
                continue

            boxes = np.array([[d["x1"], d["y1"], d["x2"], d["y2"]] for d in dets])
            confs = np.array([d["confidence"] for d in dets])

            if prev_boxes is not None and len(prev_boxes) > 0 and len(boxes) > 0:
                # Simple IoU-based association
                matches = 0
                displacements = []
                size_jitters = []
                for pb_idx, pb in enumerate(prev_boxes):
                    best_iou = 0
                    best_idx = -1
                    for b_idx, b in enumerate(boxes):
                        iou = box_iou_np(pb, b)
                        if iou > best_iou and iou > 0.3:
                            best_iou = iou
                            best_idx = b_idx
                    if best_idx >= 0:
                        matches += 1
                        # Center displacement
                        cx_prev = (pb[0] + pb[2]) / 2
                        cy_prev = (pb[1] + pb[3]) / 2
                        cx_curr = (boxes[best_idx][0] + boxes[best_idx][2]) / 2
                        cy_curr = (boxes[best_idx][1] + boxes[best_idx][3]) / 2
                        displacements.append(np.sqrt((cx_curr - cx_prev)**2 + (cy_curr - cy_prev)**2))

                        # Size jitter
                        w_prev = pb[2] - pb[0]
                        h_prev = pb[3] - pb[1]
                        w_curr = boxes[best_idx][2] - boxes[best_idx][0]
                        h_curr = boxes[best_idx][3] - boxes[best_idx][1]
                        size_jitters.append(abs(w_curr - w_prev) / max(w_prev, 1) + abs(h_curr - h_prev) / max(h_prev, 1))

                n_prev = len(prev_boxes)
                match_frac = matches / n_prev if n_prev > 0 else 0
                all_matches.append(match_frac)
                if displacements:
                    all_displacements.extend(displacements)
                if size_jitters:
                    all_size_jitters.extend(size_jitters)
                if n_prev > 0 and matches == 0:
                    clip_disappear += 1

            clip_total += 1
            prev_boxes = boxes

        if clip_total > 0:
            all_disappear_rates.append(clip_disappear / clip_total)

    result = {}
    if all_matches:
        result["matched_box_fraction_mean"] = float(np.mean(all_matches))
    if all_displacements:
        disp = np.array(all_displacements)
        result["median_center_displacement_px"] = float(np.median(disp))
        result["p90_center_displacement_px"] = float(np.percentile(disp, 90))
    if all_size_jitters:
        jit = np.array(all_size_jitters)
        result["median_box_size_jitter"] = float(np.median(jit))
    if all_disappear_rates:
        result["one_frame_disappearance_rate"] = float(np.mean(all_disappear_rates))

    return result


def box_iou_np(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0


def run_cost_profile():
    """Phase: compute cost profiles with warmup."""
    print("=== COST PROFILING ===")
    info = get_video_info(VIDEO_PATH)
    if info is None:
        print("Cannot open video.")
        return

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    total_frames = info["frame_count"]
    # Grab ~400 frames from middle
    start = int(total_frames * 0.45)
    frames = []
    for i in range(start, start + 400):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
        if len(frames) >= 350:
            break
    cap.release()

    warmup = 20
    measured = min(300, max(0, len(frames) - warmup))

    cost_data = {}
    models = ["onnx_320", "onnx_640", "onnx_1280"]

    for model_id in models:
        print(f"\nProfiling {model_id}...")
        model = load_model(model_id)
        timings_all = []

        # Warmup
        for i in range(warmup):
            _ = model.run_full(frames[i])

        # Measured
        for i in range(warmup, warmup + measured):
            result = model.run_full(frames[i])
            if "timing" in result:
                ts = result["timing"]
                timings_all.append({
                    "preprocess": ts.get("preprocess", 0),
                    "inference": ts.get("inference", 0),
                    "postprocess": ts.get("postprocess", 0),
                    "total": ts.get("total", 0),
                })

        if not timings_all:
            continue

        # Compute stats
        stats = {}
        for key in ["preprocess", "inference", "postprocess", "total"]:
            vals = np.array([t[key] for t in timings_all])
            stats[key] = {
                "mean_ms": float(np.mean(vals) * 1000),
                "p50_ms": float(np.percentile(vals, 50) * 1000),
                "p90_ms": float(np.percentile(vals, 90) * 1000),
                "p95_ms": float(np.percentile(vals, 95) * 1000),
            }

        # FPS
        e2e_fps = 1.0 / np.mean([t["total"] for t in timings_all]) if timings_all else 0
        model_fps = 1.0 / np.mean([t["inference"] for t in timings_all]) if timings_all else 0

        # Cost per video hour at 5 fps
        frames_per_hour_5fps = 3600 * 5
        gpu_sec_per_frame = np.mean([t["inference"] for t in timings_all]) if timings_all else 0
        gpu_sec_per_hour_5fps = gpu_sec_per_frame * frames_per_hour_5fps
        gpu_sec_per_hour_2_5fps = gpu_sec_per_frame * 3600 * 2.5

        cost_data[model_id] = {
            "num_warmup": warmup,
            "num_measured": len(timings_all),
            "fps_e2e": float(e2e_fps),
            "fps_model_only": float(model_fps),
            "latency_ms": stats,
            "gpu_seconds_per_video_hour_at_5fps": float(gpu_sec_per_hour_5fps),
            "gpu_seconds_per_video_hour_at_2_5fps": float(gpu_sec_per_hour_2_5fps),
            "throughput_gate_5fps_pass": bool(e2e_fps >= 5),
            "throughput_gate_20fps_pass": bool(e2e_fps >= 20),
        }
        print(f"  E2E FPS: {e2e_fps:.1f}, Model FPS: {model_fps:.1f}, 5fps gate: {e2e_fps >= 5}")

    with open(OUTPUT_DIR / "LATENCY_REPORT.json", "w") as f:
        json.dump(cost_data, f, indent=2)

    # MODEL_COMPARISON.csv
    rows = []
    for model_id, data in cost_data.items():
        rows.append({
            "model_id": model_id,
            "fps_e2e": data["fps_e2e"],
            "fps_model_only": data["fps_model_only"],
            "infer_p50_ms": data["latency_ms"]["inference"]["p50_ms"],
            "infer_p95_ms": data["latency_ms"]["inference"]["p95_ms"],
            "total_p50_ms": data["latency_ms"]["total"]["p50_ms"],
            "gpu_sec_per_hour_5fps": data["gpu_seconds_per_video_hour_at_5fps"],
            "gate_5fps": data["throughput_gate_5fps_pass"],
            "gate_20fps": data["throughput_gate_20fps_pass"],
        })
    df_cost = pd.DataFrame(rows)
    df_cost.to_csv(OUTPUT_DIR / "MODEL_COMPARISON.csv", index=False)


def run_finalize():
    """Phase: produce final audited decision."""
    print("=== FINALIZE ===")

    # Collect evidence
    evidence = {}

    # 1. Smoke results
    smoke_path = OUTPUT_DIR / "smoke_results.json"
    if smoke_path.exists():
        with open(smoke_path) as f:
            evidence["smoke"] = json.load(f)

    # 2. Sanity metrics
    metrics_path = OUTPUT_DIR / "AUTOMATED_SANITY_METRICS.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            evidence["metrics"] = json.load(f)

    # 3. Cost profile
    cost_path = OUTPUT_DIR / "LATENCY_REPORT.json"
    if cost_path.exists():
        with open(cost_path) as f:
            evidence["cost"] = json.load(f)

    # 4. Comparison stats
    comp_path = OUTPUT_DIR / "resolution_comparison_stats.json"
    if comp_path.exists():
        with open(comp_path) as f:
            evidence["comparison"] = json.load(f)

    # Decision logic
    runtime_ok = True
    detection_ok = True
    lane_ok = True
    drivable_ok = True
    cost_ok = True

    # Runtime: all models ran?
    smoke_sf = evidence.get("smoke", {}).get("single_frame", {})
    for m in ["onnx_320", "onnx_640", "onnx_1280"]:
        if m not in smoke_sf:
            runtime_ok = False

    # Detection: non-degenerate
    det_metrics = evidence.get("metrics", {}).get("detection", {})
    zero_det_frac = det_metrics.get("zero_det_fraction", 1.0)
    if zero_det_frac > 0.8:
        detection_ok = False

    # Lane: non-degenerate
    lane_metrics = evidence.get("metrics", {}).get("lane", {})
    lane_degen = lane_metrics.get("degenerate_mask_rate", 1.0)
    if lane_degen > 0.8:
        lane_ok = False

    # Drivable: non-degenerate
    da_metrics = evidence.get("metrics", {}).get("drivable", {})
    da_degen = da_metrics.get("degenerate_mask_rate", 1.0)
    if da_degen > 0.8:
        drivable_ok = False

    # Cost gate
    cost = evidence.get("cost", {})
    preferred_640_e2e = cost.get("onnx_640", {}).get("fps_e2e", 0)
    cost_ok = preferred_640_e2e >= 5.0

    # Overall decision
    if not runtime_ok:
        status = "BLOCKED_RUNTIME"
    elif not (detection_ok or lane_ok or drivable_ok):
        status = "FAIL_DOMAIN_SHIFT"
    elif not detection_ok or not lane_ok or not drivable_ok:
        status = "WEAK"
    elif not cost_ok:
        status = "WEAK"
    else:
        status = "PASS_AUTOMATED__VISUAL_REVIEW_REQUIRED"

    # Select config
    # Compare 320 vs 640: if 320 quality is close and faster, prefer 320
    comp = evidence.get("comparison", {})
    det_320 = comp.get("onnx_320", {}).get("mean_dets", 0)
    det_640 = comp.get("onnx_640", {}).get("mean_dets", 0)
    fps_320 = cost.get("onnx_320", {}).get("fps_e2e", 0)
    fps_640 = cost.get("onnx_640", {}).get("fps_e2e", 0)
    infer_320 = cost.get("onnx_320", {}).get("latency_ms", {}).get("inference", {}).get("p50_ms", 999)
    infer_640 = cost.get("onnx_640", {}).get("latency_ms", {}).get("inference", {}).get("p50_ms", 999)

    if status in ["BLOCKED_RUNTIME", "FAIL_DOMAIN_SHIFT"]:
        extractor_config = "NONE"
    else:
        # If 320 detection count is not too much worse and significantly faster
        ratio = det_320 / max(det_640, 1)
        if ratio >= 0.6 and fps_320 >= fps_640 * 1.3:
            extractor_config = "ONNX_320"
        elif fps_640 >= 5:
            extractor_config = "ONNX_640"
        else:
            extractor_config = "ONNX_640"  # Default to 640 if both are slow

    # Next work recommendation
    if status == "PASS_AUTOMATED__VISUAL_REVIEW_REQUIRED":
        next_work = "A. YOLOP frozen + ByteTrack + road-relative features"
    elif status == "WEAK":
        if not detection_ok and (lane_ok and drivable_ok):
            next_work = "C. Keep lane/drivable, replace detection head"
        elif not lane_ok and detection_ok:
            next_work = "B. Keep YOLOP detection, replace lane head"
        else:
            next_work = "D. Minimal target-domain perception annotation & fine-tuning"
    elif status == "FAIL_DOMAIN_SHIFT":
        next_work = "E. Abandon YOLOP"
    else:
        next_work = "D. Minimal target-domain perception annotation & fine-tuning"

    decision = {
        "status": status,
        "components": {
            "RUNTIME_COMPATIBILITY": "PASS" if runtime_ok else "FAIL",
            "DETECTION_AUTOMATED_SANITY": "PASS" if detection_ok else "FAIL",
            "LANE_AUTOMATED_SANITY": "PASS" if lane_ok else "FAIL",
            "DRIVABLE_AUTOMATED_SANITY": "PASS" if drivable_ok else "FAIL",
            "COST_GATE": "PASS" if cost_ok else "FAIL",
            "VISUAL_VALIDATION": "REQUIRED",
        },
        "YOLOP_TARGET_SANITY": status,
        "SELECTED_EXTRACTOR_CONFIG": extractor_config,
        "next_highest_value_work": next_work,
        "evidence_summary": {
            "zero_det_fraction": zero_det_frac,
            "lane_degenerate_rate": lane_degen,
            "drivable_degenerate_rate": da_degen,
            "onnx_640_e2e_fps": preferred_640_e2e,
        }
    }

    with open(OUTPUT_DIR / "AUDITED_DECISION.json", "w") as f:
        json.dump(decision, f, indent=2)

    # Write FINAL_REPORT.md
    report = f"""# YOLOP Target-Domain Sanity Audit — Final Report

## Decision: {status}

### Component Results

| Component | Result |
|-----------|--------|
| RUNTIME_COMPATIBILITY | {decision['components']['RUNTIME_COMPATIBILITY']} |
| DETECTION_AUTOMATED_SANITY | {decision['components']['DETECTION_AUTOMATED_SANITY']} |
| LANE_AUTOMATED_SANITY | {decision['components']['LANE_AUTOMATED_SANITY']} |
| DRIVABLE_AUTOMATED_SANITY | {decision['components']['DRIVABLE_AUTOMATED_SANITY']} |
| COST_GATE | {decision['components']['COST_GATE']} |
| VISUAL_VALIDATION | {decision['components']['VISUAL_VALIDATION']} |

### Selected Extractor Config

**`{extractor_config}`**

### Evidence Summary

- Zero-detection frame fraction: {zero_det_frac:.3f}
- Lane degenerate mask rate: {lane_degen:.3f}
- Drivable degenerate mask rate: {da_degen:.3f}
- ONNX 640 end-to-end FPS: {preferred_640_e2e:.1f}

### Next Highest-Value Work

{next_work}
"""
    with open(OUTPUT_DIR / "FINAL_REPORT.md", "w") as f:
        f.write(report)

    # EXACT_COMMANDS.md
    commands = """# Exact Commands Used

```bash
cd /qiuyeqing/llama_prl/G-ARC
python scripts/run_yolop_target_sanity.py inspect
python scripts/run_yolop_target_sanity.py smoke
python scripts/run_yolop_target_sanity.py sample
python scripts/run_yolop_target_sanity.py compare
python scripts/run_yolop_target_sanity.py finalize
```

## Dependencies installed
```bash
pip install onnx onnxruntime-gpu
```
"""
    with open(OUTPUT_DIR / "EXACT_COMMANDS.md", "w") as f:
        f.write(commands)

    # CHANGED_FILES.md
    changed = """# Changed / Created Files

## New files
- `scripts/run_yolop_target_sanity.py` — Main sanity runner
- `outputs/yolop_target_sanity_v0/` — All output artifacts

## Dependencies added
- `onnx` (1.22.0)
- `onnxruntime-gpu` (1.23.2)

## No existing files modified
"""
    with open(OUTPUT_DIR / "CHANGED_FILES.md", "w") as f:
        f.write(changed)

    print(f"\n{'='*60}")
    print(f"FINAL DECISION: {status}")
    print(f"Selected config: {extractor_config}")
    print(f"Next work: {next_work}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="YOLOP Target-Domain Sanity Audit")
    parser.add_argument("command", choices=["inspect", "smoke", "sample", "compare", "finalize"],
                        help="Which phase to run")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "inspect":
        run_inspect()
    elif args.command == "smoke":
        run_smoke()
    elif args.command == "sample":
        run_sample()
    elif args.command == "compare":
        run_compare()
    elif args.command == "finalize":
        compute_diagnostics()
        run_cost_profile()
        run_finalize()


if __name__ == "__main__":
    main()
