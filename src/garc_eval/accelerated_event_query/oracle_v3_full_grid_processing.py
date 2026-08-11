"""Frozen processor identity for every V3 full-grid model input.

This module contains the one processor path used both while preregistering
expected tensor identities and immediately before an authorized generation.
It never loads model weights by itself.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any, Iterable


NOMINAL_UNIT_INSTRUCTION = "Inspect this 10-second ego-driving unit"
TAIL_UNIT_INSTRUCTION_TEMPLATE = (
    "This is a legal shorter truncated-final ego-driving unit, not a nominal "
    "10-second unit. Its frozen "
    "source interval duration is {duration_seconds:.6f} seconds, and the model "
    "input contains {frame_count} distinct real source frames on the frozen "
    "{sampling_fps:.6f}-fps grid. No padding, repeated frame, or invented "
    "off-grid endpoint was added. Inspect this truncated-final ego-driving unit"
)


def runtime_environment_identity() -> dict[str, str]:
    """Return versions that can change processor tensor construction."""

    import cv2
    import numpy
    import PIL
    import torch
    import transformers

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils"),
        "numpy": numpy.__version__,
        "pillow": PIL.__version__,
        "opencv": cv2.__version__,
    }


def load_frozen_processor(model_path: Path):
    """Load processor assets only; no model class or checkpoint tensors."""

    from transformers import AutoProcessor

    return AutoProcessor.from_pretrained(
        model_path, trust_remote_code=True, local_files_only=True
    )


def prepare_frozen_model_inputs(
    processor: Any,
    *,
    prompt: str,
    rgb_frames: Iterable[Any],
    unit_kind: str,
    true_duration_seconds: float,
    sampling_fps: float = 2.0,
) -> Any:
    """Apply the exact frozen Qwen chat/video processor path."""

    from PIL import Image
    from qwen_vl_utils import process_vision_info

    pil_frames = [Image.fromarray(frame) for frame in rgb_frames]
    if not pil_frames:
        raise ValueError("a model input must contain at least one frame")
    model_visible_text = model_visible_query_text(
        prompt=prompt,
        unit_kind=unit_kind,
        true_duration_seconds=true_duration_seconds,
        supplied_frame_count=len(pil_frames),
        sampling_fps=sampling_fps,
    )
    messages = [{"role": "user", "content": [
        {"type": "video", "video": pil_frames, "fps": sampling_fps},
        {"type": "text", "text": model_visible_text},
    ]}]
    prompt_text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs, kwargs = process_vision_info(
        messages, return_video_kwargs=True, return_video_metadata=True
    )
    if kwargs != {"do_sample_frames": False}:
        raise RuntimeError(f"unexpected processor sampling kwargs: {kwargs}")
    return processor(
        text=[prompt_text],
        images=image_inputs,
        videos=[row[0] for row in video_inputs],
        video_metadata=[row[1] for row in video_inputs],
        padding=True,
        return_tensors="pt",
        **kwargs,
    )


def model_visible_query_text(
    *,
    prompt: str,
    unit_kind: str,
    true_duration_seconds: float,
    supplied_frame_count: int,
    sampling_fps: float,
) -> str:
    """Compose the exact model-visible query text for normal and tail units.

    Normal units preserve the frozen base-prompt bytes.  A legal final unit is
    explicitly identified to the model and replaces the otherwise false
    nominal ten-second assertion without changing the query predicate or
    authoritative output schema.
    """

    if unit_kind == "normal":
        if abs(float(true_duration_seconds) - 10.0) > 1e-6:
            raise ValueError("normal unit must have the frozen 10-second duration")
        return prompt
    if unit_kind != "truncated_final":
        raise ValueError(f"unknown unit kind: {unit_kind}")
    duration = float(true_duration_seconds)
    frame_count = int(supplied_frame_count)
    fps = float(sampling_fps)
    if not (0.0 < duration < 10.0):
        raise ValueError("truncated-final duration must be in (0, 10) seconds")
    if frame_count <= 0 or fps <= 0.0:
        raise ValueError("truncated-final frame count and sampling fps must be positive")
    if prompt.count(NOMINAL_UNIT_INSTRUCTION) != 1:
        raise RuntimeError("frozen nominal-unit instruction changed")
    tail_instruction = TAIL_UNIT_INSTRUCTION_TEMPLATE.format(
        duration_seconds=duration,
        frame_count=frame_count,
        sampling_fps=fps,
    )
    return prompt.replace(NOMINAL_UNIT_INSTRUCTION, tail_instruction, 1)


def tensor_bundle_sha256(values: Any) -> str:
    """Hash exact tensor keys, dtypes, shapes, and bytes canonically."""

    digest = hashlib.sha256()
    for key in sorted(values):
        value = values[key]
        digest.update(key.encode())
        if hasattr(value, "detach"):
            tensor = value.detach().cpu().contiguous()
            digest.update(str(tensor.dtype).encode())
            digest.update(json.dumps(list(tensor.shape)).encode())
            digest.update(tensor.view(dtype=__import__("torch").uint8).numpy().tobytes())
        else:
            digest.update(repr(value).encode())
    return digest.hexdigest()


def tensor_shapes(values: Any) -> dict[str, list[int]]:
    return {
        key: list(value.shape)
        for key, value in values.items()
        if hasattr(value, "shape")
    }
