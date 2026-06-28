#!/usr/bin/env python3
"""Stage 2: Dataset3 Full Center10 Oracle Reference.

Scans all 347 center10 anchors with Qwen3-VL-32B using the V13.6 prompt
(same approach as P1 pilot and V13.8 realcartest). Resumable.

VLM_ORACLE_RELATIVE labels. No human truth. Boundary values are templated
(see Stage 1 report) — clip-level labels are reliable, boundaries are not.
"""
import csv, json, os, re, sys, time
import cv2, torch
from collections import Counter
from PIL import Image

OUT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL_PATH = "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt"
VIDEO_ID = "dataset3"
ANCHOR_CSV = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/center10_proxy_features.csv"
P1_CSV = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/oracle_outputs/dataset3_oracle_parsed.csv"

OUTPUT_CSV = f"{OUT}/oracle_outputs/dataset3_full_center10_parsed.csv"
RAW_JSONL = f"{OUT}/oracle_outputs/dataset3_full_center10_raw.jsonl"
RESP_DIR = f"{OUT}/oracle_outputs/raw_per_anchor_full"
os.makedirs(RESP_DIR, exist_ok=True)

FIELDNAMES = [
    "anchor_id", "video_id", "anchor_time", "start_time", "end_time", "duration",
    "label", "event_start", "event_end", "event_start_absolute", "event_end_absolute",
    "event_type", "involved_object", "ego_relevant", "boundary_status", "complete_event_visible",
    "confidence", "evidence", "negative_reason", "abstain_reason",
    "runtime_seconds", "raw_response_path", "parse_status", "boundary_reliable"
]

with open(PROMPT_PATH) as f:
    PROMPT_TEXT = f.read()

# Load all 347 anchors
anchors = list(csv.DictReader(open(ANCHOR_CSV)))
print(f"Loaded {len(anchors)} anchors from {ANCHOR_CSV}")

# Merge P1 pilot results (reuse those 50 anchors, no need to re-run)
p1_rows = {}
if os.path.exists(P1_CSV):
    for r in csv.DictReader(open(P1_CSV)):
        if r.get("parse_status") == "ok":
            r["boundary_reliable"] = "False"
            p1_rows[r["anchor_id"]] = r
    print(f"P1 pilot results available: {len(p1_rows)} anchors (will be reused)")

# Resumability: check existing full scan results
existing_ids = set()
if os.path.exists(OUTPUT_CSV):
    for r in csv.DictReader(open(OUTPUT_CSV)):
        if r.get("parse_status") in ("ok", "parse_error"):
            existing_ids.add(r["anchor_id"])
    print(f"Already completed in full scan: {len(existing_ids)}")

# Also check raw responses on disk
for fname in os.listdir(RESP_DIR) if os.path.exists(RESP_DIR) else []:
    if fname.endswith(".json"):
        existing_ids.add(fname.replace(".json", ""))

# Pending = all anchors not in P1 and not in existing full scan
pending = [a for a in anchors if a["anchor_id"] not in p1_rows and a["anchor_id"] not in existing_ids]
print(f"Pending VLM calls: {len(pending)}/{len(anchors)} (P1 reused: {len(p1_rows)}, already done: {len(existing_ids - set(p1_rows.keys()))})")

if not pending:
    print("No pending anchors. Building merged output.")
else:
    # Video fps
    cap_ref = cv2.VideoCapture(VIDEO_PATH)
    video_fps = cap_ref.get(cv2.CAP_PROP_FPS)
    cap_ref.release()
    print(f"Video fps: {video_fps:.3f}")

    # Load model
    print(f"\nLoading {MODEL_PATH}...")
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info

    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
    print(f"Model loaded in {time.time()-t0:.0f}s")

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

            del inputs, generated_ids, pil_frames, frames
            torch.cuda.empty_cache()

            # Parse
            try:
                json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
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
                "boundary_reliable": "False",
            }

            raw_obj = {"anchor_id": aid, "raw": output_text, "parsed": parsed, "runtime": runtime,
                       "anchor_time": anchor["anchor_time"], "start_time": anchor["start_time"],
                       "end_time": anchor["end_time"]}
            with open(f"{RESP_DIR}/{aid}.json", "w") as f:
                json.dump(raw_obj, f, indent=2, ensure_ascii=False)
            jsonl_fh.write(json.dumps(raw_obj, ensure_ascii=False) + "\n")
            jsonl_fh.flush()

            print(f"-> {label} [{parsed.get('event_type','')}|{parsed.get('involved_object','')}]", end="")

        except Exception as e:
            print(f" ERROR: {e}", end="")
            row = {k: "" for k in FIELDNAMES}
            row.update({"anchor_id": aid, "label": "abstain", "parse_status": f"error: {str(e)[:80]}", "boundary_reliable": "False"})
            # Don't add error rows to results - they'll be retried

        # Incremental save every 20
        if (i + 1) % 20 == 0:
            # Build merged results from P1 + new
            all_results = list(p1_rows.values())
            if os.path.exists(OUTPUT_CSV):
                for r in csv.DictReader(open(OUTPUT_CSV)):
                    if r["anchor_id"] not in p1_rows and r.get("parse_status") == "ok":
                        all_results.append(r)
            # Add new rows from this session
            # (the row variable is in scope from the loop)
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed * 3600 if elapsed > 0 else 0
            print(f"  [saved, {rate:.0f}/hr, {elapsed/60:.1f}min]", end="")

    jsonl_fh.close()
    total_time = time.time() - t_start
    print(f"\n\nVLM inference complete: {len(pending)} anchors in {total_time/60:.1f} min")

# Build merged output: P1 results + full scan results
print("\nBuilding merged output...")
all_results = list(p1_rows.values())
if os.path.exists(OUTPUT_CSV):
    existing_in_csv = set(p1_rows.keys())
    for r in csv.DictReader(open(OUTPUT_CSV)):
        if r["anchor_id"] not in existing_in_csv and r.get("parse_status") == "ok":
            r["boundary_reliable"] = "False"
            all_results.append(r)
            existing_in_csv.add(r["anchor_id"])

# Also check raw_per_anchor_full for results not yet in CSV
for fname in os.listdir(RESP_DIR):
    if fname.endswith(".json"):
        aid = fname.replace(".json", "")
        if aid not in existing_in_csv:
            obj = json.load(open(f"{RESP_DIR}/{fname}"))
            parsed = obj.get("parsed", {})
            p = parsed
            start_t = float(obj.get("start_time", 0))
            row = {
                "anchor_id": aid, "video_id": VIDEO_ID,
                "anchor_time": obj.get("anchor_time", ""),
                "start_time": obj.get("start_time", ""),
                "end_time": obj.get("end_time", ""),
                "duration": "10.000",
                "label": p.get("label", "abstain"),
                "event_start": str(p.get("event_start", "")) if p.get("event_start") is not None else "",
                "event_end": str(p.get("event_end", "")) if p.get("event_end") is not None else "",
                "event_start_absolute": str(start_t + float(p["event_start"])) if p.get("event_start") is not None else "",
                "event_end_absolute": str(start_t + float(p["event_end"])) if p.get("event_end") is not None else "",
                "event_type": p.get("event_type", "none"),
                "involved_object": p.get("involved_object", "none"),
                "ego_relevant": str(p.get("ego_relevant", "")),
                "boundary_status": p.get("boundary_status", "not_applicable"),
                "complete_event_visible": str(p.get("complete_event_visible", "")),
                "confidence": p.get("confidence", "low"),
                "evidence": (p.get("evidence", "") or "")[:200],
                "negative_reason": p.get("negative_reason", "null"),
                "abstain_reason": p.get("abstain_reason", "null"),
                "runtime_seconds": f"{obj.get('runtime', 0):.1f}",
                "raw_response_path": f"{RESP_DIR}/{aid}.json",
                "parse_status": "ok",
                "boundary_reliable": "False",
            }
            all_results.append(row)
            existing_in_csv.add(aid)

# Sort by anchor_id
all_results.sort(key=lambda r: r["anchor_id"])

# Write merged CSV
with open(OUTPUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDNAMES)
    w.writeheader()
    w.writerows(all_results)

print(f"Merged output: {len(all_results)} rows -> {OUTPUT_CSV}")
labels = Counter(r["label"] for r in all_results)
print(f"Labels: {dict(labels)}")
parse_stats = Counter(r["parse_status"] for r in all_results)
print(f"Parse status: {dict(parse_stats)}")

# Save analysis
pos = [r for r in all_results if r["label"] == "positive"]
neg = [r for r in all_results if r["label"] == "negative"]
abs_count = [r for r in all_results if r["label"] == "abstain"]
analysis = {
    "total_anchors": len(all_results),
    "parse_ok": sum(1 for r in all_results if r["parse_status"] == "ok"),
    "parse_error": sum(1 for r in all_results if r["parse_status"] != "ok"),
    "positive": len(pos), "negative": len(neg), "abstain": len(abs_count),
    "positive_rate": len(pos) / len(all_results) if all_results else 0,
    "event_types": dict(Counter(r["event_type"] for r in pos)),
    "involved_objects": dict(Counter(r["involved_object"] for r in pos)),
    "confidence_dist": dict(Counter(r["confidence"] for r in all_results)),
    "negative_reasons": dict(Counter(r["negative_reason"] for r in neg)),
    "boundary_status_dist": dict(Counter(r["boundary_status"] for r in pos)),
    "boundary_unique_starts": len(set(r["event_start"] for r in pos)),
    "boundary_unique_ends": len(set(r["event_end"] for r in pos)),
    "positive_anchors": [r["anchor_id"] for r in pos],
}
with open(f"{OUT}/analysis/full_center10_analysis.json", "w") as f:
    json.dump(analysis, f, indent=2, ensure_ascii=False)
print(f"\nAnalysis saved to analysis/full_center10_analysis.json")
print(f"Positive rate: {analysis['positive_rate']:.3f} ({len(pos)}/{len(all_results)})")
