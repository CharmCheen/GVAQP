#!/usr/bin/env python3
"""Build the write-once V3 schema/determinism preflight package before sealing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from garc_eval.accelerated_event_query.k3_unit_event_adapter import K3UnitEventConfig
from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    validate_frame_set,
    write_json_once,
)
from garc_eval.accelerated_event_query.oracle_v3_schema import JSON_SCHEMA, SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
BASE = OUT / "oracle_protocol_v3_model_relative"
V2 = OUT / "operational_oracle/preflight_v2"
PROMPT = BASE / "configs/query_prompt_v3_model_relative.txt"
CONFIG = BASE / "configs/oracle_v3_execution_config.json"
SCHEMA = BASE / "schemas/oracle_v3_output_schema.json"
K3_CONFIG = BASE / "k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json"
SELECTION = BASE / "samples/V3_SCHEMA_PREFLIGHT_SAMPLE_SELECTION.json"
FRAMES = BASE / "frame_manifests/V3_SCHEMA_PREFLIGHT_FRAME_MANIFEST.json"
CALLS = BASE / "preflight/V3_SCHEMA_PREFLIGHT_AUTHORIZED_CALL_MANIFEST.json"
REGRESSION = BASE / "regression/V2_REGRESSION_CASES_FOR_V3.json"
MAPPING = BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION_MAPPING.json"
COST = BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_COST_ESTIMATE.json"
PREREG = BASE / "preflight/V3_SCHEMA_PREFLIGHT_PREREGISTRATION.json"
CODE_VERSION = BASE / "code_version.json"


SELECTED_FRAME_KEYS = (
    ("DALI_u0501", 2.0),
    ("DALI_u0548", 2.0),
    ("DALI_u0548", 4.0),
    ("DALI_u0555", 2.0),
    ("HANGZHOU_u0234", 2.0),
    ("WUHAN_u0171", 2.0),
    ("WUHAN_u0217", 2.0),
)


CALL_SPECS = (
    ("DALI_u0548_fps2_r0.json", "DALI", "DALI_u0548", 2.0, "base", 0,
     ["hard_schema_regression", "class_support", "eventization"]),
    ("DALI_u0548_fps4_sensitivity.json", "DALI", "DALI_u0548", 4.0,
     "fps_sensitivity", 0, ["hard_schema_regression", "sampling_sensitivity"]),
    ("DALI_u0555_fps2_r0.json", "DALI", "DALI_u0555", 2.0, "base", 0,
     ["same_process_anchor", "cross_replica_anchor", "class_support", "eventization"]),
    ("DALI_u0555_fps2_r1.json", "DALI", "DALI_u0555", 2.0, "base", 1,
     ["same_process_repeat"]),
    ("DALI_u0501_fps2_potential_unknown.json", "DALI", "DALI_u0501", 2.0,
     "potential_unknown", 0, ["potential_unknown", "class_support", "eventization"]),
    ("HANGZHOU_u0234_fps2_r0.json", "HANGZHOU", "HANGZHOU_u0234", 2.0,
     "base", 0, ["same_process_anchor", "class_support", "eventization"]),
    ("HANGZHOU_u0234_fps2_r1.json", "HANGZHOU", "HANGZHOU_u0234", 2.0,
     "base", 1, ["same_process_repeat"]),
    ("DALI_u0555_fps2_cross_replica_HANGZHOU.json", "HANGZHOU", "DALI_u0555", 2.0,
     "cross_replica_anchor", 0, ["cross_replica_repeat"]),
    ("WUHAN_u0217_fps2_r0.json", "WUHAN", "WUHAN_u0217", 2.0,
     "base", 0, ["same_process_anchor", "class_support", "eventization"]),
    ("WUHAN_u0217_fps2_r1.json", "WUHAN", "WUHAN_u0217", 2.0,
     "base", 1, ["same_process_repeat"]),
    ("WUHAN_u0171_fps2_r0.json", "WUHAN", "WUHAN_u0171", 2.0,
     "base", 0, ["class_support", "eventization", "unsupported_explanation_regression"]),
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build_schema_and_k3() -> None:
    write_json_once(SCHEMA, {"schema_version": SCHEMA_VERSION, "schema": JSON_SCHEMA})
    k3 = K3UnitEventConfig()
    write_json_once(K3_CONFIG, {
        "status": "FROZEN_BEFORE_V3_ORACLE_EXECUTION",
        "parameters": asdict(k3),
        "k3_config_sha256": k3.sha256,
        "probable_identity_scope": (
            "Existing IncrementalK3 owns online PROBABLE_EVENT identity; exhaustive V3 reference "
            "materialization emits only VERIFIED_EVENT records from relevant unit labels."
        ),
        "construct_validity_limit": (
            "Adjacent relevant units from distinct latent human events are observationally "
            "indistinguishable from one event under unit labels alone and merge until the frozen cap."
        ),
        "matching": {
            "eligibility": "strict_positive_temporal_overlap",
            "assignment": "one_to_one_max_cardinality_then_tiou",
            "duplicate_rule": "unmatched overlapping prediction is a duplicate false positive",
            "minimum_tiou": 0.0,
            "boundary_tolerance_seconds": 0.0,
        },
    })


def build_frames_and_selection() -> dict:
    source_path = V2 / "ORACLE_INPUT_FRAME_MANIFEST_V2.json"
    source = load_json(source_path)
    by_key = {
        (row["candidate_id"], float(row["sampling_fps"])): row
        for row in source["frame_sets"]
    }
    rows = []
    for key in SELECTED_FRAME_KEYS:
        row = by_key[key]
        validate_frame_set(row)
        rows.append(row)
    frame_manifest = {
        "status": "FROZEN_BEFORE_V3_ORACLE_EXECUTION",
        "reuse_rule": "exact byte/hash-identical frame records copied from independently audited V2",
        "source_v2_frame_manifest_path": str(source_path.relative_to(ROOT)),
        "source_v2_frame_manifest_sha256": sha256_file(source_path),
        "frame_set_count": len(rows),
        "frame_sets": rows,
    }
    write_json_once(FRAMES, frame_manifest)
    candidates = {}
    for row in rows:
        candidates.setdefault(row["candidate_id"], {
            "candidate_id": row["candidate_id"],
            "video_id": row["video_id"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "sampling_fps": [],
        })["sampling_fps"].append(row["sampling_fps"])
    rationale = {
        "DALI_u0501": "potential unknown selected from frozen V2 pre-outcome consensus unknown",
        "DALI_u0548": "hard V2 17-20 second schema regression and 2/4-fps coverage",
        "DALI_u0555": "V2 deterministic not_relevant label plus same/cross-replica anchor",
        "HANGZHOU_u0234": "V2 relevant label and traffic-signal diagnostic disagreement",
        "WUHAN_u0171": "V2 relevant label and unsupported timestamp explanation diagnostic",
        "WUHAN_u0217": "V2 deterministic not_relevant label and ego-path diagnostic disagreement",
    }
    selection = {
        "status": "FROZEN_WITHOUT_OBSERVING_ANY_V3_OUTPUT",
        "selection_rule": (
            "11-call high-information design within the allowed 8-12 range; it repeats all three "
            "V2 contradiction anchors in-process, adds one cross-replica anchor, and reuses V2 frames"
        ),
        "candidate_count": len(candidates),
        "candidates": [{**row, "sampling_fps": sorted(row["sampling_fps"]),
                        "selection_rationale": rationale[candidate_id]}
                       for candidate_id, row in sorted(candidates.items())],
        "coverage": {
            "required_v2_regressions": [
                "DALI_u0548", "DALI_u0555", "HANGZHOU_u0234",
                "WUHAN_u0217", "WUHAN_u0171",
            ],
            "potential_unknown": ["DALI_u0501"],
            "videos": ["DALI", "HANGZHOU", "WUHAN"],
            "sampling_fps": [2.0, 4.0],
        },
        "no_post_outcome_adjustment": True,
    }
    write_json_once(SELECTION, selection)
    return frame_manifest


def build_calls(frame_manifest: dict) -> dict:
    frame_sets = {
        (row["candidate_id"], float(row["sampling_fps"])): row
        for row in frame_manifest["frame_sets"]
    }
    calls = []
    for ordinal, (artifact, shard, candidate, fps, variant, repeat, roles) in enumerate(CALL_SPECS):
        frame_set = frame_sets[(candidate, fps)]
        row = {
            "ordinal": ordinal,
            "artifact_name": artifact,
            "artifact_path": str((BASE / "raw" / shard / artifact).relative_to(ROOT)),
            "execution_shard": shard,
            "candidate_id": candidate,
            "video_id": frame_set["video_id"],
            "start_time": frame_set["start_time"],
            "end_time": frame_set["end_time"],
            "sampling_fps": fps,
            "frame_count": frame_set["frame_count"],
            "frame_set_sha256": frame_set["frame_set_sha256"],
            "variant": variant,
            "repeat_index": repeat,
            "analysis_roles": roles,
        }
        row["call_spec_sha256"] = canonical_hash(row)
        calls.append(row)
    counts = {shard: sum(row["execution_shard"] == shard for row in calls)
              for shard in ("DALI", "HANGZHOU", "WUHAN")}
    manifest = {
        "status": "FROZEN_BEFORE_V3_ORACLE_EXECUTION",
        "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_SCHEMA_PREFLIGHT",
        "authorized_call_count": len(calls),
        "counts_by_execution_shard": counts,
        "calls": calls,
        "assertions": {
            "exactly_11_calls": len(calls) == 11,
            "schedule_5_3_3": counts == {"DALI": 5, "HANGZHOU": 3, "WUHAN": 3},
            "all_three_videos": {row["video_id"] for row in calls} == {"DALI", "HANGZHOU", "WUHAN"},
            "contains_2fps_and_4fps": {row["sampling_fps"] for row in calls} == {2.0, 4.0},
            "unique_artifacts": len({row["artifact_path"] for row in calls}) == 11,
        },
    }
    write_json_once(CALLS, manifest)
    return manifest


def build_regression() -> None:
    consensus = load_json(V2 / "PRE_OUTCOME_REVIEW_CONSENSUS_V2.json")
    review = {row["candidate_id"]: row["label"] for row in consensus["reviews"]}
    grounding = load_json(V2 / "GROUNDING_REVIEW_V2.json")
    raw_paths = {
        "DALI_u0548": V2 / "raw/DALI/DALI_u0548_fps4_sensitivity.json",
        "DALI_u0555": V2 / "raw/DALI/DALI_u0555_fps2_r0.json",
        "HANGZHOU_u0234": V2 / "raw/HANGZHOU/HANGZHOU_u0234_fps2_r0.json",
        "WUHAN_u0217": V2 / "raw/WUHAN/WUHAN_u0217_fps2_r0.json",
        "WUHAN_u0171": V2 / "raw/WUHAN/WUHAN_u0171_fps2_r0.json",
    }
    rows = []
    purposes = {
        "DALI_u0548": "hard_schema_no_authoritative_time_field",
        "DALI_u0555": "authoritative_label_determinism_and_non_gating_polarity_diagnostic",
        "HANGZHOU_u0234": "authoritative_label_determinism_and_signal_lane_diagnostic",
        "WUHAN_u0217": "authoritative_label_determinism_and_ego_path_diagnostic",
        "WUHAN_u0171": "authoritative_label_determinism_and_unsupported_explanation_diagnostic",
    }
    for candidate, path in raw_paths.items():
        raw = load_json(path)
        rows.append({
            "candidate_id": candidate,
            "v3_regression_purpose": purposes[candidate],
            "v2_raw_path": str(path.relative_to(ROOT)),
            "v2_raw_sha256": sha256_file(path),
            "v2_effective_label": raw["effective_label"],
            "v2_parse_status": raw["parse_status"],
            "v2_pre_outcome_agent_consensus": review[candidate],
            "agent_consensus_is_non_authoritative_in_v3": True,
        })
    write_json_once(REGRESSION, {
        "status": "FROZEN_DIAGNOSTIC_REGRESSION_SET",
        "v2_decision_remains": "REVISE_ORACLE_PROTOCOL",
        "v2_decision_path": str((V2 / "TARGETED_PILOT_DECISION_V2.json").relative_to(ROOT)),
        "v2_decision_sha256": sha256_file(V2 / "TARGETED_PILOT_DECISION_V2.json"),
        "cases": rows,
        "v2_grounding_path": str((V2 / "GROUNDING_REVIEW_V2.json").relative_to(ROOT)),
        "v2_grounding_sha256": sha256_file(V2 / "GROUNDING_REVIEW_V2.json"),
        "v2_grounding_verdict_counts": {
            verdict: sum(row["verdict"] == verdict for row in grounding["reviews"])
            for verdict in ("SUPPORTED", "UNSUPPORTED", "INDETERMINATE")
        },
        "gate_rule": "all agent semantic and explanation diagnostics are non-gating for V3 model-relative adequacy",
    })


def build_mapping() -> None:
    allowed = [
        "V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED",
        "REVISE_V3_SCHEMA",
        "REVISE_V3_INPUT_BINDING",
        "REVISE_K3_EVENTIZATION",
        "INSUFFICIENT_EVIDENCE",
    ]
    write_json_once(MAPPING, {
        "status": "FROZEN_BEFORE_V3_ORACLE_EXECUTION",
        "allowed_decisions": allowed,
        "precedence": [
            "INCOMPLETE_OR_UNAUTHENTICATED_TO_INSUFFICIENT_EVIDENCE",
            "AUTHENTICATED_INPUT_MISMATCH_TO_REVISE_V3_INPUT_BINDING",
            "SCHEMA_PARSE_LABEL_OR_DETERMINISM_FAILURE_TO_REVISE_V3_SCHEMA",
            "K3_DETERMINISM_OR_BOUNDARY_FAILURE_TO_REVISE_K3_EVENTIZATION",
            "ALL_HARD_GATES_PASS_TO_V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED",
        ],
        "construct_validity_diagnostics_can_change_decision": False,
        "pass_does_not_authorize_full_grid": True,
    })


def build_cost() -> None:
    raw_paths = sorted((V2 / "raw").glob("*/*.json"))
    records = [load_json(path) for path in raw_paths]
    inference = [row["runtime"]["inference_seconds"] for row in records]
    overhead = [row["runtime"]["total_call_seconds"] - row["runtime"]["inference_seconds"]
                for row in records]
    loads = {}
    for row in records:
        loads.setdefault(row["identity"]["execution_shard"], row["runtime"]["model_load_seconds"])
    estimated_inference = sum(inference) / len(inference) * 11
    estimated_call_overhead = sum(overhead) / len(overhead) * 11
    estimated_load = sum(loads.values())
    total_gpu_hours = 2 * (estimated_inference + estimated_call_overhead + estimated_load) / 3600
    write_json_once(COST, {
        "status": "ESTIMATE_FROM_DIRECT_V2_MEASUREMENTS_BEFORE_V3_EXECUTION",
        "physical_call_count": 11,
        "gpus_per_call": 2,
        "source_v2_record_count": len(records),
        "source_v2_total_inference_seconds": sum(inference),
        "source_v2_mean_inference_seconds_per_call": sum(inference) / len(inference),
        "estimated_v3_inference_seconds": estimated_inference,
        "estimated_three_model_load_seconds": estimated_load,
        "estimated_call_noninference_overhead_seconds": estimated_call_overhead,
        "estimated_a100_gpu_hours_including_load_and_call_overhead": total_gpu_hours,
        "rounded_approval_description": "approximately 0.19 A100 GPU-hours plus normal host overhead",
        "conservatism": "uses V2 256-token call timings although V3 caps generation at 192 tokens",
        "retry_budget": 0,
    })


def build_prereg(call_manifest: dict) -> None:
    bindings = {}
    paths = {
        "prompt": PROMPT,
        "schema": SCHEMA,
        "config": CONFIG,
        "k3_config": K3_CONFIG,
        "selection": SELECTION,
        "frame_manifest": FRAMES,
        "authorized_call_manifest": CALLS,
        "regression_manifest": REGRESSION,
        "decision_mapping": MAPPING,
        "cost_estimate": COST,
        "video_manifest": OUT / "video_manifests/frozen_videos_v1.json",
        "unit_grid": OUT / "video_manifests/frozen_unit_grid_v1.csv",
        "model_identity_audit": OUT / "operational_oracle/MODEL_IDENTITY_AUDIT_V1.json",
        "model_file_manifest": OUT / "operational_oracle/MODEL_FILE_MANIFEST_V2.json",
        "v2_decision": V2 / "TARGETED_PILOT_DECISION_V2.json",
        "parser_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_parser.py",
        "schema_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_schema.py",
        "manifest_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_manifest.py",
        "runner_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_runner.py",
        "runner_cli_source": ROOT / "scripts/run_accelerated_event_query_oracle_v3_preflight.py",
        "analyzer_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_analyzer.py",
        "analyzer_cli_source": ROOT / "scripts/analyze_accelerated_event_query_oracle_v3_preflight.py",
        "decision_source": ROOT / "scripts/decide_accelerated_event_query_oracle_v3_preflight.py",
        "seal_source": ROOT / "scripts/freeze_accelerated_event_query_oracle_v3_execution_seal.py",
        "k3_adapter_source": ROOT / "src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py",
        "event_relation_source": ROOT / "src/garc_eval/accelerated_event_query/model_relative_event_relation.py",
        "label_source": ROOT / "src/garc_eval/accelerated_event_query/model_relative_labels.py",
        "frame_extraction_source": ROOT / "src/garc_eval/accelerated_event_query/oracle_protocol.py",
        "package_builder_source": ROOT / "scripts/build_accelerated_event_query_oracle_v3_preflight.py",
    }
    for name, path in paths.items():
        bindings[f"{name}_path"] = str(path.relative_to(ROOT))
        bindings[f"{name}_sha256"] = sha256_file(path)
    prereg = {
        "status": "FROZEN_BEFORE_V3_ORACLE_EXECUTION",
        "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_SCHEMA_PREFLIGHT",
        "query_id": "Q_DRIVER_RESPONSE_V1",
        "ground_truth_definition": (
            "label emitted for each frozen unit by the exact bound Qwen3-VL-32B checkpoint, "
            "prompt, preprocessing, sampling, and deterministic decoding configuration"
        ),
        "authoritative_fields": ["label"],
        "diagnostic_fields": ["confidence", "evidence"],
        "bindings": bindings,
        "model": {
            "model_path": "models/Qwen3-VL-32B-Instruct-FP8",
            "model_content_hash": "3febe26ff0cee468bf48dc733e4bca559c8f13f8fe09f931a1e0808ba7c58873",
            "runtime_dtype": "torch.bfloat16",
            "gpus_per_replica": 2,
        },
        "workload": {
            "total_physical_calls": 11,
            "call_count_basis": (
                "11 calls within the allowed 8-12 range cover five V2 regressions, one additional "
                "potential unknown, 2/4 fps, all three videos, all three contradiction-anchor "
                "same-process pairs, and one cross-replica repeat; fewer calls would weaken the "
                "cross-video determinism test"
            ),
            "seed": 20260729,
            "generation": {"do_sample": False, "max_new_tokens": 192},
            "no_retry": True,
        },
        "gpu_schedule": {
            "DALI": {"physical_gpu_ids": [1, 2], "call_count": 5},
            "HANGZHOU": {"physical_gpu_ids": [3, 5], "call_count": 3},
            "WUHAN": {"physical_gpu_ids": [6, 7], "call_count": 3},
        },
        "determinism_groups": [
            {"group_id": "same_DALI_u0555", "kind": "same_process",
             "artifact_names": ["DALI_u0555_fps2_r0.json", "DALI_u0555_fps2_r1.json"]},
            {"group_id": "same_HANGZHOU_u0234", "kind": "same_process",
             "artifact_names": ["HANGZHOU_u0234_fps2_r0.json", "HANGZHOU_u0234_fps2_r1.json"]},
            {"group_id": "same_WUHAN_u0217", "kind": "same_process",
             "artifact_names": ["WUHAN_u0217_fps2_r0.json", "WUHAN_u0217_fps2_r1.json"]},
            {"group_id": "cross_DALI_u0555", "kind": "cross_replica",
             "artifact_names": [
                 "DALI_u0555_fps2_r0.json", "DALI_u0555_fps2_cross_replica_HANGZHOU.json"
             ]},
        ],
        "class_support_artifacts": [
            "DALI_u0548_fps2_r0.json", "DALI_u0555_fps2_r0.json",
            "DALI_u0501_fps2_potential_unknown.json", "HANGZHOU_u0234_fps2_r0.json",
            "WUHAN_u0217_fps2_r0.json", "WUHAN_u0171_fps2_r0.json",
        ],
        "eventization_canonical_artifacts": [
            "DALI_u0548_fps2_r0.json", "DALI_u0555_fps2_r0.json",
            "DALI_u0501_fps2_potential_unknown.json", "HANGZHOU_u0234_fps2_r0.json",
            "WUHAN_u0217_fps2_r0.json", "WUHAN_u0171_fps2_r0.json",
        ],
        "hard_gates": {
            "authentication": "exact 11 calls and all bound identities; zero retry/extra/missing/failure",
            "parsing": "11/11 strict parse; exact keys; frozen label vocabulary; no time field",
            "same_process_label_reproducibility": "all three pairs match authoritative label",
            "cross_replica_label_reproducibility": "DALI_u0555 anchor labels and processed inputs match",
            "exact_raw_reproducibility": "reported diagnostic because decoding is deterministic",
            "class_support": "at least one relevant and one not_relevant; unknown not required",
            "eventization": "order and diagnostics invariant; boundaries only from units; K3 hash exact",
        },
        "non_gating_diagnostics": [
            "agent polarity disagreement", "agent claim grounding", "signal-lane interpretation",
            "ego-path interpretation", "evidence plausibility", "human semantic concern",
        ],
        "scope": (
            "A pass supports requesting separate approval for 1475-unit labeling only; it does not "
            "authorize full-grid or downstream YOLO, replay, headroom, or controller work."
        ),
    }
    write_json_once(PREREG, prereg)


def build_code_version() -> None:
    write_json_once(CODE_VERSION, {
        "task_start_branch": "research/accelerated-event-query-v1",
        "task_start_git_head": "eef5050cd3e4b821509e970d70a62072186b31f1",
        "baseline_branch": "dspro",
        "baseline_commit": "5047241b0561b911b9a519b18e8e7591c0074e70",
        "observed_merge_base": "5047241b0561b911b9a519b18e8e7591c0074e70",
        "package_build_git_head": _git("rev-parse", "HEAD"),
        "task_start_dirty_state": [
            "?? benchmarks/safety_critical_driving_event_reference_pilot_v1/",
            "?? datasets/DADA-2000/",
            "?? src/garc_eval/safety_reference_pilot/",
            "?? tests/safety_reference_pilot/",
        ],
        "task_start_gpu_snapshot": {
            "timestamp_utc": "2026-07-29 12:34:26",
            "driver": "535.129.03",
            "cuda_reported": "12.2",
            "gpu_count": 8,
            "gpu_model": "NVIDIA A100-SXM4-80GB",
            "note": "GPU 0 and 4-7 had existing memory/utilization; no V3 inference was launched.",
        },
        "v2_frozen_evidence_commit": "eef5050cd",
        "v2_decision": "REVISE_ORACLE_PROTOCOL",
    })


def main() -> None:
    build_schema_and_k3()
    frame_manifest = build_frames_and_selection()
    call_manifest = build_calls(frame_manifest)
    build_regression()
    build_mapping()
    build_cost()
    build_prereg(call_manifest)
    build_code_version()
    print(json.dumps({
        "status": "BUILT_UNSEALED",
        "preflight_root": str(BASE.relative_to(ROOT)),
        "call_count": call_manifest["authorized_call_count"],
        "preregistration_sha256": sha256_file(PREREG),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
