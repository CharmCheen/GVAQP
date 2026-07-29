from copy import deepcopy

import hashlib
import json
import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer import (
    _validate_record,
)

from garc_eval.accelerated_event_query.oracle_v3_full_grid_finalizer import (
    FORMAL_DECISIONS,
    decide,
)
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash


def mapping():
    value = {"allowed_decisions": sorted(FORMAL_DECISIONS)}
    value["decision_mapping_payload_sha256"] = canonical_hash(value)
    return value


def passing_metrics():
    return {
        "global_stop_trigger": None,
        "authentication_errors": [],
        "complete": True,
        "authenticated_record_count": 1475,
        "reload_count": 0,
        "retry_count": 0,
        "model_load_count": 3,
        "actual_a100_gpu_hours": 16.1,
        "parse_status_counts": {"ok": 1475, "parse_failure": 0},
        "coverage_thresholds": {
            "minimum_global_determined_fraction": 0.99,
            "minimum_per_video_determined_fraction": 0.99,
        },
        "oracle_coverage": 1.0,
        "per_video_oracle_coverage": {"DALI": 1.0, "HANGZHOU": 1.0, "WUHAN": 1.0},
        "k3": {"deterministic": True},
    }


def test_formal_pass_requires_every_frozen_gate():
    assert decide(passing_metrics(), mapping()) == "FULL_GRID_PASS_REFERENCE_RELEASED"


def test_parse_failure_has_zero_release_tolerance():
    metrics = passing_metrics()
    metrics["parse_status_counts"] = {"ok": 1474, "parse_failure": 1}
    assert decide(metrics, mapping()) == "FULL_GRID_FAILED_PROTOCOL"


def test_unknown_global_or_per_video_threshold_blocks_release():
    metrics = passing_metrics()
    metrics["oracle_coverage"] = 0.989
    assert decide(metrics, mapping()) == "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"
    metrics = passing_metrics()
    metrics["per_video_oracle_coverage"]["WUHAN"] = 0.989
    assert decide(metrics, mapping()) == "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"


def test_authentication_and_runtime_abort_precede_incompleteness():
    metrics = passing_metrics()
    metrics["complete"] = False
    metrics["global_stop_trigger"] = "frame_hash_mismatch"
    assert decide(metrics, mapping()) == "FULL_GRID_ABORTED_AUTHENTICATION"
    metrics["global_stop_trigger"] = "retry"
    assert decide(metrics, mapping()) == "FULL_GRID_ABORTED_RUNTIME"
    metrics["global_stop_trigger"] = None
    assert decide(metrics, mapping()) == "INSUFFICIENT_EVIDENCE"


def test_raw_record_must_match_preregistered_processed_tensor_identity():
    raw = json.dumps({
        "label": "not_relevant", "confidence": "low", "evidence": "mock"
    }, separators=(",", ":"))
    unit = {
        "experiment_id": "E", "unit_id": "U0", "ordinal": 0,
        "video_id": "V", "worker_id": "W", "call_spec_sha256": "c" * 64,
        "frame_set_sha256": "f" * 64, "frame_count": 21,
        "expected_processed_input_sha256": "p" * 64,
    }
    record = {
        "status": "AUTHENTICATED_FULL_GRID_RAW_OUTPUT", "mock_not_oracle": False,
        "experiment_id": "E", "execution_seal_sha256": "s" * 64,
        "unit_id": "U0", "unit_ordinal": 0, "video_id": "V", "worker_id": "W",
        "physical_gpu_ids": [1, 2], "call_spec_sha256": "c" * 64,
        "frame_set_sha256": "f" * 64, "frame_count": 21,
        "execution_session_id": "session", "attempt_id": "attempt",
        "input_identity_sha256": "i" * 64, "model_input_identity_sha256": "m" * 64,
        "processed_input_sha256": "x" * 64,
        "generated_token_ids_sha256": "g" * 64,
        "raw": raw, "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "parse_status": "ok", "authoritative_label": "not_relevant",
        "parsed": {"label": "not_relevant", "confidence": "low", "evidence": "mock"},
        "runtime": {"model_load_seconds": 1.0, "total_call_seconds": 2.0,
                    "inference_seconds": 1.0, "worker_id": "W"},
    }
    record["record_payload_sha256"] = canonical_hash(record)
    with pytest.raises(RuntimeError, match="processed_input_sha256"):
        _validate_record(
            record, unit, execution_seal_sha256="s" * 64,
            worker={"physical_gpu_ids": [1, 2]}, allow_mock=False,
        )
