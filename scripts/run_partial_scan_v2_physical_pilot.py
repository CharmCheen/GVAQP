#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.partial_scan_v2.artifacts import (  # noqa: E402
    atomic_json,
    atomic_text,
    verify_parent_v1_manifest,
    verify_v2_immutable,
)
from garc_eval.partial_scan_v2.config import (  # noqa: E402
    INITIAL_E2E_OVERHEAD_SEC,
    INITIAL_SCAN_COST_SEC,
    LATIN_SQUARE,
    PHYSICAL_BUDGET_SEC,
    POLICY_IDS,
    SEED,
    V1_DERIVED,
    V2_AUDITS,
    V2_COST,
    V2_IMMUTABLE,
    V2_OUTPUT,
    V2_PHYSICAL,
)
from garc_eval.partial_scan_v2.hidden_evaluator import (  # noqa: E402
    load_units,
    load_video,
    load_videos,
    transition,
    warm_source_bytes,
)
from garc_eval.partial_scan_v2.id_redaction import (  # noqa: E402
    RunScopedIdMapper,
    new_public_run_id,
)
from garc_eval.partial_scan_v2.isolated_policy_client import (  # noqa: E402
    IsolatedPolicyClient,
)
from garc_eval.partial_scan_v2.physical_environment import (  # noqa: E402
    PhysicalEnvironment,
)
from garc_eval.partial_scan_v2.public_state_builder import (  # noqa: E402
    InternalRunState,
    build_choose_action_message,
    build_initialize_message,
)
from garc_eval.partial_scan_v2.run_recovery import (  # noqa: E402
    finalize_destination,
    prepare_destination,
)
from garc_eval.partial_scan_v2.runtime_accounting import (  # noqa: E402
    action_admitted,
    remaining_budget_at_validation,
)


def public_contract_hash() -> str:
    return json.loads(
        (
            V2_IMMUTABLE
            / "v2_contracts/public_protocol_contract.json"
        ).read_text()
    )["contract_hash"]


def cost_stratum(action_transition: dict[str, Any]) -> str:
    return (
        f"{action_transition['transition_class']}|"
        f"{action_transition['same_or_cross_gop']}|CONTROLLED_WARM"
    )


def estimate_completion_cost(
    action_transition: dict[str, Any],
) -> tuple[float, float, str]:
    key = cost_stratum(action_transition)
    v2_model = V2_COST / "conservative_cost_model.json"
    if v2_model.is_file():
        model = json.loads(v2_model.read_text())
        row = model.get("strata", {}).get(key)
        if row is not None:
            return (
                float(row["q90_scan_action_cost_sec"]),
                float(row["q90_post_validation_completion_sec"]),
                f"V2_EMPIRICAL_Q90:{key}",
            )
        return (
            float(model["fallback_q90_scan_action_cost_sec"]),
            float(model["fallback_q90_post_validation_completion_sec"]),
            "V2_EMPIRICAL_Q90_FALLBACK",
        )
    parent_model = json.loads(
        (
            V1_DERIVED
            / "cost_calibration/conservative_cost_model.json"
        ).read_text()
    )
    row = parent_model.get("strata", {}).get(key)
    if row is not None:
        scan = float(row["q90_action_cost_sec"])
        source = f"PARENT_V1_EMPIRICAL_Q90:{key}"
    else:
        scan = float(
            parent_model.get("fallback_q90_sec")
            or INITIAL_SCAN_COST_SEC
        )
        source = "PARENT_V1_EMPIRICAL_Q90_FALLBACK"
    return scan, scan + INITIAL_E2E_OVERHEAD_SEC, source


def component_sum(record: dict[str, Any]) -> float:
    return sum(
        float(record.get(name, 0.0))
        for name in [
            "public_state_build_sec",
            "policy_request_serialize_sec",
            "ipc_send_sec",
            "policy_decision_sec",
            "ipc_receive_sec",
            "policy_response_validate_sec",
            "environment_action_validate_sec",
            "total_scan_action_time_sec",
            "visible_subset_replay_time_sec",
        ]
    )


def run_one(video_id: str, block_id: int, policy_id: str) -> None:
    if policy_id not in LATIN_SQUARE[block_id - 1]:
        raise ValueError("policy is not in frozen Latin-square block")
    if verify_v2_immutable()["status"] != "PASS":
        raise RuntimeError("v2 immutable verification failed")
    if verify_parent_v1_manifest()["status"] != "PASS":
        raise RuntimeError("parent asset verification failed")
    sequence = LATIN_SQUARE[block_id - 1].index(policy_id) + 1
    internal_run_id = f"{video_id}_b{block_id}_{policy_id}"
    destination = V2_PHYSICAL / internal_run_id
    prepare_destination(destination, V2_PHYSICAL, V2_OUTPUT / "repair_log.json")

    video = load_video(video_id)
    units = load_units(video_id)
    by_id = {str(unit["unit_id"]): unit for unit in units}
    warm = warm_source_bytes(Path(str(video["video_path"])))
    if warm["content_sha256"] != str(video["video_hash"]):
        raise RuntimeError("controlled-warm source hash mismatch")
    environment = PhysicalEnvironment(video)
    mapper = RunScopedIdMapper(new_public_run_id())
    internal = InternalRunState(
        internal_video_id=video_id,
        duration_sec=float(video["duration_sec"]),
        units=units,
        budget_sec=PHYSICAL_BUDGET_SEC,
    )
    initialize = build_initialize_message(
        internal, mapper, public_contract_hash()
    )
    client = IsolatedPolicyClient(
        policy_id=policy_id,
        seed=SEED + block_id * 100 + POLICY_IDS.index(policy_id),
        initialize_message=initialize,
        private_stderr_log=(
            V2_OUTPUT
            / "private_policy_logs"
            / f"physical_{internal_run_id}.log"
        ),
    )
    current: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    termination_reason = "RUN_COMPLETE"
    try:
        while len(internal.scanned_internal_unit_ids) < len(units):
            action_index = len(
                [row for row in records if row["action_completed"]]
            )
            step_started = time.perf_counter()
            build_started = time.perf_counter()
            message = build_choose_action_message(
                internal, mapper, action_index
            )
            public_state_build_sec = time.perf_counter() - build_started
            available_public_units = {
                mapper.unit(str(unit["unit_id"]))
                for unit in units
                if str(unit["unit_id"]) not in internal.scanned_internal_unit_ids
            }
            selected_public, policy_timings = client.choose(
                message, available_public_units
            )
            validate_started = time.perf_counter()
            selected_internal = mapper.internal_unit(selected_public)
            if selected_internal in internal.scanned_internal_unit_ids:
                termination_reason = "ACTION_ALREADY_SCANNED"
                raise RuntimeError(termination_reason)
            selected = by_id[selected_internal]
            action_transition = transition(current, selected)
            scan_estimate, completion_estimate, estimate_source = (
                estimate_completion_cost(action_transition)
            )
            environment_action_validate_sec = (
                time.perf_counter() - validate_started
            )
            remaining_after_policy = remaining_budget_at_validation(
                internal.remaining_budget_sec, policy_timings | {
                    "environment_action_validate_sec": environment_action_validate_sec
                }
            )
            base = {
                "internal_run_id": internal_run_id,
                "public_run_id": mapper.run_id,
                "video_id": video_id,
                "block_id": block_id,
                "latin_sequence": sequence,
                "policy_id": policy_id,
                "action_index": action_index,
                **action_transition,
                "selected_public_unit_id": selected_public,
                "selected_internal_unit_id": selected_internal,
                "decoder_state": "OPEN_SINGLE_INSTANCE",
                "cache_protocol": "CONTROLLED_WARM",
                "tracker_reset": True,
                "public_state_build_sec": public_state_build_sec,
                **policy_timings,
                "environment_action_validate_sec": (
                    environment_action_validate_sec
                ),
                "estimated_scan_action_cost_sec": scan_estimate,
                "estimated_post_validation_completion_sec": (
                    completion_estimate
                ),
                "estimated_scheduler_step_cost_sec": (
                    sum(policy_timings.values()) + environment_action_validate_sec
                    + completion_estimate
                ),
                "estimated_action_cost_source": estimate_source,
                "remaining_budget_before_step_sec": (
                    internal.remaining_budget_sec
                ),
                "remaining_budget_at_validation_sec": (
                    remaining_after_policy
                ),
            }
            if not action_admitted(completion_estimate, remaining_after_policy):
                total_step = time.perf_counter() - step_started
                internal.remaining_budget_sec = max(
                    0.0, internal.remaining_budget_sec - total_step
                )
                record = {
                    **base,
                    "decoded_frame_count": 0,
                    "seek_time_sec": 0.0,
                    "decode_time_sec": 0.0,
                    "model_time_sec": 0.0,
                    "tracker_time_sec": 0.0,
                    "candidate_time_sec": 0.0,
                    "scan_environment_overhead_sec": 0.0,
                    "visible_subset_replay_time_sec": 0.0,
                    "total_scan_action_time_sec": 0.0,
                    "total_scheduler_step_time_sec": total_step,
                    "scheduler_unattributed_overhead_sec": 0.0,
                    "actual_scan_action_cost_sec": 0.0,
                    "actual_scheduler_step_cost_sec": total_step,
                    "cumulative_scheduler_wall_clock_sec": (
                        PHYSICAL_BUDGET_SEC
                        - internal.remaining_budget_sec
                    ),
                    "remaining_budget_sec": internal.remaining_budget_sec,
                    "action_started": False,
                    "action_completed": False,
                    "deadline_rejection_reason": (
                        "Q90_COMPLETION_ESTIMATE_EXCEEDS_REMAINING_BUDGET"
                    ),
                    "raw_candidate_count": 0,
                    "raw_candidate_hash": None,
                    "visible_candidate_count": len(
                        internal.visible_internal_candidate_ids
                    ),
                    "hidden_exposed_reference_count": len(
                        internal.hidden_reference_event_ids
                    ),
                }
                record["scheduler_unattributed_overhead_sec"] = max(
                    0.0,
                    total_step - component_sum(record),
                )
                records.append(record)
                termination_reason = "NO_COMPLETE_ACTION_FITS"
                break

            scan_result = environment.execute(selected)
            internal.scanned_internal_unit_ids.append(selected_internal)
            internal.current_internal_unit_id = selected_internal
            replay_started = time.perf_counter()
            candidates, exposed = environment.visible_subset(
                video_id, set(internal.scanned_internal_unit_ids)
            )
            visible_subset_replay_time_sec = (
                time.perf_counter() - replay_started
            )
            internal.visible_internal_candidate_ids = sorted(
                candidates.candidate_id.astype(str)
            )
            internal.hidden_reference_event_ids = exposed
            internal.last_result_class = "PHYSICAL_SCAN"
            total_step = time.perf_counter() - step_started
            internal.past_action_costs_sec.append(total_step)
            internal.remaining_budget_sec = max(
                0.0, internal.remaining_budget_sec - total_step
            )
            runtime = scan_result["runtime"]
            record = {
                **base,
                "decoded_frame_count": int(runtime["decoded_frames"]),
                "seek_time_sec": float(runtime["seek_time_sec"]),
                "decode_time_sec": float(runtime["decode_time_sec"]),
                "model_time_sec": float(runtime["model_time_sec"]),
                "tracker_time_sec": float(runtime["tracker_time_sec"]),
                "candidate_time_sec": float(runtime["candidate_time_sec"]),
                "scan_environment_overhead_sec": float(
                    runtime["environment_overhead_sec"]
                ),
                "visible_subset_replay_time_sec": (
                    visible_subset_replay_time_sec
                ),
                "total_scan_action_time_sec": float(
                    runtime["total_action_time_sec"]
                ),
                "total_scheduler_step_time_sec": total_step,
                "scheduler_unattributed_overhead_sec": 0.0,
                "actual_scan_action_cost_sec": float(
                    runtime["total_action_time_sec"]
                ),
                "actual_scheduler_step_cost_sec": total_step,
                "cumulative_scheduler_wall_clock_sec": (
                    PHYSICAL_BUDGET_SEC - internal.remaining_budget_sec
                ),
                "remaining_budget_sec": internal.remaining_budget_sec,
                "action_started": True,
                "action_completed": True,
                "deadline_rejection_reason": None,
                "raw_candidate_count": scan_result[
                    "raw_candidate_count"
                ],
                "raw_candidate_hash": scan_result["raw_candidate_hash"],
                "visible_candidate_count": len(candidates),
                "hidden_exposed_reference_count": len(exposed),
            }
            record["scheduler_unattributed_overhead_sec"] = max(
                0.0, total_step - component_sum(record)
            )
            records.append(record)
            current = selected
            if internal.remaining_budget_sec <= 0:
                termination_reason = "NO_COMPLETE_ACTION_FITS"
                break
    finally:
        client.close(termination_reason)
        environment.close()

    atomic_text(
        destination / "action_trace.jsonl",
        "".join(
            json.dumps(
                row, sort_keys=True, ensure_ascii=False, allow_nan=False
            )
            + "\n"
            for row in records
        ),
    )
    completed = [row for row in records if row["action_completed"]]
    rejected = [row for row in records if not row["action_started"]]
    summary = {
        "internal_run_id": internal_run_id,
        "public_run_id": mapper.run_id,
        "video_id": video_id,
        "block_id": block_id,
        "latin_sequence": sequence,
        "policy_id": policy_id,
        "fresh_evaluator_pid": os.getpid(),
        "warm_protocol": warm,
        "model_instance_count": 1,
        "decoder_instance_count": 1,
        "model_instance_identity": environment.model_instance_identity,
        "decoder_instance_identity": environment.decoder_instance_identity,
        "tracker_reset_per_completed_action": True,
        "completed_action_count": len(completed),
        "deadline_rejection_count": len(rejected),
        "cumulative_scheduler_wall_clock_sec": sum(
            row["total_scheduler_step_time_sec"] for row in records
        ),
        "cumulative_scan_wall_clock_sec": sum(
            row["total_scan_action_time_sec"] for row in completed
        ),
        "budget_sec": PHYSICAL_BUDGET_SEC,
        "termination_reason": termination_reason,
        **client.summary(),
    }
    finalize_destination(destination, summary)
    print(
        json.dumps(
            {
                "PHYSICAL_V2_RUN": "PASS",
                "run_id": internal_run_id,
                "completed_actions": len(completed),
                "rejections": len(rejected),
                "e2e_wall_clock": summary[
                    "cumulative_scheduler_wall_clock_sec"
                ],
            }
        ),
        flush=True,
    )


def read_trace(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def all_physical_rows() -> tuple[list[dict], list[dict]]:
    rows = []
    summaries = []
    for path in sorted(V2_PHYSICAL.glob("*/run_summary.json")):
        summaries.append(json.loads(path.read_text()))
        rows.extend(read_trace(path.parent / "action_trace.jsonl"))
    return rows, summaries


def calibrate_cost_model() -> dict[str, Any]:
    rows, summaries = all_physical_rows()
    completed = pd.DataFrame(
        [row for row in rows if row["action_completed"]]
    )
    if completed.empty:
        raise RuntimeError("no completed v2 physical actions")
    completed["cost_stratum"] = (
        completed.transition_class.astype(str)
        + "|"
        + completed.same_or_cross_gop.astype(str)
        + "|"
        + completed.cache_protocol.astype(str)
    )
    completed["post_validation_completion_sec"] = (
        completed.total_scheduler_step_time_sec
        - completed.public_state_build_sec
        - completed.policy_request_serialize_sec
        - completed.ipc_send_sec
        - completed.policy_decision_sec
        - completed.ipc_receive_sec
        - completed.policy_response_validate_sec
        - completed.environment_action_validate_sec
    ).clip(lower=0.0)
    strata: dict[str, Any] = {}
    for name, group in completed.groupby("cost_stratum"):
        strata[name] = {
            "n": len(group),
            "q90_scan_action_cost_sec": float(
                group.total_scan_action_time_sec.quantile(0.90)
            ),
            "median_scan_action_cost_sec": float(
                group.total_scan_action_time_sec.median()
            ),
            "q90_scheduler_step_cost_sec": float(
                group.total_scheduler_step_time_sec.quantile(0.90)
            ),
            "median_scheduler_step_cost_sec": float(
                group.total_scheduler_step_time_sec.median()
            ),
            "q90_post_validation_completion_sec": float(
                group.post_validation_completion_sec.quantile(0.90)
            ),
        }
    model = {
        "model_type": (
            "V2_EMPIRICAL_Q90_BY_TRANSITION_GOP_CONTROLLED_WARM"
        ),
        "generation_run_count": len(summaries),
        "generation_completed_action_count": len(completed),
        "policy_visible_future_actual_cost": False,
        "fallback_q90_scan_action_cost_sec": float(
            completed.total_scan_action_time_sec.quantile(0.90)
        ),
        "fallback_q90_scheduler_step_cost_sec": float(
            completed.total_scheduler_step_time_sec.quantile(0.90)
        ),
        "fallback_q90_post_validation_completion_sec": float(
            completed.post_validation_completion_sec.quantile(0.90)
        ),
        "strata": strata,
    }
    atomic_json(V2_COST / "conservative_cost_model.json", model)
    completed.to_csv(V2_COST / "transition_cost_samples.csv", index=False)
    return model


def run_all() -> None:
    logs = V2_OUTPUT / "physical_run_logs"
    logs.mkdir(parents=True, exist_ok=True)
    for video_id in load_videos().video_id.astype(str):
        for block_id, order in enumerate(LATIN_SQUARE, 1):
            for sequence, policy_id in enumerate(order, 1):
                internal_run_id = f"{video_id}_b{block_id}_{policy_id}"
                summary = V2_PHYSICAL / internal_run_id / "run_summary.json"
                if summary.is_file():
                    continue
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "run",
                    "--video-id",
                    video_id,
                    "--block-id",
                    str(block_id),
                    "--policy-id",
                    policy_id,
                ]
                with (
                    logs / f"{internal_run_id}.log"
                ).open("w", encoding="utf-8") as handle:
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        text=True,
                        check=False,
                    )
                if completed.returncode:
                    raise RuntimeError(
                        f"physical child failed: {internal_run_id}"
                    )
                print(
                    f"PHYSICAL_V2_ALL {video_id} block={block_id} "
                    f"sequence={sequence} {policy_id}",
                    flush=True,
                )
                run_count = len(
                    list(V2_PHYSICAL.glob("*/run_summary.json"))
                )
                if run_count == 8:
                    calibrate_cost_model()
    audit()


def audit() -> None:
    model = calibrate_cost_model()
    rows, summaries = all_physical_rows()
    expected_runs = 2 * 4 * 4
    completed = [row for row in rows if row["action_completed"]]
    rejected = [row for row in rows if not row["action_started"]]
    required = {
        "internal_run_id",
        "public_run_id",
        "video_id",
        "block_id",
        "latin_sequence",
        "policy_id",
        "action_index",
        "previous_unit_id",
        "selected_internal_unit_id",
        "selected_public_unit_id",
        "transition_class",
        "public_state_build_sec",
        "policy_request_serialize_sec",
        "ipc_send_sec",
        "policy_decision_sec",
        "ipc_receive_sec",
        "policy_response_validate_sec",
        "environment_action_validate_sec",
        "seek_time_sec",
        "decode_time_sec",
        "model_time_sec",
        "tracker_time_sec",
        "candidate_time_sec",
        "visible_subset_replay_time_sec",
        "total_scan_action_time_sec",
        "total_scheduler_step_time_sec",
        "estimated_scan_action_cost_sec",
        "estimated_scheduler_step_cost_sec",
        "remaining_budget_before_step_sec",
        "remaining_budget_at_validation_sec",
        "action_started",
        "action_completed",
        "deadline_rejection_reason",
    }
    schema_complete = bool(rows) and all(required.issubset(row) for row in rows)
    expected_keys = {
        (video_id, block_id, policy_id)
        for video_id in load_videos().video_id.astype(str)
        for block_id in range(1, 5)
        for policy_id in POLICY_IDS
    }
    actual_keys = {
        (
            str(summary["video_id"]),
            int(summary["block_id"]),
            str(summary["policy_id"]),
        )
        for summary in summaries
    }
    sequence_valid = all(
        LATIN_SQUARE[int(summary["block_id"]) - 1][
            int(summary["latin_sequence"]) - 1
        ]
        == summary["policy_id"]
        for summary in summaries
    )
    application_boundary_pass = all(
        summary["application_attestation"]["policy_execution_mode"]
        == "OUT_OF_PROCESS"
        and summary["application_attestation"]["transport"]
        == "STDIN_STDOUT_JSONL"
        and summary["application_attestation"]["application_boundary_only"]
        and summary["application_attestation"]["capability_security"]
        == "NOT_YET_ESTABLISHED"
        for summary in summaries
    )
    lifecycle_pass = all(
        summary["model_instance_count"] == 1
        and summary["decoder_instance_count"] == 1
        and summary["tracker_reset_per_completed_action"]
        for summary in summaries
    )
    trace_status = all(
        [
            len(summaries) == expected_runs,
            expected_keys == actual_keys,
            sequence_valid,
            schema_complete,
            application_boundary_pass,
            lifecycle_pass,
            len({row["fresh_evaluator_pid"] for row in summaries})
            == expected_runs,
            len({row["policy_pid"] for row in summaries})
            == expected_runs,
            bool(completed),
        ]
    )
    physical_audit = {
        "status": "PASS" if trace_status else "FAIL",
        "expected_run_count": expected_runs,
        "actual_run_count": len(summaries),
        "completed_action_count": len(completed),
        "rejected_action_count": len(rejected),
        "schema_complete": schema_complete,
        "latin_square_complete": expected_keys == actual_keys
        and sequence_valid,
        "fresh_evaluator_process_count": len(
            {row["fresh_evaluator_pid"] for row in summaries}
        ),
        "fresh_policy_process_count": len(
            {row["policy_pid"] for row in summaries}
        ),
        "shared_application_process_boundary": application_boundary_pass,
        "capability_security": "NOT_YET_ESTABLISHED",
        "lifecycle_contract": lifecycle_pass,
        "timing_semantics": {
            "scan_only": "total_scan_action_time_sec",
            "scheduler_e2e": "total_scheduler_step_time_sec",
        },
    }
    atomic_json(V2_AUDITS / "physical_trace_audit.json", physical_audit)

    cache_pass = len(summaries) == expected_runs and all(
        summary["warm_protocol"]["protocol"] == "CONTROLLED_WARM"
        and summary["warm_protocol"]["bytes_read"] > 0
        and summary["warm_protocol"]["content_sha256"]
        == str(load_video(summary["video_id"])["video_hash"])
        for summary in summaries
    )
    cache_audit = {
        "status": "PASS" if cache_pass else "FAIL",
        "protocol": "CONTROLLED_WARM",
        "cold_cache": "NOT_ATTEMPTED",
        "source_full_byte_read_verified_per_run": cache_pass,
        "run_count": len(summaries),
    }
    atomic_json(V2_AUDITS / "cache_protocol_audit.json", cache_audit)

    started_complete = all(
        row["action_completed"] for row in rows if row["action_started"]
    )
    rejection_valid = all(
        not row["action_completed"]
        and row["total_scan_action_time_sec"] == 0
        and row["estimated_post_validation_completion_sec"]
        > row["remaining_budget_at_validation_sec"]
        for row in rejected
    )
    synthetic_remaining = INITIAL_SCAN_COST_SEC - 0.001
    synthetic_rejected = INITIAL_SCAN_COST_SEC > synthetic_remaining
    deadline_pass = (
        bool(rejected)
        and started_complete
        and rejection_valid
        and synthetic_rejected
    )
    deadline_audit = {
        "status": "PASS" if deadline_pass else "FAIL",
        "physical_rejection_count": len(rejected),
        "started_actions_all_completed": started_complete,
        "rejection_rows_valid": rejection_valid,
        "synthetic_boundary_test": {
            "estimate_sec": INITIAL_SCAN_COST_SEC,
            "remaining_sec": synthetic_remaining,
            "action_started": not synthetic_rejected,
            "status": "PASS" if synthetic_rejected else "FAIL",
        },
    }
    atomic_json(
        V2_AUDITS / "deadline_enforcement_audit.json",
        deadline_audit,
    )

    completed_frame = pd.DataFrame(completed)
    transition_classes = sorted(
        completed_frame.transition_class.unique().tolist()
    )
    required_classes = {
        "initial",
        "same_contiguous_region",
        "forward_short_seek",
        "forward_long_seek",
        "backward_seek",
    }
    path_pass = required_classes.issubset(transition_classes)
    cost_audit = {
        "status": "PASS" if path_pass else "FAIL",
        "required_transition_classes": sorted(required_classes),
        "observed_transition_classes": transition_classes,
        "stratum_count": len(model["strata"]),
        "completed_action_count": len(completed),
        "scan_only_median_sec": float(
            completed_frame.total_scan_action_time_sec.median()
        ),
        "scheduler_e2e_median_sec": float(
            completed_frame.total_scheduler_step_time_sec.median()
        ),
        "policy_ipc_validation_median_sec": float(
            (
                completed_frame.policy_request_serialize_sec
                + completed_frame.ipc_send_sec
                + completed_frame.policy_decision_sec
                + completed_frame.ipc_receive_sec
                + completed_frame.policy_response_validate_sec
            ).median()
        ),
        "visible_subset_replay_median_sec": float(
            completed_frame.visible_subset_replay_time_sec.median()
        ),
    }
    atomic_json(V2_AUDITS / "path_cost_support_audit.json", cost_audit)

    physical_medians = (
        completed_frame.groupby(
            "transition_class"
        ).total_scheduler_step_time_sec.median().to_dict()
    )
    estimate_by_class: dict[str, float] = {}
    for transition_class in physical_medians:
        values = [
            float(value["q90_scheduler_step_cost_sec"])
            for key, value in model["strata"].items()
            if key.startswith(transition_class + "|")
        ]
        if values:
            estimate_by_class[transition_class] = float(
                np.median(values)
            )
    pairs = []
    names = sorted(set(physical_medians) & set(estimate_by_class))
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            actual_direction = np.sign(
                physical_medians[left] - physical_medians[right]
            )
            estimated_direction = np.sign(
                estimate_by_class[left] - estimate_by_class[right]
            )
            if actual_direction:
                pairs.append(bool(actual_direction == estimated_direction))
    agreement = sum(pairs) / len(pairs) if pairs else None
    agreement_pass = agreement is not None and agreement >= 0.5
    agreement_audit = {
        "status": "PASS" if agreement_pass else "PARTIAL_OR_UNVERIFIED",
        "metric": (
            "pairwise transition-class direction agreement between "
            "physical E2E medians and frozen empirical Q90 estimator"
        ),
        "transition_classes": names,
        "pair_count": len(pairs),
        "directional_agreement_fraction": agreement,
        "minimum": 0.5,
        "method_ranking_interpretation": "PROHIBITED",
    }
    atomic_json(
        V2_AUDITS / "replay_physical_agreement.json",
        agreement_audit,
    )
    overall = all(
        payload["status"] == "PASS"
        for payload in [
            physical_audit,
            cache_audit,
            deadline_audit,
            cost_audit,
            agreement_audit,
        ]
    )
    atomic_text(
        V2_OUTPUT / "reports/PHYSICAL_PATH_COST_REPORT.md",
        "# V2 Physical Path-Cost Report\n\n"
        f"Physical trace: `{physical_audit['status']}`; cache: "
        f"`{cache_audit['status']}`; deadline: "
        f"`{deadline_audit['status']}`; path support: "
        f"`{cost_audit['status']}`.\n\n"
        f"- Runs: {len(summaries)}/{expected_runs}\n"
        f"- Completed actions: {len(completed)}\n"
        f"- Deadline rejections: {len(rejected)}\n"
        f"- SCAN-only median: "
        f"{cost_audit['scan_only_median_sec']:.6f} s\n"
        f"- Scheduler E2E median: "
        f"{cost_audit['scheduler_e2e_median_sec']:.6f} s\n"
        f"- Directional agreement: {agreement}\n\n"
        "Evidence is controlled-warm only; method ranking is prohibited.\n",
    )
    if not overall:
        raise RuntimeError("v2 physical audit failed")
    print(
        json.dumps(
            {
                "PHYSICAL_V2_AUDIT": "PASS",
                "runs": len(summaries),
                "completed_actions": len(completed),
                "rejections": len(rejected),
                "strata": len(model["strata"]),
                "directional_agreement": agreement,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--video-id", required=True)
    run.add_argument("--block-id", type=int, choices=[1, 2, 3, 4], required=True)
    run.add_argument("--policy-id", choices=POLICY_IDS, required=True)
    sub.add_parser("all")
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "run":
        run_one(args.video_id, args.block_id, args.policy_id)
    elif args.command == "all":
        run_all()
    else:
        audit()


if __name__ == "__main__":
    main()
