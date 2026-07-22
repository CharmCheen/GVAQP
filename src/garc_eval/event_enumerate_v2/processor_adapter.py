"""Qwen3-VL adapter that makes temporal metadata explicit and auditable."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import numpy as np

from .temporal_contract import (
    ContractError,
    FrameSelection,
    processor_patch_timestamps,
    processor_timestamp_texts,
)


TIMESTAMP_PATTERN = re.compile(r"<([0-9]+(?:\.[0-9]+)?) seconds>")


def render_prompt(template: str, selection: FrameSelection) -> str:
    placeholder = "__CLIP_DURATION_SECONDS__"
    if placeholder not in template:
        raise ContractError(f"prompt is missing {placeholder}")
    return template.replace(placeholder, selection.prompt_duration_text)


def build_messages(prompt: str) -> list[dict[str, Any]]:
    """Build a stable chat request; video pixels are supplied separately."""

    return [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": "in_memory_predecoded_rgb_tensor"},
                {"type": "text", "text": prompt},
            ],
        }
    ]


def tensor_sha256(tensor: Any) -> str:
    value = tensor.detach().cpu().contiguous()
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(str(tuple(value.shape)).encode("ascii"))
    digest.update(value.numpy().tobytes(order="C"))
    return digest.hexdigest()


def make_video_metadata(selection: FrameSelection, width: int, height: int) -> Any:
    from transformers.video_utils import VideoMetadata

    values = selection.processor_metadata_dict()
    values["width"] = int(width)
    values["height"] = int(height)
    return VideoMetadata(**values)


def prepare_model_inputs(
    processor: Any,
    frames_rgb: np.ndarray,
    selection: FrameSelection,
    prompt_template: str,
) -> tuple[Any, dict[str, Any]]:
    """Prepare exactly one metadata-correct model input without generation."""

    if frames_rgb.ndim != 4 or frames_rgb.shape[-1] != 3:
        raise ContractError("frames_rgb must have shape [T,H,W,3]")
    if frames_rgb.shape[0] != selection.decoded_frame_count:
        raise ContractError("decoded tensor length differs from frame schedule")
    prompt = render_prompt(prompt_template, selection)
    messages = build_messages(prompt)
    chat_text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    metadata = make_video_metadata(selection, frames_rgb.shape[2], frames_rgb.shape[1])
    inputs = processor(
        text=[chat_text],
        videos=[frames_rgb],
        video_metadata=[metadata],
        do_sample_frames=False,
        return_metadata=True,
        padding=True,
        return_tensors="pt",
    )
    decoded_input = processor.tokenizer.decode(
        inputs.input_ids[0], skip_special_tokens=False
    )
    observed_timestamp_texts = TIMESTAMP_PATTERN.findall(decoded_input)
    expected_timestamp_texts = processor_timestamp_texts(selection)
    if observed_timestamp_texts != expected_timestamp_texts:
        raise ContractError(
            "serialized processor timestamps differ from the frozen transport proof"
        )
    grid = inputs.video_grid_thw[0].detach().cpu().tolist()
    expected_t = len(
        processor_patch_timestamps(
            selection.relative_source_indices, selection.source_fps
        )
    )
    if int(grid[0]) != expected_t:
        raise ContractError("video temporal grid differs from expected patch count")
    tensor_hashes = {
        key: tensor_sha256(inputs[key])
        for key in [
            "input_ids",
            "attention_mask",
            "mm_token_type_ids",
            "pixel_values_videos",
            "video_grid_thw",
        ]
        if key in inputs
    }
    audit = {
        "do_sample_frames": False,
        "video_metadata": dict(metadata),
        "processor_visible_timestamps": [
            float(x)
            for x in processor_patch_timestamps(
                selection.relative_source_indices, selection.source_fps
            )
        ],
        "processor_visible_timestamp_texts": observed_timestamp_texts,
        "video_grid_thw": grid,
        "input_token_count": int(inputs.input_ids.numel()),
        "tensor_hashes": tensor_hashes,
        "serialized_chat_text_sha256": hashlib.sha256(
            chat_text.encode("utf-8")
        ).hexdigest(),
        "rendered_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    return inputs, audit
