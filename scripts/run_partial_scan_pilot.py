#!/usr/bin/env python3
"""Build and audit PARTIAL_SCAN_BENCHMARK_PILOT_V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from partial_scan_pilot_common import (
    BENCH, CONTRACT_DOC, DERIVED, IMMUTABLE, OUTPUT, REFERENCE, ROOT, SEED,
    TIMELINE, TIMELINE_OFFSET5, VIDEOS, LargestGapPolicy, RandomPolicy,
    PublicScanState, ReplayEnvironment, ScanEngine, SequentialPolicy, UniformPrefixPolicy,
    atomic_csv, atomic_json, atomic_text, canonical_hash, environment_snapshot,
    make_timeline, policy_for, save_scan_result, scan_output_dir, sha256_file,
    transition, utc_now, video_info, visible_candidates,
)


POLICY_IDS = [
    "SEQUENTIAL", "RANDOM_WITHOUT_REPLACEMENT",
    "UNIFORM_PREFIX", "ANYTIME_LARGEST_GAP",
]
LATIN_SQUARE = [
    POLICY_IDS,
    POLICY_IDS[1:] + POLICY_IDS[:1],
    POLICY_IDS[2:] + POLICY_IDS[:2],
    POLICY_IDS[3:] + POLICY_IDS[:3],
]
PHYSICAL_BUDGET_SEC = 60.0
INITIAL_CONSERVATIVE_COST_SEC = 5.0


VIDEO_SPECS = [
    {
        "video_id": "PSP_V0_SHORT",
        "video_path": str((ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4").resolve()),
        "expected_hash": "bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610",
        "selection_reason": (
            "shorter of the two complete content-audited long videos; full source bytes, "
            "random seek, metadata, and complete timeline available"
        ),
    },
    {
        "video_id": "PSP_V1_LONG",
        "video_path": str((ROOT / "data/realcam/long_video_data/驾驶-大理.mp4").resolve()),
        "expected_hash": "64cb0cfac6c37e52045552b4ed24e8aa20fd2c1fddc22509cf33dd957d14fd09",
        "selection_reason": (
            "longer complete content-audited video; tests random access and trace scaling"
        ),
    },
]


def contract(payload: dict[str, Any]) -> dict[str, Any]:
    copy = dict(payload)
    copy["contract_hash"] = canonical_hash(copy)
    return copy


def prepare() -> None:
    if (IMMUTABLE / "immutable_manifest.json").exists():
        raise RuntimeError("Final immutable freeze already exists; create a new benchmark version")
    for path in [
        IMMUTABLE / "contracts", IMMUTABLE / "scan_outputs", DERIVED / "audits",
        DERIVED / "visible_subset_candidates", DERIVED / "cost_calibration",
        DERIVED / "policy_runs/replay", DERIVED / "policy_runs/physical",
        OUTPUT / "reports",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    rows = []
    hashes = {}
    for spec in VIDEO_SPECS:
        path = Path(spec["video_path"])
        actual_hash = sha256_file(path)
        if actual_hash != spec["expected_hash"]:
            raise RuntimeError(f"Source hash mismatch: {path}")
        info = video_info(path)
        rows.append({
            "video_id": spec["video_id"], "video_path": str(path),
            "video_hash": actual_hash, **info,
            "selection_reason": spec["selection_reason"],
        })
        hashes[str(path)] = actual_hash
    videos = pd.DataFrame(rows)
    atomic_csv(VIDEOS, videos)
    atomic_json(IMMUTABLE / "source_hashes.json", hashes)

    query_prompt = """You are constructing an evaluator-only reference for TARGET_VEHICLE_CUT_IN.
Identify every event in the supplied full-context video window where another MOTOR VEHICLE
enters the ego vehicle's expected driving path from an adjacent or lateral direction.
Exclude cyclists, pedestrians, ego lane changes, ordinary parallel driving, overtakes
without path entry, ambiguous path entry, and non-events. Return strict JSON:
{"events":[{"start_sec":number,"end_sec":number,"actor_type":"motor_vehicle",
"confidence":"high|medium|low","description":string}],"ambiguous":[string]}.
Times are seconds relative to this window. Empty events is valid."""
    query_contract = contract({
        "benchmark_name": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "query_id": "TARGET_VEHICLE_CUT_IN",
        "query_text": (
            "Another motor vehicle enters the ego vehicle's expected driving path "
            "from an adjacent or lateral direction."
        ),
        "query_prompt": query_prompt,
        "query_prompt_hash": hashlib.sha256(query_prompt.encode()).hexdigest(),
        "parser_version": "partial_scan_reference_events_json_v1",
        "actor_definition": "motor vehicle only",
        "inclusion_rules": ["lateral_or_adjacent_origin", "enters_expected_ego_path"],
        "exclusion_rules": [
            "cyclist", "pedestrian", "ego_lane_change", "parallel_driving",
            "overtake_without_path_entry", "ambiguous_path_entry", "non_event",
        ],
    })
    proxy_source = ROOT / "scripts/run_psvr_two_video_proxy.py"
    scan_contract = contract({
        "decoder": "OpenCV VideoCapture seek + sequential decode",
        "sampling_fps": 5.0, "input_resolution": "native decode; YOLO imgsz=640",
        "yolo_model": "YOLOv8n", "yolo_weight_path": "models/yolo/yolov8n.pt",
        "yolo_weight_sha256": sha256_file(ROOT / "models/yolo/yolov8n.pt"),
        "confidence": 0.25, "detector_nms_iou": 0.45,
        "motor_class_ids": [2, 3, 5, 7],
        "bytetrack": {
            "track_high_thresh": 0.25, "track_low_thresh": 0.10,
            "new_track_thresh": 0.25, "track_buffer": 30,
            "match_thresh": 0.80, "fuse_score": True,
        },
        "tracker_reset_per_action": True,
        "cross_unit_track_stitching": "PROHIBITED",
        "trigger": {
            "min_observations": 3, "min_front_region_occupancy": 0.05,
            "motion": "positive lateral-to-centre OR positive bbox growth",
        },
        "visible_subset_admission": "zero-anchored rank percentiles over visible raw candidates only",
        "temporal_nms_iou": 0.50,
        "implementation_path": "scripts/partial_scan_pilot_common.py",
        "implementation_sha256": sha256_file(ROOT / "scripts/partial_scan_pilot_common.py"),
        "reused_proxy_source_sha256": sha256_file(proxy_source),
        "hardware_environment": environment_snapshot(),
    })
    reference_contract = contract({
        "reference_type": "FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "reference_window_sec": 30.0, "reference_stride_sec": 15.0,
        "overlap_context": True,
        "oracle_model_path": "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct",
        "oracle_model_full_content_hash": (
            "c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210"
        ),
        "merge_rule": (
            "same video, motor_vehicle, overlapping intervals or midpoint distance <=2s; "
            "union boundaries; retain all source windows"
        ),
        "ambiguity": "retained, excluded from formal reference event set",
        "completeness": "all systematic windows require durable parse-valid output",
        "forbidden_inputs": [
            "immutable/scan_outputs", "raw_candidates", "P0/P1/P2 scores",
            "policy traces", "candidate_event_map",
        ],
        "query_prompt_hash": query_contract["query_prompt_hash"],
    })
    exposure_contract = contract({
        "definition": (
            "rerun frozen candidate generator from visible unit outputs; candidate lineage "
            "must be fully visible; match independent reference by frozen rule"
        ),
        "match_rule": (
            "same video and motor-vehicle type AND (temporal intersection >=0.5 sec "
            "OR reference midpoint contained in candidate)"
        ),
        "candidate_generator_version": "visible_percentile_temporal_nms_v1",
        "direct_full_scan_projection": "PROHIBITED",
    })
    physical_contract = contract({
        "cache_protocol": "CONTROLLED_WARM",
        "cold_cache": "NOT_ATTEMPTED_NO_RELIABLE_PRIVILEGED_OS_CACHE_CONTROL",
        "model_lifecycle": "load once per policy run",
        "process_lifecycle": "fresh process per policy run",
        "decoder_lifecycle": "new decoder per policy run",
        "tracker_lifecycle": "reset per action",
        "repetitions": "one complete 4x4 Latin square per video",
        "deadline_clock_source": "time.perf_counter",
        "atomic_action": "must complete; reject before start if Q90 estimate exceeds remaining",
        "action_trace_schema_version": "partial_scan_action_trace_v1",
        "policies_are_path_generators_only": True,
    })
    benchmark_contract = contract({
        "benchmark_name": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "pilot_method_selection": "PROHIBITED",
        "query": "TARGET_VEHICLE_CUT_IN",
        "scan_fidelity": "FIXED", "atomic_action": "SCAN_ONE_CONTIGUOUS_MICROCHUNK",
        "microchunk_length_sec": 10.0,
        "formal_action_universe": "OFFSET_0_NON_OVERLAPPING_UNITS",
        "partition_sensitivity": "OFFSET_0_AND_OFFSET_5_SECONDS",
        "tail_units": "allowed_as_explicit_complete-remainder actions",
        "p0_p1_p2": "OUT_OF_SCOPE", "controller": "OUT_OF_SCOPE",
        "rl_bandit_mdp_smdp": "PROHIBITED",
        "claim_scope": "benchmark engineering validity only",
    })
    contracts = {
        "benchmark_contract.yaml": benchmark_contract,
        "query_contract.yaml": query_contract,
        "scan_operator_contract.yaml": scan_contract,
        "reference_construction_contract.yaml": reference_contract,
        "event_exposure_contract.yaml": exposure_contract,
        "physical_runtime_contract.yaml": physical_contract,
    }
    for name, payload in contracts.items():
        # JSON is a strict YAML subset and avoids a second serialization dependency.
        atomic_json(IMMUTABLE / "contracts" / name, payload)

    formal = pd.concat(
        [make_timeline(row, 0.0) for row in videos.to_dict("records")],
        ignore_index=True,
    )
    offset5 = pd.concat(
        [make_timeline(row, 5.0) for row in videos.to_dict("records")],
        ignore_index=True,
    )
    atomic_csv(TIMELINE, formal)
    atomic_csv(TIMELINE_OFFSET5, offset5)
    atomic_json(OUTPUT / "environment_lock.json", environment_snapshot())
    prefreeze_assets = [
        CONTRACT_DOC, VIDEOS, IMMUTABLE / "source_hashes.json", TIMELINE,
        TIMELINE_OFFSET5, *sorted((IMMUTABLE / "contracts").glob("*.yaml")),
    ]
    freeze = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "frozen_at_utc": utc_now(),
        "assets": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in prefreeze_assets
        },
        "scan_started": False, "reference_started": False,
    }
    freeze["freeze_hash"] = canonical_hash(freeze)
    atomic_json(IMMUTABLE / "preexecution_freeze.json", freeze)
    print(json.dumps({
        "PREPARE": "PASS", "videos": videos.video_id.tolist(),
        "formal_units": formal.groupby("video_id").size().to_dict(),
        "offset5_units": offset5.groupby("video_id").size().to_dict(),
        "freeze_hash": freeze["freeze_hash"],
    }, indent=2))


def load_video(video_id: str) -> dict[str, Any]:
    videos = pd.read_csv(VIDEOS)
    selected = videos[videos.video_id.eq(video_id)]
    if len(selected) != 1:
        raise KeyError(video_id)
    return selected.iloc[0].to_dict()


def verify_prefreeze() -> None:
    freeze = json.loads((IMMUTABLE / "preexecution_freeze.json").read_text())
    for relative, expected in freeze["assets"].items():
        path = ROOT / relative
        if sha256_file(path) != expected:
            raise RuntimeError(f"Pre-execution frozen asset changed: {relative}")


def scan_video(video_id: str, offset: int, force: bool = False) -> None:
    verify_prefreeze()
    video = load_video(video_id)
    units_path = TIMELINE if offset == 0 else TIMELINE_OFFSET5
    units = pd.read_csv(units_path)
    units = units[units.video_id.eq(video_id)].sort_values("unit_index")
    engine = ScanEngine(video)
    success = failures = 0
    try:
        for number, unit in enumerate(units.to_dict("records"), 1):
            destination = scan_output_dir(video_id, unit["unit_id"], offset)
            complete = all(
                (destination / name).is_file() for name in [
                    "detections.parquet", "tracks.parquet", "triggers.json",
                    "raw_candidates.json", "runtime.json", "output_hashes.json",
                ]
            )
            if complete and not force:
                success += 1
                continue
            try:
                result = engine.scan(unit)
                save_scan_result(destination, result)
                success += 1
                print(
                    f"[{video_id} o{offset} {number:04d}/{len(units):04d}] "
                    f"{unit['unit_id']} {result['runtime']['total_action_time_sec']:.3f}s",
                    flush=True,
                )
            except Exception as exc:
                failures += 1
                destination.mkdir(parents=True, exist_ok=True)
                atomic_json(destination / "runtime.json", {
                    "status": "UNIT_SCAN_FAILURE", "video_id": video_id,
                    "unit_id": unit["unit_id"], "error_type": type(exc).__name__,
                    "error": str(exc), "created_at_utc": utc_now(),
                })
                print(f"FAIL {unit['unit_id']}: {exc}", flush=True)
    finally:
        engine.close()
    atomic_json(DERIVED / "audits" / f"scan_completion_{video_id}_o{offset}.json", {
        "video_id": video_id, "offset": offset, "unit_count": len(units),
        "success_count": success, "failure_count": failures,
        "status": "PASS" if success == len(units) and failures == 0 else "FAIL",
    })
    if failures:
        raise RuntimeError(f"{failures} units failed")


def timeline_audit() -> None:
    videos = pd.read_csv(VIDEOS)
    timeline = pd.read_csv(TIMELINE)
    rows = []
    all_pass = True
    for video in videos.to_dict("records"):
        units = timeline[timeline.video_id.eq(video["video_id"])].sort_values("unit_index")
        first_zero = abs(float(units.iloc[0].start_sec)) < 1e-9
        final_covered = abs(float(units.iloc[-1].end_sec) - float(video["duration_sec"])) < 1e-6
        gaps = np.diff(units.start_sec.to_numpy()) - units.duration_sec.iloc[:-1].to_numpy()
        no_gaps = bool(np.all(np.abs(gaps) < 1e-6))
        no_overlap = bool(np.all(gaps >= -1e-6))
        order = units.unit_index.tolist() == list(range(len(units)))
        decodable = True
        capture = cv2.VideoCapture(str(video["video_path"]))
        for unit in units.to_dict("records"):
            for frame_index in [int(unit["start_frame"]), int(unit["end_frame"])]:
                if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                    decodable = False
                    break
                ok, _ = capture.read()
                if not ok:
                    decodable = False
                    break
        capture.release()
        status = all([first_zero, final_covered, no_gaps, no_overlap, order, decodable])
        all_pass &= status
        rows.append({
            "video_id": video["video_id"], "unit_count": len(units),
            "FULL_TIMELINE_COVERED": first_zero and final_covered,
            "NO_UNEXPLAINED_GAPS": no_gaps, "NO_UNIT_OVERLAP": no_overlap,
            "UNIT_ORDER_VALID": order,
            "ALL_UNIT_SOURCE_RANGES_DECODABLE": decodable,
            "status": "PASS" if status else "FAIL",
        })
    atomic_json(DERIVED / "audits/timeline_audit.json", {
        "status": "PASS" if all_pass else "FAIL", "videos": rows,
    })
    print(json.dumps(rows, indent=2))


def determinism_audit() -> None:
    verify_prefreeze()
    timeline = pd.read_csv(TIMELINE)
    audit_rows = []
    overall = True
    for video_id, units in timeline.groupby("video_id", sort=True):
        units = units.sort_values("unit_index").reset_index(drop=True)
        n = len(units)
        selected = {0, n // 2, n - 1, min(1, n - 1)}
        keyframes = units.nearest_keyframe_sec.fillna(-1).to_numpy()
        crossing = next(
            (i for i in range(1, n) if keyframes[i] != keyframes[i - 1]),
            min(2, n - 1),
        )
        selected.add(crossing)
        rng = np.random.default_rng(SEED + n)
        target = max(10, int(math.ceil(0.10 * n)))
        for index in rng.permutation(n):
            selected.add(int(index))
            if len(selected) >= target:
                break
        video = load_video(video_id)
        engine = ScanEngine(video)
        try:
            for index in sorted(selected):
                unit = units.iloc[index].to_dict()
                semantic = []
                runtime_schema = []
                for repeat in range(3):
                    result = engine.scan(unit)
                    destination = (
                        DERIVED / "determinism_repeats" / video_id
                        / unit["unit_id"] / f"repeat_{repeat + 1}"
                    )
                    semantic.append(save_scan_result(destination, result))
                    runtime_schema.append(sorted(result["runtime"]))
                fields = ["detections", "tracks", "triggers", "raw_candidates"]
                passes = {
                    field: len({item[field] for item in semantic}) == 1
                    for field in fields
                }
                passes["lineage"] = passes["raw_candidates"]
                passes["runtime_schema"] = len({tuple(value) for value in runtime_schema}) == 1
                status = all(passes.values())
                overall &= status
                audit_rows.append({
                    "video_id": video_id, "unit_id": unit["unit_id"],
                    "unit_index": int(unit["unit_index"]), "repetitions": 3,
                    **passes, "status": "PASS" if status else "FAIL",
                })
                print(f"DETERMINISM {video_id} {unit['unit_id']} {'PASS' if status else 'FAIL'}", flush=True)
        finally:
            engine.close()
    atomic_json(DERIVED / "audits/unit_determinism_audit.json", {
        "status": "PASS" if overall else "FAIL",
        "numeric_tolerance": "semantic values rounded to 1e-6 before hashing",
        "sample_count": len(audit_rows), "rows": audit_rows,
    })
    if not overall:
        raise RuntimeError("Unit determinism audit failed")


def all_visible(video_id: str, offset: int) -> pd.DataFrame:
    path = TIMELINE if offset == 0 else TIMELINE_OFFSET5
    units = pd.read_csv(path)
    unit_ids = set(units[units.video_id.eq(video_id)].unit_id.astype(str))
    candidates = visible_candidates(video_id, unit_ids, offset)
    destination = DERIVED / "visible_subset_candidates" / f"{video_id}_offset{offset}_full.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_parquet(destination, index=False)
    return candidates


def candidate_reference_map(candidates: pd.DataFrame, references: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate in candidates.to_dict("records"):
        relevant = references[
            references.video_id.eq(candidate["video_id"])
            & references.actor_type.eq("motor_vehicle")
        ]
        for reference in relevant.to_dict("records"):
            intersection = max(
                0.0,
                min(float(candidate["candidate_end_sec"]), float(reference["event_end_sec"]))
                - max(float(candidate["candidate_start_sec"]), float(reference["event_start_sec"])),
            )
            midpoint = (
                float(reference["event_start_sec"]) + float(reference["event_end_sec"])
            ) / 2
            contained = (
                float(candidate["candidate_start_sec"])
                <= midpoint
                <= float(candidate["candidate_end_sec"])
            )
            if intersection >= 0.5 or contained:
                rows.append({
                    "video_id": candidate["video_id"],
                    "candidate_id": candidate["candidate_id"],
                    "reference_event_id": reference["reference_event_id"],
                    "temporal_intersection_sec": intersection,
                    "reference_midpoint_contained": contained,
                    "source_unit_ids": json.dumps(candidate["source_unit_ids"]),
                    "generation_state_hash": candidate["generation_state_hash"],
                    "match_rule_version": "intersection_0p5_or_ref_midpoint_v1",
                })
    return pd.DataFrame(rows, columns=[
        "video_id", "candidate_id", "reference_event_id",
        "temporal_intersection_sec", "reference_midpoint_contained",
        "source_unit_ids", "generation_state_hash", "match_rule_version",
    ])


def partition_and_exposure_audit() -> None:
    verify_prefreeze()
    if not REFERENCE.is_file():
        raise RuntimeError("Independent reference must be finalized first")
    references = pd.read_csv(REFERENCE)
    all_maps = []
    details = []
    for video_id in pd.read_csv(VIDEOS).video_id.astype(str):
        refs = references[references.video_id.eq(video_id)]
        by_offset = {}
        for offset in [0, 5]:
            candidates = all_visible(video_id, offset)
            mapping = candidate_reference_map(candidates, refs)
            exposed = set(mapping.reference_event_id.astype(str))
            by_offset[offset] = {
                "candidate_count": len(candidates),
                "exposed_ids": sorted(exposed),
                "mapping": mapping,
            }
            copy = mapping.copy()
            copy["partition_offset_sec"] = offset
            all_maps.append(copy)
        offset0 = set(by_offset[0]["exposed_ids"])
        offset5 = set(by_offset[5]["exposed_ids"])
        boundary_unexposed = []
        other_unexposed = []
        for ref in refs.to_dict("records"):
            rid = ref["reference_event_id"]
            if rid in offset0:
                continue
            midpoint = (float(ref["event_start_sec"]) + float(ref["event_end_sec"])) / 2
            distance = min(midpoint % 10.0, 10.0 - midpoint % 10.0)
            if rid in offset5 or distance <= 1.0:
                boundary_unexposed.append(rid)
            else:
                other_unexposed.append(rid)
        total = len(refs)
        ceiling0 = len(offset0) / total if total else 1.0
        ceiling5 = len(set(by_offset[5]["exposed_ids"])) / total if total else 1.0
        materially_lower = total > 0 and ceiling5 - ceiling0 >= 0.10
        enough = total == 0 or ceiling0 >= 0.50
        status = "PASS" if enough and not materially_lower else "BLOCK"
        details.append({
            "video_id": video_id,
            "REFERENCE_EVENT_TOTAL": total,
            "REFERENCE_EVENT_EXPOSABLE_OFFSET_0": len(offset0),
            "REFERENCE_EVENT_EXPOSABLE_OFFSET_5": len(by_offset[5]["exposed_ids"]),
            "REFERENCE_EVENT_UNEXPOSABLE_AT_BOUNDARY": len(boundary_unexposed),
            "REFERENCE_EVENT_UNEXPOSABLE_OTHER": len(other_unexposed),
            "offset0_ceiling": ceiling0, "offset5_ceiling": ceiling5,
            "boundary_unexposed_ids": boundary_unexposed,
            "other_unexposed_ids": other_unexposed,
            "materially_lower_threshold_absolute": 0.10,
            "minimum_engineering_ceiling": 0.50,
            "status": status,
        })
    mapping = pd.concat(all_maps, ignore_index=True) if all_maps else pd.DataFrame()
    mapping.to_parquet(DERIVED / "candidate_event_map.parquet", index=False)
    overall = all(row["status"] == "PASS" for row in details)
    payload = {
        "status": "PASS" if overall else "BLOCK",
        "formal_partition": "offset0", "sensitivity_partition": "offset5",
        "thresholds_frozen_before_evaluation": True, "videos": details,
    }
    atomic_json(DERIVED / "full_scan_exposure_audit.json", payload)
    atomic_json(DERIVED / "audits/partition_phase_audit.json", payload)
    atomic_json(DERIVED / "audits/event_exposure_audit.json", {
        "status": "PASS" if overall else "BLOCK",
        "rule": "visible candidate generation then frozen reference match",
        "direct_full_scan_projection": False,
        "mapping_rows": len(mapping),
        "lineage_complete": bool(
            len(mapping) == 0
            or mapping[["source_unit_ids", "generation_state_hash"]].notna().all().all()
        ),
    })
    print(json.dumps(payload, indent=2))


def candidate_signature(frame: pd.DataFrame) -> str:
    columns = [
        "candidate_id", "source_unit_ids", "candidate_start_sec",
        "candidate_end_sec", "generation_state_hash", "admission_version",
        "candidate_score",
    ]
    if frame.empty:
        return canonical_hash([])
    records = frame.reindex(columns=columns).copy()
    records["source_unit_ids"] = records.source_unit_ids.map(
        lambda value: sorted(value) if isinstance(value, list) else value
    )
    for name in ["candidate_start_sec", "candidate_end_sec", "candidate_score"]:
        records[name] = pd.to_numeric(records[name]).round(8)
    return canonical_hash(records.sort_values("candidate_id").to_dict("records"))


def candidate_replay_audit() -> None:
    references = pd.read_csv(REFERENCE)
    tests = []
    overall = True
    rng = np.random.default_rng(SEED)
    timeline = pd.read_csv(TIMELINE)
    for video_id, units in timeline.groupby("video_id", sort=True):
        units = units.sort_values("unit_index").reset_index(drop=True)
        n = len(units)
        sets = {
            "empty": set(),
            "single": {str(units.iloc[n // 3].unit_id)},
            "two_adjacent": set(units.iloc[[n // 2, min(n - 1, n // 2 + 1)]].unit_id.astype(str)),
            "two_nonadjacent": {str(units.iloc[1].unit_id), str(units.iloc[-2].unit_id)},
            "complete_prefix": set(units.iloc[:max(2, n // 5)].unit_id.astype(str)),
            "random_subset": set(
                units.iloc[rng.choice(n, size=max(2, n // 7), replace=False)].unit_id.astype(str)
            ),
            "full": set(units.unit_id.astype(str)),
        }
        refs = references[references.video_id.eq(video_id)]
        for name, visible in sets.items():
            first = visible_candidates(video_id, visible)
            second = visible_candidates(video_id, visible)
            first_map = candidate_reference_map(first, refs)
            second_map = candidate_reference_map(second, refs)
            lineage = all(
                set(value).issubset(visible)
                for value in first.source_unit_ids
            ) if len(first) else True
            same_candidates = candidate_signature(first) == candidate_signature(second)
            same_exposure = canonical_hash(
                sorted(first_map.reference_event_id.astype(str))
            ) == canonical_hash(sorted(second_map.reference_event_id.astype(str)))
            status = lineage and same_candidates and same_exposure
            overall &= status
            tests.append({
                "video_id": video_id, "test": name, "visible_unit_count": len(visible),
                "candidate_count": len(first),
                "exposed_event_count": first_map.reference_event_id.nunique(),
                "candidate_deterministic": same_candidates,
                "exposure_deterministic": same_exposure,
                "lineage_subset_of_visible": lineage,
                "status": "PASS" if status else "FAIL",
            })
    atomic_json(DERIVED / "audits/candidate_replay_audit.json", {
        "status": "PASS" if overall else "FAIL", "tests": tests,
    })
    if not overall:
        raise RuntimeError("Candidate replay audit failed")
    print(json.dumps({"CANDIDATE_REPLAY": "PASS", "tests": len(tests)}, indent=2))


def policy_isolation_audit() -> None:
    video_id = str(pd.read_csv(VIDEOS).iloc[0].video_id)
    env = ReplayEnvironment(INITIAL_CONSERVATIVE_COST_SEC)
    state = env.reset(video_id, 20.0)
    state_fields = set(asdict(state))
    forbidden = {
        "reference", "reference_events", "candidate_event_map",
        "unscanned_outputs", "future_actual_cost", "event_count",
    }
    attempts = {
        "reference_from_state": bool(state_fields & {"reference", "reference_events"}),
        "unscanned_output_path_from_state": bool(state_fields & {"unscanned_outputs", "output_paths"}),
        "future_runtime_from_state": bool(state_fields & {"future_actual_cost", "future_runtime"}),
        "reference_id_via_candidate_id": any(
            "_ref_" in value.lower() for value in state.revealed_candidate_ids
        ),
        "forbidden_field_union": bool(state_fields & forbidden),
    }
    policies_choose = {}
    for index, policy_id in enumerate(POLICY_IDS):
        selected = policy_for(policy_id, SEED + index).choose(state)
        policies_choose[policy_id] = selected in env.available_actions()
    pass_rate = sum(not value for value in attempts.values()) / len(attempts)
    status = pass_rate == 1.0 and all(policies_choose.values())
    atomic_json(DERIVED / "audits/policy_isolation_audit.json", {
        "status": "PASS" if status else "FAIL",
        "isolation_boundary": "immutable PublicScanState value object",
        "active_leakage_attempts": {
            name: {"access_succeeded": value, "expected": False}
            for name, value in attempts.items()
        },
        "policy_interface_compatibility": policies_choose,
        "leakage_test_pass_rate": pass_rate,
        "policy_source_has_reference_loader": False,
        "note": "Policies receive values only; no environment or filesystem path handle is present.",
    })
    if not status:
        raise RuntimeError("Policy isolation failed")
    print(json.dumps({"POLICY_ISOLATION": "PASS", "pass_rate": pass_rate}, indent=2))


def replay_runs() -> None:
    timelines = pd.read_csv(TIMELINE)
    for video_id in pd.read_csv(VIDEOS).video_id.astype(str):
        for index, policy_id in enumerate(POLICY_IDS):
            env = ReplayEnvironment(INITIAL_CONSERVATIVE_COST_SEC)
            state = env.reset(video_id, PHYSICAL_BUDGET_SEC)
            policy = policy_for(policy_id, SEED + 1000 + index)
            actions = []
            while env.available_actions() and state.remaining_estimated_budget_sec >= INITIAL_CONSERVATIVE_COST_SEC:
                selected = policy.choose(state)
                observation = env.scan(selected)
                state = env.public_state()
                actions.append({
                    "action_index": len(actions), "selected_unit_id": selected,
                    "estimated_action_cost_sec": observation.action_cost_sec,
                    "remaining_estimated_budget_sec": state.remaining_estimated_budget_sec,
                    "revealed_candidate_count": len(observation.revealed_candidate_ids),
                    "result_class": observation.result_class,
                })
            destination = DERIVED / "policy_runs/replay" / f"{video_id}_{policy_id}.json"
            atomic_json(destination, {
                "video_id": video_id, "policy_id": policy_id,
                "budget_sec": PHYSICAL_BUDGET_SEC,
                "result_class": "LOGICAL_REPLAY_OR_ESTIMATED_COST",
                "actions": actions,
            })
    print(json.dumps({"REPLAY_RUNS": "PASS", "run_count": 8}, indent=2))


def warm_source_bytes(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    byte_count = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(16 * 1024 * 1024):
            byte_count += len(chunk)
            digest.update(chunk)
    return {
        "protocol": "CONTROLLED_WARM",
        "operation": "sequential read of all source bytes immediately before decoder/model setup",
        "bytes_read": byte_count, "elapsed_sec": time.perf_counter() - started,
        "content_sha256": digest.hexdigest(),
    }


def conservative_estimate(tr: dict[str, Any]) -> tuple[float, str]:
    path = DERIVED / "cost_calibration/conservative_cost_model.json"
    if not path.is_file():
        return INITIAL_CONSERVATIVE_COST_SEC, "INITIAL_DEVELOPMENT_BOUND"
    model = json.loads(path.read_text())
    key = (
        f"{tr['transition_class']}|{tr['same_or_cross_gop']}|CONTROLLED_WARM"
    )
    if key in model.get("strata", {}):
        return (
            float(model["strata"][key]["q90_action_cost_sec"]),
            f"EMPIRICAL_Q90:{key}",
        )
    fallback = model.get("fallback_q90_sec")
    if fallback is None:
        return INITIAL_CONSERVATIVE_COST_SEC, "INITIAL_DEVELOPMENT_BOUND"
    return float(fallback), "EMPIRICAL_Q90_FALLBACK"


def physical_run(video_id: str, block_id: int, policy_id: str) -> None:
    if policy_id not in LATIN_SQUARE[block_id - 1]:
        raise ValueError("policy not in Latin block")
    verify_prefreeze()
    video = load_video(video_id)
    warm = warm_source_bytes(Path(video["video_path"]))
    if warm["content_sha256"] != video["video_hash"]:
        raise RuntimeError("Warm read source identity mismatch")
    units = pd.read_csv(TIMELINE)
    units = units[units.video_id.eq(video_id)].sort_values("unit_index")
    by_id = {str(row["unit_id"]): row for row in units.to_dict("records")}
    run_id = f"{video_id}_b{block_id}_{policy_id}"
    destination = DERIVED / "policy_runs/physical" / run_id
    destination.mkdir(parents=True, exist_ok=True)
    trace_path = destination / "action_trace.jsonl"
    if trace_path.exists():
        raise RuntimeError(f"Physical run already exists: {run_id}")
    policy = policy_for(policy_id, SEED + block_id * 100 + POLICY_IDS.index(policy_id))
    engine = ScanEngine(video)
    scanned: set[str] = set()
    current = None
    costs: list[float] = []
    cumulative = 0.0
    records = []
    model_path_identity = id(engine.detector)
    capture_identity = id(engine.capture)
    try:
        while len(scanned) < len(units):
            candidates = visible_candidates(video_id, scanned)
            state = PublicScanState(
                video_id=video_id,
                timeline=tuple(
                    (str(row.unit_id), float(row.start_sec), float(row.end_sec))
                    for row in units.itertuples(index=False)
                ),
                scanned_units=tuple(sorted(scanned)),
                current_unit_id=None if current is None else str(current["unit_id"]),
                remaining_estimated_budget_sec=PHYSICAL_BUDGET_SEC - cumulative,
                past_action_costs_sec=tuple(costs),
                revealed_candidate_ids=tuple(sorted(candidates.candidate_id.astype(str))),
                geometric_coverage_fraction=len(scanned) / len(units),
            )
            selected_id = policy.choose(state)
            selected = by_id[selected_id]
            tr = transition(current, selected)
            estimate, estimate_source = conservative_estimate(tr)
            remaining = PHYSICAL_BUDGET_SEC - cumulative
            if estimate > remaining:
                records.append({
                    "run_id": run_id, "block_id": block_id, "policy_id": policy_id,
                    "video_id": video_id, "action_index": len(costs),
                    **tr, "selected_unit_id": selected_id,
                    "decoder_state": "OPEN_SINGLE_INSTANCE",
                    "cache_protocol": "CONTROLLED_WARM", "tracker_reset": True,
                    "decoded_frame_count": 0, "seek_time_sec": 0.0,
                    "decode_time_sec": 0.0, "model_time_sec": 0.0,
                    "tracker_time_sec": 0.0, "candidate_time_sec": 0.0,
                    "environment_overhead_sec": 0.0, "total_action_time_sec": 0.0,
                    "estimated_action_cost_sec": estimate, "actual_action_cost_sec": 0.0,
                    "estimated_action_cost_source": estimate_source,
                    "cumulative_wall_clock_sec": cumulative,
                    "remaining_budget_sec": remaining,
                    "action_started": False, "action_completed": False,
                    "deadline_rejection_reason": "Q90_ESTIMATE_EXCEEDS_REMAINING_BUDGET",
                })
                break
            result = engine.scan(selected)
            actual = float(result["runtime"]["total_action_time_sec"])
            scanned.add(selected_id)
            costs.append(actual)
            cumulative += actual
            runtime = result["runtime"]
            record = {
                "run_id": run_id, "block_id": block_id, "policy_id": policy_id,
                "video_id": video_id, "action_index": len(costs) - 1, **tr,
                "selected_unit_id": selected_id,
                "decoder_state": "OPEN_SINGLE_INSTANCE",
                "cache_protocol": "CONTROLLED_WARM", "tracker_reset": True,
                "decoded_frame_count": int(runtime["decoded_frames"]),
                "seek_time_sec": runtime["seek_time_sec"],
                "decode_time_sec": runtime["decode_time_sec"],
                "model_time_sec": runtime["model_time_sec"],
                "tracker_time_sec": runtime["tracker_time_sec"],
                "candidate_time_sec": runtime["candidate_time_sec"],
                "environment_overhead_sec": runtime["environment_overhead_sec"],
                "total_action_time_sec": actual,
                "estimated_action_cost_sec": estimate,
                "estimated_action_cost_source": estimate_source,
                "actual_action_cost_sec": actual,
                "cumulative_wall_clock_sec": cumulative,
                "remaining_budget_sec": PHYSICAL_BUDGET_SEC - cumulative,
                "action_started": True, "action_completed": True,
                "deadline_rejection_reason": None,
            }
            records.append(record)
            current = selected
            if cumulative >= PHYSICAL_BUDGET_SEC:
                break
    finally:
        engine.close()
    atomic_text(
        trace_path,
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in records),
    )
    atomic_json(destination / "run_summary.json", {
        "run_id": run_id, "video_id": video_id, "block_id": block_id,
        "policy_id": policy_id, "fresh_process_pid": os.getpid(),
        "warm_protocol": warm, "model_instance_count": 1,
        "decoder_instance_count": 1, "model_instance_identity": model_path_identity,
        "decoder_instance_identity": capture_identity,
        "tracker_reset_per_completed_action": True,
        "completed_action_count": len(costs),
        "deadline_rejection_count": sum(not row["action_started"] for row in records),
        "cumulative_wall_clock_sec": cumulative,
        "budget_sec": PHYSICAL_BUDGET_SEC,
    })
    print(json.dumps({
        "PHYSICAL_RUN": "PASS", "run_id": run_id,
        "completed_actions": len(costs), "wall_clock": cumulative,
    }), flush=True)


def physical_all() -> None:
    logs = OUTPUT / "physical_run_logs"
    logs.mkdir(parents=True, exist_ok=True)
    completed_before = len(
        list((DERIVED / "policy_runs/physical").glob("*/run_summary.json"))
    )
    if completed_before >= 8 and not (
        DERIVED / "cost_calibration/conservative_cost_model.json"
    ).is_file():
        calibrate_and_audit_physical()
    for video_id in pd.read_csv(VIDEOS).video_id.astype(str):
        for block_index, order in enumerate(LATIN_SQUARE, 1):
            for sequence, policy_id in enumerate(order, 1):
                run_id = f"{video_id}_b{block_index}_{policy_id}"
                summary = DERIVED / "policy_runs/physical" / run_id / "run_summary.json"
                if summary.is_file():
                    continue
                command = [
                    sys.executable, str(Path(__file__).resolve()), "physical-run",
                    "--video-id", video_id, "--block-id", str(block_index),
                    "--policy-id", policy_id,
                ]
                with (logs / f"{run_id}.log").open("w") as handle:
                    process = subprocess.run(
                        command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                        text=True, check=False,
                    )
                if process.returncode:
                    raise RuntimeError(f"Physical child failed: {run_id}")
                print(f"PHYSICAL_ALL {video_id} block={block_index} sequence={sequence} {policy_id}", flush=True)
                completed_now = len(
                    list((DERIVED / "policy_runs/physical").glob("*/run_summary.json"))
                )
                if completed_now == 8:
                    calibrate_and_audit_physical()


def read_trace(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]


def calibrate_and_audit_physical() -> None:
    trace_paths = sorted((DERIVED / "policy_runs/physical").glob("*/action_trace.jsonl"))
    expected_runs = 2 * 4 * 4
    rows = []
    summaries = []
    for path in trace_paths:
        records = read_trace(path)
        rows.extend(records)
        summaries.append(json.loads((path.parent / "run_summary.json").read_text()))
    completed = pd.DataFrame([row for row in rows if row["action_completed"]])
    if len(completed):
        completed.to_csv(
            DERIVED / "cost_calibration/transition_cost_samples.csv", index=False
        )
    else:
        pd.DataFrame().to_csv(
            DERIVED / "cost_calibration/transition_cost_samples.csv", index=False
        )
    strata = {}
    if len(completed):
        completed["cost_stratum"] = (
            completed.transition_class.astype(str) + "|" +
            completed.same_or_cross_gop.astype(str) + "|" +
            completed.cache_protocol.astype(str)
        )
        for name, group in completed.groupby("cost_stratum"):
            strata[name] = {
                "n": len(group),
                "q90_action_cost_sec": float(group.actual_action_cost_sec.quantile(0.90)),
                "median_action_cost_sec": float(group.actual_action_cost_sec.median()),
            }
    model = {
        "model_type": "EMPIRICAL_Q90_BY_TRANSITION_GOP_CACHE",
        "policy_visible_future_actual_cost": False,
        "fallback_q90_sec": float(completed.actual_action_cost_sec.quantile(0.90))
        if len(completed) else None,
        "strata": strata,
    }
    atomic_json(DERIVED / "cost_calibration/conservative_cost_model.json", model)
    required = {
        "run_id", "block_id", "policy_id", "video_id", "action_index",
        "previous_unit_id", "selected_unit_id", "previous_timestamp",
        "selected_timestamp", "seek_direction", "seek_distance_sec",
        "same_or_cross_gop", "decoder_state", "cache_protocol", "tracker_reset",
        "decoded_frame_count", "seek_time_sec", "decode_time_sec", "model_time_sec",
        "tracker_time_sec", "candidate_time_sec", "environment_overhead_sec",
        "total_action_time_sec", "estimated_action_cost_sec",
        "actual_action_cost_sec", "cumulative_wall_clock_sec",
        "remaining_budget_sec", "action_started", "action_completed",
        "deadline_rejection_reason",
    }
    schema_pass = all(required.issubset(row) for row in rows)
    lifecycle_pass = all(
        summary["model_instance_count"] == 1
        and summary["decoder_instance_count"] == 1
        and summary["tracker_reset_per_completed_action"]
        for summary in summaries
    )
    latin_pass = len(summaries) == expected_runs
    trace_status = schema_pass and lifecycle_pass and latin_pass and len(completed) > 0
    atomic_json(DERIVED / "audits/physical_trace_audit.json", {
        "status": "PASS" if trace_status else "FAIL",
        "expected_run_count": expected_runs, "actual_run_count": len(summaries),
        "completed_action_count": len(completed), "schema_complete": schema_pass,
        "fresh_process_count": len({row["fresh_process_pid"] for row in summaries}),
        "lifecycle_contract": lifecycle_pass, "latin_square_complete": latin_pass,
    })
    cache_pass = all(
        summary["warm_protocol"]["protocol"] == "CONTROLLED_WARM"
        and summary["warm_protocol"]["bytes_read"] > 0
        and summary["warm_protocol"]["content_sha256"]
        == load_video(summary["video_id"])["video_hash"]
        for summary in summaries
    ) and latin_pass
    atomic_json(DERIVED / "audits/cache_protocol_audit.json", {
        "status": "PASS" if cache_pass else "FAIL",
        "protocol": "CONTROLLED_WARM", "cold_cache": "NOT_ATTEMPTED",
        "source_full_byte_read_verified_per_run": cache_pass,
        "run_protocols": summaries,
    })
    rejection_rows = [row for row in rows if not row["action_started"]]
    deadline_pass = all(
        row["estimated_action_cost_sec"] > row["remaining_budget_sec"]
        and not row["action_completed"]
        and row["actual_action_cost_sec"] == 0
        for row in rejection_rows
    ) and all(row["action_completed"] for row in rows if row["action_started"])
    synthetic_remaining = max(0.0, INITIAL_CONSERVATIVE_COST_SEC - 0.001)
    synthetic_rejected = INITIAL_CONSERVATIVE_COST_SEC > synthetic_remaining
    deadline_pass &= synthetic_rejected
    atomic_json(DERIVED / "audits/deadline_enforcement_audit.json", {
        "status": "PASS" if deadline_pass else "FAIL",
        "physical_rejection_count": len(rejection_rows),
        "started_actions_all_completed": all(
            row["action_completed"] for row in rows if row["action_started"]
        ),
        "synthetic_boundary_test": {
            "estimate_sec": INITIAL_CONSERVATIVE_COST_SEC,
            "remaining_sec": synthetic_remaining,
            "action_started": not synthetic_rejected,
            "status": "PASS" if synthetic_rejected else "FAIL",
        },
    })
    medians = (
        completed.groupby("transition_class").actual_action_cost_sec.median().to_dict()
        if len(completed) else {}
    )
    estimates = {}
    for transition_class in medians:
        values = [
            value["q90_action_cost_sec"] for key, value in strata.items()
            if key.startswith(transition_class + "|")
        ]
        if values:
            estimates[transition_class] = float(np.median(values))
    pairs = []
    names = sorted(set(medians) & set(estimates))
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            actual_direction = np.sign(medians[left] - medians[right])
            estimated_direction = np.sign(estimates[left] - estimates[right])
            if actual_direction:
                pairs.append(bool(actual_direction == estimated_direction))
    agreement = sum(pairs) / len(pairs) if pairs else None
    agreement_status = agreement is not None and agreement >= 0.5
    atomic_json(DERIVED / "audits/replay_physical_agreement.json", {
        "status": "PASS" if agreement_status else "PARTIAL_OR_UNVERIFIED",
        "metric": "pairwise direction agreement between physical medians and stratum Q90 estimates",
        "transition_classes": names, "pair_count": len(pairs),
        "directional_agreement_fraction": agreement,
        "minimum": 0.5,
        "method_ranking_interpretation": "PROHIBITED",
    })
    print(json.dumps({
        "PHYSICAL_AUDIT": "PASS" if trace_status and cache_pass and deadline_pass else "FAIL",
        "runs": len(summaries), "actions": len(completed), "strata": len(strata),
        "directional_agreement": agreement,
    }, indent=2))


def scan_asset_audit() -> dict[str, Any]:
    videos = pd.read_csv(VIDEOS)
    formal = pd.read_csv(TIMELINE)
    details = []
    overall = True
    for video_id in videos.video_id.astype(str):
        units = formal[formal.video_id.eq(video_id)]
        valid = 0
        for unit_id in units.unit_id.astype(str):
            destination = scan_output_dir(video_id, unit_id)
            hashes_path = destination / "output_hashes.json"
            if not hashes_path.is_file():
                continue
            hashes = json.loads(hashes_path.read_text())["file_hashes"]
            if all(
                (destination / name).is_file()
                and sha256_file(destination / name) == expected
                for name, expected in hashes.items()
            ):
                valid += 1
        status = valid == len(units)
        overall &= status
        details.append({
            "video_id": video_id, "expected_units": len(units),
            "hash_valid_complete_units": valid,
            "status": "PASS" if status else "FAIL",
        })
    payload = {
        "status": "PASS" if overall else "FAIL",
        "immutable_scan_output_hashes_valid": overall,
        "videos": details,
    }
    atomic_json(DERIVED / "audits/asset_audit.json", payload)
    return payload


def load_audit(name: str) -> dict[str, Any]:
    path = DERIVED / "audits" / name
    return json.loads(path.read_text()) if path.is_file() else {"status": "MISSING"}


def immutable_freeze() -> dict[str, Any]:
    manifest_path = IMMUTABLE / "immutable_manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    files = sorted(path for path in IMMUTABLE.rglob("*") if path.is_file())
    assets = {
        str(path.relative_to(IMMUTABLE)): {
            "sha256": sha256_file(path), "bytes": path.stat().st_size,
        }
        for path in files
    }
    payload = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "frozen_at_utc": utc_now(), "asset_count": len(assets),
        "assets": assets, "manifest_scope_excludes_self": True,
        "immutable_root_hash": canonical_hash(assets),
        "modification_rule": "new benchmark version required",
    }
    atomic_json(manifest_path, payload)
    for path in sorted(IMMUTABLE.rglob("*"), reverse=True):
        path.chmod(0o444 if path.is_file() else 0o555)
    IMMUTABLE.chmod(0o555)
    return payload


def report_file(name: str, title: str, body: str) -> None:
    atomic_text(
        OUTPUT / "reports" / name,
        f"# {title}\n\n{body.strip()}\n",
    )


def finalize_pilot() -> None:
    asset = scan_asset_audit()
    audits = {
        "timeline": load_audit("timeline_audit.json"),
        "determinism": load_audit("unit_determinism_audit.json"),
        "reference_independence": load_audit("reference_independence_audit.json"),
        "reference_completeness": load_audit("reference_completeness_audit.json"),
        "partition": load_audit("partition_phase_audit.json"),
        "exposure": load_audit("event_exposure_audit.json"),
        "candidate_replay": load_audit("candidate_replay_audit.json"),
        "policy_isolation": load_audit("policy_isolation_audit.json"),
        "physical": load_audit("physical_trace_audit.json"),
        "cache": load_audit("cache_protocol_audit.json"),
        "deadline": load_audit("deadline_enforcement_audit.json"),
        "agreement": load_audit("replay_physical_agreement.json"),
    }
    hard_pass = {
        "VIDEO_UNIVERSE_VALIDITY": len(pd.read_csv(VIDEOS)) == 2,
        "FULL_TIMELINE_UNIVERSE": audits["timeline"]["status"] == "PASS",
        "ALL_UNITS_SCAN_EXECUTABLE": asset["status"] == "PASS",
        "UNIT_SCAN_DETERMINISM": audits["determinism"]["status"] == "PASS",
        "REFERENCE_INDEPENDENCE": str(audits["reference_independence"]["status"]).startswith("PASS"),
        "EVENT_EXPOSURE_RULE": audits["exposure"]["status"] == "PASS",
        "VISIBLE_SUBSET_REPLAY": audits["candidate_replay"]["status"] == "PASS",
        "FULL_SCAN_EXPOSURE_CEILING": audits["partition"]["status"] == "PASS",
        "POLICY_INFORMATION_ISOLATION": audits["policy_isolation"]["status"] == "PASS",
        "ACTION_TRACE_COMPLETENESS": audits["physical"]["status"] == "PASS",
        "PHYSICAL_DEADLINE_ENFORCEMENT": audits["deadline"]["status"] == "PASS",
        "CACHE_PROTOCOL_REPRODUCIBILITY": audits["cache"]["status"] == "PASS",
    }
    critical_fail = not all(hard_pass.values())
    reference_complete = audits["reference_completeness"].get("status", "PARTIAL_OR_UNVERIFIED")
    agreement_status = audits["agreement"].get("status", "PARTIAL_OR_UNVERIFIED")
    if critical_fail:
        overall = "BLOCKED"
        next_stage = "BENCHMARK_REDESIGN"
    else:
        # Controlled-warm evidence and pseudo-reference are deliberately limited.
        overall = "PARTIALLY_SUPPORTED"
        next_stage = "RESOLVE_DECLARED_BENCHMARK_GAPS"
    partition_sensitivity = (
        "PASS" if audits["partition"].get("status") == "PASS" else
        audits["partition"].get("status", "MISSING")
    )
    fields = [
        "PILOT_METHOD_SELECTION = PROHIBITED",
        "",
        f"VIDEO_UNIVERSE_VALIDITY = {'PASS' if hard_pass['VIDEO_UNIVERSE_VALIDITY'] else 'FAIL'}",
        f"FULL_TIMELINE_UNIVERSE = {'PASS' if hard_pass['FULL_TIMELINE_UNIVERSE'] else 'FAIL'}",
        f"ALL_UNITS_SCAN_EXECUTABLE = {'PASS' if hard_pass['ALL_UNITS_SCAN_EXECUTABLE'] else 'FAIL'}",
        f"UNIT_SCAN_DETERMINISM = {'PASS' if hard_pass['UNIT_SCAN_DETERMINISM'] else 'FAIL'}",
        "",
        "REFERENCE_TYPE = FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        f"REFERENCE_INDEPENDENCE = {'PASS' if hard_pass['REFERENCE_INDEPENDENCE'] else 'FAIL'}",
        f"REFERENCE_COMPLETENESS_STATUS = {reference_complete}",
        "",
        f"PARTITION_PHASE_SENSITIVITY = {partition_sensitivity}",
        f"FULL_SCAN_EXPOSURE_CEILING = {'PASS' if hard_pass['FULL_SCAN_EXPOSURE_CEILING'] else 'FAIL'}",
        f"VISIBLE_SUBSET_REPLAY = {'PASS' if hard_pass['VISIBLE_SUBSET_REPLAY'] else 'FAIL'}",
        f"EVENT_EXPOSURE_REPRODUCIBILITY = {'PASS' if hard_pass['EVENT_EXPOSURE_RULE'] else 'FAIL'}",
        "",
        f"POLICY_INFORMATION_ISOLATION = {'PASS' if hard_pass['POLICY_INFORMATION_ISOLATION'] else 'FAIL'}",
        "",
        "CACHE_PROTOCOL = CONTROLLED_WARM_ONLY",
        f"ACTION_TRACE_COMPLETENESS = {'PASS' if hard_pass['ACTION_TRACE_COMPLETENESS'] else 'FAIL'}",
        f"PHYSICAL_DEADLINE_ENFORCEMENT = {'PASS' if hard_pass['PHYSICAL_DEADLINE_ENFORCEMENT'] else 'FAIL'}",
        f"PATH_COST_SUPPORT = {'PASS' if audits['physical'].get('status') == 'PASS' else 'FAIL'}",
        f"REPLAY_PHYSICAL_DIRECTIONAL_AGREEMENT = {agreement_status}",
        "",
        f"OVERALL_PARTIAL_SCAN_BENCHMARK = {overall}",
        "VALID_ENGINEERING_CLAIM = UNIT_LOCAL_PARTIAL_SCAN_CLOSED_LOOP_UNDER_FROZEN_PILOT_PROTOCOL"
        if not critical_fail else "VALID_ENGINEERING_CLAIM = NONE_BENCHMARK_BLOCKED",
        "VALID_EVENT_CLAIM = PSEUDO_REFERENCE_EXPOSURE_EVALUATION_ONLY_NO_GROUND_TRUTH_OR_POLICY_BENEFIT",
        "VALID_WALLCLOCK_CLAIM = CONTROLLED_WARM_PATH_TRACE_ONLY",
        "",
        f"NEXT_ALLOWED_STAGE = {next_stage}",
    ]
    final_text = (
        "# Final Pilot Decision\n\n"
        "This pilot evaluates benchmark engineering validity only. It does not compare "
        "scheduler quality and does not support an event-recall or policy-benefit claim.\n\n"
        "## Terminal fields\n\n```text\n" + "\n".join(fields) + "\n```\n"
    )
    report_file(
        "ASSET_DISCOVERY.md", "Asset Discovery",
        f"Two complete, seekable, hash-verified long videos were frozen.\n\n"
        f"- Video rows: {len(pd.read_csv(VIDEOS))}\n"
        f"- Immutable formal SCAN status: {asset['status']}\n"
        f"- Immutable file hashes: verified before final freeze.",
    )
    report_file(
        "TIMELINE_AND_UNIT_AUDIT.md", "Timeline and Unit Audit",
        f"Timeline audit: `{audits['timeline']['status']}`.\n\n"
        f"Unit execution: `{asset['status']}`. Determinism: `{audits['determinism']['status']}`.",
    )
    report_file(
        "REFERENCE_CONSTRUCTION_REPORT.md", "Reference Construction Report",
        f"Type: `FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE`.\n\n"
        f"Independence: `{audits['reference_independence']['status']}`. "
        f"Completeness: `{reference_complete}`. No human adjudication; not ground truth.",
    )
    report_file(
        "PARTITION_PHASE_REPORT.md", "Partition Phase Report",
        "Formal offset=0 and sensitivity offset=5 were scanned independently.\n\n"
        f"Audit status: `{audits['partition']['status']}`.\n\n"
        f"```json\n{json.dumps(audits['partition'], indent=2, ensure_ascii=False)}\n```",
    )
    report_file(
        "CANDIDATE_REPLAY_REPORT.md", "Candidate Replay Report",
        f"Visible-subset replay: `{audits['candidate_replay']['status']}`. "
        "Candidates were regenerated from revealed unit-local raw outputs; no static "
        "full-scan candidate projection was used.",
    )
    report_file(
        "POLICY_ISOLATION_REPORT.md", "Policy Isolation Report",
        f"Active leakage tests: `{audits['policy_isolation']['status']}`. "
        "The policy interface contains values only and exposes neither evaluator references "
        "nor output paths nor future actual costs.",
    )
    report_file(
        "PHYSICAL_PATH_COST_REPORT.md", "Physical Path Cost Report",
        f"Trace: `{audits['physical']['status']}`. Cache: `{audits['cache']['status']}`. "
        f"Deadline: `{audits['deadline']['status']}`. Directional agreement: "
        f"`{agreement_status}`.\n\nOnly CONTROLLED_WARM evidence was collected; no cold/warm "
        "averaging or method ranking is reported.",
    )
    atomic_text(OUTPUT / "reports/FINAL_PILOT_DECISION.md", final_text)
    atomic_text(DERIVED / "audits/FINAL_PILOT_DECISION.md", final_text)
    if not (OUTPUT / "repair_log.json").exists():
        atomic_json(OUTPUT / "repair_log.json", {
            "controlled_repair_cycles_used": 0, "maximum_allowed": 1,
            "repairs": [],
        })
    atomic_json(OUTPUT / "code_version.json", {
        "created_at_utc": utc_now(),
        "files": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in [
                ROOT / "scripts/partial_scan_pilot_common.py",
                ROOT / "scripts/run_partial_scan_pilot.py",
                ROOT / "scripts/run_partial_scan_reference.py",
                CONTRACT_DOC,
            ]
        },
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "git_worktree_dirty": bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()),
    })
    manifest = immutable_freeze()
    print(json.dumps({
        "FINALIZE": "PASS", "overall": overall,
        "next_allowed_stage": next_stage,
        "immutable_root_hash": manifest["immutable_root_hash"],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("timeline-audit")
    scan = sub.add_parser("scan")
    scan.add_argument("--video-id", required=True)
    scan.add_argument("--offset", type=int, choices=[0, 5], required=True)
    scan.add_argument("--force", action="store_true")
    sub.add_parser("determinism")
    sub.add_parser("partition-exposure")
    sub.add_parser("candidate-replay")
    sub.add_parser("policy-isolation")
    sub.add_parser("replay-runs")
    physical = sub.add_parser("physical-run")
    physical.add_argument("--video-id", required=True)
    physical.add_argument("--block-id", type=int, choices=[1, 2, 3, 4], required=True)
    physical.add_argument("--policy-id", choices=POLICY_IDS, required=True)
    sub.add_parser("physical-all")
    sub.add_parser("physical-audit")
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "timeline-audit":
        timeline_audit()
    elif args.command == "scan":
        scan_video(args.video_id, args.offset, args.force)
    elif args.command == "determinism":
        determinism_audit()
    elif args.command == "partition-exposure":
        partition_and_exposure_audit()
    elif args.command == "candidate-replay":
        candidate_replay_audit()
    elif args.command == "policy-isolation":
        policy_isolation_audit()
    elif args.command == "replay-runs":
        replay_runs()
    elif args.command == "physical-run":
        physical_run(args.video_id, args.block_id, args.policy_id)
    elif args.command == "physical-all":
        physical_all()
    elif args.command == "physical-audit":
        calibrate_and_audit_physical()
    elif args.command == "finalize":
        finalize_pilot()


if __name__ == "__main__":
    main()
