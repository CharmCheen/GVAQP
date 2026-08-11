#!/usr/bin/env python3
"""Shared implementation for PARTIAL_SCAN_BENCHMARK_PILOT_V1.

The module deliberately contains no reference-event loader in the policy
state or policy classes.  References are evaluator-only assets.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMMUTABLE = BENCH / "immutable"
DERIVED = BENCH / "derived"
OUTPUT = ROOT / "outputs/partial_scan_pilot_v1"
CONTRACT_DOC = ROOT / "docs/PARTIAL_SCAN_BENCHMARK_CONSTRUCTION_CONTRACT.md"
TIMELINE = IMMUTABLE / "timeline_units.csv"
TIMELINE_OFFSET5 = DERIVED / "timeline_units_offset5.csv"
VIDEOS = IMMUTABLE / "videos.csv"
REFERENCE = IMMUTABLE / "reference_events.csv"
SAMPLE_FPS = 5.0
CONFIDENCE = 0.25
NMS_IOU = 0.45
TEMPORAL_NMS_IOU = 0.50
MIN_OBSERVATIONS = 3
MIN_FRONT_OCCUPANCY = 0.05
MOTOR_CLASSES = {2, 3, 5, 7}
BASE_FEATURES = [
    "track_persistence",
    "path_directed_lateral_motion",
    "box_growth",
    "front_region_occupancy",
    "approximate_ttc_urgency",
]
SEED = 20260723


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


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_text(path, frame.to_csv(index=False, lineterminator="\n"))


def atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def load_proxy_module():
    path = ROOT / "scripts/run_psvr_two_video_proxy.py"
    spec = importlib.util.spec_from_file_location("partial_scan_frozen_proxy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def video_info(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    video = next(row for row in payload["streams"] if row.get("codec_type") == "video")
    fmt = payload["format"]
    numerator, denominator = (video.get("avg_frame_rate") or video["r_frame_rate"]).split("/")
    fps = float(numerator) / float(denominator)
    return {
        "duration_sec": float(fmt.get("duration") or video["duration"]),
        "fps": fps,
        "frame_count": int(video.get("nb_frames") or round(float(fmt["duration"]) * fps)),
        "resolution": f"{video['width']}x{video['height']}",
        "codec": video["codec_name"],
        "container": fmt["format_name"],
    }


def keyframes(path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-skip_frame", "nokey", "-show_entries",
            "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    values = []
    for line in result.stdout.splitlines():
        try:
            values.append(float(line.strip().split(",")[0]))
        except ValueError:
            continue
    return np.asarray(values, dtype=float)


def make_timeline(video: dict[str, Any], offset: float) -> pd.DataFrame:
    duration = float(video["duration_sec"])
    fps = float(video["fps"])
    frame_count = int(video["frame_count"])
    keys = keyframes(Path(video["video_path"]))
    rows: list[dict[str, Any]] = []
    index = 0
    start = float(offset)
    while start < duration - 1e-9:
        end = min(duration, start + 10.0)
        start_frame = min(frame_count - 1, max(0, int(math.ceil(start * fps - 1e-9))))
        end_frame = min(frame_count - 1, max(start_frame, int(math.ceil(end * fps - 1e-9)) - 1))
        if len(keys):
            nearest = float(keys[np.argmin(np.abs(keys - start))])
        else:
            nearest = math.nan
        rows.append({
            "video_id": video["video_id"],
            "unit_id": f"{video['video_id']}_o{int(offset):02d}_u{index:04d}",
            "unit_index": index,
            "offset_sec": float(offset),
            "start_sec": start,
            "end_sec": end,
            "duration_sec": end - start,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "nearest_keyframe_sec": nearest,
            "is_tail_unit": bool(end - start < 10.0 - 1e-6),
            "source_hash": video["video_hash"],
        })
        index += 1
        start = offset + index * 10.0
    return pd.DataFrame(rows)


def scan_output_dir(video_id: str, unit_id: str, offset: int = 0) -> Path:
    if offset == 0:
        return IMMUTABLE / "scan_outputs" / video_id / unit_id
    return DERIVED / "offset5_scan_outputs" / video_id / unit_id


def rounded_records(frame: pd.DataFrame, decimals: int = 6) -> list[dict[str, Any]]:
    copy = frame.copy()
    for column in copy.select_dtypes(include=[np.number]).columns:
        copy[column] = copy[column].astype(float).round(decimals)
    return copy.astype(object).where(pd.notna(copy), None).to_dict("records")


class ScanEngine:
    """One decoder/model per run; fresh ByteTrack state for every action."""

    def __init__(self, video: dict[str, Any]):
        self.video = video
        self.proxy = load_proxy_module()
        weights = ROOT / "models/yolo/yolov8n.pt"
        if sha256_file(weights) != json.loads(
            (IMMUTABLE / "contracts/scan_operator_contract.yaml").read_text()
        )["yolo_weight_sha256"]:
            raise RuntimeError("YOLO weights changed after contract freeze")
        started = time.perf_counter()
        self.detector = self.proxy.Y8Detector(weights)
        self.model_load_sec = time.perf_counter() - started
        self.capture = cv2.VideoCapture(str(video["video_path"]))
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open {video['video_path']}")
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.interval = max(1, int(round(self.fps / SAMPLE_FPS)))

    def close(self) -> None:
        self.capture.release()

    def scan(self, unit: dict[str, Any]) -> dict[str, Any]:
        started_total = time.perf_counter()
        start_frame, end_frame = int(unit["start_frame"]), int(unit["end_frame"])
        seek_started = time.perf_counter()
        if not self.capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame):
            raise RuntimeError(f"seek failed for {unit['unit_id']}")
        seek_sec = time.perf_counter() - seek_started
        tracker = self.proxy.make_tracker()
        histories: dict[int, dict[str, float]] = {}
        candidates: dict[int, dict[str, Any]] = {}
        bounds: dict[int, list[float]] = {}
        detections: list[dict[str, Any]] = []
        tracks: list[dict[str, Any]] = []
        decode_sec = model_sec = tracker_sec = candidate_sec = 0.0
        decoded = sampled = 0
        for frame_index in range(start_frame, end_frame + 1):
            t0 = time.perf_counter()
            ok, frame = self.capture.read()
            decode_sec += time.perf_counter() - t0
            if not ok:
                raise RuntimeError(f"decode failed {unit['unit_id']} frame={frame_index}")
            decoded += 1
            if (frame_index - start_frame) % self.interval:
                continue
            sampled += 1
            timestamp = frame_index / self.fps
            boxes, scores, classes, _, detector_time = self.detector.detect(frame)
            model_sec += float(detector_time)
            keep = np.isin(classes.astype(int), sorted(MOTOR_CLASSES))
            boxes, scores, classes = boxes[keep], scores[keep], classes[keep]
            for box, score, cls in zip(boxes, scores, classes):
                detections.append({
                    "video_id": unit["video_id"], "unit_id": unit["unit_id"],
                    "frame_index": frame_index, "timestamp_sec": timestamp,
                    "class_id": int(cls), "confidence": float(score),
                    "x1": float(box[0]), "y1": float(box[1]),
                    "x2": float(box[2]), "y2": float(box[3]),
                })
            t0 = time.perf_counter()
            active = tracker.update(self.proxy.TrackerDetections(boxes, scores, classes))
            tracker_sec += time.perf_counter() - t0
            t0 = time.perf_counter()
            height, width = frame.shape[:2]
            for track in active:
                bbox = np.asarray(track[:4], dtype=float)
                track_id, class_id = int(track[4]), int(track[6])
                if class_id not in MOTOR_CLASSES:
                    continue
                tracks.append({
                    "video_id": unit["video_id"], "unit_id": unit["unit_id"],
                    "frame_index": frame_index, "timestamp_sec": timestamp,
                    "track_id": track_id, "class_id": class_id,
                    "confidence": float(track[5]),
                    "x1": float(bbox[0]), "y1": float(bbox[1]),
                    "x2": float(bbox[2]), "y2": float(bbox[3]),
                })
                if track_id not in candidates:
                    candidates[track_id] = self.proxy.new_candidate(
                        unit["video_id"], "TARGET_VEHICLE_CUT_IN",
                        int(unit["unit_index"]), track_id, class_id,
                    )
                    bounds[track_id] = [timestamp, timestamp]
                bounds[track_id][1] = timestamp
                geometry = {
                    "lane_center": 0.5, "left_boundary": 0.3,
                    "right_boundary": 0.7, "reliability": 0.0,
                    "drivable_overlap": 0.0,
                }
                self.proxy.update_candidate(
                    candidates[track_id], bbox, timestamp, histories.get(track_id),
                    geometry, frame.shape[:2],
                )
                cx = ((bbox[0] + bbox[2]) / 2) / width
                bh = max(1e-9, (bbox[3] - bbox[1]) / height)
                histories[track_id] = {
                    "timestamp": timestamp, "center_x": cx,
                    "area": max(1e-12, ((bbox[2] - bbox[0]) / width) * bh),
                    "box_height": bh, "lane_center": 0.5,
                    "left_boundary": 0.3, "right_boundary": 0.7,
                }
            candidate_sec += time.perf_counter() - t0
        raw: list[dict[str, Any]] = []
        triggers: list[dict[str, Any]] = []
        for track_id, candidate in sorted(candidates.items()):
            eligible = (
                int(candidate["observations"]) >= MIN_OBSERVATIONS
                and float(candidate["front_region_occupancy"]) >= MIN_FRONT_OCCUPANCY
                and (
                    float(candidate["path_directed_lateral_motion"]) > 0
                    or float(candidate["box_growth"]) > 0
                )
            )
            row = {
                **candidate,
                "unit_id": unit["unit_id"],
                "candidate_start_sec": bounds[track_id][0],
                "candidate_end_sec": bounds[track_id][1],
                "source_unit_ids": [unit["unit_id"]],
                "tracker_reset": True,
                "trigger_eligible": eligible,
            }
            row["candidate_id"] = "cand_" + canonical_hash({
                "video": unit["video_id"], "unit": unit["unit_id"],
                "track": track_id, "start": round(bounds[track_id][0], 6),
                "end": round(bounds[track_id][1], 6),
            })[:24]
            if eligible:
                raw.append(row)
                triggers.append({
                    "candidate_id": row["candidate_id"], "track_id": track_id,
                    "trigger": "MOTOR_TRACK_LATERAL_OR_GROWTH",
                    "observations": int(candidate["observations"]),
                    "front_region_occupancy": float(candidate["front_region_occupancy"]),
                })
        runtime = {
            "status": "PASS", "video_id": unit["video_id"], "unit_id": unit["unit_id"],
            "decoder_start": start_frame, "decoded_frames": decoded,
            "sampled_frames": sampled, "detection_count": len(detections),
            "track_count": len({row["track_id"] for row in tracks}),
            "trigger_count": len(triggers), "raw_candidate_count": len(raw),
            "tracker_reset": True, "seek_time_sec": seek_sec,
            "decode_time_sec": decode_sec, "model_time_sec": model_sec,
            "tracker_time_sec": tracker_sec, "candidate_time_sec": candidate_sec,
            "environment_overhead_sec": max(
                0.0, time.perf_counter() - started_total
                - seek_sec - decode_sec - model_sec - tracker_sec - candidate_sec
            ),
            "total_action_time_sec": time.perf_counter() - started_total,
            "scan_operator_hash": json.loads(
                (IMMUTABLE / "contracts/scan_operator_contract.yaml").read_text()
            )["contract_hash"],
        }
        return {
            "detections": pd.DataFrame(detections),
            "tracks": pd.DataFrame(tracks),
            "triggers": triggers, "raw_candidates": raw, "runtime": runtime,
        }


def save_scan_result(destination: Path, result: dict[str, Any]) -> dict[str, str]:
    destination.mkdir(parents=True, exist_ok=True)
    detection_columns = [
        "video_id", "unit_id", "frame_index", "timestamp_sec", "class_id",
        "confidence", "x1", "y1", "x2", "y2",
    ]
    track_columns = [
        "video_id", "unit_id", "frame_index", "timestamp_sec", "track_id",
        "class_id", "confidence", "x1", "y1", "x2", "y2",
    ]
    detections = result["detections"].reindex(columns=detection_columns)
    tracks = result["tracks"].reindex(columns=track_columns)
    atomic_parquet(destination / "detections.parquet", detections)
    atomic_parquet(destination / "tracks.parquet", tracks)
    atomic_json(destination / "triggers.json", result["triggers"])
    atomic_json(destination / "raw_candidates.json", result["raw_candidates"])
    atomic_json(destination / "runtime.json", result["runtime"])
    hashes = {
        name: sha256_file(destination / name) for name in [
            "detections.parquet", "tracks.parquet", "triggers.json",
            "raw_candidates.json", "runtime.json",
        ]
    }
    semantic = {
        "detections": canonical_hash(rounded_records(detections)),
        "tracks": canonical_hash(rounded_records(tracks)),
        "triggers": canonical_hash(result["triggers"]),
        "raw_candidates": canonical_hash(result["raw_candidates"]),
    }
    payload = {"file_hashes": hashes, "semantic_hashes": semantic}
    atomic_json(destination / "output_hashes.json", payload)
    return semantic


def temporal_iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    intersection = max(
        0.0,
        min(float(left["candidate_end_sec"]), float(right["candidate_end_sec"]))
        - max(float(left["candidate_start_sec"]), float(right["candidate_start_sec"])),
    )
    union = (
        max(float(left["candidate_end_sec"]), float(right["candidate_end_sec"]))
        - min(float(left["candidate_start_sec"]), float(right["candidate_start_sec"]))
    )
    return intersection / union if union > 0 else 0.0


def visible_candidates(video_id: str, visible_unit_ids: set[str], offset: int = 0) -> pd.DataFrame:
    raw: list[dict[str, Any]] = []
    for unit_id in sorted(visible_unit_ids):
        path = scan_output_dir(video_id, unit_id, offset) / "raw_candidates.json"
        if not path.is_file():
            raise RuntimeError(f"Attempt to reveal unavailable unit output: {unit_id}")
        raw.extend(json.loads(path.read_text()))
    if not raw:
        return pd.DataFrame(columns=[
            "candidate_id", "video_id", "source_unit_ids", "candidate_start_sec",
            "candidate_end_sec", "generation_state_hash", "admission_version",
            "candidate_score",
        ])
    frame = pd.DataFrame(raw)
    normalized = []
    for feature in BASE_FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").fillna(0.0)
        ranks = pd.Series(0.0, index=frame.index)
        positive = values > 0
        if positive.any():
            ranks.loc[positive] = values.loc[positive].rank(method="average", pct=True)
        normalized.append(ranks)
    frame["candidate_score"] = pd.concat(normalized, axis=1).mean(axis=1)
    ordered = frame.sort_values(
        ["candidate_score", "candidate_id"], ascending=[False, True]
    )
    admitted: list[dict[str, Any]] = []
    for row in ordered.to_dict("records"):
        if any(temporal_iou(row, prior) >= TEMPORAL_NMS_IOU for prior in admitted):
            continue
        admitted.append(row)
    state_hash = canonical_hash(sorted(visible_unit_ids))
    for row in admitted:
        row["generation_state_hash"] = state_hash
        row["admission_version"] = "visible_percentile_temporal_nms_v1"
    return pd.DataFrame(admitted)


@dataclass(frozen=True)
class PublicScanState:
    video_id: str
    timeline: tuple[tuple[str, float, float], ...]
    scanned_units: tuple[str, ...]
    current_unit_id: str | None
    remaining_estimated_budget_sec: float
    past_action_costs_sec: tuple[float, ...]
    revealed_candidate_ids: tuple[str, ...]
    geometric_coverage_fraction: float


@dataclass(frozen=True)
class ScanObservation:
    unit_id: str
    action_cost_sec: float
    revealed_candidate_ids: tuple[str, ...]
    result_class: str


class ReplayEnvironment:
    def __init__(self, estimated_cost_sec: float = 2.0):
        self.estimated_cost_sec = float(estimated_cost_sec)
        self._units = pd.DataFrame()
        self._video_id = ""
        self._scanned: set[str] = set()
        self._current: str | None = None
        self._remaining = 0.0
        self._costs: list[float] = []

    def reset(self, video_id: str, budget_sec: float) -> PublicScanState:
        timeline = pd.read_csv(TIMELINE)
        self._units = timeline[timeline.video_id.eq(video_id)].sort_values("unit_index")
        if self._units.empty:
            raise KeyError(video_id)
        self._video_id, self._scanned, self._current = video_id, set(), None
        self._remaining, self._costs = float(budget_sec), []
        return self.public_state()

    def available_actions(self) -> list[str]:
        return [
            str(value) for value in self._units.unit_id
            if str(value) not in self._scanned
        ]

    def public_state(self) -> PublicScanState:
        candidates = visible_candidates(self._video_id, self._scanned)
        return PublicScanState(
            video_id=self._video_id,
            timeline=tuple(
                (str(row.unit_id), float(row.start_sec), float(row.end_sec))
                for row in self._units.itertuples(index=False)
            ),
            scanned_units=tuple(sorted(self._scanned)),
            current_unit_id=self._current,
            remaining_estimated_budget_sec=self._remaining,
            past_action_costs_sec=tuple(self._costs),
            revealed_candidate_ids=tuple(sorted(candidates.candidate_id.astype(str))),
            geometric_coverage_fraction=len(self._scanned) / len(self._units),
        )

    def scan(self, unit_id: str) -> ScanObservation:
        if unit_id not in self.available_actions():
            raise ValueError("action unavailable")
        if self._remaining < self.estimated_cost_sec:
            raise RuntimeError("ACTION_START_PROHIBITED_INSUFFICIENT_ESTIMATED_BUDGET")
        self._scanned.add(unit_id)
        self._current = unit_id
        self._remaining -= self.estimated_cost_sec
        self._costs.append(self.estimated_cost_sec)
        candidates = visible_candidates(self._video_id, self._scanned)
        return ScanObservation(
            unit_id=unit_id, action_cost_sec=self.estimated_cost_sec,
            revealed_candidate_ids=tuple(sorted(candidates.candidate_id.astype(str))),
            result_class="LOGICAL_REPLAY_OR_ESTIMATED_COST",
        )


class ScanPolicy:
    policy_id = "ABSTRACT"

    def choose(self, state: PublicScanState) -> str:
        raise NotImplementedError


def unscanned(state: PublicScanState) -> list[tuple[str, float, float]]:
    scanned = set(state.scanned_units)
    return [unit for unit in state.timeline if unit[0] not in scanned]


class SequentialPolicy(ScanPolicy):
    policy_id = "SEQUENTIAL"

    def choose(self, state: PublicScanState) -> str:
        return unscanned(state)[0][0]


class RandomPolicy(ScanPolicy):
    policy_id = "RANDOM_WITHOUT_REPLACEMENT"

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def choose(self, state: PublicScanState) -> str:
        values = unscanned(state)
        return values[self.rng.randrange(len(values))][0]


class UniformPrefixPolicy(ScanPolicy):
    policy_id = "UNIFORM_PREFIX"

    def choose(self, state: PublicScanState) -> str:
        remaining = unscanned(state)
        scanned = set(state.scanned_units)
        n = len(state.timeline)
        for levels in range(int(math.ceil(math.log2(max(2, n)))) + 1):
            step = max(1, n // (2 ** levels))
            for index in range(0, n, step):
                candidate = state.timeline[index][0]
                if candidate not in scanned:
                    return candidate
        return remaining[0][0]


class LargestGapPolicy(ScanPolicy):
    policy_id = "ANYTIME_LARGEST_GAP"

    def choose(self, state: PublicScanState) -> str:
        remaining = unscanned(state)
        if not state.scanned_units:
            return remaining[len(remaining) // 2][0]
        index_by_id = {unit[0]: i for i, unit in enumerate(state.timeline)}
        observed = [index_by_id[value] for value in state.scanned_units]
        return max(
            remaining,
            key=lambda unit: (
                min(abs(index_by_id[unit[0]] - index) for index in observed),
                -index_by_id[unit[0]],
            ),
        )[0]


def policy_for(policy_id: str, seed: int) -> ScanPolicy:
    if policy_id == "SEQUENTIAL":
        return SequentialPolicy()
    if policy_id == "RANDOM_WITHOUT_REPLACEMENT":
        return RandomPolicy(seed)
    if policy_id == "UNIFORM_PREFIX":
        return UniformPrefixPolicy()
    if policy_id == "ANYTIME_LARGEST_GAP":
        return LargestGapPolicy()
    raise KeyError(policy_id)


def transition(previous: dict[str, Any] | None, selected: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {
            "previous_unit_id": None, "previous_timestamp": None,
            "selected_timestamp": float(selected["start_sec"]),
            "seek_direction": "INITIAL", "seek_distance_sec": 0.0,
            "same_or_cross_gop": "INITIAL", "transition_class": "initial",
        }
    distance = float(selected["start_sec"]) - float(previous["start_sec"])
    direction = "FORWARD" if distance > 0 else "BACKWARD" if distance < 0 else "SAME"
    same_gop = abs(
        float(previous["nearest_keyframe_sec"]) - float(selected["nearest_keyframe_sec"])
    ) < 1e-6
    if abs(distance) <= 10.000001 and direction == "FORWARD":
        klass = "same_contiguous_region"
    elif direction == "BACKWARD":
        klass = "backward_seek"
    elif abs(distance) <= 60:
        klass = "forward_short_seek"
    else:
        klass = "forward_long_seek"
    return {
        "previous_unit_id": previous["unit_id"],
        "previous_timestamp": float(previous["start_sec"]),
        "selected_timestamp": float(selected["start_sec"]),
        "seek_direction": direction, "seek_distance_sec": abs(distance),
        "same_or_cross_gop": "SAME_GOP" if same_gop else "CROSS_GOP",
        "transition_class": klass,
    }


def environment_snapshot() -> dict[str, Any]:
    packages = {}
    for name in ["numpy", "pandas", "cv2", "torch", "ultralytics", "pyarrow"]:
        try:
            module = __import__(name)
            packages[name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            packages[name] = f"UNAVAILABLE:{exc}"
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,temperature.gpu,clocks.current.sm",
         "--format=csv,noheader"],
        capture_output=True, text=True, check=False,
    )
    return {
        "created_at_utc": utc_now(), "python": sys.version,
        "platform": sys.platform, "packages": packages,
        "gpu": gpu.stdout.strip() or "UNAVAILABLE",
        "cpu_count": os.cpu_count(),
    }
