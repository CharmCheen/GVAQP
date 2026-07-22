from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from garc_eval.event_enumerate_v2.forensics import reconstruct_old_processor
from garc_eval.event_enumerate_v2.temporal_contract import processor_patch_timestamps


def test_old_nominal_60_second_compression_is_reproduced_from_local_source():
    source_fps = 30.000005775562784
    source_indices = list(range(1350, 3150 + 1, 15))
    reconstruction = reconstruct_old_processor(source_indices, source_fps)
    assert len(source_indices) == 121
    assert reconstruction["qwen_utils_padded_count"] == 122
    assert reconstruction["processor_frame_count"] == 10
    assert reconstruction["processor_selected_tensor_positions"] == [
        0,
        13,
        27,
        40,
        54,
        67,
        81,
        94,
        108,
        121,
    ]
    assert reconstruction["processor_timestamp_texts"] == [
        "0.3",
        "1.4",
        "2.5",
        "3.6",
        "4.8",
    ]
    assert reconstruction["processor_patch_timestamps"][-1] == pytest.approx(
        4.770833333333334
    )


def test_installed_qwen_classes_execute_the_reconstructed_old_rules():
    from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessor
    from transformers.models.qwen3_vl.video_processing_qwen3_vl import (
        Qwen3VLVideoProcessor,
    )
    from transformers.video_utils import VideoMetadata

    metadata = VideoMetadata(
        total_num_frames=122,
        fps=None,
        frames_indices=list(range(122)),
    )
    video_processor = Qwen3VLVideoProcessor()
    positions = video_processor.sample_frames(metadata).tolist()
    assert metadata.fps == 24
    assert positions == [0, 13, 27, 40, 54, 67, 81, 94, 108, 121]
    timestamps = Qwen3VLProcessor._calculate_timestamps(
        None, positions, metadata.fps, merge_size=2
    )
    assert timestamps == pytest.approx(
        [0.2708333333333333, 1.3958333333333335, 2.520833333333333, 3.645833333333333, 4.770833333333334]
    )


def test_exact_v1_helper_to_processor_call_compresses_sentinel_frames(local_processor):
    from PIL import Image
    from qwen_vl_utils import process_vision_info

    frames = [
        Image.fromarray(np.full((64, 96, 3), index % 256, dtype=np.uint8))
        for index in range(121)
    ]
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": frames, "fps": 2.0},
                {"type": "text", "text": "processor-only v1 regression"},
            ],
        }
    ]
    chat_text = local_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    assert image_inputs is None
    assert tuple(video_inputs[0].shape[:2]) == (122, 3)
    # This is the exact old call signature: no returned video kwargs, no
    # VideoMetadata, and no do_sample_frames=False override.
    inputs = local_processor(
        text=[chat_text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    decoded = local_processor.tokenizer.decode(
        inputs.input_ids[0], skip_special_tokens=False
    )
    assert inputs.video_grid_thw[0, 0].item() == 5
    assert [
        token.split(" seconds>")[0]
        for token in decoded.split("<")
        if " seconds>" in token
    ] == ["0.3", "1.4", "2.5", "3.6", "4.8"]


def test_all_68_nominal_old_calls_have_the_reconstructed_compression():
    root = Path(__file__).resolve().parents[4]
    path = (
        root
        / "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/audit/OLD_CALL_TIMELINE_RECONSTRUCTION.csv"
    )
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    nominal = [row for row in rows if row["is_nominal_60_second_call"] == "True"]
    assert len(nominal) == 68
    assert {int(row["decoded_frame_count"]) for row in nominal} == {121}
    assert {int(row["qwen_utils_padded_frame_count"]) for row in nominal} == {122}
    assert {int(row["processor_consumed_frame_count"]) for row in nominal} == {10}
    assert {int(row["processor_temporal_patch_count"]) for row in nominal} == {5}
    assert {
        round(float(row["processor_visible_end"]), 12) for row in nominal
    } == {round(4.770833333333334, 12)}


def test_corrected_metadata_retains_all_121_frames_and_sixty_seconds():
    relative_source_indices = list(range(0, 601, 5))
    timestamps = processor_patch_timestamps(relative_source_indices, 10.0)
    assert len(relative_source_indices) == 121
    assert len(timestamps) == 61
    assert timestamps[0] == pytest.approx(0.25)
    assert timestamps[-1] == pytest.approx(60.0)
    assert timestamps == sorted(timestamps)
