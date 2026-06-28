#!/usr/bin/env python3
"""Stage 3: VLM Oracle Pilot — run Qwen3-VL-32B-Instruct on 100 pilot clips.

O_enter_ego_path_v0 schema. Conservative labeling.
VLM_ORACLE_RELATIVE — not human truth.
"""
import csv
import json
import os
import time
import sys
import subprocess

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"

os.makedirs(f"{ROOT}/raw_vlm_responses/pilot", exist_ok=True)
os.makedirs(f"{ROOT}/tables", exist_ok=True)
os.makedirs(f"{ROOT}/logs", exist_ok=True)

# Load pilot sample
samples = []
with open(f"{ROOT}/tables/vlm_pilot_sample_100.csv") as f:
    for row in csv.DictReader(f):
        samples.append(row)
print(f"Loaded {len(samples)} pilot samples")

# Prompt for O_enter_ego_path_v0
SYSTEM_PROMPT = """You are a driving safety analyst. Your task is to examine a short driving video clip and determine whether it contains an "object enters ego path" event.

Definition: An object (vehicle, pedestrian, cyclist, or other road user) starts outside or near the boundary of the ego vehicle's future driving path, then enters or clearly overlaps the ego path, creating potential spatial conflict or requiring ego attention.

Rules:
- Normal following traffic, static roadside objects, parked vehicles, and dense traffic without identifiable entering events are NOT positives.
- Only label positive if there is a clear, identifiable moment where an object enters the ego path or creates a spatial conflict.
- Be conservative. If uncertain, use abstain.

Respond with a single JSON object only — no markdown, no explanation:
{
  "conservative_positive": "yes/no/abstain",
  "risk_level": "L0/L1/L2/L3/L4",
  "affected_ego": true/false,
  "event_type": "cut_in/crossing/approach/hard_brake/dense_traffic/other/none",
  "starts_outside_ego_path": true/false,
  "enters_ego_path": true/false,
  "requires_ego_attention": true/false,
  "evidence": "one sentence describing what you see",
  "confidence": "low/medium/high"
}

Risk levels: L0=no risk, L1=minor attention, L2=moderate potential conflict, L3=clear potential conflict, L4=imminent danger."""

import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

print(f"Loading model from {MODEL_PATH}...")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    gpu_name = torch.cuda.get_device_name(0)
    mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {gpu_name}, memory: {mem_total:.1f} GB")

t0 = time.time()
model = Qwen3VLForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
load_time = time.time() - t0
print(f"Model loaded in {load_time:.1f}s")

# Get peak GPU memory after loading
if torch.cuda.is_available():
    mem_used = torch.cuda.max_memory_allocated() / 1024**3
    mem_reserved = torch.cuda.max_memory_reserved() / 1024**3
    print(f"Peak GPU memory after load: allocated={mem_used:.1f}GB, reserved={mem_reserved:.1f}GB")

# Use ffmpeg to extract frames for each clip
import cv2
import subprocess
import numpy as np

def extract_clip_frames(clip_start, clip_end, fps=2):
    """Extract frames from video at given fps within [clip_start, clip_end]."""
    frames = []
    cap = cv2.VideoCapture(VIDEO_PATH)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(1, int(video_fps / fps))

    start_frame = int(clip_start * video_fps)
    end_frame = int(clip_end * video_fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_idx = start_frame

    while frame_idx <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (frame_idx - start_frame) % frame_interval == 0:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
        frame_idx += 1
    cap.release()
    return frames

# Run inference
results = []
t0_infer = time.time()
positive_count = 0
negative_count = 0
abstain_count = 0
failed_calls = 0
runtimes = []

for i, sample in enumerate(samples):
    clip_id = sample["clip_id"]
    start_t = float(sample["start_time"])
    end_t = float(sample["end_time"])
    print(f"[{i+1}/{len(samples)}] {clip_id} [{start_t:.0f}s - {end_t:.0f}s] source={sample['sample_source']}", end=" ")

    try:
        # Extract frames
        frames = extract_clip_frames(start_t, end_t, fps=2)
        if len(frames) == 0:
            print("NO_FRAMES")
            failed_calls += 1
            results.append({
                "clip_id": clip_id, "start_time": sample["start_time"], "end_time": sample["end_time"],
                "conservative_positive": "abstain", "risk_level": "L0", "event_type": "none",
                "starts_outside_ego_path": "false", "enters_ego_path": "false",
                "requires_ego_attention": "false", "confidence": "low",
                "evidence": "VLM call failed: no frames extracted",
                "raw_response_path": "", "runtime_seconds": 0, "vlm_call_status": "failed_no_frames",
            })
            continue

        # Build messages
        from PIL import Image
        pil_frames = [Image.fromarray(f) for f in frames]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "video", "video": pil_frames, "fps": 2.0},
                {"type": "text", "text": "Analyze this driving clip for O_enter_ego_path_v0 events. Output JSON only."}
            ]}
        ]

        # Prepare inputs
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt"
        )
        inputs = inputs.to(model.device)

        t1 = time.time()
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]
        runtime = time.time() - t1
        runtimes.append(runtime)

        # Save raw response
        resp_path = f"{ROOT}/raw_vlm_responses/pilot/{clip_id}.json"
        raw_data = {
            "clip_id": clip_id, "start_time": sample["start_time"], "end_time": sample["end_time"],
            "sample_source": sample["sample_source"],
            "raw_output": output_text,
            "runtime_seconds": runtime,
            "model": "Qwen3-VL-32B-Instruct",
            "prompt_version": "O_enter_ego_path_v0_v13_5",
        }

        # Parse JSON from output
        try:
            # Find JSON in output
            import re
            json_match = re.search(r'\{[^{}]*\}', output_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
            else:
                parsed = {"conservative_positive": "abstain", "error": "no_json_found"}
        except json.JSONDecodeError:
            parsed = {"conservative_positive": "abstain", "error": "json_parse_error"}

        raw_data["parsed"] = parsed
        with open(resp_path, "w") as f:
            json.dump(raw_data, f, indent=2)

        cp = parsed.get("conservative_positive", "abstain")
        if cp == "yes":
            # Check positive rule
            starts = str(parsed.get("starts_outside_ego_path", "")).lower()
            enters = str(parsed.get("enters_ego_path", "")).lower()
            attention = str(parsed.get("requires_ego_attention", "")).lower()
            conf = str(parsed.get("confidence", "")).lower()
            if starts == "true" and enters == "true" and attention == "true" and conf != "low":
                positive_count += 1
                print(f"POSITIVE (conf={conf}, type={parsed.get('event_type','?')})")
            else:
                cp = "negative"  # Reclassify as negative per rules
                negative_count += 1
                print(f"NEGATIVE (failed positive rule: starts={starts}, enters={enters}, attention={attention}, conf={conf})")
        elif cp == "no":
            negative_count += 1
            print(f"NEGATIVE")
        else:
            abstain_count += 1
            print(f"ABSTAIN")

        results.append({
            "clip_id": clip_id, "start_time": sample["start_time"], "end_time": sample["end_time"],
            "sample_source": sample["sample_source"],
            "conservative_positive": cp,
            "risk_level": parsed.get("risk_level", "L0"),
            "event_type": parsed.get("event_type", "none"),
            "starts_outside_ego_path": str(parsed.get("starts_outside_ego_path", "")),
            "enters_ego_path": str(parsed.get("enters_ego_path", "")),
            "requires_ego_attention": str(parsed.get("requires_ego_attention", "")),
            "confidence": parsed.get("confidence", "low"),
            "evidence": parsed.get("evidence", "")[:200],
            "raw_response_path": resp_path,
            "runtime_seconds": runtime,
            "vlm_call_status": "ok",
        })

    except Exception as e:
        print(f"ERROR: {e}")
        failed_calls += 1
        results.append({
            "clip_id": clip_id, "start_time": sample["start_time"], "end_time": sample["end_time"],
            "sample_source": sample["sample_source"],
            "conservative_positive": "abstain", "risk_level": "L0", "event_type": "none",
            "starts_outside_ego_path": "false", "enters_ego_path": "false",
            "requires_ego_attention": "false", "confidence": "low",
            "evidence": f"VLM call error: {str(e)[:150]}",
            "raw_response_path": "", "runtime_seconds": 0, "vlm_call_status": f"error: {str(e)[:80]}",
        })

total_infer_time = time.time() - t0_infer

# Write labels CSV
fieldnames = list(results[0].keys())
with open(f"{ROOT}/tables/vlm_pilot_labels.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)
print(f"\nWritten {len(results)} rows to vlm_pilot_labels.csv")

# Statistics
pos_by_source = {}
for r in results:
    src = r.get("sample_source", "unknown")
    pos_by_source.setdefault(src, {"total": 0, "positive": 0})
    pos_by_source[src]["total"] += 1
    if r["conservative_positive"] == "yes":
        pos_by_source[src]["positive"] += 1

print(f"\n=== VLM PILOT SUMMARY ===")
print(f"Total clips: {len(results)}")
print(f"Positive: {positive_count}")
print(f"Negative: {negative_count}")
print(f"Abstain: {abstain_count}")
print(f"Failed: {failed_calls}")
print(f"Positive rate: {positive_count/len(results):.4f}")
print(f"Abstain rate: {abstain_count/len(results):.4f}")
print(f"Mean runtime: {sum(runtimes)/len(runtimes):.1f}s" if runtimes else "No runtimes")
print(f"Total inference time: {total_infer_time:.0f}s")
for src, counts in pos_by_source.items():
    print(f"  {src}: {counts['positive']}/{counts['total']} positive")
if torch.cuda.is_available():
    print(f"Peak GPU mem allocated: {torch.cuda.max_memory_allocated()/1024**3:.1f}GB")
    print(f"Peak GPU mem reserved: {torch.cuda.max_memory_reserved()/1024**3:.1f}GB")

# Decision
print(f"\n=== STAGE 3 DECISION ===")
pos_rate = positive_count / len(results)
abstain_rate = abstain_count / len(results)
if positive_count >= 5 or pos_rate >= 0.03:
    if abstain_rate <= 0.30:
        print("PROCEED_FULL_ORACLE")
    else:
        print(f"PILOT_UNSTABLE (abstain_rate={abstain_rate:.3f} > 0.30)")
else:
    if positive_count < 3:
        print(f"REVISE_QUERY_OR_VIDEO (positive_count={positive_count} < 3)")
    else:
        print(f"PROCEED_FULL_ORACLE (positive_count={positive_count} >= 3 but < 5, rate={pos_rate:.3f})")
