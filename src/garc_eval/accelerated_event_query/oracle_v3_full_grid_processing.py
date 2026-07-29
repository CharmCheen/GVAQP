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
    sampling_fps: float = 2.0,
) -> Any:
    """Apply the exact frozen Qwen chat/video processor path."""

    from PIL import Image
    from qwen_vl_utils import process_vision_info

    pil_frames = [Image.fromarray(frame) for frame in rgb_frames]
    if not pil_frames:
        raise ValueError("a model input must contain at least one frame")
    messages = [{"role": "user", "content": [
        {"type": "video", "video": pil_frames, "fps": sampling_fps},
        {"type": "text", "text": prompt},
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
