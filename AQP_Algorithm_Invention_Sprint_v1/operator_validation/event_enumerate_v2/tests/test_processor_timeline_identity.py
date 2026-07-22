from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import torch

from garc_eval.event_enumerate_v2.processor_adapter import (
    TIMESTAMP_PATTERN,
    build_messages,
    make_video_metadata,
    prepare_model_inputs,
    render_prompt,
)
from garc_eval.event_enumerate_v2.temporal_contract import (
    IntervalRequest,
    VideoInfo,
    build_frame_selection,
    decode_frame_selection,
    processor_patch_timestamps,
    processor_timestamp_texts,
)


CORPUS = Path(__file__).resolve().parent / "metadata_videos"


def _selection(file_name: str, interval_id: str, start: float, end: float):
    video = VideoInfo.probe(CORPUS / file_name)
    request = IntervalRequest(interval_id, start, end, start, end)
    selection = build_frame_selection(video, request)
    decoded = decode_frame_selection(selection)
    return selection, decoded.frames_rgb


def test_pure_timestamp_transport_covers_all_registered_lengths(corpus_manifest):
    for spec in corpus_manifest["videos"]:
        video = VideoInfo.probe(CORPUS / spec["file"])
        for interval in spec["intervals"]:
            request = IntervalRequest(
                interval["id"],
                float(interval["start"]),
                float(interval["end"]),
                float(interval["start"]),
                float(interval["end"]),
            )
            selection = build_frame_selection(video, request)
            patches = processor_patch_timestamps(
                selection.relative_source_indices, selection.source_fps
            )
            assert len(patches) == (selection.decoded_frame_count + 1) // 2
            assert patches == sorted(patches)
            assert patches[-1] <= selection.prompt_duration_seconds + 1e-12
            assert abs(
                selection.timestamp_anchor_seconds + selection.relative_timestamps[-1]
                - selection.actual_end
            ) <= 1e-12


def test_installed_processor_preserves_the_full_nominal_60_second_timeline(
    local_processor, prompt_template
):
    selection, frames = _selection("timeline_60s_10fps.mp4", "full60", 0.0, 60.0)
    inputs, audit = prepare_model_inputs(
        local_processor, frames, selection, prompt_template
    )
    assert audit["do_sample_frames"] is False
    assert audit["video_metadata"]["fps"] == 10.0
    assert audit["video_metadata"]["frames_indices"] == list(range(0, 601, 5))
    assert audit["video_grid_thw"][0] == 61
    assert audit["processor_visible_timestamp_texts"][0] == "0.2"
    assert audit["processor_visible_timestamp_texts"][-1] == "60.0"
    assert inputs.pixel_values_videos.shape[0] == int(
        torch.prod(inputs.video_grid_thw[0]).item()
    )
    assert set(audit["tensor_hashes"]) >= {
        "input_ids",
        "pixel_values_videos",
        "video_grid_thw",
    }


def test_batch_and_single_processor_outputs_are_equivalent(
    local_processor, prompt_template
):
    cases = [
        _selection("timeline_60s_10fps.mp4", "ten", 12.3, 22.3),
        _selection("timeline_73p4s_10fps.mp4", "partial", 70.0, 73.4),
    ]
    singles = [
        prepare_model_inputs(local_processor, frames, selection, prompt_template)[0]
        for selection, frames in cases
    ]
    chat_texts, videos, metadata = [], [], []
    for selection, frames in cases:
        prompt = render_prompt(prompt_template, selection)
        chat_texts.append(
            local_processor.apply_chat_template(
                build_messages(prompt), tokenize=False, add_generation_prompt=True
            )
        )
        videos.append(frames)
        metadata.append(make_video_metadata(selection, frames.shape[2], frames.shape[1]))
    batch = local_processor(
        text=chat_texts,
        videos=videos,
        video_metadata=metadata,
        do_sample_frames=False,
        return_metadata=True,
        padding=True,
        return_tensors="pt",
    )
    assert torch.equal(
        batch.video_grid_thw.cpu(),
        torch.cat([single.video_grid_thw.cpu() for single in singles], dim=0),
    )
    offset = 0
    for index, single in enumerate(singles):
        active = batch.attention_mask[index].bool()
        assert torch.equal(batch.input_ids[index][active].cpu(), single.input_ids[0].cpu())
        length = int(torch.prod(single.video_grid_thw[0]).item())
        actual_pixels = batch.pixel_values_videos[offset : offset + length].cpu()
        assert torch.equal(actual_pixels, single.pixel_values_videos.cpu())
        offset += length
        decoded = local_processor.tokenizer.decode(
            batch.input_ids[index][active], skip_special_tokens=False
        )
        assert TIMESTAMP_PATTERN.findall(decoded) == processor_timestamp_texts(cases[index][0])
    assert offset == batch.pixel_values_videos.shape[0]
