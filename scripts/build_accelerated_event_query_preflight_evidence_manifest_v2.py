#!/usr/bin/env python3
"""Build a read-only integrity inventory for the completed AEQ V2 pilot."""

from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash, sha256_file
from garc_eval.accelerated_event_query.oracle_response_protocol import loads_unique


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/preflight_v2"
ANALYZER_PATH = ROOT / "scripts/analyze_accelerated_event_query_oracle_preflight_v2.py"
DESTINATION = PREFLIGHT / "PILOT_EVIDENCE_MANIFEST_V2.json"


def load(path: Path) -> dict:
    return loads_unique(path.read_text(encoding="utf-8"))


def load_analyzer():
    spec = importlib.util.spec_from_file_location("aeq_v2_evidence_analyzer", ANALYZER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import sealed analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    analyzer = load_analyzer()
    runner, prereg, _, _, calls = analyzer.expected_calls()
    expected_paths = {(runner.RAW / row["shard"] / row["artifact"]).resolve() for row in calls}
    observed_paths = {path.resolve() for path in runner.RAW.glob("*/*.json")}
    if observed_paths != expected_paths or len(calls) != 32:
        raise RuntimeError("raw artifact set is not the exact authorized 32-call set")

    records = {}
    raw_rows = []
    for row in calls:
        path = runner.RAW / row["shard"] / row["artifact"]
        record = load(path)
        analyzer.validate_record(runner, row, record)
        records[(row["shard"], row["artifact"])] = record
        raw_rows.append({
            "artifact_path": str(path.relative_to(ROOT)),
            "artifact_file_sha256": sha256_file(path),
            "record_sha256": record["record_sha256"],
            "raw_response_sha256": record["raw_response_sha256"],
            "input_identity_sha256": record["input_identity_sha256"],
            "model_input_identity_sha256": record["model_input_identity_sha256"],
            "processed_input_sha256": record["processed_input_sha256"],
            "generated_token_ids_sha256": record["generated_token_ids_sha256"],
            "parse_status": record["parse_status"],
            "effective_label": record["effective_label"],
            "declared_physical_gpus": record["runtime"]["declared_physical_gpus"],
            "inference_seconds": record["runtime"]["inference_seconds"],
        })

    events = []
    ledger_rows = []
    for shard in runner.SHARDS:
        path = runner.ATTEMPTS / f"{shard}.jsonl"
        shard_events = analyzer.validate_attempt_chain(path)
        events.extend(shard_events)
        ledger_rows.append({
            "execution_shard": shard,
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "event_counts": dict(Counter(row["event"] for row in shard_events)),
        })
    event_counts = analyzer.validate_authorized_accounting(calls, records, events)

    named_artifacts = [
        "PREFLIGHT_V2_EXECUTION_SEAL.json",
        "COMPUTE_APPROVAL_V2.json",
        "AUTHORIZED_CALL_MANIFEST_V2.json",
        "PREFLIGHT_METRICS_V2.json",
        "GROUNDING_QUEUE_V2.json",
        "GROUNDING_REVIEW_V2.json",
        "PREFLIGHT_FINAL_DECISION_V2.json",
        "USER_DECISION_MAPPING_V2.json",
        "TARGETED_PILOT_DECISION_V2.json",
    ]
    artifact_hashes = {
        name: sha256_file(PREFLIGHT / name)
        for name in named_artifacts
    }
    model_loads = {}
    for (shard, _), record in records.items():
        model_loads.setdefault(shard, record["runtime"]["model_load_seconds"])
    inference_seconds = sum(record["runtime"]["inference_seconds"] for record in records.values())
    decision = load(PREFLIGHT / "TARGETED_PILOT_DECISION_V2.json")
    value = {
        "status": "PASS_COMPLETE_INTEGRITY_INVENTORY",
        "experiment_id": prereg["experiment_id"],
        "scope": "completed targeted 32-call pilot only",
        "authorized_calls": 32,
        "observed_raw_records": len(records),
        "physical_event_counts": dict(event_counts),
        "failure_or_uncertain_generation_events": sum(
            row["event"] in {"GENERATION_FAILED", "UNCERTAIN_INTERRUPTION", "FAILED_POST_INFERENCE"}
            for row in events
        ),
        "raw_label_counts": dict(Counter(record["effective_label"] for record in records.values())),
        "parse_status_counts": dict(Counter(record["parse_status"] for record in records.values())),
        "inference_seconds": inference_seconds,
        "two_gpu_inference_hours": 2.0 * inference_seconds / 3600.0,
        "model_load_seconds_by_shard": model_loads,
        "model_load_seconds_total": sum(model_loads.values()),
        "declared_gpu_pairs_by_shard": {
            shard: next(record["runtime"]["declared_physical_gpus"]
                        for (record_shard, _), record in records.items() if record_shard == shard)
            for shard in runner.SHARDS
        },
        "attempt_ledgers": ledger_rows,
        "raw_records": raw_rows,
        "artifact_sha256": artifact_hashes,
        "decision": decision["decision"],
        "decision_payload_sha256": decision["decision_payload_sha256"],
    }
    value["manifest_payload_sha256"] = canonical_hash(value)
    if DESTINATION.exists():
        raise RuntimeError(f"refusing to overwrite evidence manifest: {DESTINATION}")
    temporary = DESTINATION.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, DESTINATION)
    print(json.dumps({
        "path": str(DESTINATION.relative_to(ROOT)),
        "sha256": sha256_file(DESTINATION),
        "decision": value["decision"],
        "records": value["observed_raw_records"],
    }, indent=2))


if __name__ == "__main__":
    main()
