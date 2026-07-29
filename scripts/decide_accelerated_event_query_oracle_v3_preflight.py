#!/usr/bin/env python3
"""Write exactly one allowed V3 preflight decision from sealed metrics."""

import json
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    write_json_once,
)
from garc_eval.accelerated_event_query.oracle_v3_runner import BASE, ROOT, SEAL, validate_execution_seal


METRICS = BASE / "preflight/V3_SCHEMA_PREFLIGHT_METRICS.json"
MAPPING = BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION_MAPPING.json"
DECISION = BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION.json"


def decide() -> dict:
    seal, prereg = validate_execution_seal("decision")
    metrics = load_json(METRICS)
    mapping = load_json(MAPPING)
    if metrics.get("execution_seal_sha256") != sha256_file(SEAL):
        raise RuntimeError("metrics/execution-seal mismatch")
    if metrics.get("analyzer_source_sha256") != seal["sources"]["analyzer_source_sha256"]:
        raise RuntimeError("metrics/analyzer-source mismatch")
    status = metrics["protocol_adequacy_decision"]
    allowed = set(mapping["allowed_decisions"])
    if status not in allowed:
        raise RuntimeError("analyzer emitted a nonfrozen decision")
    result = {
        "experiment_id": prereg["experiment_id"],
        "decision": status,
        "metrics_sha256": sha256_file(METRICS),
        "mapping_sha256": sha256_file(MAPPING),
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
