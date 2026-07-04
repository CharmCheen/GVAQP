#!/usr/bin/env python3
"""Run Qwen3-VL oracle labels on probe_set_v1 center frame + contact sheet.

These labels are VLM-oracle-relative, not human ground truth.
"""
import argparse
import csv
import json
import random
import re
import time
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
DEFAULT_MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
DEFAULT_INPUT = ROOT / "outputs/probe_set_v1/probe_set_human_labels_template.csv"
DEFAULT_OUT = ROOT / "outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv"
DEFAULT_RAW_JSONL = ROOT / "outputs/probe_set_v1/vlm_oracle_raw.jsonl"
DEFAULT_RAW_DIR = ROOT / "outputs/probe_set_v1/vlm_oracle_raw_responses"
DEFAULT_SPOTCHECK = ROOT / "outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv"

REFERENCE_SOURCE = "probe_set_v1_vlm_oracle_reference"
MODEL_NAME = "Qwen3-VL-32B-Instruct"
TARGET_EVENT = (
    "A traffic participant or object enters, crosses, approaches, or creates a "
    "near-interaction with the ego vehicle path during the provided local time window."
)

SYSTEM_PROMPT = (
    "You are a visual event reviewer for a driving-video probe set. Your task is to judge "
    "whether a short time window contains the target event type using visible semantic "
    "evidence from the provided images. Do not try to reproduce object tracking, distance, "
    "speed, TTC, or geometric calculations. Use holistic visual judgment from the center "
    "frame and contact sheet."
)


def build_prompt(row: dict) -> str:
    return f"""
{SYSTEM_PROMPT}

Target event type: {TARGET_EVENT}

Review probe `{row['probe_id']}`.
Local time window: {float(row['local_t_start']):.3f} to {float(row['local_t_end']):.3f} seconds.

Inputs:
1. Center frame for the probe.
2. Contact sheet showing multiple frames from the probe window.

Question: In this time window, does the visual evidence show the target event type?

Important rules:
- Do not base your answer on inferred detector scores, tracking distances, speeds, TTC, or cheap-signal computations.
- Use semantic visual evidence only.
- Use `true_interval` when the target event is visible and the contact sheet supports an approximate start and end inside the local window.
- Use `point_anchor` when the target event is visible but only a point-like moment or rough anchor can be inferred.
- Use `negative` when no target event is visible.
- Use `uncertain` when image quality, occlusion, contact-sheet ambiguity, or missing temporal context prevents a reliable judgment.
- Give a concrete rationale for later human spot-checking.

Return exactly one JSON object, with no markdown:
{{
  "label": "true_interval | point_anchor | negative | uncertain",
  "event_t_start_local": null,
  "event_t_end_local": null,
  "confidence": "low | medium | high",
  "rationale": "short visible-evidence explanation"
}}
""".strip()


def parse_json(raw: str) -> tuple[dict, str]:
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


def norm_label(value: object) -> str:
    label = str(value or "").strip().lower()
    label = label.replace(" ", "_")
    allowed = {"true_interval", "point_anchor", "negative", "uncertain"}
    return label if label in allowed else "uncertain"


def norm_conf(value: object) -> str:
    conf = str(value or "").strip().lower()
    allowed = {"low", "medium", "high"}
    return conf if conf in allowed else "low"


def norm_time(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    if s in {"", "none", "null", "nan"}:
        return ""
    try:
        return f"{float(s):.3f}"
    except ValueError:
        return ""


def load_model(model_path: Path):
    print(f"Loading {model_path} ...", flush=True)
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(model_path),
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=True,
    )
    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)
    return model, processor


def run_one(model, processor, row: dict, max_new_tokens: int, temperature: float) -> dict:
    center = Image.open(row["center_frame_path"]).convert("RGB")
    sheet = Image.open(row["sheet_path"]).convert("RGB")
    prompt = build_prompt(row)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": center},
                {"type": "image", "image": sheet},
                {"type": "text", "text": prompt},
            ],
        }
    ]
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

    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=False,
        )
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    runtime = time.time() - t0

    generated_trimmed = [
        out_ids[len(in_ids) :]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    raw = processor.batch_decode(
        generated_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]
    parsed, parse_status = parse_json(raw)
    peak_gb = torch.cuda.max_memory_allocated(0) / (1024**3) if torch.cuda.is_available() else 0.0

    label = norm_label(parsed.get("label"))
    result = {
        "probe_id": row["probe_id"],
        "video_id": row.get("video_id", ""),
        "local_t_start": f"{float(row['local_t_start']):.3f}",
        "local_t_end": f"{float(row['local_t_end']):.3f}",
        "center_frame_path": row["center_frame_path"],
        "sheet_path": row["sheet_path"],
        "reference_source": REFERENCE_SOURCE,
        "model_name": MODEL_NAME,
        "label": label,
        "event_t_start_local": norm_time(parsed.get("event_t_start_local")),
        "event_t_end_local": norm_time(parsed.get("event_t_end_local")),
        "confidence": norm_conf(parsed.get("confidence")),
        "rationale": str(parsed.get("rationale", "") or "")[:1000],
        "parse_status": parse_status,
        "runtime_seconds": f"{runtime:.3f}",
        "peak_gpu_memory_gb": f"{peak_gb:.3f}",
        "raw_output": raw,
    }
    if label in {"negative", "uncertain"}:
        result["event_t_start_local"] = result["event_t_start_local"] or ""
        result["event_t_end_local"] = result["event_t_end_local"] or ""
    return result


def write_oracle_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "probe_id",
        "video_id",
        "local_t_start",
        "local_t_end",
        "center_frame_path",
        "sheet_path",
        "reference_source",
        "model_name",
        "label",
        "event_t_start_local",
        "event_t_end_local",
        "confidence",
        "rationale",
        "parse_status",
        "runtime_seconds",
        "peak_gpu_memory_gb",
        "raw_response_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("# VLM oracle judgment, not human ground truth.\n")
        f.write("# Downstream metrics must use dataset_source=probe_set_v1_vlm_oracle_reference.\n")
        f.write("# Do not call these labels true recall or ground truth recall; use relative to VLM oracle judgment.\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_spotcheck(path: Path, rows: list[dict], sample_n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    ids = sorted([r["probe_id"] for r in rows])
    picked = sorted(rng.sample(ids, min(sample_n, len(ids))))
    by_id = {r["probe_id"]: r for r in rows}
    fieldnames = ["probe_id", "vlm_label", "vlm_rationale", "human_label", "agree_or_disagree"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pid in picked:
            r = by_id[pid]
            writer.writerow(
                {
                    "probe_id": pid,
                    "vlm_label": r.get("label", ""),
                    "vlm_rationale": r.get("rationale", ""),
                    "human_label": "",
                    "agree_or_disagree": "",
                }
            )
    meta = path.with_suffix(".meta.json")
    meta.write_text(
        json.dumps(
            {
                "sampling_rule": "pure random sample without looking at VLM labels",
                "seed": seed,
                "sample_n_requested": sample_n,
                "sampled_probe_ids": picked,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return picked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--raw-jsonl", type=Path, default=DEFAULT_RAW_JSONL)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--spotcheck", type=Path, default=DEFAULT_SPOTCHECK)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--spotcheck-n", type=int, default=12)
    parser.add_argument("--spotcheck-seed", type=int, default=20260703)
    parser.add_argument("--no-spotcheck", action="store_true")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    rows = df.to_dict("records")
    if args.offset:
        rows = rows[args.offset :]
    if args.limit:
        rows = rows[: args.limit]
    print(f"Input probes: {len(rows)}", flush=True)

    model, processor = load_model(args.model)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.raw_jsonl.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    with args.raw_jsonl.open("w", encoding="utf-8") as jf:
        for i, row in enumerate(rows, start=1):
            print(f"[{i}/{len(rows)}] {row['probe_id']} ...", flush=True)
            try:
                result = run_one(model, processor, row, args.max_new_tokens, args.temperature)
            except Exception as exc:
                result = {
                    "probe_id": row["probe_id"],
                    "video_id": row.get("video_id", ""),
                    "local_t_start": f"{float(row['local_t_start']):.3f}",
                    "local_t_end": f"{float(row['local_t_end']):.3f}",
                    "center_frame_path": row["center_frame_path"],
                    "sheet_path": row["sheet_path"],
                    "reference_source": REFERENCE_SOURCE,
                    "model_name": MODEL_NAME,
                    "label": "uncertain",
                    "event_t_start_local": "",
                    "event_t_end_local": "",
                    "confidence": "low",
                    "rationale": "",
                    "parse_status": f"runtime_error: {str(exc)[:200]}",
                    "runtime_seconds": "",
                    "peak_gpu_memory_gb": "",
                    "raw_output": "",
                }
                print(f"  ERROR {exc}", flush=True)

            raw_path = args.raw_dir / f"{row['probe_id']}.json"
            raw_obj = dict(result)
            raw_obj["prompt"] = build_prompt(row)
            raw_path.write_text(json.dumps(raw_obj, indent=2, ensure_ascii=False), encoding="utf-8")
            result["raw_response_path"] = str(raw_path)
            jf.write(json.dumps(result, ensure_ascii=False) + "\n")
            jf.flush()
            results.append(result)
            print(
                f"  label={result.get('label')} confidence={result.get('confidence')} "
                f"parse={result.get('parse_status')} runtime={result.get('runtime_seconds')}",
                flush=True,
            )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    write_oracle_csv(args.out, results)
    if not args.no_spotcheck:
        picked = write_spotcheck(args.spotcheck, results, args.spotcheck_n, args.spotcheck_seed)
        print(f"Spotcheck sample ({len(picked)}): {picked}", flush=True)
    print(f"Wrote {args.out}", flush=True)
    print(f"Wrote {args.raw_jsonl}", flush=True)


if __name__ == "__main__":
    main()
