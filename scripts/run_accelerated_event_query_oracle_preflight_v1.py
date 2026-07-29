#!/usr/bin/env python3
"""Run one video's frozen 32B oracle-preflight shard with resumable raw evidence."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V1_PREREGISTRATION.json"
CONFIG = OUT / "configs/stage1_freeze_v1.json"
VIDEO_MANIFEST = OUT / "video_manifests/frozen_videos_v1.json"
RAW = OUT / "operational_oracle/preflight_v1/raw"
FROZEN_SOURCE = (
    ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
    "clean_baseline_benchmark_v2_strict/scripts/build_strict_oracle.py"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def load_frozen():
    spec = importlib.util.spec_from_file_location("aeq_frozen_oracle_support", FROZEN_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {FROZEN_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_response(raw: str) -> tuple[dict, str]:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}, "no_json_object"
        parsed = json.loads(match.group(0))
        required = {
            "label", "event_start_sec", "event_end_sec", "required_response",
            "cause", "confidence", "evidence", "unknown_reason",
        }
        if not isinstance(parsed, dict) or set(parsed) != required:
            return parsed if isinstance(parsed, dict) else {}, "schema_mismatch"
        label = str(parsed["label"]).lower()
        confidence = str(parsed["confidence"]).lower()
        if label not in {"relevant", "not_relevant", "unknown"}:
            return parsed, "invalid_label"
        if confidence not in {"high", "medium", "low"}:
            return parsed, "invalid_confidence"
        responses = parsed["required_response"]
        if not isinstance(responses, list) or any(
            response not in {"slowdown", "brake", "avoid"} for response in responses
        ):
            return parsed, "invalid_required_response"
        if label == "relevant":
            start, end = parsed["event_start_sec"], parsed["event_end_sec"]
            if not responses or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                return parsed, "missing_relevant_boundary_or_response"
            if not 0.0 <= float(start) <= float(end) <= 10.0:
                return parsed, "invalid_relevant_boundary"
        parsed["label"] = label
        parsed["confidence"] = confidence
        return parsed, "ok"
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"


def write_once_or_validate(path: Path, value: dict) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("input_identity_sha256") != value.get("input_identity_sha256"):
            raise RuntimeError(f"existing raw artifact has different input identity: {path}")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", choices=("DALI", "HANGZHOU", "WUHAN"), required=True)
    parser.add_argument("--declared-physical-gpus", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    videos = {row["video_id"]: row for row in json.loads(VIDEO_MANIFEST.read_text())["videos"]}
    video = videos[args.video_id]
    video_path = ROOT / video["path"]
    prompt_path = ROOT / config["query"]["prompt_path"]
    model_path = ROOT / config["oracle"]["model_path"]
    if sha256_file(video_path) != video["sha256"]:
        raise RuntimeError("video identity mismatch")
    if sha256_file(OUT / "video_manifests/frozen_unit_grid_v1.csv") != prereg["unit_grid_sha256"]:
        raise RuntimeError("unit-grid identity mismatch")
    clips = [row for row in prereg["clips"] if row["video_id"] == args.video_id]
    if len(clips) != 4 or len({row["candidate_id"] for row in clips}) != 4:
        raise RuntimeError("preflight shard must contain four unique frozen clips")
    if args.validate_only:
        sensitivity_ids = set(prereg["frame_sampling_sensitivity"]["single_sensitivity_call_candidate_ids"])
        sensitivity_count = sum(row["candidate_id"] in sensitivity_ids for row in clips)
        print(json.dumps({
            "status": "PASS",
            "video_id": args.video_id,
            "clips": clips,
            "expected_physical_calls": (
                len(clips) * int(prereg["repeat_policy"]["repeats_per_clip"])
                + sensitivity_count
            ),
            "video_sha256": video["sha256"],
            "prompt_sha256": sha256_file(prompt_path),
            "model_content_hash": config["oracle"]["model_content_hash"],
        }, indent=2, sort_keys=True))
        return

    import cv2
    import torch
    import transformers
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    physical = [int(token) for token in args.declared_physical_gpus.split(",")]
    if len(physical) != 2 or torch.cuda.device_count() != 2:
        raise RuntimeError("32B preflight requires exactly two visible and declared GPUs")
    gpu_identities = []
    for index in physical:
        identity = subprocess.check_output([
            "nvidia-smi", f"--id={index}", "--query-gpu=index,name,uuid", "--format=csv,noheader",
        ], text=True).strip()
        if not identity.startswith(f"{index},"):
            raise RuntimeError(f"physical GPU declaration mismatch: {identity}")
        gpu_identities.append(identity)

    frozen = load_frozen()
    frozen.VIDEO = video_path
    cap = cv2.VideoCapture(str(video_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    prompt = prompt_path.read_text(encoding="utf-8")

    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map="balanced",
        trust_remote_code=True,
        local_files_only=True,
    )
    model.to(dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(
        model_path, trust_remote_code=True, local_files_only=True
    )
    model.eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started

    sensitivity_ids = set(prereg["frame_sampling_sensitivity"]["single_sensitivity_call_candidate_ids"])
    schedule = []
    for clip in clips:
        schedule.extend((clip, repeat_index, float(config["oracle"]["frame_sampling_fps"]), "base")
                        for repeat_index in range(int(prereg["repeat_policy"]["repeats_per_clip"])))
        if clip["candidate_id"] in sensitivity_ids:
            schedule.append((
                clip,
                0,
                float(prereg["frame_sampling_sensitivity"]["sensitivity_fps"]),
                "fps_sensitivity",
            ))
    completed = []
    for clip, repeat_index, sampling_fps, variant in schedule:
            suffix = f"fps{sampling_fps:g}_r{repeat_index}" if variant == "base" else f"fps{sampling_fps:g}_sensitivity"
            path = RAW / args.video_id / f"{clip['candidate_id']}_{suffix}.json"
            identity_payload = {
                "experiment_id": prereg["experiment_id"],
                "video_sha256": video["sha256"],
                "candidate_id": clip["candidate_id"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "repeat_index": repeat_index,
                "variant": variant,
                "frame_sampling_fps": sampling_fps,
                "prompt_sha256": sha256_file(prompt_path),
                "model_content_hash": config["oracle"]["model_content_hash"],
                "seed": prereg["repeat_policy"]["seed"],
                "generation": {
                    "do_sample": config["oracle"]["do_sample"],
                    "max_new_tokens": config["oracle"]["max_new_tokens"],
                },
            }
            input_identity = canonical_hash(identity_payload)
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("input_identity_sha256") != input_identity:
                    raise RuntimeError(f"resume identity mismatch: {path}")
                completed.append(path.name)
                continue

            call_started = time.perf_counter()
            extract_started = time.perf_counter()
            frames = frozen.extract_frames(
                float(clip["start_time"]), float(clip["end_time"]), fps, sampling_fps
            )
            if not frames:
                raise RuntimeError(f"no frames decoded for {clip['candidate_id']} at {sampling_fps} fps")
            extract_seconds = time.perf_counter() - extract_started
            frame_hashes = [row["content_sha256"] for row in frames]
            pil_frames = [Image.fromarray(row["rgb"]) for row in frames]
            messages = [{"role": "user", "content": [
                {"type": "video", "video": pil_frames, "fps": sampling_fps},
                {"type": "text", "text": prompt},
            ]}]
            preprocess_started = time.perf_counter()
            prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs, kwargs = process_vision_info(
                messages, return_video_kwargs=True, return_video_metadata=True
            )
            if kwargs != {"do_sample_frames": False}:
                raise RuntimeError(f"unexpected video sampling kwargs: {kwargs}")
            video_tensors = [item[0] for item in video_inputs]
            video_metadata = [item[1] for item in video_inputs]
            inputs = processor(
                text=[prompt_text], images=image_inputs, videos=video_tensors,
                video_metadata=video_metadata, padding=True, return_tensors="pt", **kwargs,
            ).to(model.device)
            rng = frozen.configure_rng(int(prereg["repeat_policy"]["seed"]), torch)
            preprocess_seconds = time.perf_counter() - preprocess_started
            torch.cuda.synchronize()
            inference_started = time.perf_counter()
            with torch.no_grad():
                generated = model.generate(
                    **inputs,
                    do_sample=bool(config["oracle"]["do_sample"]),
                    max_new_tokens=int(config["oracle"]["max_new_tokens"]),
                )
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed, parse_status = parse_response(raw)
            record = {
                **identity_payload,
                "input_identity_sha256": input_identity,
                "model_input_identity_sha256": canonical_hash({
                    **{key: value for key, value in identity_payload.items() if key != "repeat_index"},
                    "frame_hashes": frame_hashes,
                }),
                "stratum": clip["stratum"],
                "frame_count": len(frames),
                "decoded_frame_indices": [int(row["decoded_index"]) for row in frames],
                "decoded_frame_content_sha256": canonical_hash(frame_hashes),
                "rng_state_identity_sha256": rng["rng_state_identity_sha256"],
                "parse_status": parse_status,
                "effective_label": parsed.get("label") if parse_status == "ok" else "parse_failure",
                "parsed": parsed,
                "raw": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "stage_seconds": {
                    "clip_extraction": extract_seconds,
                    "preprocess": preprocess_seconds,
                    "inference": inference_seconds,
                    "total": time.perf_counter() - call_started,
                },
                "runtime": {
                    "declared_physical_gpus": physical,
                    "gpu_identities": gpu_identities,
                    "model_load_seconds": load_seconds,
                    "parameter_dtypes": sorted({str(parameter.dtype) for parameter in model.parameters()}),
                    "torch": torch.__version__,
                    "transformers": transformers.__version__,
                },
            }
            write_once_or_validate(path, record)
            completed.append(path.name)
            print(json.dumps({
                "video_id": args.video_id,
                "candidate_id": clip["candidate_id"],
                "repeat_index": repeat_index,
                "variant": variant,
                "frame_sampling_fps": sampling_fps,
                "parse_status": parse_status,
                "effective_label": record["effective_label"],
                "inference_seconds": inference_seconds,
            }), flush=True)
            del frames, pil_frames, messages, image_inputs, video_inputs, video_tensors
            del video_metadata, inputs, generated, trimmed
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    print(json.dumps({
        "video_id": args.video_id,
        "expected_calls": len(schedule),
        "completed_artifacts": sorted(completed),
        "model_load_seconds": load_seconds,
    }, indent=2))


if __name__ == "__main__":
    main()
