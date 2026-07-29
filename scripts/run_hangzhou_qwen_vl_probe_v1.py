#!/usr/bin/env python3
"""Run the frozen Hangzhou physical VLM cost/agreement probe on one model."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/binary_smdp_value_v1/hangzhou_physical"
PROTOCOL_PATH = OUT / "PROBE_PROTOCOL.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_frozen(path: Path):
    spec = importlib.util.spec_from_file_location("hangzhou_frozen_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen oracle source: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def model_manifest(model_path: Path) -> tuple[list[dict], str]:
    rows = []
    for path in sorted(model_path.iterdir(), key=lambda item: item.name):
        if path.is_file():
            rows.append({"file": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    if not rows or not any(row["file"].endswith(".safetensors") for row in rows):
        raise RuntimeError("model manifest contains no safetensors weights")
    return rows, canonical_hash(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("8b", "32b"), required=True)
    parser.add_argument("--declared-physical-gpus", required=True,
                        help="comma-separated physical GPU indices bound by CUDA_VISIBLE_DEVICES")
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    video_path = ROOT / protocol["video_path"]
    prompt_path = ROOT / protocol["prompt_path"]
    model_path = ROOT / protocol["models"][args.model]
    frozen_path = ROOT / protocol["parser_source"]
    for path, expected in ((video_path, protocol["video_sha256"]), (prompt_path, protocol["prompt_sha256"])):
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"frozen identity mismatch for {path}: {observed}")

    import cv2
    import torch
    import transformers
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    declared_gpus = [int(value) for value in args.declared_physical_gpus.split(",")]
    if not torch.cuda.is_available() or torch.cuda.device_count() != len(declared_gpus):
        raise RuntimeError("visible CUDA device count does not match declared physical GPUs")
    physical_names = []
    for physical_gpu in declared_gpus:
        identity = subprocess.check_output(
            ["nvidia-smi", f"--id={physical_gpu}",
             "--query-gpu=index,name,uuid", "--format=csv,noheader"], text=True
        ).strip()
        if not identity.startswith(f"{physical_gpu},"):
            raise RuntimeError(f"declared physical GPU does not match identity: {identity}")
        physical_names.append(identity)
    if args.model == "8b" and len(declared_gpus) != 1:
        raise RuntimeError("8b probe is frozen to one GPU")
    if args.model == "32b" and len(declared_gpus) != 2:
        raise RuntimeError("32b A100 BF16-dequantized probe is frozen to two GPUs")

    frozen = load_frozen(frozen_path)
    frozen.VIDEO = video_path
    prompt = prompt_path.read_text(encoding="utf-8")
    cap = cv2.VideoCapture(str(video_path))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    files, content_hash = model_manifest(model_path)

    # This is a fresh process, so CUDA peak counters start at zero. Avoid an
    # environment-specific pre-initialization failure in the reset API.
    load_start = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, dtype=torch.bfloat16,
        device_map="cuda:0" if args.model == "8b" else "balanced",
        trust_remote_code=True, local_files_only=True
    )
    if args.model == "32b":
        # A100 cannot execute the checkpoint's FP8 path. Transformers 5.9
        # dequantizes most weights to BF16 but leaves some ignored layers in
        # FP32, which otherwise makes the first linear operation fail.
        model.to(dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    model.eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_start

    schedule = [(clip, 0) for clip in protocol["clips"]]
    schedule.append((next(clip for clip in protocol["clips"] if clip["clip_id"] == "HZ_2800"), 1))
    calls = []
    for clip, repeat_index in schedule:
        call_start = time.perf_counter()
        extraction_start = time.perf_counter()
        frames = frozen.frames_for_unit(clip["start_seconds"], clip["end_seconds"], video_fps)
        extraction_seconds = time.perf_counter() - extraction_start
        frame_hashes = [frame["content_sha256"] for frame in frames]
        frame_indices = [int(frame["decoded_index"]) for frame in frames]

        preprocess_start = time.perf_counter()
        pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
        messages = [{"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": protocol["frame_sampling"]["message_fps"]},
            {"type": "text", "text": prompt},
        ]}]
        prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs, video_kwargs = process_vision_info(
            messages, return_video_kwargs=True, return_video_metadata=True
        )
        # Qwen3-VL needs the metadata paired with each pre-sampled video tensor
        # to construct temporal position IDs. qwen-vl-utils supplies the
        # frozen 2 fps identity when return_video_metadata=True.
        if video_kwargs != {"do_sample_frames": False}:
            raise RuntimeError(f"unexpected video kwargs: {video_kwargs}")
        video_tensors = [item[0] for item in video_inputs]
        video_metadata = [item[1] for item in video_inputs]
        inputs = processor(
            text=[prompt_text], images=image_inputs, videos=video_tensors,
            video_metadata=video_metadata, padding=True, return_tensors="pt", **video_kwargs
        ).to(model.device)
        rng = frozen.configure_rng(protocol["rng_seed"], torch)
        preprocess_seconds = time.perf_counter() - preprocess_start

        torch.cuda.synchronize()
        inference_start = time.perf_counter()
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                do_sample=protocol["generation"]["do_sample"],
                max_new_tokens=protocol["generation"]["max_new_tokens"],
            )
        torch.cuda.synchronize()
        inference_seconds = time.perf_counter() - inference_start
        trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated)]
        raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        parsed, parse_status = frozen.parse_response(raw)
        calls.append({
            "clip_id": clip["clip_id"],
            "repeat_index": repeat_index,
            "start_seconds": clip["start_seconds"],
            "end_seconds": clip["end_seconds"],
            "frame_count": len(frames),
            "decoded_frame_indices": frame_indices,
            "decoded_frame_content_sha256": canonical_hash(frame_hashes),
            "rng_state_identity_sha256": rng["rng_state_identity_sha256"],
            "model_input_shapes": {
                name: list(value.shape) for name, value in inputs.items() if hasattr(value, "shape")
            },
            "stage_seconds": {
                "clip_extraction": extraction_seconds,
                "preprocess": preprocess_seconds,
                "inference": inference_seconds,
                "total": time.perf_counter() - call_start,
            },
            "parse_status": parse_status,
            "parsed": parsed,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        })
        del inputs, generated, frames, pil_frames, image_inputs, video_inputs
        del video_tensors, video_metadata, video_kwargs, messages
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    result = {
        "probe_status": "COMPLETE",
        "model_key": args.model,
        "model_path": str(model_path.relative_to(ROOT)),
        "model_content_hash": content_hash,
        "model_file_manifest": files,
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "cuda_runtime": torch.version.cuda,
            "declared_physical_gpus": declared_gpus,
            "gpu_identities": physical_names,
            "load_seconds": load_seconds,
            "hf_device_map": {
                str(key): str(value) for key, value in sorted(getattr(model, "hf_device_map", {}).items())
            },
            "parameter_dtypes": sorted({str(parameter.dtype) for parameter in model.parameters()}),
            "peak_allocated_bytes_by_visible_device": [
                int(torch.cuda.max_memory_allocated(torch.device(f"cuda:{index}")))
                for index in range(torch.cuda.device_count())
            ],
            "peak_reserved_bytes_by_visible_device": [
                int(torch.cuda.max_memory_reserved(torch.device(f"cuda:{index}")))
                for index in range(torch.cuda.device_count())
            ],
            "platform": platform.platform(),
            "python": sys.version,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "calls": calls,
    }
    atomic_json(OUT / f"{args.model}_results.json", result)
    print(json.dumps({
        "model": args.model,
        "load_seconds": load_seconds,
        "peak_allocated_bytes_by_visible_device": result["runtime"]["peak_allocated_bytes_by_visible_device"],
        "calls": [{"clip_id": c["clip_id"], "repeat": c["repeat_index"],
                   "label": c["parsed"].get("label"), "parse": c["parse_status"],
                   "inference_seconds": c["stage_seconds"]["inference"]} for c in calls],
    }, indent=2))


if __name__ == "__main__":
    main()
