#!/usr/bin/env python3
"""Run the frozen H002 2-FPS YOLO preview only on selected regions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time

import numpy as np
import pandas as pd
import psutil
import torch
from ultralytics import YOLO

from run_mfrp_previews import p1_frame_features


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"
EXPERIMENT = OUT / "preview_experiments/YGS-H002"
MODEL_PATH = ROOT / "models/yolo/yolov8n.pt"
RATE, WIDTH, HEIGHT = 2.0, 320, 180
TARGET_CLASSES = [0, 1, 2, 3, 5, 7]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20): digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["video_id", "region_index"]).copy()
    numeric = ordered.select_dtypes(include=[np.number]).columns
    ordered[numeric] = ordered[numeric].round(8)
    return hashlib.sha256(ordered.to_csv(index=False, float_format="%.8g").encode()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def aggregate(samples: pd.DataFrame, region: pd.Series) -> dict:
    row = {
        "video_id": region.video_id, "region_id": region.region_id,
        "region_index": int(region.region_index), "start_sec": float(region.start_sec),
        "end_sec": float(region.end_sec), "actual_duration_sec": float(region.actual_duration_sec),
        "q2__selected": 1.0, "q2__preview_sample_count": int(len(samples)),
        "q2__valid_sample_fraction": min(1.0, len(samples) / max(1, int(np.ceil(region.actual_duration_sec * RATE)))),
        "q2__preview_missingness_fraction": float(len(samples) == 0),
    }
    excluded = {"sample_index", "timestamp_sec"}
    for column in (value for value in samples.columns if value not in excluded):
        values = samples[column].to_numpy(float)
        prefix = f"q2__detector__{column}"
        if not len(values):
            stats = [0.0] * 6
        else:
            top = np.sort(values)[-min(3, len(values)):]
            slope = float(np.polyfit(np.arange(len(values)), values, 1)[0]) if len(values) >= 2 else 0.0
            stats = [float(values.mean()), float(values.max()), float(values.std()),
                     float(np.quantile(values, 0.90)), float(top.mean()), slope]
        for name, value in zip(("mean", "max", "std", "q90", "top3mean", "slope"), stats):
            row[f"{prefix}__{name}"] = value
    return row


def run_once(run_index: int) -> dict:
    selection = pd.read_csv(EXPERIMENT / "selected_regions.csv")
    videos = pd.read_csv(ROOT / "benchmarks/partial_scan_pilot_v1/immutable/videos.csv").set_index("video_id")
    torch.manual_seed(20260726); np.random.seed(20260726)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(20260726); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    load_start = time.perf_counter(); model = YOLO(str(MODEL_PATH)); model_load_sec = time.perf_counter() - load_start
    rows, sample_rows, runtime_rows = [], [], []
    for video_id, selected in selection.groupby("video_id", sort=True):
        video_start = time.perf_counter(); decode_sec = inference_sec = feature_sec = 0.0
        video_samples = 0; peak_rss = psutil.Process().memory_info().rss
        for region in selected.sort_values("region_index").itertuples(index=False):
            command = [
                "ffmpeg", "-v", "error", "-ss", f"{region.start_sec:.6f}",
                "-t", f"{region.actual_duration_sec:.6f}", "-i", str(videos.loc[video_id].video_path),
                "-vf", f"fps={RATE:g},scale={WIDTH}:{HEIGHT}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
            ]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert process.stdout is not None
            frame_bytes = WIDTH * HEIGHT * 3
            frames, indices = [], []
            index = 0; read_start = time.perf_counter()
            while True:
                payload = process.stdout.read(frame_bytes)
                if not payload: break
                if len(payload) != frame_bytes:
                    process.kill(); raise RuntimeError(f"partial frame {len(payload)}/{frame_bytes}")
                frames.append(np.frombuffer(payload, np.uint8).reshape(HEIGHT, WIDTH, 3).copy())
                indices.append(index); index += 1
            decode_sec += time.perf_counter() - read_start
            stderr = process.stderr.read().decode() if process.stderr is not None else ""
            if process.wait() != 0: raise RuntimeError(stderr)
            region_samples = []
            previous = None
            for begin in range(0, len(frames), 64):
                batch = frames[begin:begin + 64]
                infer_start = time.perf_counter()
                results = model.predict(
                    source=batch, imgsz=320, conf=0.25, iou=0.7, classes=TARGET_CLASSES,
                    device=0 if torch.cuda.is_available() else "cpu", half=torch.cuda.is_available(),
                    max_det=100, verbose=False, stream=False,
                )
                inference_sec += time.perf_counter() - infer_start
                feature_start = time.perf_counter()
                for local_index, result in zip(indices[begin:begin + 64], results):
                    values = p1_frame_features(result, previous); previous = dict(values)
                    sample = {"sample_index": local_index, "timestamp_sec": region.start_sec + local_index / RATE, **values}
                    region_samples.append(sample)
                    sample_rows.append({"video_id": video_id, "region_id": region.region_id, **sample})
                feature_sec += time.perf_counter() - feature_start
            region_frame = pd.DataFrame(region_samples)
            rows.append(aggregate(region_frame, pd.Series(region._asdict())))
            video_samples += len(region_frame)
            peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        runtime_rows.append({
            "run_index": run_index, "video_id": video_id, "selected_region_count": len(selected),
            "selected_duration_sec": float(selected.actual_duration_sec.sum()), "sample_count": video_samples,
            "model_load_time_sec_allocated": model_load_sec / selection.video_id.nunique(),
            "decode_time_sec": decode_sec, "inference_time_sec": inference_sec,
            "feature_time_sec": feature_sec, "total_wallclock_sec": time.perf_counter() - video_start + model_load_sec / selection.video_id.nunique(),
            "peak_cpu_memory_bytes": int(peak_rss),
            "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0,
            "process_lifetime_max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        })
    features = pd.DataFrame(rows).sort_values(["video_id", "region_index"]).reset_index(drop=True)
    samples = pd.DataFrame(sample_rows).sort_values(["video_id", "region_id", "sample_index"]).reset_index(drop=True)
    runtime = pd.DataFrame(runtime_rows)
    features.to_parquet(EXPERIMENT / f"region_features_run{run_index}.parquet", index=False)
    samples.to_parquet(EXPERIMENT / f"sample_features_run{run_index}.parquet", index=False)
    runtime.to_csv(EXPERIMENT / f"runtime_run{run_index}.csv", index=False)
    manifest = {
        "run_index": run_index, "region_count": len(features), "sample_count": len(samples),
        "canonical_feature_hash": canonical_hash(features), "feature_file_sha256": sha256(EXPERIMENT / f"region_features_run{run_index}.parquet"),
        "sample_file_sha256": sha256(EXPERIMENT / f"sample_features_run{run_index}.parquet"),
        "runtime_total_sec": float(runtime.total_wallclock_sec.sum()), "missing_cells": int(features.isna().sum().sum()),
        "model_sha256": sha256(MODEL_PATH), "input_contract": "FROZEN_SELECTION_CSV_AND_SOURCE_VIDEO_BYTES_ONLY",
    }
    atomic_json(EXPERIMENT / f"run{run_index}_manifest.json", manifest)
    return manifest


def main() -> None:
    EXPERIMENT.mkdir(parents=True, exist_ok=True)
    manifests = [run_once(run) for run in (1, 2)]
    result = {
        "status": "PASS" if manifests[0]["canonical_feature_hash"] == manifests[1]["canonical_feature_hash"] else "FAIL",
        "deterministic_hash_match": manifests[0]["canonical_feature_hash"] == manifests[1]["canonical_feature_hash"],
        "runs": manifests, "implementation_hash": sha256(Path(__file__)),
        "forbidden_inputs_used": [], "tracking": False, "region_state_reset": True,
    }
    atomic_json(EXPERIMENT / "operator_manifest.json", result)
    if result["status"] != "PASS": raise AssertionError("H002 preview nondeterministic")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__": main()
