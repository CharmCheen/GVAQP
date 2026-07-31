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
PACKAGE = BASE / "full_grid_preregistration_staged_v6_split_exit_lease"
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
    """Reauthenticate the V5 -> V2 -> V1 failed-run evidence chain."""

    bindings = prereg.get("bindings", {})
    prior_binding = bindings.get("prior_failed_execution_evidence")
    derivation_binding = bindings.get("call_reservation_derivation")
    if not isinstance(prior_binding, dict) or not isinstance(derivation_binding, dict):
        raise RuntimeError("preregistration lacks prior-failure revision bindings")
    prior = load_json(ROOT / prior_binding["path"])
    validate_payload_hash(prior, "prior_failure_evidence_payload_sha256")
    def validate_failure(
        evidence: dict[str, Any],
        *,
        completed: int,
        attempted: int,
        terminal_field: str,
        terminal_value: Any,
        binding_count: int,
        nested_count: int,
    ) -> dict[str, Any] | None:
        if not all((
            evidence.get("status")
            == "AUTHENTICATED_INCOMPLETE_PRIOR_RUN_REVISION_EVIDENCE_ONLY",
            evidence.get("completed_call_count") == completed,
            evidence.get("attempted_call_count") == attempted,
            evidence.get(terminal_field) == terminal_value,
            evidence.get("formal_reference_artifacts_present") is False,
            len(evidence.get("bindings", [])) == binding_count,
            len(evidence.get("raw_output_bindings", [])) == completed,
        )):
            raise RuntimeError("prior failed execution evidence semantics changed")
        if evidence.get("reuse_in_new_execution") is not None and (
            evidence.get("reuse_in_new_execution")
            != "FORBIDDEN; fresh execution starts at unit 0"
        ):
            raise RuntimeError("prior failed label-reuse boundary changed")
        for binding in evidence.get("bindings", []) + evidence.get(
            "raw_output_bindings", []
        ):
            _validate_path_hash(binding)
        candidates = [
            binding for binding in evidence.get("bindings", [])
            if Path(binding.get("path", "")).name
            == "FULL_GRID_PRIOR_FAILURE_EVIDENCE.json"
        ]
        if len(candidates) != nested_count:
            raise RuntimeError("prior evidence nested-chain cardinality changed")
        if not candidates:
            return None
        nested_evidence = load_json(ROOT / candidates[0]["path"])
        validate_payload_hash(
            nested_evidence, "prior_failure_evidence_payload_sha256"
        )
        return nested_evidence

    v2 = validate_failure(
        prior,
        completed=1084,
        attempted=1086,
        terminal_field="uncertain_terminal_unit_ids",
        terminal_value=["DALI_u0351", "HANGZHOU_u0386"],
        binding_count=14,
        nested_count=1,
    )
    if not all((
        prior.get("prior_execution_seal_sha256")
        == "8f1884ac84609aab86e726c5c2caf2c4c2739329fed89f7f0db8e5af1b9ac184",
        prior.get("stop_trigger") == "cost_envelope_exceeded",
        prior.get("stop_detail")
        == "stop_intent:loaded_worker_idle:V3_FULL_GRID_WUHAN:elapsed=2.073427:limit=2.000000",
        prior.get("model_load_count") == 3,
        prior.get("strict_parse_completed_raw_count") == 1084,
        prior.get("immediate_prior_conservative_usage_upper_bound_a100_gpu_hours")
        == 12.38081599596055,
        prior.get("conservative_usage_upper_bound_a100_gpu_hours")
        == 19.077998283059436,
        prior.get("reuse_in_new_execution")
        == "FORBIDDEN; fresh execution starts at unit 0",
    )):
        raise RuntimeError("immediate V5 failure identity/accounting changed")
    if v2 is None:
        raise RuntimeError("V5 evidence did not bind V2 evidence")
    v1 = validate_failure(
        v2,
        completed=473,
        attempted=476,
        terminal_field="uncertain_terminal_unit_ids",
        terminal_value=["DALI_u0468", "HANGZHOU_u0003", "WUHAN_u0002"],
        binding_count=14,
        nested_count=1,
    )
    if v1 is None:
        raise RuntimeError("V2 evidence did not bind V1 evidence")
    validate_failure(
        v1,
        completed=136,
        attempted=137,
        terminal_field="uncertain_terminal_unit_id",
        terminal_value="DALI_u0136",
        binding_count=11,
        nested_count=0,
    )
    derivation = load_json(ROOT / derivation_binding["path"])
    validate_payload_hash(
        derivation, "call_reservation_derivation_payload_sha256"
    )
    if not all((
        derivation.get("status")
        == "FROZEN_PROSPECTIVE_REVISION_BEFORE_FRESH_EXECUTION",
        derivation.get("completed_observation_count") == 1084,
        derivation.get("concurrent_activation_observation_count") == 1084,
        len(derivation.get("incomplete_concurrent_preinference_observations", []))
        == 2,
        derivation.get("incomplete_concurrent_preinference_observations")
        == [
            {
                "unit_id": "DALI_u0351",
                "call_reserved_to_inference_started_seconds": 1.770811581,
            },
            {
                "unit_id": "HANGZHOU_u0386",
                "call_reserved_to_inference_started_seconds": 0.738602882,
            },
        ],
        derivation.get(
            "incomplete_maximum_call_reserved_to_inference_started_seconds", 0.0
        ) == 1.770811581,
        derivation.get("concurrent_token_cap_total_upper_seconds", 0.0)
        == 42.57284809026531,
        derivation.get(
            "maximum_observed_post_inference_pre_persistence_seconds", 0.0
        ) == 0.17407700266037662,
        derivation.get("maximum_observed_post_persistence_coordinator_seconds")
        == 0.09615138588443628,
        derivation.get("governing_evidence_based_floor_seconds")
        == 42.57284809026531,
        derivation.get("absolute_safety_margin_seconds")
        == 9.42715190973469,
        derivation.get("atomic_loaded_worker_idle_lease_wall_seconds") == 2.0,
        derivation.get("atomic_loaded_worker_process_exit_lease_wall_seconds")
        == 8.0,
        derivation.get("frozen_generation_max_new_tokens") == 192,
        derivation.get("revised_per_call_hard_reservation_wall_seconds") == 52.0,
        derivation.get("fresh_formal_execution_envelope_a100_gpu_hours") == 44.4,
        derivation.get("full_grid_all_operations_hard_bound_a100_gpu_hours", 1e9)
        == 44.31666666666667,
        derivation.get("maximum_ordinary_idle_residency_gap_count") == 1478,
        derivation.get("maximum_process_exit_residency_gap_count") == 3,
        derivation.get("maximum_ordinary_idle_wall_seconds_per_gap") == 2.0,
        derivation.get("maximum_process_exit_wall_seconds_per_gap") == 8.0,
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
