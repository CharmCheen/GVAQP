"""Fail-closed validation of the frozen V3 full-grid preregistration package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .oracle_v3_full_grid_manifest import (
    EXECUTION_DIRECTORY_NAME,
    EXPECTED_UNIT_COUNT,
    validate_frame_manifest,
    validate_processed_input_manifest,
    validate_unit_manifest,
    validate_worker_schedule,
)
from .oracle_v3_manifest import load_json, sha256_file, validate_payload_hash


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
PACKAGE = BASE / "full_grid_preregistration_staged_v4_evidence_complete_reservation"
EXECUTION = BASE / EXECUTION_DIRECTORY_NAME
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


def _validate_prior_failure_revision_bindings(prereg: dict[str, Any]) -> None:
    """Reauthenticate every nested failed-run binding at launch time."""

    bindings = prereg.get("bindings", {})
    prior_binding = bindings.get("prior_failed_execution_evidence")
    derivation_binding = bindings.get("call_reservation_derivation")
    if not isinstance(prior_binding, dict) or not isinstance(derivation_binding, dict):
        raise RuntimeError("preregistration lacks prior-failure revision bindings")
    prior = load_json(ROOT / prior_binding["path"])
    validate_payload_hash(prior, "prior_failure_evidence_payload_sha256")
    if not all((
        prior.get("status")
        == "AUTHENTICATED_INCOMPLETE_PRIOR_RUN_REVISION_EVIDENCE_ONLY",
        prior.get("completed_call_count") == 473,
        prior.get("attempted_call_count") == 476,
        prior.get("uncertain_terminal_unit_ids")
        == ["DALI_u0468", "HANGZHOU_u0003", "WUHAN_u0002"],
        prior.get("formal_reference_artifacts_present") is False,
        prior.get("reuse_in_new_execution")
        == "FORBIDDEN; fresh execution starts at unit 0",
        len(prior.get("bindings", [])) == 14,
        len(prior.get("raw_output_bindings", [])) == 473,
    )):
        raise RuntimeError("prior failed execution evidence semantics changed")
    for binding in prior.get("bindings", []) + prior.get(
        "raw_output_bindings", []
    ):
        _validate_path_hash(binding)
    nested_candidates = [
        binding for binding in prior.get("bindings", [])
        if Path(binding.get("path", "")).name
        == "FULL_GRID_PRIOR_FAILURE_EVIDENCE.json"
    ]
    if len(nested_candidates) != 1:
        raise RuntimeError("immediate prior evidence lacks one nested failure record")
    nested = load_json(ROOT / nested_candidates[0]["path"])
    validate_payload_hash(nested, "prior_failure_evidence_payload_sha256")
    if not all((
        nested.get("status")
        == "AUTHENTICATED_INCOMPLETE_PRIOR_RUN_REVISION_EVIDENCE_ONLY",
        nested.get("completed_call_count") == 136,
        nested.get("attempted_call_count") == 137,
        nested.get("uncertain_terminal_unit_id") == "DALI_u0136",
        nested.get("formal_reference_artifacts_present") is False,
        len(nested.get("bindings", [])) == 11,
        len(nested.get("raw_output_bindings", [])) == 136,
    )):
        raise RuntimeError("nested first-failure evidence semantics changed")
    for binding in nested.get("bindings", []) + nested.get(
        "raw_output_bindings", []
    ):
        _validate_path_hash(binding)
    derivation = load_json(ROOT / derivation_binding["path"])
    validate_payload_hash(
        derivation, "call_reservation_derivation_payload_sha256"
    )
    if not all((
        derivation.get("status")
        == "FROZEN_PROSPECTIVE_REVISION_BEFORE_FRESH_EXECUTION",
        derivation.get("completed_observation_count") == 473,
        derivation.get("concurrent_activation_observation_count") == 7,
        len(derivation.get("incomplete_concurrent_preinference_observations", []))
        == 3,
        derivation.get("incomplete_concurrent_preinference_observations")
        == [
            {
                "unit_id": "DALI_u0468",
                "call_reserved_to_inference_started_seconds": 3.567687389,
            },
            {
                "unit_id": "HANGZHOU_u0003",
                "call_reserved_to_inference_started_seconds": 1.580861416,
            },
            {
                "unit_id": "WUHAN_u0002",
                "call_reserved_to_inference_started_seconds": 3.48622021,
            },
        ],
        derivation.get(
            "incomplete_maximum_call_reserved_to_inference_started_seconds", 0.0
        ) == 3.567687389,
        derivation.get("concurrent_token_cap_total_upper_seconds", 0.0)
        >= 62.08846018493341,
        derivation.get("frozen_generation_max_new_tokens") == 192,
        derivation.get("revised_per_call_hard_reservation_wall_seconds") == 66.0,
        derivation.get("fresh_formal_execution_envelope_a100_gpu_hours") == 56.0,
        derivation.get("full_grid_all_operations_hard_bound_a100_gpu_hours", 1e9)
        == 55.778888888888886,
        derivation.get("maximum_idle_residency_gap_count") == 1481,
        derivation.get("maximum_idle_wall_seconds_per_gap") == 2.0,
        derivation.get("prior_plus_fresh_formal_envelope_a100_gpu_hours", 1e9)
        < 64.0,
        derivation.get("absolute_safety_margin_seconds", -1.0) > 0.0,
        derivation.get("prior_failure_evidence_payload_sha256")
        == prior.get("prior_failure_evidence_payload_sha256"),
    )):
        raise RuntimeError("call-reservation revision derivation mismatch")


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
    _validate_prior_failure_revision_bindings(prereg)
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
