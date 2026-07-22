#!/usr/bin/env python3
"""Re-freeze PSVR physical workload regimes with required replication."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
OUT = REPO / "outputs/psvr_stage0b_physical_profile"
RAW = OUT / "raw"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
PROXY_MODEL = REPO / "models/yolo/yolov8n.pt"
ORACLE_MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT = BENCH / "oracle/oracle_prompt.txt"
BATCH_SIZE = 4
SAFETY_MARGIN_SECONDS = 1.0


def now_ns() -> int:
    return time.perf_counter_ns()


def seconds(start: int) -> float:
    return (now_ns() - start) / 1e9


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as fh:
        json.dump(value, fh, indent=2, default=str); fh.flush(); os.fsync(fh.fileno())
    os.replace(temp, path)


def gpu_state() -> str:
    return subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"],
        text=True, capture_output=True,
    ).stdout.strip()


def load_profiler_module():
    path = REPO / "scripts/psvr_stage0b_physical_profile.py"
    spec = importlib.util.spec_from_file_location("stage0b_replicated_profiler", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def proxy_phase(repetitions: int) -> None:
    import torch
    from ultralytics import YOLO

    p = load_profiler_module(); RAW.mkdir(parents=True, exist_ok=True)
    fps, frame_count, duration = p.video_info()
    coarse_seconds = [min(duration - 1 / fps, 15.0 + 30.0 * i) for i in range(int(math.ceil(duration / 30.0)))]
    init_samples = []
    for i in range(10):
        start = now_ns(); temporary = YOLO(str(PROXY_MODEL)); elapsed = seconds(start)
        init_samples.append({"iteration": i, "duration_seconds": elapsed, "process_id": os.getpid()})
        del temporary; gc.collect(); torch.cuda.empty_cache()
    pd.DataFrame(init_samples).to_csv(RAW / "proxy_initialization_observations.csv", index=False)

    model = YOLO(str(PROXY_MODEL)); warmup_rows = []
    for i in range(3):
        elapsed, scores = p.run_grid_proxy(model, torch, coarse_seconds, BATCH_SIZE, warmup_rows, "coarse_warmup")
        atomic_json(RAW / f"coarse_warmup_{i:02d}.json", {"iteration": i, "duration_seconds": elapsed, "samples": len(scores)})

    coarse_records = []
    for i in range(repetitions):
        detail = []; before = gpu_state(); start = now_ns()
        elapsed, scores = p.run_grid_proxy(model, torch, coarse_seconds, BATCH_SIZE, detail, "coarse_valid")
        wall = seconds(start)
        record = {"iteration": i, "duration_seconds": elapsed, "outer_wall_seconds": wall,
                  "samples": len(scores), "coverage_fraction": 1.0, "stride_seconds": 30.0,
                  "batch_size": BATCH_SIZE, "gpu_before": before, "gpu_after": gpu_state(), "status": "ok"}
        coarse_records.append(record); atomic_json(RAW / f"coarse_valid_{i:02d}.json", {"summary": record, "operators": detail})
        pd.DataFrame(coarse_records).to_csv(RAW / "coarse_scan_observations.csv", index=False)
        print(json.dumps({"phase": "coarse", **record}), flush=True)

    # One complete producer-faithful warm-up, excluded from valid replication.
    detail = []; elapsed, scores = p.run_full_proxy(model, torch, fps, frame_count, duration, BATCH_SIZE, detail)
    atomic_json(RAW / "full_proxy_warmup.json", {"duration_seconds": elapsed, "samples": len(scores), "operators": detail})
    print(json.dumps({"phase": "full_warmup", "duration_seconds": elapsed}), flush=True)

    full_records = []
    for i in range(repetitions):
        detail = []; before = gpu_state(); start = now_ns()
        elapsed, scores = p.run_full_proxy(model, torch, fps, frame_count, duration, BATCH_SIZE, detail)
        wall = seconds(start)
        record = {"iteration": i, "duration_seconds": elapsed, "outer_wall_seconds": wall,
                  "samples": len(scores), "coverage_fraction": 1.0, "stride_seconds": 5.0,
                  "motion_fps": 2.0, "batch_size": BATCH_SIZE, "gpu_before": before,
                  "gpu_after": gpu_state(), "status": "ok"}
        full_records.append(record); atomic_json(RAW / f"full_proxy_valid_{i:02d}.json", {"summary": record, "operators": detail})
        pd.DataFrame(full_records).to_csv(RAW / "full_proxy_observations.csv", index=False)
        print(json.dumps({"phase": "full", **record}), flush=True)
    del model; gc.collect(); torch.cuda.empty_cache()


def resident_proxy_phase(repetitions: int) -> None:
    """Measure Regime B proxy operators with the physical oracle resident."""
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from ultralytics import YOLO

    p = load_profiler_module(); RAW.mkdir(parents=True, exist_ok=True)
    fps, frame_count, duration = p.video_info()
    grid = [min(duration - 1 / fps, 15.0 + 30.0 * i) for i in range(int(math.ceil(duration / 30.0)))]
    start = now_ns()
    oracle_model = Qwen3VLForConditionalGeneration.from_pretrained(
        ORACLE_MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    oracle_processor = AutoProcessor.from_pretrained(ORACLE_MODEL, trust_remote_code=True); oracle_model.eval()
    atomic_json(RAW / "regime_b_resident_oracle_context.json", {
        "oracle_initialization_seconds": seconds(start), "oracle_checkpoint": str(ORACLE_MODEL),
        "resident_during_all_measurements": True, "gpu_state": gpu_state()})
    proxy_model = YOLO(str(PROXY_MODEL))
    for i in range(3):
        duration_s, scores = p.run_grid_proxy(proxy_model, torch, grid, BATCH_SIZE, [], "regime_b_coarse_warmup")
        atomic_json(RAW / f"regime_b_coarse_warmup_{i:02d}.json", {"duration_seconds": duration_s, "samples": len(scores)})
    coarse_rows = []
    for i in range(repetitions):
        detail = []; duration_s, scores = p.run_grid_proxy(proxy_model, torch, grid, BATCH_SIZE, detail, "regime_b_coarse_valid")
        row = {"iteration": i, "duration_seconds": duration_s, "samples": len(scores), "batch_size": BATCH_SIZE,
               "oracle_resident": True, "status": "ok"}
        coarse_rows.append(row); atomic_json(RAW / f"regime_b_coarse_valid_{i:02d}.json", {"summary": row, "operators": detail})
        pd.DataFrame(coarse_rows).to_csv(RAW / "regime_b_coarse_scan_observations.csv", index=False)
        print(json.dumps({"phase": "regime_b_coarse", **row}), flush=True)
    for i in range(3):
        detail = []; duration_s, scores = p.run_full_proxy(proxy_model, torch, fps, frame_count, duration, BATCH_SIZE, detail)
        atomic_json(RAW / f"regime_b_full_warmup_{i:02d}.json", {"duration_seconds": duration_s, "samples": len(scores), "operators": detail})
        print(json.dumps({"phase": "regime_b_full_warmup", "iteration": i, "duration_seconds": duration_s}), flush=True)
    full_rows = []
    for i in range(repetitions):
        detail = []; duration_s, scores = p.run_full_proxy(proxy_model, torch, fps, frame_count, duration, BATCH_SIZE, detail)
        row = {"iteration": i, "duration_seconds": duration_s, "samples": len(scores), "batch_size": BATCH_SIZE,
               "oracle_resident": True, "status": "ok"}
        full_rows.append(row); atomic_json(RAW / f"regime_b_full_valid_{i:02d}.json", {"summary": row, "operators": detail})
        pd.DataFrame(full_rows).to_csv(RAW / "regime_b_full_proxy_observations.csv", index=False)
        print(json.dumps({"phase": "regime_b_full", **row}), flush=True)
    del proxy_model, oracle_model, oracle_processor
    gc.collect(); torch.cuda.empty_cache()


def parse_response(raw: str) -> tuple[dict, str]:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match: return {}, "no_json"
        parsed = json.loads(match.group(0))
        if str(parsed.get("label", "")).lower() not in {"positive", "negative", "abstain"}: return parsed, "invalid_label"
        if str(parsed.get("confidence", "")).lower() not in {"high", "medium", "low"}: return parsed, "invalid_confidence"
        return parsed, "ok"
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"


def extract_frames(start_s: float, end_s: float, fps: float):
    start = now_ns(); cap = cv2.VideoCapture(str(VIDEO)); cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * fps))
    interval = max(1, int(fps / 2.0)); frames = []
    for idx in range(int(start_s * fps), int(end_s * fps) + 1):
        ok, frame = cap.read()
        if not ok: break
        if (idx - int(start_s * fps)) % interval == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release(); return frames, seconds(start)


def physical_verify(model, processor, torch, process_vision_info, unit: dict, prompt: str, iteration: str) -> tuple[dict, str]:
    from PIL import Image

    total = now_ns(); frames, extraction = extract_frames(float(unit["start_time"]), float(unit["end_time"]), float(unit["video_fps"]))
    start = now_ns()
    messages = [{"role": "user", "content": [
        {"type": "video", "video": [Image.fromarray(frame) for frame in frames], "fps": 2},
        {"type": "text", "text": prompt},
    ]}]
    prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[prompt_text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
    preprocessing = seconds(start); start = now_ns()
    with torch.no_grad():
        generated = model.generate(**inputs, do_sample=False, max_new_tokens=256)
    torch.cuda.synchronize(); inference = seconds(start); start = now_ns()
    trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated)]
    raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
    postprocessing = seconds(start); start = now_ns(); parsed, parse_status = parse_response(raw); parsing = seconds(start)
    record = {
        "iteration": iteration, "unit_id": int(unit["unit_id"]), "duration_seconds": seconds(total),
        "clip_extraction_seconds": extraction, "preprocessing_seconds": preprocessing,
        "inference_seconds": inference, "postprocessing_seconds": postprocessing,
        "parsing_seconds": parsing, "parse_status": parse_status,
        "physical_oracle_invocation": True, "cache_replay": False, "logical_oracle_call": True,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(), "parsed": parsed,
    }
    del inputs, generated, frames; gc.collect(); torch.cuda.empty_cache()
    return record, raw


def oracle_process_worker(process_index: int, unit_ids: list[int], warmup_ids: list[int], result_path: str) -> None:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    obs = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv").set_index("unit_id")
    cap = cv2.VideoCapture(str(VIDEO)); fps = float(cap.get(cv2.CAP_PROP_FPS)); cap.release()
    prompt = PROMPT.read_text(); before = gpu_state(); start = now_ns()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        ORACLE_MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(ORACLE_MODEL, trust_remote_code=True); model.eval()
    initialization = seconds(start)
    warmups = []
    for j, uid in enumerate(warmup_ids):
        unit = obs.loc[uid].to_dict(); unit.update({"unit_id": uid, "video_fps": fps})
        record, _ = physical_verify(model, processor, torch, process_vision_info, unit, prompt, f"p{process_index}_warmup{j}")
        warmups.append(record)
    observations = []; raw_dir = Path(result_path).parent / "oracle_raw"; raw_dir.mkdir(parents=True, exist_ok=True)
    for j, uid in enumerate(unit_ids):
        unit = obs.loc[uid].to_dict(); unit.update({"unit_id": uid, "video_fps": fps})
        record, raw = physical_verify(model, processor, torch, process_vision_info, unit, prompt, f"p{process_index}_valid{j}")
        observations.append(record)
        atomic_json(raw_dir / f"process_{process_index:02d}_unit_{uid:04d}.json", {**record, "raw": raw})
        print(json.dumps({"phase": "verify", "process": process_index, "unit": uid, "seconds": record["duration_seconds"]}), flush=True)
    value = {"process_index": process_index, "pid": os.getpid(), "gpu_before": before,
             "initialization_seconds": initialization, "warmups": warmups,
             "valid_observations": observations, "gpu_after": gpu_state(), "status": "ok"}
    atomic_json(Path(result_path), value)


def oracle_phase(processes: int, calls_per_process: int) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    obs = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv")
    positives = obs.loc[obs.parsed_label.eq("positive"), "unit_id"].astype(int).tolist()
    negatives = obs.loc[obs.parsed_label.eq("negative"), "unit_id"].astype(int).tolist()
    chosen = []
    for i in range(processes * calls_per_process):
        source = positives if i % 2 == 0 else negatives
        chosen.append(source[(i // 2) * max(1, len(source) // (processes * calls_per_process // 2)) % len(source)])
    # Ensure no duplicate logical units across valid calls.
    seen = set(); chosen = [uid for uid in chosen if not (uid in seen or seen.add(uid))]
    remaining = [int(x) for x in obs.unit_id if int(x) not in seen]
    chosen.extend(remaining[:processes * calls_per_process - len(chosen)])
    ctx = mp.get_context("spawn")
    for process_index in range(processes):
        result_path = RAW / f"oracle_process_{process_index:02d}.json"
        if result_path.exists():
            print(json.dumps({"phase": "oracle_process", "process": process_index, "status": "existing"}), flush=True); continue
        ids = chosen[process_index * calls_per_process:(process_index + 1) * calls_per_process]
        warmup_ids = [1, 2, 3] if process_index == 0 else []
        process = ctx.Process(target=oracle_process_worker, args=(process_index, ids, warmup_ids, str(result_path)))
        process.start(); process.join()
        if process.exitcode != 0:
            raise RuntimeError(f"oracle process {process_index} failed: exit={process.exitcode}")
        print(json.dumps({"phase": "oracle_process", "process": process_index, "status": "complete"}), flush=True)
    initialization_rows = []; verify_rows = []; warmup_rows = []
    for path in sorted(RAW.glob("oracle_process_*.json")):
        value = json.loads(path.read_text())
        initialization_rows.append({"process_index": value["process_index"], "pid": value["pid"],
                                    "duration_seconds": value["initialization_seconds"], "status": value["status"]})
        verify_rows.extend(value["valid_observations"]); warmup_rows.extend(value["warmups"])
    pd.DataFrame(initialization_rows).to_csv(RAW / "oracle_initialization_observations.csv", index=False)
    pd.DataFrame(verify_rows).to_csv(RAW / "physical_verify_observations.csv", index=False)
    pd.DataFrame(warmup_rows).to_csv(RAW / "physical_verify_warmups.csv", index=False)


def k3_snapshot_phase(repetitions: int = 50) -> None:
    p = load_profiler_module(); rows = []; snapshot_dir = RAW / "commit_snapshots"; snapshot_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the unchanged frozen K3 adapter and record paired K3+snapshot cost.
    import importlib.util
    path = BENCH / "scripts/benchmark_lib.py"; spec = importlib.util.spec_from_file_location("regime_benchmark_lib", path)
    assert spec and spec.loader
    lib = importlib.util.module_from_spec(spec); sys.modules[spec.name] = lib; spec.loader.exec_module(lib)
    units = pd.read_csv(BENCH / "frozen_inputs/units.csv"); oracle = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv")
    trace = oracle[["unit_id", "parsed_label"]].rename(columns={"parsed_label": "oracle_label_after_query"})
    for i in range(repetitions):
        prefix = trace.iloc[:max(1, int(len(trace) * (i + 1) / repetitions))]
        total = now_ns(); start = now_ns()
        events = lib.materialize_from_trace(prefix, units, {"benchmark_id": "regime", "run_id": f"commit_{i}",
            "method": "profile", "method_variant": "unchanged_k3", "seed": 0, "horizon_budget": len(prefix)},
            "k3_bridge_safe", {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0})
        k3_time = seconds(start); start = now_ns(); target = snapshot_dir / f"snapshot_{i:03d}.json"; temp = target.with_suffix(".tmp")
        with temp.open("w") as fh:
            json.dump({"confirmed_events": events.to_dict("records")}, fh, sort_keys=True, default=str); fh.flush(); os.fsync(fh.fileno())
        os.replace(temp, target); snapshot_time = seconds(start)
        rows.append({"iteration": i, "k3_seconds": k3_time, "snapshot_seconds": snapshot_time,
                     "k3_snapshot_seconds": seconds(total), "events": len(events), "status": "ok"})
    pd.DataFrame(rows).to_csv(RAW / "k3_snapshot_observations.csv", index=False)


def single_physical_commit(verification_record: dict) -> dict:
    """Run exactly one unchanged K3 materialization and durable snapshot commit."""
    path = BENCH / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("parallel_benchmark_lib", path)
    assert spec and spec.loader
    lib = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = lib
    spec.loader.exec_module(lib)
    units = pd.read_csv(BENCH / "frozen_inputs/units.csv")
    parsed = verification_record.get("parsed", {})
    trace = pd.DataFrame([{
        "unit_id": int(verification_record["unit_id"]),
        "oracle_label_after_query": str(parsed.get("label", "abstain")).lower(),
    }])
    total = now_ns()
    start = now_ns()
    events = lib.materialize_from_trace(
        trace,
        units,
        {"benchmark_id": "regime", "run_id": "parallel_cold_commit", "method": "profile",
         "method_variant": "unchanged_k3", "seed": 0, "horizon_budget": 1},
        "k3_bridge_safe",
        {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
    )
    k3_seconds = seconds(start)
    start = now_ns()
    target = RAW / "cold_parallel_committed_snapshot.json"
    temporary = target.with_suffix(".tmp")
    with temporary.open("w") as fh:
        json.dump({"confirmed_events": events.to_dict("records")}, fh, sort_keys=True, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, target)
    snapshot_seconds = seconds(start)
    return {"event": "commit_complete", "k3_seconds": k3_seconds,
            "snapshot_seconds": snapshot_seconds, "duration_seconds": seconds(total),
            "confirmed_events": len(events)}


def parallel_oracle_worker(command, sender, unit_id: int) -> None:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    obs = pd.read_csv(BENCH / "frozen_inputs/oracle_observations.csv").set_index("unit_id")
    cap = cv2.VideoCapture(str(VIDEO)); fps = float(cap.get(cv2.CAP_PROP_FPS)); cap.release(); start = now_ns()
    try:
        model = Qwen3VLForConditionalGeneration.from_pretrained(ORACLE_MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
        processor = AutoProcessor.from_pretrained(ORACLE_MODEL, trust_remote_code=True); model.eval(); init_time = seconds(start)
        sender.send({"event": "oracle_ready", "initialization_seconds": init_time, "pid": os.getpid()})
        if command.recv() != "verify": raise RuntimeError("parallel command protocol")
        unit = obs.loc[unit_id].to_dict(); unit.update({"unit_id": unit_id, "video_fps": fps})
        record, raw = physical_verify(model, processor, torch, process_vision_info, unit, PROMPT.read_text(), "parallel_valid")
        sender.send({"event": "verify_complete", "record": record, "raw": raw})
        command.recv()
    except Exception as exc:
        sender.send({"event": "failure", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        sender.close(); command.close()


def parallel_proxy_worker(result_path: str) -> None:
    try:
        import torch
        from ultralytics import YOLO
        p = load_profiler_module(); fps, _, duration = p.video_info()
        points = [min(duration - 1/fps, 15.0 + 30.0*i) for i in range(int(math.ceil(duration/30.0)))]
        start = now_ns(); model = YOLO(str(PROXY_MODEL)); init_time = seconds(start); detail = []
        elapsed, scores = p.run_grid_proxy(model, torch, points, BATCH_SIZE, detail, "parallel_coarse")
        atomic_json(Path(result_path), {"event": "coarse_complete", "proxy_initialization_seconds": init_time,
                    "coarse_seconds": elapsed, "samples": len(scores), "pid": os.getpid(), "operators": detail})
    except Exception as exc:
        atomic_json(Path(result_path), {"event": "failure", "error": f"{type(exc).__name__}: {exc}", "pid": os.getpid()})


def parallel_phase() -> None:
    result_path = RAW / "cold_parallel_end_to_end_trace.json"
    if result_path.exists():
        print(json.dumps({"phase": "parallel", "status": "existing"})); return
    ctx = mp.get_context("spawn")
    main_command, oracle_command = ctx.Pipe(duplex=True); main_oracle, oracle_sender = ctx.Pipe(duplex=False)
    proxy_child_result = RAW / "cold_parallel_proxy_child.json"
    proxy_child_result.unlink(missing_ok=True)
    oracle = ctx.Process(target=parallel_oracle_worker, args=(oracle_command, oracle_sender, 50))
    proxy = ctx.Process(target=parallel_proxy_worker, args=(str(proxy_child_result),))
    start = now_ns(); oracle.start(); proxy.start(); oracle_command.close(); oracle_sender.close()
    events = []; oracle_ready = coarse_ready = False
    while not (oracle_ready and coarse_ready):
        if main_oracle.poll(0.1):
            try:
                event = main_oracle.recv()
            except EOFError:
                event = {"event": "failure", "error": "oracle child pipe EOF"}
            event["elapsed_from_start_seconds"] = seconds(start); events.append(event)
            if event["event"] == "failure": break
            oracle_ready = event["event"] == "oracle_ready" or oracle_ready
        if not coarse_ready and proxy_child_result.exists():
            event = json.loads(proxy_child_result.read_text()); event["elapsed_from_start_seconds"] = seconds(start); events.append(event)
            if event["event"] == "failure": break
            coarse_ready = event["event"] == "coarse_complete"
        if not coarse_ready and not proxy.is_alive() and not proxy_child_result.exists():
            events.append({"event": "failure", "error": f"proxy child exited {proxy.exitcode} without result",
                           "elapsed_from_start_seconds": seconds(start)}); break
    status = "ok"
    if oracle_ready and coarse_ready:
        main_command.send("verify"); event = main_oracle.recv(); event["elapsed_from_start_seconds"] = seconds(start); events.append(event)
        if event["event"] == "verify_complete":
            # Exactly one real K3 and fsync snapshot after the physical verification.
            commit_event = single_physical_commit(event["record"])
            commit_event["elapsed_from_start_seconds"] = seconds(start)
            events.append(commit_event)
            end_to_end = seconds(start)
        else:
            status = "failed"; end_to_end = seconds(start)
        main_command.send("shutdown")
    else:
        status = "failed"; end_to_end = seconds(start)
    oracle.join(timeout=30); proxy.join(timeout=30)
    if oracle.is_alive(): oracle.terminate(); oracle.join()
    if proxy.is_alive(): proxy.terminate(); proxy.join()
    value = {"status": status, "same_gpu_true_parallel": True, "events": events,
             "end_to_end_seconds": end_to_end, "oracle_exitcode": oracle.exitcode, "proxy_exitcode": proxy.exitcode}
    atomic_json(result_path, value); print(json.dumps({"phase": "parallel", **value}, default=str), flush=True)


def stats(values: pd.Series) -> dict:
    array = values.astype(float).to_numpy()
    return {"n": len(array), "p50_seconds": float(np.percentile(array, 50)), "p90_seconds": float(np.percentile(array, 90)),
            "p95_seconds": float(np.percentile(array, 95)), "mean_seconds": float(np.mean(array)),
            "std_seconds": float(np.std(array)), "min_seconds": float(np.min(array)), "max_seconds": float(np.max(array))}


def finalize_phase() -> None:
    standalone_coarse = pd.read_csv(RAW / "coarse_scan_observations.csv")
    standalone_full = pd.read_csv(RAW / "full_proxy_observations.csv")
    coarse = pd.read_csv(RAW / "regime_b_coarse_scan_observations.csv")
    full = pd.read_csv(RAW / "regime_b_full_proxy_observations.csv")
    oracle_init = pd.read_csv(RAW / "oracle_initialization_observations.csv"); verify = pd.read_csv(RAW / "physical_verify_observations.csv")
    proxy_init = pd.read_csv(RAW / "proxy_initialization_observations.csv"); commit = pd.read_csv(RAW / "k3_snapshot_observations.csv")
    rows = []
    for operator, frame, column in [
        ("coarse_scan_regime_B_oracle_resident", coarse, "duration_seconds"),
        ("full_proxy_regime_B_oracle_resident", full, "duration_seconds"),
        ("coarse_scan_proxy_only_diagnostic", standalone_coarse, "duration_seconds"),
        ("full_proxy_proxy_only_diagnostic", standalone_full, "duration_seconds"),
        ("oracle_initialization", oracle_init, "duration_seconds"), ("proxy_initialization", proxy_init, "duration_seconds"),
        ("physical_verify", verify, "duration_seconds"), ("K3", commit, "k3_seconds"),
        ("snapshot", commit, "snapshot_seconds"), ("K3_snapshot", commit, "k3_snapshot_seconds")]:
        rows.append({"operator": operator, **stats(frame[column])})
    summary = pd.DataFrame(rows); summary.to_csv(OUT / "operator_latency_summary.csv", index=False)
    by = summary.set_index("operator")
    enough = {"coarse": len(coarse) >= 10, "full": len(full) >= 10, "oracle_init": len(oracle_init) >= 5,
              "verify": len(verify) >= 20, "commit": len(commit) >= 30}
    c95 = float(by.loc["coarse_scan_regime_B_oracle_resident", "p95_seconds"])
    f50 = float(by.loc["full_proxy_regime_B_oracle_resident", "p50_seconds"])
    standalone_f50 = float(by.loc["full_proxy_proxy_only_diagnostic", "p50_seconds"])
    v95 = float(by.loc["physical_verify", "p95_seconds"]); commit95 = float(by.loc["K3_snapshot", "p95_seconds"])
    init95 = float(by.loc["oracle_initialization", "p95_seconds"]); pinit95 = float(by.loc["proxy_initialization", "p95_seconds"])
    pinit50 = float(by.loc["proxy_initialization", "p50_seconds"])
    tmin_b = c95 + v95 + commit95 + SAFETY_MARGIN_SECONDS; tmax_b = f50; width_b = tmax_b - tmin_b
    tmin_a = init95 + pinit95 + c95 + v95 + commit95 + SAFETY_MARGIN_SECONDS
    tmax_a = pinit50 + standalone_f50; width_a = tmax_a - tmin_a
    if not all(enough.values()):
        b_decision = a_decision = "INSUFFICIENT_REPLICATION"
    else:
        b_decision = "NO_GO" if width_b <= 0 else ("WEAK" if width_b <= max(5.0, 0.10 * f50) else "GO")
        a_decision = "NO_GO" if width_a <= 0 else ("WEAK" if width_a <= max(5.0, 0.10 * tmax_a) else "GO")
    parallel_path = RAW / "cold_parallel_end_to_end_trace.json"
    parallel = json.loads(parallel_path.read_text()) if parallel_path.exists() else {"status": "not_run"}
    parallel_event_times = {
        event.get("event", f"event_{index}"): event.get("elapsed_from_start_seconds")
        for index, event in enumerate(parallel.get("events", []))
    }
    parallel_summary = {
        "status": parallel.get("status", "not_run"),
        "same_gpu_true_parallel": parallel.get("same_gpu_true_parallel", False),
        "end_to_end_seconds": parallel.get("end_to_end_seconds"),
        "event_elapsed_seconds": parallel_event_times,
        "oracle_exitcode": parallel.get("oracle_exitcode"),
        "proxy_exitcode": parallel.get("proxy_exitcode"),
        "raw_trace": str(parallel_path.relative_to(REPO)),
    }
    warm_proxy_load = []
    proxy_file = BENCH / "frozen_inputs/public_proxy.csv"
    for _ in range(30):
        start = now_ns(); table = pd.read_csv(proxy_file); warm_proxy_load.append(seconds(start)); del table
    regime_c_lookup = stats(pd.Series(warm_proxy_load))
    regimes = [
        {"regime": "A_cold_process_cold_proxy_serial", "oracle_resident": False, "proxy_materialized": False,
         "T_min_seconds": tmin_a, "T_max_seconds": tmax_a, "interval_width_seconds": width_a,
         "normalized_interval_width": width_a / tmax_a, "decision": a_decision},
        {"regime": "A_cold_process_cold_proxy_parallel_observed", "oracle_resident": False, "proxy_materialized": False,
         "T_min_seconds": parallel.get("end_to_end_seconds", np.nan), "T_max_seconds": tmax_a,
         "interval_width_seconds": tmax_a - float(parallel.get("end_to_end_seconds", np.nan)),
         "normalized_interval_width": (tmax_a - float(parallel.get("end_to_end_seconds", np.nan))) / tmax_a,
         "decision": "OBSERVED_ONLY" if parallel.get("status") == "ok" else "NOT_AVAILABLE"},
        {"regime": "B_warm_oracle_cold_proxy", "oracle_resident": True, "proxy_materialized": False,
         "T_min_seconds": tmin_b, "T_max_seconds": tmax_b, "interval_width_seconds": width_b,
         "normalized_interval_width": width_b / tmax_b, "decision": b_decision},
        {"regime": "C_warm_oracle_warm_proxy", "oracle_resident": True, "proxy_materialized": True,
         "T_min_seconds": regime_c_lookup["p95_seconds"] + v95 + commit95 + SAFETY_MARGIN_SECONDS,
         "T_max_seconds": np.nan, "interval_width_seconds": np.nan, "normalized_interval_width": np.nan,
         "decision": "NOT_A_PARTIAL_PROXY_GATE"},
    ]
    pd.DataFrame(regimes).to_csv(OUT / "workload_regime_summary.csv", index=False)
    gate = {
        "COLD_PROCESS_COLD_PROXY_REGIME": a_decision,
        "WARM_ORACLE_COLD_PROXY_REGIME": b_decision,
        "replication_requirements_met": enough,
        "regime_B": {"coarse_p95": c95, "physical_verify_p95": v95, "k3_snapshot_p95": commit95,
                     "safety_margin": SAFETY_MARGIN_SECONDS, "T_min_B": tmin_b, "full_proxy_p50": f50,
                     "T_max_B": tmax_b, "interval_width_B": width_b, "normalized_interval_width_B": width_b / tmax_b},
        "regime_A_serial": {"oracle_initialization_p95": init95, "proxy_initialization_p95": pinit95,
                            "T_min_A": tmin_a, "T_max_A": tmax_a, "interval_width_A": width_a,
                            "normalized_interval_width_A": width_a / tmax_a},
        "regime_A_parallel_physical_trace": parallel_summary,
        "regime_C_proxy_cache_load": regime_c_lookup,
        "physical_verify_calls": len(verify), "cache_replay_calls_in_latency": 0,
        "video": str(VIDEO), "proxy_checkpoint": str(PROXY_MODEL), "oracle_checkpoint": str(ORACLE_MODEL),
        "batch_size": BATCH_SIZE, "hardware": "NVIDIA A800-SXM4-80GB",
        "regime_B_proxy_measurement_context": "physical Qwen3-VL-32B resident on same GPU",
    }
    atomic_json(OUT / "partial_proxy_gate.json", gate)
    report = f"""# PSVR Stage 0B — Re-frozen Physical Workload Regimes

`COLD_PROCESS_COLD_PROXY_REGIME = {a_decision}`

`WARM_ORACLE_COLD_PROXY_REGIME = {b_decision}`

## Replication

- coarse scan: n={len(coarse)}
- full proxy: n={len(full)}
- independent oracle cold initialization processes: n={len(oracle_init)}
- valid physical VERIFY: n={len(verify)}; cache replay used for latency: 0
- paired K3 + snapshot: n={len(commit)}

## Regime B — warm oracle, cold/unmaterialized proxy

Coarse and full-proxy repetitions in this gate were measured with the physical Qwen3-VL-32B checkpoint resident on the same GPU.

- T_min_B = {tmin_b:.3f} s
- T_max_B = {tmax_b:.3f} s
- interval_width_B = {width_b:.3f} s
- normalized_interval_width_B = {width_b/f50:.4f}

## Regime A — cold process, cold/unmaterialized proxy

- Serial T_min_A = {tmin_a:.3f} s
- T_max_A = {tmax_a:.3f} s
- serial interval width = {width_a:.3f} s
- true same-A800 parallel trace status = {parallel.get('status')}; end-to-end = {parallel.get('end_to_end_seconds', 'NA')} s

Regime C is reported separately as oracle-resident and proxy-materialized; it is not used to support a partial-proxy claim. All latency observations are physical; frozen response replay is excluded.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    print(json.dumps(gate, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=["proxy", "resident_proxy", "oracle", "commit", "parallel", "finalize", "all"])
    parser.add_argument("--repetitions", type=int, default=10); args = parser.parse_args(); RAW.mkdir(parents=True, exist_ok=True)
    phases = ["proxy", "resident_proxy", "oracle", "commit", "parallel", "finalize"] if args.phase == "all" else [args.phase]
    for phase in phases:
        if phase == "proxy": proxy_phase(args.repetitions)
        elif phase == "resident_proxy": resident_proxy_phase(args.repetitions)
        elif phase == "oracle": oracle_phase(5, 4)
        elif phase == "commit": k3_snapshot_phase(50)
        elif phase == "parallel": parallel_phase()
        elif phase == "finalize": finalize_phase()


if __name__ == "__main__":
    main()
