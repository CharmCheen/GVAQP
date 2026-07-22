#!/usr/bin/env python3
"""Materialize exact-sample YOLO/ByteTrack temporal features for MF-PSVR Stage A.

The frozen full-pool extractor intentionally persisted only aggregate track
features and discarded detector confidence and per-frame trajectories.  This
bounded supplement replays *only* the already frozen 96 Stage-A units, with
the identical source, weight, proxy, tracker, unit, and witness identities.
It never reads oracle labels and cannot add a semantic sample or oracle call.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
CANDIDATES = CYCLE / "candidates"
STAGE = CYCLE / "stage_a"
MODEL_OUT = STAGE / "modeling"
PER_CALL = MODEL_OUT / "temporal_per_call"
SAMPLE = STAGE / "STAGE_A_FROZEN_SAMPLE.csv"
OPPORTUNITIES = STAGE / "STAGE_A_QUERY_OPPORTUNITIES.csv"
FREEZE = STAGE / "STAGE_A_FREEZE_MANIFEST.json"
CANDIDATE_AUDIT = CANDIDATES / "CANDIDATE_EXTRACTION_COMPLETION_AUDIT.json"
UNIT_MANIFEST = CANDIDATES / "UNIT_MANIFEST.csv"
TRACK_CANDIDATES = CANDIDATES / "TRACK_CANDIDATES.csv"
PROXY_CONFIG = CYCLE / "TRAINING_POOL_PROXY_CONFIG.json"
PROXY_FREEZE = ROOT / "outputs/psvr_two_video_loop/proxy_finalization/PROXY_IMPLEMENTATION_FREEZE.json"
PROXY_SOURCE = ROOT / "scripts/run_psvr_two_video_proxy.py"
GLOBAL_NPZ = MODEL_OUT / "STAGE_A_TEMPORAL_SEQUENCES.npz"
GLOBAL_INDEX = MODEL_OUT / "STAGE_A_TEMPORAL_INDEX.csv"
FEATURE_SCHEMA = MODEL_OUT / "STAGE_A_TEMPORAL_FEATURE_SCHEMA.json"
AUDIT = MODEL_OUT / "STAGE_A_TEMPORAL_MATERIALIZATION_AUDIT.json"
COST = MODEL_OUT / "STAGE_A_TEMPORAL_COST.json"
LOCK = MODEL_OUT / ".temporal_materializer.lock"

MAX_STEPS = 64
FEATURES = [
    "frame_valid",
    "witness_observed",
    "raw_yolo_confidence",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_width",
    "bbox_height",
    "bbox_area",
    "bbox_bottom",
    "delta_center_x_per_second",
    "delta_center_y_per_second",
    "box_growth_per_second",
    "height_growth_per_second",
    "front_region_occupancy",
    "approximate_ttc_urgency",
    "elapsed_fraction",
    "active_query_track_count",
    "max_query_raw_yolo_confidence",
]
QUERY_CLASSES = {"Q1": {1, 2, 3, 5, 7}, "Q2": {0, 1, 3}}
RAW_AGGREGATE_FEATURES = [
    "observations",
    "track_persistence",
    "path_directed_lateral_motion",
    "box_growth",
    "front_region_occupancy",
    "approximate_ttc_urgency",
    "lane_relative_motion",
    "boundary_crossing",
    "ego_corridor_overlap",
    "road_geometry_reliability",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode(),
    )


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".npz", dir=path.parent)
    os.close(descriptor)
    try:
        np.savez_compressed(temporary, **arrays)
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_proxy_module(expected_hash: str):
    if sha256_file(PROXY_SOURCE) != expected_hash:
        raise RuntimeError("Frozen proxy source changed")
    spec = importlib.util.spec_from_file_location("mf_psvr_temporal_frozen_proxy", PROXY_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen proxy implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_scope() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    candidate_audit = load_json(CANDIDATE_AUDIT)
    freeze = load_json(FREEZE)
    config = load_json(PROXY_CONFIG)
    proxy_freeze = load_json(PROXY_FREEZE)
    if candidate_audit.get("status") != "PASS":
        raise RuntimeError("Independent candidate completion audit is not PASS")
    if freeze.get("status") != "FROZEN_ORACLE_NOT_RUN":
        raise RuntimeError("Stage-A sample is not in the exact frozen state")
    if sha256_file(SAMPLE) != freeze["sample_sha256"]:
        raise RuntimeError("Frozen Stage-A sample changed")
    if sha256_file(OPPORTUNITIES) != freeze["query_opportunities_sha256"]:
        raise RuntimeError("Frozen query opportunity table changed")
    if sha256_file(UNIT_MANIFEST) != freeze["unit_manifest_sha256"]:
        raise RuntimeError("Frozen unit manifest changed")
    if sha256_file(PROXY_SOURCE) != proxy_freeze["implementation_sha256"]:
        raise RuntimeError("Proxy implementation no longer matches its freeze")
    if sha256_file(Path(config["weight_path"])) != config["weight_sha256"]:
        raise RuntimeError("Frozen Y8 weight changed")
    if sha256_file(Path(config["tracker"]["implementation_path"])) != config["tracker"]["implementation_sha256"]:
        raise RuntimeError("Frozen ByteTrack source changed")
    sample = pd.read_csv(SAMPLE, keep_default_na=False)
    opportunities = pd.read_csv(OPPORTUNITIES, keep_default_na=False)
    units = pd.read_csv(UNIT_MANIFEST, keep_default_na=False)
    if len(sample) != 96 or sample["physical_call_id"].nunique() != 96:
        raise RuntimeError("Temporal scope is not exactly the frozen 96-call sample")
    if len(opportunities) != 192 or opportunities["verification_key"].nunique() != 192:
        raise RuntimeError("Temporal scope is not exactly the frozen 192 semantic samples")
    if set(opportunities["query_id"]) != {"Q1", "Q2"}:
        raise RuntimeError("Temporal query scope changed")
    if sample.duplicated(["source_dataset", "session_id", "unit_id"]).any():
        raise RuntimeError("Frozen physical-call units are not unique")
    unit_subset = units.merge(
        sample[["physical_call_id", "source_dataset", "session_id", "unit_id"]],
        on=["source_dataset", "session_id", "unit_id"],
        how="inner",
        validate="one_to_one",
    )
    if len(unit_subset) != 96:
        raise RuntimeError("Frozen sample does not map one-to-one to unit manifest")
    return sample, opportunities, unit_subset, config, freeze


def call_paths(call_id: str) -> tuple[Path, Path]:
    directory = PER_CALL / call_id
    return directory / "SEQUENCES.npz", directory / "MATERIALIZATION_COMPLETE.json"


def valid_call_marker(
    marker_path: Path,
    npz_path: Path,
    row: dict[str, Any],
    freeze_hash: str,
    config: dict[str, Any],
) -> bool:
    if not marker_path.is_file() or not npz_path.is_file():
        return False
    try:
        marker = load_json(marker_path)
        if not (
            marker["status"] == "COMPLETE"
            and marker["physical_call_id"] == row["physical_call_id"]
            and marker["source_sha256"] == row["source_sha256"]
            and int(marker["unit_id"]) == int(row["unit_id"])
            and marker["freeze_hash"] == freeze_hash
            and marker["weight_sha256"] == config["weight_sha256"]
            and marker["tracker_sha256"] == config["tracker"]["implementation_sha256"]
            and marker["proxy_source_sha256"] == sha256_file(PROXY_SOURCE)
            and marker["sequences_sha256"] == sha256_file(npz_path)
            and marker["aggregate_reproduction_status"] == "PASS"
            and marker["heldout_opened"] is False
        ):
            return False
        with np.load(npz_path, allow_pickle=False) as value:
            return (
                value["sequences"].shape == (2, MAX_STEPS, len(FEATURES))
                and value["frame_indices"].shape == (2, MAX_STEPS)
                and value["valid_mask"].shape == (2, MAX_STEPS)
                and value["raw_yolo_score"].shape == (2,)
                and value["witness_class_id"].shape == (2,)
            )
    except Exception:
        return False


def scan_call(
    frozen: Any,
    detector: Any,
    sample_row: dict[str, Any],
    unit_row: dict[str, Any],
    opportunity_rows: list[dict[str, Any]],
    persisted_tracks: pd.DataFrame,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    video_path = ROOT / str(unit_row["local_locator"])
    if sha256_file(video_path) != sample_row["source_sha256"]:
        raise RuntimeError(f"Selected source changed: {sample_row['physical_call_id']}")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if abs(fps - float(unit_row["video_fps"])) > 1e-6 or frame_count != int(unit_row["video_frame_count"]):
        capture.release()
        raise RuntimeError("Selected source metadata changed")
    start_frame = int(unit_row["start_frame"])
    requested_end = int(unit_row["end_frame"])
    end_frame = min(requested_end, frame_count - 1)
    if start_frame < 0 or end_frame < start_frame or requested_end > frame_count:
        capture.release()
        raise RuntimeError("Frozen unit frame bounds are invalid")
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame):
        capture.release()
        raise RuntimeError("OpenCV seek failed")
    if abs(float(capture.get(cv2.CAP_PROP_POS_FRAMES)) - start_frame) > 0.5:
        capture.release()
        raise RuntimeError("OpenCV seek landed on a different frame")

    query_order = ["Q1", "Q2"]
    witness_by_query: dict[str, int | None] = {}
    for row in opportunity_rows:
        value = row["witness_track_id"]
        witness_by_query[row["query_id"]] = None if value == "" or pd.isna(value) else int(float(value))
    sequences = np.zeros((2, MAX_STEPS, len(FEATURES)), dtype=np.float32)
    frame_indices = np.full((2, MAX_STEPS), -1, dtype=np.int64)
    valid_mask = np.zeros((2, MAX_STEPS), dtype=np.uint8)
    raw_yolo_score = np.zeros(2, dtype=np.float32)
    witness_class_id = np.full(2, -1, dtype=np.int64)
    tracker = frozen.make_tracker()
    history: dict[int, dict[str, float]] = {}
    candidates: dict[tuple[str, int], dict[str, Any]] = {}
    sampled_steps = 0
    detector_gpu_seconds = 0.0
    started = time.perf_counter()
    interval = max(1, int(round(fps / float(frozen.SAMPLE_FPS))))
    try:
        for frame_index in range(start_frame, end_frame + 1):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Decode failed at frame {frame_index}")
            if (frame_index - start_frame) % interval:
                continue
            if sampled_steps >= MAX_STEPS:
                raise RuntimeError("Frozen sequence exceeds MAX_STEPS")
            boxes, scores, classes, masks, detector_gpu = detector.detect(frame)
            detector_gpu_seconds += float(detector_gpu)
            active = tracker.update(frozen.TrackerDetections(boxes, scores, classes))
            geometry = frozen.road_geometry(masks)
            height, width = frame.shape[:2]
            timestamp = frame_index / fps
            active_by_query: dict[str, list[np.ndarray]] = {"Q1": [], "Q2": []}
            for track in active:
                bbox = np.asarray(track[:4], dtype=float)
                track_id = int(track[4])
                class_id = int(track[6])
                previous = history.get(track_id)
                for query_id in query_order:
                    if class_id not in QUERY_CLASSES[query_id]:
                        continue
                    active_by_query[query_id].append(track)
                    key = (query_id, track_id)
                    if key not in candidates:
                        candidates[key] = frozen.new_candidate(
                            str(unit_row["video_id"]), query_id, int(unit_row["unit_id"]), track_id, class_id
                        )
                    frozen.update_candidate(
                        candidates[key], bbox, timestamp, previous, geometry, frame.shape[:2]
                    )
                center_x = ((bbox[0] + bbox[2]) / 2.0) / width
                center_y = ((bbox[1] + bbox[3]) / 2.0) / height
                box_width = max(0.0, (bbox[2] - bbox[0]) / width)
                box_height = max(0.0, (bbox[3] - bbox[1]) / height)
                history[track_id] = {
                    "timestamp": timestamp,
                    "center_x": center_x,
                    "center_y": center_y,
                    "area": max(1e-12, box_width * box_height),
                    "box_height": max(1e-9, box_height),
                    "lane_center": geometry["lane_center"],
                    "left_boundary": geometry["left_boundary"],
                    "right_boundary": geometry["right_boundary"],
                }

            for query_index, query_id in enumerate(query_order):
                frame_indices[query_index, sampled_steps] = frame_index
                valid_mask[query_index, sampled_steps] = 1
                sequences[query_index, sampled_steps, FEATURES.index("frame_valid")] = 1.0
                sequences[query_index, sampled_steps, FEATURES.index("elapsed_fraction")] = (
                    (frame_index - start_frame) / max(1, end_frame - start_frame)
                )
                eligible_detection = np.isin(classes.astype(int), list(QUERY_CLASSES[query_id]))
                if eligible_detection.any():
                    raw_yolo_score[query_index] = max(
                        raw_yolo_score[query_index], float(np.max(scores[eligible_detection]))
                    )
                query_tracks = active_by_query[query_id]
                sequences[query_index, sampled_steps, FEATURES.index("active_query_track_count")] = len(query_tracks)
                if query_tracks:
                    sequences[query_index, sampled_steps, FEATURES.index("max_query_raw_yolo_confidence")] = max(
                        float(track[5]) for track in query_tracks
                    )
                witness = witness_by_query[query_id]
                matching = next((track for track in query_tracks if int(track[4]) == witness), None)
                if matching is None:
                    continue
                bbox = np.asarray(matching[:4], dtype=float)
                track_id = int(matching[4])
                confidence = float(matching[5])
                class_id = int(matching[6])
                witness_class_id[query_index] = class_id
                cx = ((bbox[0] + bbox[2]) / 2.0) / width
                cy = ((bbox[1] + bbox[3]) / 2.0) / height
                bw = max(0.0, (bbox[2] - bbox[0]) / width)
                bh = max(0.0, (bbox[3] - bbox[1]) / height)
                area = bw * bh
                bottom = bbox[3] / height
                previous = None
                if sampled_steps > 0:
                    previous_seen = sequences[query_index, sampled_steps - 1, FEATURES.index("witness_observed")] > 0
                    if previous_seen:
                        previous = sequences[query_index, sampled_steps - 1]
                delta_seconds = interval / fps
                delta_cx = delta_cy = growth = height_growth = ttc = 0.0
                if previous is not None:
                    delta_cx = (cx - float(previous[FEATURES.index("bbox_center_x")])) / delta_seconds
                    delta_cy = (cy - float(previous[FEATURES.index("bbox_center_y")])) / delta_seconds
                    previous_area = max(1e-12, float(previous[FEATURES.index("bbox_area")]))
                    previous_height = max(1e-9, float(previous[FEATURES.index("bbox_height")]))
                    growth = max(0.0, area / previous_area - 1.0) / delta_seconds
                    height_growth = max(0.0, bh / previous_height - 1.0) / delta_seconds
                    ttc = max(0.0, bh - previous_height) / delta_seconds / max(bh, 1e-9)
                corridor = max(0.0, 1.0 - abs(cx - 0.5) / 0.3)
                values = {
                    "witness_observed": 1.0,
                    "raw_yolo_confidence": confidence,
                    "bbox_center_x": cx,
                    "bbox_center_y": cy,
                    "bbox_width": bw,
                    "bbox_height": bh,
                    "bbox_area": area,
                    "bbox_bottom": bottom,
                    "delta_center_x_per_second": delta_cx,
                    "delta_center_y_per_second": delta_cy,
                    "box_growth_per_second": growth,
                    "height_growth_per_second": height_growth,
                    "front_region_occupancy": corridor * bottom,
                    "approximate_ttc_urgency": ttc,
                }
                for key, value in values.items():
                    sequences[query_index, sampled_steps, FEATURES.index(key)] = value
            sampled_steps += 1
    finally:
        capture.release()

    aggregate_errors: list[str] = []
    for query_id in query_order:
        witness = witness_by_query[query_id]
        if witness is None:
            continue
        key = (query_id, witness)
        if key not in candidates:
            aggregate_errors.append(f"{query_id}:witness_not_reproduced")
            continue
        persisted = persisted_tracks[
            (persisted_tracks["query_id"] == query_id)
            & (pd.to_numeric(persisted_tracks["track_id"], errors="coerce") == witness)
        ]
        if len(persisted) != 1:
            aggregate_errors.append(f"{query_id}:persisted_witness_rows={len(persisted)}")
            continue
        expected = candidates[key]
        observed = persisted.iloc[0]
        if int(observed["class_id"]) != int(expected["class_id"]):
            aggregate_errors.append(f"{query_id}:class_id")
        for field in RAW_AGGREGATE_FEATURES:
            if not math.isclose(float(observed[field]), float(expected[field]), rel_tol=1e-6, abs_tol=1e-6):
                aggregate_errors.append(f"{query_id}:{field}")
    if aggregate_errors:
        raise RuntimeError("Frozen aggregate reproduction failed: " + ",".join(aggregate_errors))

    arrays = {
        "sequences": sequences,
        "frame_indices": frame_indices,
        "valid_mask": valid_mask,
        "raw_yolo_score": raw_yolo_score,
        "witness_class_id": witness_class_id,
        "query_code": np.asarray([1, 2], dtype=np.int64),
    }
    metadata = {
        "sampled_steps": sampled_steps,
        "detector_gpu_seconds": detector_gpu_seconds,
        "processing_wall_seconds": time.perf_counter() - started,
        "aggregate_reproduction_status": "PASS",
        "aggregate_errors": aggregate_errors,
        "raw_yolo_score": {query_id: float(raw_yolo_score[index]) for index, query_id in enumerate(query_order)},
        "witness_class_id": {query_id: int(witness_class_id[index]) for index, query_id in enumerate(query_order)},
        "observed_steps": {
            query_id: int(sequences[index, :, FEATURES.index("witness_observed")].sum())
            for index, query_id in enumerate(query_order)
        },
    }
    return arrays, metadata


def verify(write_global: bool = False) -> dict[str, Any]:
    sample, opportunities, _, config, freeze = validate_scope()
    rows: list[dict[str, Any]] = []
    sequences: list[np.ndarray] = []
    frame_indices: list[np.ndarray] = []
    valid_masks: list[np.ndarray] = []
    raw_scores: list[float] = []
    witness_classes: list[int] = []
    query_codes: list[int] = []
    for sample_row in sample.sort_values("physical_call_id").to_dict("records"):
        npz_path, marker_path = call_paths(sample_row["physical_call_id"])
        if not valid_call_marker(marker_path, npz_path, sample_row, freeze["freeze_hash"], config):
            raise RuntimeError(f"Invalid temporal call marker: {sample_row['physical_call_id']}")
        marker = load_json(marker_path)
        call_opportunities = opportunities[
            opportunities["physical_call_id"] == sample_row["physical_call_id"]
        ].sort_values("query_id")
        with np.load(npz_path, allow_pickle=False) as value:
            for query_index, opportunity in enumerate(call_opportunities.to_dict("records")):
                sequences.append(value["sequences"][query_index])
                frame_indices.append(value["frame_indices"][query_index])
                valid_masks.append(value["valid_mask"][query_index])
                raw_scores.append(float(value["raw_yolo_score"][query_index]))
                witness_classes.append(int(value["witness_class_id"][query_index]))
                query_codes.append(int(value["query_code"][query_index]))
                rows.append({
                    "semantic_sample_id": opportunity["verification_key"],
                    "physical_call_id": sample_row["physical_call_id"],
                    "source_dataset": sample_row["source_dataset"],
                    "session_id": sample_row["session_id"],
                    "unit_id": int(sample_row["unit_id"]),
                    "query_id": opportunity["query_id"],
                    "witness_track_id": opportunity["witness_track_id"],
                    "witness_class_id": witness_classes[-1],
                    "raw_yolo_score": raw_scores[-1],
                    "sampled_steps": int(marker["sampled_steps"]),
                    "witness_observed_steps": int(marker["observed_steps"][opportunity["query_id"]]),
                    "call_sequences_sha256": marker["sequences_sha256"],
                })
    index = pd.DataFrame(rows)
    if len(index) != 192 or index["semantic_sample_id"].nunique() != 192:
        raise RuntimeError("Temporal global semantic sample universe changed")
    stacked = {
        "sequences": np.stack(sequences).astype(np.float32),
        "frame_indices": np.stack(frame_indices).astype(np.int64),
        "valid_mask": np.stack(valid_masks).astype(np.uint8),
        "raw_yolo_score": np.asarray(raw_scores, dtype=np.float32),
        "witness_class_id": np.asarray(witness_classes, dtype=np.int64),
        "query_code": np.asarray(query_codes, dtype=np.int64),
        "semantic_sample_id": index["semantic_sample_id"].to_numpy(dtype="U256"),
    }
    marker_rows = [
        load_json(call_paths(call_id)[1])
        for call_id in sample.sort_values("physical_call_id")["physical_call_id"]
    ]
    schema = {
        "schema_id": "MF_PSVR_STAGE_A_TEMPORAL_FEATURE_SCHEMA_V1",
        "sequence_shape": [192, MAX_STEPS, len(FEATURES)],
        "feature_order": FEATURES,
        "sample_rate_fps": 5,
        "padding": "right zero padding to 64 steps; frame_valid and valid_mask distinguish padding",
        "witness_policy": "pre-label frozen query witness track; no label-aware track selection",
        "raw_yolo_score": "maximum post-NMS YOLOv8 detection confidence among query-eligible classes in the frozen unit",
        "query_conditioning": "query_code plus query-specific class eligibility and witness sequence",
        "runtime_visible_only": True,
        "identity_fields_excluded_from_model_inputs": ["source_dataset", "session_id", "physical_call_id", "semantic_sample_id"],
    }
    cost = {
        "cost_id": "MF_PSVR_STAGE_A_TEMPORAL_MATERIALIZATION_COST_V1",
        "status": "COMPLETE",
        "provider_unit_replays": 96,
        "semantic_samples": 192,
        "detector_gpu_seconds": sum(float(row["detector_gpu_seconds"]) for row in marker_rows),
        "summed_processing_wall_seconds": sum(float(row["processing_wall_seconds"]) for row in marker_rows),
        "sampled_frames": sum(int(row["sampled_steps"]) for row in marker_rows),
        "heldout_opened": False,
    }
    if not write_global:
        for path in (GLOBAL_NPZ, GLOBAL_INDEX, FEATURE_SCHEMA, COST, AUDIT):
            if not path.is_file():
                raise RuntimeError(f"Temporal finalized artifact is missing: {path.name}")
        with np.load(GLOBAL_NPZ, allow_pickle=False) as existing:
            if set(existing.files) != set(stacked):
                raise RuntimeError("Temporal global array universe changed")
            for key, value in stacked.items():
                if not np.array_equal(existing[key], value):
                    raise RuntimeError(f"Temporal global array changed: {key}")
        existing_index = pd.read_csv(GLOBAL_INDEX, keep_default_na=False)
        pd.testing.assert_frame_equal(existing_index, index, check_dtype=False)
        if load_json(FEATURE_SCHEMA) != schema:
            raise RuntimeError("Temporal feature schema does not recompute")
        if load_json(COST) != cost:
            raise RuntimeError("Temporal cost artifact does not recompute")
        audit = load_json(AUDIT)
        claimed_hash = audit.get("audit_hash")
        payload = {key: value for key, value in audit.items() if key != "audit_hash"}
        if claimed_hash != canonical_hash(payload) or audit.get("status") != "PASS":
            raise RuntimeError("Temporal audit self-hash is invalid")
        bound = {
            "global_sequences_sha256": sha256_file(GLOBAL_NPZ),
            "global_index_sha256": sha256_file(GLOBAL_INDEX),
            "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
            "cost_sha256": sha256_file(COST),
        }
        if any(audit.get(key) != value for key, value in bound.items()):
            raise RuntimeError("Temporal audit artifact hashes changed")
        return audit

    atomic_npz(GLOBAL_NPZ, **stacked)
    atomic_csv(GLOBAL_INDEX, index)
    atomic_json(FEATURE_SCHEMA, schema)
    atomic_json(COST, cost)
    audit = {
        "audit_id": "MF_PSVR_STAGE_A_TEMPORAL_MATERIALIZATION_AUDIT_V1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "scope_reason": "Required because the frozen full-pool extractor discarded per-frame trajectories and raw detector confidence.",
        "frozen_physical_calls": 96,
        "materialized_provider_units": 96,
        "semantic_samples": 192,
        "new_provider_videos": 0,
        "new_units": 0,
        "new_anchors": 0,
        "new_oracle_calls": 0,
        "oracle_labels_read": 0,
        "aggregate_reproduction_failures": 0,
        "source_hashes_validated": 96,
        "weight_sha256": config["weight_sha256"],
        "tracker_sha256": config["tracker"]["implementation_sha256"],
        "proxy_source_sha256": sha256_file(PROXY_SOURCE),
        "freeze_hash": freeze["freeze_hash"],
        "global_sequences_sha256": sha256_file(GLOBAL_NPZ),
        "global_index_sha256": sha256_file(GLOBAL_INDEX),
        "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
        "cost_sha256": sha256_file(COST),
        "heldout_opened": False,
    }
    audit["audit_hash"] = canonical_hash(audit)
    atomic_json(AUDIT, audit)
    return audit


def materialize() -> dict[str, Any]:
    sample, opportunities, units, config, freeze = validate_scope()
    frozen = load_proxy_module(load_json(PROXY_FREEZE)["implementation_sha256"])
    load_started = time.perf_counter()
    detector = frozen.Y8Detector(Path(config["weight_path"]))
    detector_initialization_seconds = time.perf_counter() - load_started
    all_tracks = pd.read_csv(TRACK_CANDIDATES, keep_default_na=False)
    unit_by_call = units.set_index("physical_call_id").to_dict("index")
    for ordinal, sample_row in enumerate(sample.sort_values("physical_call_id").to_dict("records"), start=1):
        call_id = sample_row["physical_call_id"]
        npz_path, marker_path = call_paths(call_id)
        if valid_call_marker(marker_path, npz_path, sample_row, freeze["freeze_hash"], config):
            print(json.dumps({"physical_call_id": call_id, "status": "REUSED_EXACT"}), flush=True)
            continue
        unit_row = unit_by_call[call_id]
        call_opportunities = opportunities[opportunities["physical_call_id"] == call_id].sort_values("query_id")
        persisted = all_tracks[
            (all_tracks["source_dataset"] == sample_row["source_dataset"])
            & (all_tracks["session_id"] == sample_row["session_id"])
            & (pd.to_numeric(all_tracks["unit_id"], errors="coerce") == int(sample_row["unit_id"]))
        ]
        arrays, metadata = scan_call(
            frozen,
            detector,
            sample_row,
            unit_row,
            call_opportunities.to_dict("records"),
            persisted,
        )
        atomic_npz(npz_path, **arrays)
        marker = {
            "status": "COMPLETE",
            "physical_call_id": call_id,
            "source_dataset": sample_row["source_dataset"],
            "session_id": sample_row["session_id"],
            "source_sha256": sample_row["source_sha256"],
            "unit_id": int(sample_row["unit_id"]),
            "freeze_hash": freeze["freeze_hash"],
            "weight_sha256": config["weight_sha256"],
            "tracker_sha256": config["tracker"]["implementation_sha256"],
            "proxy_source_sha256": sha256_file(PROXY_SOURCE),
            "sequences_sha256": sha256_file(npz_path),
            "detector_initialization_seconds": detector_initialization_seconds if ordinal == 1 else 0.0,
            "heldout_opened": False,
            **metadata,
        }
        marker["marker_hash"] = canonical_hash(marker)
        atomic_json(marker_path, marker)
        print(json.dumps({"physical_call_id": call_id, "status": "COMPLETE", "sampled_steps": metadata["sampled_steps"]}), flush=True)
    return verify(write_global=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["materialize", "verify"])
    parser.add_argument("--confirm-gpu", action="store_true")
    args = parser.parse_args()
    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit("Another temporal materializer owns the lock") from exc
        if args.stage == "materialize":
            if not args.confirm_gpu:
                raise SystemExit("Physical Y8 replay requires --confirm-gpu")
            result = materialize()
        else:
            result = verify(write_global=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
