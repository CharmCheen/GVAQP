#!/usr/bin/env python3
"""Local Qwen3-VL helper functions for roadclip_budget_v2."""

from __future__ import annotations

import json
import re
from pathlib import Path


def parse_json_object(text: str) -> tuple[dict | None, str]:
    raw = (text or "").strip()
    if not raw:
        return None, "empty_response"
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None, "" if isinstance(obj, dict) else "json_not_object"
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None, "json_parse_failed"
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None, "" if isinstance(obj, dict) else "json_not_object"
        except Exception as exc:
            return None, f"json_parse_failed: {exc}"


def load_qwen3_vl(model_dir: Path):
    try:
        import torch
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    except Exception as exc:
        raise RuntimeError(f"missing Qwen3-VL dependencies: {exc}") from exc
    if not model_dir.is_dir():
        raise RuntimeError(f"missing Qwen3-VL model directory: {model_dir}")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(model_dir),
        torch_dtype="auto",
        device_map="auto",
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
    return torch, process_vision_info, model, processor


def run_video_prompt(torch, process_vision_info, model, processor, clip_path: str, prompt: str, fps: float) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": clip_path, "fps": fps},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


SCENE_FILTER_PROMPT = """You are filtering dashcam video windows for a semantic clip-query benchmark.

Task: decide whether this window is a valid road-driving segment.

Return strict JSON only:
{
  "valid_road_driving": "yes|no|uncertain",
  "scene_type": "road_driving|pre_road|closed_area|parking_low_speed|title_or_black|static_or_parked|unusable|other",
  "confidence": "low|medium|high",
  "reason": "brief explanation"
}

Use valid_road_driving = yes only if the clip shows a forward moving dashcam / ego vehicle road-driving view with real road/lane/traffic context and possible interaction with traffic participants.

Use no for title cards, black screen, transitions, pre-road scenes, garage/campus/closed area, parking-lot or low-speed maneuvering, stationary/parked camera, only roadside static scene, unusable blur, indoor or non-driving content.

If evidence is unclear, use uncertain. Ignore OSD, subtitles, timestamps, and black borders."""


CONSERVATIVE_RISK_PROMPT = """You are a conservative traffic-risk verifier for dashcam clips.

Only mark positive when there is a clear ego-path conflict. Do not mark ordinary traffic, many vehicles, normal following, adjacent-lane vehicles, far vehicles, roadside vehicles, or ambiguous lane changes as positive.

Answer these points:
1. Is there an object that starts outside the ego vehicle's projected path?
2. Does it enter, cross, or clearly intrude into the ego vehicle's projected path during this clip?
3. Is it close/relevant enough that the ego vehicle may need to brake, slow down, or pay attention?
4. Is this merely normal following, dense traffic, roadside/static vehicles, or a vehicle already in the ego lane?
5. Is there clear visual evidence, not just possible/ambiguous motion?

Return strict JSON only:
{
  "conservative_positive": "yes|no|uncertain",
  "risk_level": "L0|L1|L2|L3",
  "affected_ego": "true|false|uncertain",
  "event_type": "cut_in|crossing|sudden_braking|lane_conflict|close_approach|normal_following|dense_traffic_only|roadside_static|far_vehicle|ambiguous|none",
  "starts_outside_ego_path": "true|false|uncertain",
  "enters_ego_path": "true|false|uncertain",
  "requires_ego_attention": "true|false|uncertain",
  "negative_reason": "normal_following|dense_traffic_only|already_in_ego_lane|adjacent_no_intrusion|roadside_static|far_vehicle|camera_motion_apparent|insufficient_evidence|none",
  "confidence": "low|medium|high",
  "evidence": "brief visual evidence"
}

Positive only if affected_ego is true, enters_ego_path is true, starts_outside_ego_path is true OR event_type is crossing/sudden_braking/lane_conflict, risk_level is L2/L3, and confidence is medium/high.

If evidence is ambiguous, answer uncertain or no."""
