#!/usr/bin/env python3
"""Run a separately authorized Guangzhou exploratory physical comparison.

This is intentionally *not* the frozen Gate-O launcher.  It never modifies
the strict protocol or its authorization state, and stamps every artifact as
EXPLORATORY_DEVELOPMENT_PHYSICAL_RUN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from rc_sem.exploratory_gate_o import POLICIES, event_f1, event_groups, event_recall, right_continuous_auc, temporal_bisection_order

VIDEO = ROOT / "data/realcam/guangzhou.mp4"
VIDEO_SHA256 = "4cef5c884ac879fd00bcc7962707b5f0f5e6dec6ac97e5ec8d247561ce2ec1c6"
MODEL = ROOT / "models/Qwen3-VL-8B-Instruct"
PROMPT = ROOT / "configs/prompts/confirm_visual.yaml"
OUT_ROOT = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1"
DEADLINE_SECONDS = 300.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_label(raw: str) -> tuple[str, dict]:
    try:
        begin, end = raw.find("{"), raw.rfind("}")
        value = json.loads(raw[begin:end + 1]) if begin >= 0 and end >= begin else {}
        label = str(value.get("label", "abstain")).lower()
        return (label if label in {"positive", "negative", "abstain"} else "abstain"), value
    except (json.JSONDecodeError, TypeError):
        return "abstain", {"parse_error": True}


def unit_frames(unit_id: int, fps: float, *, sample_fps: float = 2.0) -> list[np.ndarray]:
    start, end = unit_id * 10.0, min((unit_id + 1) * 10.0, 4238.25)
    indices = [int(round(second * fps)) for second in np.arange(start, end, 1.0 / sample_fps)]
    cap = cv2.VideoCapture(str(VIDEO)); images: list[np.ndarray] = []
    current = -1
    for wanted in indices:
        if wanted <= current:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, wanted)
        ok, frame = cap.read(); current = wanted
        if not ok:
            break
        images.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    if not images:
        raise RuntimeError(f"cannot decode unit {unit_id}")
    return images


def frame_difference_score(unit_id: int, fps: float) -> tuple[float, dict]:
    """Existing deterministic OpenCV frame-difference proxy; no learned proxy."""
    frames = unit_frames(unit_id, fps, sample_fps=1.0)
    gray = [cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) for frame in frames]
    differences = [float(cv2.absdiff(left, right).mean() / 255.0) for left, right in zip(gray, gray[1:])]
    score = float(np.mean(differences)) if differences else 0.0
    return score, {"frame_count": len(frames), "mean_frame_difference": score, "max_frame_difference": float(max(differences, default=0.0))}


def gpu_snapshot() -> list[str]:
    command = ["nvidia-smi", "--query-gpu=index,name,uuid,memory.total,memory.used,driver_version", "--format=csv,noheader"]
    return subprocess.check_output(command, text=True).strip().splitlines()


class Oracle:
    def __init__(self, gpu_id: int):
        import torch
        import transformers
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self.torch, self.transformers, self.process_vision_info = torch, transformers, process_vision_info
        if not MODEL.is_dir():
            raise RuntimeError(f"missing exploratory 8B model: {MODEL}")
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            MODEL, dtype=torch.bfloat16, device_map="cuda:0", trust_remote_code=True, local_files_only=True
        )
        self.processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True, local_files_only=True)
        self.model.eval(); torch.cuda.synchronize()
        self.prompt = yaml.safe_load(PROMPT.read_text(encoding="utf-8"))["text"]
        self.gpu_id = gpu_id

    def verify(self, unit_id: int, fps: float) -> dict:
        from PIL import Image
        frames = unit_frames(unit_id, fps)
        started = time.perf_counter()
        images = [Image.fromarray(frame) for frame in frames]
        messages = [{"role": "user", "content": [{"type": "video", "video": images, "fps": 2.0}, {"type": "text", "text": self.prompt}]}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs, video_kwargs = self.process_vision_info(messages, return_video_kwargs=True, return_video_metadata=True)
        tensors = [item[0] for item in video_inputs]; metadata = [item[1] for item in video_inputs]
        inputs = self.processor(text=[text], images=image_inputs, videos=tensors, video_metadata=metadata, padding=True, return_tensors="pt", **video_kwargs).to(self.model.device)
        self.torch.cuda.synchronize(); inference_started = time.perf_counter()
        with self.torch.no_grad():
            generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=256)
        self.torch.cuda.synchronize()
        raw = self.processor.batch_decode([output[len(source):] for source, output in zip(inputs.input_ids, generated)], skip_special_tokens=True)[0]
        label, parsed = parse_label(raw)
        return {"unit_id": unit_id, "label": label, "parsed": parsed, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(), "frame_count": len(frames), "inference_seconds": time.perf_counter() - inference_started, "total_seconds": time.perf_counter() - started}


def build_manifest(run_id: str, gpu_id: int) -> dict:
    return {
        "schema_version": "EXPLORATORY_DEVELOPMENT_PHYSICAL_RUN_V1",
        "run_id": run_id, "created_utc": utc_now(), "protocol_class": "EXPLORATORY_DEVELOPMENT",
        "strict_gate_o_confirmatory": False, "execution_authorized_by_researcher": True,
        "known_deviations": [
            "Source B/C preservation not bound", "formal hardware reservation not frozen",
            "numeric deadline not derived from frozen Gate-O calibration", "exact frozen BF16 Qwen artifact unavailable",
            "existing Qwen3-VL-8B-Instruct used after 32B FP8 was infeasible on currently available GPUs",
            "exact YOLOv8n artifact unavailable; existing deterministic OpenCV frame-difference proxy used",
        ],
        "input": {"path": str(VIDEO), "sha256": VIDEO_SHA256, "duration_seconds": 4238.25},
        "oracle_runtime": {"path": str(MODEL), "model": "Qwen3-VL-8B-Instruct", "dtype": "bfloat16", "not_frozen_bf16_equivalent": True},
        "scan_runtime": {"implementation": "OpenCV frame-difference proxy", "learned_detector_used": False, "parameters": {"sample_fps": 1.0}},
        "hardware": {"hostname": socket.gethostname(), "gpu_ids": [gpu_id], "snapshot_before": gpu_snapshot()},
        "deadline_seconds": DEADLINE_SECONDS, "deadline_selection_basis": "pre-result fixed 300-second exploratory budget; approximately 30 prior 8B VERIFY calls", "deadline_frozen_before_results": True,
        "policies": list(POLICIES), "strict_gate_o_execution_authorized": False,
    }


def exhaustive_reference(oracle: Oracle, fps: float, unit_count: int, run_dir: Path, start: int, end: int) -> dict[int, str]:
    if not (0 <= start < end <= unit_count):
        raise ValueError("invalid reference shard")
    path = run_dir / ("reference_labels.json" if start == 0 and end == unit_count else f"reference_labels_{start}_{end}.json")
    labels = json.loads(path.read_text()) if path.exists() else {}
    for unit_id in range(start, end):
        if str(unit_id) in labels:
            continue
        result = oracle.verify(unit_id, fps)
        labels[str(unit_id)] = result
        atomic_json(path, labels)
    return {int(key): value["label"] for key, value in labels.items()}


def run_policy(policy: str, oracle: Oracle, fps: float, unit_count: int, run_dir: Path) -> dict:
    cells = [tuple(range(offset, min(offset + 10, unit_count))) for offset in range(0, unit_count, 10)]
    scan_order = tuple(range(len(cells))) if policy != POLICIES[1] else temporal_bisection_order(len(cells))
    scanned: set[int] = set(); scores: dict[int, float] = {}; labels: dict[int, str] = {}; trace: list[dict] = []
    started = time.perf_counter(); next_scan = 0
    while True:
        elapsed = time.perf_counter() - started
        if elapsed >= DEADLINE_SECONDS:
            break
        scan_available = next_scan < len(scan_order)
        verify_candidates = sorted(set(scores) - set(labels), key=lambda unit: (-scores[unit], unit))
        if policy == POLICIES[2]:
            action = "SCAN" if scan_available else ("VERIFY" if verify_candidates else "STOP")
        else:
            action = "SCAN" if (len(scanned) == len(labels) and scan_available) else ("VERIFY" if verify_candidates else ("SCAN" if scan_available else "STOP"))
        if action == "STOP":
            break
        timestamp = time.perf_counter() - started
        if action == "SCAN":
            cell_id = scan_order[next_scan]; next_scan += 1; detail = []
            for unit in cells[cell_id]:
                score, meta = frame_difference_score(unit, fps); scores[unit] = score; detail.append({"unit_id": unit, "score": score, **meta})
            scanned.add(cell_id); target = cell_id; outcome = {"exposed": detail}
        else:
            target = verify_candidates[0]; outcome = oracle.verify(target, fps); labels[target] = outcome["label"]
        positives = event_groups(unit for unit, label in labels.items() if label == "positive")
        trace.append({"timestamp_seconds": timestamp, "policy": policy, "action_type": action, "target": target, "legal_state": {"scanned_cells": sorted(scanned), "verifiable_units": verify_candidates}, "admission": "accepted_exploratory_deadline", "physical_cost_seconds": time.perf_counter() - started - timestamp, "outcome": outcome, "current_event_relation": [list(group) for group in positives]})
        atomic_json(run_dir / f"{policy}.trace.json", trace)
    positives = event_groups(unit for unit, label in labels.items() if label == "positive")
    return {"policy": policy, "deadline_seconds": DEADLINE_SECONDS, "wall_clock_seconds": time.perf_counter() - started, "scan_cells_completed": len(scanned), "scan_coverage_fraction": len(scanned) / len(cells), "verify_calls": len(labels), "verified_positive_units": sorted(unit for unit, label in labels.items() if label == "positive"), "distinct_confirmed_events": len(positives), "trace_path": str((run_dir / f"{policy}.trace.json").relative_to(ROOT))}


def evaluate_result(result: dict, reference: dict[int, str]) -> dict:
    trace = json.loads((ROOT / result["trace_path"]).read_text(encoding="utf-8"))
    reference_events = event_groups(unit for unit, label in reference.items() if label == "positive")
    recall_points, f1_points = [], []
    for row in trace:
        groups = tuple(tuple(group) for group in row["current_event_relation"])
        when = min(row["timestamp_seconds"] + row["physical_cost_seconds"], DEADLINE_SECONDS)
        recall_points.append((when, event_recall(groups, reference_events)))
        f1_points.append((when, event_f1(groups, reference_events)))
    final_groups = tuple(tuple(group) for group in trace[-1]["current_event_relation"]) if trace else ()
    return {**result, "event_recall_auc": right_continuous_auc(recall_points, DEADLINE_SECONDS), "event_recall_at_deadline": event_recall(final_groups, reference_events), "event_f1_auc": right_continuous_auc(f1_points, DEADLINE_SECONDS), "event_f1_at_deadline": event_f1(final_groups, reference_events), "reference_event_count": len(reference_events)}


def load_complete_reference(run_dir: Path, unit_count: int) -> dict[int, str]:
    merged: dict[int, dict] = {}
    for path in sorted(run_dir.glob("reference_labels*.json")):
        for key, value in json.loads(path.read_text(encoding="utf-8")).items():
            unit_id = int(key)
            if unit_id in merged and merged[unit_id]["raw_sha256"] != value["raw_sha256"]:
                raise RuntimeError(f"inconsistent duplicate evaluator label for unit {unit_id}")
            merged[unit_id] = value
    if set(merged) != set(range(unit_count)):
        raise RuntimeError(f"exploratory evaluator reference incomplete: {len(merged)}/{unit_count}")
    atomic_json(run_dir / "reference_labels.json", {str(key): merged[key] for key in sorted(merged)})
    return {key: value["label"] for key, value in merged.items()}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--mode", choices=("smoke", "reference", "policies", "all"), required=True); parser.add_argument("--gpu-id", type=int, required=True); parser.add_argument("--run-id", required=True); parser.add_argument("--reference-start", type=int, default=0); parser.add_argument("--reference-end", type=int)
    args = parser.parse_args()
    if sha256(VIDEO) != VIDEO_SHA256:
        raise RuntimeError("Guangzhou source hash mismatch")
    run_dir = OUT_ROOT / args.run_id
    if run_dir.exists() and args.mode == "all":
        raise RuntimeError("refusing to overwrite an exploratory run directory")
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "EXPLORATORY_MANIFEST.json"
    if not manifest_path.exists(): atomic_json(manifest_path, build_manifest(args.run_id, args.gpu_id))
    cap = cv2.VideoCapture(str(VIDEO)); fps = float(cap.get(cv2.CAP_PROP_FPS)); count = int(np.ceil(4238.25 / 10)); cap.release()
    oracle = Oracle(args.gpu_id)
    atomic_json(run_dir / "runtime_loaded.json", {"loaded_utc": utc_now(), "gpu_snapshot_after_load": gpu_snapshot(), "torch": oracle.torch.__version__, "transformers": oracle.transformers.__version__, "fps": fps, "unit_count": count})
    if args.mode == "smoke":
        print(json.dumps({"status": "MODEL_LOAD_PASS_NO_SOURCE_A_SEMANTIC_CALL", "run_dir": str(run_dir)})); return
    reference_end = count if args.reference_end is None else args.reference_end
    if args.mode == "all" and (args.reference_start != 0 or reference_end != count):
        raise RuntimeError("all mode requires the complete reference range")
    reference = exhaustive_reference(oracle, fps, count, run_dir, args.reference_start, reference_end) if args.mode in {"reference", "all"} else None
    if args.mode == "reference":
        print(json.dumps({"status": "EXPLORATORY_REFERENCE_COMPLETE", "unit_count": len(reference), "run_dir": str(run_dir)})); return
    results = [run_policy(policy, oracle, fps, count, run_dir) for policy in POLICIES]
    if reference is None:
        reference = load_complete_reference(run_dir, count)
    results = [evaluate_result(result, reference) for result in results]
    atomic_json(run_dir / "RESULTS.json", {"scientific_status": "EXPLORATORY_DEVELOPMENT_PHYSICAL_RESULT", "not_strict_confirmatory": True, "reference_oracle": "same exploratory 8B exhaustive evaluator-only pass", "results": results, "hardware_snapshot_after": gpu_snapshot()})
    print(json.dumps({"status": "EXPLORATORY_POLICIES_COMPLETE", "run_dir": str(run_dir), "results": results}, indent=2))


if __name__ == "__main__":
    main()
