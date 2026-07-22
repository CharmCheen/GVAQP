from __future__ import annotations

import pytest

from garc_eval.mf_psvr.training_pool import (
    deterministic_split,
    frame_bounds,
    project_generic_label,
    unit_windows,
    verification_key,
)


def test_session_split_is_stable_and_label_independent() -> None:
    first = deterministic_split("nexar_collision_prediction", "train/positive/00822.mp4")
    second = deterministic_split("nexar_collision_prediction", "train/positive/00822.mp4")
    assert first == second
    assert first in {"model_train", "model_calibration", "pool_audit"}


def test_frozen_unitization_includes_overlapping_centered_tail() -> None:
    windows = unit_windows(20.25)
    assert [
        (row.unit_id, row.anchor_seconds, row.start_seconds, row.end_seconds)
        for row in windows
    ] == [
        (0, 5.0, 0.0, 10.0),
        (1, 15.0, 10.0, 20.0),
        (2, 20.25, 15.25, 20.25),
    ]


def test_frame_bounds_match_both_frozen_video_tails() -> None:
    v0_tail = unit_windows(3462.930499)[-1]
    assert (v0_tail.start_seconds, v0_tail.end_seconds) == (3457.930499, 3462.930499)
    assert frame_bounds(
        v0_tail.start_seconds,
        v0_tail.end_seconds,
        30.000005775562784,
        103886,
    ) == (103737, 103885)

    v1_tail = unit_windows(5665.535333)[-1]
    assert (v1_tail.start_seconds, v1_tail.end_seconds) == (5660.0, 5665.535333)
    assert frame_bounds(v1_tail.start_seconds, v1_tail.end_seconds, 30.0, 169962) == (
        169800,
        169961,
    )


@pytest.mark.parametrize(
    ("generic", "actor", "query", "expected"),
    [
        ("positive", "vehicle", "Q1", "positive"),
        ("positive", "vehicle", "Q2", "negative"),
        ("positive", "pedestrian", "Q1", "negative"),
        ("positive", "pedestrian", "Q2", "positive"),
        ("positive", "cyclist", "Q1", "positive"),
        ("positive", "cyclist", "Q2", "positive"),
        ("negative", "vehicle", "Q1", "negative"),
        ("abstain", "unknown", "Q2", "abstain"),
    ],
)
def test_frozen_query_projection(
    generic: str, actor: str, query: str, expected: str
) -> None:
    assert project_generic_label(generic, actor, query) == expected


def test_verification_key_excludes_track_witness() -> None:
    assert verification_key("nexar:00822", "Q1", 2) == ("nexar:00822", "Q1", 2)
    with pytest.raises(ValueError):
        verification_key("nexar:00822", "Q3", 2)
