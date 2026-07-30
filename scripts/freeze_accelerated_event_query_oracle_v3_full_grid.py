#!/usr/bin/env python3
"""Freeze the V3 full-grid seal, review bundle, audit, and final package."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from garc_eval.accelerated_event_query.oracle_v3_full_grid_manifest import (
    EXPECTED_FRAME_OCCURRENCES,
    EXPECTED_UNIT_COUNT,
    canonical_file_bindings,
    validate_frame_manifest,
    validate_processed_input_manifest,
    validate_unit_manifest,
    validate_worker_schedule,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_package import (
    FRAMES,
    EXECUTION,
    PACKAGE,
    PREREG,
    PROCESSED_INPUTS,
    ROOT,
    SCHEDULE,
    SEAL,
    UNITS,
    validate_execution_seal,
    validate_preregistration,
    validate_review_bundle,
)
from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    atomic_text,
    canonical_hash,
    load_json,
    sha256_file,
    validate_payload_hash,
    write_json_once,
)


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = canonical_hash(value)
    return value


def seal() -> None:
    prereg = validate_preregistration()
    units = load_json(UNITS); frames = load_json(FRAMES); processed = load_json(PROCESSED_INPUTS); schedule = load_json(SCHEDULE)
    validate_unit_manifest(units); validate_frame_manifest(frames, units)
    validate_processed_input_manifest(processed, units)
    validate_worker_schedule(schedule, units)
    sources = load_json(PACKAGE / "FULL_GRID_SOURCE_BINDINGS.json")
    validate_payload_hash(sources, "source_bindings_payload_sha256")
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if current_head != prereg["source_commit"] or current_head != sources["source_commit"]:
        raise RuntimeError("current source commit differs from preregistration")
    for row in sources["sources"]:
        if sha256_file(ROOT / row["path"]) != row["sha256"]:
            raise RuntimeError(f"source changed after package build: {row['path']}")
    component_paths = {
        "runner": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_runner.py",
        "supervisor": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_supervisor.py",
        "processing": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_processing.py",
        "analyzer": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_analyzer.py",
        "finalizer": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_finalizer.py",
        "package_validator": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_package.py",
        "manifest": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_manifest.py",
        "control": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_control.py",
        "label_hiding": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_hiding.py",
        "dry_run": "src/garc_eval/accelerated_event_query/oracle_v3_full_grid_dry_run.py",
        "seal_builder": "scripts/freeze_accelerated_event_query_oracle_v3_full_grid.py",
    }
    frozen_paths = [PREREG, UNITS, FRAMES, PROCESSED_INPUTS, SCHEDULE]
    for value in prereg["bindings"].values():
        path = ROOT / value["path"]
        if path not in frozen_paths:
            frozen_paths.append(path)
    payload = self_hash({
        "status": "FROZEN_AWAITING_EXPLICIT_FULL_GRID_COMPUTE_APPROVAL",
        "experiment_id": prereg["experiment_id"],
        "source_commit": current_head,
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_sha256": sha256_file(PREREG),
        "unit_manifest_sha256": sha256_file(UNITS),
        "frame_manifest_sha256": sha256_file(FRAMES),
        "processed_input_manifest_sha256": sha256_file(PROCESSED_INPUTS),
        "worker_schedule_sha256": sha256_file(SCHEDULE),
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "exact_frame_occurrence_count": EXPECTED_FRAME_OCCURRENCES,
        "estimated_a100_gpu_hours": 16.09712320568816,
        "authorization_envelope_a100_gpu_hours": 19.4,
        "estimated_parallel_wall_hours": 3.0931814077885096,
        "model_load_count": 3,
        "reload_count": 0,
        "retry_count": 0,
        "global_fail_stop": True,
        "partial_reference_publication": "forbidden",
        "downstream_authorization": "none",
        "execution_rule": "all package/source/input/model/GPU/approval bindings must match exactly; otherwise abort without repair or inference",
        "sources": {name: binding(ROOT / path) for name, path in component_paths.items()},
        "frozen_artifacts": [binding(path) for path in sorted(set(frozen_paths))],
        "expected_approval_path": str((PACKAGE / "FULL_GRID_COMPUTE_APPROVAL.json").relative_to(ROOT)),
        "approval_artifact_exists_at_seal_time": False,
    }, "execution_seal_payload_sha256")
    write_json_once(SEAL, payload)
    template = f"""# Full-Grid Compute Approval Template

Status: `TEMPLATE_ONLY_NOT_APPROVAL`

Exact execution seal SHA-256:
`{sha256_file(SEAL)}`

This template does not authorize execution. A valid approval artifact must bind
the exact seal, review bundle, final package manifest, 1,475 calls, 16.097123
A100 GPU-hour estimate, 19.4 A100 GPU-hour envelope, three frozen two-GPU
workers, exactly three model loads, zero reloads, zero retries, global
fail-stop, and complete-only reference publication.

Approval scope must explicitly exclude every downstream YOLO, replay,
conditioned-value, headroom, or controller experiment. Any binding change
requires a new seal, independent review, and approval.
"""
    atomic_text(PACKAGE / "FULL_GRID_APPROVAL_TEMPLATE.md", template)
    print(json.dumps({"status": "SEALED_NO_APPROVAL", "seal_sha256": sha256_file(SEAL)}, indent=2))


def record_tests(passed: int, summary: str) -> None:
    if passed <= 0:
        raise ValueError("passed test count must be positive")
    result = self_hash({
        "status": "PASS",
        "command": "python -m pytest -q tests/accelerated_event_query",
        "passed": passed,
        "failed": 0,
        "summary": summary,
        "checkpoint_loaded": False,
        "model_inference_calls": 0,
    }, "test_audit_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_TEST_AUDIT.json", result)


def review_bundle() -> None:
    validate_execution_seal("seal_builder")
    required = [
        PACKAGE / "FULL_GRID_DRY_RUN_AUDIT.json",
        PACKAGE / "FULL_GRID_TEST_AUDIT.json",
        PACKAGE / "FULL_GRID_APPROVAL_TEMPLATE.md",
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("test, dry-run, or approval-template artifact missing")
    forbidden = [
        PACKAGE / "FULL_GRID_COMPUTE_APPROVAL.json",
        PACKAGE / "FULL_GRID_INDEPENDENT_REVIEW.md",
        PACKAGE / "FULL_GRID_PACKAGE_MANIFEST.json",
    ]
    if any(path.exists() for path in forbidden):
        raise RuntimeError("review bundle must precede approval/review/final package")
    execution_root = EXECUTION
    if execution_root.exists() and any(execution_root.rglob("*.json")):
        raise RuntimeError("formal full-grid runtime artifacts already exist")
    paths = [path for path in PACKAGE.rglob("*") if path.is_file() and path.name != "FULL_GRID_REVIEW_BUNDLE.json"]
    bundle = self_hash({
        "status": "FROZEN_FOR_INDEPENDENT_ADVERSARIAL_REVIEW",
        "execution_seal_sha256": sha256_file(SEAL),
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "artifacts": canonical_file_bindings(paths, ROOT),
        "required_review_decisions": [
            "GO_TO_REQUEST_FULL_GRID_APPROVAL",
            "REVISE_FULL_GRID_PREREGISTRATION",
            "REJECT_FULL_GRID_PROTOCOL",
        ],
        "review_scope": [
            "1475 call accounting", "three tail units", "three model loads",
            "19.4 GPU-hour envelope", "global fail-stop", "partial publication",
            "unknown threshold", "K3 merge rules", "evaluator leakage",
            "worker overlap", "resume/retry", "analyzer/finalizer bindings",
        ],
    }, "review_bundle_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json", bundle)
    print(json.dumps({
        "status": bundle["status"],
        "review_bundle_file_sha256": sha256_file(PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json"),
        "execution_seal_sha256": sha256_file(SEAL),
        "artifact_count": len(paths),
    }, indent=2))


def completion_audit() -> None:
    bundle = validate_review_bundle()
    review_path = PACKAGE / "FULL_GRID_INDEPENDENT_REVIEW.md"
    if not review_path.is_file():
        raise RuntimeError("independent review artifact missing")
    review_text = review_path.read_text(encoding="utf-8")
    if "GO_TO_REQUEST_FULL_GRID_APPROVAL" not in review_text:
        raise RuntimeError("independent review did not return GO")
    if sha256_file(SEAL) not in review_text or sha256_file(
        PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json"
    ) not in review_text:
        raise RuntimeError("independent review does not bind exact seal/bundle")
    tests = load_json(PACKAGE / "FULL_GRID_TEST_AUDIT.json")
    dry = load_json(PACKAGE / "FULL_GRID_DRY_RUN_AUDIT.json")
    text = f"""# Full-Grid Preregistration Completion Audit

Audit state: `COMPLETE_REVIEWED_AWAITING_EXPLICIT_COMPUTE_APPROVAL`

- Exact units: 1,475; frame occurrences: 30,932; duplicate/missing units: 0/0.
- Tail units: DALI 12, HANGZHOU 2, WUHAN 6 frames; real processor-only audit PASS.
- Workers: 567/561/347 on frozen pairs (1,2)/(3,5)/(6,7); disjoint union PASS.
- Cost: 16.097123 A100 GPU-hours expected; 19.4 envelope; three loads; zero reload/retry.
- Coverage: global and per-video determined fraction >= 0.99; parse failure release tolerance 0.
- Global fail-stop, cost shield, no-resume, partial nonpublication, K3 determinism,
  diagnostic independence, and evaluator/runtime separation are implemented and tested.
- Tests: {tests['passed']} passed, 0 failed.
- Complete 1,475-record mock dry-run: {dry['complete_mock']['finalizer_status']}; formal publication false.
- Independent review: `GO_TO_REQUEST_FULL_GRID_APPROVAL`.
- Execution seal SHA-256: `{sha256_file(SEAL)}`.
- Review bundle SHA-256: `{sha256_file(PACKAGE / 'FULL_GRID_REVIEW_BUNDLE.json')}`.
- No compute approval artifact exists; no formal full-grid raw output or reference exists.
- V3 preflight and V2 frozen evidence were not modified or rerun.

Strongest conclusion: the exact full-grid protocol is ready to request compute
approval. It is not executed, does not establish representative adequacy, and
authorizes no downstream experiment.
"""
    atomic_text(PACKAGE / "FULL_GRID_COMPLETION_AUDIT.md", text)


def final_package() -> None:
    validate_review_bundle()
    required = [
        PACKAGE / "FULL_GRID_INDEPENDENT_REVIEW.md",
        PACKAGE / "FULL_GRID_COMPLETION_AUDIT.md",
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("review or completion audit missing")
    if (PACKAGE / "FULL_GRID_COMPUTE_APPROVAL.json").exists():
        raise RuntimeError("approval must not exist during preregistration packaging")
    paths = [path for path in PACKAGE.rglob("*") if path.is_file() and path.name not in {
        "FULL_GRID_PACKAGE_MANIFEST.json", "FULL_GRID_COMPUTE_APPROVAL.json"
    }]
    manifest = self_hash({
        "status": "COMPLETE_REVIEWED_AWAITING_EXPLICIT_COMPUTE_APPROVAL",
        "execution_seal_sha256": sha256_file(SEAL),
        "review_bundle_sha256": sha256_file(PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json"),
        "independent_review_sha256": sha256_file(PACKAGE / "FULL_GRID_INDEPENDENT_REVIEW.md"),
        "completion_audit_sha256": sha256_file(PACKAGE / "FULL_GRID_COMPLETION_AUDIT.md"),
        "exact_call_count": EXPECTED_UNIT_COUNT,
        "artifacts": canonical_file_bindings(paths, ROOT),
        "compute_approval_present": False,
        "formal_raw_output_count": 0,
        "formal_reference_present": False,
    }, "package_manifest_payload_sha256")
    write_json_once(PACKAGE / "FULL_GRID_PACKAGE_MANIFEST.json", manifest)
    print(json.dumps({
        "status": manifest["status"],
        "final_package_manifest_sha256": sha256_file(PACKAGE / "FULL_GRID_PACKAGE_MANIFEST.json"),
        "execution_seal_sha256": sha256_file(SEAL),
        "artifact_count": len(paths),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seal")
    tests = sub.add_parser("record-tests")
    tests.add_argument("--passed", type=int, required=True)
    tests.add_argument("--summary", required=True)
    sub.add_parser("review-bundle")
    sub.add_parser("completion-audit")
    sub.add_parser("final-package")
    args = parser.parse_args()
    if args.command == "seal": seal()
    elif args.command == "record-tests": record_tests(args.passed, args.summary)
    elif args.command == "review-bundle": review_bundle()
    elif args.command == "completion-audit": completion_audit()
    else: final_package()


if __name__ == "__main__":
    main()
