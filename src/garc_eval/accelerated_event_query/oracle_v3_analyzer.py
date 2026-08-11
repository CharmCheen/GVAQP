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
    ATTEMPTS,
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
    observed_paths = set(RAW.rglob("*.json"))
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


def _attempt_accounting(
    prereg: dict, frame_sets: dict, call_manifest: dict, records: dict
) -> tuple[dict[str, int], list[str]]:
    """Join every successful ledger chain to one exact authorized raw record."""
    counts = Counter()
    errors = []
    calls = {row["artifact_name"]: row for row in call_manifest["calls"]}
    expected = set(calls)
    by_artifact = {artifact: Counter() for artifact in expected}
    rows_by_artifact = {artifact: [] for artifact in expected}
    expected_ledgers = {ATTEMPTS / f"{shard}.jsonl" for shard in SHARDS}
    observed_ledgers = set(ATTEMPTS.glob("*.jsonl")) if ATTEMPTS.exists() else set()
    for path in sorted(observed_ledgers - expected_ledgers):
        errors.append(f"unauthorized_attempt_ledger:{path.relative_to(ROOT)}")
    try:
        for shard in SHARDS:
            for row in _read_attempts(shard):
                artifact = row.get("artifact")
                if artifact not in expected:
                    errors.append(f"unauthorized_attempt_artifact:{artifact}")
                    continue
                call = calls[artifact]
                if shard != call["execution_shard"]:
                    errors.append(f"attempt_wrong_shard:{artifact}:{shard}")
                counts[row["event"]] += 1
                by_artifact[artifact][row["event"]] += 1
                rows_by_artifact[artifact].append(row)
    except Exception as exc:
        errors.append(f"invalid_attempt_ledger:{type(exc).__name__}:{exc}")
    required = {
        "PREPARED": 1, "INFERENCE_STARTED": 1,
        "INFERENCE_COMPLETED": 1, "ACCEPTED": 1,
    }
    for artifact in sorted(expected):
        observed = by_artifact[artifact]
        rows = rows_by_artifact[artifact]
        call = calls[artifact]
        frame_set = frame_sets[(call["candidate_id"], float(call["sampling_fps"]))]
        expected_input = canonical_hash(identity_payload(prereg, call, frame_set))
        if any(observed[event] != count for event, count in required.items()):
            errors.append(f"incomplete_attempt:{artifact}:{dict(observed)}")
        if set(observed) - set(required):
            errors.append(f"failed_or_uncertain_attempt:{artifact}:{dict(observed)}")
        if not rows:
            continue
        attempt_ids = {row.get("attempt_id") for row in rows}
        session_ids = {row.get("execution_session_id") for row in rows}
        if len(attempt_ids) != 1 or None in attempt_ids:
            errors.append(f"attempt_id_mismatch:{artifact}")
        if len(session_ids) != 1 or None in session_ids:
            errors.append(f"attempt_session_mismatch:{artifact}")
        for row in rows:
            if not all((
                row.get("call_spec_sha256") == call["call_spec_sha256"],
                row.get("input_identity_sha256") == expected_input,
                row.get("artifact") == artifact,
            )):
                errors.append(f"attempt_identity_mismatch:{artifact}:{row.get('event')}")
        record = records.get(artifact)
        if record is None:
            continue
        if attempt_ids != {record["attempt_id"]}:
            errors.append(f"attempt_raw_id_mismatch:{artifact}")
        if session_ids != {record["execution_session_id"]}:
            errors.append(f"attempt_raw_session_mismatch:{artifact}")
        indexed = {row["event"]: row for row in rows if row.get("event") in required}
        for event in ("PREPARED", "INFERENCE_STARTED"):
            if indexed.get(event, {}).get("processed_input_sha256") != record[
                "processed_input_sha256"
            ]:
                errors.append(f"attempt_processed_input_mismatch:{artifact}:{event}")
        for event in ("INFERENCE_COMPLETED", "ACCEPTED"):
            if indexed.get(event, {}).get("generated_token_ids_sha256") != record[
                "generated_token_ids_sha256"
            ]:
                errors.append(f"attempt_generated_tokens_mismatch:{artifact}:{event}")
        accepted = indexed.get("ACCEPTED", {})
        if accepted.get("record_sha256") != record["record_sha256"]:
            errors.append(f"attempt_record_mismatch:{artifact}")
        if accepted.get("recovered_after_crash") not in {True, False}:
            errors.append(f"attempt_acceptance_recovery_flag_invalid:{artifact}")
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
            "execution_session_relation_pass": len(rows) == len(members) and (
                len({row["execution_session_id"] for row in rows}) == 1
                if group["kind"] == "same_process"
                else len({row["execution_session_id"] for row in rows}) == len(rows)
            ),
            "authoritative_label_equal": len(rows) == len(members) and len({
                row["effective_label"] for row in rows
            }) == 1,
            "exact_raw_response_equal_diagnostic": len(rows) == len(members) and len({
                row["raw_response_sha256"] for row in rows
            }) == 1,
        }
        (same_process if group["kind"] == "same_process" else cross_replica).append(result)
    all_rows = [*same_process, *cross_replica]
    input_binding_hard_pass = all(
        all(row[field] for field in (
            "complete", "model_input_identity_equal", "processed_input_identity_equal",
            "execution_session_relation_pass",
        ))
        for row in all_rows
    )
    label_reproducibility_hard_pass = all(
        row["complete"] and row["authoritative_label_equal"] for row in all_rows
    )
    return {
        "hard_pass": input_binding_hard_pass and label_reproducibility_hard_pass,
        "input_binding_hard_pass": input_binding_hard_pass,
        "label_reproducibility_hard_pass": label_reproducibility_hard_pass,
        "same_process": same_process,
        "cross_replica": cross_replica,
    }


def _sampling_sensitivity(records: dict) -> dict:
    artifacts = ["DALI_u0548_fps2_r0.json", "DALI_u0548_fps4_sensitivity.json"]
    rows = [records[name] for name in artifacts if name in records]
    return {
        "status": "NON_GATING_DIAGNOSTIC",
        "artifact_names": artifacts,
        "complete": len(rows) == len(artifacts),
        "authoritative_labels": {
            name: records[name]["effective_label"] for name in artifacts if name in records
        },
        "authoritative_label_equal": len(rows) == len(artifacts) and len({
            row["effective_label"] for row in rows
        }) == 1,
        "interpretation": (
            "Reports 2/4-fps label sensitivity only; strict parsing remains globally gating, "
            "but label equality across sampling rates is not a V3 preflight hard gate."
        ),
    }


def _execution_profile(prereg: dict, call_manifest: dict, records: dict) -> dict:
    preprocessing_hashes = {
        canonical_hash(row["runtime"]["preprocessing_runtime"])
        for row in records.values()
    }
    library_pairs = {
        (row["runtime"]["torch"], row["runtime"]["transformers"])
        for row in records.values()
    }
    sessions_by_shard = {}
    for shard in SHARDS:
        artifacts = [
            call["artifact_name"] for call in call_manifest["calls"]
            if call["execution_shard"] == shard
        ]
        sessions_by_shard[shard] = sorted({
            records[name]["execution_session_id"] for name in artifacts if name in records
        })
    one_session_per_shard = all(
        len(sessions_by_shard[shard]) == 1 for shard in SHARDS
    )
    distinct_shard_sessions = one_session_per_shard and len({
        sessions_by_shard[shard][0] for shard in SHARDS
    }) == len(SHARDS)
    hard_pass = all((
        len(records) == prereg["workload"]["total_physical_calls"],
        len(preprocessing_hashes) == 1,
        len(library_pairs) == 1,
        one_session_per_shard,
        distinct_shard_sessions,
    ))
    return {
        "hard_pass": hard_pass,
        "preprocessing_runtime_equal": len(preprocessing_hashes) == 1,
        "preprocessing_runtime_sha256": (
            next(iter(preprocessing_hashes)) if len(preprocessing_hashes) == 1 else None
        ),
        "library_versions_equal": len(library_pairs) == 1,
        "one_execution_session_per_shard": one_session_per_shard,
        "distinct_execution_sessions_across_shards": distinct_shard_sessions,
        "execution_session_ids_by_shard": sessions_by_shard,
    }


def _parsed_output_payloads(prereg: dict, call_manifest: dict, records: dict) -> list[dict]:
    payloads = []
    for call in call_manifest["calls"]:
        artifact = call["artifact_name"]
        record = records[artifact]
        parsed = record["parsed"]
        payload = {
            "status": "AUTHENTICATED_PARSED_V3_OUTPUT",
            "experiment_id": prereg["experiment_id"],
            "artifact_name": artifact,
            "execution_shard": call["execution_shard"],
            "source_raw_path": call["artifact_path"],
            "source_raw_file_sha256": sha256_file(ROOT / call["artifact_path"]),
            "source_record_sha256": record["record_sha256"],
            "attempt_id": record["attempt_id"],
            "execution_session_id": record["execution_session_id"],
            "input_identity_sha256": record["input_identity_sha256"],
            "model_input_identity_sha256": record["model_input_identity_sha256"],
            "processed_input_sha256": record["processed_input_sha256"],
            "generated_token_ids_sha256": record["generated_token_ids_sha256"],
            "parse_status": record["parse_status"],
            "authoritative_label": record["effective_label"],
            "parsed": parsed,
            "diagnostic_confidence": parsed.get("confidence") if parsed else None,
            "diagnostic_evidence": parsed.get("evidence") if parsed else None,
            "unknown_and_parse_failure_are_preserved": True,
        }
        payload["parsed_payload_sha256"] = canonical_hash(payload)
        payloads.append({
            "path": str((
                BASE / "parsed" / call["execution_shard"] / artifact
            ).relative_to(ROOT)),
            "payload": payload,
        })
    return payloads


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


def _decision_status(
    *, complete: bool, authenticated_input_mismatch: bool,
    input_binding_pass: bool, parse_pass: bool,
    label_reproducibility_pass: bool, class_support_pass: bool,
    eventization_pass: bool,
) -> str:
    if authenticated_input_mismatch:
        return "REVISE_V3_INPUT_BINDING"
    if not complete:
        return "INSUFFICIENT_EVIDENCE"
    if not input_binding_pass:
        return "REVISE_V3_INPUT_BINDING"
    if not parse_pass or not label_reproducibility_pass or not class_support_pass:
        return "REVISE_V3_SCHEMA"
    if not eventization_pass:
        return "REVISE_K3_EVENTIZATION"
    return "V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED"


def _authenticated_input_mismatch(
    raw_errors: list[str], attempt_errors: list[str],
    observed_expected_raw_count: int, expected_call_count: int,
) -> bool:
    authenticated_join_prefixes = (
        "attempt_wrong_shard:",
        "attempt_identity_mismatch:",
        "attempt_raw_id_mismatch:",
        "attempt_raw_session_mismatch:",
        "attempt_processed_input_mismatch:",
        "attempt_generated_tokens_mismatch:",
        "attempt_record_mismatch:",
        "attempt_acceptance_recovery_flag_invalid:",
    )
    invalid_complete_raw_set = (
        observed_expected_raw_count == expected_call_count
        and any(error.startswith("invalid_raw:") for error in raw_errors)
    )
    authenticated_join_mismatch = any(
        error.startswith(authenticated_join_prefixes) for error in attempt_errors
    )
    return invalid_complete_raw_set or authenticated_join_mismatch


def analyze_bundle() -> tuple[dict, list[dict]]:
    seal, prereg = validate_execution_seal("analyzer")
    prereg2, _, frame_sets, call_manifest = frozen_context()
    if prereg2 != prereg:
        raise RuntimeError("analyzer/runner preregistration views differ")
    validate_call_manifest(call_manifest, prereg["workload"]["total_physical_calls"])
    for frame_set in frame_sets.values():
        validate_frame_set(frame_set)
    records, raw_errors = _artifact_records(prereg, frame_sets, call_manifest)
    attempt_counts, attempt_errors = _attempt_accounting(
        prereg, frame_sets, call_manifest, records
    )
    errors = [*raw_errors, *attempt_errors]
    expected_paths = {ROOT / row["artifact_path"] for row in call_manifest["calls"]}
    observed_expected_raw_count = sum(path.exists() for path in expected_paths)
    authenticated_input_mismatch = _authenticated_input_mismatch(
        raw_errors,
        attempt_errors,
        observed_expected_raw_count,
        prereg["workload"]["total_physical_calls"],
    )
    complete = len(records) == prereg["workload"]["total_physical_calls"] and not errors
    if not complete:
        determinism = {
            "hard_pass": False,
            "input_binding_hard_pass": False,
            "label_reproducibility_hard_pass": False,
            "same_process": [],
            "cross_replica": [],
        }
        eventization = {"hard_pass": False, "complete": False}
        execution_profile = {"hard_pass": False}
        parse_pass = False
        class_support_pass = False
    else:
        determinism = _determinism(prereg, records)
        execution_profile = _execution_profile(prereg, call_manifest, records)
        eventization = _eventization(prereg, call_manifest, records)
        parse_counts = Counter(row["parse_status"] for row in records.values())
        parse_pass = parse_counts == {"ok": prereg["workload"]["total_physical_calls"]}
        labels = Counter(
            records[name]["effective_label"] for name in prereg["class_support_artifacts"]
        )
        class_support_pass = labels["relevant"] >= 1 and labels["not_relevant"] >= 1
    status = _decision_status(
        complete=complete,
        authenticated_input_mismatch=authenticated_input_mismatch,
        input_binding_pass=(
            determinism["input_binding_hard_pass"] and execution_profile["hard_pass"]
        ),
        parse_pass=parse_pass,
        label_reproducibility_pass=determinism["label_reproducibility_hard_pass"],
        class_support_pass=class_support_pass,
        eventization_pass=eventization["hard_pass"],
    )
    parse_counts = Counter(row["parse_status"] for row in records.values())
    label_counts = Counter(row["effective_label"] for row in records.values())
    parsed_outputs = _parsed_output_payloads(prereg, call_manifest, records) if complete else []
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
        "execution_profile": execution_profile,
        "sampling_sensitivity": _sampling_sensitivity(records),
        "eventization": eventization,
        "parsed_output_manifest": [{
            "path": row["path"],
            "parsed_payload_sha256": row["payload"]["parsed_payload_sha256"],
        } for row in parsed_outputs],
        "protocol_adequacy_decision": status,
        "construct_validity_diagnostics_are_non_gating": True,
        "execution_seal_sha256": sha256_file(SEAL),
        "analyzer_source_sha256": sha256_file(Path(__file__)),
        "scope": "11-call V3 schema-and-determinism preflight only; never full-grid authorization",
    }
    result["metrics_payload_sha256"] = canonical_hash(result)
    return result, parsed_outputs


def analyze() -> dict:
    return analyze_bundle()[0]
