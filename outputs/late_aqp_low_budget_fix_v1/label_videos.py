#!/usr/bin/env python3
"""One-time VLM oracle labeling for low-budget tuning/validation data.

This is the ONLY GPU/VLM step in the low-budget fix workflow. It labels
center10-style 10s anchors for realcartest_5k and test videos, then stitches
positive anchors into events.

All outputs are written to outputs/late_aqp_low_budget_fix_v1/new_labels/.
"""

import csv
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUTDIR = ROOT / "outputs" / "late_aqp_low_budget_fix_v1" / "new_labels"
OUTDIR.mkdir(parents=True, exist_ok=True)

PROMPT_PATH = ROOT / "test_vlm" / "outputs" / "v13_6_clip_construction_sensitivity_v1" / "prompts" / "o_enter_ego_path_v0_v13_6_prompt.txt"
MODEL_PATH = ROOT / "models" / "vlm" / "qwen3_vl" / "Qwen3-VL-32B-Instruct"

VIDEOS = [
    {
        "video_id": "realcartest_5k",
        "video_path": ROOT / "try_or_no" / "videos" / "realcartest_5k.mp4",
        # Use first 208 s (full video) for labeling; we will split into tuning/final afterwards.
        "label_start": 0.0,
        "label_end": 208.333333,
    },
    {
        "video_id": "test",
        "video_path": ROOT / "try_or_no" / "videos" / "test.mov",
        "label_start": 0.0,
        "label_end": 43.043333,
    },
    {
        "video_id": "realcartest_tail",
        "video_path": ROOT / "try_or_no" / "videos" / "realcartest.mp4",
        "label_start": 3920.0,
        "label_end": 3987.104,
    },
]

ANCHOR_INTERVAL = 10.0
HALF_WINDOW = 5.0
FPS = 2.0


def load_prompt():
    with open(PROMPT_PATH) as f:
        return f.read()


def build_anchor_grid(video_id, video_path, duration, start, end):
    anchors = []
    # effective duration to label
    eff_start = max(0.0, start)
    eff_end = min(duration, end)
    n = math.ceil((eff_end - eff_start) / ANCHOR_INTERVAL)
    for i in range(n):
        center = eff_start + i * ANCHOR_INTERVAL + ANCHOR_INTERVAL / 2.0
        if center > eff_end:
            center = eff_end
        s = max(eff_start, center - HALF_WINDOW)
        e = min(eff_end, center + HALF_WINDOW)
        anchors.append({
            "anchor_id": f"{video_id}_anchor_{i:04d}",
            "video_id": video_id,
            "anchor_time": f"{center:.3f}",
            "start_time": f"{s:.3f}",
            "end_time": f"{e:.3f}",
            "duration": f"{e - s:.3f}",
            "source_video_path": str(video_path),
            "construction_policy": "center_10s",
        })
    return anchors


def extract_frames(video_path, clip_start, clip_end, video_fps, fps=2.0):
    frames = []
    cap = cv2.VideoCapture(str(video_path))
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


def parse_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```")).strip()
    try:
        return json.loads(text), "ok"
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}, "no_json_object"
    try:
        return json.loads(match.group(0)), "ok"
    except json.JSONDecodeError as exc:
        return {}, f"json_parse_error: {exc}"


def run_one(model, processor, prompt_text, pil_frames, device):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": pil_frames, "fps": FPS},
                {"type": "text", "text": prompt_text},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
    inputs = inputs.to(device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1, do_sample=False)
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    raw = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    return raw


def stitch_events(video_id, labels, gap_merge=5.0, gap_same_type=10.0):
    positives = [r for r in labels if r["label"] == "positive"]
    raw = []
    for r in positives:
        try:
            es = float(r["event_start_absolute"])
            ee = float(r["event_end_absolute"])
        except (ValueError, TypeError):
            es = float(r["start_time"])
            ee = float(r["end_time"])
        raw.append({
            "anchor_id": r["anchor_id"],
            "start": es,
            "end": ee,
            "event_type": r.get("event_type", ""),
            "involved_object": r.get("involved_object", ""),
            "confidence": r.get("confidence", ""),
            "complete_event_visible": r.get("complete_event_visible", ""),
            "boundary_status": r.get("boundary_status", ""),
            "evidence": r.get("evidence", ""),
        })
    raw.sort(key=lambda x: x["start"])
    events = []
    current = None
    trace = []
    trace_keys = ["action", "anchor_id", "start", "end", "num_anchors", "gap"]
    def add_trace(**kwargs):
        row = {k: "" for k in trace_keys}
        row.update(kwargs)
        trace.append(row)

    for ri in raw:
        if current is None:
            current = {
                "start": ri["start"], "end": ri["end"],
                "supporting_anchors": [ri["anchor_id"]],
                "event_types": [ri["event_type"]],
                "involved_objects": [ri["involved_object"]],
                "confidences": [ri["confidence"]],
                "complete_flags": [ri["complete_event_visible"]],
                "boundary_statuses": [ri["boundary_status"]],
                "evidences": [ri["evidence"]],
            }
            add_trace(action="start_new", anchor_id=ri["anchor_id"], start=ri["start"], end=ri["end"])
            continue
        gap = ri["start"] - current["end"]
        same_type = ri["event_type"] == max(set(current["event_types"]), key=current["event_types"].count)
        if gap <= gap_merge or (gap <= gap_same_type and same_type):
            current["end"] = max(current["end"], ri["end"])
            current["supporting_anchors"].append(ri["anchor_id"])
            current["event_types"].append(ri["event_type"])
            current["involved_objects"].append(ri["involved_object"])
            current["confidences"].append(ri["confidence"])
            current["complete_flags"].append(ri["complete_event_visible"])
            current["boundary_statuses"].append(ri["boundary_status"])
            current["evidences"].append(ri["evidence"])
            add_trace(action="merge", anchor_id=ri["anchor_id"], start=ri["start"], end=ri["end"], gap=gap)
        else:
            events.append(current)
            add_trace(action="emit_group", num_anchors=len(current["supporting_anchors"]), start=current["start"], end=current["end"])
            current = {
                "start": ri["start"], "end": ri["end"],
                "supporting_anchors": [ri["anchor_id"]],
                "event_types": [ri["event_type"]],
                "involved_objects": [ri["involved_object"]],
                "confidences": [ri["confidence"]],
                "complete_flags": [ri["complete_event_visible"]],
                "boundary_statuses": [ri["boundary_status"]],
                "evidences": [ri["evidence"]],
            }
            add_trace(action="start_new", anchor_id=ri["anchor_id"], start=ri["start"], end=ri["end"])
    if current is not None:
        events.append(current)
        add_trace(action="emit_group_final", num_anchors=len(current["supporting_anchors"]), start=current["start"], end=current["end"])

    event_rows = []
    for i, ev in enumerate(events):
        etype_counts = Counter(t for t in ev["event_types"] if t)
        obj_counts = Counter(o for o in ev["involved_objects"] if o)
        event_rows.append({
            "event_id": f"{video_id}_event_{i:04d}",
            "video_id": video_id,
            "event_start": f"{ev['start']:.3f}",
            "event_end": f"{ev['end']:.3f}",
            "event_duration": f"{ev['end']-ev['start']:.3f}",
            "event_type_majority": etype_counts.most_common(1)[0][0] if etype_counts else "",
            "involved_object_majority": obj_counts.most_common(1)[0][0] if obj_counts else "",
            "num_supporting_anchors": len(ev["supporting_anchors"]),
            "supporting_anchor_ids": "|".join(ev["supporting_anchors"]),
            "mean_confidence_proxy": "high" if ev["confidences"].count("high") > len(ev["confidences"]) / 2 else "medium",
            "all_boundary_statuses": "|".join(set(ev["boundary_statuses"])),
            "complete_event_visible_all": str(all(str(f).lower() == "true" for f in ev["complete_flags"])),
            "evidence_summary": ev["evidences"][0][:200] if ev["evidences"] else "",
            "label_source": "newly_generated_this_task",
            "oracle_version": "qwen3_vl_32b_v13_6_prompt",
        })
    return event_rows, trace


def main():
    prompt_text = load_prompt()
    print(f"Loading model {MODEL_PATH} ...", flush=True)
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(MODEL_PATH),
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(
        str(MODEL_PATH),
        trust_remote_code=True,
        local_files_only=True,
    )
    device = next(model.parameters()).device
    print(f"Model loaded in {time.time()-t0:.1f}s on {device}", flush=True)

    total_calls = 0
    summary = []

    for vid_spec in VIDEOS:
        video_id = vid_spec["video_id"]
        video_path = vid_spec["video_path"]
        cap = cv2.VideoCapture(str(video_path))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        # Fallback fps from frame count / duration if cv2 cannot read it (e.g., .mov).
        spec_duration = float(vid_spec["label_end"])
        if video_fps <= 0 and frame_count > 0 and spec_duration > 0:
            video_fps = frame_count / spec_duration
        duration = frame_count / video_fps if video_fps > 0 else spec_duration

        if video_fps <= 0 or duration <= 0:
            print(f"\nSkipping {video_id}: cannot read video metadata (fps={video_fps}, duration={duration}).", flush=True)
            continue

        print(f"\nProcessing {video_id}: fps={video_fps:.2f}, duration={duration:.1f}s", flush=True)

        anchors = build_anchor_grid(video_id, video_path, duration, vid_spec["label_start"], vid_spec["label_end"])
        print(f"  Anchors: {len(anchors)}", flush=True)
        total_calls += len(anchors)

        labels = []
        resp_dir = OUTDIR / f"raw_vlm_responses_{video_id}"
        resp_dir.mkdir(exist_ok=True)

        for i, a in enumerate(anchors):
            start_t = float(a["start_time"])
            end_t = float(a["end_time"])
            sys.stdout.write(f"\r  [{i+1}/{len(anchors)}] {a['anchor_id']}")
            sys.stdout.flush()

            resp_file = resp_dir / f"{a['anchor_id']}.json"
            try:
                if resp_file.exists():
                    # Resume from existing raw response.
                    with open(resp_file) as f:
                        cached = json.load(f)
                    raw = cached.get("raw", "")
                    parsed, parse_status = parse_json(raw)
                    if not parsed and "parsed" in cached:
                        parsed = cached["parsed"]
                else:
                    frames = extract_frames(video_path, start_t, end_t, video_fps, fps=FPS)
                    if len(frames) < 5:
                        frames = extract_frames(video_path, start_t, end_t, video_fps, fps=4.0)
                    pil_frames = [Image.fromarray(f) for f in frames]
                    raw = run_one(model, processor, prompt_text, pil_frames, device)
                    parsed, parse_status = parse_json(raw)

                label = parsed.get("label", "abstain").strip().lower()
                if label not in ("positive", "negative", "abstain"):
                    label = "abstain"
                ev_start_rel = parsed.get("event_start")
                ev_end_rel = parsed.get("event_end")
                ev_start_abs = ""
                ev_end_abs = ""
                if ev_start_rel not in (None, "", "null"):
                    try:
                        ev_start_abs = f"{start_t + float(ev_start_rel):.3f}"
                    except Exception:
                        pass
                if ev_end_rel not in (None, "", "null"):
                    try:
                        ev_end_abs = f"{start_t + float(ev_end_rel):.3f}"
                    except Exception:
                        pass

                row = {
                    "anchor_id": a["anchor_id"],
                    "video_id": video_id,
                    "anchor_time": a["anchor_time"],
                    "start_time": a["start_time"],
                    "end_time": a["end_time"],
                    "duration": a["duration"],
                    "label": label,
                    "event_start": str(ev_start_rel) if ev_start_rel is not None else "",
                    "event_end": str(ev_end_rel) if ev_end_rel is not None else "",
                    "event_start_absolute": ev_start_abs,
                    "event_end_absolute": ev_end_abs,
                    "event_type": parsed.get("event_type", ""),
                    "involved_object": parsed.get("involved_object", ""),
                    "ego_relevant": str(parsed.get("ego_relevant", "")),
                    "boundary_status": parsed.get("boundary_status", ""),
                    "complete_event_visible": str(parsed.get("complete_event_visible", "")),
                    "confidence": parsed.get("confidence", ""),
                    "evidence": (parsed.get("evidence", "") or "")[:200],
                    "negative_reason": parsed.get("negative_reason", ""),
                    "abstain_reason": parsed.get("abstain_reason", ""),
                    "raw_response_path": str(resp_file),
                    "parse_status": parse_status,
                }
                if not resp_file.exists():
                    with open(resp_file, "w") as f:
                        json.dump({"anchor_id": a["anchor_id"], "raw": raw, "parsed": parsed}, f, indent=2)
            except Exception as e:
                print(f" ERROR: {e}", flush=True)
                row = {
                    "anchor_id": a["anchor_id"], "video_id": video_id,
                    "anchor_time": a["anchor_time"], "start_time": a["start_time"], "end_time": a["end_time"], "duration": a["duration"],
                    "label": "abstain", "event_start": "", "event_end": "", "event_start_absolute": "", "event_end_absolute": "",
                    "event_type": "", "involved_object": "", "ego_relevant": "", "boundary_status": "", "complete_event_visible": "",
                    "confidence": "", "evidence": "", "negative_reason": "", "abstain_reason": "",
                    "raw_response_path": "", "parse_status": f"error: {str(e)[:80]}",
                }
            labels.append(row)

        # Write labels and anchors for this video.
        labels_path = OUTDIR / f"center10_full_oracle_labels_{video_id}.csv"
        with open(labels_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=labels[0].keys())
            w.writeheader(); w.writerows(labels)
        anchors_path = OUTDIR / f"center10_anchor_grid_{video_id}.csv"
        with open(anchors_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=anchors[0].keys())
            w.writeheader(); w.writerows(anchors)

        event_rows, trace = stitch_events(video_id, labels)
        events_path = OUTDIR / f"center10_vlm_oracle_events_{video_id}.csv"
        if event_rows:
            with open(events_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=event_rows[0].keys())
                w.writeheader(); w.writerows(event_rows)
        else:
            # Write empty file with header from existing schema if possible.
            with open(events_path, "w", newline="") as f:
                f.write("event_id,video_id,event_start,event_end,event_duration,event_type_majority,involved_object_majority,num_supporting_anchors,supporting_anchor_ids,mean_confidence_proxy,all_boundary_statuses,complete_event_visible_all,evidence_summary,label_source,oracle_version\n")
        trace_path = OUTDIR / f"center10_event_stitching_trace_{video_id}.csv"
        if trace:
            with open(trace_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=trace[0].keys())
                w.writeheader(); w.writerows(trace)
        else:
            with open(trace_path, "w", newline="") as f:
                f.write("action,anchor_id,start,end,num_anchors,gap\n")

        positives = [r for r in labels if r["label"] == "positive"]
        print(f"\n  {video_id}: {len(positives)}/{len(labels)} positive anchors -> {len(event_rows)} stitched events", flush=True)
        summary.append({
            "video_id": video_id,
            "anchors": len(anchors),
            "positives": len(positives),
            "events": len(event_rows),
            "events_path": str(events_path.relative_to(ROOT)),
        })

    # Write combined events file with consistent schema.
    combined_events = []
    for s in summary:
        events_file = OUTDIR / f"center10_vlm_oracle_events_{s['video_id']}.csv"
        with open(events_file) as f:
            rows = list(csv.DictReader(f))
            if rows:
                combined_events.extend(rows)
    if combined_events:
        combined_path = OUTDIR / "center10_vlm_oracle_events_combined.csv"
        with open(combined_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=combined_events[0].keys())
            w.writeheader(); w.writerows(combined_events)

    # Cost report.
    cost_md = "# Labeling Cost Report\n\n"
    cost_md += "This report records the one-time VLM oracle calls used to generate new labels.\n"
    cost_md += "These calls are **not** counted toward any method's oracle budget.\n\n"
    cost_md += "| Video | Anchors labeled | Positive anchors | Stitched events |\n"
    cost_md += "|-------|-----------------|------------------|-----------------|\n"
    for s in summary:
        cost_md += f"| {s['video_id']} | {s['anchors']} | {s['positives']} | {s['events']} |\n"
    cost_md += f"\n**Total VLM inference calls: {total_calls}**\n"
    cost_md += f"\nModel: `{MODEL_PATH}`\n"
    cost_md += f"Prompt: `{PROMPT_PATH}`\n"
    cost_md += f"Outputs: `{OUTDIR}`\n"

    cost_path = OUTDIR.parent / "labeling_cost_report.md"
    with open(cost_path, "w") as f:
        f.write(cost_md)
    print(f"\nTotal VLM calls: {total_calls}")
    print(f"Cost report: {cost_path}")


if __name__ == "__main__":
    main()
