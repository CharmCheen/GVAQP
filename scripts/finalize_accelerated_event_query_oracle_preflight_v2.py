#!/usr/bin/env python3
"""Finalize AEQ preflight V2 only from sealed metrics and complete claim review."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash, sha256_file
from garc_eval.accelerated_event_query.oracle_response_protocol import loads_unique


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREFLIGHT = OUT / "operational_oracle/preflight_v2"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
SEAL = PREFLIGHT / "PREFLIGHT_V2_EXECUTION_SEAL.json"
METRICS = PREFLIGHT / "PREFLIGHT_METRICS_V2.json"
QUEUE = PREFLIGHT / "GROUNDING_QUEUE_V2.json"
FINAL = PREFLIGHT / "PREFLIGHT_FINAL_DECISION_V2.json"


def load(path: Path) -> dict:
    return loads_unique(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite final decision: {path}")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def validate_seal() -> tuple[dict, dict]:
    seal = load(SEAL)
    prereg = load(PREREG)
    if seal.get("status") != "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION":
        raise RuntimeError("execution seal is not frozen")
    if seal.get("preregistration_sha256") != sha256_file(PREREG):
        raise RuntimeError("execution seal/preregistration mismatch")
    source = seal["sources"]
    if sha256_file(Path(__file__)) != source["finalizer_source_sha256"]:
        raise RuntimeError("sealed finalizer source mismatch")
    protocol_path = ROOT / prereg["bindings"]["grounding_protocol_path"]
    if sha256_file(protocol_path) != prereg["bindings"]["grounding_protocol_sha256"]:
        raise RuntimeError("grounding protocol binding mismatch")
    return seal, prereg


def derive_final_status(analyzer_status: str, verdicts: dict[str, str], expected_ids: set[str]) -> str:
    if analyzer_status != "PENDING_INDEPENDENT_CLAIM_GROUNDING_REVIEW":
        return analyzer_status
    observed = set(verdicts.values())
    if "UNSUPPORTED" in observed:
        return "FAIL_CLAIM_GROUNDING_GATE"
    if set(verdicts) != expected_ids or "INDETERMINATE" in observed:
        return "REVIEW_REQUIRED"
    if expected_ids and observed == {"SUPPORTED"}:
        return "PASS_TARGETED_PILOT"
    return "REVIEW_REQUIRED"


def finalize(review_path: Path) -> dict:
    seal, prereg = validate_seal()
    metrics = load(METRICS)
    queue = load(QUEUE)
    review = load(review_path)
    sources = seal["sources"]
    if metrics.get("execution_seal_sha256") != sha256_file(SEAL):
        raise RuntimeError("metrics/execution-seal mismatch")
    if metrics.get("analyzer_source_sha256") != sources["analyzer_source_sha256"]:
        raise RuntimeError("metrics/analyzer-source mismatch")
    if metrics.get("runner_source_sha256") != sources["runner_source_sha256"]:
        raise RuntimeError("metrics/runner-source mismatch")
    if not metrics.get("artifact_authentication_pass") or not metrics.get("authorized_generation_accounting_pass"):
        raise RuntimeError("metrics do not establish artifact and generation authentication")
    claimed_queue_hash = queue.get("queue_payload_sha256")
    unsigned_queue = {key: value for key, value in queue.items() if key != "queue_payload_sha256"}
    if claimed_queue_hash != canonical_hash(unsigned_queue):
        raise RuntimeError("grounding queue payload hash mismatch")
    if metrics.get("grounding_queue_payload_sha256") != claimed_queue_hash:
        raise RuntimeError("metrics/grounding-queue mismatch")
    required_review_fields = {
        "status", "protocol_sha256", "queue_file_sha256", "metrics_file_sha256",
        "reviewer_id", "independence_declaration", "reviews",
    }
    if set(review) != required_review_fields:
        raise RuntimeError("grounding review top-level schema mismatch")
    if review["status"] != "COMPLETED_INDEPENDENT_VISUAL_REVIEW":
        raise RuntimeError("grounding review is not complete")
    if review["protocol_sha256"] != prereg["bindings"]["grounding_protocol_sha256"]:
        raise RuntimeError("grounding review/protocol mismatch")
    if review["queue_file_sha256"] != sha256_file(QUEUE) or review["metrics_file_sha256"] != sha256_file(METRICS):
        raise RuntimeError("grounding review does not bind the exact queue and metrics")
    if not isinstance(review["reviewer_id"], str) or not review["reviewer_id"].strip():
        raise RuntimeError("grounding reviewer identity is missing")
    if not isinstance(review["independence_declaration"], str) or not review["independence_declaration"].strip():
        raise RuntimeError("grounding independence declaration is missing")
    allowed = {"SUPPORTED", "UNSUPPORTED", "INDETERMINATE"}
    reviews = {}
    for row in review["reviews"]:
        if set(row) != {"claim_id", "verdict", "visual_rationale"}:
            raise RuntimeError("grounding claim-review schema mismatch")
        if row["claim_id"] in reviews or row["verdict"] not in allowed:
            raise RuntimeError("duplicate claim review or invalid verdict")
        if not isinstance(row["visual_rationale"], str) or not row["visual_rationale"].strip():
            raise RuntimeError("visual rationale is missing")
        reviews[row["claim_id"]] = row
    expected_ids = {row["claim_id"] for row in queue["claims"]}
    if set(reviews) != expected_ids or queue.get("claim_count") != len(expected_ids):
        raise RuntimeError("grounding review is missing claims or contains extras")

    analyzer_status = metrics["overall_gate_status"]
    final_status = derive_final_status(
        analyzer_status, {claim_id: row["verdict"] for claim_id, row in reviews.items()}, expected_ids
    )
    result = {
        "experiment_id": prereg["experiment_id"],
        "final_status": final_status,
        "analyzer_status": analyzer_status,
        "claim_count": len(expected_ids),
        "verdict_counts": {verdict: sum(row["verdict"] == verdict for row in reviews.values())
                           for verdict in sorted(allowed)},
        "metrics_sha256": sha256_file(METRICS),
        "grounding_queue_sha256": sha256_file(QUEUE),
        "grounding_review_path": str(review_path.relative_to(ROOT)),
        "grounding_review_sha256": sha256_file(review_path),
        "execution_seal_sha256": sha256_file(SEAL),
        "scope_limitation": "A pass validates only the targeted preflight and does not authorize a larger oracle run.",
    }
    result["decision_payload_sha256"] = canonical_hash(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    review_path = args.review if args.review.is_absolute() else ROOT / args.review
    result = finalize(review_path)
    write_once(FINAL, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
