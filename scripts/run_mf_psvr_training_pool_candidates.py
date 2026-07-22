#!/usr/bin/env python3
"""Prepare or run frozen Y8 candidate extraction for the Cycle-1 pool.

`preflight` is CPU/read-only with respect to media semantics and is safe to run
without compute authorization. `smoke` and `extract` require the explicit
`--confirm-gpu` switch and perform physical YOLOv8 inference.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
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
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.mf_psvr.training_pool import frame_bounds, unit_windows  # noqa: E402


CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
POOL_MANIFEST = CYCLE / "TRAINING_POOL_MANIFEST.csv"
POOL_AUDIT_MANIFEST = CYCLE / "AUDIT_MANIFEST.json"
PROTOCOL = CYCLE / "ORACLE_ACQUISITION_PROTOCOL.json"
TRAINING_POOL_PROXY_CONFIG = CYCLE / "TRAINING_POOL_PROXY_CONFIG.json"
PROXY_FREEZE = ROOT / "outputs/psvr_two_video_loop/proxy_finalization/PROXY_IMPLEMENTATION_FREEZE.json"
PROXY_SOURCE = ROOT / "scripts/run_psvr_two_video_proxy.py"
OUT = CYCLE / "candidates"
PER_VIDEO = OUT / "per_video"
UNIT_MANIFEST = OUT / "UNIT_MANIFEST.csv"
PLAN = OUT / "CANDIDATE_EXTRACTION_PLAN.json"
STATE = OUT / "CANDIDATE_EXTRACTION_STATE.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_proxy_module():
    freeze = load_json(PROXY_FREEZE)
    if sha256_file(PROXY_SOURCE) != freeze["implementation_sha256"]:
        raise RuntimeError("Frozen proxy implementation source changed")
    spec = importlib.util.spec_from_file_location("mf_psvr_frozen_proxy", PROXY_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen proxy implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_pool() -> pd.DataFrame:
    frame = pd.read_csv(POOL_MANIFEST, keep_default_na=False)
    frame = frame[
        (frame["source_dataset"] == "nexar_collision_prediction")
        & (frame["pool_status"] == "ELIGIBLE_PENDING_CANDIDATE_EXTRACTION")
    ].copy()
    if len(frame) != 603:
        raise RuntimeError(f"Expected 603 eligible Nexar videos, found {len(frame)}")
    if frame["content_sha256"].duplicated().any() or frame["session_id"].duplicated().any():
        raise RuntimeError("Pool contains duplicate content or provider video identity")
    return frame.sort_values("session_id").reset_index(drop=True)


def make_units(row: dict[str, Any]) -> pd.DataFrame:
    duration = float(row["duration_seconds"])
    fps = float(row["fps"])
    frame_count = int(row["frame_or_image_count"])
    rows = []
    for window in unit_windows(duration):
        start_frame, end_frame = frame_bounds(
            window.start_seconds, window.end_seconds, fps, frame_count
        )
        rows.append({
            "source_dataset": row["source_dataset"],
            "session_id": row["session_id"],
            "source_sha256": row["content_sha256"],
            "model_split_role": row["model_split_role"],
            "sampling_tag_only": row["sampling_tag_only"],
            "sampling_anchor_seconds": row["sampling_anchor_seconds"],
            "video_id": row["session_id"],
            "unit_id": window.unit_id,
            "anchor_id": f"center10_anchor_{window.unit_id:04d}",
            "anchor_time": window.anchor_seconds,
            "start_time": window.start_seconds,
            "end_time": window.end_seconds,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "duration_seconds": round(window.end_seconds - window.start_seconds, 6),
            "video_fps": fps,
            "video_frame_count": frame_count,
            "local_locator": row["local_locator"],
        })
    return pd.DataFrame(rows)


def build_unit_manifest(pool: pd.DataFrame) -> pd.DataFrame:
    parts = [make_units(row) for row in pool.to_dict("records")]
    frame = pd.concat(parts, ignore_index=True)
    if len(frame) != int(pool["nominal_oracle_units_10s"].astype(int).sum()):
        raise RuntimeError("Unit-manifest row count diverges from audited pool")
    if frame.duplicated(["source_dataset", "session_id", "unit_id"]).any():
        raise RuntimeError("Duplicate unit identity")
    return frame


def candidate_dir(session_id: str, source_sha256: str) -> Path:
    safe = session_id.replace(":", "_").replace("/", "_")
    return PER_VIDEO / f"{safe}__{source_sha256[:12]}"


def marker_valid(
    directory: Path,
    source_sha256: str,
    config_hash: str,
    expected_units: int,
) -> bool:
    marker = directory / "EXTRACTION_COMPLETE.json"
    if not marker.exists():
        return False
    try:
        value = load_json(marker)
        return (
            value["status"] == "COMPLETE"
            and value["unit_scope"] == "FULL_PROVIDER_VIDEO"
            and value["unit_scope_complete"] is True
            and int(value["units"]) == expected_units
            and int(value["expected_units"]) == expected_units
            and int(value["unit_score_rows"]) == 2 * expected_units
            and value["source_sha256"] == source_sha256
            and value["proxy_config_hash"] == config_hash
            and sha256_file(directory / "TRACK_CANDIDATES.csv") == value["track_candidates_sha256"]
            and sha256_file(directory / "UNIT_SCORES.csv") == value["unit_scores_sha256"]
            and sha256_file(directory / "UNIT_PROCESSING.json") == value["unit_processing_sha256"]
        )
    except Exception:
        return False


class SharedDetectorEngine:
    """Unit engine using the frozen implementation with one shared detector load."""

    def __init__(self, frozen: Any, session_id: str, path: Path, detector: Any):
        self._frozen = frozen
        self.family = "Y8"
        self.video_id = session_id
        self.video_path = path
        self.detector = detector
        self.initialization_seconds = 0.0
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open pool video {path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.frame_count <= 0 or self.fps <= 0:
            raise RuntimeError(f"invalid pool video metadata: {path}")
        self.interval = max(1, int(round(self.fps / frozen.SAMPLE_FPS)))

    def close(self) -> None:
        self.cap.release()

    def scan_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        # Dispatch the unchanged audited method against this compatible object.
        return self._frozen.UnitProxyEngine.scan_unit(self, unit)


def add_identities(
    frame: pd.DataFrame,
    pool_row: dict[str, Any],
    label_scope: str,
) -> pd.DataFrame:
    result = frame.copy()
    result.insert(0, "source_dataset", pool_row["source_dataset"])
    result.insert(1, "session_id", pool_row["session_id"])
    result.insert(2, "source_sha256", pool_row["content_sha256"])
    result.insert(3, "model_split_role", pool_row["model_split_role"])
    result["verification_key"] = (
        f"{pool_row['source_dataset']}|{pool_row['session_id']}|"
        + result["query_id"].astype(str)
        + "|"
        + result["unit_id"].astype(int).astype(str)
    )
    result["label_scope"] = label_scope
    if "track_id" in result:
        result["witness_track_id"] = result["track_id"].astype(int)
        result["opportunity_id"] = (
            result["verification_key"]
            + "|track:"
            + result["track_id"].astype(int).astype(str)
        )
    else:
        result["witness_track_id"] = result["top_track_id"]
        track_tokens = result["top_track_id"].map(
            lambda value: "NONE" if pd.isna(value) else str(int(value))
        )
        result["opportunity_id"] = result["verification_key"] + "|track:" + track_tokens
    return result


def extract_one(
    frozen: Any,
    detector: Any,
    pool_row: dict[str, Any],
    units: pd.DataFrame,
    config: dict[str, Any],
    expected_units: int,
    unit_scope: str,
    directory: Path,
) -> dict[str, Any]:
    path = ROOT / pool_row["local_locator"]
    if sha256_file(path) != pool_row["content_sha256"]:
        raise RuntimeError(f"Pool media changed: {pool_row['session_id']}")
    if unit_scope == "FULL_PROVIDER_VIDEO" and marker_valid(
        directory,
        pool_row["content_sha256"],
        config["training_pool_proxy_config_hash"],
        expected_units,
    ):
        return {"status": "REUSED_EXACT", "directory": str(directory)}

    engine = SharedDetectorEngine(frozen, pool_row["session_id"], path, detector)
    if abs(engine.fps - float(pool_row["fps"])) > 1e-6:
        engine.close()
        raise RuntimeError(f"FPS changed: {pool_row['session_id']}")
    if engine.frame_count != int(pool_row["frame_or_image_count"]):
        engine.close()
        raise RuntimeError(f"Frame count changed: {pool_row['session_id']}")
    candidates: list[dict[str, Any]] = []
    processing: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for unit in units.to_dict("records"):
            result = engine.scan_unit(unit)
            candidates.extend(result["candidates"])
            processing.append({key: value for key, value in result.items() if key not in {"candidates", "frame_costs"}})
    finally:
        engine.close()

    candidate_frame = pd.DataFrame(candidates)
    if candidate_frame.empty:
        candidate_frame = pd.DataFrame(columns=[
            "video_id", "query_id", "unit_id", "track_id", "class_id", "observations",
            *frozen.BASE_FEATURES, *frozen.GEOMETRY_FEATURES,
        ])
    scored, unit_scores = frozen.score_candidates(candidate_frame, "Y8", units)
    scored = add_identities(scored, pool_row, "UNIT_OUTCOME_WITH_TRACK_WITNESS")
    unit_scores = add_identities(unit_scores, pool_row, "UNIT_OUTCOME")
    atomic_csv(directory / "TRACK_CANDIDATES.csv", scored)
    atomic_csv(directory / "UNIT_SCORES.csv", unit_scores)
    atomic_json(directory / "UNIT_PROCESSING.json", processing)
    sampled_frames = sum(int(row["sampled_frames"]) for row in processing)
    decoded_frames = sum(int(row["decoded_frames"]) for row in processing)
    detector_gpu_seconds = sum(float(row["detector_gpu_seconds"]) for row in processing)
    marker = {
        "status": "COMPLETE",
        "source_dataset": pool_row["source_dataset"],
        "session_id": pool_row["session_id"],
        "source_sha256": pool_row["content_sha256"],
        "proxy_config_hash": config["training_pool_proxy_config_hash"],
        "proxy_source_sha256": sha256_file(PROXY_SOURCE),
        "unit_scope": unit_scope,
        "unit_scope_complete": unit_scope == "FULL_PROVIDER_VIDEO" and len(units) == expected_units,
        "units": len(units),
        "expected_units": expected_units,
        "track_candidate_rows": len(scored),
        "unit_score_rows": len(unit_scores),
        "sampled_frames": sampled_frames,
        "decoded_frames": decoded_frames,
        "detector_gpu_seconds": detector_gpu_seconds,
        "processing_wall_seconds": time.perf_counter() - started,
        "track_candidates_sha256": sha256_file(directory / "TRACK_CANDIDATES.csv"),
        "unit_scores_sha256": sha256_file(directory / "UNIT_SCORES.csv"),
        "unit_processing_sha256": sha256_file(directory / "UNIT_PROCESSING.json"),
        "heldout_opened": False,
    }
    atomic_json(directory / "EXTRACTION_COMPLETE.json", marker)
    return {"status": "PHYSICAL_COMPLETE", "directory": str(directory), **marker}


def valid_full_markers(
    pool: pd.DataFrame,
    units: pd.DataFrame,
    config_hash: str,
) -> list[dict[str, Any]]:
    unit_counts = units.groupby("session_id").size().to_dict()
    markers = []
    for row in pool.to_dict("records"):
        directory = candidate_dir(row["session_id"], row["content_sha256"])
        expected_units = int(unit_counts[row["session_id"]])
        if marker_valid(directory, row["content_sha256"], config_hash, expected_units):
            markers.append(load_json(directory / "EXTRACTION_COMPLETE.json"))
    return markers


def preflight() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    audit = load_json(POOL_AUDIT_MANIFEST)
    protocol = load_json(PROTOCOL)
    config = load_json(TRAINING_POOL_PROXY_CONFIG)
    freeze = load_json(PROXY_FREEZE)
    if audit["decision"] != "AUDIT_READY_ORACLE_NOT_RUN":
        raise RuntimeError("Cycle-1 pool audit is not ready")
    if protocol["status"] != "FROZEN_BEFORE_CANDIDATE_EXTRACTION_OR_ORACLE_LABELING":
        raise RuntimeError("Acquisition protocol is not frozen")
    if config["selected_proxy_config"] != "Y8":
        raise RuntimeError("Frozen candidate family is not Y8")
    if sha256_file(PROXY_SOURCE) != freeze["implementation_sha256"]:
        raise RuntimeError("Frozen proxy source changed")
    if sha256_file(Path(config["weight_path"])) != config["weight_sha256"]:
        raise RuntimeError("Frozen Y8 weights changed")
    pool = load_pool()
    units = build_unit_manifest(pool)
    atomic_csv(UNIT_MANIFEST, units)
    intervals = np.maximum(1, np.rint(pool["fps"].astype(float) / float(config["sample_fps"]))).astype(int)
    interval_by_session = dict(zip(pool["session_id"], intervals))
    planned_sampled_frames = sum(
        ((int(row.end_frame) - int(row.start_frame)) // interval_by_session[row.session_id]) + 1
        for row in units.itertuples()
    )
    cost_plan = load_json(CYCLE / "COST_AND_SUPPORT_PLAN.json")
    plan = {
        "plan_id": "MF_PSVR_CYCLE1_Y8_EXTRACTION_V1",
        "status": "PREFLIGHT_PASS_GPU_NOT_RUN",
        "pool_manifest_sha256": sha256_file(POOL_MANIFEST),
        "pool_audit_manifest_sha256": sha256_file(POOL_AUDIT_MANIFEST),
        "acquisition_protocol_sha256": sha256_file(PROTOCOL),
        "proxy_config_hash": config["training_pool_proxy_config_hash"],
        "proxy_source_sha256": sha256_file(PROXY_SOURCE),
        "weight_sha256": config["weight_sha256"],
        "tracker_sha256": config["tracker"]["implementation_sha256"],
        "provider_videos": len(pool),
        "units": len(units),
        "query_unit_rows_expected": 2 * len(units),
        "planned_sampled_frames": int(planned_sampled_frames),
        "estimated_detector_gpu_seconds": cost_plan[
            "y8_detector_gpu_seconds_frame_component"
        ],
        "estimated_initialization_seconds": cost_plan["y8_initialization_seconds"],
        "estimated_p95_wall_seconds_plus_initialization_and_profiled_short_clip_overhead": (
            cost_plan[
                "y8_p95_wall_seconds_plus_initialization_and_profiled_short_clip_overhead"
            ]
        ),
        "short_clip_overhead_profile": cost_plan["short_clip_overhead_profile"],
        "shared_detector_load": True,
        "resume_scope": "exact source SHA and proxy-config hash per provider video",
        "semantic_labels_accessed": False,
        "heldout_opened": False,
    }
    if int(cost_plan["planned_sampled_frames"]) != int(planned_sampled_frames):
        raise RuntimeError("Candidate preflight frame plan diverges from the audited cost plan")
    plan["plan_hash"] = canonical_hash(plan)
    atomic_json(PLAN, plan)
    markers = valid_full_markers(pool, units, config["training_pool_proxy_config_hash"])
    completed = len(markers)
    atomic_json(STATE, {
        "status": (
            "COMPLETE" if completed == len(pool)
            else "PARTIAL" if completed
            else "PREFLIGHT_PASS_GPU_NOT_RUN"
        ),
        "physical_y8_frames": sum(int(marker["sampled_frames"]) for marker in markers),
        "decoded_frames": sum(int(marker["decoded_frames"]) for marker in markers),
        "detector_gpu_seconds": sum(float(marker["detector_gpu_seconds"]) for marker in markers),
        "completed_provider_videos": completed,
        "total_provider_videos": len(pool),
        "query_unit_rows": sum(int(marker["unit_score_rows"]) for marker in markers),
        "oracle_labels": 0,
        "heldout_opened": False,
    })
    return pool, units, plan


def merge_outputs(pool: pd.DataFrame, units: pd.DataFrame, config_hash: str) -> dict[str, Any]:
    tracks = []
    scores = []
    markers = []
    unit_counts = units.groupby("session_id").size().to_dict()
    for row in pool.to_dict("records"):
        directory = candidate_dir(row["session_id"], row["content_sha256"])
        if not marker_valid(
            directory,
            row["content_sha256"],
            config_hash,
            int(unit_counts[row["session_id"]]),
        ):
            continue
        tracks.append(pd.read_csv(directory / "TRACK_CANDIDATES.csv"))
        scores.append(pd.read_csv(directory / "UNIT_SCORES.csv"))
        markers.append(load_json(directory / "EXTRACTION_COMPLETE.json"))
    track_frame = pd.concat(tracks, ignore_index=True) if tracks else pd.DataFrame()
    score_frame = pd.concat(scores, ignore_index=True) if scores else pd.DataFrame()
    if not score_frame.empty and score_frame["verification_key"].duplicated().any():
        raise RuntimeError("Merged unit scores contain duplicate verification keys")
    atomic_csv(OUT / "TRACK_CANDIDATES.csv", track_frame)
    atomic_csv(OUT / "UNIT_SCORES.csv", score_frame)
    report = {
        "status": "COMPLETE" if len(markers) == len(pool) else "PARTIAL",
        "completed_provider_videos": len(markers),
        "total_provider_videos": len(pool),
        "track_candidate_rows": len(track_frame),
        "unit_score_rows": len(score_frame),
        "physical_y8_frames": sum(int(marker["sampled_frames"]) for marker in markers),
        "decoded_frames": sum(int(marker["decoded_frames"]) for marker in markers),
        "detector_gpu_seconds": sum(float(marker["detector_gpu_seconds"]) for marker in markers),
        "proxy_config_hash": config_hash,
        "track_candidates_sha256": sha256_file(OUT / "TRACK_CANDIDATES.csv"),
        "unit_scores_sha256": sha256_file(OUT / "UNIT_SCORES.csv"),
        "semantic_labels_accessed": False,
        "heldout_opened": False,
    }
    atomic_json(STATE, report)
    return report


def run_physical(mode: str, limit_videos: int | None) -> None:
    pool, all_units, plan = preflight()
    if mode == "smoke":
        limit_videos = 1 if limit_videos is None else limit_videos
    selected_pool = pool if limit_videos is None else pool.iloc[:limit_videos].copy()
    frozen = load_proxy_module()
    config = load_json(TRAINING_POOL_PROXY_CONFIG)
    load_started = time.perf_counter()
    detector = frozen.Y8Detector(Path(config["weight_path"]))
    initialization_seconds = time.perf_counter() - load_started
    results = []
    for index, row in enumerate(selected_pool.to_dict("records"), start=1):
        full_units = all_units[all_units["session_id"] == row["session_id"]].copy()
        units = full_units
        unit_scope = "FULL_PROVIDER_VIDEO"
        directory = candidate_dir(row["session_id"], row["content_sha256"])
        if mode == "smoke":
            units = units.iloc[:1].copy()
            unit_scope = "SMOKE_FIRST_UNIT_ONLY"
            directory = OUT / "smoke" / candidate_dir(
                row["session_id"], row["content_sha256"]
            ).name
        result = extract_one(
            frozen,
            detector,
            row,
            units,
            config,
            expected_units=len(full_units),
            unit_scope=unit_scope,
            directory=directory,
        )
        results.append(result)
        print(json.dumps({
            "provider_video": index,
            "selected_provider_videos": len(selected_pool),
            "session_id": row["session_id"],
            "status": result["status"],
        }), flush=True)
    report = merge_outputs(pool, all_units, config["training_pool_proxy_config_hash"])
    report["this_run_initialization_seconds"] = initialization_seconds
    report["this_run_selected_provider_videos"] = len(selected_pool)
    report["this_run_results"] = results
    report["preflight_plan_hash"] = plan["plan_hash"]
    atomic_json(OUT / f"{mode.upper()}_RUN_REPORT.json", report)
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["preflight", "smoke", "extract"])
    parser.add_argument("--confirm-gpu", action="store_true")
    parser.add_argument("--limit-videos", type=int)
    args = parser.parse_args()
    if args.limit_videos is not None and args.limit_videos < 1:
        raise SystemExit("--limit-videos must be positive")
    if args.stage == "preflight":
        _, _, plan = preflight()
        print(json.dumps(plan, indent=2))
        return
    if not args.confirm_gpu:
        raise SystemExit(
            "Physical Y8 inference was not authorized. Re-run with --confirm-gpu only after explicit authority."
        )
    run_physical(args.stage, args.limit_videos)


if __name__ == "__main__":
    main()
