from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from garc_eval.event_enumerate_v2.temporal_contract import (
    ContractError,
    IntervalRequest,
    VideoInfo,
    build_frame_selection,
    map_event_response,
    parse_event_enumeration,
    reconcile_owned_fragments,
)


CORPUS = Path(__file__).resolve().parent / "metadata_videos"


def _response(start: float = 1.5, end: float = 2.5) -> str:
    return json.dumps(
        {
            "clip_status": "ok",
            "events": [
                {
                    "event_start": start,
                    "event_end": end,
                    "event_type": "enter_ego_path",
                    "involved_object": "vehicle",
                    "object_identity": "synthetic schema vehicle",
                    "ego_relevant": True,
                    "boundary_status": "ok",
                    "complete_event_visible": True,
                    "confidence": "high",
                    "evidence": "parser-only synthetic response",
                }
            ],
            "abstain_reason": None,
        }
    )


def test_nonzero_offset_maps_from_actual_first_decoded_timestamp():
    video = VideoInfo.probe(CORPUS / "timeline_60s_10fps.mp4")
    selection = build_frame_selection(
        video, IntervalRequest("offset", 12.3, 22.3, 12.3, 22.3)
    )
    parsed = parse_event_enumeration(_response(), selection.prompt_duration_seconds)
    rows = map_event_response(parsed, selection, video.duration_seconds)
    assert len(rows) == 1
    assert rows[0]["start_time"] == pytest.approx(selection.actual_start + 1.5)
    assert rows[0]["end_time"] == pytest.approx(selection.actual_start + 2.5)
    assert rows[0]["owned"] is True


def test_parser_is_deterministic_and_rejects_repairs():
    text = "prefix\n" + _response() + "\nsuffix"
    first = parse_event_enumeration(text, 10.0)
    for _ in range(10):
        assert parse_event_enumeration(text, 10.0) == first
    with pytest.raises(ContractError):
        parse_event_enumeration(_response(9.5, 10.2), 10.0)
    invalid = json.loads(_response())
    invalid["events"][0]["event_type"] = "collision"
    with pytest.raises(ContractError):
        parse_event_enumeration(json.dumps(invalid), 10.0)


def test_reconciliation_is_invariant_to_row_order():
    base = [
        {
            "source_interval_id": "b",
            "start_time": 3.0,
            "end_time": 4.0,
            "involved_object": "vehicle",
            "object_identity": "same",
            "owned": True,
        },
        {
            "source_interval_id": "a",
            "start_time": 3.0,
            "end_time": 4.0,
            "involved_object": "vehicle",
            "object_identity": "same",
            "owned": True,
        },
        {
            "source_interval_id": "c",
            "start_time": 7.0,
            "end_time": 8.0,
            "involved_object": "pedestrian",
            "object_identity": "different",
            "owned": True,
        },
    ]
    expected = reconcile_owned_fragments(base)
    assert [row["source_interval_id"] for row in expected] == ["a", "c"]
    for permutation in itertools.permutations(base):
        assert reconcile_owned_fragments(permutation) == expected


def test_inference_modules_have_no_reference_or_label_access():
    package = Path(__file__).resolve().parents[4] / "src/garc_eval/event_enumerate_v2"
    inference_files = [package / "temporal_contract.py", package / "processor_adapter.py"]
    forbidden = ["event_reference.csv", "HELDOUT_REFERENCE", "reference_count", "stratum_label"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in inference_files)
    for token in forbidden:
        assert token not in text
