#!/usr/bin/env python3
"""Stage 1: Boundary-Fix Smoke Test.

Tests 3 input schemes on selected anchors (5 positives + 5 high-score negs + 4 medium negs)
to determine which produces non-degenerate event boundaries.

Scheme A: video metadata fix (pass raw_fps=30 so VLM gets correct temporal context)
Scheme B: timestamped contact sheet (5-frame grid image with timestamp overlays)
Scheme C: post-hoc boundary localization (positives only, explicit boundary query)

VLM_ORACLE_RELATIVE labels. No human truth.
"""
import csv, json, os, re, sys, time, argparse, math
import cv2, torch, numpy as np
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

OUT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt"
VIDEO_ID = "dataset3"
P1_CSV = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/oracle_outputs/dataset3_oracle_parsed.csv"

SCHEME_OUT = f"{OUT}/oracle_outputs/stage1_boundary_smoke"
os.makedirs(SCHEME_OUT, exist_ok=True)

# Load prompt
with open(PROMPT_PATH) as f:
    PROMPT_TEXT = f.read()

# Post-hoc boundary prompt (Scheme C)
POSTHOC_PROMPT = """You are a driving safety analyst. The following video clip (10 seconds long, frames sampled at 2fps) contains an "object enters ego path" event — a road user (vehicle, pedestrian, or cyclist) enters the ego vehicle's future driving path.

Your task: localize the event's temporal boundary within this 10-second clip.

The clip starts at t=0.0s and ends at t=10.0s. Each frame is 0.5s apart (2fps).

Respond with a single JSON object only:
{
  "event_start": <float, seconds from clip start, 0.0-10.0>,
  "event_end": <float, seconds from clip start, 0.0-10.0>,
  "event_duration": <float, seconds>,
  "before_event": "what happens before the event starts",
  "during_event": "what happens during the event",
  "after_event": "what happens after the event ends",
  "boundary_confidence": "high | medium | low",
  "boundary_status": "ok | truncated_start | truncated_end | truncated_both | uncertain",
  "involved_object": "vehicle | pedestrian | cyclist | other",
  "evidence": "brief evidence for the boundary localization"
}
"""

# Select anchors from P1 results
p1_rows = list(csv.DictReader(open(P1_CSV)))
positives = [r for r in p1_rows if r["label"] == "positive"]
negatives = [r for r in p1_rows if r["label"] == "negative"]

# 5 positives
positive_anchors = [(r["anchor_id"], float(r["start_time"]), float(r["end_time"])) for r in positives]

# 5 high-score negatives (by proxy score, from the anchor plan)
anchor_plan = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/dataset3_anchor_plan.csv"
plan_rows = {r["anchor_id"]: r for r in csv.DictReader(open(anchor_plan))}
neg_with_scores = [(r, float(plan_rows.get(r["anchor_id"], {}).get("score_fusion_geometry_motion", "-999"))) for r in negatives]
neg_with_scores.sort(key=lambda x: -x[1])
high_score_neg_anchors = [(r["anchor_id"], float(r["start_time"]), float(r["end_time"])) for r, _ in neg_with_scores[:5]]

# 4 medium/diverse negatives (from different time regions)
medium_negs = [r for r in negatives if r not in [x[0] for x in neg_with_scores[:5]]]
# spread across video
medium_negs.sort(key=lambda r: float(r["anchor_time"]))
step = max(1, len(medium_negs) // 4)
medium_neg_anchors = [(medium_negs[i]["anchor_id"], float(medium_negs[i]["start_time"]), float(medium_negs[i]["end_time"])) for i in range(0, len(medium_negs), step)][:4]

all_anchors = positive_anchors + high_score_neg_anchors + medium_neg_anchors
print(f"Stage 1 anchors: {len(positive_anchors)} positives + {len(high_score_neg_anchors)} high-score negs + {len(medium_neg_anchors)} medium negs = {len(all_anchors)}")

# Video fps
cap_ref = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap_ref.get(cv2.CAP_PROP_FPS)
total_frames = int(cap_ref.get(cv2.CAP_PROP_FRAME_COUNT))
cap_ref.release()
print(f"Video: {video_fps:.3f}fps, {total_frames} frames, {total_frames/video_fps:.1f}s")

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

def make_contact_sheet(frames, clip_start, clip_duration=10.0, n_frames=5):
    """Create a contact sheet with timestamp annotations."""
    if len(frames) < n_frames:
        n_frames = len(frames)
    # Select n_frames uniformly
    indices = np.linspace(0, len(frames) - 1, n_frames, dtype=int)
    selected = [frames[i] for i in indices]
    timestamps = [clip_start + (i / (n_frames - 1)) * clip_duration for i in range(n_frames)]

    # Resize each frame to 480x270
    w, h = 480, 270
    resized = [Image.fromarray(f).resize((w, h)) for f in selected]

    # Create contact sheet: 1 row x n_frames cols
    margin = 10
    label_h = 30
    sheet_w = n_frames * w + (n_frames + 1) * margin
    sheet_h = h + label_h + 2 * margin
    sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()

    for i, (img, ts) in enumerate(zip(resized, timestamps)):
        x = margin + i * (w + margin)
        y = margin
        sheet.paste(img, (x, y))
        # Draw timestamp
        label = f"t={ts:.1f}s"
        draw.text((x + 5, y + h + 5), label, fill=(0, 0, 0), font=font)

    return sheet

# Load model
print(f"\nLoading {MODEL_PATH}...")
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

t0 = time.time()
model = Qwen3VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
print(f"Model loaded in {time.time()-t0:.0f}s")

def run_vlm_video(frames, prompt, raw_fps=None, max_new_tokens=256):
    """Run VLM with video input (list of PIL frames)."""
    pil_frames = [Image.fromarray(f) for f in frames]
    video_ele = {"type": "video", "video": pil_frames, "fps": 2.0}
    if raw_fps is not None:
        video_ele["raw_fps"] = raw_fps
    messages = [{"role": "user", "content": [video_ele, {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                       padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    t1 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, temperature=0.1)
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    runtime = time.time() - t1
    del inputs, generated_ids, pil_frames
    torch.cuda.empty_cache()
    return output_text, runtime

def run_vlm_image(image, prompt, max_new_tokens=256):
    """Run VLM with single image input (contact sheet)."""
    messages = [{"role": "user", "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": prompt}
    ]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                       padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    t1 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, temperature=0.1)
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    runtime = time.time() - t1
    del inputs, generated_ids
    torch.cuda.empty_cache()
    return output_text, runtime

def parse_json(text):
    # Greedy match from first { to last } to capture full JSON
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0)), "ok"
    except Exception as e:
        return {"_parse_error": str(e)[:80]}, "parse_error"
    return {}, "parse_error"

# Results storage
results = []

# ============ Scheme A: video metadata fix (raw_fps=30) ============
print("\n" + "="*60)
print("Scheme A: Video metadata fix (raw_fps=30)")
print("="*60)

for i, (aid, start_t, end_t) in enumerate(all_anchors):
    sys.stdout.write(f"\r[A {i+1}/{len(all_anchors)}] {aid} ")
    sys.stdout.flush()
    try:
        frames = extract_frames(start_t, end_t, fps=2.0)
        if len(frames) < 5:
            frames = extract_frames(start_t, end_t, fps=4.0)
        output, runtime = run_vlm_video(frames, PROMPT_TEXT, raw_fps=30.0)
        parsed, ps = parse_json(output)
        results.append({
            "scheme": "A_video_metadata", "anchor_id": aid,
            "start_time": start_t, "end_time": end_t,
            "label": parsed.get("label", "abstain"),
            "event_start": str(parsed.get("event_start", "")),
            "event_end": str(parsed.get("event_end", "")),
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "confidence": parsed.get("confidence", "low"),
            "evidence": (parsed.get("evidence", "") or "")[:150],
            "negative_reason": parsed.get("negative_reason", "null"),
            "runtime": f"{runtime:.1f}",
            "parse_status": ps,
            "raw": output[:800],
        })
        with open(f"{SCHEME_OUT}/{aid}_A.json", "w") as f:
            json.dump({"anchor_id": aid, "scheme": "A", "raw": output, "parsed": parsed, "runtime": runtime}, f, indent=2, ensure_ascii=False)
        print(f"-> {parsed.get('label','')} [{parsed.get('event_start','')}-{parsed.get('event_end','')}]", end="")
    except Exception as e:
        print(f" ERR: {e}", end="")
        results.append({"scheme": "A_video_metadata", "anchor_id": aid, "parse_status": f"error:{str(e)[:60]}"})

# ============ Scheme B: timestamped contact sheet ============
print("\n\n" + "="*60)
print("Scheme B: Timestamped contact sheet")
print("="*60)

CONTACT_SHEET_PROMPT = """You are a driving safety analyst. Below is a contact sheet showing 5 frames from a 10-second driving video clip, sampled at uniform intervals. Each frame has a timestamp label showing the time in seconds from the start of the clip.

""" + PROMPT_TEXT

for i, (aid, start_t, end_t) in enumerate(all_anchors):
    sys.stdout.write(f"\r[B {i+1}/{len(all_anchors)}] {aid} ")
    sys.stdout.flush()
    try:
        frames = extract_frames(start_t, end_t, fps=2.0)
        if len(frames) < 5:
            frames = extract_frames(start_t, end_t, fps=4.0)
        sheet = make_contact_sheet(frames, start_t, clip_duration=10.0, n_frames=5)
        output, runtime = run_vlm_image(sheet, CONTACT_SHEET_PROMPT)
        parsed, ps = parse_json(output)
        results.append({
            "scheme": "B_contact_sheet", "anchor_id": aid,
            "start_time": start_t, "end_time": end_t,
            "label": parsed.get("label", "abstain"),
            "event_start": str(parsed.get("event_start", "")),
            "event_end": str(parsed.get("event_end", "")),
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "confidence": parsed.get("confidence", "low"),
            "evidence": (parsed.get("evidence", "") or "")[:150],
            "negative_reason": parsed.get("negative_reason", "null"),
            "runtime": f"{runtime:.1f}",
            "parse_status": ps,
            "raw": output[:800],
        })
        with open(f"{SCHEME_OUT}/{aid}_B.json", "w") as f:
            json.dump({"anchor_id": aid, "scheme": "B", "raw": output, "parsed": parsed, "runtime": runtime}, f, indent=2, ensure_ascii=False)
        print(f"-> {parsed.get('label','')} [{parsed.get('event_start','')}-{parsed.get('event_end','')}]", end="")
    except Exception as e:
        print(f" ERR: {e}", end="")
        results.append({"scheme": "B_contact_sheet", "anchor_id": aid, "parse_status": f"error:{str(e)[:60]}"})

# ============ Scheme C: post-hoc boundary localization (positives only) ============
print("\n\n" + "="*60)
print("Scheme C: Post-hoc boundary localization (positives only)")
print("="*60)

for i, (aid, start_t, end_t) in enumerate(positive_anchors):
    sys.stdout.write(f"\r[C {i+1}/{len(positive_anchors)}] {aid} ")
    sys.stdout.flush()
    try:
        frames = extract_frames(start_t, end_t, fps=2.0)
        if len(frames) < 5:
            frames = extract_frames(start_t, end_t, fps=4.0)
        output, runtime = run_vlm_video(frames, POSTHOC_PROMPT, raw_fps=30.0, max_new_tokens=300)
        parsed, ps = parse_json(output)
        results.append({
            "scheme": "C_posthoc_boundary", "anchor_id": aid,
            "start_time": start_t, "end_time": end_t,
            "label": "positive",  # known positive
            "event_start": str(parsed.get("event_start", "")),
            "event_end": str(parsed.get("event_end", "")),
            "event_type": "enter_ego_path",
            "involved_object": parsed.get("involved_object", "none"),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "confidence": parsed.get("boundary_confidence", "low"),
            "evidence": (parsed.get("evidence", "") or "")[:150],
            "negative_reason": "null",
            "runtime": f"{runtime:.1f}",
            "parse_status": ps,
            "raw": output[:800],
        })
        with open(f"{SCHEME_OUT}/{aid}_C.json", "w") as f:
            json.dump({"anchor_id": aid, "scheme": "C", "raw": output, "parsed": parsed, "runtime": runtime}, f, indent=2, ensure_ascii=False)
        print(f"-> [{parsed.get('event_start','')}-{parsed.get('event_end','')}]", end="")
    except Exception as e:
        print(f" ERR: {e}", end="")
        results.append({"scheme": "C_posthoc_boundary", "anchor_id": aid, "parse_status": f"error:{str(e)[:60]}"})

# Save results
csv_path = f"{OUT}/analysis/stage1_boundary_scheme_comparison.csv"
fields = ["scheme", "anchor_id", "start_time", "end_time", "label", "event_start", "event_end",
          "event_type", "involved_object", "boundary_status", "confidence", "evidence",
          "negative_reason", "runtime", "parse_status", "raw"]
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in results:
        w.writerow({k: r.get(k, "") for k in fields})
print(f"\n\nSaved {len(results)} results to {csv_path}")

# Summary
print("\n=== Scheme A (video metadata) ===")
a_results = [r for r in results if r.get("scheme") == "A_video_metadata"]
a_pos = [r for r in a_results if r.get("label") == "positive"]
a_starts = [r.get("event_start", "") for r in a_pos]
a_ends = [r.get("event_end", "") for r in a_pos]
print(f"  Positives: {len(a_pos)}, event_starts: {a_starts}, event_ends: {a_ends}")
print(f"  Unique starts: {len(set(a_starts))}, unique ends: {len(set(a_ends))}")

print("\n=== Scheme B (contact sheet) ===")
b_results = [r for r in results if r.get("scheme") == "B_contact_sheet"]
b_pos = [r for r in b_results if r.get("label") == "positive"]
b_starts = [r.get("event_start", "") for r in b_pos]
b_ends = [r.get("event_end", "") for r in b_pos]
print(f"  Positives: {len(b_pos)}, event_starts: {b_starts}, event_ends: {b_ends}")
print(f"  Unique starts: {len(set(b_starts))}, unique ends: {len(set(b_ends))}")

print("\n=== Scheme C (post-hoc boundary) ===")
c_results = [r for r in results if r.get("scheme") == "C_posthoc_boundary"]
c_starts = [r.get("event_start", "") for r in c_results if r.get("parse_status") == "ok"]
c_ends = [r.get("event_end", "") for r in c_results if r.get("parse_status") == "ok"]
print(f"  event_starts: {c_starts}, event_ends: {c_ends}")
print(f"  Unique starts: {len(set(c_starts))}, unique ends: {len(set(c_ends))}")

# Label stability check (A vs P1)
print("\n=== Label stability (Scheme A vs P1) ===")
p1_labels = {r["anchor_id"]: r["label"] for r in p1_rows}
for r in a_results:
    aid = r["anchor_id"]
    p1l = p1_labels.get(aid, "?")
    al = r.get("label", "?")
    match = "MATCH" if p1l == al else "MISMATCH"
    print(f"  {aid}: P1={p1l} -> A={al} [{match}]")
