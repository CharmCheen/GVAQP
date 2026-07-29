#!/usr/bin/env python3
"""Write exactly one allowed V3 preflight decision from sealed metrics."""

import json
from pathlib import Path

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
    validate_payload_hash(metrics, "metrics_payload_sha256")
    validate_payload_hash(evidence, "evidence_payload_sha256")
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
        evidence.get("experiment_id") == prereg["experiment_id"],
        evidence.get("execution_seal_sha256") == sha256_file(SEAL),
        evidence.get("metrics_file_sha256") == sha256_file(METRICS),
        evidence.get("metrics_payload_sha256") == metrics["metrics_payload_sha256"],
    )):
        raise RuntimeError("postrun evidence manifest mismatch")
    for collection in ("raw_outputs", "parsed_outputs", "attempt_ledgers"):
        for row in evidence[collection]:
            if sha256_file(ROOT / row["path"]) != row["file_sha256"]:
                raise RuntimeError(f"postrun evidence file mismatch: {row['path']}")
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
