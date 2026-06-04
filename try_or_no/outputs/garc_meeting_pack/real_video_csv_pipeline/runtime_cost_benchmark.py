#!/usr/bin/env python3
"""
runtime_cost_benchmark.py

Micro-benchmark to distinguish offline CSV generation cost from query-time cost.
Measures proxy-only, oracle-only, dual-model inference fps, and CSV read time.

Usage:
    python runtime_cost_benchmark.py \
        --video /path/to/video.mov \
        --proxy-model /path/to/yolov8n.pt \
        --oracle-model /path/to/yolov8x.pt \
        --csv-path outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg.csv \
        --max-frames 100
"""

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--proxy-model", required=True)
    p.add_argument("--oracle-model", required=True)
    p.add_argument("--csv-path", required=True)
    p.add_argument("--max-frames", type=int, default=100)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="auto")
    return p.parse_args()


def resolve_device(d):
    if d != "auto":
        return d
    import torch
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def load_frames(video_path, max_frames):
    """Load max_frames into memory once for fair benchmarking."""
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    while len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames


def bench_inference(model, frames, conf, imgsz, label):
    """Run inference on pre-loaded frames, return fps."""
    # Warmup
    if frames:
        model(frames[0], conf=conf, imgsz=imgsz, verbose=False)

    t0 = time.perf_counter()
    for f in frames:
        model(f, conf=conf, imgsz=imgsz, verbose=False)
    elapsed = time.perf_counter() - t0
    fps = len(frames) / elapsed if elapsed > 0 else 0
    print(f"  [{label}] {len(frames)} frames in {elapsed:.2f}s → {fps:.1f} fps")
    return fps, elapsed


def bench_csv_read_and_stitch(csv_path, k=5):
    """Measure CSV read + clip stitching time."""
    # CSV read
    t0 = time.perf_counter()
    df = pd.read_csv(csv_path)
    read_time = time.perf_counter() - t0

    # Clip stitching (tau=20)
    t1 = time.perf_counter()
    labels = df[f"label_K{k}"].tolist()
    clips = []
    start = None
    tau = 20
    for i, v in enumerate(labels):
        if v == 1:
            if start is None:
                start = i
        else:
            if start is not None:
                if i - start >= tau:
                    clips.append((start, i - 1))
                start = None
    if start is not None and len(labels) - start >= tau:
        clips.append((start, len(labels) - 1))
    stitch_time = time.perf_counter() - t1

    print(f"  [CSV read] {len(df)} rows in {read_time*1000:.1f}ms")
    print(f"  [Clip stitch] {len(clips)} clips in {stitch_time*1000:.2f}ms")
    return read_time, stitch_time, len(df), len(clips)


def main():
    args = parse_args()
    device = resolve_device(args.device)
    print(f"Device: {device}")
    print(f"Max frames: {args.max_frames}")
    print()

    from ultralytics import YOLO

    # Load frames once
    print("Loading video frames...")
    frames = load_frames(args.video, args.max_frames)
    print(f"Loaded {len(frames)} frames\n")

    # Load models
    print("Loading proxy model (YOLOv8n)...")
    proxy = YOLO(args.proxy_model)
    proxy.to(device)

    print("Loading oracle model (YOLOv8x)...")
    oracle = YOLO(args.oracle_model)
    oracle.to(device)
    print()

    # Benchmarks
    print("=== Inference Benchmarks ===")
    proxy_fps, proxy_time = bench_inference(proxy, frames, args.conf, args.imgsz, "proxy-only (YOLOv8n)")
    oracle_fps, oracle_time = bench_inference(oracle, frames, args.conf, args.imgsz, "oracle-only (YOLOv8x)")

    # Dual: interleave proxy + oracle per frame (worst-case sequential)
    print("  [dual-model] running sequentially (proxy + oracle per frame)...")
    t0 = time.perf_counter()
    for f in frames:
        proxy(f, conf=args.conf, imgsz=args.imgsz, verbose=False)
        oracle(f, conf=args.conf, imgsz=args.imgsz, verbose=False)
    dual_time = time.perf_counter() - t0
    dual_fps = len(frames) / dual_time if dual_time > 0 else 0
    print(f"  [dual-model] {len(frames)} frames in {dual_time:.2f}s → {dual_fps:.1f} fps")
    print()

    # CSV benchmark
    print("=== CSV Read + Stitch ===")
    csv_path = Path(args.csv_path)
    if csv_path.exists():
        read_time, stitch_time, n_rows, n_clips = bench_csv_read_and_stitch(csv_path)
    else:
        print(f"  CSV not found: {csv_path}, skipping")
        read_time, stitch_time, n_rows, n_clips = 0, 0, 0, 0
    print()

    # --- Query-time cost model ---
    N = n_rows if n_rows > 0 else len(frames)
    print("=== Query-Time Cost Model ===")
    print(f"N (processed frames) = {N}")
    print()

    exact_query_time = N / oracle_fps if oracle_fps > 0 else float("inf")
    print(f"Exact query (oracle on all N frames): {exact_query_time:.2f}s")

    # Candidate generation: assume proxy full scan or proxy table lookup
    # If precomputed: candidate gen is just filtering the CSV
    # If not precomputed: must run proxy on all frames
    proxy_scan_time = N / proxy_fps if proxy_fps > 0 else float("inf")
    print(f"Proxy full scan time: {proxy_scan_time:.2f}s")
    print(f"CSV read time: {read_time*1000:.1f}ms")
    print(f"Clip stitch time: {stitch_time*1000:.2f}ms")
    print()

    print("=== Estimated Speedup (precomputed proxy table) ===")
    print(f"{'oracle_ratio':>14s} {'candidates':>10s} {'oracle_time':>12s} {'approx_total':>13s} {'speedup':>8s}")
    print("-" * 60)

    results = []
    for ratio in [0.05, 0.10, 0.20]:
        n_candidates = max(1, int(N * ratio))
        oracle_partial_time = n_candidates / oracle_fps if oracle_fps > 0 else 0
        approx_total = read_time + stitch_time + oracle_partial_time
        speedup = exact_query_time / approx_total if approx_total > 0 else float("inf")
        print(f"{ratio:>13.0%} {n_candidates:>10d} {oracle_partial_time:>11.2f}s {approx_total:>12.2f}s {speedup:>7.1f}x")
        results.append({
            "oracle_ratio": ratio,
            "n_candidates": n_candidates,
            "oracle_partial_time": oracle_partial_time,
            "approx_total": approx_total,
            "speedup": speedup,
        })
    print()

    print("=== Estimated Speedup (online: proxy scan NOT precomputed) ===")
    print(f"{'oracle_ratio':>14s} {'candidates':>10s} {'oracle_time':>12s} {'approx_total':>13s} {'speedup':>8s}")
    print("-" * 60)
    for ratio in [0.05, 0.10, 0.20]:
        n_candidates = max(1, int(N * ratio))
        oracle_partial_time = n_candidates / oracle_fps if oracle_fps > 0 else 0
        approx_total = proxy_scan_time + oracle_partial_time
        speedup = exact_query_time / approx_total if approx_total > 0 else float("inf")
        print(f"{ratio:>13.0%} {n_candidates:>10d} {oracle_partial_time:>11.2f}s {approx_total:>12.2f}s {speedup:>7.1f}x")

    # Return structured results for report generation
    return {
        "proxy_fps": proxy_fps,
        "oracle_fps": oracle_fps,
        "dual_fps": dual_fps,
        "proxy_time": proxy_time,
        "oracle_time": oracle_time,
        "dual_time": dual_time,
        "csv_read_time": read_time,
        "csv_stitch_time": stitch_time,
        "n_rows": N,
        "n_clips": n_clips,
        "exact_query_time": exact_query_time,
        "proxy_scan_time": proxy_scan_time,
        "speedup_table": results,
    }


if __name__ == "__main__":
    main()
