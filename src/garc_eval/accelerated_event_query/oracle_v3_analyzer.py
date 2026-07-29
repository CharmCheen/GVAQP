"""Frozen hard-gate analyzer for the AEQ model-relative V3 preflight."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

from .k3_unit_event_adapter import K3UnitEventAdapter, K3UnitEventConfig
from .model_relative_labels import unit_label_from_parse
from .oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    validate_call_manifest,
    validate_frame_set,
)
from .oracle_v3_parser import parse_oracle_v3_response
from .oracle_v3_runner import (
    BASE,
    PREREG,
    RAW,
    ROOT,
    SEAL,
    SHARDS,
    _read_attempts,
    _validate_existing_record,
    frozen_context,
    identity_payload,
    validate_execution_seal,
)


def _artifact_records(prereg: dict, frame_sets: dict, call_manifest: dict) -> tuple[dict, list[str]]:
    records = {}
    errors = []
    expected_paths = {ROOT / row["artifact_path"] for row in call_manifest["calls"]}
    observed_paths = set(RAW.glob("*/*.json"))
    extras = sorted(str(path.relative_to(ROOT)) for path in observed_paths - expected_paths)
    missing = sorted(str(path.relative_to(ROOT)) for path in expected_paths - observed_paths)
    if extras:
        errors.append(f"extra_raw:{extras}")
    if missing:
        errors.append(f"missing_raw:{missing}")
    for call in call_manifest["calls"]:
        path = ROOT / call["artifact_path"]
        if not path.exists():
            continue
        try:
            record = load_json(path)
            frame_set = frame_sets[(call["candidate_id"], float(call["sampling_fps"]))]
            payload = identity_payload(prereg, call, frame_set)
            _validate_existing_record(record, payload, frame_set)
            if not isinstance(record.get("processed_input_sha256"), str):
                raise RuntimeError("missing processed-input hash")
            records[call["artifact_name"]] = record
        except Exception as exc:
            errors.append(f"invalid_raw:{call['artifact_name']}:{type(exc).__name__}:{exc}")
    return records, errors


def _attempt_accounting(call_manifest: dict) -> tuple[dict[str, int], list[str]]:
    counts = Counter()
    errors = []
    expected = {row["artifact_name"] for row in call_manifest["calls"]}
    by_artifact = {artifact: Counter() for artifact in expected}
    try:
        for shard in SHARDS:
            for row in _read_attempts(shard):
                artifact = row.get("artifact")
                if artifact not in expected:
                    errors.append(f"unauthorized_attempt_artifact:{artifact}")
                    continue
                counts[row["event"]] += 1
                by_artifact[artifact][row["event"]] += 1
    except Exception as exc:
        errors.append(f"invalid_attempt_ledger:{type(exc).__name__}:{exc}")
    for artifact, observed in by_artifact.items():
        required = {"PREPARED": 1, "INFERENCE_STARTED": 1, "INFERENCE_COMPLETED": 1, "ACCEPTED": 1}
        if any(observed[event] != count for event, count in required.items()):
            errors.append(f"incomplete_attempt:{artifact}:{dict(observed)}")
        forbidden = {"GENERATION_FAILED", "UNCERTAIN_INTERRUPTION", "FAILED_POST_INFERENCE"}
        if any(observed[event] for event in forbidden):
            errors.append(f"failed_or_uncertain_attempt:{artifact}:{dict(observed)}")
    return dict(counts), errors


def _determinism(prereg: dict, records: dict) -> dict:
    same_process = []
    cross_replica = []
    for group in prereg["determinism_groups"]:
        members = group["artifact_names"]
        rows = [records[name] for name in members if name in records]
        result = {
            "group_id": group["group_id"],
            "kind": group["kind"],
            "artifact_names": members,
            "complete": len(rows) == len(members),
            "model_input_identity_equal": len(rows) == len(members) and len({
                row["model_input_identity_sha256"] for row in rows
            }) == 1,
            "processed_input_identity_equal": len(rows) == len(members) and len({
                row["processed_input_sha256"] for row in rows
            }) == 1,
            "authoritative_label_equal": len(rows) == len(members) and len({
                row["effective_label"] for row in rows
            }) == 1,
            "exact_raw_response_equal_diagnostic": len(rows) == len(members) and len({
                row["raw_response_sha256"] for row in rows
            }) == 1,
        }
        (same_process if group["kind"] == "same_process" else cross_replica).append(result)
    required_fields = (
        "complete", "model_input_identity_equal", "processed_input_identity_equal",
        "authoritative_label_equal",
    )
    hard_pass = all(
        all(row[field] for field in required_fields)
        for row in [*same_process, *cross_replica]
    )
    return {"hard_pass": hard_pass, "same_process": same_process, "cross_replica": cross_replica}


def _eventization(prereg: dict, call_manifest: dict, records: dict) -> dict:
    config_artifact = load_json(ROOT / prereg["bindings"]["k3_config_path"])
    config = K3UnitEventConfig(**config_artifact["parameters"])
    canonical_calls = {
        row["artifact_name"]: row for row in call_manifest["calls"]
        if row["artifact_name"] in prereg["eventization_canonical_artifacts"]
    }
    units = []
    for artifact in prereg["eventization_canonical_artifacts"]:
        if artifact not in records:
            continue
        call = canonical_calls[artifact]
        parsed = parse_oracle_v3_response(records[artifact]["raw"])
        units.append(unit_label_from_parse(
            unit_id=call["candidate_id"],
            query_id=prereg["query_id"],
            video_id=call["video_id"],
            start_time=float(call["start_time"]),
            end_time=float(call["end_time"]),
            result=parsed,
        ))
    complete = len(units) == len(prereg["eventization_canonical_artifacts"])
    adapter = K3UnitEventAdapter(prereg["query_id"], config)
    forward = adapter.materialize(units)
    reverse = adapter.materialize(reversed(units))
    changed_diagnostics = [replace(
        row,
        confidence="low" if row.outcome != "parse_failure" else None,
        evidence="diagnostic replacement with time claim 17-20 seconds"
            if row.outcome != "parse_failure" else None,
    ) for row in units]
    diagnostic_variant = adapter.materialize(changed_diagnostics)
    boundary_sources_only = all(
        event.start_time == min(row.start_time for row in units if row.unit_id in event.source_candidate_ids)
        and event.end_time == max(row.end_time for row in units if row.unit_id in event.source_candidate_ids)
        for event in forward.events
    )
    hard_pass = all((
        complete,
        forward == reverse,
        forward == diagnostic_variant,
        boundary_sources_only,
        forward.k3_config_sha256 == config.sha256 == config_artifact["k3_config_sha256"],
    ))
    return {
        "hard_pass": hard_pass,
        "complete": complete,
        "forward_relation_sha256": forward.relation_sha256,
        "reverse_relation_sha256": reverse.relation_sha256,
        "diagnostic_variant_relation_sha256": diagnostic_variant.relation_sha256,
        "boundary_sources_only": boundary_sources_only,
        "k3_config_sha256": config.sha256,
        "event_count": len(forward.events),
        "unknown_unit_ids": list(forward.unknown_unit_ids),
        "parse_failure_unit_ids": list(forward.parse_failure_unit_ids),
    }


def analyze() -> dict:
    seal, prereg = validate_execution_seal("analyzer")
    prereg2, _, frame_sets, call_manifest = frozen_context()
    if prereg2 != prereg:
        raise RuntimeError("analyzer/runner preregistration views differ")
    validate_call_manifest(call_manifest, prereg["workload"]["total_physical_calls"])
    for frame_set in frame_sets.values():
        validate_frame_set(frame_set)
    records, raw_errors = _artifact_records(prereg, frame_sets, call_manifest)
    attempt_counts, attempt_errors = _attempt_accounting(call_manifest)
    errors = [*raw_errors, *attempt_errors]
    expected_paths = {ROOT / row["artifact_path"] for row in call_manifest["calls"]}
    observed_expected_raw_count = sum(path.exists() for path in expected_paths)
    authenticated_input_mismatch = (
        observed_expected_raw_count == prereg["workload"]["total_physical_calls"]
        and any(error.startswith("invalid_raw:") for error in raw_errors)
    )
    complete = len(records) == prereg["workload"]["total_physical_calls"] and not errors
    if authenticated_input_mismatch:
        status = "REVISE_V3_INPUT_BINDING"
        determinism = {"hard_pass": False, "same_process": [], "cross_replica": []}
        eventization = {"hard_pass": False, "complete": False}
    elif not complete:
        status = "INSUFFICIENT_EVIDENCE"
        determinism = {"hard_pass": False, "same_process": [], "cross_replica": []}
        eventization = {"hard_pass": False, "complete": False}
    else:
        determinism = _determinism(prereg, records)
        eventization = _eventization(prereg, call_manifest, records)
        parse_counts = Counter(row["parse_status"] for row in records.values())
        parse_pass = parse_counts == {"ok": prereg["workload"]["total_physical_calls"]}
        labels = Counter(
            records[name]["effective_label"] for name in prereg["class_support_artifacts"]
        )
        class_support_pass = labels["relevant"] >= 1 and labels["not_relevant"] >= 1
        input_binding_pass = not errors and all(
            row["model_input_identity_sha256"] and row["processed_input_sha256"]
            for row in records.values()
        )
        if not input_binding_pass:
            status = "REVISE_V3_INPUT_BINDING"
        elif not parse_pass or not determinism["hard_pass"] or not class_support_pass:
            status = "REVISE_V3_SCHEMA"
        elif not eventization["hard_pass"]:
            status = "REVISE_K3_EVENTIZATION"
        else:
            status = "V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED"
    parse_counts = Counter(row["parse_status"] for row in records.values())
    label_counts = Counter(row["effective_label"] for row in records.values())
    result = {
        "experiment_id": prereg["experiment_id"],
        "complete": complete,
        "observed_calls": len(records),
        "observed_expected_raw_files": observed_expected_raw_count,
        "expected_calls": prereg["workload"]["total_physical_calls"],
        "attempt_event_counts": attempt_counts,
        "authentication_errors": errors,
        "parse_status_counts": dict(sorted(parse_counts.items())),
        "physical_label_counts": dict(sorted(label_counts.items())),
        "determinism": determinism,
        "eventization": eventization,
        "protocol_adequacy_decision": status,
        "construct_validity_diagnostics_are_non_gating": True,
        "execution_seal_sha256": sha256_file(SEAL),
        "analyzer_source_sha256": sha256_file(Path(__file__)),
        "scope": "11-call V3 schema-and-determinism preflight only; never full-grid authorization",
    }
    result["metrics_payload_sha256"] = canonical_hash(result)
    return result
