#!/usr/bin/env python3
"""V13.8 Full Center10 Oracle Reference — Qwen3-VL-32B on all 399 anchors. Resumable."""
import csv, json, os, re, sys, time, numpy as np, cv2, torch
from collections import Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
V13_7 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"
V13_6 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
ANCHOR_CSV = f"{V13_7}/tables/center10_anchor_grid.csv"
OUTPUT_CSV = f"{ROOT}/tables/center10_full_oracle_labels.csv"
EVENTS_CSV = f"{ROOT}/tables/center10_vlm_oracle_events.csv"
TRACE_CSV = f"{ROOT}/tables/center10_event_stitching_trace.csv"
RESP_DIR = f"{ROOT}/raw_vlm_responses"

for d in ["tables","reports","logs","raw_vlm_responses"]:
    os.makedirs(f"{ROOT}/{d}", exist_ok=True)

# Load prompt
with open(f"{V13_6}/prompts/o_enter_ego_path_v0_v13_6_prompt.txt") as f:
    PROMPT_TEXT = f.read()

# Load anchors
anchors = list(csv.DictReader(open(ANCHOR_CSV)))
print(f"Loaded {len(anchors)} anchors")

# Check already completed
existing_ids = set()
existing_responses = set()
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        for row in csv.DictReader(f):
            if row.get("parse_status","") in ("ok","parse_error"):
                existing_ids.add(row["anchor_id"])
    print(f"Already completed in CSV: {len(existing_ids)}")
# Also check raw responses
if os.path.exists(RESP_DIR):
    for fname in os.listdir(RESP_DIR):
        if fname.endswith(".json"):
            existing_responses.add(fname.replace(".json",""))
    print(f"Raw responses on disk: {len(existing_responses)}")

existing_ids = existing_ids | existing_responses

pending = [a for a in anchors if a["anchor_id"] not in existing_ids]
print(f"Pending: {len(pending)}/{len(anchors)}")

if len(pending) == 0:
    print("All anchors processed. Skipping VLM inference.")
    sys.exit(0)

# Load model
print(f"\nLoading {MODEL_PATH}...")
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

# Load existing results
all_results = []
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV) as f:
        all_results = list(csv.DictReader(f))

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

FIELDNAMES = [
    "anchor_id","video_id","anchor_time","start_time","end_time","duration",
    "label","event_start","event_end","event_start_absolute","event_end_absolute",
    "event_type","involved_object","ego_relevant","boundary_status","complete_event_visible",
    "confidence","evidence","negative_reason","abstain_reason",
    "runtime_seconds","raw_response_path","parse_status"
]

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

        from PIL import Image
        pil_frames = [Image.fromarray(f) for f in frames]
        messages = [{"role": "user", "content": [
            {"type": "video", "video": pil_frames, "fps": 2.0},
            {"type": "text", "text": PROMPT_TEXT}
        ]}]

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
        ev_start_abs = start_t + float(ev_start_rel) if ev_start_rel not in (None, "", "null") and str(ev_start_rel).replace(".","").replace("-","").isdigit() else ""
        ev_end_abs = start_t + float(ev_end_rel) if ev_end_rel not in (None, "", "null") and str(ev_end_rel).replace(".","").replace("-","").isdigit() else ""

        row = {
            "anchor_id": aid, "video_id": "realcartest",
            "anchor_time": anchor["anchor_time"], "start_time": anchor["start_time"],
            "end_time": anchor["end_time"], "duration": anchor["duration"],
            "label": label,
            "event_start": str(ev_start_rel) if ev_start_rel is not None else "",
            "event_end": str(ev_end_rel) if ev_end_rel is not None else "",
            "event_start_absolute": str(ev_start_abs),
            "event_end_absolute": str(ev_end_abs),
            "event_type": parsed.get("event_type","none"),
            "involved_object": parsed.get("involved_object","none"),
            "ego_relevant": str(parsed.get("ego_relevant","")),
            "boundary_status": parsed.get("boundary_status","not_applicable"),
            "complete_event_visible": str(parsed.get("complete_event_visible","")),
            "confidence": parsed.get("confidence","low"),
            "evidence": (parsed.get("evidence","") or "")[:200],
            "negative_reason": parsed.get("negative_reason","null"),
            "abstain_reason": parsed.get("abstain_reason","null"),
            "runtime_seconds": f"{runtime:.1f}",
            "raw_response_path": f"{RESP_DIR}/{aid}.json",
            "parse_status": parse_status,
        }

        # Save raw
        with open(f"{RESP_DIR}/{aid}.json","w") as f:
            json.dump({"anchor_id":aid,"raw":output_text,"parsed":parsed,"runtime":runtime}, f, indent=2)

        all_results.append(row)
        print(f"-> {label}", end="")

    except Exception as e:
        print(f" ERROR: {e}")
        row = {k: "" for k in FIELDNAMES}
        row.update({"anchor_id": aid, "label": "abstain", "parse_status": f"error: {str(e)[:80]}"})
        all_results.append(row)

    # Incremental save every 25
    if (i+1) % 25 == 0:
        with open(OUTPUT_CSV,"w",newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            w.writeheader(); w.writerows(all_results)
        elapsed = time.time() - t_start
        rate = (i+1) / elapsed * 3600
        print(f"  [saved {len(all_results)} rows, {rate:.0f}/hr, {elapsed/60:.1f}min]")

# Final save
with open(OUTPUT_CSV,"w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDNAMES)
    w.writeheader(); w.writerows(all_results)

total_time = time.time() - t_start
print(f"\n\nComplete: {len(all_results)} rows in {total_time/60:.0f} min")
labels = Counter(r["label"] for r in all_results)
print(f"Labels: {dict(labels)}")
