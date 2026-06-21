#!/usr/bin/env python3
"""Batch-run Qwen3-VL on video clips for driving risk detection.

Example:
    python test_vlm/scripts/run_qwen3_vl_batch.py \
        --model /qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-8B-Instruct \
        --manifest test_vlm/manifests/smoke_manifest.csv \
        --out test_vlm/outputs/qwen3_vl_smoke_fps1.jsonl \
        --fps 1.0 \
        --limit 1
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
QUERY_TEMPLATES = {
    "general_risk": (
        "You are an advanced driver-assistance safety analyst. "
        "Watch this short driving video clip carefully. "
        "Determine whether it contains ANY of the following: "
        "potential collision risk, abnormal lane changes, cut-ins, "
        "pedestrians/cyclists/vehicles suddenly entering the ego lane, "
        "sudden hard braking, dangerous close following, or traffic conflicts.\n\n"
        "Respond with a single JSON object only — no markdown, no explanation:\n"
        '{"relevant": "yes/no/uncertain", '
        '"risk_type": "collision_risk/lane_cut_in/pedestrian_or_bike_crossing/sudden_braking/none/uncertain", '
        '"confidence": 0.0, '
        '"evidence": "one sentence describing the basis of your judgment", '
        '"temporal_location": "early/middle/late/whole_clip/unclear"}'
    ),
    "ego_risk": (
        "You are an advanced driver-assistance safety analyst. "
        "The video is recorded from the ego vehicle's front-facing dashcam.\n\n"
        "Your task: determine whether this clip contains a situation that could "
        "directly affect the EGO vehicle's driving decisions, safety, braking, "
        "evasion, deceleration, or path selection.\n\n"
        "CRITICAL RULES:\n"
        "- relevant=yes ONLY if the risk could force the ego driver to react "
        "(brake, steer, slow down, change path).\n"
        "- Do NOT label relevant=yes just because a pedestrian is visible far away, "
        "or a vehicle changes lane in another road, or a subtitle/text describes danger.\n"
        "- If the ego vehicle is stopped and nothing is approaching it, label no or uncertain.\n"
        "- IGNORE all on-screen text: subtitles, titles, watermarks, timestamps, overlays. "
        "Base your judgment ONLY on what you see in the driving scene itself.\n"
        "- Normal driving, steady following, clear lanes → no.\n\n"
        "Respond with a single JSON object only — no markdown, no explanation:\n"
        '{"relevant": "yes/no/uncertain", '
        '"risk_level": "none/low/medium/high/uncertain", '
        '"risk_type": "cut_in/pedestrian_or_bike_conflict/sudden_braking/near_collision/abnormal_lane_change/ego_static_no_conflict/normal_driving/other/uncertain", '
        '"ego_motion": "moving/stopped/uncertain", '
        '"affected_ego": "yes/no/uncertain", '
        '"evidence": "one sentence describing the basis of your judgment", '
        '"temporal_location": "early/middle/late/whole_clip/unclear"}'
    ),
    "ego_risk_L2": (
        "You are a strict driver-assistance safety analyst. "
        "The video is recorded from the ego vehicle's front-facing dashcam.\n\n"
        "Your task: determine whether this clip contains a situation that would "
        "REQUIRE the ego driver to actively brake, swerve, or significantly change speed.\n\n"
        "STRICT RULES:\n"
        "- relevant=yes ONLY if the ego driver MUST take evasive action to avoid a problem.\n"
        "- A pedestrian crossing far ahead, a vehicle in another lane, or a car slowing down "
        "normally at a traffic light does NOT count as relevant.\n"
        "- Steady car-following at normal distance is NOT relevant, even if the lead car brakes gently.\n"
        "- Only count situations where the ego driver would feel urgency: sudden obstacle in path, "
        "vehicle cutting in at close range, pedestrian stepping into road within braking distance.\n"
        "- If the ego vehicle is stopped with nothing approaching within 10 meters, label no.\n"
        "- IGNORE all on-screen text, subtitles, watermarks, timestamps.\n\n"
        "Respond with a single JSON object only — no markdown, no explanation:\n"
        '{"relevant": "yes/no/uncertain", '
        '"risk_level": "none/low/medium/high/uncertain", '
        '"risk_type": "cut_in/pedestrian_or_bike_conflict/sudden_braking/near_collision/abnormal_lane_change/ego_static_no_conflict/normal_driving/other/uncertain", '
        '"ego_motion": "moving/stopped/uncertain", '
        '"affected_ego": "yes/no/uncertain", '
        '"evidence": "one sentence describing the basis of your judgment", '
        '"temporal_location": "early/middle/late/whole_clip/unclear"}'
    ),
    "ego_risk_L3": (
        "You are a very strict driver-assistance safety analyst. "
        "The video is recorded from the ego vehicle's front-facing dashcam.\n\n"
        "Your task: determine whether this clip contains IMMINENT physical danger to the ego vehicle.\n\n"
        "VERY STRICT RULES:\n"
        "- relevant=yes ONLY if there is a clear, immediate threat within the ego vehicle's "
        "current travel path AND within close proximity (less than ~15 meters).\n"
        "- The threat must be an object, vehicle, or person that is directly blocking or "
        "entering the ego vehicle's lane at close range.\n"
        "- A pedestrian on the sidewalk, a vehicle changing lane 50m ahead, or a car braking "
        "gently 3 car-lengths away does NOT count.\n"
        "- Normal urban driving with nearby traffic is NOT relevant unless there is a direct, "
        "close-proximity conflict that requires immediate action.\n"
        "- Following a vehicle at normal distance on a highway is NOT relevant.\n"
        "- If the ego vehicle is stopped, label no unless something is about to collide with it.\n"
        "- IGNORE all on-screen text, subtitles, watermarks, timestamps.\n\n"
        "Respond with a single JSON object only — no markdown, no explanation:\n"
        '{"relevant": "yes/no/uncertain", '
        '"risk_level": "none/low/medium/high/uncertain", '
        '"risk_type": "cut_in/pedestrian_or_bike_conflict/sudden_braking/near_collision/abnormal_lane_change/ego_static_no_conflict/normal_driving/other/uncertain", '
        '"ego_motion": "moving/stopped/uncertain", '
        '"affected_ego": "yes/no/uncertain", '
        '"evidence": "one sentence describing the basis of your judgment", '
        '"temporal_location": "early/middle/late/whole_clip/unclear"}'
    ),
    "ego_risk_L4": (
        "You are an extremely conservative driver-assistance safety analyst. "
        "The video is recorded from the ego vehicle's front-facing dashcam.\n\n"
        "Your task: determine whether a collision or near-collision event is VISIBLY OCCURRING "
        "or is UNAVOIDABLE in this clip.\n\n"
        "EXTREMELY STRICT RULES:\n"
        "- relevant=yes ONLY if you can see a collision happening, or the ego vehicle is performing "
        "emergency braking/swerving to narrowly avoid impact, or an object is within ~5 meters "
        "and directly in the ego vehicle's path.\n"
        "- Potential risks, approaching vehicles, pedestrians crossing at a distance, vehicles "
        "changing lanes ahead, or cars braking at traffic lights are ALL labeled no.\n"
        "- If you are uncertain whether the situation is dangerous, label no.\n"
        "- When in doubt, always choose no.\n"
        "- IGNORE all on-screen text, subtitles, watermarks, timestamps.\n\n"
        "Respond with a single JSON object only — no markdown, no explanation:\n"
        '{"relevant": "yes/no/uncertain", '
        '"risk_level": "none/low/medium/high/uncertain", '
        '"risk_type": "cut_in/pedestrian_or_bike_conflict/sudden_braking/near_collision/abnormal_lane_change/ego_static_no_conflict/normal_driving/other/uncertain", '
        '"ego_motion": "moving/stopped/uncertain", '
        '"affected_ego": "yes/no/uncertain", '
        '"evidence": "one sentence describing the basis of your judgment", '
        '"temporal_location": "early/middle/late/whole_clip/unclear"}'
    ),
}

# Fields to extract from parsed JSON per prompt style
FIELD_MAPS = {
    "general_risk": {
        "vlm_relevant": "relevant",
        "vlm_risk_type": "risk_type",
        "vlm_confidence": "confidence",
        "vlm_evidence": "evidence",
        "vlm_temporal_location": "temporal_location",
    },
    "ego_risk": {
        "vlm_relevant": "relevant",
        "vlm_risk_level": "risk_level",
        "vlm_risk_type": "risk_type",
        "vlm_ego_motion": "ego_motion",
        "vlm_affected_ego": "affected_ego",
        "vlm_evidence": "evidence",
        "vlm_temporal_location": "temporal_location",
    },
}

# All ego_risk_L* levels share the same field map as ego_risk
for _lvl in ("ego_risk_L2", "ego_risk_L3", "ego_risk_L4"):
    FIELD_MAPS[_lvl] = FIELD_MAPS["ego_risk"]


def parse_vlm_json(raw: str) -> tuple:
    """Try to extract a JSON object from the model output."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Try direct parse
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    # Try to find first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1]), None
        except json.JSONDecodeError as e:
            return None, f"JSON parse error: {e}"
    return None, "No JSON object found in output"


def build_messages(video_path: str, query_type: str, fps: float) -> list:
    """Build the chat messages for Qwen3-VL."""
    prompt = QUERY_TEMPLATES.get(query_type, QUERY_TEMPLATES["general_risk"])
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": video_path,
                    "fps": fps,
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }
    ]
    return messages


def load_model(model_dir: str):
    """Load Qwen3-VL model and processor."""
    print(f"Loading model from {model_dir} ...")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_dir,
        dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    print("Model loaded.")
    return model, processor


def run_one_clip(model, processor, video_path: str, query_type: str, fps: float) -> dict:
    """Run VLM on a single clip. Returns a dict with parsed results."""
    messages = build_messages(video_path, query_type, fps)

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)

    t0 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]
    latency = time.time() - t0

    parsed, parse_err = parse_vlm_json(output_text)

    result = {
        "fps": fps,
        "latency_sec": round(latency, 3),
        "raw_output": output_text,
    }

    field_map = FIELD_MAPS.get(query_type, FIELD_MAPS["general_risk"])

    if parsed:
        result["json_ok"] = True
        for out_key, json_key in field_map.items():
            result[out_key] = parsed.get(json_key, "uncertain")
        result["error"] = ""
    else:
        result["json_ok"] = False
        for out_key in field_map:
            result[out_key] = "parse_error"
        result["error"] = parse_err or ""

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch-run Qwen3-VL on video clips.")
    parser.add_argument("--model", type=str, required=True, help="Path to Qwen3-VL model directory.")
    parser.add_argument("--manifest", type=Path, required=True, help="Manifest CSV from make_clips.py.")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL path.")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to sample from video.")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N clips (0 = all).")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed clip_ids in output.")
    parser.add_argument("--prompt_style", type=str, default="general_risk",
                        choices=["general_risk", "ego_risk", "ego_risk_L2", "ego_risk_L3", "ego_risk_L4"],
                        help="Prompt template to use.")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    with open(args.manifest, newline="") as f:
        reader = csv.DictReader(f)
        clips = list(reader)

    if args.limit > 0:
        clips = clips[:args.limit]

    print(f"Manifest: {len(clips)} clips to process. prompt_style={args.prompt_style}")

    done_ids = set()
    if args.resume and args.out.is_file():
        with open(args.out) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    done_ids.add(obj.get("clip_id", ""))
                except json.JSONDecodeError:
                    pass
        print(f"Resume: {len(done_ids)} clips already processed, will skip them.")

    model, processor = load_model(args.model)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    with open(args.out, "a" if args.resume else "w") as fout:
        for i, clip in enumerate(clips):
            clip_id = clip["clip_id"]
            if clip_id in done_ids:
                skipped += 1
                continue

            video_path = clip["video_path"]
            query_type = args.prompt_style  # override manifest query_type

            print(f"[{i+1}/{len(clips)}] {clip_id} ...", end=" ", flush=True)

            try:
                vlm_result = run_one_clip(model, processor, video_path, query_type, args.fps)
            except Exception as e:
                print(f"ERROR: {e}")
                field_map = FIELD_MAPS.get(query_type, FIELD_MAPS["general_risk"])
                vlm_result = {
                    "fps": args.fps,
                    "latency_sec": 0.0,
                    "json_ok": False,
                    "raw_output": "",
                    "error": str(e),
                }
                for out_key in field_map:
                    vlm_result[out_key] = "runtime_error"

            row = {
                "clip_id": clip_id,
                "video_path": video_path,
                "source_video": clip.get("source_video", ""),
                "start_sec": clip.get("start_sec", ""),
                "end_sec": clip.get("end_sec", ""),
                "query_type": query_type,
                "human_label": clip.get("human_label", "unknown"),
                "note": clip.get("note", ""),
            }
            row.update(vlm_result)

            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            processed += 1

            print(f"relevant={vlm_result.get('vlm_relevant', '?')} "
                  f"latency={vlm_result.get('latency_sec', 0):.1f}s "
                  f"json_ok={vlm_result.get('json_ok', False)}")

    print(f"\nDone. Processed={processed}, Skipped(resume)={skipped}, Output={args.out}")


if __name__ == "__main__":
    main()
