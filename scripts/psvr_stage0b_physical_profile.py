#!/usr/bin/env python3
"""Single-video physical profiler for the PSVR partial-proxy gate."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
PROXY_MODEL = REPO / "models/yolo/yolov8n.pt"
ORACLE_MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT = BENCH / "oracle/oracle_prompt.txt"
DEFAULT_OUT = REPO / "outputs/psvr_stage0b_physical_profile"


def ns() -> int:
    return time.perf_counter_ns()


def elapsed_s(start: int) -> float:
    return (ns() - start) / 1e9


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), p))


def summarize(rows: list[dict]) -> pd.DataFrame:
    out = []
    df = pd.DataFrame(rows)
    for (operator, phase), group in df.groupby(["operator", "phase"], sort=True):
        v = group.duration_seconds.astype(float).to_numpy()
        out.append({
            "operator": operator, "phase": phase, "n": len(v),
            "p50_seconds": np.percentile(v, 50), "p90_seconds": np.percentile(v, 90),
            "p95_seconds": np.percentile(v, 95), "mean_seconds": np.mean(v),
            "std_seconds": np.std(v), "min_seconds": np.min(v), "max_seconds": np.max(v),
            "failures": int((group.status != "ok").sum()),
        })
    return pd.DataFrame(out)


def add(rows: list[dict], operator: str, phase: str, duration: float, iteration: int,
        invocation: str = "none", status: str = "ok", **extra) -> None:
    rows.append({"operator": operator, "phase": phase, "duration_seconds": duration,
                 "iteration": iteration, "invocation_type": invocation, "status": status, **extra})


def video_info() -> tuple[float, int, float]:
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        raise RuntimeError("video open failed")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps
    cap.release()
    return fps, frames, duration


def yolo_batch(model, frames: list[np.ndarray], torch, batch_size: int, rows: list[dict], phase: str, batch_idx: int):
    start = ns()
    # Match the frozen producer: pass original decoded frames to Ultralytics;
    # its own letterbox preprocessing performs the model resize.
    prepared = frames
    add(rows, "proxy_preprocessing", phase, elapsed_s(start), batch_idx, batch_size=len(frames))
    start = ns()
    results = model(prepared, device="cuda", verbose=False, batch=batch_size)
    torch.cuda.synchronize()
    add(rows, "proxy_inference", phase, elapsed_s(start), batch_idx, invocation="physical_proxy", batch_size=len(frames))
    start = ns()
    scores = []
    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            scores.append(0.0)
        else:
            classes = boxes.cls.detach().cpu().numpy()
            scores.append(float(np.isin(classes, [2, 3, 5, 7]).sum()))
    add(rows, "proxy_postprocessing", phase, elapsed_s(start), batch_idx, batch_size=len(frames))
    return scores


def run_grid_proxy(model, torch, seconds: list[float], batch_size: int, rows: list[dict], phase: str) -> tuple[float, list[float]]:
    total_start = ns()
    open_start = ns(); cap = cv2.VideoCapture(str(VIDEO)); add(rows, "video_open", phase, elapsed_s(open_start), 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS)); all_scores = []
    frames: list[np.ndarray] = []
    for i, second in enumerate(seconds):
        start = ns(); cap.set(cv2.CAP_PROP_POS_FRAMES, int(second * fps)); ok, frame = cap.read()
        add(rows, "decode_seek", phase, elapsed_s(start), i, status="ok" if ok else "failed", timestamp_seconds=second)
        if not ok:
            continue
        frames.append(frame)
        if len(frames) == batch_size or i == len(seconds) - 1:
            all_scores.extend(yolo_batch(model, frames, torch, batch_size, rows, phase, len(all_scores) // batch_size))
            frames = []
    cap.release()
    return elapsed_s(total_start), all_scores


def run_full_proxy(model, torch, fps: float, frame_count: int, duration: float,
                   batch_size: int, rows: list[dict]) -> tuple[float, list[float]]:
    """Physical full pass: sequential 2-FPS motion plus 5-second YOLO grid."""
    total_start = ns(); phase = "warm_full"
    start = ns(); cap = cv2.VideoCapture(str(VIDEO)); add(rows, "video_open", phase, elapsed_s(start), 0)
    motion_interval = max(1, int(round(fps / 2.0)))
    target_frames = {min(frame_count - 1, int((2.5 + 5.0 * i) * fps)) for i in range(int(math.ceil(duration / 5.0)))}
    gray_prev = None; motion: list[float] = []; batch: list[np.ndarray] = []; scores: list[float] = []
    chunk_start = ns(); chunk_reads = 0; batch_idx = 0
    for frame_idx in range(frame_count):
        ok, frame = cap.read()
        if not ok:
            break
        chunk_reads += 1
        if frame_idx % motion_interval == 0:
            start = ns(); gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (320, 180))
            motion.append(0.0 if gray_prev is None else float(np.mean(cv2.absdiff(gray, gray_prev))))
            gray_prev = gray
            add(rows, "motion_preprocessing", phase, elapsed_s(start), len(motion) - 1)
        if frame_idx in target_frames:
            batch.append(frame.copy())
            if len(batch) == batch_size:
                scores.extend(yolo_batch(model, batch, torch, batch_size, rows, phase, batch_idx)); batch_idx += 1; batch = []
        if chunk_reads == 3000:
            add(rows, "sequential_decode", phase, elapsed_s(chunk_start), len(rows), decoded_frames=chunk_reads)
            chunk_start = ns(); chunk_reads = 0
    if chunk_reads:
        add(rows, "sequential_decode", phase, elapsed_s(chunk_start), len(rows), decoded_frames=chunk_reads)
    if batch:
        scores.extend(yolo_batch(model, batch, torch, batch_size, rows, phase, batch_idx))
    cap.release()
    start = ns()
    _ = np.asarray(scores) + np.interp(np.arange(len(scores)), np.linspace(0, len(scores) - 1, len(motion)), np.asarray(motion))[:len(scores)]
    add(rows, "proxy_postprocessing_full_aggregation", phase, elapsed_s(start), 0)
    return elapsed_s(total_start), scores


def parse_response(raw: str) -> tuple[dict, str]:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match: return {}, "no_json"
        value = json.loads(match.group(0))
        if str(value.get("label", "")).lower() not in {"positive", "negative", "abstain"}: return value, "invalid_label"
        if str(value.get("confidence", "")).lower() not in {"high", "medium", "low"}: return value, "invalid_confidence"
        return value, "ok"
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"


def extract_oracle_frames(start_s: float, end_s: float, fps: float):
    begin = ns(); cap = cv2.VideoCapture(str(VIDEO)); cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * fps))
    interval = max(1, int(fps / 2.0)); frames = []
    for idx in range(int(start_s * fps), int(end_s * fps) + 1):
        ok, frame = cap.read()
        if not ok: break
        if (idx - int(start_s * fps)) % interval == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames, elapsed_s(begin)


def materialization_profiles(rows: list[dict], out: Path) -> None:
    import importlib.util, sys
    lib_path = BENCH / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("stage0b_benchmark_lib", lib_path); assert spec and spec.loader
    lib = importlib.util.module_from_spec(spec); sys.modules[spec.name] = lib; spec.loader.exec_module(lib)
    units = pd.read_csv(BENCH / "frozen_inputs/units.csv")
    oracle = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv")
    trace = oracle[["unit_id", "parsed_label"]].rename(columns={"parsed_label": "oracle_label_after_query"})
    last_events = None
    for i in range(35):
        prefix = trace.iloc[:max(1, int(len(trace) * (i + 1) / 35))]
        start = ns(); events = lib.materialize_from_trace(prefix, units, {
            "benchmark_id": "stage0b", "run_id": f"k3_{i}", "method": "profile", "method_variant": "k3",
            "seed": 0, "horizon_budget": len(prefix)}, "k3_bridge_safe", {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0})
        add(rows, "K3_replay", "warm", elapsed_s(start), i)
        start = ns()
        boundary = [{"event_id": str(r.event_id), "core_start": float(r.core_start_time), "core_end": float(r.core_end_time),
                     "left_state": "censored", "right_state": "censored"} for _, r in events.iterrows()]
        add(rows, "boundary_refinement", "warm", elapsed_s(start), i)
        if i >= 5:
            payload = {"iteration": i, "confirmed_events": events.to_dict("records"), "boundary_state": boundary}
            temp = out / "snapshots" / f"snapshot_{i:03d}.json.tmp"; final = temp.with_suffix("")
            start = ns()
            with temp.open("w") as fh:
                json.dump(payload, fh, sort_keys=True, default=str); fh.flush(); os.fsync(fh.fileno())
            os.replace(temp, final)
            add(rows, "snapshot_serialization_commit", "warm", elapsed_s(start), i)
        last_events = events
    assert last_events is not None


def oracle_profiles(rows: list[dict], out: Path, fps: float, calls: int) -> dict:
    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    start = ns()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        ORACLE_MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(ORACLE_MODEL, trust_remote_code=True); model.eval()
    add(rows, "oracle_model_initialization", "cold", elapsed_s(start), 0, invocation="physical_oracle")
    obs = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv")
    positives = obs.loc[obs.parsed_label.eq("positive"), "unit_id"].astype(int).tolist()
    negatives = obs.loc[obs.parsed_label.eq("negative"), "unit_id"].astype(int).tolist()
    chosen = []
    for a, b in zip(positives, negatives[::max(1, len(negatives)//max(1, calls//2))]):
        chosen.extend([a, b])
        if len(chosen) >= calls: break
    chosen = chosen[:calls]
    prompt = PROMPT.read_text()
    raw_dir = out / "physical_oracle_raw"; raw_dir.mkdir()
    call_results = []
    for i, uid in enumerate(chosen):
        row = obs.set_index("unit_id").loc[uid]
        total = ns(); queue_start = ns(); add(rows, "oracle_queue", "warm", elapsed_s(queue_start), i, invocation="physical_oracle")
        frames, extract_time = extract_oracle_frames(float(row.start_time), float(row.end_time), fps)
        add(rows, "oracle_clip_extraction", "warm", extract_time, i, invocation="physical_oracle", frames=len(frames))
        start = ns()
        messages = [{"role": "user", "content": [{"type": "video", "video": [Image.fromarray(x) for x in frames], "fps": 2}, {"type": "text", "text": prompt}]}]
        prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[prompt_text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
        add(rows, "oracle_preprocessing", "warm", elapsed_s(start), i, invocation="physical_oracle")
        start = ns()
        with torch.no_grad(): generated = model.generate(**inputs, do_sample=False, max_new_tokens=256)
        torch.cuda.synchronize(); inference_time = elapsed_s(start)
        add(rows, "oracle_inference", "warm", inference_time, i, invocation="physical_oracle")
        start = ns(); trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated)]
        raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        add(rows, "oracle_postprocessing", "warm", elapsed_s(start), i, invocation="physical_oracle")
        start = ns(); parsed, parse_status = parse_response(raw); add(rows, "oracle_parsing", "warm", elapsed_s(start), i, invocation="physical_oracle", status="ok" if parse_status == "ok" else "failed")
        total_time = elapsed_s(total); add(rows, "VERIFY", "warm", total_time, i, invocation="physical_oracle", status="ok" if parse_status == "ok" else "failed")
        record = {"unit_id": uid, "physical_oracle_invocation": True, "cache_replay": False, "logical_oracle_call": True,
                  "latency_seconds": total_time, "inference_seconds": inference_time, "parse_status": parse_status,
                  "parsed": parsed, "raw": raw, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest()}
        (raw_dir / f"unit_{uid:04d}.json").write_text(json.dumps(record, indent=2) + "\n")
        call_results.append({k: v for k, v in record.items() if k not in {"raw", "parsed"}})
        del inputs, generated, frames; gc.collect(); torch.cuda.empty_cache()
    del model, processor; gc.collect(); torch.cuda.empty_cache()
    pd.DataFrame(call_results).to_csv(out / "physical_oracle_calls.csv", index=False)
    return {"calls": len(call_results), "units": chosen, "parse_successes": sum(x["parse_status"] == "ok" for x in call_results)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--oracle-calls", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--epsilon-seconds", type=float, default=1.0)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False); (out / "snapshots").mkdir()
    rows: list[dict] = []
    fps, frame_count, duration = video_info()
    import torch
    from ultralytics import YOLO
    start = ns(); proxy = YOLO(str(PROXY_MODEL)); add(rows, "proxy_model_initialization", "cold", elapsed_s(start), 0, invocation="physical_proxy")
    coarse_seconds = [min(duration - 1/fps, 15.0 + 30.0*i) for i in range(int(math.ceil(duration/30.0)))]
    for i in range(3):
        _, _ = run_grid_proxy(proxy, torch, coarse_seconds[:args.batch_size], args.batch_size, rows, "warmup")
    coarse_total, coarse_scores = run_grid_proxy(proxy, torch, coarse_seconds, args.batch_size, rows, "warm_coarse")
    add(rows, "coarse_scan", "warm", coarse_total, 0, invocation="physical_proxy", coverage_fraction=1.0, temporal_stride_seconds=30.0)
    full_total, full_scores = run_full_proxy(proxy, torch, fps, frame_count, duration, args.batch_size, rows)
    add(rows, "full_proxy", "warm", full_total, 0, invocation="physical_proxy", coverage_fraction=1.0, temporal_stride_seconds=5.0)
    del proxy; gc.collect(); torch.cuda.empty_cache()
    materialization_profiles(rows, out)
    oracle_info = oracle_profiles(rows, out, fps, args.oracle_calls)
    pd.DataFrame(rows).to_csv(out / "operator_observations.csv", index=False)
    summary = summarize(rows); summary.to_csv(out / "operator_latency_summary.csv", index=False)
    lookup = summary.set_index(["operator", "phase"])
    k3 = float(lookup.loc[("K3_replay", "warm"), "p95_seconds"])
    snapshot = float(lookup.loc[("snapshot_serialization_commit", "warm"), "p95_seconds"])
    verify = float(lookup.loc[("VERIFY", "warm"), "p95_seconds"])
    c_commit = k3 + snapshot + args.epsilon_seconds
    proxy_init = float(lookup.loc[("proxy_model_initialization", "cold"), "p95_seconds"])
    oracle_init = float(lookup.loc[("oracle_model_initialization", "cold"), "p95_seconds"])
    warm_t_min = coarse_total + verify + c_commit
    warm_t_max = full_total
    warm_width = warm_t_max - warm_t_min
    # v3 section 6.1 explicitly counts model initialization in the cold workload.
    # Proxy initialization appears on both sides; oracle initialization is needed
    # only before the first physical VERIFY and is therefore decision-critical.
    t_min = proxy_init + coarse_total + oracle_init + verify + c_commit
    t_max = proxy_init + full_total
    width = t_max - t_min; normalized = width / t_max
    noise_floor = max(1.0, 0.05 * full_total)
    if width <= 0: decision = "NO_GO"
    elif width <= noise_floor or oracle_info["calls"] < 10 or oracle_info["parse_successes"] < oracle_info["calls"]: decision = "WEAK"
    else: decision = "WEAK"  # single-video pilot cannot establish robust GO
    gate = {
        "PARTIAL_PROXY_REGIME": decision, "pilot_scope": "single_video_single_query_single_hardware",
        "coarse_definition": "uniform global 30-second grid; YOLOv8n midpoint frames", "full_proxy_definition": "5-second grid YOLOv8n plus sequential 2-FPS motion decode",
        "batch_size": args.batch_size, "warmups": 3, "physical_oracle_calls": oracle_info["calls"], "cache_replay_calls": 0,
        "logical_oracle_calls": oracle_info["calls"], "C_p95_K3": k3, "C_p95_snapshot": snapshot,
        "epsilon": args.epsilon_seconds, "C_commit": c_commit, "C_p95_VERIFY": verify,
        "C_p95_proxy_initialization_cold": proxy_init, "C_p95_oracle_initialization_cold": oracle_init,
        "C_p95_coarse_warm": coarse_total, "C_p50_full_proxy_warm": warm_t_max,
        "warm_conditional_T_min": warm_t_min, "warm_conditional_T_max": warm_t_max,
        "warm_conditional_interval_width": warm_width, "warm_conditional_normalized_interval_width": warm_width / warm_t_max,
        "C_p95_coarse": proxy_init + coarse_total, "C_p50_full_proxy": t_max, "T_min": t_min, "T_max": t_max,
        "interval_width": width, "normalized_interval_width": normalized, "measurement_noise_floor_seconds": noise_floor,
        "coarse_global_coverage": True, "video_duration_seconds": duration, "coarse_samples": len(coarse_scores), "full_samples": len(full_scores),
        "oracle": oracle_info,
    }
    (out / "partial_proxy_gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    env = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True, capture_output=True).stdout.strip()
    (out / "environment.json").write_text(json.dumps({"gpu": env, "torch": torch.__version__, "torch_cuda": torch.version.cuda,
        "video": str(VIDEO), "proxy_checkpoint": str(PROXY_MODEL), "oracle_checkpoint": str(ORACLE_MODEL), "perf_clock": "time.perf_counter_ns"}, indent=2) + "\n")
    report = f"""# PSVR Stage 0B — Single-Video Physical Regime Pilot

`PARTIAL_PROXY_REGIME = {decision}`

- Physical coarse scan: {coarse_total:.3f} s warm operator time, uniform global coverage at 30 s stride.
- Physical full proxy: {full_total:.3f} s warm operator time, 5 s YOLO grid plus 2 FPS motion decode.
- Cold initialization: proxy {proxy_init:.3f} s; oracle {oracle_init:.3f} s.
- Physical VERIFY p95: {verify:.3f} s from {oracle_info['calls']} Qwen3-VL-32B calls; cache replay calls: 0.
- C_commit: {c_commit:.3f} s (K3 p95 {k3:.6f} + snapshot p95 {snapshot:.6f} + epsilon {args.epsilon_seconds:.3f}).
- Strict-cold T_min: {t_min:.3f} s; strict-cold T_max: {t_max:.3f} s.
- Interval width: {width:.3f} s; normalized width: {normalized:.4f}.
- Warm-oracle conditional interval: [{warm_t_min:.3f}, {warm_t_max:.3f}] s, width {warm_width:.3f} s.

The primary gate is strict cold because v3 explicitly includes model initialization. The warm-oracle interval is reported only as a competing regime, not used to rescue the cold gate. A positive strict-cold interval would still be classified at most WEAK in this single-video pilot.
"""
    (out / "FINAL_REPORT.md").write_text(report)
    print(json.dumps(gate, indent=2))


if __name__ == "__main__":
    main()
