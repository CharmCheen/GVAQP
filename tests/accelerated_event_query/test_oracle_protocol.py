import json

import pytest

from garc_eval.accelerated_event_query.oracle_protocol import (
    exact_sample_indices,
)
from garc_eval.accelerated_event_query.oracle_response_protocol import parse_response_strict


def response(**overrides) -> str:
    value = {
        "label": "relevant",
        "event_start_sec": 1.0,
        "event_end_sec": 2.0,
        "required_response": ["brake"],
        "cause": "lead vehicle stops",
        "confidence": "high",
        "evidence": "visible closing distance",
        "unknown_reason": None,
    }
    value.update(overrides)
    return json.dumps(value)


def test_exact_endpoint_inclusive_frame_grids():
    at_two = exact_sample_indices(100.0, 110.0, 30.0, 2.0)
    at_four = exact_sample_indices(100.0, 110.0, 30.0, 4.0)
    assert len(at_two) == 21
    assert len(at_four) == 41
    assert (at_two[0]["requested_index"], at_two[-1]["requested_index"]) == (3000, 3300)
    assert (at_four[0]["requested_index"], at_four[-1]["requested_index"]) == (3000, 3300)
    assert {right["requested_index"] - left["requested_index"] for left, right in zip(at_four, at_four[1:])} == {7, 8}
    assert [row["target_relative_seconds"] for row in at_four][::4] == list(range(11))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("prefix " + response(), "parse_error:JSONDecodeError"),
        (response(label="not_relevant", event_start_sec=1.0, event_end_sec=2.0, required_response=[], cause=None), "not_relevant_has_boundary"),
        (response(label="not_relevant", event_start_sec=None, event_end_sec=None, required_response=["brake"], cause=None), "not_relevant_has_response"),
        (response(label="unknown", event_start_sec=None, event_end_sec=None, required_response=[], cause=None), "unknown_missing_reason"),
        (response(cause=7), "invalid_cause"),
        (response(evidence=["visible"]), "invalid_evidence"),
        (response(required_response=["brake", "brake"]), "duplicate_required_response"),
        (response(event_start_sec=True), "invalid_relevant_boundary"),
    ],
)
def test_strict_parser_rejects_contract_inconsistent_outputs(raw, expected):
    _, status = parse_response_strict(raw)
    assert status == expected


def test_strict_parser_accepts_all_three_well_formed_labels():
    assert parse_response_strict(response())[1] == "ok"
    assert parse_response_strict(response(
        label="not_relevant",
        event_start_sec=None,
        event_end_sec=None,
        required_response=[],
        cause=None,
    ))[1] == "ok"
    assert parse_response_strict(response(
        label="unknown",
        event_start_sec=None,
        event_end_sec=None,
        required_response=[],
        cause="occluded pedestrian",
        unknown_reason="occlusion prevents path assessment",
    ))[1] == "ok"


def test_strict_parser_rejects_duplicate_json_keys():
    duplicate = response().replace('"label": "relevant"', '"label": "relevant", "label": "not_relevant"')
    _, status = parse_response_strict(duplicate)
    assert status == "parse_error:ValueError"
