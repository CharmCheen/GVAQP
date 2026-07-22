#!/usr/bin/env python3
"""Preregister H-PROXY-2VIDEO before V1 reference outcomes are evaluated."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_two_video_loop"
QUERY_PROTOCOL = OUT / "QUERY_SELECTION_PROTOCOL.json"
VIDEO_MANIFEST = OUT / "VIDEO_MANIFEST.json"
DEST = OUT / "proxy_finalization/H_PROXY_2VIDEO_PREREGISTRATION.json"
DEST_REV0 = OUT / "proxy_finalization/H_PROXY_2VIDEO_PREREGISTRATION_REV0.json"
CAPABILITY = OUT / "proxy_finalization/PROXY_CAPABILITY_AUDIT.json"
REPAIR_AUDIT = OUT / "proxy_finalization/CAUSAL_NORMALIZATION_REPAIR.json"
Y8 = ROOT / "models/yolo/yolov8n.pt"
YP640 = ROOT / "YOLOP/weights/yolop-640-640.onnx"
YP320 = ROOT / "YOLOP/weights/yolop-320-320.onnx"
BYTE_TRACK = (
    Path(metadata.distribution("ultralytics").locate_file(""))
    / "ultralytics/trackers/byte_tracker.py"
)


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


def main() -> None:
    query = json.loads(QUERY_PROTOCOL.read_text(encoding="utf-8"))
    videos = json.loads(VIDEO_MANIFEST.read_text(encoding="utf-8"))
    if query.get("protocol_hash") is None or videos.get("VIDEO_FREEZE") != "PASS":
        raise RuntimeError("Query/video freeze is incomplete")
    models = {
        "Y8": {
            "family": "YOLOV8",
            "detector": "YOLOv8n",
            "weight_path": str(Y8),
            "weight_sha256": sha256_file(Y8),
            "resolution": 640,
            "class_support": {
                "Q1": ["bicycle", "car", "motorcycle", "bus", "truck"],
                "Q2": ["person", "bicycle", "motorcycle"],
            },
            "road_geometry": False,
        },
        "YP640": {
            "family": "YOLOP",
            "detector": "YOLOP-640",
            "weight_path": str(YP640),
            "weight_sha256": sha256_file(YP640),
            "resolution": 640,
            "onnx_output_shape": [1, 25200, 6],
            "detector_classes": 1,
            "class_support": {"Q1": ["vehicle"], "Q2": []},
            "road_geometry": True,
        },
        "YP320": {
            "family": "YOLOP",
            "detector": "YOLOP-320",
            "weight_path": str(YP320),
            "weight_sha256": sha256_file(YP320),
            "resolution": 320,
            "onnx_output_shape": [1, 6300, 6],
            "detector_classes": 1,
            "class_support": {"Q1": ["vehicle"], "Q2": []},
            "road_geometry": True,
        },
    }
    capability = {
        "audit_version": "PSVR_PROXY_CAPABILITY_V1",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "decisive_finding": (
            "Frozen YOLOP ONNX heads have nc=1 vehicle detection. They cannot directly instantiate "
            "the preregistered person/bicycle/motorcycle Q2 tracks."
        ),
        "Q2_fail_closed_policy": (
            "YOLOP Q2 emits no eligible track candidates and unit score 0. No hidden YOLOv8 "
            "detector, semantic oracle, textual evidence, or hybrid frontend is permitted."
        ),
        "scientific_interpretation": (
            "This is a measured candidate-family capability limitation, not a reason to change Q2 "
            "or add an unregistered hybrid."
        ),
        "heldout_opened": False,
    }
    feature_definitions = {
        "track_persistence": "number of eligible active observations for one track in the unit",
        "path_directed_lateral_motion": (
            "maximum positive per-second reduction in |bbox_center_x - 0.5|"
        ),
        "box_growth": "maximum positive per-second log box-area growth",
        "front_region_occupancy": (
            "maximum triangular center-corridor membership multiplied by normalized box-bottom y"
        ),
        "approximate_ttc_urgency": (
            "maximum positive relative box-height growth per second; larger means shorter TTC"
        ),
        "lane_relative_motion": (
            "maximum positive per-second reduction in distance to the estimated YOLOP lane center, "
            "multiplied by road-geometry reliability"
        ),
        "boundary_crossing": (
            "binary change across a frozen left/right ego-corridor boundary, multiplied by reliability"
        ),
        "ego_corridor_overlap": (
            "maximum bottom-center inclusion in the estimated ego corridor/drivable region, "
            "multiplied by reliability"
        ),
        "road_geometry_reliability": (
            "bounded score from nondegenerate lane/drivable masks and plausible corridor width"
        ),
    }
    base_features = [
        "track_persistence",
        "path_directed_lateral_motion",
        "box_growth",
        "front_region_occupancy",
        "approximate_ttc_urgency",
    ]
    geometry_features = [
        "lane_relative_motion",
        "boundary_crossing",
        "ego_corridor_overlap",
        "road_geometry_reliability",
    ]
    existing = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else None
    if existing is not None and int(existing.get("revision", -1)) == 0 and not DEST_REV0.exists():
        atomic_json(DEST_REV0, existing)
    original_registration_time = (
        existing.get("registered_at_utc")
        if existing is not None
        else datetime.now(timezone.utc).isoformat()
    )
    repair_time = (
        existing.get("causal_normalization_repair", {}).get("registered_at_utc")
        if existing is not None and int(existing.get("revision", -1)) == 1
        else datetime.now(timezone.utc).isoformat()
    )
    preregistration = {
        "hypothesis_id": "H-PROXY-2VIDEO",
        "revision": 1,
        "status": "REGISTERED_WITH_CAUSAL_NORMALIZATION_REPAIR_BEFORE_V1_REFERENCE_EVALUATION",
        "registered_at_utc": original_registration_time,
        "causal_normalization_repair": {
            "registered_at_utc": repair_time,
            "reason": (
                "Revision 0 defined empirical percentiles over the complete video-task candidate "
                "set. That is valid for terminal offline ranking but would reveal future proxy "
                "observations during online PSVR execution."
            ),
            "scope": "normalization population only; candidates, features, weights, and ties unchanged",
            "offline_population": "complete frozen video-task candidate set",
            "online_population": (
                "only track candidates whose physical score-availability timestamp is no later "
                "than the current decision timestamp"
            ),
            "outcome_information_used": False,
            "V1_reference_finalized_before_repair": False,
            "proxy_candidate_run_before_repair": False,
        },
        "scientific_question": (
            "Which single frozen proxy family supplies the best four-task quality/cost frontier "
            "under neutral PSVR execution?"
        ),
        "frozen_inputs": {
            "query_protocol_hash": query["protocol_hash"],
            "video_manifest_sha256": sha256_file(VIDEO_MANIFEST),
            "video_sha256": {
                "V0": videos["V0"]["sha256"],
                "V1": videos["V1"]["sha256"],
            },
        },
        "candidates": models,
        "common_pipeline": {
            "sample_fps": 5,
            "decode": "sequential OpenCV decode; identical sampled frame indices for all families",
            "unitization": "frozen center-10-second units including the final clipped window",
            "confidence_threshold": 0.25,
            "nms_iou": 0.45,
            "tracker": {
                "implementation": "Ultralytics BYTETracker",
                "implementation_path": str(BYTE_TRACK),
                "implementation_sha256": sha256_file(BYTE_TRACK),
                "ultralytics_version": metadata.version("ultralytics"),
                "parameters": {
                    "track_high_thresh": 0.25,
                    "track_low_thresh": 0.10,
                    "new_track_thresh": 0.25,
                    "track_buffer": 30,
                    "match_thresh": 0.80,
                    "fuse_score": True,
                },
            },
            "candidate_aggregation": (
                "Build one candidate per eligible track×unit; unit score is the maximum candidate "
                "score with track_id as deterministic tie-break. Offline evaluation uses the "
                "complete video-task normalization population. Online execution recomputes the "
                "same ranks using only causally available candidates."
            ),
            "normalization": (
                "Zero-anchored empirical percentile: raw values <=0 map to 0; positive values use "
                "deterministic average-rank percentile among positive values. Offline population "
                "is the complete video-task candidate set; online population contains only "
                "candidates already physically observed. No reference labels."
            ),
            "online_score_update": (
                "At each completed SCAN batch, recompute deterministic average-rank percentiles "
                "over all and only currently observed candidates; record the score-availability "
                "timestamp and never expose later candidates."
            ),
            "fallback": "no eligible track => unit score 0 and explicit empty evidence",
            "serialization_schema": "PSVR_TRACK_CANDIDATE_V1",
        },
        "feature_definitions": feature_definitions,
        "query_heads": {
            "Q1": {
                "Y8": {
                    "eligible_coco_class_ids": [1, 2, 3, 5, 7],
                    "features": base_features,
                    "weights": {name: 1 / len(base_features) for name in base_features},
                },
                "YOLOP": {
                    "eligible_detector_class_ids": [0],
                    "features": base_features + geometry_features,
                    "weights": {
                        name: 1 / len(base_features + geometry_features)
                        for name in base_features + geometry_features
                    },
                },
            },
            "Q2": {
                "Y8": {
                    "eligible_coco_class_ids": [0, 1, 3],
                    "features": base_features,
                    "weights": {name: 1 / len(base_features) for name in base_features},
                },
                "YOLOP": {
                    "eligible_detector_class_ids": [],
                    "features": [],
                    "weights": {},
                    "score_policy": "FAIL_CLOSED_ZERO_UNSUPPORTED_TARGET_CLASSES",
                },
            },
        },
        "no_tuning": {
            "continuous_weight_sweep": False,
            "threshold_sweep": False,
            "reference_label_training": False,
            "detector_finetuning": False,
            "learned_scheduler": False,
            "drivingdojo_learned_head_primary_evidence": False,
        },
        "offline_metrics": [
            "Unit_AUPRC",
            "Candidate_Precision@10/20/50",
            "Candidate_Recall@10/20/50",
            "Unique_Event_Recall@10/20/50",
            "first_positive_rank",
            "positive_event_exposure_AUC",
            "false_positives_before_first_hit",
        ],
        "physical_cost_protocol": {
            "warmup_frames": 20,
            "measured_frames_minimum": 1000,
            "physical_repeats": 3,
            "included_stages": [
                "decode", "preprocess", "detector", "NMS", "segmentation", "tracking",
                "road_geometry", "rule_scoring", "serialization",
            ],
            "reported_metrics": [
                "end_to_end_FPS", "p50_latency", "p90_latency", "p95_latency",
                "peak_GPU_memory", "GPU_seconds_per_video_hour", "CPU_seconds_per_video_hour",
            ],
        },
        "neutral_psvr_pilot": {
            "scanner": "Uniform-Temporal-Interleave",
            "verify_allocator": "A0 Fixed-Periodic",
            "frontier": "score-only deterministic",
            "K3": "frozen k3_bridge_safe",
            "deadline_guard": "frozen H-DS1",
            "snapshot_checkpoints": "frozen",
            "only_changed_variable": "proxy family and query-specific proxy score with physical cost",
            "deadlines": ["T_transition", "T_high"],
            "repeats": 3,
        },
        "selection_rule": {
            "invalid_elimination": [
                "deadline miss", "replay", "future access", "visibility violation", "snapshot failure"
            ],
            "near_best_quality": {
                "macro_anytime_auc_fraction_of_best": 0.90,
                "unique_events_rule": "best<=2: same; best>=3: at most one fewer per task",
                "macro_f1_absolute_tolerance": 0.02,
                "macro_precision_absolute_tolerance": 0.02,
                "macro_ttfc_multiplier": 1.20,
                "ttfc_exception": "or more unique events",
            },
            "primary_tiebreak": "minimum total GPU-seconds",
            "cost_near_tie_fraction": 0.10,
            "secondary_tiebreaks": [
                "lower p95 latency",
                "higher candidate precision",
                "less redundant VERIFY",
                "simpler deployment dependencies",
            ],
            "yolop_resolution_rule": (
                "Choose 320 only if AnytimeAUC>=95% of 640, identical unique events, "
                "UR@20>=95% of 640, and GPU cost at least 25% lower; otherwise 640."
            ),
        },
        "heldout_opened": False,
    }
    preregistration["preregistration_hash"] = canonical_hash(preregistration)
    if existing is not None and int(existing.get("revision", -1)) == 1:
        if existing != preregistration:
            raise RuntimeError("Revision-1 proxy preregistration changed after causal repair freeze")
        print(json.dumps({
            "H-PROXY-2VIDEO": "EXISTING_VALID",
            "revision": 1,
            "preregistration_hash": existing["preregistration_hash"],
            "YOLOP_Q2_CAPABILITY": "UNSUPPORTED_FAIL_CLOSED",
        }, indent=2))
        return
    atomic_json(CAPABILITY, capability)
    atomic_json(DEST, preregistration)
    atomic_json(REPAIR_AUDIT, {
        "repair_id": "H-PROXY-2VIDEO-R1-CAUSAL-NORMALIZATION",
        "revision_0_path": str(DEST_REV0),
        "revision_0_sha256": sha256_file(DEST_REV0),
        "revision_1_path": str(DEST),
        "revision_1_sha256": sha256_file(DEST),
        "repair_registered_at_utc": repair_time,
        "decision": "VALIDITY_REPAIR_ACCEPTED_BEFORE_OUTCOME_EVALUATION",
        "changed_semantics": preregistration["causal_normalization_repair"],
        "weights_changed": False,
        "candidate_families_changed": False,
        "query_protocol_changed": False,
        "heldout_opened": False,
    })
    atomic_json(OUT / "state/PROXY_PREREGISTRATION_DECISION.json", {
        "H-PROXY-2VIDEO": "REGISTERED",
        "preregistration_hash": preregistration["preregistration_hash"],
        "weights_frozen_before_V1_reference_evaluation": True,
        "NEXT_EXACT_COMMAND": "python scripts/build_psvr_two_video_references.py infer",
        "heldout_opened": False,
    })
    print(json.dumps({
        "H-PROXY-2VIDEO": "REGISTERED",
        "preregistration_hash": preregistration["preregistration_hash"],
        "YOLOP_Q2_CAPABILITY": "UNSUPPORTED_FAIL_CLOSED",
    }, indent=2))


if __name__ == "__main__":
    main()
