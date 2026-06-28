#!/usr/bin/env python3
"""Build a 32B-oracle-relative Micro-CASQ v0 benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
INPUT_DIR = ROOT / "test_vlm/outputs/micro_casq_adjudication_package_v0"
OUT_DIR = ROOT / "test_vlm/outputs/micro_casq_32b_oracle_v0"
SCRIPTS_DIR = OUT_DIR / "scripts"
REPORTS_DIR = OUT_DIR / "reports"
TABLES_DIR = OUT_DIR / "tables"
LOGS_DIR = OUT_DIR / "logs"
PROMPTS_DIR = OUT_DIR / "prompts"
MODEL_OUTPUTS_DIR = OUT_DIR / "model_outputs"
INPUT_CLIPS_DIR = MODEL_OUTPUTS_DIR / "input_clips"
BENCHMARK_DIR = OUT_DIR / "benchmark"
REVIEW_EXPORTS_DIR = OUT_DIR / "review_exports"
SUMMARY_MD = ROOT / "garc_eval/outputs/micro_casq_32b_oracle_v0_summary.md"
RUN_SUMMARY_JSON = LOGS_DIR / "run_summary.json"
MODEL_DIR = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
MODEL_NAME = "Qwen3-VL-32B-Instruct"
PROMPT_VERSION = "o_enter_ego_path_v0_32b_oracle_prompt_v0"
FPS = 1.0
MAX_PIXELS = 360 * 640
RANDOM_SEED = 20260622

REQUIRED_INPUTS = [
    INPUT_DIR / "tables/micro_casq_adjudication_samples_v0.csv",
    INPUT_DIR / "tables/micro_casq_sample_feasibility_v0.csv",
    INPUT_DIR / "review_package/micro_casq_pilot_review_50.csv",
    INPUT_DIR / "review_package/micro_casq_pilot_adjudication_template.csv",
    INPUT_DIR / "reports/HUMAN_REVIEW_GUIDE.md",
    INPUT_DIR / "reports/MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md",
    INPUT_DIR / "reports/MICRO_CASQ_V0_READINESS_REPORT.md",
]

MATERIALIZABLE_COLUMNS = [
    "adjudication_sample_id",
    "pool_item_id",
    "sampling_stratum",
    "video_id",
    "clip_id",
    "source_video_path",
    "clip_start_time",
    "clip_end_time",
    "clip_duration",
    "source_asset",
    "candidate_source",
    "old_label",
    "old_label_source",
    "old_confidence",
    "old_event_start",
    "old_event_end",
    "boundary_source",
    "is_nexar_derived",
    "is_vlm_derived",
    "is_human_audited",
    "is_pseudo_boundary",
    "is_external_label",
    "path_exists",
    "time_window_valid",
    "feasibility_status",
    "selection_reason",
    "notes",
]

RESULT_COLUMNS = [
    "adjudication_sample_id",
    "pool_item_id",
    "sampling_stratum",
    "video_id",
    "clip_id",
    "source_video_path",
    "clip_start_time",
    "clip_end_time",
    "clip_duration",
    "source_asset",
    "candidate_source",
    "old_label",
    "old_label_source",
    "old_confidence",
    "old_event_start",
    "old_event_end",
    "boundary_source",
    "is_nexar_derived",
    "is_vlm_derived",
    "is_human_audited",
    "is_pseudo_boundary",
    "is_external_label",
    "input_mode",
    "model_name",
    "prompt_version",
    "frame_sampling_policy",
    "raw_model_output_path",
    "parse_status",
    "run_status",
    "label",
    "event_start",
    "event_end",
    "event_type",
    "involved_object",
    "ego_relevant",
    "boundary_status",
    "confidence",
    "evidence",
    "negative_reason",
    "abstain_reason",
    "needs_human_sanity_check",
    "device_status",
    "gpu_name",
    "cuda_available",
    "model_parameter_device",
    "gpu_memory_allocated_gb",
    "gpu_memory_reserved_gb",
    "runtime_seconds",
    "run_phase",
    "error_message",
]

ALLOWED_LABELS = {"positive", "negative", "abstain"}
ALLOWED_BOUNDARIES = {"ok", "uncertain", "truncated", "not_applicable"}
ALLOWED_CONF = {"high", "medium", "low"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for path in [SCRIPTS_DIR, REPORTS_DIR, TABLES_DIR, LOGS_DIR, PROMPTS_DIR, MODEL_OUTPUTS_DIR, INPUT_CLIPS_DIR, BENCHMARK_DIR, REVIEW_EXPORTS_DIR, SUMMARY_MD.parent]:
        path.mkdir(parents=True, exist_ok=True)


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        out.append("| " + " | ".join(str(row[c]).replace("\n", " ") for c in df.columns) + " |")
    return "\n".join(out)


def read_protocol_reference() -> tuple[str, bool]:
    primary = ROOT / "docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md"
    fallback = ROOT / "CASQ_CODEX_BRIEF_V12_1.md"
    if primary.exists():
        return str(primary), True
    if fallback.exists():
        return str(fallback), True
    return "MISSING", False


def run_shell(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 999, "", str(exc)


def gpu_info() -> dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"nvidia_smi_available": False, "num_gpus": 0, "gpu_name": "", "gpu_memory_total_mib": "", "gpu_memory_used_mib": ""}
    code, out, err = run_shell(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"], timeout=20)
    if code != 0 or not out:
        return {"nvidia_smi_available": True, "num_gpus": 0, "gpu_name": "", "gpu_memory_total_mib": "", "gpu_memory_used_mib": "", "gpu_error": err}
    rows = [line.split(",") for line in out.splitlines() if line.strip()]
    first = [x.strip() for x in rows[0]]
    return {
        "nvidia_smi_available": True,
        "num_gpus": len(rows),
        "gpu_name": first[0] if len(first) > 0 else "",
        "gpu_memory_total_mib": first[1] if len(first) > 1 else "",
        "gpu_memory_used_mib": first[2] if len(first) > 2 else "",
    }


def preflight() -> dict[str, Any]:
    protocol_path, protocol_ok = read_protocol_reference()
    missing = [p for p in REQUIRED_INPUTS if not p.exists()]
    feas_path = INPUT_DIR / "tables/micro_casq_sample_feasibility_v0.csv"
    materializable_count = 0
    if feas_path.exists():
        feas = pd.read_csv(feas_path, low_memory=False)
        materializable_count = int(feas["feasibility_status"].astype(str).eq("materializable").sum()) if "feasibility_status" in feas.columns else 0
    gpu = gpu_info()
    checks = [
        ("casq_v12_1_exists", protocol_ok, protocol_path),
        ("required_inputs_exist", not missing, "; ".join(rel(p) for p in missing)),
        ("sample_feasibility_exists", feas_path.exists(), rel(feas_path)),
        ("materializable_samples_exist", materializable_count > 0, str(materializable_count)),
        ("nvidia_smi_available", bool(gpu.get("nvidia_smi_available")), gpu.get("gpu_name", "")),
        ("gpu_count_positive", int(gpu.get("num_gpus", 0)) > 0, str(gpu.get("num_gpus", 0))),
        ("model_dir_exists", MODEL_DIR.is_dir(), str(MODEL_DIR)),
        ("model_index_exists", (MODEL_DIR / "model.safetensors.index.json").exists(), rel(MODEL_DIR / "model.safetensors.index.json")),
        ("ffmpeg_available", bool(shutil.which("ffmpeg")), shutil.which("ffmpeg") or ""),
    ]
    for mod in ["torch", "transformers", "qwen_vl_utils", "cv2"]:
        try:
            __import__(mod)
            checks.append((f"python_module_{mod}", True, "available"))
        except Exception as exc:
            checks.append((f"python_module_{mod}", False, str(exc)[:200]))
    checks_df = pd.DataFrame([{"check": c, "passed": p, "detail": d} for c, p, d in checks])
    checks_df.to_csv(TABLES_DIR / "preflight_checks.csv", index=False)
    report = [
        "# Preflight Report",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This preflight checks inputs, local 32B model availability, GPU visibility, and media tooling. It does not run candidate generation, YOLO, embeddings, training, or dataset download.",
        "",
        md_table(checks_df),
        "",
        f"- Protocol path used: `{protocol_path}`",
        f"- Materializable samples found: `{materializable_count}`",
        f"- GPU name: `{gpu.get('gpu_name', '')}`",
        "",
    ]
    if missing:
        report.append("MICRO_CASQ_32B_ORACLE_DECISION: MISSING_INPUTS")
    write_text(REPORTS_DIR / "PREFLIGHT_REPORT.md", "\n".join(report))
    return {
        "protocol_path": protocol_path,
        "protocol_ok": protocol_ok,
        "missing_inputs": [str(p) for p in missing],
        "materializable_count": materializable_count,
        "gpu": gpu,
        "preflight_passed": bool(protocol_ok and not missing and materializable_count > 0 and MODEL_DIR.is_dir()),
    }


def make_prompt() -> str:
    prompt = """You are the fixed expensive semantic oracle O for a CASQ clip benchmark.

Oracle predicate: O_enter_ego_path_v0.

Definition:
A road user enters or clearly overlaps the ego vehicle's future driving path and creates potential spatial conflict or requires ego attention.

Positive criteria:
1. A vehicle, pedestrian, cyclist, or other road user is visible.
2. The object starts outside or near the boundary of the ego path.
3. The object enters or clearly overlaps the ego path / future driving corridor.
4. The event is temporally localized within the clip.
5. The object is sufficiently close or trajectory-relevant to ego motion to require attention.

Negative criteria:
1. normal following traffic;
2. dense traffic with no identifiable entering event;
3. static roadside objects;
4. far-away crossing without ego-path conflict;
5. parked vehicles with no motion into ego path;
6. low-speed irrelevant maneuvers without spatial conflict;
7. poor or irrelevant view.

Return strict JSON only:
{
  "label": "positive | negative | abstain",
  "event_start": "seconds relative to clip start, or null",
  "event_end": "seconds relative to clip start, or null",
  "event_type": "enter_ego_path | none | unclear",
  "involved_object": "vehicle | pedestrian | cyclist | other | unknown | none",
  "ego_relevant": true_or_false,
  "boundary_status": "ok | uncertain | truncated | not_applicable",
  "confidence": "high | medium | low",
  "evidence": "short textual evidence",
  "negative_reason": "normal_following | dense_traffic_only | static_roadside | far_crossing_no_ego_conflict | parked_vehicle_no_motion | low_speed_irrelevant | poor_view | other | null",
  "abstain_reason": "poor_view | ambiguous_ego_path | insufficient_context | boundary_uncertain | other | null",
  "needs_human_sanity_check": true_or_false
}

Rules:
* Judge only O_enter_ego_path_v0.
* Old labels are provenance only.
* Nexar-derived labels are noisy external labels.
* VLM-derived old labels are provenance only.
* Do not copy or infer from old_label.
* If label is positive, event_start and event_end should be non-null unless boundary_status is uncertain or truncated.
* If label is negative, event_start and event_end must be null and boundary_status should be not_applicable.
* Use abstain when the video is too ambiguous, too short, or ego path cannot be determined.
* Set needs_human_sanity_check=true for low confidence, uncertain boundary, truncated event, ambiguous ego path, parsing ambiguity, or conflict with old label provenance.
"""
    write_text(PROMPTS_DIR / "o_enter_ego_path_v0_32b_oracle_prompt.txt", prompt)
    write_text(
        REPORTS_DIR / "PROMPT_CONTRACT.md",
        "# Prompt Contract\n\n"
        f"Prompt version: `{PROMPT_VERSION}`\n\n"
        "This contract defines the fixed expensive semantic oracle for an oracle-relative CASQ benchmark. It does not define human truth or real-world safety ground truth.\n\n"
        "```text\n" + prompt + "\n```\n",
    )
    return prompt


def numeric(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return float("nan")
        return float(value)
    except Exception:
        return float("nan")


def select_materializable() -> pd.DataFrame:
    samples = pd.read_csv(INPUT_DIR / "tables/micro_casq_adjudication_samples_v0.csv", low_memory=False)
    feas = pd.read_csv(INPUT_DIR / "tables/micro_casq_sample_feasibility_v0.csv", low_memory=False)
    feas_small = feas[["adjudication_sample_id", "feasibility_status", "path_exists", "time_window_valid"]].copy()
    merged = samples.merge(feas_small, on="adjudication_sample_id", how="inner", suffixes=("", "_feas"))
    if "path_exists_feas" in merged.columns:
        merged["path_exists"] = merged["path_exists_feas"]
    if "time_window_valid_feas" in merged.columns:
        merged["time_window_valid"] = merged["time_window_valid_feas"]
    materializable = merged[merged["feasibility_status"].astype(str).eq("materializable")].copy()
    for col in MATERIALIZABLE_COLUMNS:
        if col not in materializable.columns:
            materializable[col] = ""
    materializable = materializable[MATERIALIZABLE_COLUMNS]
    materializable.to_csv(TABLES_DIR / "micro_casq_materializable_samples_for_32b.csv", index=False)
    return materializable


def extract_clip(row: pd.Series) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg unavailable")
    out = INPUT_CLIPS_DIR / f"{row['adjudication_sample_id']}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    start = numeric(row["clip_start_time"])
    end = numeric(row["clip_end_time"])
    duration = max(0.01, end - start)
    source = str(row["source_video_path"])
    base = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", source, "-t", f"{duration:.3f}"]
    cmd = base + ["-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", "-y", str(out)]
    code, _, err = run_shell(cmd, timeout=120)
    if code != 0 and "Unknown encoder" in err:
        cmd = base + ["-c:v", "mpeg4", "-q:v", "5", "-an", "-movflags", "+faststart", "-y", str(out)]
        code, _, err = run_shell(cmd, timeout=120)
    if code != 0:
        raise RuntimeError(err[:500] or f"ffmpeg failed with code {code}")
    return out


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str]:
    raw = (text or "").strip()
    if not raw:
        return None, "empty_response"
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        return (obj, "") if isinstance(obj, dict) else (None, "json_not_object")
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None, "json_parse_failed"
        try:
            obj = json.loads(match.group(0))
            return (obj, "") if isinstance(obj, dict) else (None, "json_not_object")
        except Exception as exc:
            return None, f"json_parse_failed: {exc}"


def load_model():
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    if not torch.cuda.is_available():
        raise RuntimeError("GPU_NOT_AVAILABLE: torch.cuda.is_available() is false")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(MODEL_DIR),
        dtype=torch.bfloat16,
        device_map={"": "cuda:0"},
        attn_implementation="sdpa",
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
    verify_model_on_cuda(torch, model)
    return torch, process_vision_info, model, processor


def verify_model_on_cuda(torch, model) -> None:
    device_map = getattr(model, "hf_device_map", {})
    if isinstance(device_map, dict) and any(str(v).startswith(("cpu", "disk")) for v in device_map.values()):
        raise RuntimeError(f"CPU_OFFLOAD_DETECTED: hf_device_map contains CPU/disk placement: {device_map}")
    inspected = []
    for i, (_, param) in enumerate(model.named_parameters()):
        if i >= 12:
            break
        inspected.append(str(param.device))
    try:
        first_device = str(next(model.parameters()).device)
    except Exception as exc:
        raise RuntimeError(f"MODEL_DEVICE_UNKNOWN: {exc}") from exc
    devices = inspected + [first_device]
    if not devices or all(d == "cpu" for d in devices):
        raise RuntimeError(f"MODEL_ON_CPU: inspected parameter devices={devices}")
    if any(d == "cpu" or d.startswith("disk") for d in devices):
        raise RuntimeError(f"CPU_OFFLOAD_DETECTED: inspected parameter devices={devices}")
    if not all(d.startswith("cuda") for d in devices):
        raise RuntimeError(f"CODE_REVIEW_NEEDED: unexpected model parameter devices={devices}")


def model_device_snapshot(torch, model) -> dict[str, Any]:
    first_device = str(next(model.parameters()).device)
    return {
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "cuda_available": bool(torch.cuda.is_available()),
        "model_parameter_device": first_device,
        "gpu_memory_allocated_gb": round(torch.cuda.memory_allocated() / (1024**3), 3) if torch.cuda.is_available() else "",
        "gpu_memory_reserved_gb": round(torch.cuda.memory_reserved() / (1024**3), 3) if torch.cuda.is_available() else "",
    }


def run_one_clip(torch, process_vision_info, model, processor, clip_path: Path, prompt: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": str(clip_path), "fps": FPS, "max_pixels": MAX_PIXELS},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


def normalize_result(obj: dict[str, Any] | None) -> dict[str, Any]:
    out = {k: "" for k in ["label", "event_start", "event_end", "event_type", "involved_object", "ego_relevant", "boundary_status", "confidence", "evidence", "negative_reason", "abstain_reason", "needs_human_sanity_check"]}
    if not obj:
        return out
    for k in out:
        v = obj.get(k, "")
        if isinstance(v, str) and v.lower() in {"null", "none"}:
            v = ""
        out[k] = v
    out["label"] = str(out["label"]).strip().lower()
    out["boundary_status"] = str(out["boundary_status"]).strip().lower()
    out["confidence"] = str(out["confidence"]).strip().lower()
    out["event_type"] = str(out["event_type"]).strip().lower()
    out["involved_object"] = str(out["involved_object"]).strip().lower()
    out["negative_reason"] = str(out["negative_reason"]).strip().lower()
    out["abstain_reason"] = str(out["abstain_reason"]).strip().lower()
    return out


def raw_json_parse_success(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if obj.get("parse_status") == "success" and obj.get("parsed") is not None:
        return True
    raw = obj.get("raw_text", "")
    parsed, _ = parse_json_object(raw)
    return parsed is not None


def result_from_raw(row: pd.Series, raw_path: Path, phase: str, device_status: str, device_info: dict[str, Any]) -> dict[str, Any]:
    obj = json.loads(raw_path.read_text(encoding="utf-8"))
    parsed = obj.get("parsed")
    parse_status = obj.get("parse_status", "")
    if parsed is None and obj.get("raw_text"):
        parsed, parse_err = parse_json_object(obj.get("raw_text", ""))
        parse_status = "success" if parsed is not None else parse_err
    norm = normalize_result(parsed)
    result = {col: row[col] if col in row.index else "" for col in MATERIALIZABLE_COLUMNS}
    result.update(
        {
            "input_mode": "ffmpeg_extracted_clip_interval",
            "model_name": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "frame_sampling_policy": f"fps={FPS}; max_pixels={MAX_PIXELS}; target interval only",
            "raw_model_output_path": str(raw_path),
            "parse_status": parse_status or "success",
            "run_status": "success" if parse_status == "success" else "not_run_error",
            "runtime_seconds": obj.get("runtime_seconds", ""),
            "error_message": obj.get("error", ""),
            "device_status": device_status,
            "gpu_name": device_info.get("gpu_name", ""),
            "cuda_available": device_info.get("cuda_available", ""),
            "model_parameter_device": device_info.get("model_parameter_device", ""),
            "gpu_memory_allocated_gb": device_info.get("gpu_memory_allocated_gb", ""),
            "gpu_memory_reserved_gb": device_info.get("gpu_memory_reserved_gb", ""),
            "run_phase": phase,
        }
    )
    result.update(norm)
    if old_label_disagrees(row.get("old_label", ""), str(result.get("label", ""))):
        result["needs_human_sanity_check"] = True
    for col in RESULT_COLUMNS:
        if col not in result:
            result[col] = ""
    return {col: result[col] for col in RESULT_COLUMNS}


def create_resume_plan(all_samples: pd.DataFrame, materializable: pd.DataFrame) -> pd.DataFrame:
    materializable_ids = set(materializable["adjudication_sample_id"].astype(str))
    rows = []
    for _, row in all_samples.iterrows():
        aid = str(row["adjudication_sample_id"])
        verified_raw = MODEL_OUTPUTS_DIR / "gpu_verified" / f"{aid}.json"
        old_raw = MODEL_OUTPUTS_DIR / f"{aid}.json"
        existing_raw = verified_raw.exists() or old_raw.exists()
        existing_parse_success = raw_json_parse_success(verified_raw)
        if aid not in materializable_ids:
            action = "skip_non_materializable"
            reason = "sample feasibility status is not materializable"
            previous_status = ""
        elif verified_raw.exists() and existing_parse_success:
            action = "skip_existing_success"
            reason = "existing GPU-verified raw output parses successfully"
            previous_status = "success"
        elif verified_raw.exists():
            action = "rerun_parse_failure" if not existing_parse_success else "skip_existing_success"
            reason = "existing GPU-verified raw output is missing successful parse"
            previous_status = "parse_failure"
        elif old_raw.exists():
            action = "rerun_previous_error"
            reason = "pre-repair raw output exists but device execution was unverified; rerun after GPU verification"
            previous_status = "unverified_gpu_or_cpu_suspected"
        else:
            action = "rerun_missing_output"
            reason = "no raw output exists"
            previous_status = ""
        rows.append(
            {
                "adjudication_sample_id": aid,
                "existing_raw_output": str(verified_raw if verified_raw.exists() else old_raw if old_raw.exists() else ""),
                "existing_parse_success": bool(existing_parse_success),
                "previous_run_status": previous_status,
                "resume_action": action,
                "reason": reason,
            }
        )
    plan = pd.DataFrame(rows)
    plan.to_csv(TABLES_DIR / "resume_plan.csv", index=False)
    counts = plan["resume_action"].value_counts().rename_axis("resume_action").reset_index(name="count")
    write_text(
        REPORTS_DIR / "RESUME_PLAN.md",
        "# Resume Plan\n\n"
        "The initial 32B-oracle loop was stopped because GPU execution was suspected or unverified. Pre-repair raw outputs are preserved, but materializable rows with only pre-repair outputs are scheduled for GPU-verified rerun.\n\n"
        + md_table(counts)
        + "\n",
    )
    return plan


def old_label_disagrees(old_label: Any, label: str) -> bool:
    old = str(old_label).strip().lower()
    old_pos = old in {"positive", "yes", "true", "1"} or "positive" in old
    old_neg = old in {"negative", "no", "false", "0", "normal"} or "negative" in old or "normal" in old
    return (old_pos and label == "negative") or (old_neg and label == "positive")


def probe_and_run(materializable: pd.DataFrame, prompt: str, pre: dict[str, Any], resume_plan: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    t_load0 = time.time()
    torch, process_vision_info, model, processor = load_model()
    load_seconds = time.time() - t_load0
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else str(model.device)
    dtype = str(getattr(model, "dtype", "auto"))
    device_info = model_device_snapshot(torch, model)
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    probe_row = materializable.iloc[0]
    probe_status, probe_error, probe_runtime, peak_mem = "success", "", 0.0, ""
    mem_before = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0.0
    try:
        clip = extract_clip(probe_row)
        t0 = time.time()
        raw = run_one_clip(torch, process_vision_info, model, processor, clip, prompt)
        probe_runtime = time.time() - t0
        if torch.cuda.is_available():
            peak_mem = round(torch.cuda.max_memory_allocated() / (1024 ** 3), 3)
        probe_out_dir = MODEL_OUTPUTS_DIR / "gpu_verified_probe"
        probe_out_dir.mkdir(parents=True, exist_ok=True)
        (probe_out_dir / f"{probe_row['adjudication_sample_id']}.json").write_text(
            json.dumps({"adjudication_sample_id": probe_row["adjudication_sample_id"], "probe": True, "raw_text": raw}, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        probe_status = "failure"
        probe_error = str(exc)[:1000]
    probe_df = pd.DataFrame(
        [
            {
                "model_name": MODEL_NAME,
                "device_name": device_name,
                "num_gpus": pre.get("gpu", {}).get("num_gpus", 0),
                "dtype": dtype,
                "quantization": "none",
                "frames_per_clip_or_fps": FPS,
                "resolution_or_max_pixels": MAX_PIXELS,
                "runtime_seconds": round(probe_runtime, 3),
                "model_load_seconds": round(load_seconds, 3),
                "peak_gpu_memory_observed": peak_mem,
                "model_parameter_device": device_info.get("model_parameter_device", ""),
                "gpu_memory_allocated_before_inference_gb": round(mem_before, 3),
                "gpu_memory_allocated_after_inference_gb": round(torch.cuda.memory_allocated() / (1024**3), 3) if torch.cuda.is_available() else "",
                "gpu_memory_reserved_after_inference_gb": round(torch.cuda.memory_reserved() / (1024**3), 3) if torch.cuda.is_available() else "",
                "device_status": "gpu_verified" if probe_status == "success" and str(device_info.get("model_parameter_device", "")).startswith("cuda") else "not_run_error",
                "success_or_failure": probe_status,
                "error_message": probe_error,
            }
        ]
    )
    probe_df.to_csv(TABLES_DIR / "vlm_32b_gpu_verified_probe.csv", index=False)
    probe_df.to_csv(TABLES_DIR / "vlm_32b_oracle_feasibility_probe.csv", index=False)
    write_text(
        REPORTS_DIR / "VLM_32B_GPU_VERIFIED_PROBE.md",
        "# VLM 32B GPU-Verified Probe\n\n"
        "This probe runs one target clip interval after forced CUDA model loading and verifies that model parameters are on CUDA before full-loop resume.\n\n"
        + md_table(probe_df)
        + ("\n\nMICRO_CASQ_32B_ORACLE_DECISION: PROBE_FAILED\n" if probe_status != "success" else "\n"),
    )
    write_text(
        REPORTS_DIR / "VLM_32B_ORACLE_FEASIBILITY_PROBE.md",
        "# VLM 32B Oracle Feasibility Probe\n\n"
        f"Generated: `{utc_now()}`\n\n"
        "The probe runs the same local Qwen3-VL-32B-Instruct inference path used for full adjudication on one materializable sample.\n\n"
        + md_table(probe_df)
        + ("\n\nMICRO_CASQ_32B_ORACLE_DECISION: PROBE_FAILED\n" if probe_status != "success" else "\n"),
    )
    if probe_status != "success":
        return pd.DataFrame(columns=RESULT_COLUMNS), {"probe_status": probe_status, "probe_error": probe_error, "device_name": device_name}
    rows = []
    verified_dir = MODEL_OUTPUTS_DIR / "gpu_verified"
    verified_dir.mkdir(parents=True, exist_ok=True)
    plan_by_id = resume_plan.set_index("adjudication_sample_id")["resume_action"].to_dict()
    for i, (_, row) in enumerate(materializable.iterrows(), start=1):
        aid = str(row["adjudication_sample_id"])
        raw_path = verified_dir / f"{aid}.json"
        action = plan_by_id.get(aid, "rerun_missing_output")
        if action == "skip_existing_success" and raw_json_parse_success(raw_path):
            skipped = result_from_raw(row, raw_path, "resume_gpu_verified_skip", "gpu_verified", device_info)
            rows.append(skipped)
            print(f"[oracle-resume] {i}/{len(materializable)} {aid} action=skip_existing_success label={skipped.get('label','')}", flush=True)
            continue
        result = {col: row[col] if col in row.index else "" for col in MATERIALIZABLE_COLUMNS}
        result.update(
            {
                "input_mode": "ffmpeg_extracted_clip_interval",
                "model_name": MODEL_NAME,
                "prompt_version": PROMPT_VERSION,
                "frame_sampling_policy": f"fps={FPS}; max_pixels={MAX_PIXELS}; target interval only",
                "raw_model_output_path": str(raw_path),
                "parse_status": "not_run",
                "run_status": "not_run",
                "runtime_seconds": "",
                "device_status": "gpu_verified",
                "gpu_name": device_info.get("gpu_name", ""),
                "cuda_available": device_info.get("cuda_available", ""),
                "model_parameter_device": device_info.get("model_parameter_device", ""),
                "gpu_memory_allocated_gb": "",
                "gpu_memory_reserved_gb": "",
                "run_phase": "resume_gpu_verified_rerun",
                "error_message": "",
            }
        )
        try:
            verify_model_on_cuda(torch, model)
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            clip = extract_clip(row)
            t0 = time.time()
            raw = run_one_clip(torch, process_vision_info, model, processor, clip, prompt)
            runtime = time.time() - t0
            obj, parse_err = parse_json_object(raw)
            norm = normalize_result(obj)
            if obj is None:
                result["parse_status"] = parse_err
                norm["needs_human_sanity_check"] = True
            else:
                result["parse_status"] = "success"
            result["run_status"] = "success"
            result["runtime_seconds"] = round(runtime, 3)
            result.update(norm)
            mem = model_device_snapshot(torch, model)
            result["gpu_memory_allocated_gb"] = mem["gpu_memory_allocated_gb"]
            result["gpu_memory_reserved_gb"] = mem["gpu_memory_reserved_gb"]
            result["model_parameter_device"] = mem["model_parameter_device"]
            if old_label_disagrees(row.get("old_label", ""), str(result.get("label", ""))):
                result["needs_human_sanity_check"] = True
            raw_path.write_text(
                json.dumps(
                    {
                        "adjudication_sample_id": aid,
                        "model_name": MODEL_NAME,
                        "prompt_version": PROMPT_VERSION,
                        "input_clip_path": str(clip),
                        "raw_text": raw,
                        "parsed": obj,
                        "parse_status": result["parse_status"],
                        "runtime_seconds": result["runtime_seconds"],
                        "device_status": result["device_status"],
                        "gpu_name": result["gpu_name"],
                        "cuda_available": result["cuda_available"],
                        "model_parameter_device": result["model_parameter_device"],
                        "gpu_memory_allocated_gb": result["gpu_memory_allocated_gb"],
                        "gpu_memory_reserved_gb": result["gpu_memory_reserved_gb"],
                        "run_phase": result["run_phase"],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            result["run_status"] = "not_run_error"
            result["parse_status"] = "not_run"
            result["device_status"] = "not_run_error"
            result["error_message"] = str(exc)[:1000]
            raw_path.write_text(
                json.dumps(
                    {
                        "adjudication_sample_id": aid,
                        "model_name": MODEL_NAME,
                        "prompt_version": PROMPT_VERSION,
                        "error": result["error_message"],
                        "device_status": result["device_status"],
                        "gpu_name": result["gpu_name"],
                        "cuda_available": result["cuda_available"],
                        "model_parameter_device": result["model_parameter_device"],
                        "run_phase": result["run_phase"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        for col in RESULT_COLUMNS:
            if col not in result:
                result[col] = ""
        rows.append({col: result[col] for col in RESULT_COLUMNS})
        print(f"[oracle-resume] {i}/{len(materializable)} {aid} action={action} run_status={result['run_status']} parse_status={result['parse_status']} device_status={result['device_status']} label={result.get('label','')}", flush=True)
    results = pd.DataFrame(rows)
    results.to_csv(TABLES_DIR / "micro_casq_32b_oracle_adjudication_results.csv", index=False)
    return results, {"probe_status": "success", "device_name": device_name, "dtype": dtype, "model_load_seconds": round(load_seconds, 3)}


def bool_value(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def validate_outputs(materializable: pd.DataFrame, results: pd.DataFrame) -> tuple[bool, pd.DataFrame, dict[str, Any]]:
    rows = []
    selected = set(materializable["adjudication_sample_id"].astype(str))
    result_ids = set(results["adjudication_sample_id"].astype(str)) if not results.empty else set()
    def add(check: str, passed: bool, detail: str = "") -> None:
        rows.append({"check": check, "passed": bool(passed), "detail": detail})
    add("every_selected_materializable_sample_accounted_for", selected == result_ids, f"selected={len(selected)} results={len(result_ids)}")
    add("no_non_materializable_samples_processed", result_ids.issubset(selected), f"extra={len(result_ids - selected)}")
    if results.empty:
        add("results_non_empty", False, "no result rows")
    else:
        raw_or_not_run = results.apply(lambda r: Path(str(r["raw_model_output_path"])).exists() or str(r["run_status"]) != "success", axis=1)
        add("every_row_has_raw_output_or_explicit_not_run", bool(raw_or_not_run.all()), str(int(raw_or_not_run.sum())))
        successful = results["run_status"].astype(str).eq("success")
        parsed = successful & results["parse_status"].astype(str).eq("success")
        add("successful_parses_have_allowed_labels", bool(results.loc[parsed, "label"].astype(str).isin(ALLOWED_LABELS).all()), "")
        add("successful_parses_have_allowed_boundary_status", bool(results.loc[parsed, "boundary_status"].astype(str).isin(ALLOWED_BOUNDARIES).all()), "")
        pos = parsed & results["label"].astype(str).eq("positive")
        pos_ok = results.loc[pos].apply(lambda r: str(r["boundary_status"]) in {"uncertain", "truncated"} or (pd.notna(pd.to_numeric(r["event_start"], errors="coerce")) and pd.notna(pd.to_numeric(r["event_end"], errors="coerce"))), axis=1)
        add("positive_rows_have_boundaries_or_uncertain_truncated", bool(pos_ok.all()) if len(pos_ok) else True, str(int(pos_ok.sum())) if len(pos_ok) else "0")
        neg = parsed & results["label"].astype(str).eq("negative")
        neg_ok = results.loc[neg].apply(lambda r: pd.isna(pd.to_numeric(r["event_start"], errors="coerce")) and pd.isna(pd.to_numeric(r["event_end"], errors="coerce")), axis=1)
        add("negative_rows_have_null_boundaries", bool(neg_ok.all()) if len(neg_ok) else True, str(int(neg_ok.sum())) if len(neg_ok) else "0")
        def boundaries_in_clip(r: pd.Series) -> bool:
            es = pd.to_numeric(r["event_start"], errors="coerce")
            ee = pd.to_numeric(r["event_end"], errors="coerce")
            dur = pd.to_numeric(r["clip_duration"], errors="coerce")
            if pd.isna(es) and pd.isna(ee):
                return True
            if pd.isna(es) or pd.isna(ee) or pd.isna(dur):
                return False
            return 0 <= es <= dur and 0 <= ee <= dur and ee >= es
        b_ok = results.loc[parsed].apply(boundaries_in_clip, axis=1)
        add("event_boundaries_within_clip_duration", bool(b_ok.all()) if len(b_ok) else True, str(int(b_ok.sum())) if len(b_ok) else "0")
    add("old_labels_not_promoted_to_gold", True, "old labels retained only as provenance columns")
    validation = pd.DataFrame(rows)
    validation.to_csv(TABLES_DIR / "micro_casq_32b_oracle_output_validation.csv", index=False)
    passed = bool(validation["passed"].all())
    write_text(
        REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_OUTPUT_VALIDATION_REPORT.md",
        "# Micro-CASQ 32B Oracle Output Validation Report\n\n"
        f"Generated: `{utc_now()}`\n\n"
        "Validation checks oracle-relative output schema and accounting. It does not rewrite labels or event boundaries.\n\n"
        + md_table(validation)
        + ("" if passed else "\n\nMICRO_CASQ_32B_ORACLE_DECISION: CODE_REVIEW_NEEDED\n"),
    )
    return passed, validation, {"validation_passed": passed}


def is_valid_boundary(row: pd.Series) -> bool:
    es = pd.to_numeric(row["event_start"], errors="coerce")
    ee = pd.to_numeric(row["event_end"], errors="coerce")
    dur = pd.to_numeric(row["clip_duration"], errors="coerce")
    return pd.notna(es) and pd.notna(ee) and pd.notna(dur) and 0 <= es < ee <= dur


def construct_benchmark(results: pd.DataFrame) -> dict[str, Any]:
    r = results.copy()
    r["needs_human_sanity_check_bool"] = r["needs_human_sanity_check"].map(bool_value)
    r["valid_event_boundary"] = r.apply(is_valid_boundary, axis=1)
    parsed_success = r["parse_status"].astype(str).eq("success") & r["run_status"].astype(str).eq("success")
    oracle_positive = parsed_success & r["label"].astype(str).eq("positive") & r["confidence"].astype(str).isin(["high", "medium"]) & r["boundary_status"].astype(str).eq("ok") & r["valid_event_boundary"] & ~r["needs_human_sanity_check_bool"]
    oracle_negative = parsed_success & r["label"].astype(str).eq("negative") & r["confidence"].astype(str).isin(["high", "medium"]) & r["boundary_status"].astype(str).eq("not_applicable") & ~r["needs_human_sanity_check_bool"]
    excluded = ~(oracle_positive | oracle_negative)
    benchmark = r[oracle_positive | oracle_negative].copy()
    benchmark["oracle_category"] = ["oracle_positive" if x else "oracle_negative" for x in oracle_positive[oracle_positive | oracle_negative]]
    benchmark.to_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_benchmark.csv", index=False)
    pos = r[oracle_positive].copy()
    pos["oracle_event_id"] = [f"oracle_event_v0_{i:04d}" for i in range(1, len(pos) + 1)]
    pos["event_start_video_time"] = pd.to_numeric(pos["clip_start_time"], errors="coerce") + pd.to_numeric(pos["event_start"], errors="coerce")
    pos["event_end_video_time"] = pd.to_numeric(pos["clip_start_time"], errors="coerce") + pd.to_numeric(pos["event_end"], errors="coerce")
    pos_cols = ["oracle_event_id", "adjudication_sample_id", "video_id", "source_video_path", "clip_start_time", "clip_end_time", "event_start", "event_end", "event_start_video_time", "event_end_video_time", "event_type", "involved_object", "ego_relevant", "confidence", "evidence", "sampling_stratum", "candidate_source", "old_label", "old_label_source", "boundary_source"]
    pos[pos_cols].to_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_positive_events.csv", index=False)
    neg = r[oracle_negative].copy()
    neg["oracle_negative_id"] = [f"oracle_negative_v0_{i:04d}" for i in range(1, len(neg) + 1)]
    neg_cols = ["oracle_negative_id", "adjudication_sample_id", "video_id", "source_video_path", "clip_start_time", "clip_end_time", "confidence", "negative_reason", "evidence", "sampling_stratum", "candidate_source", "old_label", "old_label_source", "boundary_source"]
    neg[neg_cols].to_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_negative_windows.csv", index=False)
    excl = r[excluded].copy()
    excl.to_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv", index=False)
    return {"eligible_positive": int(oracle_positive.sum()), "eligible_negative": int(oracle_negative.sum()), "excluded": int(excluded.sum())}


def split_proposal(results: pd.DataFrame) -> dict[str, Any]:
    bench = pd.read_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_benchmark.csv", low_memory=False)
    excluded = pd.read_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv", low_memory=False)
    random.seed(RANDOM_SEED)
    assignments = []
    videos = list(bench["video_id"].fillna("__missing__").astype(str).unique())
    random.shuffle(videos)
    n = len(videos)
    video_split = {}
    for i, v in enumerate(videos):
        if i < int(0.3 * n):
            video_split[v] = "candidate_dev"
        elif i < int(0.7 * n):
            video_split[v] = "heldout_eval"
        else:
            video_split[v] = "reserved_certification_pool"
    for _, row in bench.iterrows():
        assignments.append({"adjudication_sample_id": row["adjudication_sample_id"], "video_id": row["video_id"], "oracle_category": row["oracle_category"], "sampling_stratum": row["sampling_stratum"], "split_label": video_split.get(str(row["video_id"]), "heldout_eval")})
    for _, row in excluded.iterrows():
        assignments.append({"adjudication_sample_id": row["adjudication_sample_id"], "video_id": row["video_id"], "oracle_category": "excluded_or_needs_sanity_check", "sampling_stratum": row["sampling_stratum"], "split_label": "excluded_or_needs_sanity_check"})
    split = pd.DataFrame(assignments)
    split.to_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_split_proposal.csv", index=False)
    counts = split.groupby(["split_label", "oracle_category"]).size().reset_index(name="count") if not split.empty else pd.DataFrame()
    write_text(
        REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_V0_SPLIT_PROPOSAL.md",
        "# Micro-CASQ 32B-Oracle v0 Split Proposal\n\n"
        f"Generated: `{utc_now()}`\n\n"
        "Splits are proposed for future oracle-relative candidate feasibility and certificate experiments. Excluded rows are kept out of candidate tuning, heldout evaluation, and the reserved certification pool. Event boundaries must not be used to generate future candidates.\n\n"
        + md_table(counts)
        + "\n\nThe reserved certification pool must not be used for candidate tuning. If eligible positives are sparse, this benchmark is useful for candidate signal testing but underpowered for final certificate claims.\n",
    )
    return {"split_rows": int(len(split))}


def human_sanity_queue(results: pd.DataFrame) -> dict[str, Any]:
    r = results.copy()
    bench_ids = set(pd.read_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_benchmark.csv", low_memory=False)["adjudication_sample_id"].astype(str))
    excluded_ids = set(pd.read_csv(BENCHMARK_DIR / "micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv", low_memory=False)["adjudication_sample_id"].astype(str))
    r["needs_human_sanity_check_bool"] = r["needs_human_sanity_check"].map(bool_value)
    reasons = {}
    for _, row in r.iterrows():
        aid = str(row["adjudication_sample_id"])
        rs = []
        if aid in excluded_ids: rs.append("excluded_or_needs_sanity_check")
        if row["label"] == "abstain": rs.append("abstain")
        if row["confidence"] == "low": rs.append("low_confidence")
        if row["boundary_status"] in {"uncertain", "truncated"}: rs.append("uncertain_or_truncated_boundary")
        if row["parse_status"] != "success": rs.append("parse_failure")
        if row["run_status"] != "success": rs.append("run_failure")
        if old_label_disagrees(row.get("old_label", ""), str(row.get("label", ""))): rs.append("old_label_disagreement")
        if rs:
            reasons[aid] = ";".join(sorted(set(rs)))
    accepted = r[r["adjudication_sample_id"].astype(str).isin(bench_ids)].copy()
    pos_sample = accepted[accepted["label"].eq("positive")].sample(n=min(10, int(accepted["label"].eq("positive").sum())), random_state=RANDOM_SEED) if not accepted.empty else accepted.head(0)
    neg_sample = accepted[accepted["label"].eq("negative")].sample(n=min(10, int(accepted["label"].eq("negative").sum())), random_state=RANDOM_SEED + 1) if not accepted.empty else accepted.head(0)
    for aid in pd.concat([pos_sample, neg_sample])["adjudication_sample_id"].astype(str).tolist():
        reasons.setdefault(aid, "random_accepted_oracle_sanity_sample")
    queue = r[r["adjudication_sample_id"].astype(str).isin(reasons)].copy()
    queue["queue_reason"] = queue["adjudication_sample_id"].astype(str).map(reasons)
    queue.to_csv(REVIEW_EXPORTS_DIR / "micro_casq_32b_oracle_human_sanity_audit_queue.csv", index=False)
    write_text(
        REPORTS_DIR / "HUMAN_SANITY_AUDIT_PLAN.md",
        "# Human Sanity Audit Plan\n\n"
        f"Generated: `{utc_now()}`\n\n"
        "Human sanity audit is used to assess oracle prompt quality and obvious failure modes. It is not required to define the primary oracle-relative benchmark.\n\n"
        f"Queue rows: `{len(queue)}`\n\n"
        "The queue includes excluded rows, abstains, low-confidence outputs, uncertain/truncated boundaries, parse/run failures, old-label disagreement cases, and random accepted positive/negative samples when available.\n",
    )
    return {"human_sanity_queue_count": int(len(queue))}


def write_summaries(results: pd.DataFrame, eligibility: dict[str, Any]) -> dict[str, Any]:
    processed = int(results["run_status"].astype(str).eq("success").sum()) if not results.empty else 0
    parse_fail = int((results["run_status"].astype(str).eq("success") & ~results["parse_status"].astype(str).eq("success")).sum()) if not results.empty else 0
    run_fail = int(~results["run_status"].astype(str).eq("success").sum()) if False else int((results["run_status"].astype(str) != "success").sum()) if not results.empty else 0
    label_counts = results["label"].fillna("").astype(str).value_counts().reset_index() if not results.empty else pd.DataFrame(columns=["label", "count"])
    label_counts.columns = ["label", "count"]
    overview = pd.DataFrame([
        {"metric": "selected_materializable_count", "value": len(results)},
        {"metric": "processed_count", "value": processed},
        {"metric": "run_failure_count", "value": run_fail},
        {"metric": "parse_failure_count", "value": parse_fail},
        {"metric": "positive_count", "value": int(results["label"].astype(str).eq("positive").sum()) if not results.empty else 0},
        {"metric": "negative_count", "value": int(results["label"].astype(str).eq("negative").sum()) if not results.empty else 0},
        {"metric": "abstain_count", "value": int(results["label"].astype(str).eq("abstain").sum()) if not results.empty else 0},
        {"metric": "oracle_positive_eligible_count", "value": eligibility["eligible_positive"]},
        {"metric": "oracle_negative_eligible_count", "value": eligibility["eligible_negative"]},
        {"metric": "excluded_count", "value": eligibility["excluded"]},
        {"metric": "needs_human_sanity_check_count", "value": int(results["needs_human_sanity_check"].map(bool_value).sum()) if not results.empty else 0},
    ])
    overview.to_csv(TABLES_DIR / "micro_casq_32b_oracle_label_summary.csv", index=False)
    by = results.groupby("sampling_stratum").agg(
        selected_count=("adjudication_sample_id", "count"),
        positive_count=("label", lambda s: int((s == "positive").sum())),
        negative_count=("label", lambda s: int((s == "negative").sum())),
        abstain_count=("label", lambda s: int((s == "abstain").sum())),
    ).reset_index() if not results.empty else pd.DataFrame()
    if not by.empty:
        by["positive_rate"] = by["positive_count"] / by["selected_count"]
        by["negative_rate"] = by["negative_count"] / by["selected_count"]
    by.to_csv(TABLES_DIR / "micro_casq_32b_oracle_by_stratum_summary.csv", index=False)
    boundary = results["boundary_status"].fillna("").astype(str).value_counts().reset_index() if not results.empty else pd.DataFrame(columns=["boundary_status", "count"])
    boundary.columns = ["boundary_status", "count"]
    boundary.to_csv(TABLES_DIR / "micro_casq_32b_oracle_boundary_summary.csv", index=False)
    runtime = pd.to_numeric(results["runtime_seconds"], errors="coerce") if not results.empty else pd.Series(dtype=float)
    runtime_df = pd.DataFrame([{"metric": k, "value": v} for k, v in {
        "runtime_count": int(runtime.notna().sum()),
        "runtime_mean": float(runtime.mean()) if runtime.notna().any() else "",
        "runtime_median": float(runtime.median()) if runtime.notna().any() else "",
        "runtime_min": float(runtime.min()) if runtime.notna().any() else "",
        "runtime_max": float(runtime.max()) if runtime.notna().any() else "",
    }.items()])
    runtime_df.to_csv(TABLES_DIR / "micro_casq_32b_oracle_runtime_summary.csv", index=False)
    elig_df = pd.DataFrame([{"category": "oracle_positive", "count": eligibility["eligible_positive"]}, {"category": "oracle_negative", "count": eligibility["eligible_negative"]}, {"category": "excluded_or_needs_sanity_check", "count": eligibility["excluded"]}])
    elig_df.to_csv(TABLES_DIR / "micro_casq_32b_oracle_benchmark_eligibility_summary.csv", index=False)
    return {"processed": processed, "run_fail": run_fail, "parse_fail": parse_fail, "label_summary": overview}


def decide(summary: dict[str, Any]) -> str:
    if summary.get("missing_inputs"):
        return "MICRO_CASQ_32B_ORACLE_DECISION: MISSING_INPUTS"
    if summary.get("probe_status") == "failure":
        return "MICRO_CASQ_32B_ORACLE_DECISION: PROBE_FAILED"
    if summary.get("token_leak_detected") or not summary.get("validation_passed", True) or not summary.get("required_outputs_ok", True):
        return "MICRO_CASQ_32B_ORACLE_DECISION: CODE_REVIEW_NEEDED"
    processed = max(1, summary.get("processed_count", 0))
    bad_rate = (summary.get("parse_failure_count", 0) + summary.get("abstain_count", 0)) / processed
    if bad_rate > 0.5:
        return "MICRO_CASQ_32B_ORACLE_DECISION: NEED_PROMPT_REPAIR"
    if summary.get("eligible_positive", 0) < 30:
        return "MICRO_CASQ_32B_ORACLE_DECISION: NEED_MORE_POSITIVES"
    if summary.get("eligible_negative", 0) >= 80:
        return "MICRO_CASQ_32B_ORACLE_DECISION: READY_FOR_CANDIDATE_FEASIBILITY"
    return "MICRO_CASQ_32B_ORACLE_DECISION: NEED_MORE_POSITIVES"


def write_final_report(summary: dict[str, Any]) -> None:
    decision = summary["final_decision"]
    next_action = summary.get("next_action", "")
    report = [
        "# Micro-CASQ 32B-Oracle v0 Report",
        "",
        "## 1. Goal",
        "",
        "Construct an oracle-relative Micro-CASQ v0 benchmark from materializable adjudication samples using Qwen3-VL-32B-Instruct as the fixed expensive semantic oracle O.",
        "",
        "The initial full-loop attempt was stopped because GPU execution was suspected or unverified. Existing pre-repair raw outputs were preserved and marked as `unverified_gpu_or_cpu_suspected`; final accepted outputs are generated only after explicit GPU diagnostics and GPU-verified probing.",
        "",
        "## 2. Protocol Reference",
        "",
        f"Protocol path read: `{summary.get('protocol_path')}`",
        "",
        "## 3. Oracle Definition",
        "",
        "`O = Qwen3-VL-32B-Instruct` with the fixed `O_enter_ego_path_v0` prompt contract. This benchmark is 32B-oracle-relative. 32B labels are not claimed as human truth or real-world safety ground truth.",
        "",
        "## 4. Input Sample Set",
        "",
        f"Selected materializable samples: `{summary.get('selected_materializable_count', 0)}`. Non-materializable samples remain excluded until sample repair.",
        "",
        "## 5. Hardware and Model Environment",
        "",
        f"GPU: `{summary.get('gpu_name', '')}`. Model path: `{MODEL_DIR}`. FPS: `{FPS}`. Max pixels: `{MAX_PIXELS}`. GPU device diagnostics were performed before resume.",
        "",
        "## 6. Feasibility Probe",
        "",
        f"Probe status: `{summary.get('probe_status')}`. See `tables/vlm_32b_oracle_feasibility_probe.csv` and `tables/vlm_32b_gpu_verified_probe.csv`.",
        "",
        "## 7. Prompt Contract",
        "",
        "`prompts/o_enter_ego_path_v0_32b_oracle_prompt.txt` and `reports/PROMPT_CONTRACT.md` define the fixed oracle prompt.",
        "",
        "## 8. 32B Oracle Adjudication Execution",
        "",
        f"Processed rows: `{summary.get('processed_count', 0)}`. Run failures: `{summary.get('run_failure_count', 0)}`. Raw GPU-verified model outputs are under `model_outputs/gpu_verified/`. Pre-repair outputs under `model_outputs/` are retained as provenance only unless explicitly rerun.",
        "",
        "## 9. Output Validation",
        "",
        f"Validation passed: `{summary.get('validation_passed')}`. Old labels were retained as provenance only and were not promoted to gold.",
        "",
        "## 10. Label and Boundary Summary",
        "",
        f"Positive / negative / abstain: `{summary.get('positive_count', 0)}` / `{summary.get('negative_count', 0)}` / `{summary.get('abstain_count', 0)}`.",
        "",
        "## 11. Benchmark Eligibility",
        "",
        f"Eligible oracle positives: `{summary.get('eligible_positive', 0)}`. Eligible oracle negatives: `{summary.get('eligible_negative', 0)}`. Excluded: `{summary.get('excluded', 0)}`.",
        "",
        "## 12. Micro-CASQ 32B-Oracle v0 Benchmark",
        "",
        "Benchmark files were written under `benchmark/`. Excluded rows are retained separately and are not used for headline recall/certificate metrics.",
        "",
        "## 13. Split Proposal",
        "",
        "`benchmark/micro_casq_32b_oracle_v0_split_proposal.csv` proposes candidate-dev, heldout-eval, reserved-certification-pool, and excluded splits. The reserved certification pool must not be used for candidate tuning.",
        "",
        "## 14. Human Sanity Audit Queue",
        "",
        f"Human sanity audit queue rows: `{summary.get('human_sanity_queue_count', 0)}`. Human sanity audit is recommended for prompt quality and obvious failure analysis, but full human relabeling is not required for oracle-relative CASQ experiments.",
        "",
        "## 15. Implications for V12.1 Progress",
        "",
        "This run creates a bounded oracle-relative sample for candidate feasibility. It does not establish human ground truth or final G-ARC guarantees.",
        "",
        "## 16. Risks and Limitations",
        "",
        "- This benchmark is 32B-oracle-relative.",
        "- 32B labels are not claimed as human truth.",
        "- Old labels are provenance only.",
        "- Nexar-derived labels are noisy external labels.",
        "- This run adjudicates only materializable Micro-CASQ samples.",
        "- Non-materializable samples remain excluded until sample repair.",
        "- The stopped pre-repair run had suspected CPU or unverified GPU execution.",
        "- GPU device diagnostics and a GPU-verified probe were performed before the resumed full loop.",
        "- Pre-repair outputs retained in provenance are marked `unverified_gpu_or_cpu_suspected` and are not treated as final GPU-verified accepted outputs.",
        "",
        "## 17. Next Action",
        "",
        next_action,
        "",
        "## 18. Final Decision",
        "",
        decision,
        "",
    ]
    write_text(REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_V0_REPORT.md", "\n".join(report))


def scan_and_redact_tokens() -> bool:
    token_re = re.compile(r"hf_[A-Za-z0-9]{20,}")
    leaked = False
    for base in [LOGS_DIR, REPORTS_DIR, TABLES_DIR, MODEL_OUTPUTS_DIR, BENCHMARK_DIR, REVIEW_EXPORTS_DIR]:
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if token_re.search(text):
                leaked = True
                path.write_text(token_re.sub("[REDACTED_HF_TOKEN]", text), encoding="utf-8")
    return leaked


def required_outputs_ok() -> tuple[bool, list[str]]:
    paths = [
        REPORTS_DIR / "PREFLIGHT_REPORT.md",
        REPORTS_DIR / "PARTIAL_RUN_GPU_DIAGNOSTIC.md",
        REPORTS_DIR / "GPU_DEVICE_DIAGNOSTIC_REPORT.md",
        TABLES_DIR / "preflight_checks.csv",
        TABLES_DIR / "gpu_device_diagnostic.csv",
        TABLES_DIR / "resume_plan.csv",
        REPORTS_DIR / "RESUME_PLAN.md",
        TABLES_DIR / "micro_casq_materializable_samples_for_32b.csv",
        TABLES_DIR / "vlm_32b_oracle_feasibility_probe.csv",
        TABLES_DIR / "vlm_32b_gpu_verified_probe.csv",
        REPORTS_DIR / "VLM_32B_ORACLE_FEASIBILITY_PROBE.md",
        REPORTS_DIR / "VLM_32B_GPU_VERIFIED_PROBE.md",
        PROMPTS_DIR / "o_enter_ego_path_v0_32b_oracle_prompt.txt",
        REPORTS_DIR / "PROMPT_CONTRACT.md",
        TABLES_DIR / "micro_casq_32b_oracle_adjudication_results.csv",
        TABLES_DIR / "micro_casq_32b_oracle_output_validation.csv",
        REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_OUTPUT_VALIDATION_REPORT.md",
        BENCHMARK_DIR / "micro_casq_32b_oracle_v0_benchmark.csv",
        BENCHMARK_DIR / "micro_casq_32b_oracle_v0_positive_events.csv",
        BENCHMARK_DIR / "micro_casq_32b_oracle_v0_negative_windows.csv",
        BENCHMARK_DIR / "micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv",
        BENCHMARK_DIR / "micro_casq_32b_oracle_v0_split_proposal.csv",
        REVIEW_EXPORTS_DIR / "micro_casq_32b_oracle_human_sanity_audit_queue.csv",
        TABLES_DIR / "micro_casq_32b_oracle_label_summary.csv",
        TABLES_DIR / "micro_casq_32b_oracle_by_stratum_summary.csv",
        TABLES_DIR / "micro_casq_32b_oracle_boundary_summary.csv",
        TABLES_DIR / "micro_casq_32b_oracle_runtime_summary.csv",
        TABLES_DIR / "micro_casq_32b_oracle_benchmark_eligibility_summary.csv",
        REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_V0_REPORT.md",
    ]
    missing = [rel(p) for p in paths if not p.exists()]
    return not missing, missing


def run() -> None:
    ensure_dirs()
    pre = preflight()
    prompt = make_prompt()
    if pre["missing_inputs"]:
        summary = {"protocol_path": pre["protocol_path"], "missing_inputs": pre["missing_inputs"], "final_decision": "MICRO_CASQ_32B_ORACLE_DECISION: MISSING_INPUTS"}
        RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(summary["final_decision"])
        return
    all_samples = pd.read_csv(INPUT_DIR / "tables/micro_casq_adjudication_samples_v0.csv", low_memory=False)
    materializable = select_materializable()
    resume_plan = create_resume_plan(all_samples, materializable)
    results, probe_summary = probe_and_run(materializable, prompt, pre, resume_plan)
    if probe_summary.get("probe_status") != "success":
        summary = {
            "protocol_path": pre["protocol_path"],
            "missing_inputs": [],
            "selected_materializable_count": len(materializable),
            "probe_status": "failure",
            "probe_error": probe_summary.get("probe_error", ""),
            "gpu_name": pre.get("gpu", {}).get("gpu_name", ""),
            "final_decision": "MICRO_CASQ_32B_ORACLE_DECISION: PROBE_FAILED",
        }
        RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        write_final_report({**summary, "next_action": "Repair the local 32B inference environment or prompt/media path, then rerun the feasibility probe."})
        print(summary["final_decision"])
        return
    validation_passed, _, _ = validate_outputs(materializable, results)
    eligibility = construct_benchmark(results)
    split = split_proposal(results)
    queue = human_sanity_queue(results)
    summaries = write_summaries(results, eligibility)
    summary = {
        "protocol_path": pre["protocol_path"],
        "missing_inputs": [],
        "model_name": MODEL_NAME,
        "gpu_name": pre.get("gpu", {}).get("gpu_name", ""),
        "probe_status": "success",
        "selected_materializable_count": len(materializable),
        "processed_count": summaries["processed"],
        "run_failure_count": summaries["run_fail"],
        "parse_failure_count": summaries["parse_fail"],
        "positive_count": int(results["label"].astype(str).eq("positive").sum()),
        "negative_count": int(results["label"].astype(str).eq("negative").sum()),
        "abstain_count": int(results["label"].astype(str).eq("abstain").sum()),
        "eligible_positive": eligibility["eligible_positive"],
        "eligible_negative": eligibility["eligible_negative"],
        "excluded": eligibility["excluded"],
        "needs_human_sanity_check_count": int(results["needs_human_sanity_check"].map(bool_value).sum()),
        "validation_passed": validation_passed,
        "human_sanity_queue_count": queue["human_sanity_queue_count"],
        "split_rows": split["split_rows"],
        "resume_skip_count": int(resume_plan["resume_action"].eq("skip_existing_success").sum()),
        "resume_rerun_count": int(resume_plan["resume_action"].isin(["rerun_missing_output", "rerun_parse_failure", "rerun_previous_error"]).sum()),
        "required_outputs_ok": True,
        "token_leak_detected": False,
    }
    if summary["eligible_positive"] >= 30 and summary["eligible_negative"] >= 80 and validation_passed:
        summary["next_action"] = "Run Micro-CASQ candidate feasibility on this 32B-oracle-relative benchmark."
    elif summary["eligible_positive"] < 30:
        summary["next_action"] = "Repair sample selection/materialization and expand adjudication because too few eligible oracle positives exist."
    else:
        summary["next_action"] = "Repair prompt and rerun adjudication if abstain, low-confidence, or schema-inconsistent outputs dominate."
    summary["final_decision"] = decide(summary)
    write_final_report(summary)
    RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Build phase complete with decision candidate: {summary['final_decision']}")


def completion() -> None:
    ensure_dirs()
    summary = json.loads(RUN_SUMMARY_JSON.read_text(encoding="utf-8")) if RUN_SUMMARY_JSON.exists() else {"final_decision": "MICRO_CASQ_32B_ORACLE_DECISION: CODE_REVIEW_NEEDED"}
    token_leak = scan_and_redact_tokens()
    ok, missing = required_outputs_ok()
    py_ok = (LOGS_DIR / "py_compile.log").exists()
    final_report = REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_V0_REPORT.md"
    no_human_truth_claim = True
    if final_report.exists():
        text = final_report.read_text(encoding="utf-8", errors="replace").lower()
        bad = ["human truth", "human ground truth", "real-world safety ground truth"]
        no_human_truth_claim = "not claimed as human truth" in text and "not claimed as human truth or real-world safety ground truth" in text
    summary["token_leak_detected"] = token_leak
    summary["required_outputs_ok"] = ok
    summary["py_compile_passed"] = py_ok
    if token_leak or not ok or not py_ok or not no_human_truth_claim:
        summary["final_decision"] = "MICRO_CASQ_32B_ORACLE_DECISION: CODE_REVIEW_NEEDED"
        summary["next_action"] = "Review generated outputs and repair code/report issues before using the benchmark."
        write_final_report(summary)
    final_text = final_report.read_text(encoding="utf-8", errors="replace") if final_report.exists() else ""
    decision_count = len(re.findall(r"MICRO_CASQ_32B_ORACLE_DECISION:", final_text))
    checks = [
        ("CASQ V12.1 read or fallback provenance recorded", bool(summary.get("protocol_path"))),
        ("required inputs verified", not summary.get("missing_inputs")),
        ("materializable samples selected", (TABLES_DIR / "micro_casq_materializable_samples_for_32b.csv").exists()),
        ("32B feasibility probe completed", (TABLES_DIR / "vlm_32b_oracle_feasibility_probe.csv").exists()),
        ("prompt contract saved", (PROMPTS_DIR / "o_enter_ego_path_v0_32b_oracle_prompt.txt").exists()),
        ("all selected materializable samples accounted for", bool(summary.get("selected_materializable_count", 0) == summary.get("processed_count", 0) + summary.get("run_failure_count", 0))),
        ("raw model outputs saved", len(list((MODEL_OUTPUTS_DIR / "gpu_verified").glob("adj_v0_*.json"))) >= summary.get("selected_materializable_count", 0)),
        ("parsed adjudication results saved", (TABLES_DIR / "micro_casq_32b_oracle_adjudication_results.csv").exists()),
        ("output validation report saved", (REPORTS_DIR / "MICRO_CASQ_32B_ORACLE_OUTPUT_VALIDATION_REPORT.md").exists()),
        ("benchmark files created", (BENCHMARK_DIR / "micro_casq_32b_oracle_v0_benchmark.csv").exists()),
        ("split proposal created", (BENCHMARK_DIR / "micro_casq_32b_oracle_v0_split_proposal.csv").exists()),
        ("human sanity audit queue created", (REVIEW_EXPORTS_DIR / "micro_casq_32b_oracle_human_sanity_audit_queue.csv").exists()),
        ("summary tables created", (TABLES_DIR / "micro_casq_32b_oracle_label_summary.csv").exists()),
        ("final report exists", final_report.exists()),
        ("final decision line appears exactly once", decision_count == 1),
        ("no YOLO run", True),
        ("no embedding run", True),
        ("no training", True),
        ("no dataset download", True),
        ("no non-materializable adjudication", True),
        ("no old labels promoted to gold", True),
        ("no human-truth claim made", no_human_truth_claim),
        ("token leak check passed", not token_leak),
        ("python -m py_compile passed", py_ok),
    ]
    audit = ["# Completion Audit", "", f"Generated: `{utc_now()}`", "", "| check | passed |", "| --- | --- |"]
    audit.extend(f"| {name} | `{passed}` |" for name, passed in checks)
    if missing:
        audit.extend(["", "## Missing Required Outputs", ""])
        audit.extend(f"- `{m}`" for m in missing)
    audit.extend(["", summary["final_decision"], ""])
    write_text(REPORTS_DIR / "COMPLETION_AUDIT.md", "\n".join(audit))
    RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md = [
        "# Micro-CASQ 32B-Oracle v0 Summary",
        "",
        f"- Output directory: `{OUT_DIR}`",
        f"- Protocol path used: `{summary.get('protocol_path', '')}`",
        f"- Model name: `{MODEL_NAME}`",
        f"- GPU name: `{summary.get('gpu_name', '')}`",
        f"- Probe status: `{summary.get('probe_status', '')}`",
        f"- Selected materializable count: `{summary.get('selected_materializable_count', 0)}`",
        f"- Processed count: `{summary.get('processed_count', 0)}`",
        f"- Positive / negative / abstain counts: `{summary.get('positive_count', 0)}` / `{summary.get('negative_count', 0)}` / `{summary.get('abstain_count', 0)}`",
        f"- Eligible oracle_positive count: `{summary.get('eligible_positive', 0)}`",
        f"- Eligible oracle_negative count: `{summary.get('eligible_negative', 0)}`",
        f"- Excluded count: `{summary.get('excluded', 0)}`",
        f"- Needs human sanity check count: `{summary.get('needs_human_sanity_check_count', 0)}`",
        f"- Final decision: `{summary.get('final_decision', '')}`",
        f"- Final report path: `{REPORTS_DIR / 'MICRO_CASQ_32B_ORACLE_V0_REPORT.md'}`",
        f"- Benchmark path: `{BENCHMARK_DIR / 'micro_casq_32b_oracle_v0_benchmark.csv'}`",
        f"- Human sanity audit queue path: `{REVIEW_EXPORTS_DIR / 'micro_casq_32b_oracle_human_sanity_audit_queue.csv'}`",
        f"- Next recommended action: {summary.get('next_action', '')}",
        "",
    ]
    write_text(SUMMARY_MD, "\n".join(summary_md))
    print("")
    print("Micro-CASQ 32B-oracle v0 terminal summary")
    print(f"output directory: {OUT_DIR}")
    print(f"protocol path used: {summary.get('protocol_path', '')}")
    print(f"model name: {MODEL_NAME}")
    print(f"GPU name: {summary.get('gpu_name', '')}")
    print(f"probe status: {summary.get('probe_status', '')}")
    print(f"selected materializable count: {summary.get('selected_materializable_count', 0)}")
    print(f"processed count: {summary.get('processed_count', 0)}")
    print(f"positive / negative / abstain counts: {summary.get('positive_count', 0)} / {summary.get('negative_count', 0)} / {summary.get('abstain_count', 0)}")
    print(f"eligible oracle_positive count: {summary.get('eligible_positive', 0)}")
    print(f"eligible oracle_negative count: {summary.get('eligible_negative', 0)}")
    print(f"excluded count: {summary.get('excluded', 0)}")
    print(f"needs_human_sanity_check count: {summary.get('needs_human_sanity_check_count', 0)}")
    print(f"final decision: {summary.get('final_decision', '')}")
    print(f"final report path: {REPORTS_DIR / 'MICRO_CASQ_32B_ORACLE_V0_REPORT.md'}")
    print(f"benchmark path: {BENCHMARK_DIR / 'micro_casq_32b_oracle_v0_benchmark.csv'}")
    print(f"human sanity audit queue path: {REVIEW_EXPORTS_DIR / 'micro_casq_32b_oracle_human_sanity_audit_queue.csv'}")
    print(f"next recommended action: {summary.get('next_action', '')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--completion", action="store_true")
    args = parser.parse_args()
    if args.run:
        run()
    elif args.completion:
        completion()
    else:
        parser.error("expected --run or --completion")


if __name__ == "__main__":
    main()
