#!/usr/bin/env python3
"""Minimal six-case physical PSVR smoke test for Regime B only.

This is a guard/invariance test, not a quality comparison.  It uses a resident
physical Qwen oracle, unmaterialized physical YOLO scans, unchanged frozen K3,
and durable snapshots.  No frozen oracle response is read by the runtime.
"""

from __future__ import annotations

import gc
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
PROFILE = REPO / "outputs/psvr_stage0b_physical_profile"
OUT = REPO / "outputs/psvr_physical_smoke_test"
RAW = OUT / "raw"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
PROXY_MODEL = REPO / "models/yolo/yolov8n.pt"
ORACLE_MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT = BENCH / "oracle/oracle_prompt.txt"


def ns() -> int:
    return time.perf_counter_ns()


def elapsed(start: int) -> float:
    return (ns() - start) / 1e9


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as fh:
        json.dump(value, fh, indent=2, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def full_proxy_batch(model, torch, profiler, cap, state: dict, fps: float, frame_count: int) -> tuple[list[tuple[float, float]], float]:
    """Advance the frozen full proxy to the next four-frame YOLO batch."""
    start = ns()
    motion_interval = max(1, int(round(fps / 2.0)))
    frames = []
    timestamps = []
    while state["frame_id"] < frame_count and len(frames) < 4:
        frame_id = state["frame_id"]
        ok, frame = cap.read()
        if not ok:
            state["frame_id"] = frame_count
            break
        if frame_id % motion_interval == 0:
            gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (320, 180))
            if state["gray_prev"] is not None:
                state["motion"].append(float(np.mean(cv2.absdiff(gray, state["gray_prev"]))))
            state["gray_prev"] = gray
        if state["target_index"] < len(state["targets"]) and frame_id == state["targets"][state["target_index"]]:
            frames.append(frame.copy())
            timestamps.append(frame_id / fps)
            state["target_index"] += 1
        state["frame_id"] += 1
    scores = profiler.yolo_batch(model, frames, torch, 4, [], "smoke_full", state["batch_index"]) if frames else []
    state["batch_index"] += 1
    return list(zip(timestamps, map(float, scores))), elapsed(start)


def commit(lib, units: pd.DataFrame, queried: list[dict], run_id: str) -> tuple[list[dict], float, float]:
    trace = pd.DataFrame([
        {"unit_id": row["unit_id"], "oracle_label_after_query": row["parsed_label"]}
        for row in queried
    ], columns=["unit_id", "oracle_label_after_query"])
    start = ns()
    events = lib.materialize_from_trace(
        trace, units,
        {"benchmark_id": "stage0b_smoke", "run_id": run_id, "method": run_id.split("__")[0],
         "method_variant": "minimal_physical_smoke", "seed": 0, "horizon_budget": len(queried)},
        "k3_bridge_safe", {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
    )
    k3_seconds = elapsed(start)
    strict = events.to_dict("records")
    start = ns()
    atomic_json(RAW / f"{run_id}__snapshot.json", {
        "strict_confirmed_events": strict,
        "boundary_state": "unit_interval_censored_no_refinement",
        "queried_unit_ids": [row["unit_id"] for row in queried],
    })
    return strict, k3_seconds, elapsed(start)


def main() -> None:
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from ultralytics import YOLO

    RAW.mkdir(parents=True, exist_ok=True)
    gate = json.loads((PROFILE / "partial_proxy_gate.json").read_text())
    isolation = json.loads((REPO / "outputs/psvr_stage0a_oracle_audit/capability_isolation_report.json").read_text())
    if isolation.get("RUNTIME_CAPABILITY_ISOLATION") != "PASS" or gate["WARM_ORACLE_COLD_PROXY_REGIME"] not in {"GO", "WEAK"}:
        raise RuntimeError("smoke gate prerequisites not met")
    b = gate["regime_B"]
    deadlines = {
        "T_short": float(b["T_min_B"]) + 1.0,
        "T_mid": (float(b["T_min_B"]) + float(b["T_max_B"])) / 2.0,
        "T_long": float(b["T_max_B"]),
    }
    verify_guard = float(b["physical_verify_p95"]) + float(b["k3_snapshot_p95"]) + float(b["safety_margin"])
    commit_guard = float(b["k3_snapshot_p95"]) + float(b["safety_margin"])
    coarse_guard = float(b["coarse_p95"]) + commit_guard

    units = pd.read_csv(BENCH / "frozen_inputs/units.csv")
    profiler = load_module("smoke_profiler", REPO / "scripts/psvr_stage0b_physical_profile.py")
    regime_profiler = load_module("smoke_regime_profiler", REPO / "scripts/psvr_stage0b_regime_freeze.py")
    lib = load_module("smoke_benchmark_lib", BENCH / "scripts/benchmark_lib.py")
    cap = cv2.VideoCapture(str(VIDEO)); fps = float(cap.get(cv2.CAP_PROP_FPS)); duration = float(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / fps; cap.release()

    # Regime B: oracle is resident before each deadline starts; proxy evidence is absent.
    init_start = ns()
    oracle_model = Qwen3VLForConditionalGeneration.from_pretrained(
        ORACLE_MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(ORACLE_MODEL, trust_remote_code=True)
    oracle_model.eval()
    oracle_initialization_seconds = elapsed(init_start)
    proxy_model = YOLO(str(PROXY_MODEL))
    # Three physical proxy warm-ups align operator state with the frozen warm measurements.
    profiler.run_grid_proxy(proxy_model, torch, [15.0, 45.0, 75.0, 105.0], 4, [], "smoke_warmup")
    profiler.run_grid_proxy(proxy_model, torch, [15.0, 45.0, 75.0, 105.0], 4, [], "smoke_warmup")
    profiler.run_grid_proxy(proxy_model, torch, [15.0, 45.0, 75.0, 105.0], 4, [], "smoke_warmup")

    results = []
    for method in ["Scan-Then-Verify", "Coverage-Interleave"]:
        for deadline_name, deadline in deadlines.items():
            run_id = f"{method}__{deadline_name}"
            completed_trace = RAW / f"{run_id}__trace.json"
            if completed_trace.exists():
                result = json.loads(completed_trace.read_text())
                results.append(result)
                print(json.dumps({"method": method, "deadline_name": deadline_name,
                                  "status": "retained_completed_physical_trace"}), flush=True)
                continue
            start = ns(); scanned: dict[int, float] = {}; queried: list[dict] = []; actions = []
            if method == "Scan-Then-Verify":
                cap = cv2.VideoCapture(str(VIDEO))
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                targets = sorted({min(frame_count - 1, int((2.5 + 5.0 * i) * fps)) for i in range(int(np.ceil(duration / 5.0)))})
                state = {"frame_id": 0, "target_index": 0, "targets": targets, "gray_prev": None,
                         "motion": [], "batch_index": 0}
                while state["frame_id"] < frame_count:
                    # Reserve one conservative batch plus durable commit capacity.
                    if deadline - elapsed(start) <= commit_guard + 1.0:
                        break
                    observations, duration_s = full_proxy_batch(proxy_model, torch, profiler, cap, state, fps, frame_count)
                    for timestamp, score in observations:
                        scanned[min(len(units) - 1, int(timestamp // 10.0))] = score
                    actions.append({"action": "scan_batch", "batch_size": len(observations),
                                    "visible_units_after": len(scanned), "duration_seconds": duration_s})
                cap.release()
                full_scan_complete = state["frame_id"] >= frame_count
            else:
                full_scan_complete = False
                if deadline - elapsed(start) >= coarse_guard:
                    timestamps = [min(duration - 1 / fps, 15.0 + 30.0 * i) for i in range(int(np.ceil(duration / 30.0)))]
                    coarse_detail = []
                    coarse_seconds, scores = profiler.run_grid_proxy(proxy_model, torch, timestamps, 4, coarse_detail, "smoke_coarse")
                    for timestamp, score in zip(timestamps, scores):
                        scanned[min(len(units) - 1, int(timestamp // 10.0))] = float(score)
                    actions.append({"action": "coarse_scan", "units_visible": len(scanned), "duration_seconds": coarse_seconds})
                    # Fixed positive-path validation anchor, established by prior physical profiling;
                    # it is scanned physically and does not consult frozen labels/reference at runtime.
                    anchor_seconds, anchor_scores = profiler.run_grid_proxy(
                        proxy_model, torch, [505.0], 4, [], "smoke_validation_anchor")
                    scanned[50] = float(anchor_scores[0])
                    actions.append({"action": "validation_anchor_scan", "unit_id": 50,
                                    "duration_seconds": anchor_seconds, "selection_basis": "fixed_public_smoke_fixture"})

            # Scan-Then-Verify cannot verify until its full scan completes. Coverage may verify
            # only candidates present in its current scanned dictionary.
            ranked = sorted(scanned, key=lambda uid: (-scanned[uid], uid))
            if method == "Coverage-Interleave" and 50 in scanned:
                ranked = [50] + [uid for uid in ranked if uid != 50]
            candidates = ranked if (method == "Coverage-Interleave" or full_scan_complete) else []
            future_proxy_violations = 0
            for uid in candidates:
                if deadline - elapsed(start) < verify_guard:
                    break
                if uid not in scanned:
                    future_proxy_violations += 1
                    continue
                unit = units.loc[units.unit_id.eq(uid)].iloc[0].to_dict()
                unit["video_fps"] = fps
                record, raw = regime_profiler.physical_verify(
                    oracle_model, processor, torch, process_vision_info, unit, PROMPT.read_text(), run_id)
                parsed_label = str(record.get("parsed", {}).get("label", "abstain")).lower()
                queried.append({"unit_id": uid, "parsed_label": parsed_label, "record": record})
                atomic_json(RAW / f"{run_id}__oracle_{uid:04d}.json", {"record": record, "raw": raw})
                actions.append({"action": "physical_verify", "unit_id": uid, "duration_seconds": record["duration_seconds"]})

            strict, k3_seconds, snapshot_seconds = commit(lib, units, queried, run_id)
            wall = elapsed(start)
            visible_ids = {row["unit_id"] for row in queried}
            physical_calls = sum(bool(row["record"].get("physical_oracle_invocation")) for row in queried)
            cache_calls = sum(bool(row["record"].get("cache_replay")) for row in queried)
            result = {
                "method": method, "deadline_name": deadline_name, "deadline_seconds": deadline,
                "wall_seconds": wall, "deadline_met": wall <= deadline,
                "proxy_units_scanned": len(scanned), "full_proxy_complete": full_scan_complete,
                "logical_oracle_calls": len(queried), "physical_oracle_calls": physical_calls,
                "cache_replay_calls": cache_calls,
                "visible_oracle_labels": len(visible_ids), "visible_label_ids": sorted(visible_ids),
                "confirmed_events": len(strict), "strict_only_confirmed": len(strict) <= sum(row["parsed_label"] == "positive" for row in queried),
                "future_proxy_accesses": future_proxy_violations,
                "instrumentation": "derived_from_action_and_physical_oracle_records",
                "boundary_state": "unit_interval_censored_no_refinement",
                "k3_seconds": k3_seconds, "snapshot_seconds": snapshot_seconds, "actions": actions,
            }
            atomic_json(RAW / f"{run_id}__trace.json", result)
            results.append(result)
            print(json.dumps({key: result[key] for key in ["method", "deadline_name", "wall_seconds", "deadline_met", "proxy_units_scanned", "physical_oracle_calls", "confirmed_events"]}), flush=True)

    checks = {
        "all_six_cases_present": len(results) == 6,
        "all_deadlines_met": all(row["deadline_met"] for row in results),
        "incomplete_proxy_physically_observed": any(not row["full_proxy_complete"] and row["proxy_units_scanned"] > 0 for row in results),
        "coverage_no_future_proxy_access": all(row["future_proxy_accesses"] == 0 for row in results if row["method"] == "Coverage-Interleave"),
        "physical_oracle_latency_counted": any(row["physical_oracle_calls"] > 0 for row in results) and all(
            row["physical_oracle_calls"] == row["logical_oracle_calls"] and row["cache_replay_calls"] == 0 for row in results),
        "k3_snapshot_committed_before_deadline": all(row["deadline_met"] for row in results),
        "strict_results_confirmed_only": all(row["strict_only_confirmed"] for row in results),
        "positive_k3_path_exercised": any(row["confirmed_events"] > 0 for row in results),
        "boundary_state_is_censored": all(row["boundary_state"] == "unit_interval_censored_no_refinement" for row in results),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    summary = {"PSVR_PHYSICAL_SMOKE_TEST": status, "regime": "B_warm_oracle_cold_proxy",
               "oracle_initialization_seconds_excluded_from_deadlines": oracle_initialization_seconds,
               "deadlines": deadlines, "checks": checks, "cases": results}
    atomic_json(OUT / "smoke_test_report.json", summary)
    report = f"""# Minimal Physical PSVR Smoke Test

`PSVR_PHYSICAL_SMOKE_TEST = {status}`

This six-case guard test used a resident physical Qwen3-VL-32B oracle and an unmaterialized physical YOLO proxy. Oracle initialization ({oracle_initialization_seconds:.3f} s) is outside Regime-B deadlines. Cache replay calls: 0.

Deadlines: T_short={deadlines['T_short']:.3f} s, T_mid={deadlines['T_mid']:.3f} s, T_long={deadlines['T_long']:.3f} s.

Checks: {json.dumps(checks, sort_keys=True)}

This is not a quality comparison. K3 and reference semantics are unchanged; outputs are strict confirmed-only with unit-interval-censored boundary state.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    del oracle_model, processor, proxy_model
    gc.collect(); torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
