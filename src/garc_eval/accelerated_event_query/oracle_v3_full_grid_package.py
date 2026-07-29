"""Fail-closed validation of the frozen V3 full-grid preregistration package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .oracle_v3_full_grid_manifest import (
    EXPECTED_UNIT_COUNT,
    validate_frame_manifest,
    validate_processed_input_manifest,
    validate_unit_manifest,
    validate_worker_schedule,
)
from .oracle_v3_manifest import load_json, sha256_file, validate_payload_hash


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
PACKAGE = BASE / "full_grid_preregistration"
EXECUTION = BASE / "full_grid_execution"
PREREG = PACKAGE / "FULL_GRID_PREREGISTRATION.json"
SEAL = PACKAGE / "FULL_GRID_EXECUTION_SEAL.json"
UNITS = PACKAGE / "FULL_GRID_UNIT_MANIFEST.json"
FRAMES = PACKAGE / "FULL_GRID_FRAME_MANIFEST.json"
PROCESSED_INPUTS = PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json"
SCHEDULE = PACKAGE / "FULL_GRID_WORKER_SCHEDULE.json"
DECISIONS = PACKAGE / "FULL_GRID_DECISION_MAPPING.json"
APPROVAL = PACKAGE / "FULL_GRID_COMPUTE_APPROVAL.json"


def _validate_path_hash(binding: dict[str, Any]) -> None:
    path = ROOT / binding["path"]
    if not path.is_file() or sha256_file(path) != binding["sha256"]:
        raise RuntimeError(f"full-grid binding mismatch: {binding['path']}")


def validate_preregistration() -> dict[str, Any]:
    prereg = load_json(PREREG)
    validate_payload_hash(prereg, "preregistration_payload_sha256")
    if prereg.get("status") != "FROZEN_BEFORE_FULL_GRID_EXECUTION":
        raise RuntimeError("full-grid preregistration status mismatch")
    if prereg.get("workload", {}).get("exact_call_count") != EXPECTED_UNIT_COUNT:
        raise RuntimeError("full-grid preregistration call count mismatch")
    for binding in prereg.get("bindings", {}).values():
        if isinstance(binding, dict) and set(binding) >= {"path", "sha256"}:
            _validate_path_hash(binding)
    return prereg


def validate_execution_seal(component: str) -> tuple[dict[str, Any], dict[str, Any]]:
    seal = load_json(SEAL)
    validate_payload_hash(seal, "execution_seal_payload_sha256")
    prereg = validate_preregistration()
    if seal.get("status") != "FROZEN_AWAITING_EXPLICIT_FULL_GRID_COMPUTE_APPROVAL":
        raise RuntimeError("full-grid execution seal is not awaiting approval")
    if seal.get("preregistration_sha256") != sha256_file(PREREG):
        raise RuntimeError("full-grid seal/preregistration mismatch")
    source = seal.get("sources", {}).get(component)
    if not isinstance(source, dict):
        raise RuntimeError(f"execution seal lacks component binding: {component}")
    _validate_path_hash(source)
    for binding in seal.get("frozen_artifacts", []):
        _validate_path_hash(binding)
    source_binding = prereg.get("bindings", {}).get("source_bindings")
    if not isinstance(source_binding, dict):
        raise RuntimeError("preregistration lacks source-binding manifest")
    source_manifest = load_json(ROOT / source_binding["path"])
    validate_payload_hash(source_manifest, "source_bindings_payload_sha256")
    for binding in source_manifest.get("sources", []):
        _validate_path_hash(binding)
    units = load_json(UNITS)
    frames = load_json(FRAMES)
    processed_inputs = load_json(PROCESSED_INPUTS)
    schedule = load_json(SCHEDULE)
    validate_unit_manifest(units)
    validate_frame_manifest(frames, units)
    validate_processed_input_manifest(processed_inputs, units)
    validate_worker_schedule(schedule, units)
    if seal.get("unit_manifest_sha256") != sha256_file(UNITS):
        raise RuntimeError("execution seal/unit manifest mismatch")
    if seal.get("frame_manifest_sha256") != sha256_file(FRAMES):
        raise RuntimeError("execution seal/frame manifest mismatch")
    if seal.get("processed_input_manifest_sha256") != sha256_file(PROCESSED_INPUTS):
        raise RuntimeError("execution seal/processed-input manifest mismatch")
    if seal.get("worker_schedule_sha256") != sha256_file(SCHEDULE):
        raise RuntimeError("execution seal/worker schedule mismatch")
    return seal, prereg


def validate_review_bundle() -> dict[str, Any]:
    path = PACKAGE / "FULL_GRID_REVIEW_BUNDLE.json"
    bundle = load_json(path)
    validate_payload_hash(bundle, "review_bundle_payload_sha256")
    for binding in bundle.get("artifacts", []):
        _validate_path_hash(binding)
    if bundle.get("execution_seal_sha256") != sha256_file(SEAL):
        raise RuntimeError("review bundle/execution seal mismatch")
    return bundle
