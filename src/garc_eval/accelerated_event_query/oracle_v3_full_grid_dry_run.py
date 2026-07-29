"""No-inference end-to-end mechanics and fault injection for the full-grid package."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .oracle_v3_full_grid_analyzer import analyze_execution
from .oracle_v3_full_grid_control import GlobalFailStopCoordinator, append_hash_chain
from .oracle_v3_full_grid_finalizer import decide, finalize_execution
from .oracle_v3_full_grid_manifest import EXPECTED_UNIT_COUNT
from .oracle_v3_full_grid_package import DECISIONS, PACKAGE, SCHEDULE, SEAL, UNITS
from .oracle_v3_manifest import atomic_text, canonical_hash, load_json, sha256_file


def _mock_raw(unit: dict[str, Any], worker: dict[str, Any], seal_sha: str) -> dict[str, Any]:
    # Synthetic pattern exercises K3 and unknown coverage without claiming any visual label.
    if unit["ordinal"] in {0, 567, 1128}:
        label = "unknown"
    elif unit["ordinal"] % 97 in {20, 21}:
        label = "relevant"
    else:
        label = "not_relevant"
    raw = json.dumps({
        "label": label,
        "confidence": "low",
        "evidence": "synthetic dry-run payload; not an oracle observation",
    }, separators=(",", ":"))
    parsed = {
        "label": label,
        "confidence": "low",
        "evidence": "synthetic dry-run payload; not an oracle observation",
    }
    attempt_id = f"MOCK:{unit['worker_id']}:{unit['unit_id']}"
    session_id = f"MOCK_SESSION:{unit['worker_id']}"
    processed = hashlib.sha256(f"MOCK_PROCESSED:{unit['unit_id']}".encode()).hexdigest()
    generated = hashlib.sha256(f"MOCK_TOKENS:{unit['unit_id']}".encode()).hexdigest()
    identity = {
        "experiment_id": unit["experiment_id"],
        "execution_seal_sha256": seal_sha,
        "unit_id": unit["unit_id"],
        "call_spec_sha256": unit["call_spec_sha256"],
        "frame_set_sha256": unit["frame_set_sha256"],
        "mock": True,
    }
    record = {
        "status": "MOCK_DRY_RUN_RECORD_NOT_ORACLE",
        "mock_not_oracle": True,
        "experiment_id": unit["experiment_id"],
        "execution_seal_sha256": seal_sha,
        "unit_id": unit["unit_id"],
        "unit_ordinal": unit["ordinal"],
        "video_id": unit["video_id"],
        "worker_id": unit["worker_id"],
        "physical_gpu_ids": worker["physical_gpu_ids"],
        "call_spec_sha256": unit["call_spec_sha256"],
        "frame_set_sha256": unit["frame_set_sha256"],
        "frame_count": unit["frame_count"],
        "execution_session_id": session_id,
        "attempt_id": attempt_id,
        "input_identity_sha256": canonical_hash(identity),
        "model_input_identity_sha256": canonical_hash({**identity, "processor": "MOCK"}),
        "processed_input_sha256": processed,
        "generated_token_ids_sha256": generated,
        "raw": raw,
        "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "parse_status": "ok",
        "authoritative_label": label,
        "parsed": parsed,
        "runtime": {
            "worker_id": unit["worker_id"],
            "model_load_seconds": 0.01,
            "inference_seconds": 0.001,
            "total_call_seconds": 0.002,
        },
    }
    record["record_payload_sha256"] = canonical_hash(record)
    return record


def run_complete_mock(execution_root: Path) -> dict[str, Any]:
    units = load_json(UNITS)
    schedule = load_json(SCHEDULE)
    seal_sha = sha256_file(SEAL)
    workers = {row["worker_id"]: row for row in schedule["workers"]}
    coordinator = GlobalFailStopCoordinator(
        execution_root,
        execution_seal_sha256=seal_sha,
        worker_bindings={worker_id: {
            "physical_gpu_ids": row["physical_gpu_ids"], "unit_ids": row["unit_ids"]
        } for worker_id, row in workers.items()},
        envelope_a100_gpu_hours=19.4,
        call_reservation_wall_seconds=23.579961206763983,
        model_load_reservation_wall_seconds=30.0,
    )
    coordinator.initialize()
    for worker_id, worker in workers.items():
        ledger = execution_root / worker["attempt_ledger_relative_path"]
        coordinator.start_model_load(worker_id, worker["physical_gpu_ids"])
        append_hash_chain(ledger, {
            "event": "MODEL_LOAD_STARTED", "worker_id": worker_id,
            "physical_gpu_ids": worker["physical_gpu_ids"],
        })
        coordinator.complete_model_load(worker_id, 0.01)
        append_hash_chain(ledger, {
            "event": "MODEL_LOAD_COMPLETED", "worker_id": worker_id,
            "physical_gpu_ids": worker["physical_gpu_ids"],
            "execution_session_id": f"MOCK_SESSION:{worker_id}",
            "wall_seconds": 0.01,
        })
    unit_map = {row["unit_id"]: row for row in units["units"]}
    for unit in units["units"]:
        worker = workers[unit["worker_id"]]
        ledger = execution_root / worker["attempt_ledger_relative_path"]
        record = _mock_raw(unit, worker, seal_sha)
        common = {
            "worker_id": unit["worker_id"], "unit_id": unit["unit_id"],
            "call_spec_sha256": unit["call_spec_sha256"],
            "attempt_id": record["attempt_id"],
            "execution_session_id": record["execution_session_id"],
        }
        append_hash_chain(ledger, {
            "event": "PREPARED", **common,
            "processed_input_sha256": record["processed_input_sha256"],
        })
        coordinator.reserve_call(
            worker_id=unit["worker_id"], gpu_pair=worker["physical_gpu_ids"],
            unit_id=unit["unit_id"], call_spec_sha256=unit["call_spec_sha256"],
        )
        append_hash_chain(ledger, {
            "event": "INFERENCE_STARTED", **common,
            "processed_input_sha256": record["processed_input_sha256"],
        })
        append_hash_chain(ledger, {
            "event": "INFERENCE_COMPLETED", **common,
            "generated_token_ids_sha256": record["generated_token_ids_sha256"],
        })
        destination = execution_root / unit["raw_output_relative_path"]
        atomic_text(destination, json.dumps(record, indent=2, sort_keys=True) + "\n")
        append_hash_chain(ledger, {
            "event": "ACCEPTED", **common,
            "record_payload_sha256": record["record_payload_sha256"],
        })
        coordinator.complete_call(
            worker_id=unit["worker_id"], unit_id=unit["unit_id"], wall_seconds=0.002
        )
    coordinator.mark_complete(EXPECTED_UNIT_COUNT)
    metrics, _ = analyze_execution(execution_root=execution_root, allow_mock=True)
    finalizer = finalize_execution(execution_root=execution_root, allow_mock=True)
    if finalizer["would_emit_formal_decision"] != "FULL_GRID_PASS_REFERENCE_RELEASED":
        raise RuntimeError("complete mock did not exercise the formal PASS decision path")
    if (execution_root / "FORMAL_REFERENCE_RELEASE.json").exists():
        raise RuntimeError("mock dry-run published a formal reference")
    return {
        "exact_mock_call_count": metrics["authenticated_record_count"],
        "mock_worker_ledger_event_counts": metrics["worker_ledger_event_counts"],
        "mock_global_ledger_event_count": metrics["global_ledger_event_count"],
        "analyzer_authentication_errors": metrics["authentication_errors"],
        "k3_deterministic": metrics["k3"]["deterministic"],
        "finalizer_status": finalizer["status"],
        "would_emit_formal_decision": finalizer["would_emit_formal_decision"],
        "formal_publication_performed": finalizer["formal_publication_performed"],
        "mock_label_pattern_sha256": canonical_hash({
            "rule": "unknown at first unit of each video; relevant at ordinal mod 97 in {20,21}; otherwise not_relevant",
            "not_visual_ground_truth": True,
        }),
    }


def run_fault_injections(root: Path) -> dict[str, Any]:
    schedule = load_json(SCHEDULE)
    units = load_json(UNITS)
    seal_sha = sha256_file(SEAL)
    workers = {row["worker_id"]: row for row in schedule["workers"]}

    def make(name: str, envelope: float = 19.4) -> GlobalFailStopCoordinator:
        return GlobalFailStopCoordinator(
            root / name,
            execution_seal_sha256=seal_sha,
            worker_bindings={worker_id: {
                "physical_gpu_ids": row["physical_gpu_ids"], "unit_ids": row["unit_ids"]
            } for worker_id, row in workers.items()},
            envelope_a100_gpu_hours=envelope,
            call_reservation_wall_seconds=23.579961206763983,
            model_load_reservation_wall_seconds=30.0,
        )

    results: dict[str, bool] = {}
    first_worker = schedule["workers"][0]
    first_unit = units["units"][0]
    c = make("duplicate")
    c.initialize(); c.start_model_load(first_worker["worker_id"], first_worker["physical_gpu_ids"])
    c.complete_model_load(first_worker["worker_id"], 0.01)
    c.reserve_call(worker_id=first_worker["worker_id"], gpu_pair=first_worker["physical_gpu_ids"],
                   unit_id=first_unit["unit_id"], call_spec_sha256=first_unit["call_spec_sha256"])
    try:
        c.reserve_call(worker_id=first_worker["worker_id"], gpu_pair=first_worker["physical_gpu_ids"],
                       unit_id=first_unit["unit_id"], call_spec_sha256=first_unit["call_spec_sha256"])
    except RuntimeError:
        results["duplicate_unit_global_stop"] = c.state()["stop_trigger"] == "duplicate_unit_attempt"

    c = make("gpu")
    c.initialize()
    try:
        c.start_model_load(first_worker["worker_id"], [0, 7])
    except RuntimeError:
        results["gpu_binding_global_stop"] = c.state()["stop_trigger"] == "gpu_binding_mismatch"

    c = make("reload")
    c.initialize(); c.start_model_load(first_worker["worker_id"], first_worker["physical_gpu_ids"])
    c.complete_model_load(first_worker["worker_id"], 0.01)
    try:
        c.start_model_load(first_worker["worker_id"], first_worker["physical_gpu_ids"])
    except RuntimeError:
        results["reload_global_stop"] = c.state()["stop_trigger"] == "unauthorized_model_reload"

    c = make("cost", envelope=0.001)
    c.initialize()
    try:
        c.start_model_load(first_worker["worker_id"], first_worker["physical_gpu_ids"])
    except RuntimeError:
        results["cost_envelope_global_stop"] = c.state()["stop_trigger"] == "cost_envelope_exceeded"

    c = make("resume")
    c.initialize()
    try:
        c.initialize()
    except RuntimeError:
        results["resume_prohibited"] = True

    mapping = load_json(DECISIONS)
    base_metrics = {
        "global_stop_trigger": None,
        "authentication_errors": [],
        "complete": True,
        "authenticated_record_count": EXPECTED_UNIT_COUNT,
        "reload_count": 0, "retry_count": 0, "model_load_count": 3,
        "actual_a100_gpu_hours": 16.0,
        "parse_status_counts": {"ok": EXPECTED_UNIT_COUNT, "parse_failure": 0},
        "coverage_thresholds": {
            "minimum_global_determined_fraction": 0.99,
            "minimum_per_video_determined_fraction": 0.99,
        },
        "oracle_coverage": 1.0,
        "per_video_oracle_coverage": {"DALI": 1.0, "HANGZHOU": 1.0, "WUHAN": 1.0},
        "k3": {"deterministic": True},
    }
    parse_metrics = copy.deepcopy(base_metrics)
    parse_metrics["parse_status_counts"] = {"ok": 1474, "parse_failure": 1}
    results["parse_failure_blocks_release"] = decide(
        parse_metrics, mapping
    ) == "FULL_GRID_FAILED_PROTOCOL"
    unknown_metrics = copy.deepcopy(base_metrics)
    unknown_metrics["oracle_coverage"] = 0.98
    results["unknown_threshold_blocks_release"] = decide(
        unknown_metrics, mapping
    ) == "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"
    auth_metrics = copy.deepcopy(base_metrics)
    auth_metrics["global_stop_trigger"] = "frame_hash_mismatch"
    results["authentication_priority"] = decide(
        auth_metrics, mapping
    ) == "FULL_GRID_ABORTED_AUTHENTICATION"

    partial_root = root / "partial"
    # No records: finalizer must report insufficient evidence and publish nothing formal.
    # Create empty valid worker ledgers so the analyzer can exercise incomplete accounting.
    partial = finalize_execution(execution_root=partial_root, allow_mock=True)
    results["partial_nonpublication"] = all((
        partial["would_emit_formal_decision"] == "INSUFFICIENT_EVIDENCE",
        not (partial_root / "FORMAL_REFERENCE_RELEASE.json").exists(),
    ))
    if not all(results.values()):
        raise RuntimeError(f"fault injection failure: {results}")
    return results
