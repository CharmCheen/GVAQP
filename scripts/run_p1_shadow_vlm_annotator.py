#!/usr/bin/env python3
"""Run one isolated VLM-direct shadow annotator over frozen full timelines."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/p1_shadow_vlm_direct_reference_v1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()


def frames(path: Path, start: float, end: float, n: int) -> list[Image.Image]:
    cap = cv2.VideoCapture(str(path))
    images = []
    try:
        for sec in np.linspace(start, max(start, end - 0.05), n):
            cap.set(cv2.CAP_PROP_POS_MSEC, float(sec) * 1000.0)
            ok, frame = cap.read()
            if ok:
                images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    finally:
        cap.release()
    if not images:
        raise RuntimeError(f"no frames decoded: {path} [{start},{end}]")
    return images


def parse(raw: str, duration: float) -> tuple[list[dict], str]:
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        obj = json.loads(match.group(0) if match else raw.strip())
        value = obj.get("events")
        if not isinstance(value, list):
            raise ValueError("events is not a list")
        events = []
        for event in value:
            start, end = float(event["start_offset_sec"]), float(event["end_offset_sec"])
            if not 0 <= start < end <= duration + 1e-6:
                raise ValueError("event outside window")
            events.append({
                "start_offset_sec": max(0.0, start), "end_offset_sec": min(duration, end),
                "boundary_ambiguous": bool(event.get("boundary_ambiguous", False)),
                "semantic_ambiguous": bool(event.get("semantic_ambiguous", False)),
                "notes": str(event.get("notes", ""))[:500],
            })
        return events, "JSON_SCHEMA_VALID"
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, AttributeError):
        return [], "PARSE_FAILURE_COERCED_EMPTY_UNCERTAIN"


def complete(raw_path: Path) -> set[str]:
    if not raw_path.exists():
        return set()
    return {json.loads(line)["window_id"] for line in raw_path.read_text().splitlines() if line.strip() and json.loads(line).get("terminal")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", choices=["VLM_A", "VLM_B"], required=True)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--balanced", action="store_true", help="shard a large frozen checkpoint across visible GPUs")
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    args = ap.parse_args()
    protocol = json.loads((OUT / "SHADOW_PROTOCOL.json").read_text())
    cases = json.loads((OUT / "BLINDED_CASES.json").read_text())
    spec = protocol["annotators"][args.annotator]
    model_path = Path(spec["path"])
    if not 0 <= args.shard_index < args.num_shards:
        raise RuntimeError("invalid deterministic shard")
    raw_path = OUT / (f"{args.annotator}_RAW.jsonl" if args.num_shards == 1 else f"{args.annotator}_RAW_SHARD{args.shard_index:02d}.jsonl")
    done = complete(raw_path)
    if args.annotator == "VLM_B" and (OUT / "VLM_A_RAW.jsonl").exists():
        # Independence is enforced by code: that path is never opened here.
        pass
    if spec["family"] == "Qwen3-VL":
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
        placement = "balanced" if args.balanced else args.device
        model = Qwen3VLForConditionalGeneration.from_pretrained(model_path, dtype=torch.bfloat16, device_map=placement, trust_remote_code=True, local_files_only=True)
        # The local 32B FP8 checkpoint is dequantized on A100; normalize all
        # shards to bf16 exactly as the existing frozen Qwen32 runtime does.
        model.to(dtype=torch.bfloat16)
    else:
        from transformers import AutoModelForImageTextToText, AutoProcessor
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForImageTextToText.from_pretrained(model_path, torch_dtype=torch.bfloat16, local_files_only=True).to(args.device)
    model.eval()
    window_sec = float(protocol["windowing"]["window_sec"])
    stride = float(protocol["windowing"]["stride_sec"])
    cap = int(protocol["windowing"]["frame_cap"])
    tasks = []
    for case in cases:
        starts = list(np.arange(0.0, float(case["duration_sec"]), stride))
        for index, start in enumerate(starts):
            end = min(float(case["duration_sec"]), start + window_sec)
            tasks.append((case, index, float(start), float(end)))
    tasks = [task for global_index, task in enumerate(tasks) if global_index % args.num_shards == args.shard_index]
    for task_index, (case, index, start, end) in enumerate(tasks, 1):
        window_id = f"{case['case_id']}::W{index:04d}"
        if window_id in done:
            continue
        imgs = frames(Path(case["video_path"]), start, end, cap)
        prompt_template = protocol.get("prompt_template_b", protocol["prompt_template"]) if args.annotator == "VLM_B" else protocol["prompt_template"]
        prompt = prompt_template.replace("ABS_START", f"{start:.3f}").replace("ABS_END", f"{end:.3f}").replace("WINDOW_DURATION", f"{end-start:.3f}").replace("QUERY_TEXT", case["query_definition"])
        t0 = time.perf_counter()
        if spec["family"] == "Qwen3-VL":
            # Frames are already sampled uniformly from the raw-video window.
            # Supplying them as chronological images avoids processor-side
            # resampling/default-FPS ambiguity while retaining the same pixels.
            messages = [{"role": "user", "content": [{"type": "image", "image": image} for image in imgs] + [{"type": "text", "text": prompt}]}]
            text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text], images=imgs, padding=True, return_tensors="pt").to(model.device)
        else:
            content = [{"type": "image"} for _ in imgs] + [{"type": "text", "text": prompt}]
            text = processor.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True)
            inputs = processor(text=text, images=imgs, padding=True, return_tensors="pt").to(args.device)
        with torch.inference_mode():
            generated = model.generate(**inputs, do_sample=False, max_new_tokens=int(protocol["generation"]["max_new_tokens"]), use_cache=True)
        trimmed = generated[:, inputs.input_ids.shape[1]:]
        raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        events, parse_status = parse(raw, end - start)
        append(raw_path, {
            "annotator_id": args.annotator, "window_id": window_id, "case_id": case["case_id"],
            "video_id": case["video_id"], "query_id": case["query_id"], "window_index": index,
            "window_start": start, "window_end": end, "events": events, "parse_status": parse_status,
            "raw_response": raw, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "model_identity_hash": spec["identity_hash"], "protocol_hash": protocol["protocol_hash"],
            "latency_sec": time.perf_counter() - t0, "completed_at": now(), "terminal": True,
        })
        done.add(window_id)
        if len(done) % 20 == 0 or task_index == len(tasks):
            print(f"{args.annotator}_PROGRESS {len(done)}/{len(tasks)}", flush=True)
    if args.num_shards == 1:
        state_path = OUT / "SHADOW_STATE.json"
        state = json.loads(state_path.read_text())
        state[args.annotator.lower() + "_complete"] = True
        state[args.annotator.lower() + "_raw_sha256"] = sha(raw_path)
        state["status"] = "VLM_ANNOTATION_RUNNING" if not (state.get("vlm_a_complete") and state.get("vlm_b_complete")) else "BOTH_VLM_ANNOTATIONS_COMPLETE"
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(f"{args.annotator}_COMPLETE {len(done)}/{len(tasks)}")


if __name__ == "__main__":
    main()
