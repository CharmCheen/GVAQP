#!/usr/bin/env python3
"""Extract, profile, and evaluate the preregistered two-video proxy families.

This script never chooses queries or rule weights.  It reads the frozen
H-PROXY-2VIDEO preregistration and rejects any implementation mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from argparse import Namespace
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_two_video_loop"
PREREG_PATH = OUT / "proxy_finalization/H_PROXY_2VIDEO_PREREGISTRATION.json"
VIDEO_MANIFEST_PATH = OUT / "VIDEO_MANIFEST.json"
DEV = OUT / "dev_benchmark_v1"
RAW = OUT / "proxy_finalization/raw"
TABLES = OUT / "proxy_finalization/tables"
PROFILES = OUT / "proxy_finalization/physical_cost"
IMPLEMENTATION_FREEZE = OUT / "proxy_finalization/PROXY_IMPLEMENTATION_FREEZE.json"
SAMPLE_FPS = 5.0
CONFIDENCE = 0.25
NMS_IOU = 0.45
BASE_FEATURES = [
    "track_persistence",
    "path_directed_lateral_motion",
    "box_growth",
    "front_region_occupancy",
    "approximate_ttc_urgency",
]
GEOMETRY_FEATURES = [
    "lane_relative_motion",
    "boundary_crossing",
    "ego_corridor_overlap",
    "road_geometry_reliability",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        frame.to_csv(handle, index=False, lineterminator="\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def gpu_memory_mib() -> float:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=False,
    )
    try:
        return float(result.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return math.nan


class TrackerDetections:
    """Minimal ndarray-backed interface consumed by Ultralytics BYTETracker."""

    def __init__(self, xyxy: np.ndarray, conf: np.ndarray, cls: np.ndarray):
        self.xyxy = np.asarray(xyxy, dtype=np.float32).reshape(-1, 4)
        self.conf = np.asarray(conf, dtype=np.float32).reshape(-1)
        self.cls = np.asarray(cls, dtype=np.float32).reshape(-1)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, item):
        return TrackerDetections(self.xyxy[item], self.conf[item], self.cls[item])

    @property
    def xywh(self) -> np.ndarray:
        result = self.xyxy.copy()
        result[:, 2:] -= result[:, :2]
        result[:, :2] += result[:, 2:] / 2
        return result


class Y8Detector:
    def __init__(self, path: Path):
        import torch
        from ultralytics import YOLO

        self.torch = torch
        self.model = YOLO(str(path))

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], float]:
        started = time.perf_counter_ns()
        results = self.model.predict(
            frame, imgsz=640, conf=CONFIDENCE, iou=NMS_IOU,
            device="cuda", verbose=False,
        )
        self.torch.cuda.synchronize()
        detector_seconds = (time.perf_counter_ns() - started) / 1e9
        if not results or results[0].boxes is None:
            return (
                np.empty((0, 4), np.float32),
                np.empty(0, np.float32),
                np.empty(0, np.float32),
                {},
                detector_seconds,
            )
        boxes = results[0].boxes
        classes = boxes.cls.detach().cpu().numpy().astype(np.float32)
        keep = np.isin(classes.astype(int), [0, 1, 2, 3, 5, 7])
        return (
            boxes.xyxy.detach().cpu().numpy().astype(np.float32)[keep],
            boxes.conf.detach().cpu().numpy().astype(np.float32)[keep],
            classes[keep],
            {},
            detector_seconds,
        )


class YOLOPDetector:
    def __init__(self, path: Path, size: int):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(path), options, providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.size = size
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        height, width = frame.shape[:2]
        ratio = min(self.size / height, self.size / width)
        resized_width, resized_height = int(round(width * ratio)), int(round(height * ratio))
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        pad_x, pad_y = (self.size - resized_width) // 2, (self.size - resized_height) // 2
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + resized_height, pad_x:pad_x + resized_width] = cv2.cvtColor(
            resized, cv2.COLOR_BGR2RGB
        )
        image = canvas.astype(np.float32) / 255.0
        image[..., 0] = (image[..., 0] - 0.485) / 0.229
        image[..., 1] = (image[..., 1] - 0.456) / 0.224
        image[..., 2] = (image[..., 2] - 0.406) / 0.225
        return image.transpose(2, 0, 1)[None].astype(np.float32), {
            "ratio": ratio,
            "pad_x": pad_x,
            "pad_y": pad_y,
            "resized_width": resized_width,
            "resized_height": resized_height,
            "width": width,
            "height": height,
        }

    @staticmethod
    def nms(boxes: np.ndarray, scores: np.ndarray) -> np.ndarray:
        if not len(boxes):
            return np.empty(0, dtype=int)
        xywh = np.column_stack([
            boxes[:, 0], boxes[:, 1],
            boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1],
        ]).tolist()
        indices = cv2.dnn.NMSBoxes(xywh, scores.tolist(), CONFIDENCE, NMS_IOU)
        return np.asarray(indices, dtype=int).reshape(-1)[:300] if len(indices) else np.empty(0, dtype=int)

    def restore_segmentation(self, logits: np.ndarray, meta: dict[str, Any]) -> np.ndarray:
        crop = logits[
            0, :,
            meta["pad_y"]:meta["pad_y"] + meta["resized_height"],
            meta["pad_x"]:meta["pad_x"] + meta["resized_width"],
        ]
        mask = np.argmax(crop, axis=0).astype(np.uint8)
        return cv2.resize(
            mask, (meta["width"], meta["height"]), interpolation=cv2.INTER_NEAREST
        )

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], float]:
        image, meta = self.preprocess(frame)
        started = time.perf_counter_ns()
        detection, drivable, lane = self.session.run(self.output_names, {self.input_name: image})
        detector_seconds = (time.perf_counter_ns() - started) / 1e9
        values = detection[0]
        final_confidence = values[:, 4] * values[:, 5]
        values = values[final_confidence >= CONFIDENCE]
        final_confidence = final_confidence[final_confidence >= CONFIDENCE]
        boxes = np.empty((len(values), 4), dtype=np.float32)
        if len(values):
            boxes[:, 0] = values[:, 0] - values[:, 2] / 2
            boxes[:, 1] = values[:, 1] - values[:, 3] / 2
            boxes[:, 2] = values[:, 0] + values[:, 2] / 2
            boxes[:, 3] = values[:, 1] + values[:, 3] / 2
            boxes[:, [0, 2]] = (boxes[:, [0, 2]] - meta["pad_x"]) / meta["ratio"]
            boxes[:, [1, 3]] = (boxes[:, [1, 3]] - meta["pad_y"]) / meta["ratio"]
            boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, meta["width"])
            boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, meta["height"])
        keep = self.nms(boxes, final_confidence)
        geometry = {
            "drivable_mask": self.restore_segmentation(drivable, meta),
            "lane_mask": self.restore_segmentation(lane, meta),
        }
        return (
            boxes[keep],
            final_confidence[keep].astype(np.float32),
            np.zeros(len(keep), dtype=np.float32),
            geometry,
            detector_seconds,
        )


def make_tracker():
    from ultralytics.trackers.byte_tracker import BYTETracker

    arguments = Namespace(
        track_high_thresh=0.25,
        track_low_thresh=0.10,
        new_track_thresh=0.25,
        track_buffer=30,
        match_thresh=0.80,
        fuse_score=True,
    )
    return BYTETracker(arguments)


def road_geometry(geometry: dict[str, Any]) -> dict[str, float]:
    if not geometry:
        return {
            "lane_center": 0.5, "left_boundary": 0.3, "right_boundary": 0.7,
            "reliability": 0.0, "drivable_overlap": 0.0,
        }
    lane = geometry["lane_mask"].astype(np.uint8)
    drivable = geometry["drivable_mask"].astype(np.uint8)
    height, width = lane.shape
    bottom = lane[int(height * 0.60):]
    histogram = bottom.sum(axis=0)
    threshold = max(2.0, float(np.percentile(histogram, 90)))
    columns = (
        np.where(histogram >= threshold)[0] / max(width - 1, 1)
        if lane.any() else np.empty(0)
    )
    left = columns[columns < 0.5]
    right = columns[columns > 0.5]
    left_boundary = float(left.max()) if len(left) else 0.3
    right_boundary = float(right.min()) if len(right) else 0.7
    plausible = 0.15 <= right_boundary - left_boundary <= 0.80
    lane_ratio = float(lane.mean())
    drivable_ratio = float(drivable.mean())
    lane_ok = 0.001 <= lane_ratio <= 0.15
    drivable_ok = 0.02 <= drivable_ratio <= 0.80
    reliability = (float(lane_ok) + float(drivable_ok) + float(plausible)) / 3.0
    return {
        "lane_center": (left_boundary + right_boundary) / 2,
        "left_boundary": left_boundary,
        "right_boundary": right_boundary,
        "reliability": reliability,
        "drivable_overlap": drivable_ratio,
    }


def unit_memberships(units: pd.DataFrame, timestamp: float) -> list[int]:
    mask = (units["start_time"].astype(float) - 1e-9 <= timestamp) & (
        units["end_time"].astype(float) + 1e-9 >= timestamp
    )
    return units.loc[mask, "unit_id"].astype(int).tolist()


def new_candidate(video_id: str, query_id: str, unit_id: int, track_id: int, class_id: int) -> dict[str, Any]:
    row = {
        "video_id": video_id, "query_id": query_id, "unit_id": unit_id,
        "track_id": track_id, "class_id": class_id, "observations": 0,
    }
    for feature in BASE_FEATURES + GEOMETRY_FEATURES:
        row[feature] = 0.0
    return row


def update_candidate(
    candidate: dict[str, Any],
    bbox: np.ndarray,
    timestamp: float,
    previous: dict[str, float] | None,
    geometry: dict[str, float],
    frame_shape: tuple[int, int],
) -> None:
    height, width = frame_shape
    x1, y1, x2, y2 = map(float, bbox)
    center_x = ((x1 + x2) / 2) / width
    box_height = max(1e-9, (y2 - y1) / height)
    area = max(1e-12, ((x2 - x1) / width) * box_height)
    bottom_y = max(0.0, min(1.0, y2 / height))
    corridor = max(0.0, 1.0 - abs(center_x - 0.5) / 0.25)
    candidate["observations"] += 1
    candidate["track_persistence"] = float(candidate["observations"])
    candidate["front_region_occupancy"] = max(
        candidate["front_region_occupancy"], corridor * bottom_y
    )
    reliability = geometry["reliability"]
    in_corridor = float(
        geometry["left_boundary"] <= center_x <= geometry["right_boundary"]
    )
    candidate["ego_corridor_overlap"] = max(
        candidate["ego_corridor_overlap"], in_corridor * reliability
    )
    candidate["road_geometry_reliability"] = max(
        candidate["road_geometry_reliability"], reliability
    )
    if previous and timestamp > previous["timestamp"]:
        delta = timestamp - previous["timestamp"]
        lateral = max(
            0.0,
            abs(previous["center_x"] - 0.5) - abs(center_x - 0.5),
        ) / delta
        growth = max(0.0, math.log(area / max(previous["area"], 1e-12))) / delta
        relative_height_growth = max(
            0.0, (box_height - previous["box_height"]) / delta
        ) / max(previous["box_height"], 1e-9)
        candidate["path_directed_lateral_motion"] = max(
            candidate["path_directed_lateral_motion"], lateral
        )
        candidate["box_growth"] = max(candidate["box_growth"], growth)
        candidate["approximate_ttc_urgency"] = max(
            candidate["approximate_ttc_urgency"], relative_height_growth
        )
        previous_lane_distance = abs(previous["center_x"] - previous["lane_center"])
        lane_distance = abs(center_x - geometry["lane_center"])
        candidate["lane_relative_motion"] = max(
            candidate["lane_relative_motion"],
            max(0.0, previous_lane_distance - lane_distance) / delta * reliability,
        )
        previous_side = (
            -1 if previous["center_x"] < previous["left_boundary"]
            else 1 if previous["center_x"] > previous["right_boundary"]
            else 0
        )
        current_side = (
            -1 if center_x < geometry["left_boundary"]
            else 1 if center_x > geometry["right_boundary"]
            else 0
        )
        if previous_side != current_side and 0 in {previous_side, current_side}:
            candidate["boundary_crossing"] = max(
                candidate["boundary_crossing"], reliability
            )


def positive_percentile(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    result = pd.Series(0.0, index=series.index)
    mask = values > 0
    if mask.any():
        result.loc[mask] = values.loc[mask].rank(method="average", pct=True)
    return result


def score_candidates(candidates: pd.DataFrame, family: str, units: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_parts = []
    unit_rows = []
    for query_id in ("Q1", "Q2"):
        part = candidates[candidates["query_id"] == query_id].copy()
        features = BASE_FEATURES + (GEOMETRY_FEATURES if family.startswith("YP") else [])
        if family.startswith("YP") and query_id == "Q2":
            part = part.iloc[0:0].copy()
            features = []
        for feature in features:
            part[f"{feature}_normalized"] = positive_percentile(part[feature])
        if features:
            part["candidate_score"] = part[
                [f"{feature}_normalized" for feature in features]
            ].mean(axis=1)
        else:
            part["candidate_score"] = pd.Series(dtype=float)
        scored_parts.append(part)
        by_unit = {
            int(unit_id): group.sort_values(
                ["candidate_score", "track_id"], ascending=[False, True]
            ).iloc[0]
            for unit_id, group in part.groupby("unit_id")
        }
        for unit in units.to_dict("records"):
            unit_id = int(unit["unit_id"])
            top = by_unit.get(unit_id)
            unit_rows.append({
                "video_id": str(unit["video_id"]),
                "query_id": query_id,
                "unit_id": unit_id,
                "start_time": float(unit["start_time"]),
                "end_time": float(unit["end_time"]),
                "unit_score": 0.0 if top is None else float(top["candidate_score"]),
                "top_track_id": None if top is None else int(top["track_id"]),
                "top_class_id": None if top is None else int(top["class_id"]),
                "candidate_count": 0 if unit_id not in by_unit else int(
                    len(part[part["unit_id"] == unit_id])
                ),
                "top_track_evidence_json": "{}" if top is None else json.dumps({
                    feature: float(top[feature]) for feature in features
                }, sort_keys=True),
            })
    scored = pd.concat(scored_parts, ignore_index=True, sort=False)
    return scored, pd.DataFrame(unit_rows)


def load_units(video_id: str) -> pd.DataFrame:
    if video_id == "V1":
        return pd.read_csv(DEV / "units/V1_units.csv")
    source = (
        ROOT
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
        / "agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv"
    )
    units = pd.read_csv(source).copy()
    units["video_id"] = "V0"
    return units


def detector_for(family: str, prereg: dict[str, Any]):
    candidate = prereg["candidates"][family]
    path = Path(candidate["weight_path"])
    if sha256_file(path) != candidate["weight_sha256"]:
        raise RuntimeError(f"{family} weight hash changed")
    if family == "Y8":
        return Y8Detector(path)
    return YOLOPDetector(path, int(candidate["resolution"]))


def freeze_implementation() -> None:
    """Resolve causal online details before any candidate-family execution."""

    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if int(prereg.get("revision", -1)) != 1:
        raise RuntimeError("Expected causal-normalization preregistration revision 1")
    freeze = {
        "freeze_id": "PSVR_TWO_VIDEO_PROXY_IMPLEMENTATION_V2",
        "implementation_revision": 2,
        "supersedes_freeze_hash": (
            "573463e1fb1eaea70e14586709685fe24fd73405a203b0e051358f4195c1fe66"
        ),
        "revision_reason": (
            "The first full V0 extraction failed closed at frozen unit 346 because its "
            "inclusive end_frame 103886 equals the container frame count and is therefore "
            "one past the last decodable index 103885. The correction is frozen before any "
            "successful full-video proxy artifact or reference-based proxy evaluation."
        ),
        "preregistration_hash": prereg["preregistration_hash"],
        "frozen_before_proxy_candidate_execution": False,
        "frozen_before_successful_full_video_proxy_artifact": True,
        "frozen_before_reference_based_proxy_evaluation": True,
        "outcome_information_used": False,
        "frame_membership": (
            "Use each frozen unit's inclusive start_frame/end_frame fields intersected with the "
            "container's decodable frame-index domain. Only an end_frame exactly equal to the "
            "positive container frame count may be tail-clamped by one frame; any larger "
            "overrun or invalid start fails closed. No timestamp-boundary duplication."
        ),
        "decode_path": (
            "For each requested unit, seek to start_frame and sequentially decode through the "
            "validated effective end_frame; sample every round(video_fps/5) frames relative to "
            "start_frame. Persist requested and effective endpoints and the clamp count."
        ),
        "profile_retention": (
            "Revision 2 does not invalidate earlier physical cost profiles: all profiled units "
            "are within the decodable domain, so the revised branch was not exercised."
        ),
        "tracker_scope": (
            "Fresh frozen-parameter ByteTrack state per unit. This makes an arbitrary temporal "
            "scan order causal and makes raw unit features invariant to future or previously "
            "unscanned units."
        ),
        "offline_normalization_population": "all raw candidates in the complete video-query task",
        "online_normalization_population": (
            "all and only raw candidates from units whose scan has durably completed by the "
            "decision timestamp"
        ),
        "online_score_update": (
            "Recompute zero-anchored deterministic average-rank percentiles after each completed "
            "SCAN batch; previously exposed scores may be updated only from newly observed "
            "past/current candidates, never from future units."
        ),
        "unit_score": "maximum current candidate score; track_id ascending deterministic tie-break",
        "YOLOP_Q2": "fail closed with zero candidates and score 0",
        "implementation_path": str(Path(__file__).resolve()),
        "implementation_sha256": sha256_file(Path(__file__).resolve()),
        "heldout_opened": False,
    }
    freeze["freeze_hash"] = canonical_hash(freeze)
    if IMPLEMENTATION_FREEZE.exists():
        existing = json.loads(IMPLEMENTATION_FREEZE.read_text(encoding="utf-8"))
        if existing.get("freeze_id") == "PSVR_TWO_VIDEO_PROXY_IMPLEMENTATION_V1":
            archive = IMPLEMENTATION_FREEZE.with_name(
                "PROXY_IMPLEMENTATION_FREEZE_REVISION_1.json"
            )
            if archive.exists():
                if json.loads(archive.read_text(encoding="utf-8")) != existing:
                    raise RuntimeError("Proxy implementation revision-1 archive changed")
            else:
                atomic_json(archive, existing)
            atomic_json(IMPLEMENTATION_FREEZE, freeze)
        elif existing != freeze:
            raise RuntimeError("Proxy implementation changed after freeze")
    else:
        atomic_json(IMPLEMENTATION_FREEZE, freeze)
    print(json.dumps({
        "PROXY_IMPLEMENTATION_FREEZE": "PASS",
        "freeze_hash": freeze["freeze_hash"],
    }, indent=2))


class UnitProxyEngine:
    """Causal physical proxy path with tracker state scoped to one frozen unit."""

    def __init__(
        self,
        family: str,
        video_id: str,
        video_path: Path,
        prereg: dict[str, Any],
    ):
        self.family = family
        self.video_id = video_id
        self.video_path = Path(video_path)
        started = time.perf_counter_ns()
        self.detector = detector_for(family, prereg)
        self.initialization_seconds = (time.perf_counter_ns() - started) / 1e9
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open frozen video {self.video_path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.frame_count <= 0:
            raise RuntimeError(
                f"frozen video has invalid frame count {self.frame_count}: "
                f"{self.video_path}"
            )
        self.interval = max(1, int(round(self.fps / SAMPLE_FPS)))

    def close(self) -> None:
        self.cap.release()

    def scan_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        """Physically seek, decode, detect, track, score, and serialize one unit."""

        unit_id = int(unit["unit_id"])
        start_frame = int(unit["start_frame"])
        requested_end_frame = int(unit["end_frame"])
        if start_frame < 0 or start_frame >= self.frame_count:
            raise RuntimeError(
                f"unit {unit_id} start_frame {start_frame} is outside decodable "
                f"range [0, {self.frame_count - 1}]"
            )
        if requested_end_frame < start_frame:
            raise RuntimeError(
                f"unit {unit_id} has end_frame {requested_end_frame} before "
                f"start_frame {start_frame}"
            )
        if requested_end_frame > self.frame_count:
            raise RuntimeError(
                f"unit {unit_id} end_frame {requested_end_frame} exceeds the "
                f"one-past-tail allowance {self.frame_count}"
            )
        end_frame = min(requested_end_frame, self.frame_count - 1)
        tail_clamped_frames = requested_end_frame - end_frame
        tracker = make_tracker()
        history: dict[int, dict[str, float]] = {}
        candidates: dict[tuple[str, int], dict[str, Any]] = {}
        frame_costs: list[dict[str, Any]] = []
        seek_started = time.perf_counter_ns()
        seek_ok = self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        seek_seconds = (time.perf_counter_ns() - seek_started) / 1e9
        if not seek_ok:
            raise RuntimeError(f"OpenCV seek failed for unit {unit_id}")
        positioned_frame = float(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        if abs(positioned_frame - start_frame) > 0.5:
            raise RuntimeError(
                f"OpenCV seek landed at {positioned_frame} for unit {unit_id}, "
                f"expected {start_frame}"
            )
        decoded_frames = sampled_frames = 0
        detector_seconds = tracking_seconds = scoring_seconds = 0.0
        decode_accumulated = seek_seconds
        for frame_index in range(start_frame, end_frame + 1):
            decode_started = time.perf_counter_ns()
            ok, frame = self.cap.read()
            decode_accumulated += (time.perf_counter_ns() - decode_started) / 1e9
            if not ok:
                raise RuntimeError(
                    f"decode failed for unit {unit_id} at frame {frame_index}"
                )
            decoded_frames += 1
            if (frame_index - start_frame) % self.interval:
                continue
            sampled_frames += 1
            timestamp = frame_index / self.fps
            detector_path_started = time.perf_counter_ns()
            boxes, scores, classes, masks, detector_gpu = self.detector.detect(frame)
            detector_path = (time.perf_counter_ns() - detector_path_started) / 1e9
            detector_seconds += detector_gpu
            tracking_started = time.perf_counter_ns()
            active = tracker.update(TrackerDetections(boxes, scores, classes))
            tracking = (time.perf_counter_ns() - tracking_started) / 1e9
            tracking_seconds += tracking
            scoring_started = time.perf_counter_ns()
            geometry = road_geometry(masks)
            for track in active:
                bbox = np.asarray(track[:4], dtype=float)
                track_id = int(track[4])
                class_id = int(track[6])
                previous = history.get(track_id)
                query_ids: list[str] = []
                if self.family == "Y8":
                    if class_id in {1, 2, 3, 5, 7}:
                        query_ids.append("Q1")
                    if class_id in {0, 1, 3}:
                        query_ids.append("Q2")
                else:
                    query_ids.append("Q1")
                for query_id in query_ids:
                    key = (query_id, track_id)
                    if key not in candidates:
                        candidates[key] = new_candidate(
                            self.video_id, query_id, unit_id, track_id, class_id
                        )
                    update_candidate(
                        candidates[key],
                        bbox,
                        timestamp,
                        previous,
                        geometry,
                        frame.shape[:2],
                    )
                center_x = ((bbox[0] + bbox[2]) / 2) / frame.shape[1]
                history[track_id] = {
                    "timestamp": timestamp,
                    "center_x": center_x,
                    "area": max(
                        1e-12,
                        ((bbox[2] - bbox[0]) / frame.shape[1])
                        * ((bbox[3] - bbox[1]) / frame.shape[0]),
                    ),
                    "box_height": max(
                        1e-9, (bbox[3] - bbox[1]) / frame.shape[0]
                    ),
                    "lane_center": geometry["lane_center"],
                    "left_boundary": geometry["left_boundary"],
                    "right_boundary": geometry["right_boundary"],
                }
            scoring = (time.perf_counter_ns() - scoring_started) / 1e9
            scoring_seconds += scoring
            summary = {
                "video_id": self.video_id,
                "unit_id": unit_id,
                "frame_index": frame_index,
                "active_tracks": int(len(active)),
                "road_geometry_reliability": geometry["reliability"],
            }
            serialization_started = time.perf_counter_ns()
            json.dumps(summary, sort_keys=True, separators=(",", ":"))
            serialization = (time.perf_counter_ns() - serialization_started) / 1e9
            frame_costs.append({
                "unit_id": unit_id,
                "frame_index": frame_index,
                "decode_seconds": decode_accumulated,
                "detector_path_seconds": detector_path,
                "detector_gpu_seconds": detector_gpu,
                "tracking_seconds": tracking,
                "road_rule_scoring_seconds": scoring,
                "serialization_seconds": serialization,
                "total_seconds": (
                    decode_accumulated
                    + detector_path
                    + tracking
                    + scoring
                    + serialization
                ),
                "status": "PASS",
            })
            decode_accumulated = 0.0
        if frame_costs and decode_accumulated > 0:
            frame_costs[-1]["decode_seconds"] += decode_accumulated
            frame_costs[-1]["total_seconds"] += decode_accumulated
        evidence_started = time.perf_counter_ns()
        evidence_json = json.dumps(
            list(candidates.values()),
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_serialization_seconds = (
            time.perf_counter_ns() - evidence_started
        ) / 1e9
        if frame_costs:
            amortized = evidence_serialization_seconds / len(frame_costs)
            for row in frame_costs:
                row["serialization_seconds"] += amortized
                row["total_seconds"] += amortized
        return {
            "video_id": self.video_id,
            "unit_id": unit_id,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "requested_end_frame": requested_end_frame,
            "effective_end_frame": end_frame,
            "tail_clamped_frames": tail_clamped_frames,
            "container_frame_count": self.frame_count,
            "decoded_frames": decoded_frames,
            "sampled_frames": sampled_frames,
            "seek_seconds": seek_seconds,
            "decode_seconds": sum(
                float(row["decode_seconds"]) for row in frame_costs
            ),
            "detector_path_seconds": sum(
                float(row["detector_path_seconds"]) for row in frame_costs
            ),
            "detector_gpu_seconds": detector_seconds,
            "tracking_cpu_seconds": tracking_seconds,
            "rule_scoring_cpu_seconds": scoring_seconds,
            "evidence_serialization_seconds": evidence_serialization_seconds,
            "candidates": list(candidates.values()),
            "candidate_evidence_sha256": hashlib.sha256(
                evidence_json.encode()
            ).hexdigest(),
            "frame_costs": frame_costs,
        }


def smoke(family: str, video_id: str, unit_id: int) -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    videos = json.loads(VIDEO_MANIFEST_PATH.read_text(encoding="utf-8"))
    units = load_units(video_id)
    selected = units[units.unit_id.astype(int) == int(unit_id)]
    if len(selected) != 1:
        raise RuntimeError("Unknown frozen smoke unit")
    video_path = Path(videos[video_id]["absolute_path"])
    engine = UnitProxyEngine(family, video_id, video_path, prereg)
    try:
        result = engine.scan_unit(selected.iloc[0].to_dict())
    finally:
        engine.close()
    candidates = pd.DataFrame(result["candidates"])
    if candidates.empty:
        candidates = pd.DataFrame(columns=[
            "video_id", "query_id", "unit_id", "track_id", "class_id",
            "observations", *BASE_FEATURES, *GEOMETRY_FEATURES,
        ])
    scored, unit_scores = score_candidates(candidates, family, selected)
    if int(result["sampled_frames"]) < 1:
        raise RuntimeError("Proxy smoke decoded no sampled frames")
    if not np.isfinite(
        unit_scores["unit_score"].astype(float).to_numpy()
    ).all():
        raise RuntimeError("Proxy smoke produced a non-finite unit score")
    payload = {
        "status": "PASS",
        "family": family,
        "video_id": video_id,
        "unit_id": int(unit_id),
        "initialization_seconds": engine.initialization_seconds,
        "scan_result": {
            key: value
            for key, value in result.items()
            if key not in {"candidates", "frame_costs"}
        },
        "candidate_rows": len(scored),
        "unit_scores": unit_scores.astype(object).where(
            pd.notna(unit_scores), None
        ).to_dict("records"),
        "implementation_sha256": sha256_file(Path(__file__).resolve()),
        "preregistration_hash": prereg["preregistration_hash"],
        "heldout_opened": False,
    }
    destination = (
        PROFILES.parent / "smoke" / f"{family}_{video_id}_unit_{unit_id:04d}.json"
    )
    atomic_json(destination, payload)
    print(json.dumps(payload, indent=2))


def extract(family: str, video_id: str) -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    videos = json.loads(VIDEO_MANIFEST_PATH.read_text(encoding="utf-8"))
    video_path = Path(videos[video_id]["absolute_path"])
    if sha256_file(video_path) != videos[video_id]["sha256"]:
        raise RuntimeError("Frozen video hash changed")
    units = load_units(video_id)
    engine = UnitProxyEngine(family, video_id, video_path, prereg)
    initialization_seconds = engine.initialization_seconds
    candidates: list[dict[str, Any]] = []
    decode_seconds = detector_path_seconds = detector_seconds = 0.0
    tracking_seconds = scoring_seconds = 0.0
    evidence_serialization_seconds = 0.0
    sampled_frames = decoded_frames = 0
    unit_rows: list[dict[str, Any]] = []
    processing_start_utc = utc_now()
    started = time.perf_counter_ns()
    peak_memory = gpu_memory_mib()
    try:
        for index, unit in enumerate(units.to_dict("records"), start=1):
            result = engine.scan_unit(unit)
            candidates.extend(result["candidates"])
            decoded_frames += int(result["decoded_frames"])
            sampled_frames += int(result["sampled_frames"])
            decode_seconds += float(result["decode_seconds"])
            detector_path_seconds += float(result["detector_path_seconds"])
            detector_seconds += float(result["detector_gpu_seconds"])
            tracking_seconds += float(result["tracking_cpu_seconds"])
            scoring_seconds += float(result["rule_scoring_cpu_seconds"])
            evidence_serialization_seconds += float(
                result["evidence_serialization_seconds"]
            )
            unit_rows.append({
                key: value for key, value in result.items()
                if key not in {"candidates", "frame_costs"}
            })
            peak_memory = max(peak_memory, gpu_memory_mib())
            if index % 20 == 0 or index == len(units):
                print(json.dumps({
                    "family": family,
                    "video_id": video_id,
                    "completed_units": index,
                    "total_units": len(units),
                    "sampled_frames": sampled_frames,
                }), flush=True)
    finally:
        engine.close()
    extraction_wall = (time.perf_counter_ns() - started) / 1e9
    candidate_frame = pd.DataFrame(candidates)
    if candidate_frame.empty:
        candidate_frame = pd.DataFrame(columns=[
            "video_id", "query_id", "unit_id", "track_id", "class_id", "observations",
            *BASE_FEATURES, *GEOMETRY_FEATURES,
        ])
    aggregation_started = time.perf_counter_ns()
    scored, unit_scores = score_candidates(candidate_frame, family, units)
    aggregation_scoring_seconds = (
        time.perf_counter_ns() - aggregation_started
    ) / 1e9
    serialization_started = time.perf_counter_ns()
    directory = RAW / family / video_id
    atomic_csv(directory / "TRACK_CANDIDATES.csv", scored)
    atomic_csv(directory / "UNIT_SCORES.csv", unit_scores)
    atomic_json(directory / "UNIT_PROCESSING.json", unit_rows)
    serialization_seconds = (time.perf_counter_ns() - serialization_started) / 1e9
    total_wall = (
        extraction_wall + aggregation_scoring_seconds + serialization_seconds
    )
    duration = float(videos[video_id]["duration_seconds"])
    cost = {
        "family": family,
        "video_id": video_id,
        "video_duration_seconds": duration,
        "sample_fps": SAMPLE_FPS,
        "decoded_frames": decoded_frames,
        "sampled_frames": sampled_frames,
        "tracker_scope": "fresh deterministic ByteTrack state per frozen unit",
        "decode_path": "seek to frozen start_frame then sequential decode through end_frame",
        "initialization_seconds": initialization_seconds,
        "decode_seconds": decode_seconds,
        "detector_path_seconds": detector_path_seconds,
        "detector_gpu_seconds": detector_seconds,
        "detector_host_overhead_seconds": max(
            0.0, detector_path_seconds - detector_seconds
        ),
        "tracking_cpu_seconds": tracking_seconds,
        "rule_scoring_cpu_seconds": scoring_seconds,
        "aggregation_normalization_scoring_seconds": aggregation_scoring_seconds,
        "candidate_evidence_serialization_seconds": evidence_serialization_seconds,
        "serialization_seconds": serialization_seconds + evidence_serialization_seconds,
        "processing_wall_seconds": total_wall,
        "end_to_end_sample_fps": sampled_frames / total_wall,
        "peak_gpu_memory_mib": peak_memory,
        "gpu_seconds_per_video_hour": detector_seconds / duration * 3600,
        "cpu_seconds_per_video_hour": (
            decode_seconds + tracking_seconds + scoring_seconds
            + aggregation_scoring_seconds
            + serialization_seconds + evidence_serialization_seconds
            + max(0.0, detector_path_seconds - detector_seconds)
        ) / duration * 3600,
        "proxy_processing_start_utc": processing_start_utc,
        "proxy_processing_end_utc": utc_now(),
        "preregistration_hash": prereg["preregistration_hash"],
        "heldout_opened": False,
    }
    atomic_json(directory / "FULL_VIDEO_COST.json", cost)
    atomic_json(directory / "EXTRACTION_COMPLETE.json", {
        "status": "COMPLETE",
        "family": family,
        "video_id": video_id,
        "unit_scores_sha256": sha256_file(directory / "UNIT_SCORES.csv"),
        "track_candidates_sha256": sha256_file(directory / "TRACK_CANDIDATES.csv"),
        "full_video_cost_sha256": sha256_file(directory / "FULL_VIDEO_COST.json"),
    })
    print(json.dumps(cost, indent=2))


def event_ids_for_top(reference: pd.DataFrame, top_units: set[int]) -> set[str]:
    result = set()
    for row in reference.to_dict("records"):
        source = {
            int(value) for value in str(row["source_unit_ids"]).split("|")
            if str(value).strip()
        }
        if source & top_units:
            result.add(str(row["reference_event_id"]))
    return result


def evaluate_one(family: str, task_id: str) -> dict[str, Any]:
    video_id, query_id = task_id.split("_")
    scores = pd.read_csv(RAW / family / video_id / "UNIT_SCORES.csv")
    scores = scores[scores["query_id"] == query_id].copy()
    labels = pd.read_csv(DEV / f"parsed_labels/{task_id}.csv")
    reference = pd.read_csv(DEV / f"reference_events/{task_id}.csv")
    merged = scores.merge(
        labels[["unit_id", "parsed_label"]], on="unit_id", validate="one_to_one"
    )
    merged["positive"] = (merged["parsed_label"] == "positive").astype(int)
    ranking = merged.sort_values(["unit_score", "unit_id"], ascending=[False, True]).reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    try:
        from sklearn.metrics import average_precision_score

        auprc = float(average_precision_score(merged["positive"], merged["unit_score"]))
    except ValueError:
        auprc = 0.0
    positives = int(merged["positive"].sum())
    first = ranking.index[ranking["positive"] == 1]
    first_rank = None if len(first) == 0 else int(first[0] + 1)
    rows: dict[str, Any] = {
        "family": family,
        "task_id": task_id,
        "video_id": video_id,
        "query_id": query_id,
        "units": len(merged),
        "positive_units": positives,
        "reference_events": len(reference),
        "unit_auprc": auprc,
        "first_positive_rank": first_rank,
        "false_positives_before_first_hit": None if first_rank is None else first_rank - 1,
    }
    exposure = []
    seen = set()
    for _, row in ranking.iterrows():
        seen |= event_ids_for_top(reference, {int(row["unit_id"])})
        exposure.append(len(seen) / max(len(reference), 1))
    rows["positive_event_exposure_auc"] = float(np.mean(exposure)) if exposure else 0.0
    for k in (10, 20, 50):
        top = ranking.head(k)
        top_units = set(top["unit_id"].astype(int))
        hits = int(top["positive"].sum())
        events = event_ids_for_top(reference, top_units)
        rows[f"candidate_precision@{k}"] = hits / k
        rows[f"candidate_recall@{k}"] = hits / max(positives, 1)
        rows[f"unique_event_recall@{k}"] = len(events) / max(len(reference), 1)
        rows[f"unique_events@{k}"] = len(events)
    return rows


def evaluate() -> None:
    task_manifest = json.loads((DEV / "TASK_MANIFEST.json").read_text())
    rows = []
    for family in ("Y8", "YP640", "YP320"):
        for task in task_manifest["tasks"]:
            rows.append(evaluate_one(family, task["task_id"]))
    frame = pd.DataFrame(rows)
    atomic_csv(TABLES / "OFFLINE_TASK_METRICS.csv", frame)
    numeric = [
        column for column in frame.columns
        if column not in {"family", "task_id", "video_id", "query_id"}
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
    macro = frame.groupby("family")[numeric].mean(numeric_only=True).reset_index()
    atomic_csv(TABLES / "OFFLINE_MACRO_METRICS.csv", macro)
    print(macro.to_string(index=False))


def profile(family: str) -> None:
    """Three physical repeats after 20 warm-up and 1000 measured sampled frames."""
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    videos = json.loads(VIDEO_MANIFEST_PATH.read_text(encoding="utf-8"))
    video_path = Path(videos["V0"]["absolute_path"])
    units = load_units("V0")
    engine = UnitProxyEngine(family, "V0", video_path, prereg)
    initialization_seconds = engine.initialization_seconds
    rows = []
    peak_memory = gpu_memory_mib()
    try:
        for repeat in range(3):
            costs: list[dict[str, Any]] = []
            for unit in units.to_dict("records"):
                costs.extend(engine.scan_unit(unit)["frame_costs"])
                if len(costs) >= 1020:
                    break
            if len(costs) < 1020:
                raise RuntimeError("Profile video ended before 1020 sampled frames")
            for measured_index, row in enumerate(costs[20:1020]):
                rows.append({
                    **row,
                    "family": family,
                    "repeat": repeat,
                    "measured_index": measured_index,
                })
            peak_memory = max(peak_memory, gpu_memory_mib())
            print(json.dumps({
                "family": family, "profile_repeat": repeat,
                "warmup_frames": 20, "measured_frames": 1000,
            }), flush=True)
    finally:
        engine.close()
    frame = pd.DataFrame(rows)
    atomic_csv(PROFILES / f"{family}_PROFILE_SAMPLES.csv", frame)
    total = frame["total_seconds"].astype(float)
    detector_gpu = frame["detector_gpu_seconds"].astype(float)
    report = {
        "family": family,
        "warmup_frames_per_repeat": 20,
        "measured_frames_per_repeat": 1000,
        "physical_repeats": 3,
        "valid_samples": len(frame),
        "initialization_seconds": initialization_seconds,
        "end_to_end_fps": 1 / float(total.mean()),
        "p50_latency_ms": float(np.percentile(total, 50) * 1000),
        "p90_latency_ms": float(np.percentile(total, 90) * 1000),
        "p95_latency_ms": float(np.percentile(total, 95) * 1000),
        "peak_gpu_memory_mib": peak_memory,
        "gpu_seconds_per_video_hour": float(detector_gpu.mean() * SAMPLE_FPS * 3600),
        "cpu_seconds_per_video_hour": float(
            (total - detector_gpu).clip(lower=0).mean() * SAMPLE_FPS * 3600
        ),
        "stage_mean_ms": {
            column: float(frame[column].astype(float).mean() * 1000)
            for column in [
                "decode_seconds", "detector_path_seconds", "detector_gpu_seconds",
                "tracking_seconds", "road_rule_scoring_seconds", "serialization_seconds",
            ]
        },
        "samples_sha256": sha256_file(PROFILES / f"{family}_PROFILE_SAMPLES.csv"),
        "preregistration_hash": prereg["preregistration_hash"],
        "heldout_opened": False,
    }
    atomic_json(PROFILES / f"{family}_PHYSICAL_COST.json", report)
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze-implementation")
    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--family", required=True, choices=["Y8", "YP640", "YP320"])
    smoke_parser.add_argument("--video", required=True, choices=["V0", "V1"])
    smoke_parser.add_argument("--unit", type=int, default=0)
    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("--family", required=True, choices=["Y8", "YP640", "YP320"])
    extract_parser.add_argument("--video", required=True, choices=["V0", "V1"])
    sub.add_parser("evaluate")
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--family", required=True, choices=["Y8", "YP640", "YP320"])
    args = parser.parse_args()
    if args.command == "freeze-implementation":
        freeze_implementation()
    elif args.command == "smoke":
        smoke(args.family, args.video, args.unit)
    elif args.command == "extract":
        extract(args.family, args.video)
    elif args.command == "profile":
        profile(args.family)
    else:
        evaluate()


if __name__ == "__main__":
    main()
