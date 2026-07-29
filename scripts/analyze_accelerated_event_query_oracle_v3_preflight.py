#!/usr/bin/env python3
"""Analyze the sealed AEQ V3 preflight after authorized execution."""

import json

from garc_eval.accelerated_event_query.oracle_v3_analyzer import BASE, analyze_bundle
from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    canonical_hash,
    load_json,
    sha256_file,
    write_json_once,
)
from garc_eval.accelerated_event_query.oracle_v3_runner import PREREG, ROOT, SEAL, SHARDS


METRICS = BASE / "preflight/V3_SCHEMA_PREFLIGHT_METRICS.json"
EVIDENCE = BASE / "preflight/V3_SCHEMA_PREFLIGHT_EVIDENCE_MANIFEST.json"


def _evidence_manifest(result: dict, parsed_outputs: list[dict]) -> dict:
    prereg = load_json(PREREG)
    calls = load_json(
        ROOT / prereg["bindings"]["authorized_call_manifest_path"]
    )["calls"]
    raw_outputs = []
    for call in calls:
        path = ROOT / call["artifact_path"]
        if path.exists():
            raw_outputs.append({
                "artifact_name": call["artifact_name"],
                "path": call["artifact_path"],
                "file_sha256": sha256_file(path),
            })
    parsed_manifest = []
    for row in parsed_outputs:
        path = ROOT / row["path"]
        parsed_manifest.append({
            "path": row["path"],
            "file_sha256": sha256_file(path),
            "parsed_payload_sha256": row["payload"]["parsed_payload_sha256"],
        })
    ledgers = []
    for shard in SHARDS:
        path = BASE / f"preflight/attempt_ledgers/{shard}.jsonl"
        if path.exists():
            ledgers.append({
                "execution_shard": shard,
                "path": str(path.relative_to(ROOT)),
                "file_sha256": sha256_file(path),
                "event_count": len(path.read_text(encoding="utf-8").splitlines()),
            })
    payload = {
        "status": "WRITE_ONCE_POSTRUN_EVIDENCE_MANIFEST",
        "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": sha256_file(SEAL),
        "metrics_path": str(METRICS.relative_to(ROOT)),
        "metrics_file_sha256": sha256_file(METRICS),
        "metrics_payload_sha256": result["metrics_payload_sha256"],
        "raw_outputs": raw_outputs,
        "parsed_outputs": parsed_manifest,
        "attempt_ledgers": ledgers,
        "unknown_contradictory_unsupported_and_failed_outputs_are_not_relabelled": True,
    }
    payload["evidence_payload_sha256"] = canonical_hash(payload)
    return payload


def main() -> None:
    result, parsed_outputs = analyze_bundle()
    for row in parsed_outputs:
        write_json_once(ROOT / row["path"], row["payload"])
    write_json_once(METRICS, result)
    write_json_once(EVIDENCE, _evidence_manifest(result, parsed_outputs))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
