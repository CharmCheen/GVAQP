from __future__ import annotations

from pathlib import Path

import pytest

from garc_eval.event_enumerate_v2.temporal_contract import (
    IntervalRequest,
    VideoInfo,
    build_frame_selection,
    owner_accepts,
    processor_patch_timestamps,
)


CORPUS = Path(__file__).resolve().parent / "metadata_videos"


@pytest.mark.parametrize(
    "file_name,interval_id,start,end,expected_count",
    [
        ("timeline_60s_10fps.mp4", "len10", 0.0, 10.0, 21),
        ("timeline_60s_10fps.mp4", "len50", 5.0, 55.0, 101),
        ("timeline_60s_10fps.mp4", "len55", 0.0, 55.0, 111),
        ("timeline_60s_10fps.mp4", "len60", 0.0, 60.0, 121),
        ("timeline_60s_10fps.mp4", "offset", 12.3, 22.3, 21),
        ("timeline_73p4s_10fps.mp4", "offset60", 10.0, 70.0, 121),
        ("timeline_73p4s_10fps.mp4", "partial", 70.0, 73.4, 7),
        ("timeline_73p4s_10fps.mp4", "odd", 1.0, 4.0, 7),
        ("timeline_10s_12fps.mp4", "fps12", 0.0, 10.0, 21),
    ],
)
def test_interval_boundaries_and_variable_frame_counts(
    file_name, interval_id, start, end, expected_count
):
    video = VideoInfo.probe(CORPUS / file_name)
    selection = build_frame_selection(
        video, IntervalRequest(interval_id, start, end, start, end)
    )
    assert selection.decoded_frame_count == expected_count
    assert selection.actual_start <= start + 1.0 / video.fps
    assert selection.actual_end <= min(end, (video.total_frames - 1) / video.fps) + 1e-12
    assert selection.actual_end >= min(end, (video.total_frames - 1) / video.fps) - 0.5 - 1e-12
    patches = processor_patch_timestamps(
        selection.relative_source_indices, selection.source_fps
    )
    assert patches[-1] == pytest.approx(selection.relative_timestamps[-1])


def test_half_open_ownership_and_closed_final_boundary():
    assert owner_accepts(49.0, 51.0, 0.0, 50.0, 100.0) is False
    assert owner_accepts(49.0, 50.9, 0.0, 50.0, 100.0) is True
    assert owner_accepts(99.9, 100.0, 50.0, 100.0, 100.0) is True
    assert owner_accepts(49.5, 50.5, 0.0, 50.0, 100.0) is False
    assert owner_accepts(49.5, 50.5, 50.0, 100.0, 100.0) is True
