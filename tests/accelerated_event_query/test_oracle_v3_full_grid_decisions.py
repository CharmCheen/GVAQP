from copy import deepcopy

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
