#!/usr/bin/env python3
"""P1 dataset3 semantic oracle pilot — Qwen3-VL-32B on 50 stratified center10 anchors.

Adapted from V13.8 run_full_center10_oracle.py. Same prompt, same VLM call,
same parsing, same CSV schema. Only changes: video path, anchor source, video_id,
output dir. Resumable.

VLM_ORACLE_RELATIVE labels. No human truth. No oracle labels used for generation.
"""
import csv, json, os, re, sys, time, argparse
import cv2, torch
from collections import Counter

OUT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt"
VIDEO_ID = "dataset3"

ANCHOR_PLAN = f"{OUT}/metadata/dataset3_anchor_plan.csv"
OUTPUT_CSV = f"{OUT}/oracle_outputs/dataset3_oracle_parsed.csv"
RAW_JSONL = f"{OUT}/oracle_outputs/dataset3_oracle_raw.jsonl"
RESP_DIR = f"{OUT}/oracle_outputs/raw_per_anchor"

for d in ["oracle_outputs", "logs", "figures"]:
    os.makedirs(f"{OUT}/{d}", exist_ok=True)
os.makedirs(RESP_DIR, exist_ok=True)

FIELDNAMES = [
    "anchor_id", "video_id", "anchor_time", "start_time", "end_time", "duration",
    "label", "event_start", "event_end", "event_start_absolute", "event_end_absolute",
    "event_type", "involved_object", "ego_relevant", "boundary_status", "complete_event_visible",
    "confidence", "evidence", "negative_reason", "abstain_reason",
    "runtime_seconds", "raw_response_path", "parse_status"
]

# Load prompt (verbatim V13.6 prompt — do not modify for cross-video comparability)
with open(PROMPT_PATH) as f:
    PROMPT_TEXT = f.read()

# Load anchors
anchors = list(csv.DictReader(open(ANCHOR_PLAN)))
print(f"Loaded {len(anchors)} pilot anchors from {ANCHOR_PLAN}")

# Resumability
existing_ids = set()
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        for row in csv.DictReader(f):
            if row.get("parse_status", "") in ("ok", "parse_error"):
                existing_ids.add(row["anchor_id"])
    print(f"Already completed: {len(existing_ids)}")
for fname in os.listdir(RESP_DIR) if os.path.exists(RESP_DIR) else []:
    if fname.endswith(".json"):
        existing_ids.add(fname.replace(".json", ""))
existing_ids = {a for a in existing_ids if a.startswith("center10")}
pending = [a for a in anchors if a["anchor_id"] not in existing_ids]
print(f"Pending: {len(pending)}/{len(anchors)}")

if not pending:
    print("All anchors processed. Exiting.")
    sys.exit(0)

# Load existing results
all_results = []
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        all_results = list(csv.DictReader(f))

# Video fps
cap_ref = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap_ref.get(cv2.CAP_PROP_FPS)
cap_ref.release()
print(f"Video fps: {video_fps:.3f}")

# Load model
print(f"\nLoading {MODEL_PATH}...")
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from PIL import Image

t0 = time.time()
model = Qwen3VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
print(f"Model loaded in {time.time()-t0:.0f}s")
gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
print(f"GPU: {gpu_name}")

def extract_frames(clip_start, clip_end, fps=2.0):
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

# Open JSONL in append mode
jsonl_fh = open(RAW_JSONL, "a")

t_start = time.time()
for i, anchor in enumerate(pending):
    aid = anchor["anchor_id"]
    start_t = float(anchor["start_time"])
    end_t = float(anchor["end_time"])
    sys.stdout.write(f"\r[{i+1}/{len(pending)}] {aid} [{start_t:.0f}s-{end_t:.0f}s] ")
    sys.stdout.flush()

    try:
        frames = extract_frames(start_t, end_t, fps=2.0)
        if len(frames) < 5:
            frames = extract_frames(start_t, end_t, fps=4.0)
        print(f"({len(frames)}fr)", end="")

        pil_frames = [Image.fromarray(f) for f in frames]
        messages = [{"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": 2.0},
            {"type": "text", "text": PROMPT_TEXT}
        ]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                           padding=True, return_tensors="pt")
        inputs = inputs.to(model.device)

        t1 = time.time()
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
        generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
        runtime = time.time() - t1

        # free GPU memory
        del inputs, generated_ids, pil_frames, frames
        torch.cuda.empty_cache()

        # Parse
        try:
            json_match = re.search(r'\{[^{}]*\}', output_text, re.DOTALL)
            parsed = json.loads(json_match.group(0)) if json_match else {}
            parse_status = "ok"
        except:
            parsed = {}
            parse_status = "parse_error"

        label = parsed.get("label", "abstain")
        ev_start_rel = parsed.get("event_start")
        ev_end_rel = parsed.get("event_end")
        def to_abs(rel):
            if rel in (None, "", "null"): return ""
            try: return str(start_t + float(rel))
            except: return ""
        ev_start_abs = to_abs(ev_start_rel)
        ev_end_abs = to_abs(ev_end_rel)

        row = {
            "anchor_id": aid, "video_id": VIDEO_ID,
            "anchor_time": anchor["anchor_time"], "start_time": anchor["start_time"],
            "end_time": anchor["end_time"], "duration": anchor["duration"],
            "label": label,
            "event_start": str(ev_start_rel) if ev_start_rel is not None else "",
            "event_end": str(ev_end_rel) if ev_end_rel is not None else "",
            "event_start_absolute": ev_start_abs,
            "event_end_absolute": ev_end_abs,
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "ego_relevant": str(parsed.get("ego_relevant", "")),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": str(parsed.get("complete_event_visible", "")),
            "confidence": parsed.get("confidence", "low"),
            "evidence": (parsed.get("evidence", "") or "")[:200],
            "negative_reason": parsed.get("negative_reason", "null"),
            "abstain_reason": parsed.get("abstain_reason", "null"),
            "runtime_seconds": f"{runtime:.1f}",
            "raw_response_path": f"{RESP_DIR}/{aid}.json",
            "parse_status": parse_status,
        }

        # Save raw per-anchor JSON
        raw_obj = {"anchor_id": aid, "raw": output_text, "parsed": parsed, "runtime": runtime,
                   "anchor_time": anchor["anchor_time"], "start_time": anchor["start_time"],
                   "end_time": anchor["end_time"]}
        with open(f"{RESP_DIR}/{aid}.json", "w") as f:
            json.dump(raw_obj, f, indent=2, ensure_ascii=False)
        # Append to JSONL
        jsonl_fh.write(json.dumps(raw_obj, ensure_ascii=False) + "\n")
        jsonl_fh.flush()

        all_results.append(row)
        print(f"-> {label} [{parsed.get('event_type','')}|{parsed.get('involved_object','')}]", end="")

    except Exception as e:
        print(f" ERROR: {e}")
        row = {k: "" for k in FIELDNAMES}
        row.update({"anchor_id": aid, "label": "abstain", "parse_status": f"error: {str(e)[:80]}"})
        all_results.append(row)

    # Incremental save every 10
    if (i + 1) % 10 == 0:
        with open(OUTPUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            w.writeheader(); w.writerows(all_results)
        elapsed = time.time() - t_start
        rate = (i + 1) / elapsed * 3600 if elapsed > 0 else 0
        print(f"  [saved {len(all_results)} rows, {rate:.0f}/hr, {elapsed/60:.1f}min]")

# Final save
with open(OUTPUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDNAMES)
    w.writeheader(); w.writerows(all_results)
jsonl_fh.close()

total_time = time.time() - t_start
print(f"\n\nComplete: {len(all_results)} rows in {total_time/60:.1f} min")
labels = Counter(r["label"] for r in all_results)
print(f"Labels: {dict(labels)}")
print(f"Parse status: {dict(Counter(r['parse_status'] for r in all_results))}")
