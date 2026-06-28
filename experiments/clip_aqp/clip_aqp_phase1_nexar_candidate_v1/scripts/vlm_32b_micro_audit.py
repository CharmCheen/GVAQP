#!/usr/bin/env python3
"""Bounded Qwen3-VL-32B micro-audit for Nexar-derived labels."""

from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUTPUT_ROOT = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1"
AUDIT_DIR = OUTPUT_ROOT / "audits"
REPORT_DIR = OUTPUT_ROOT / "reports"
CLIP_DIR = OUTPUT_ROOT / "audit_clips/vlm_micro_audit"
ROADCLIP_SCRIPT_DIR = PROJECT_ROOT / "test_vlm/experiments/roadclip_budget_v2"
ROADCLIP_CONFIG = ROADCLIP_SCRIPT_DIR / "config_vlm_oracle_expanded.yaml"
EVENTS_CSV = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_events_nexar_200.csv"
POS_META = PROJECT_ROOT / "datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv"
NEG_META = PROJECT_ROOT / "datasets/casq_external/nexar/hf_metadata_probe/train/negative/metadata.csv"
VIDEO_ROOT = PROJECT_ROOT / "datasets/casq_external/nexar/videos_hf/train"

FPS = 1.0
CLIP_SECONDS = 5.0
NFRAMES = 6
MAX_TOTAL_CALLS = 100
MAX_CALLS_PER_VIDEO = 2
MAX_NEW_TOKENS = 512
RNG_SEED = 271828

PROBE_CSV = AUDIT_DIR / "vlm_32b_feasibility_probe.csv"
PROBE_REPORT = REPORT_DIR / "VLM_32B_FEASIBILITY_PROBE.md"
SAMPLES_CSV = AUDIT_DIR / "vlm_micro_audit_samples.csv"
RESULTS_CSV = AUDIT_DIR / "vlm_micro_audit_results.csv"
AUDIT_REPORT = REPORT_DIR / "VLM_MICRO_AUDIT_REPORT.md"

PROBE_FIELDS = [
    "model_name",
    "device_name",
    "num_gpus",
    "quantization",
    "dtype",
    "fps",
    "frames_per_clip",
    "clip_length_seconds",
    "max_pixels_or_resolution",
    "peak_gpu_memory_observed",
    "runtime_seconds",
    "success_or_failure",
    "error_message",
    "probe_clip_path",
]

SAMPLE_FIELDS = [
    "sample_id",
    "sample_split",
    "used_for_positive_agreement",
    "used_for_random_negative_miss_rate",
    "video_id",
    "external_label",
    "source_video_path",
    "clip_path",
    "clip_start",
    "clip_end",
    "clip_length_seconds",
    "derived_event_id",
    "derived_event_start",
    "derived_event_end",
    "boundary_reference",
    "sampling_reason",
]

RESULT_FIELDS = SAMPLE_FIELDS + [
    "call_index",
    "model_name",
    "quantization",
    "dtype",
    "device_name",
    "num_gpus",
    "fps",
    "frames_per_clip",
    "max_pixels_or_resolution",
    "conservative_positive",
    "risk_level",
    "affected_ego",
    "event_type",
    "starts_outside_ego_path",
    "enters_ego_path",
    "requires_ego_attention",
    "negative_reason",
    "confidence",
    "evidence",
    "raw_response",
    "runtime_seconds",
    "status",
    "error_message",
    "peak_gpu_memory_observed",
]

PROMPT = """You are a conservative traffic-risk verifier for dashcam clips.

Only mark positive when there is a clear ego-path conflict. Do not mark ordinary traffic, many vehicles, normal following, adjacent-lane vehicles, far vehicles, roadside vehicles, or ambiguous lane changes as positive.

Answer these points:
1. Is there an object that starts outside the ego vehicle's projected path?
2. Does it enter, cross, or clearly intrude into the ego vehicle's projected path during this clip?
3. Is it close/relevant enough that the ego vehicle may need to brake, slow down, or pay attention?
4. Is this merely normal following, dense traffic, roadside/static vehicles, or a vehicle already in the ego lane?
5. Is there clear visual evidence, not just possible/ambiguous motion?

Return strict JSON only:
{
  "conservative_positive": "yes|no|uncertain",
  "risk_level": "L0|L1|L2|L3",
  "affected_ego": "true|false|uncertain",
  "event_type": "cut_in|crossing|sudden_braking|lane_conflict|close_approach|normal_following|dense_traffic_only|roadside_static|far_vehicle|ambiguous|none",
  "starts_outside_ego_path": "true|false|uncertain",
  "enters_ego_path": "true|false|uncertain",
  "requires_ego_attention": "true|false|uncertain",
  "negative_reason": "normal_following|dense_traffic_only|already_in_ego_lane|adjacent_no_intrusion|roadside_static|far_vehicle|camera_motion_apparent|insufficient_evidence|none",
  "confidence": "low|medium|high",
  "evidence": "brief visual evidence"
}

Positive only if affected_ego is true, enters_ego_path is true, starts_outside_ego_path is true OR event_type is crossing/sudden_braking/lane_conflict, risk_level is L2/L3, and confidence is medium/high.

If evidence is ambiguous, answer uncertain or no."""


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def encoder_candidates() -> list[str]:
    result = run_cmd(["ffmpeg", "-hide_banner", "-encoders"])
    text = result.stdout + result.stderr
    encoders = [encoder for encoder in ["libx264", "libopenh264", "mpeg4"] if encoder in text]
    if not encoders:
        raise RuntimeError("ffmpeg has no usable MP4 encoder among libx264, libopenh264, mpeg4")
    return encoders


def ffprobe_duration(path: Path) -> float:
    result = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return float(json.loads(result.stdout)["format"]["duration"])


def cut_clip(source: Path, start: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_file() and out_path.stat().st_size > 0:
        return
    last_error = ""
    for encoder in encoder_candidates():
        result = run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(source),
                "-t",
                f"{CLIP_SECONDS:.3f}",
                "-c:v",
                encoder,
                "-an",
                "-loglevel",
                "error",
                str(out_path),
            ]
        )
        if result.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            return
        last_error = result.stderr.strip()
        if out_path.exists():
            out_path.unlink()
    raise RuntimeError(f"ffmpeg failed for {out_path}: {last_error}")


def normalize_video_path(split: str, label: str, video_id: str) -> Path:
    return VIDEO_ROOT / label / video_id


def choose_start(center: float, duration: float) -> float:
    return max(0.0, min(center - CLIP_SECONDS / 2.0, max(0.0, duration - CLIP_SECONDS)))


def load_model_path() -> Path:
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError(f"missing dependency PyYAML: {exc}") from exc
    cfg = yaml.safe_load(ROADCLIP_CONFIG.read_text(encoding="utf-8")) or {}
    return Path(cfg["vlm_model_path"])


def build_samples() -> list[dict]:
    rng = random.Random(RNG_SEED)
    calls_by_video: defaultdict[str, int] = defaultdict(int)
    samples: list[dict] = []

    events = read_csv(EVENTS_CSV)
    rng.shuffle(events)
    for event in events:
        if len([s for s in samples if s["sample_split"] == "near_label"]) >= 50:
            break
        video_id = event["video_id"]
        if calls_by_video[video_id] >= MAX_CALLS_PER_VIDEO:
            continue
        source = normalize_video_path("train", "positive", video_id)
        if not source.is_file():
            continue
        duration = ffprobe_duration(source)
        for boundary_name, boundary_value in [
            ("derived_event_start", float(event["event_start"])),
            ("derived_event_end", float(event["event_end"])),
        ]:
            if calls_by_video[video_id] >= MAX_CALLS_PER_VIDEO:
                break
            if len([s for s in samples if s["sample_split"] == "near_label"]) >= 50:
                break
            start = choose_start(boundary_value, duration)
            clip_id = f"near_{Path(video_id).stem}_{boundary_name}_{len(samples):03d}"
            out = CLIP_DIR / f"{clip_id}_s{int(start * 1000):09d}ms.mp4"
            cut_clip(source, start, out)
            samples.append(
                {
                    "sample_id": clip_id,
                    "sample_split": "near_label",
                    "used_for_positive_agreement": "true",
                    "used_for_random_negative_miss_rate": "false",
                    "video_id": video_id,
                    "external_label": "positive",
                    "source_video_path": str(source),
                    "clip_path": str(out),
                    "clip_start": f"{start:.3f}",
                    "clip_end": f"{start + CLIP_SECONDS:.3f}",
                    "clip_length_seconds": f"{CLIP_SECONDS:.3f}",
                    "derived_event_id": event["event_id"],
                    "derived_event_start": event["event_start"],
                    "derived_event_end": event["event_end"],
                    "boundary_reference": boundary_name,
                    "sampling_reason": "5s window centered near Nexar positive derived boundary",
                }
            )
            calls_by_video[video_id] += 1

    neg_rows = read_csv(NEG_META)
    rng.shuffle(neg_rows)
    for row in neg_rows:
        if len(samples) >= MAX_TOTAL_CALLS:
            break
        video_id = row["file_name"]
        if calls_by_video[video_id] >= MAX_CALLS_PER_VIDEO:
            continue
        source = normalize_video_path("train", "negative", video_id)
        if not source.is_file():
            continue
        duration = ffprobe_duration(source)
        if duration < CLIP_SECONDS:
            continue
        start = rng.uniform(0.0, max(0.0, duration - CLIP_SECONDS))
        clip_id = f"neg_{Path(video_id).stem}_{len(samples):03d}"
        out = CLIP_DIR / f"{clip_id}_s{int(start * 1000):09d}ms.mp4"
        cut_clip(source, start, out)
        samples.append(
            {
                "sample_id": clip_id,
                "sample_split": "random_negative",
                "used_for_positive_agreement": "false",
                "used_for_random_negative_miss_rate": "true",
                "video_id": video_id,
                "external_label": "negative",
                "source_video_path": str(source),
                "clip_path": str(out),
                "clip_start": f"{start:.3f}",
                "clip_end": f"{start + CLIP_SECONDS:.3f}",
                "clip_length_seconds": f"{CLIP_SECONDS:.3f}",
                "derived_event_id": "",
                "derived_event_start": "",
                "derived_event_end": "",
                "boundary_reference": "",
                "sampling_reason": "random 5s window from Nexar-negative video",
            }
        )
        calls_by_video[video_id] += 1

    if len(samples) > MAX_TOTAL_CALLS:
        samples = samples[:MAX_TOTAL_CALLS]
    write_csv(SAMPLES_CSV, samples, SAMPLE_FIELDS)
    return samples


def classify_failure(message: str) -> str:
    msg = message.lower()
    if "out of memory" in msg or "cuda oom" in msg or "oom" in msg:
        return "OOM"
    if "missing qwen3-vl model" in msg or "model directory" in msg or "no such file" in msg:
        return "missing model"
    if "missing dependency" in msg or "no module named" in msg:
        return "missing dependency"
    if "ffmpeg" in msg or "ffprobe" in msg or "video" in msg:
        return "invalid video preprocessing"
    if "runtime" in msg or "cuda" in msg:
        return "runtime error"
    return "other"


def parse_json_object(text: str) -> tuple[dict | None, str]:
    sys.path.insert(0, str(ROADCLIP_SCRIPT_DIR))
    from vlm_utils import parse_json_object as parse

    return parse(text)


def load_oracle(model_path: Path):
    sys.path.insert(0, str(ROADCLIP_SCRIPT_DIR))
    from vlm_utils import load_qwen3_vl

    if not model_path.is_dir():
        raise RuntimeError(f"missing Qwen3-VL model directory: {model_path}")
    return load_qwen3_vl(model_path)


def run_oracle(torch, process_vision_info, model, processor, clip_path: str) -> str:
    messages = [{"role": "user", "content": [{"type": "video", "video": clip_path, "nframes": NFRAMES}, {"type": "text", "text": PROMPT}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs, video_kwargs = process_vision_info(messages, return_video_kwargs=True)
    if isinstance(video_kwargs.get("fps"), list) and len(video_kwargs["fps"]) == 1:
        video_kwargs["fps"] = video_kwargs["fps"][0]
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt", **video_kwargs)
    inputs = inputs.to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
    generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


def norm(value, allowed: set[str], default: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in allowed else default


def norm_bool(value) -> str:
    return norm(value, {"true", "false", "uncertain"}, "uncertain")


def positive_by_rule(row: dict) -> str:
    if row["affected_ego"] != "true":
        return "no"
    if row["enters_ego_path"] != "true":
        return "no"
    starts_or_event = row["starts_outside_ego_path"] == "true" or row["event_type"] in {"crossing", "sudden_braking", "lane_conflict"}
    if not starts_or_event:
        return "no"
    if row["risk_level"] not in {"L2", "L3"}:
        return "no"
    if row["confidence"] not in {"medium", "high"}:
        return "no"
    return "yes"


def normalize_result(raw: str, parsed: dict | None, parse_error: str) -> dict:
    parsed = parsed or {}
    risk = str(parsed.get("risk_level", "L0")).strip().upper()
    if risk not in {"L0", "L1", "L2", "L3"}:
        risk = "L0"
    row = {
        "conservative_positive": norm(parsed.get("conservative_positive"), {"yes", "no", "uncertain"}, "uncertain"),
        "risk_level": risk,
        "affected_ego": norm_bool(parsed.get("affected_ego")),
        "event_type": norm(
            parsed.get("event_type"),
            {"cut_in", "crossing", "sudden_braking", "lane_conflict", "close_approach", "normal_following", "dense_traffic_only", "roadside_static", "far_vehicle", "ambiguous", "none"},
            "ambiguous",
        ),
        "starts_outside_ego_path": norm_bool(parsed.get("starts_outside_ego_path")),
        "enters_ego_path": norm_bool(parsed.get("enters_ego_path")),
        "requires_ego_attention": norm_bool(parsed.get("requires_ego_attention")),
        "negative_reason": norm(
            parsed.get("negative_reason"),
            {"normal_following", "dense_traffic_only", "already_in_ego_lane", "adjacent_no_intrusion", "roadside_static", "far_vehicle", "camera_motion_apparent", "insufficient_evidence", "none"},
            "insufficient_evidence",
        ),
        "confidence": norm(parsed.get("confidence"), {"low", "medium", "high"}, "low"),
        "evidence": str(parsed.get("evidence", ""))[:1200],
        "raw_response": raw,
        "status": "ok",
        "error_message": "",
    }
    if parse_error:
        row.update(
            {
                "conservative_positive": "uncertain",
                "risk_level": "L0",
                "affected_ego": "uncertain",
                "event_type": "ambiguous",
                "starts_outside_ego_path": "uncertain",
                "enters_ego_path": "uncertain",
                "requires_ego_attention": "uncertain",
                "negative_reason": "insufficient_evidence",
                "confidence": "low",
                "evidence": "",
                "status": "parse_failed",
                "error_message": parse_error,
            }
        )
    else:
        row["conservative_positive"] = positive_by_rule(row)
    return row


def gpu_context(torch, model) -> dict:
    dtype = "unknown"
    try:
        dtype = str(next(model.parameters()).dtype)
    except Exception:
        pass
    device_name = "cpu"
    num_gpus = 0
    if torch.cuda.is_available():
        num_gpus = torch.cuda.device_count()
        device_name = torch.cuda.get_device_name(0)
    max_pixels = "video_preprocessor default longest_edge=25165824; source clips 1280x720"
    return {
        "model_name": "Qwen3-VL-32B-Instruct",
        "quantization": "none",
        "dtype": dtype,
        "device_name": device_name,
        "num_gpus": str(num_gpus),
        "fps": "n/a_explicit_nframes",
        "frames_per_clip": str(NFRAMES),
        "clip_length_seconds": f"{CLIP_SECONDS:.3f}",
        "max_pixels_or_resolution": max_pixels,
    }


def peak_memory(torch) -> str:
    if not torch.cuda.is_available():
        return "n/a"
    allocated = torch.cuda.max_memory_allocated() / (1024**3)
    reserved = torch.cuda.max_memory_reserved() / (1024**3)
    return f"allocated={allocated:.3f}GiB; reserved={reserved:.3f}GiB"


def write_probe_report(row: dict) -> None:
    lines = [
        "# VLM 32B Feasibility Probe",
        "",
        f"- model_name: {row.get('model_name', '')}",
        f"- device_name: {row.get('device_name', '')}",
        f"- num_gpus: {row.get('num_gpus', '')}",
        f"- quantization: {row.get('quantization', '')}",
        f"- dtype: {row.get('dtype', '')}",
        f"- fps: {row.get('fps', '')}",
        f"- frames_per_clip: {row.get('frames_per_clip', '')}",
        f"- clip_length_seconds: {row.get('clip_length_seconds', '')}",
        f"- max_pixels_or_resolution: {row.get('max_pixels_or_resolution', '')}",
        "- preprocessing note: inference used explicit pre-sampled video frames (`nframes=6`) on 5-second clips; Qwen3-VL logged a timestamp fallback to fps=24 because video metadata was not passed through, but frame sampling was bounded by `nframes`.",
        f"- peak_gpu_memory_observed: {row.get('peak_gpu_memory_observed', '')}",
        f"- runtime_seconds: {row.get('runtime_seconds', '')}",
        f"- success_or_failure: {row.get('success_or_failure', '')}",
        f"- error_message: {row.get('error_message', '')}",
        f"- probe_clip_path: {row.get('probe_clip_path', '')}",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PROBE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_probe_failure_outputs(message: str, probe_clip: str = "") -> None:
    reason = classify_failure(message)
    row = {
        "model_name": "Qwen3-VL-32B-Instruct",
        "device_name": "",
        "num_gpus": "",
        "quantization": "none",
        "dtype": "",
        "fps": "n/a_explicit_nframes",
        "frames_per_clip": str(NFRAMES),
        "clip_length_seconds": f"{CLIP_SECONDS:.3f}",
        "max_pixels_or_resolution": "video_preprocessor default longest_edge=25165824; source clips 1280x720",
        "peak_gpu_memory_observed": "",
        "runtime_seconds": "0.000",
        "success_or_failure": "failure",
        "error_message": f"{reason}: {message}",
        "probe_clip_path": probe_clip,
    }
    write_csv(PROBE_CSV, [row], PROBE_FIELDS)
    write_probe_report(row)
    write_audit_report([], 0, 0, "NOT_RUN_32B_PROBE_FAILED", f"{reason}: {message}", row)


def write_audit_report(results: list[dict], planned: int, completed: int, result: str, failure_reason: str, probe_row: dict | None = None) -> None:
    valid = [r for r in results if r.get("status") in {"ok", "parse_failed"}]
    near = [r for r in valid if r["sample_split"] == "near_label"]
    neg = [r for r in valid if r["sample_split"] == "random_negative"]
    abstain = [r for r in valid if r.get("conservative_positive") == "uncertain" or r.get("status") == "parse_failed"]
    pos_agree = sum(1 for r in near if r.get("conservative_positive") == "yes") / len(near) if near else None
    neg_miss = sum(1 for r in neg if r.get("conservative_positive") == "yes") / len(neg) if neg else None
    abstain_rate = len(abstain) / len(valid) if valid else None
    ctx = probe_row or (results[0] if results else {})
    lines = [
        "# VLM Micro-Audit Report",
        "",
        f"- model_name: {ctx.get('model_name', 'Qwen3-VL-32B-Instruct')}",
        f"- quantization: {ctx.get('quantization', 'none')}",
        f"- dtype: {ctx.get('dtype', '')}",
        f"- device_name: {ctx.get('device_name', '')}",
        f"- num_gpus: {ctx.get('num_gpus', '')}",
        f"- fps: {ctx.get('fps', f'{FPS:.3f}')}",
        f"- frames_per_clip: {ctx.get('frames_per_clip', int(round(FPS * CLIP_SECONDS)))}",
        f"- max_pixels_or_resolution: {ctx.get('max_pixels_or_resolution', '')}",
        "- preprocessing note: inference used explicit pre-sampled video frames (`nframes=6`) on 5-second clips; Qwen3-VL logged a timestamp fallback to fps=24 because video metadata was not passed through, but frame sampling was bounded by `nframes`.",
        f"- peak_gpu_memory_observed: {ctx.get('peak_gpu_memory_observed', '')}",
        f"- calls_completed / calls_planned: {completed} / {planned}",
        f"- max_total_vlm_calls: {MAX_TOTAL_CALLS}",
        f"- max_calls_per_video: {MAX_CALLS_PER_VIDEO}",
        f"- clip_length_seconds: {CLIP_SECONDS:.3f}",
        f"- positive agreement: {'n/a' if pos_agree is None else f'{pos_agree:.3f}'}",
        f"- random-negative estimated miss rate: {'n/a' if neg_miss is None else f'{neg_miss:.3f}'}",
        f"- abstain rate: {'n/a' if abstain_rate is None else f'{abstain_rate:.3f}'}",
        "- boundary error if available: not evaluated; oracle prompt returns clip-level event presence, not temporal boundaries",
        f"- failure reason: {failure_reason}",
        "",
        f"EXTERNAL_LABEL_AUDIT_RESULT: {result}",
    ]
    if completed and completed < 30 and result not in {"PARTIAL_RUN_INCOMPLETE", "NOT_RUN_32B_PROBE_FAILED"}:
        lines.append("AUDIT_UNDERPOWERED: completed sample count is too small for stable threshold interpretation.")
    lines += ["", "## Status Counts", "", "| status | count |", "|---|---:|"]
    for key, value in Counter(r.get("status", "") for r in results).most_common():
        lines.append(f"| {key} | {value} |")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def derive_result(results: list[dict], completed: int, planned: int) -> tuple[str, str]:
    if completed < planned:
        return "PARTIAL_RUN_INCOMPLETE", "audit failed before completing all planned calls"
    valid = [r for r in results if r.get("status") in {"ok", "parse_failed"}]
    near = [r for r in valid if r["sample_split"] == "near_label"]
    neg = [r for r in valid if r["sample_split"] == "random_negative"]
    if not near or not neg or not valid:
        return "UNRELIABLE", "missing one or more required sample splits"
    pos_agree = sum(1 for r in near if r.get("conservative_positive") == "yes") / len(near)
    neg_miss = sum(1 for r in neg if r.get("conservative_positive") == "yes") / len(neg)
    abstain_rate = sum(1 for r in valid if r.get("conservative_positive") == "uncertain" or r.get("status") == "parse_failed") / len(valid)
    if pos_agree < 0.65 or neg_miss > 0.25 or abstain_rate > 0.50:
        return "UNRELIABLE", ""
    if pos_agree >= 0.85 and neg_miss <= 0.10 and abstain_rate <= 0.15:
        return "AGREES_WELL", ""
    return "PARTIAL_DISAGREEMENT", ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-calls", type=int, default=MAX_TOTAL_CALLS)
    args = parser.parse_args()
    if args.max_calls > MAX_TOTAL_CALLS:
        raise SystemExit(f"--max-calls must be <= {MAX_TOTAL_CALLS}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        samples = build_samples()[: args.max_calls]
        write_csv(SAMPLES_CSV, samples, SAMPLE_FIELDS)
        if not samples:
            raise RuntimeError("no readable audit samples could be constructed")
        probe_sample = samples[0]
        model_path = load_model_path()
        start = time.time()
        torch, process_vision_info, model, processor = load_oracle(model_path)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        raw = run_oracle(torch, process_vision_info, model, processor, probe_sample["clip_path"])
        parsed, parse_error = parse_json_object(raw)
        if parse_error:
            raise RuntimeError(f"probe parse failed: {parse_error}; raw={raw[:500]}")
        ctx = gpu_context(torch, model)
        probe_row = {
            **ctx,
            "peak_gpu_memory_observed": peak_memory(torch),
            "runtime_seconds": f"{time.time() - start:.3f}",
            "success_or_failure": "success",
            "error_message": "",
            "probe_clip_path": probe_sample["clip_path"],
        }
        write_csv(PROBE_CSV, [probe_row], PROBE_FIELDS)
        write_probe_report(probe_row)
    except Exception as exc:
        write_probe_failure_outputs(str(exc))
        print(f"probe_failed={exc}")
        return

    results: list[dict] = []
    completed = 0
    planned = len(samples)
    failure_reason = ""
    try:
        for index, sample in enumerate(samples, 1):
            call_start = time.time()
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            try:
                raw = run_oracle(torch, process_vision_info, model, processor, sample["clip_path"])
                parsed, parse_error = parse_json_object(raw)
                row = normalize_result(raw, parsed, parse_error)
            except Exception as exc:
                row = {
                    "conservative_positive": "uncertain",
                    "risk_level": "L0",
                    "affected_ego": "uncertain",
                    "event_type": "ambiguous",
                    "starts_outside_ego_path": "uncertain",
                    "enters_ego_path": "uncertain",
                    "requires_ego_attention": "uncertain",
                    "negative_reason": "insufficient_evidence",
                    "confidence": "low",
                    "evidence": "",
                    "raw_response": "",
                    "status": "runtime_failed",
                    "error_message": str(exc),
                }
                failure_reason = f"{classify_failure(str(exc))}: {exc}"
            row = {
                **sample,
                **row,
                **ctx,
                "call_index": str(index),
                "runtime_seconds": f"{time.time() - call_start:.3f}",
                "peak_gpu_memory_observed": peak_memory(torch),
            }
            results.append(row)
            completed += 1
            write_csv(RESULTS_CSV, results, RESULT_FIELDS)
            print(f"[{index}/{planned}] {sample['sample_id']} {row['sample_split']} {row['conservative_positive']} {row['status']}", flush=True)
            if row["status"] == "runtime_failed":
                break
    finally:
        write_csv(RESULTS_CSV, results, RESULT_FIELDS)
        result, derived_failure = derive_result(results, completed, planned)
        if derived_failure and not failure_reason:
            failure_reason = derived_failure
        write_audit_report(results, planned, completed, result, failure_reason, probe_row)

    print(f"probe_csv={PROBE_CSV}")
    print(f"samples_csv={SAMPLES_CSV}")
    print(f"results_csv={RESULTS_CSV}")
    print(f"audit_report={AUDIT_REPORT}")


if __name__ == "__main__":
    main()
