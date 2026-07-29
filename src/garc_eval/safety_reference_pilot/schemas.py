from __future__ import annotations

import json
import re
from typing import Any


class ContractError(ValueError):
    """A model response violates the frozen semantic or structural contract."""


FAMILIES = {
    "lateral_conflict",
    "longitudinal_conflict",
    "crossing_conflict",
    "intersection_conflict",
    "oncoming_conflict",
    "collision_or_near_collision",
    "ego_behavior",
    "road_hazard",
    "visibility_or_control_hazard",
    "other",
}
FAMILY_TYPES = {
    "lateral_conflict": {"vehicle_cut_in", "unsafe_merge", "lane_intrusion", "close_lateral_approach"},
    "longitudinal_conflict": {"lead_vehicle_hard_braking", "rapid_closing", "stopped_object_ahead", "unsafe_following"},
    "crossing_conflict": {"pedestrian_crossing", "cyclist_crossing", "animal_crossing", "vehicle_crossing"},
    "intersection_conflict": {"turning_conflict", "failure_to_yield", "intersection_encroachment"},
    "oncoming_conflict": {"wrong_way_vehicle", "oncoming_path_intrusion"},
    "collision_or_near_collision": {"collision", "near_collision"},
    "ego_behavior": {"ego_lane_departure", "ego_unsafe_merge", "ego_tailgating", "ego_signal_violation"},
    "road_hazard": {"road_debris", "blocked_lane", "work_zone_conflict", "road_surface_hazard"},
    "visibility_or_control_hazard": {"severe_visibility_loss", "apparent_loss_of_control"},
    "other": {"other", "none"},
}
ACTORS = {
    "ego_vehicle", "motor_vehicle", "pedestrian", "cyclist", "animal",
    "road_object", "environment", "unknown",
}
BOUNDARIES = {
    "ok", "truncated_start", "truncated_end", "truncated_both", "uncertain",
}
CONFIDENCES = {"high", "medium", "low"}


def _strict_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("response must be non-empty text")
    text = raw.strip()
    if text.startswith("```") or text.endswith("```"):
        raise ContractError("markdown fences are not allowed")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ContractError("top-level value must be an object")
    return value


def _exact_keys(value: dict[str, Any], required: set[str], where: str) -> None:
    missing = required - set(value)
    extra = set(value) - required
    if missing or extra:
        raise ContractError(
            f"{where} key mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _enum(value: Any, allowed: set[str], where: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ContractError(f"{where} must be one of {sorted(allowed)}")
    return value


def _nonempty(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{where} must be a non-empty string")
    return value.strip()


def _frame(value: Any, frame_count: int, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{where} must be an integer")
    if value < 0 or value >= frame_count:
        raise ContractError(f"{where}={value} is outside [0, {frame_count - 1}]")
    return value


def _ordered_frames(item: dict[str, Any], frame_count: int, where: str) -> None:
    start = _frame(item["start_frame_index"], frame_count, f"{where}.start_frame_index")
    peak = _frame(item["peak_frame_index"], frame_count, f"{where}.peak_frame_index")
    end = _frame(item["end_frame_index"], frame_count, f"{where}.end_frame_index")
    if not start <= peak <= end:
        raise ContractError(f"{where} frames must satisfy start <= peak <= end")


def parse_stage_a(raw: str, frame_count: int) -> dict[str, Any]:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    value = _strict_object(raw)
    _exact_keys(value, {"window_status", "proposals", "ambiguous_proposals"}, "stage_a")
    _enum(value["window_status"], {"ok", "partially_observable", "unusable"}, "window_status")
    if not isinstance(value["proposals"], list) or not isinstance(value["ambiguous_proposals"], list):
        raise ContractError("proposal fields must be arrays")
    if value["window_status"] == "unusable" and value["proposals"]:
        raise ContractError("an unusable window cannot contain accepted proposals")

    seen: set[str] = set()
    proposal_keys = {
        "proposal_id", "event_family_hint", "primary_actor", "start_frame_index",
        "peak_frame_index", "end_frame_index", "boundary_status",
        "observable_transition", "confidence",
    }
    for index, item in enumerate(value["proposals"]):
        where = f"proposals[{index}]"
        if not isinstance(item, dict):
            raise ContractError(f"{where} must be an object")
        _exact_keys(item, proposal_keys, where)
        proposal_id = _nonempty(item["proposal_id"], f"{where}.proposal_id")
        if not re.fullmatch(r"P[1-9][0-9]*", proposal_id) or proposal_id in seen:
            raise ContractError(f"{where}.proposal_id must be unique P<n>")
        seen.add(proposal_id)
        _enum(item["event_family_hint"], FAMILIES, f"{where}.event_family_hint")
        _enum(item["primary_actor"], ACTORS, f"{where}.primary_actor")
        _ordered_frames(item, frame_count, where)
        boundary = _enum(item["boundary_status"], BOUNDARIES, f"{where}.boundary_status")
        _nonempty(item["observable_transition"], f"{where}.observable_transition")
        confidence = _enum(item["confidence"], CONFIDENCES, f"{where}.confidence")
        if boundary == "uncertain" and confidence == "high":
            raise ContractError(f"{where} cannot be high confidence with uncertain boundary")

    ambiguous_keys = {
        "proposal_id", "possible_event_family", "start_frame_index",
        "end_frame_index", "reason_ambiguous", "missing_evidence",
    }
    for index, item in enumerate(value["ambiguous_proposals"]):
        where = f"ambiguous_proposals[{index}]"
        if not isinstance(item, dict):
            raise ContractError(f"{where} must be an object")
        _exact_keys(item, ambiguous_keys, where)
        proposal_id = _nonempty(item["proposal_id"], f"{where}.proposal_id")
        if not re.fullmatch(r"A[1-9][0-9]*", proposal_id) or proposal_id in seen:
            raise ContractError(f"{where}.proposal_id must be unique A<n>")
        seen.add(proposal_id)
        _enum(item["possible_event_family"], FAMILIES, f"{where}.possible_event_family")
        start = _frame(item["start_frame_index"], frame_count, f"{where}.start_frame_index")
        end = _frame(item["end_frame_index"], frame_count, f"{where}.end_frame_index")
        if start > end:
            raise ContractError(f"{where} frames must satisfy start <= end")
        _nonempty(item["reason_ambiguous"], f"{where}.reason_ambiguous")
        _nonempty(item["missing_evidence"], f"{where}.missing_evidence")
    return value


def parse_stage_b(raw: str, frame_count: int, expected_proposal_id: str) -> dict[str, Any]:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    value = _strict_object(raw)
    keys = {
        "proposal_id", "is_safety_relevant", "is_hazard", "risk_level",
        "event_family", "event_type", "proposed_event_type", "primary_actor",
        "affected_actor", "start_frame_index", "peak_frame_index", "end_frame_index",
        "boundary_status", "observable_evidence", "plausible_consequence",
        "required_response", "alternative_explanation",
        "alternative_explanation_rejected", "confidence", "review_required",
    }
    _exact_keys(value, keys, "stage_b")
    if value["proposal_id"] != expected_proposal_id:
        raise ContractError("proposal_id does not match the requested proposal")
    for field in ["is_safety_relevant", "is_hazard", "alternative_explanation_rejected", "review_required"]:
        if not isinstance(value[field], bool):
            raise ContractError(f"{field} must be boolean")
    risk = _enum(value["risk_level"], {"L0", "L1", "L2", "L3"}, "risk_level")
    if value["is_safety_relevant"] != (risk != "L0"):
        raise ContractError("is_safety_relevant must be false exactly for L0")
    if value["is_hazard"] != (risk in {"L2", "L3"}):
        raise ContractError("is_hazard must be true exactly for L2/L3")
    family = _enum(value["event_family"], FAMILIES, "event_family")
    event_type = _nonempty(value["event_type"], "event_type")
    if event_type not in FAMILY_TYPES[family]:
        raise ContractError(f"event_type={event_type} is not valid for family={family}")
    _enum(value["primary_actor"], ACTORS, "primary_actor")
    _enum(value["affected_actor"], {"ego_vehicle", "another_road_user", "multiple", "unknown", "none"}, "affected_actor")
    boundary = _enum(value["boundary_status"], BOUNDARIES | {"not_applicable"}, "boundary_status")
    confidence = _enum(value["confidence"], CONFIDENCES, "confidence")
    _enum(value["required_response"], {"none", "attention", "slow", "brake", "steer", "stop", "yield", "multiple", "unknown"}, "required_response")
    if not isinstance(value["observable_evidence"], list) or not all(
        isinstance(item, str) and item.strip() for item in value["observable_evidence"]
    ):
        raise ContractError("observable_evidence must be an array of non-empty strings")
    _nonempty(value["plausible_consequence"], "plausible_consequence")
    if value["alternative_explanation"] is not None:
        _nonempty(value["alternative_explanation"], "alternative_explanation")

    if risk == "L0":
        if event_type != "none" or family != "other" or boundary != "not_applicable":
            raise ContractError("L0 must use family=other, event_type=none, boundary=not_applicable")
        if value["observable_evidence"]:
            raise ContractError("L0 must have an empty observable_evidence list")
    else:
        _ordered_frames(value, frame_count, "stage_b")
        if boundary == "not_applicable":
            raise ContractError("safety-relevant events require an applicable boundary status")

    proposed = value["proposed_event_type"]
    if event_type == "other":
        _nonempty(proposed, "proposed_event_type")
        if family != "other" or not value["review_required"]:
            raise ContractError("open-set events require family=other and review_required=true")
    elif proposed is not None:
        raise ContractError("proposed_event_type must be null unless event_type=other")
    if boundary == "uncertain" and confidence == "high":
        raise ContractError("uncertain boundary cannot have high confidence")
    if (
        risk != "L0"
        and confidence == "high"
        and value["alternative_explanation"] is not None
        and not value["alternative_explanation_rejected"]
    ):
        raise ContractError("high confidence requires the stated benign explanation to be rejected")
    return value


def parse_single_stage(raw: str, frame_count: int) -> dict[str, Any]:
    """Validate the one-call control arm against the same final-event semantics."""
    value = _strict_object(raw)
    _exact_keys(value, {"window_status", "events", "ambiguous_events"}, "single_stage")
    _enum(value["window_status"], {"ok", "partially_observable", "unusable"}, "window_status")
    if not isinstance(value["events"], list) or not isinstance(value["ambiguous_events"], list):
        raise ContractError("single-stage event fields must be arrays")
    if value["window_status"] == "unusable" and value["events"]:
        raise ContractError("an unusable window cannot contain accepted events")
    seen: set[str] = set()
    for index, event in enumerate(value["events"]):
        where = f"events[{index}]"
        if not isinstance(event, dict) or "event_id" not in event or "proposal_id" in event:
            raise ContractError(f"{where} must contain event_id and not proposal_id")
        event_id = _nonempty(event["event_id"], f"{where}.event_id")
        if not re.fullmatch(r"E[1-9][0-9]*", event_id) or event_id in seen:
            raise ContractError(f"{where}.event_id must be unique E<n>")
        seen.add(event_id)
        projected = dict(event)
        projected["proposal_id"] = projected.pop("event_id")
        parse_stage_b(json.dumps(projected), frame_count, event_id)
        if event["risk_level"] == "L0":
            raise ContractError(f"{where} cannot contain L0; absence is represented by no event")
    ambiguous_keys = {
        "event_id", "possible_event_family", "start_frame_index", "end_frame_index",
        "reason_ambiguous", "missing_evidence",
    }
    for index, event in enumerate(value["ambiguous_events"]):
        where = f"ambiguous_events[{index}]"
        if not isinstance(event, dict):
            raise ContractError(f"{where} must be an object")
        _exact_keys(event, ambiguous_keys, where)
        event_id = _nonempty(event["event_id"], f"{where}.event_id")
        if not re.fullmatch(r"A[1-9][0-9]*", event_id) or event_id in seen:
            raise ContractError(f"{where}.event_id must be unique A<n>")
        seen.add(event_id)
        _enum(event["possible_event_family"], FAMILIES, f"{where}.possible_event_family")
        start = _frame(event["start_frame_index"], frame_count, f"{where}.start_frame_index")
        end = _frame(event["end_frame_index"], frame_count, f"{where}.end_frame_index")
        if start > end:
            raise ContractError(f"{where} frames must satisfy start <= end")
        _nonempty(event["reason_ambiguous"], f"{where}.reason_ambiguous")
        _nonempty(event["missing_evidence"], f"{where}.missing_evidence")
    return value
