"""Frozen decision and complete-only publication for the V3 full-grid reference."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .oracle_v3_full_grid_analyzer import FullGridAnalysisProducts, analyze_execution
from .oracle_v3_full_grid_manifest import EXPECTED_UNIT_COUNT
from .oracle_v3_full_grid_hiding import (
    RuntimeOSIsolationPolicy,
    secure_evaluator_directory,
)
from .oracle_v3_full_grid_package import DECISIONS, EXECUTION, PACKAGE
from .oracle_v3_manifest import (
    atomic_text, canonical_hash, load_json, sha256_file, validate_payload_hash,
)


FORMAL_DECISIONS = {
    "FULL_GRID_PASS_REFERENCE_RELEASED",
    "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE",
    "FULL_GRID_ABORTED_AUTHENTICATION",
    "FULL_GRID_ABORTED_RUNTIME",
    "FULL_GRID_FAILED_PROTOCOL",
    "INSUFFICIENT_EVIDENCE",
}

AUTHENTICATION_TRIGGERS = {
    "authentication_mismatch",
    "frame_hash_mismatch",
    "processed_input_identity_mismatch",
    "gpu_binding_mismatch",
    "parser_implementation_mismatch",
    "unknown_runner_version",
    "integrity_mismatch",
}
RUNTIME_TRIGGERS = {
    "unauthorized_model_reload",
    "duplicate_unit_attempt",
    "missing_attempt_ledger_transition",
    "extra_call",
    "retry",
    "output_path_collision",
    "cost_envelope_exceeded",
    "generation_failed",
    "uncertain_interruption",
    "post_load_process_fault",
}


UNIT_LABEL_SCHEMA = pa.schema([
    ("ordinal", pa.int64()),
    ("unit_id", pa.string()),
    ("video_id", pa.string()),
    ("start_time", pa.float64()),
    ("end_time", pa.float64()),
    ("unit_kind", pa.string()),
    ("parse_status", pa.string()),
    ("authoritative_label", pa.string()),
    ("diagnostic_confidence", pa.string()),
    ("diagnostic_evidence", pa.string()),
    ("source_raw_sha256", pa.string()),
    ("record_payload_sha256", pa.string()),
])

EVENT_RELATION_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("query_id", pa.string()),
    ("video_id", pa.string()),
    ("start_time", pa.float64()),
    ("end_time", pa.float64()),
    ("evidence_status", pa.string()),
    ("source_unit_ids", pa.list_(pa.string())),
    ("k3_group", pa.string()),
    ("k3_config_sha256", pa.string()),
])


def decide(metrics: dict[str, Any], mapping: dict[str, Any]) -> str:
    validate_payload_hash(mapping, "decision_mapping_payload_sha256")
    if set(mapping["allowed_decisions"]) != FORMAL_DECISIONS:
        raise RuntimeError("decision mapping vocabulary mismatch")
    trigger = metrics.get("global_stop_trigger")
    if trigger in AUTHENTICATION_TRIGGERS:
        return "FULL_GRID_ABORTED_AUTHENTICATION"
    if trigger in RUNTIME_TRIGGERS:
        return "FULL_GRID_ABORTED_RUNTIME"
    errors = metrics.get("authentication_errors", [])
    if any(error.startswith((
        "extra_raw_outputs", "invalid_raw:", "ledger_identity:",
        "ledger_processed_input:", "ledger_output_join:", "ledger_wrong_worker:",
    )) for error in errors):
        return "FULL_GRID_ABORTED_AUTHENTICATION"
    if any(error.startswith((
        "invalid_worker_ledger:", "model_load_transition:", "ledger_transition:",
        "invalid_global_ledger:", "invalid_supervisor_audit:",
        "missing_supervisor_audit",
    )) for error in errors):
        return "FULL_GRID_ABORTED_RUNTIME"
    if not metrics.get("complete") or metrics.get("authenticated_record_count") != EXPECTED_UNIT_COUNT:
        return "INSUFFICIENT_EVIDENCE"
    if metrics.get("reload_count") != 0 or metrics.get("retry_count") != 0:
        return "FULL_GRID_ABORTED_RUNTIME"
    if metrics.get("model_load_count") != 3 or metrics.get("actual_a100_gpu_hours", 1e9) > 19.4:
        return "FULL_GRID_ABORTED_RUNTIME"
    if metrics.get("parse_status_counts", {}).get("parse_failure", 0) != 0:
        return "FULL_GRID_FAILED_PROTOCOL"
    policy = metrics["coverage_thresholds"]
    if metrics.get("oracle_coverage", 0.0) < policy["minimum_global_determined_fraction"]:
        return "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"
    if any(value < policy["minimum_per_video_determined_fraction"] for value in metrics[
        "per_video_oracle_coverage"
    ].values()):
        return "FULL_GRID_INSUFFICIENT_ORACLE_COVERAGE"
    if not metrics.get("k3", {}).get("deterministic"):
        return "FULL_GRID_FAILED_PROTOCOL"
    return "FULL_GRID_PASS_REFERENCE_RELEASED"


def _write_parquet_once(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, temporary, compression="zstd", version="2.6")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    if path.exists():
        if sha256_file(path) != sha256_file(temporary):
            temporary.unlink()
            raise RuntimeError(f"refusing to overwrite nonmatching release artifact: {path}")
        temporary.unlink()
        return
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _event_rows(products: FullGridAnalysisProducts, k3_hash: str) -> list[dict[str, Any]]:
    return [{
        "event_id": row.event_id,
        "query_id": row.query_id,
        "video_id": row.video_id,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "evidence_status": row.evidence_status,
        "source_unit_ids": list(row.source_candidate_ids),
        "k3_group": row.k3_group,
        "k3_config_sha256": k3_hash,
    } for row in products.primary_relation.events]


def _publish(
    *,
    execution_root: Path,
    metrics: dict[str, Any],
    products: FullGridAnalysisProducts,
    policy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    release_id = canonical_hash({
        "execution_seal_sha256": metrics["execution_seal_sha256"],
        "metrics_payload_sha256": metrics["metrics_payload_sha256"],
        "primary_relation_sha256": products.primary_relation.relation_sha256,
    })
    release_root = execution_root / "evaluator_only_reference_releases" / release_id
    policy_payload = policy_payload or load_json(
        PACKAGE / "FULL_GRID_LABEL_ACCESS_POLICY.json"
    )
    validate_payload_hash(policy_payload, "label_access_policy_payload_sha256")
    policy = RuntimeOSIsolationPolicy(
        evaluator_uid=policy_payload["evaluator_uid"],
        runtime_uid=policy_payload["runtime_uid"],
        evaluator_directory_mode=int(policy_payload["evaluator_directory_mode"], 8),
        evaluator_file_mode=int(policy_payload["evaluator_file_mode"], 8),
        required_runtime_effective_capabilities_hex=policy_payload[
            "required_runtime_effective_capabilities_hex"
        ],
    )
    secure_evaluator_directory(release_root.parent, policy)
    secure_evaluator_directory(release_root, policy)
    unit_path = release_root / "unit_labels.parquet"
    coverage_path = release_root / "oracle_coverage_report.json"
    event_path = release_root / "k3_model_relative_event_relation.parquet"
    unit_table = pa.Table.from_pylist(list(products.unit_rows), schema=UNIT_LABEL_SCHEMA)
    event_table = pa.Table.from_pylist(
        _event_rows(products, products.primary_relation.k3_config_sha256),
        schema=EVENT_RELATION_SCHEMA,
    )
    _write_parquet_once(unit_path, unit_table)
    _write_parquet_once(event_path, event_table)
    coverage = {
        "status": "FORMAL_MODEL_RELATIVE_ORACLE_COVERAGE",
        "oracle_coverage": metrics["oracle_coverage"],
        "per_video_oracle_coverage": metrics["per_video_oracle_coverage"],
        "label_counts": metrics["label_counts"],
        "parse_status_counts": metrics["parse_status_counts"],
        "coverage_thresholds": metrics["coverage_thresholds"],
        "primary_relation_rule": "frozen K3 four-state relation; one short unknown may bridge relevant neighbors; parse_failure is a barrier",
        "primary_relation_sha256": products.primary_relation.relation_sha256,
        "determined_only_lower_bound_relation_sha256": products.lower_bound_relation.relation_sha256,
        "unknown_sensitive_upper_bound_diagnostic_relation_sha256": products.upper_bound_relation.relation_sha256,
        "parse_failure_regions_are_unevaluable": True,
    }
    coverage["coverage_payload_sha256"] = canonical_hash(coverage)
    atomic_text(coverage_path, json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    os.chmod(coverage_path, policy.evaluator_file_mode)
    artifacts = [{
        "path": str(path.relative_to(execution_root)),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    } for path in (unit_path, coverage_path, event_path)]
    release = {
        "status": "FORMAL_REFERENCE_RELEASE_COMMITTED",
        "release_id": release_id,
        "execution_seal_sha256": metrics["execution_seal_sha256"],
        "metrics_payload_sha256": metrics["metrics_payload_sha256"],
        "artifacts": artifacts,
        "downstream_must_validate_this_commit_before_access": True,
    }
    release["release_payload_sha256"] = canonical_hash(release)
    pointer = execution_root / "FORMAL_REFERENCE_RELEASE.json"
    atomic_text(pointer, json.dumps(release, indent=2, sort_keys=True) + "\n")
    os.chmod(pointer, 0o600)
    return release


def finalize_execution(
    *,
    execution_root: Path = EXECUTION,
    allow_mock: bool = False,
) -> dict[str, Any]:
    metrics, products = analyze_execution(
        execution_root=execution_root, allow_mock=allow_mock
    )
    mapping = load_json(DECISIONS)
    candidate = decide(metrics, mapping)
    if allow_mock:
        if (execution_root / "FORMAL_REFERENCE_RELEASE.json").exists():
            raise RuntimeError("mock dry-run must never publish a formal reference")
        return {
            "status": "DRY_RUN_FINALIZER_PASS_NOT_ORACLE",
            "mock_not_oracle": True,
            "would_emit_formal_decision": candidate,
            "formal_publication_performed": False,
            "metrics_payload_sha256": metrics["metrics_payload_sha256"],
        }
    decision = {
        "status": "FROZEN_FULL_GRID_FINAL_DECISION",
        "decision": candidate,
        "execution_seal_sha256": metrics["execution_seal_sha256"],
        "metrics_payload_sha256": metrics["metrics_payload_sha256"],
        "scope": "exact authenticated 1475-unit model-relative full grid only",
    }
    if candidate == "FULL_GRID_PASS_REFERENCE_RELEASED":
        decision["formal_reference_release"] = _publish(
            execution_root=execution_root, metrics=metrics, products=products
        )
    else:
        incomplete = execution_root / "incomplete_diagnostics"
        incomplete.mkdir(parents=True, exist_ok=True)
        decision["formal_reference_release"] = None
    decision["decision_payload_sha256"] = canonical_hash(decision)
    destination = (
        execution_root / "FULL_GRID_FINAL_DECISION.json"
        if candidate == "FULL_GRID_PASS_REFERENCE_RELEASED"
        else execution_root / "incomplete_diagnostics/FULL_GRID_FINAL_DECISION.json"
    )
    atomic_text(destination, json.dumps(decision, indent=2, sort_keys=True) + "\n")
    return decision
