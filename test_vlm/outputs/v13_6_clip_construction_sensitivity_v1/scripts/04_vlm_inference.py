#!/usr/bin/env python3
"""Stage 4: Run Qwen3-VL-32B on all constructed clips. Resumable."""

import csv, json, os, re, sys, time, numpy as np, cv2, torch
from PIL import Image
from collections import Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
SAMPLES_CSV = f"{ROOT}/tables/clip_construction_samples.csv"
OUTPUT_CSV = f"{ROOT}/tables/clip_construction_vlm_labels.csv"
RESP_DIR = f"{ROOT}/raw_vlm_responses"

os.makedirs(RESP_DIR, exist_ok=True)

# Load prompt
with open(f"{ROOT}/prompts/o_enter_ego_path_v0_v13_6_prompt.txt") as f:
    PROMPT_TEXT = f.read()

# Load samples
samples = list(csv.DictReader(open(SAMPLES_CSV)))
print(f"Loaded {len(samples)} samples")

# Check already completed
existing_ids = set()
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        for row in csv.DictReader(f):
            if row.get("vlm_call_status","") == "ok":
                existing_ids.add(row["sample_id"])
    print(f"Already completed: {len(existing_ids)} — will skip")

# Load model
print(f"\nLoading model from {MODEL_PATH}...")
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

t0 = time.time()
model = Qwen3VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
print(f"Model loaded in {time.time()-t0:.0f}s")

gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
print(f"GPU: {gpu_name}")

cap_ref = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap_ref.get(cv2.CAP_PROP_FPS)
cap_ref.release()

def extract_frames(clip_start, clip_end, fps=2.0):
    """Extract frames from video at given fps."""
    frames = []
    cap = cv2.VideoCapture(VIDEO_PATH)
    start_frame = int(clip_start * video_fps)
    end_frame = int(clip_end * video_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_interval = max(1, int(video_fps / fps))
    for fi in range(start_frame, end_frame + 1):
        ret, frame = cap.read()
        if not ret:
            break
        if (fi - start_frame) % frame_interval == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames

def extract_contact_sheet_frames(center_t, n_frames):
    """Extract uniformly spaced frames from [center_t-5, center_t+5]."""
    clip_start = max(0.0, center_t - 5.0)
    clip_end = min(VIDEO_DURATION := 3987.104, center_t + 5.0)  # use correct duration
    clip_end = min(3987.104, center_t + 5.0)
    all_frames = extract_frames(clip_start, clip_end, fps=24.0)
    if len(all_frames) <= n_frames:
        return all_frames
    indices = np.linspace(0, len(all_frames)-1, n_frames, dtype=int)
    return [all_frames[i] for i in indices]

def run_vlm_video(frames, clip_duration):
    """Run VLM on video frames."""
    pil_frames = [Image.fromarray(f) for f in frames]
    messages = [
        {"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": 2.0},
            {"type": "text", "text": PROMPT_TEXT}
        ]}
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    t1 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    runtime = time.time() - t1
    return output_text, runtime

def run_vlm_contact_sheet(frames):
    """Run VLM on contact sheet (list of images)."""
    pil_frames = [Image.fromarray(f) for f in frames]
    content = [{"type": "image", "image": img} for img in pil_frames]
    content.append({"type": "text", "text": PROMPT_TEXT + "\n\nThese are uniformly sampled frames from a 10-second driving clip. Analyze for O_enter_ego_path_v0 events."})
    messages = [{"role": "user", "content": content}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    t1 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    runtime = time.time() - t1
    return output_text, runtime

def parse_response(output_text):
    """Parse JSON from VLM output."""
    try:
        json_match = re.search(r'\{[^{}]*\}', output_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except:
        pass
    return {"label": "abstain", "error": "json_parse_failed"}

# Process
fieldnames = [
    "sample_id", "source_pilot_clip_id", "source_pilot_label", "construction_policy",
    "input_mode", "center_time", "start_time", "end_time", "duration",
    "model_name", "device_name", "dtype", "quantization", "input_mode_used",
    "frames_used", "max_pixels", "runtime_seconds", "peak_gpu_memory_gb",
    "label", "event_start", "event_end", "event_type", "involved_object",
    "ego_relevant", "boundary_status", "complete_event_visible", "confidence",
    "evidence", "negative_reason", "abstain_reason",
    "raw_output_truncated", "vlm_call_status"
]

all_results = list(existing_ids)  # track completed
results_rows = []
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        results_rows = list(csv.DictReader(f))

pending = [s for s in samples if s["sample_id"] not in existing_ids]
print(f"Pending: {len(pending)}/{len(samples)}")

t_start = time.time()
for i, sample in enumerate(pending):
    sid = sample["sample_id"]
    policy = sample["construction_policy"]
    start_t = float(sample["start_time"])
    end_t = float(sample["end_time"])
    duration = float(sample["duration"])
    center_t = float(sample["center_time"])
    input_mode = sample["input_mode"]

    sys.stdout.write(f"\r[{i+1}/{len(pending)}] {sid} policy={policy} dur={duration:.1f}s ")
    sys.stdout.flush()

    try:
        if input_mode == "video":
            fps = max(1.0, min(2.0, 10.0 / duration))  # at least 5 frames
            frames = extract_frames(start_t, end_t, fps=fps)
            if len(frames) < 3:
                frames = extract_frames(start_t, end_t, fps=24.0)
                if len(frames) > 10:
                    idx = np.linspace(0, len(frames)-1, 10, dtype=int)
                    frames = [frames[j] for j in idx]
            output_text, runtime = run_vlm_video(frames, duration)
            frames_used = len(frames)
        else:
            n_frames = int(sample.get("num_frames_if_contact_sheet", 5) or 5)
            frames = extract_contact_sheet_frames(center_t, n_frames)
            output_text, runtime = run_vlm_contact_sheet(frames)
            frames_used = len(frames)

        parsed = parse_response(output_text)

        if torch.cuda.is_available():
            peak_mem = torch.cuda.max_memory_allocated() / 1024**3
        else:
            peak_mem = 0.0

        row = {
            "sample_id": sid,
            "source_pilot_clip_id": sample["source_pilot_clip_id"],
            "source_pilot_label": sample["source_pilot_label"],
            "construction_policy": policy,
            "input_mode": input_mode,
            "center_time": sample["center_time"],
            "start_time": sample["start_time"],
            "end_time": sample["end_time"],
            "duration": sample["duration"],
            "model_name": "Qwen3-VL-32B-Instruct",
            "device_name": gpu_name,
            "dtype": "bfloat16",
            "quantization": "none",
            "input_mode_used": input_mode,
            "frames_used": str(frames_used),
            "max_pixels": "1920x1080",
            "runtime_seconds": f"{runtime:.1f}",
            "peak_gpu_memory_gb": f"{peak_mem:.1f}",
            "label": parsed.get("label", "abstain"),
            "event_start": str(parsed.get("event_start", "")),
            "event_end": str(parsed.get("event_end", "")),
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "ego_relevant": str(parsed.get("ego_relevant", "")),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": str(parsed.get("complete_event_visible", "")),
            "confidence": parsed.get("confidence", "low"),
            "evidence": (parsed.get("evidence", "") or "")[:200],
            "negative_reason": parsed.get("negative_reason", "null"),
            "abstain_reason": parsed.get("abstain_reason", "null"),
            "raw_output_truncated": output_text[:300],
            "vlm_call_status": "ok",
        }

        # Save raw response
        resp_path = f"{RESP_DIR}/{sid}.json"
        with open(resp_path, "w") as f:
            json.dump({"sample_id": sid, "policy": policy, "raw": output_text, "parsed": parsed, "runtime": runtime}, f, indent=2)

        results_rows.append(row)
        all_results.append(sid)

        # Incrementally save every 10 results
        if (i+1) % 10 == 0:
            with open(OUTPUT_CSV, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results_rows)
            elapsed = time.time() - t_start
            rate = (i+1) / elapsed * 3600
            print(f"  [saved, {rate:.0f}/hr, {elapsed/60:.1f}min elapsed]")

    except Exception as e:
        print(f"  ERROR: {e}")
        row = {k: "" for k in fieldnames}
        row.update({"sample_id": sid, "construction_policy": policy,
                     "label": "abstain", "vlm_call_status": f"error: {str(e)[:100]}"})
        results_rows.append(row)

# Final save
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results_rows)

total_time = time.time() - t_start
print(f"\n\nComplete: {len(results_rows)} results in {total_time/60:.1f} min")
labels = Counter(r["label"] for r in results_rows)
print(f"Labels: {dict(labels)}")
