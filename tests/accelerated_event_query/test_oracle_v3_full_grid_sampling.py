import math

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_manifest import (
    full_grid_sample_indices,
    resolve_targets_to_available_frames,
)


def test_normal_full_grid_unit_retains_endpoint_inclusive_21_frames():
    kind, rows = full_grid_sample_indices(100.0, 110.0, 30.0, 2.0)
    assert kind == "normal"
    assert len(rows) == 21
    assert rows[0]["requested_index"] == 3000
    assert rows[-1]["requested_index"] == 3300
    assert rows[-1]["target_absolute_seconds"] == 110.0


@pytest.mark.parametrize(
    ("start", "end", "count", "last_relative", "last_index"),
    [
        (5660.0, 5665.535333, 12, 5.5, 169965),
        (5600.0, 5600.566, 2, 0.5, 168015),
        (3460.0, 3462.930499, 6, 2.5, 103875),
    ],
)
def test_truncated_final_units_use_only_source_anchored_targets(
    start, end, count, last_relative, last_index
):
    kind, rows = full_grid_sample_indices(start, end, 30.0, 2.0)
    assert kind == "truncated_final"
    assert len(rows) == count
    assert rows[-1]["target_relative_seconds"] == last_relative
    assert rows[-1]["requested_index"] == last_index
    assert rows[-1]["target_absolute_seconds"] <= end
    assert not math.isclose(rows[-1]["target_absolute_seconds"], end)
    assert len({row["requested_index"] for row in rows}) == count


def test_nonintegral_duration_is_not_legal_for_a_full_length_unit():
    with pytest.raises(ValueError, match="only a shorter final unit"):
        full_grid_sample_indices(0.0, 10.1, 30.0, 2.0)


def test_dali_last_target_resolves_to_unique_nearest_available_stream_frame():
    _, targets = full_grid_sample_indices(5660.0, 5665.535333, 30.0, 2.0)
    rows = resolve_targets_to_available_frames(targets, available_frame_count=169962)
    assert len(rows) == 12
    assert rows[-1]["ideal_requested_index"] == 169965
    assert rows[-1]["requested_index"] == 169961
    assert rows[-1]["source_boundary_resolution"] == "nearest_available_final_video_frame"
    assert len({row["requested_index"] for row in rows}) == 12


def test_boundary_resolution_refuses_repeated_padding_frame():
    _, targets = full_grid_sample_indices(0.0, 0.566, 30.0, 2.0)
    with pytest.raises(RuntimeError, match="repeat"):
        resolve_targets_to_available_frames(targets, available_frame_count=1)
