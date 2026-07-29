import json

import pytest

from garc_eval.safety_reference_pilot.schemas import (
    ContractError,
    parse_single_stage,
    parse_stage_a,
    parse_stage_b,
)


def stage_a(**changes):
    value = {
        "window_status": "ok",
        "proposals": [{
            "proposal_id": "P1",
            "event_family_hint": "lateral_conflict",
            "primary_actor": "motor_vehicle",
            "start_frame_index": 3,
            "peak_frame_index": 5,
            "end_frame_index": 8,
            "boundary_status": "ok",
            "observable_transition": "vehicle crosses a visible lane boundary",
            "confidence": "medium",
        }],
        "ambiguous_proposals": [],
    }
    value.update(changes)
    return json.dumps(value)


def stage_b(**changes):
    value = {
        "proposal_id": "P1",
        "is_safety_relevant": True,
        "is_hazard": True,
        "risk_level": "L2",
        "event_family": "lateral_conflict",
        "event_type": "vehicle_cut_in",
        "proposed_event_type": None,
        "primary_actor": "motor_vehicle",
        "affected_actor": "ego_vehicle",
        "start_frame_index": 3,
        "peak_frame_index": 5,
        "end_frame_index": 8,
        "boundary_status": "ok",
        "observable_evidence": ["vehicle crosses the lane boundary"],
        "plausible_consequence": "the available gap decreases",
        "required_response": "brake",
        "alternative_explanation": "normal merge",
        "alternative_explanation_rejected": True,
        "confidence": "high",
        "review_required": False,
    }
    value.update(changes)
    return json.dumps(value)


def test_stage_a_accepts_valid_proposal():
    parsed = parse_stage_a(stage_a(), frame_count=60)
    assert parsed["proposals"][0]["proposal_id"] == "P1"


@pytest.mark.parametrize(
    "raw",
    [
        lambda: "```json\n" + stage_a() + "\n```",
        lambda: stage_a(extra="forbidden"),
        lambda: stage_a(proposals=[{
            "proposal_id": "P1", "event_family_hint": "lateral_conflict",
            "primary_actor": "motor_vehicle", "start_frame_index": 3,
            "peak_frame_index": 61, "end_frame_index": 8, "boundary_status": "ok",
            "observable_transition": "motion", "confidence": "medium",
        }]),
    ],
)
def test_stage_a_rejects_non_contract_outputs(raw):
    with pytest.raises(ContractError):
        parse_stage_a(raw(), frame_count=60)


def test_stage_a_uncertain_boundary_cannot_be_high_confidence():
    item = json.loads(stage_a())["proposals"][0]
    item.update(boundary_status="uncertain", confidence="high")
    with pytest.raises(ContractError):
        parse_stage_a(stage_a(proposals=[item]), frame_count=60)


def test_stage_b_accepts_valid_hazard():
    parsed = parse_stage_b(stage_b(), frame_count=60, expected_proposal_id="P1")
    assert parsed["is_hazard"] is True


def test_stage_b_hazard_must_match_risk():
    with pytest.raises(ContractError):
        parse_stage_b(stage_b(is_hazard=False), 60, "P1")


def test_stage_b_rejects_family_type_mismatch():
    with pytest.raises(ContractError):
        parse_stage_b(stage_b(event_family="crossing_conflict"), 60, "P1")


def test_stage_b_open_set_requires_review_and_name():
    with pytest.raises(ContractError):
        parse_stage_b(
            stage_b(event_family="other", event_type="other", proposed_event_type=None),
            60,
            "P1",
        )
    parsed = parse_stage_b(
        stage_b(
            event_family="other", event_type="other",
            proposed_event_type="animal_falls_from_vehicle", review_required=True,
        ),
        60,
        "P1",
    )
    assert parsed["proposed_event_type"] == "animal_falls_from_vehicle"


def test_stage_b_l0_contract():
    parsed = parse_stage_b(
        stage_b(
            is_safety_relevant=False, is_hazard=False, risk_level="L0",
            event_family="other", event_type="none", primary_actor="unknown",
            affected_actor="none", boundary_status="not_applicable",
            observable_evidence=[], plausible_consequence="none",
            required_response="none", alternative_explanation="ordinary traffic",
            alternative_explanation_rejected=False, confidence="high",
        ),
        60,
        "P1",
    )
    assert parsed["risk_level"] == "L0"


def test_single_stage_reuses_final_event_semantics():
    event = json.loads(stage_b())
    event["event_id"] = event.pop("proposal_id")
    event["event_id"] = "E1"
    raw = json.dumps({"window_status": "ok", "events": [event], "ambiguous_events": []})
    parsed = parse_single_stage(raw, 60)
    assert parsed["events"][0]["event_id"] == "E1"


def test_single_stage_rejects_stage_b_semantic_error():
    event = json.loads(stage_b(is_hazard=False))
    event["event_id"] = "E1"
    event.pop("proposal_id")
    raw = json.dumps({"window_status": "ok", "events": [event], "ambiguous_events": []})
    with pytest.raises(ContractError):
        parse_single_stage(raw, 60)


def test_single_stage_represents_no_event_with_empty_list_not_l0_object():
    event = json.loads(stage_b(
        is_safety_relevant=False, is_hazard=False, risk_level="L0",
        event_family="other", event_type="none", affected_actor="none",
        boundary_status="not_applicable", observable_evidence=[],
        plausible_consequence="none", required_response="none",
    ))
    event["event_id"] = "E1"
    event.pop("proposal_id")
    with pytest.raises(ContractError):
        parse_single_stage(
            json.dumps({"window_status": "ok", "events": [event], "ambiguous_events": []}),
            60,
        )
    parsed = parse_single_stage(
        json.dumps({"window_status": "ok", "events": [], "ambiguous_events": []}),
        60,
    )
    assert parsed["events"] == []
