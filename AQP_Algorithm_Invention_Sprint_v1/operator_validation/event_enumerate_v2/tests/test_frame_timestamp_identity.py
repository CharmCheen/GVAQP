from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from garc_eval.event_enumerate_v2.temporal_contract import (
    IntervalRequest,
    VideoInfo,
    build_frame_selection,
    decode_frame_selection,
)


CORPUS = Path(__file__).resolve().parent / "metadata_videos"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_barcode(frame_rgb: np.ndarray, barcode: dict) -> int:
    result = 0
    for bit in range(int(barcode["bits"])):
        x = int(barcode["x"]) + bit * int(barcode["step"])
        y = int(barcode["y"])
        size = int(barcode["square_size"])
        patch = frame_rgb[y : y + size, x : x + size]
        if float(patch.mean()) >= float(barcode["decode_threshold"]):
            result |= 1 << bit
    return result


def _requests(video_spec: dict):
    for interval in video_spec["intervals"]:
        yield IntervalRequest(
            interval_id=interval["id"],
            input_start=float(interval["start"]),
            input_end=float(interval["end"]),
            core_start=float(interval["start"]),
            core_end=float(interval["end"]),
        )


def test_corpus_hashes_and_container_metadata(corpus_manifest):
    assert corpus_manifest["semantic_event_labels_present"] is False
    for spec in corpus_manifest["videos"]:
        path = CORPUS / spec["file"]
        assert _sha256(path) == spec["sha256"]
        video = VideoInfo.probe(path)
        assert video.total_frames == int(spec["total_frames"])
        assert abs(video.fps - float(spec["fps"])) <= 1e-9
        assert video.width == int(spec["width"])
        assert video.height == int(spec["height"])


def test_every_decoded_frame_has_the_requested_identity_and_time(corpus_manifest):
    barcode = corpus_manifest["barcode"]
    for spec in corpus_manifest["videos"]:
        video = VideoInfo.probe(CORPUS / spec["file"])
        for request in _requests(spec):
            selection = build_frame_selection(video, request)
            decoded = decode_frame_selection(selection)
            assert decoded.frames_rgb.shape[0] == selection.decoded_frame_count
            for frame, identity, expected_index, expected_time in zip(
                decoded.frames_rgb,
                decoded.identities,
                selection.frame_indices,
                selection.frame_timestamps,
            ):
                assert identity["frame_index"] == expected_index
                assert abs(identity["timestamp_seconds"] - expected_time) <= 1e-12
                assert _decode_barcode(frame, barcode) == expected_index


def test_beginning_middle_end_markers_are_in_the_nominal_60_second_input(
    corpus_manifest,
):
    spec = next(
        row for row in corpus_manifest["videos"] if row["file"] == "timeline_60s_10fps.mp4"
    )
    video = VideoInfo.probe(CORPUS / spec["file"])
    request = IntervalRequest("markers", 0.0, 60.0, 0.0, 60.0)
    selection = build_frame_selection(video, request)
    decoded = decode_frame_selection(selection)
    by_index = {
        identity["frame_index"]: frame
        for identity, frame in zip(decoded.identities, decoded.frames_rgb)
    }
    for marker_index in spec["marker_frame_indices"].values():
        assert int(marker_index) in by_index
    # Marker rectangles remain visibly color-dominant after MP4 compression.
    begin = by_index[int(spec["marker_frame_indices"]["begin"])][85:125, 30:225]
    middle = by_index[int(spec["marker_frame_indices"]["middle"])][85:125, 30:225]
    end = by_index[int(spec["marker_frame_indices"]["end"])][85:125, 30:225]
    assert begin[..., 0].mean() > begin[..., 1].mean() + 60
    assert middle[..., 1].mean() > middle[..., 0].mean() + 60
    assert end[..., 2].mean() > end[..., 1].mean() + 60
