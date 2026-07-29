#!/usr/bin/env python3
"""Write exactly one allowed V3 preflight decision from sealed metrics."""

import json
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_v3_analyzer import analyze_bundle
from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    validate_payload_hash,
    write_json_once,
)
from garc_eval.accelerated_event_query.oracle_v3_runner import BASE, ROOT, SEAL, validate_execution_seal


METRICS = BASE / "preflight/V3_SCHEMA_PREFLIGHT_METRICS.json"
MAPPING = BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION_MAPPING.json"
DECISION = BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION.json"
EVIDENCE = BASE / "preflight/V3_SCHEMA_PREFLIGHT_EVIDENCE_MANIFEST.json"


def decide() -> dict:
    seal, prereg = validate_execution_seal("decision")
    metrics = load_json(METRICS)
    mapping = load_json(MAPPING)
    evidence = load_json(EVIDENCE)
    recomputed_metrics, recomputed_parsed_outputs = analyze_bundle()
    if recomputed_metrics != metrics:
        raise RuntimeError("stored metrics differ from frozen analyzer recomputation")
    validate_payload_hash(metrics, "metrics_payload_sha256")
    validate_payload_hash(evidence, "evidence_payload_sha256")
    expected_evidence_keys = {
        "status", "experiment_id", "execution_seal_sha256", "metrics_path",
        "metrics_file_sha256", "metrics_payload_sha256", "raw_outputs",
        "parsed_outputs", "attempt_ledgers",
        "unknown_contradictory_unsupported_and_failed_outputs_are_not_relabelled",
        "evidence_payload_sha256",
    }
    if set(evidence) != expected_evidence_keys:
        raise RuntimeError("postrun evidence schema mismatch")
    if metrics.get("experiment_id") != prereg["experiment_id"]:
        raise RuntimeError("metrics/experiment mismatch")
    if metrics.get("execution_seal_sha256") != sha256_file(SEAL):
        raise RuntimeError("metrics/execution-seal mismatch")
    if metrics.get("analyzer_source_sha256") != seal["sources"]["analyzer_source_sha256"]:
        raise RuntimeError("metrics/analyzer-source mismatch")
    mapping_sha256 = sha256_file(MAPPING)
    if not all((
        mapping_sha256 == prereg["bindings"]["decision_mapping_sha256"],
        mapping_sha256 == seal["decision_mapping_sha256"],
    )):
        raise RuntimeError("decision-mapping binding mismatch")
    if not all((
        evidence.get("status") == "WRITE_ONCE_POSTRUN_EVIDENCE_MANIFEST",
        evidence.get("experiment_id") == prereg["experiment_id"],
        evidence.get("execution_seal_sha256") == sha256_file(SEAL),
        evidence.get("metrics_path") == str(METRICS.relative_to(ROOT)),
        evidence.get("metrics_file_sha256") == sha256_file(METRICS),
        evidence.get("metrics_payload_sha256") == metrics["metrics_payload_sha256"],
        evidence.get(
            "unknown_contradictory_unsupported_and_failed_outputs_are_not_relabelled"
        ) is True,
    )):
        raise RuntimeError("postrun evidence manifest mismatch")
    call_manifest = load_json(
        ROOT / prereg["bindings"]["authorized_call_manifest_path"]
    )
    expected_raw_paths = {
        row["artifact_path"] for row in call_manifest["calls"]
        if (ROOT / row["artifact_path"]).exists()
    }
    expected_parsed_paths = {
        row["path"] for row in metrics["parsed_output_manifest"]
    }
    recomputed_parsed_by_path = {
        row["path"]: row["payload"] for row in recomputed_parsed_outputs
    }
    call_by_raw_path = {row["artifact_path"]: row for row in call_manifest["calls"]}
    parsed_by_path = {row["path"]: row for row in metrics["parsed_output_manifest"]}
    expected_ledger_paths = {
        str((BASE / f"preflight/attempt_ledgers/{shard}.jsonl").relative_to(ROOT))
        for shard in ("DALI", "HANGZHOU", "WUHAN")
        if (BASE / f"preflight/attempt_ledgers/{shard}.jsonl").exists()
    }
    if not all((
        {row.get("path") for row in evidence["raw_outputs"]} == expected_raw_paths,
        {row.get("path") for row in evidence["parsed_outputs"]} == expected_parsed_paths,
        {row.get("path") for row in evidence["attempt_ledgers"]} == expected_ledger_paths,
        len(evidence["raw_outputs"]) == len(expected_raw_paths),
        len(evidence["parsed_outputs"]) == len(expected_parsed_paths),
        len(evidence["attempt_ledgers"]) == len(expected_ledger_paths),
    )):
        raise RuntimeError("postrun evidence membership mismatch")
    row_schemas = {
        "raw_outputs": {"artifact_name", "path", "file_sha256", "record_sha256"},
        "parsed_outputs": {"path", "file_sha256", "parsed_payload_sha256"},
        "attempt_ledgers": {"execution_shard", "path", "file_sha256", "event_count"},
    }
    for collection in ("raw_outputs", "parsed_outputs", "attempt_ledgers"):
        for row in evidence[collection]:
            if set(row) != row_schemas[collection]:
                raise RuntimeError(f"postrun evidence row schema mismatch: {collection}")
            if sha256_file(ROOT / row["path"]) != row["file_sha256"]:
                raise RuntimeError(f"postrun evidence file mismatch: {row['path']}")
            if collection == "raw_outputs":
                if not all((
                    row["artifact_name"] == call_by_raw_path[row["path"]]["artifact_name"],
                    load_json(ROOT / row["path"])["record_sha256"] == row["record_sha256"],
                )):
                    raise RuntimeError(f"postrun raw-record mismatch: {row['path']}")
            elif collection == "parsed_outputs":
                parsed = load_json(ROOT / row["path"])
                validate_payload_hash(parsed, "parsed_payload_sha256")
                if not all((
                    parsed == recomputed_parsed_by_path[row["path"]],
                    parsed["parsed_payload_sha256"] == row["parsed_payload_sha256"],
                    parsed["parsed_payload_sha256"]
                        == parsed_by_path[row["path"]]["parsed_payload_sha256"],
                )):
                    raise RuntimeError(f"postrun parsed-payload mismatch: {row['path']}")
            else:
                observed_events = len(
                    (ROOT / row["path"]).read_text(encoding="utf-8").splitlines()
                )
                if row["event_count"] != observed_events:
                    raise RuntimeError(f"postrun ledger-count mismatch: {row['path']}")
                if row["path"] != str((
                    BASE / f"preflight/attempt_ledgers/{row['execution_shard']}.jsonl"
                ).relative_to(ROOT)):
                    raise RuntimeError(f"postrun ledger-shard mismatch: {row['path']}")
    if metrics.get("complete") and not all((
        len(expected_raw_paths) == prereg["workload"]["total_physical_calls"],
        len(expected_parsed_paths) == prereg["workload"]["total_physical_calls"],
        len(expected_ledger_paths) == 3,
        sum(row["event_count"] for row in evidence["attempt_ledgers"])
            == 4 * prereg["workload"]["total_physical_calls"],
    )):
        raise RuntimeError("complete metrics lack complete postrun evidence")
    status = metrics["protocol_adequacy_decision"]
    allowed = set(mapping["allowed_decisions"])
    if status not in allowed:
        raise RuntimeError("analyzer emitted a nonfrozen decision")
    result = {
        "experiment_id": prereg["experiment_id"],
        "decision": status,
        "metrics_sha256": sha256_file(METRICS),
        "mapping_sha256": mapping_sha256,
        "evidence_manifest_sha256": sha256_file(EVIDENCE),
        "execution_seal_sha256": sha256_file(SEAL),
        "scope": "V3 11-call schema-and-determinism preflight only",
    }
    result["decision_payload_sha256"] = canonical_hash(result)
    return result


def main() -> None:
    result = decide()
    write_json_once(DECISION, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
