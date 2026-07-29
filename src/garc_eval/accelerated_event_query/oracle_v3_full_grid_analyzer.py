"""Frozen pre-execution analyzer design for the V3 1,475-unit full grid."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .k3_unit_event_adapter import K3UnitEventAdapter, K3UnitEventConfig
from .model_relative_event_relation import ModelRelativeEventRelation
from .model_relative_labels import ModelRelativeUnitLabel
from .oracle_v3_full_grid_control import _read_jsonl
from .oracle_v3_full_grid_manifest import (
    EXPECTED_UNIT_COUNT,
    QUERY_ID,
    validate_unit_manifest,
    validate_worker_schedule,
)
from .oracle_v3_full_grid_package import (
    EXECUTION,
    PACKAGE,
    SCHEDULE,
    UNITS,
    ROOT,
    validate_execution_seal,
)
from .oracle_v3_manifest import canonical_hash, load_json, sha256_file, validate_payload_hash
from .oracle_v3_parser import parse_oracle_v3_response


@dataclass(frozen=True)
class FullGridAnalysisProducts:
    unit_rows: tuple[dict[str, Any], ...]
    primary_relation: ModelRelativeEventRelation
    lower_bound_relation: ModelRelativeEventRelation
    upper_bound_relation: ModelRelativeEventRelation


def _validate_record(
    record: dict[str, Any],
    unit: dict[str, Any],
    *,
    execution_seal_sha256: str,
    worker: dict[str, Any],
    allow_mock: bool,
) -> tuple[str, str, dict[str, Any] | None]:
    validate_payload_hash(record, "record_payload_sha256")
    expected_status = (
        "MOCK_DRY_RUN_RECORD_NOT_ORACLE" if allow_mock
        else "AUTHENTICATED_FULL_GRID_RAW_OUTPUT"
    )
    if record.get("status") != expected_status:
        raise RuntimeError("raw record status/mode mismatch")
    if bool(record.get("mock_not_oracle")) is not allow_mock:
        raise RuntimeError("mock marker/mode mismatch")
    expected = {
        "experiment_id": unit["experiment_id"],
        "execution_seal_sha256": execution_seal_sha256,
        "unit_id": unit["unit_id"],
        "unit_ordinal": unit["ordinal"],
        "video_id": unit["video_id"],
        "worker_id": unit["worker_id"],
        "call_spec_sha256": unit["call_spec_sha256"],
        "frame_set_sha256": unit["frame_set_sha256"],
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise RuntimeError(f"raw record identity mismatch: {unit['unit_id']}:{key}")
    if record.get("physical_gpu_ids") != worker["physical_gpu_ids"]:
        raise RuntimeError("raw worker/GPU binding mismatch")
    if record.get("frame_count") != unit["frame_count"]:
        raise RuntimeError("raw frame count mismatch")
    for key in (
        "execution_session_id", "attempt_id", "input_identity_sha256",
        "model_input_identity_sha256", "processed_input_sha256",
        "generated_token_ids_sha256", "raw_response_sha256",
    ):
        if not isinstance(record.get(key), str) or not record[key]:
            raise RuntimeError(f"raw record lacks {key}")
    raw = record.get("raw")
    if not isinstance(raw, str) or hashlib.sha256(raw.encode()).hexdigest() != record[
        "raw_response_sha256"
    ]:
        raise RuntimeError("raw response hash mismatch")
    parsed = parse_oracle_v3_response(raw)
    if not all((
        record.get("parse_status") == parsed.parse_status,
        record.get("authoritative_label") == parsed.effective_label,
        record.get("parsed") == parsed.parsed,
    )):
        raise RuntimeError("stored strict parse result mismatch")
    runtime = record.get("runtime")
    if not isinstance(runtime, dict):
        raise RuntimeError("raw record lacks runtime")
    for key in ("model_load_seconds", "total_call_seconds", "inference_seconds"):
        if not isinstance(runtime.get(key), (int, float)) or runtime[key] < 0:
            raise RuntimeError(f"invalid runtime field: {key}")
    if runtime.get("worker_id") != unit["worker_id"]:
        raise RuntimeError("runtime worker mismatch")
    return parsed.parse_status, parsed.effective_label, parsed.parsed


def _validate_worker_ledgers(
    *,
    execution_root: Path,
    schedule: dict[str, Any],
    units: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> tuple[dict[str, int], list[str]]:
    errors: list[str] = []
    event_counts: Counter = Counter()
    unit_map = {row["unit_id"]: row for row in units["units"]}
    for worker in schedule["workers"]:
        path = execution_root / worker["attempt_ledger_relative_path"]
        if not path.exists():
            errors.append(f"missing_worker_ledger:{worker['worker_id']}")
            continue
        try:
            rows = _read_jsonl(path)
        except Exception as exc:
            errors.append(f"invalid_worker_ledger:{worker['worker_id']}:{exc}")
            continue
        event_counts.update(row.get("event") for row in rows)
        load_events = [row for row in rows if str(row.get("event", "")).startswith("MODEL_LOAD_")]
        if [row.get("event") for row in load_events] != [
            "MODEL_LOAD_STARTED", "MODEL_LOAD_COMPLETED"
        ]:
            errors.append(f"model_load_transition:{worker['worker_id']}")
        by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            unit_id = row.get("unit_id")
            if unit_id is not None:
                by_unit[unit_id].append(row)
                if unit_id not in worker["unit_ids"]:
                    errors.append(f"ledger_wrong_worker:{unit_id}:{worker['worker_id']}")
        if set(by_unit) != set(worker["unit_ids"]):
            errors.append(f"ledger_unit_membership:{worker['worker_id']}")
        for unit_id in worker["unit_ids"]:
            rows_for_unit = by_unit.get(unit_id, [])
            if [row.get("event") for row in rows_for_unit] != [
                "PREPARED", "INFERENCE_STARTED", "INFERENCE_COMPLETED", "ACCEPTED"
            ]:
                errors.append(f"ledger_transition:{unit_id}")
                continue
            unit = unit_map[unit_id]
            record = records.get(unit_id)
            if record is None:
                continue
            for row in rows_for_unit:
                if not all((
                    row.get("worker_id") == worker["worker_id"],
                    row.get("call_spec_sha256") == unit["call_spec_sha256"],
                    row.get("attempt_id") == record["attempt_id"],
                    row.get("execution_session_id") == record["execution_session_id"],
                )):
                    errors.append(f"ledger_identity:{unit_id}:{row.get('event')}")
            if rows_for_unit[0].get("processed_input_sha256") != record[
                "processed_input_sha256"
            ] or rows_for_unit[1].get("processed_input_sha256") != record[
                "processed_input_sha256"
            ]:
                errors.append(f"ledger_processed_input:{unit_id}")
            if rows_for_unit[2].get("generated_token_ids_sha256") != record[
                "generated_token_ids_sha256"
            ] or rows_for_unit[3].get("record_payload_sha256") != record[
                "record_payload_sha256"
            ]:
                errors.append(f"ledger_output_join:{unit_id}")
    return dict(event_counts), errors


def _relations(
    unit_rows: list[dict[str, Any]], k3_config: K3UnitEventConfig
) -> tuple[ModelRelativeEventRelation, ModelRelativeEventRelation, ModelRelativeEventRelation, dict]:
    units = [ModelRelativeUnitLabel(
        unit_id=row["unit_id"],
        query_id=QUERY_ID,
        video_id=row["video_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        outcome=row["authoritative_label"],
        confidence=row["diagnostic_confidence"],
        evidence=row["diagnostic_evidence"],
    ) for row in unit_rows]
    adapter = K3UnitEventAdapter(QUERY_ID, k3_config)
    primary = adapter.materialize(units)
    reverse = adapter.materialize(reversed(units))
    changed_diagnostics = [replace(
        row,
        confidence=None if row.outcome == "parse_failure" else "low",
        evidence=None if row.outcome == "parse_failure" else "diagnostic mutation 17-20 sec",
    ) for row in units]
    diagnostic_variant = adapter.materialize(changed_diagnostics)
    lower_config = replace(k3_config, maximum_unknown_gap_units=0)
    lower = K3UnitEventAdapter(QUERY_ID, lower_config).materialize(units)
    upper_units = [replace(
        row,
        outcome="relevant" if row.outcome == "unknown" else row.outcome,
        confidence=None,
        evidence=None,
    ) for row in units]
    upper = K3UnitEventAdapter(QUERY_ID, k3_config).materialize(upper_units)
    checks = {
        "primary_relation_sha256": primary.relation_sha256,
        "reverse_relation_sha256": reverse.relation_sha256,
        "diagnostic_variant_relation_sha256": diagnostic_variant.relation_sha256,
        "lower_bound_diagnostic_relation_sha256": lower.relation_sha256,
        "upper_bound_diagnostic_relation_sha256": upper.relation_sha256,
        "deterministic": primary == reverse == diagnostic_variant,
    }
    return primary, lower, upper, checks


def analyze_execution(
    *,
    execution_root: Path = EXECUTION,
    allow_mock: bool = False,
) -> tuple[dict[str, Any], FullGridAnalysisProducts]:
    seal, prereg = validate_execution_seal("analyzer")
    units = load_json(UNITS)
    schedule = load_json(SCHEDULE)
    validate_unit_manifest(units)
    validate_worker_schedule(schedule, units)
    seal_sha = sha256_file(PACKAGE / "FULL_GRID_EXECUTION_SEAL.json")
    expected_paths = {
        execution_root / row["raw_output_relative_path"]: row
        for row in units["units"]
    }
    observed = set((execution_root / "raw").rglob("*.json")) if (
        execution_root / "raw"
    ).exists() else set()
    errors: list[str] = []
    if observed - set(expected_paths):
        errors.append("extra_raw_outputs")
    if set(expected_paths) - observed:
        errors.append("missing_raw_outputs")
    workers = {row["worker_id"]: row for row in schedule["workers"]}
    records: dict[str, dict[str, Any]] = {}
    parsed_by_unit: dict[str, tuple[str, str, dict[str, Any] | None]] = {}
    for path, unit in expected_paths.items():
        if not path.exists():
            continue
        try:
            record = load_json(path)
            parsed_by_unit[unit["unit_id"]] = _validate_record(
                record,
                unit,
                execution_seal_sha256=seal_sha,
                worker=workers[unit["worker_id"]],
                allow_mock=allow_mock,
            )
            records[unit["unit_id"]] = record
        except Exception as exc:
            errors.append(f"invalid_raw:{unit['unit_id']}:{type(exc).__name__}:{exc}")
    ledger_counts, ledger_errors = _validate_worker_ledgers(
        execution_root=execution_root,
        schedule=schedule,
        units=units,
        records=records,
    )
    errors.extend(ledger_errors)
    global_state_path = execution_root / "GLOBAL_EXECUTION_STATE.json"
    global_ledger_path = execution_root / "GLOBAL_EXECUTION_LEDGER.jsonl"
    global_state = load_json(global_state_path) if global_state_path.exists() else {}
    try:
        global_events = _read_jsonl(global_ledger_path)
    except Exception as exc:
        global_events = []
        errors.append(f"invalid_global_ledger:{type(exc).__name__}:{exc}")
    global_pass = all((
        global_state.get("status") == "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS",
        global_state.get("execution_seal_sha256") == seal_sha,
        len(global_state.get("model_load_workers", [])) == 3,
        len(global_state.get("model_load_completed_workers", [])) == 3,
        len(global_state.get("attempted_unit_ids", [])) == EXPECTED_UNIT_COUNT,
        len(global_state.get("completed_unit_ids", [])) == EXPECTED_UNIT_COUNT,
        not global_state.get("in_flight_unit_ids", ["missing"]),
        global_state.get("stop_trigger") is None,
        float(global_state.get("actual_gpu_seconds", float("inf"))) <= 19.4 * 3600,
        bool(global_events) and global_events[-1].get("event") == "PHYSICAL_CALLS_COMPLETE",
    ))
    if not global_pass:
        errors.append("global_execution_state_incomplete_or_stopped")
    label_counts = Counter(
        value[1] for value in parsed_by_unit.values()
    )
    parse_status_counts = Counter(
        value[0] for value in parsed_by_unit.values()
    )
    unit_rows: list[dict[str, Any]] = []
    for unit in units["units"]:
        record = records.get(unit["unit_id"])
        if record is None:
            continue
        parse_status, label, parsed = parsed_by_unit[unit["unit_id"]]
        unit_rows.append({
            "ordinal": unit["ordinal"],
            "unit_id": unit["unit_id"],
            "video_id": unit["video_id"],
            "start_time": unit["start_time"],
            "end_time": unit["end_time"],
            "unit_kind": unit["unit_kind"],
            "parse_status": parse_status,
            "authoritative_label": label,
            "diagnostic_confidence": parsed.get("confidence") if parsed else None,
            "diagnostic_evidence": parsed.get("evidence") if parsed else None,
            "source_raw_sha256": sha256_file(execution_root / unit["raw_output_relative_path"]),
            "record_payload_sha256": record["record_payload_sha256"],
        })
    k3_artifact = load_json(ROOT / prereg["bindings"]["k3_config"]["path"])
    k3_config = K3UnitEventConfig(**k3_artifact["parameters"])
    primary, lower, upper, k3_checks = _relations(unit_rows, k3_config)
    by_video = Counter(row["video_id"] for row in unit_rows if row[
        "authoritative_label"
    ] in {"relevant", "not_relevant"})
    expected_by_video = {
        worker["video_id"]: worker["exact_call_count"] for worker in schedule["workers"]
    }
    determined = label_counts["relevant"] + label_counts["not_relevant"]
    coverage = determined / EXPECTED_UNIT_COUNT
    per_video_coverage = {
        video: by_video[video] / count for video, count in expected_by_video.items()
    }
    metrics = {
        "status": "MOCK_DRY_RUN_ANALYSIS_NOT_ORACLE" if allow_mock else "FULL_GRID_ANALYSIS",
        "mock_not_oracle": allow_mock,
        "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": seal_sha,
        "expected_call_count": EXPECTED_UNIT_COUNT,
        "authenticated_record_count": len(records),
        "worker_ledger_event_counts": ledger_counts,
        "global_ledger_event_count": len(global_events),
        "authentication_errors": errors,
        "global_execution_state_pass": global_pass,
        "global_stop_trigger": global_state.get("stop_trigger"),
        "global_stop_detail": global_state.get("stop_detail"),
        "model_load_count": len(global_state.get("model_load_workers", [])),
        "reload_count": max(0, len(global_state.get("model_load_workers", [])) - 3),
        "retry_count": max(0, len(global_state.get("attempted_unit_ids", [])) - len(set(
            global_state.get("attempted_unit_ids", [])
        ))),
        "actual_a100_gpu_hours": float(global_state.get("actual_gpu_seconds", 0.0)) / 3600,
        "parse_status_counts": dict(parse_status_counts),
        "label_counts": dict(label_counts),
        "oracle_coverage": coverage,
        "per_video_oracle_coverage": per_video_coverage,
        "coverage_thresholds": prereg["coverage_policy"],
        "k3": k3_checks,
        "complete": len(records) == EXPECTED_UNIT_COUNT and not errors,
        "construct_validity_diagnostics_are_non_gating": True,
    }
    metrics["metrics_payload_sha256"] = canonical_hash(metrics)
    products = FullGridAnalysisProducts(
        unit_rows=tuple(unit_rows),
        primary_relation=primary,
        lower_bound_relation=lower,
        upper_bound_relation=upper,
    )
    return metrics, products
