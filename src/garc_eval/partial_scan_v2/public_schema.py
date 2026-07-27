from __future__ import annotations

import math
import re
from typing import Any

from .protocol import (
    CHOOSE_ACTION,
    INITIALIZE,
    INITIALIZED,
    POLICY_PROTOCOL_VERSION,
)


OPAQUE_RUN_RE = re.compile(r"^r_[0-9a-f]{32}$")
OPAQUE_VIDEO_RE = re.compile(r"^v_[0-9a-f]{16}$")
OPAQUE_UNIT_RE = re.compile(r"^u_[0-9a-f]{20}$")
OPAQUE_CANDIDATE_RE = re.compile(r"^c_[0-9a-f]{20}$")
HEX_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

FORBIDDEN_PUBLIC_KEY_FRAGMENTS = (
    "reference",
    "future",
    "path",
    "scan_output",
    "candidate_event_map",
    "oracle",
    "internal",
)
FORBIDDEN_PUBLIC_STRING_FRAGMENTS = (
    "/qiuyeqing/",
    "/benchmarks/",
    "reference_events",
    "candidate_event_map",
    "scan_outputs",
)


PUBLIC_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "PARTIAL_SCAN_BENCHMARK_PILOT_V2_PUBLIC_PROTOCOL",
    "additionalProperties": False,
    "messages": {
        "initialize": {
            "required": [
                "type",
                "protocol_version",
                "run_id",
                "video",
                "units",
                "budget_sec",
                "public_contract_hash",
            ],
            "additionalProperties": False,
        },
        "choose_action": {
            "required": ["type", "step_id", "state"],
            "additionalProperties": False,
        },
        "action_response": {
            "required": ["step_id", "unit_id"],
            "additionalProperties": False,
        },
    },
    "public_state": {
        "required": [
            "step_id",
            "public_protocol_version",
            "scanned_unit_ids",
            "current_unit_id",
            "remaining_budget_sec",
            "past_action_costs_sec",
            "geometric_coverage",
            "revealed_observations",
        ],
        "additionalProperties": False,
    },
}


class PublicSchemaError(ValueError):
    pass


def _exact_keys(value: dict[str, Any], keys: set[str], context: str) -> None:
    actual = set(value)
    if actual != keys:
        raise PublicSchemaError(f"{context}: field set mismatch")


def _finite_nonnegative(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PublicSchemaError(f"{context}: expected number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise PublicSchemaError(f"{context}: expected finite nonnegative number")
    return number


def _integer(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PublicSchemaError(f"{context}: expected nonnegative integer")
    return value


def validate_initialize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaError("initialize: expected object")
    keys = {
        "type",
        "protocol_version",
        "run_id",
        "video",
        "units",
        "budget_sec",
        "public_contract_hash",
    }
    _exact_keys(value, keys, "initialize")
    if value["type"] != INITIALIZE:
        raise PublicSchemaError("initialize: wrong type")
    if value["protocol_version"] != POLICY_PROTOCOL_VERSION:
        raise PublicSchemaError("initialize: protocol mismatch")
    if not OPAQUE_RUN_RE.fullmatch(str(value["run_id"])):
        raise PublicSchemaError("initialize: invalid run id")
    if not HEX_HASH_RE.fullmatch(str(value["public_contract_hash"])):
        raise PublicSchemaError("initialize: invalid contract hash")
    _finite_nonnegative(value["budget_sec"], "initialize budget")
    video = value["video"]
    if not isinstance(video, dict):
        raise PublicSchemaError("initialize video: expected object")
    _exact_keys(video, {"video_id", "duration_sec"}, "initialize video")
    if not OPAQUE_VIDEO_RE.fullmatch(str(video["video_id"])):
        raise PublicSchemaError("initialize: invalid video id")
    _finite_nonnegative(video["duration_sec"], "initialize duration")
    units = value["units"]
    if not isinstance(units, list) or not units:
        raise PublicSchemaError("initialize: units must be non-empty list")
    seen: set[str] = set()
    previous_end = -1.0
    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            raise PublicSchemaError("initialize unit: expected object")
        _exact_keys(unit, {"unit_id", "start_sec", "end_sec"}, "initialize unit")
        unit_id = str(unit["unit_id"])
        if not OPAQUE_UNIT_RE.fullmatch(unit_id) or unit_id in seen:
            raise PublicSchemaError("initialize: invalid or duplicate unit id")
        start = _finite_nonnegative(unit["start_sec"], "unit start")
        end = _finite_nonnegative(unit["end_sec"], "unit end")
        if end <= start or (index and start < previous_end - 1e-7):
            raise PublicSchemaError("initialize: invalid unit boundary order")
        seen.add(unit_id)
        previous_end = end
    assert_public_payload_clean(value)
    return value


def validate_public_state(value: Any, known_units: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaError("state: expected object")
    keys = {
        "step_id",
        "public_protocol_version",
        "scanned_unit_ids",
        "current_unit_id",
        "remaining_budget_sec",
        "past_action_costs_sec",
        "geometric_coverage",
        "revealed_observations",
    }
    _exact_keys(value, keys, "state")
    _integer(value["step_id"], "state step")
    if value["public_protocol_version"] != POLICY_PROTOCOL_VERSION:
        raise PublicSchemaError("state: protocol mismatch")
    scanned = value["scanned_unit_ids"]
    if not isinstance(scanned, list) or len(scanned) != len(set(scanned)):
        raise PublicSchemaError("state: scanned ids invalid")
    if not all(isinstance(item, str) and item in known_units for item in scanned):
        raise PublicSchemaError("state: unknown scanned id")
    current = value["current_unit_id"]
    if current is not None and (not isinstance(current, str) or current not in scanned):
        raise PublicSchemaError("state: current id invalid")
    _finite_nonnegative(value["remaining_budget_sec"], "state remaining budget")
    costs = value["past_action_costs_sec"]
    if not isinstance(costs, list):
        raise PublicSchemaError("state: costs invalid")
    for cost in costs:
        _finite_nonnegative(cost, "state past cost")
    if len(costs) != len(scanned):
        raise PublicSchemaError("state: cost/action cardinality mismatch")
    coverage = value["geometric_coverage"]
    if not isinstance(coverage, dict):
        raise PublicSchemaError("state: coverage invalid")
    _exact_keys(
        coverage,
        {"fraction", "covered_duration_sec"},
        "state coverage",
    )
    fraction = _finite_nonnegative(coverage["fraction"], "coverage fraction")
    if fraction > 1.0 + 1e-9:
        raise PublicSchemaError("state: coverage fraction exceeds one")
    _finite_nonnegative(coverage["covered_duration_sec"], "covered duration")
    observations = value["revealed_observations"]
    if not isinstance(observations, dict):
        raise PublicSchemaError("state: observations invalid")
    _exact_keys(
        observations,
        {"candidate_ids", "last_completed_unit_id", "result_class"},
        "state observations",
    )
    candidate_ids = observations["candidate_ids"]
    if not isinstance(candidate_ids, list) or len(candidate_ids) != len(set(candidate_ids)):
        raise PublicSchemaError("state: candidate ids invalid")
    if not all(
        isinstance(item, str) and OPAQUE_CANDIDATE_RE.fullmatch(item)
        for item in candidate_ids
    ):
        raise PublicSchemaError("state: candidate id format invalid")
    last = observations["last_completed_unit_id"]
    if last is not None and last not in scanned:
        raise PublicSchemaError("state: last completed id invalid")
    if observations["result_class"] not in {
        "INITIAL",
        "LOGICAL_REPLAY",
        "PHYSICAL_SCAN",
    }:
        raise PublicSchemaError("state: result class invalid")
    assert_public_payload_clean(value)
    return value


def validate_choose_action(value: Any, known_units: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaError("choose_action: expected object")
    _exact_keys(value, {"type", "step_id", "state"}, "choose_action")
    if value["type"] != CHOOSE_ACTION:
        raise PublicSchemaError("choose_action: wrong type")
    step = _integer(value["step_id"], "choose_action step")
    state = validate_public_state(value["state"], known_units)
    if state["step_id"] != step:
        raise PublicSchemaError("choose_action: step mismatch")
    return value


def validate_initialized(value: Any, expected_run_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaError("initialized: expected object")
    _exact_keys(value, {"type", "run_id", "protocol_version"}, "initialized")
    if (
        value["type"] != INITIALIZED
        or value["run_id"] != expected_run_id
        or value["protocol_version"] != POLICY_PROTOCOL_VERSION
    ):
        raise PublicSchemaError("initialized: mismatch")
    return value


def validate_action(
    value: Any,
    known_units: set[str],
    expected_step_id: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaError("action: expected object")
    _exact_keys(value, {"step_id", "unit_id"}, "action response")
    if _integer(value["step_id"], "action response step") != expected_step_id:
        raise PublicSchemaError("action response: stale or future step")
    if not isinstance(value["unit_id"], str) or value["unit_id"] not in known_units:
        raise PublicSchemaError("action response: unknown unit")
    assert_public_payload_clean(value)
    return value


def assert_public_payload_clean(value: Any) -> None:
    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                lowered = str(key).lower()
                if any(fragment in lowered for fragment in FORBIDDEN_PUBLIC_KEY_FRAGMENTS):
                    raise PublicSchemaError("public payload contains forbidden key")
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)
        elif isinstance(item, str):
            lowered = item.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_PUBLIC_STRING_FRAGMENTS):
                raise PublicSchemaError("public payload contains forbidden string")

    walk(value)
