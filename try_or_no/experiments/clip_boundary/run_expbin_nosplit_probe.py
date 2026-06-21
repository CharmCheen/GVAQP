#!/usr/bin/env python3
"""No-split upper bound probe for expbin.

Measures how well expbin expansion discovers clip regions WITHOUT post-split.
Two evaluation modes:
  A. Strict legality: predicted interval invalid if any label==0 inside
  B. Tolerant hit: counts as hit if IoU >= 0.5 with true clip

Usage:
    python experiments/clip_boundary/run_expbin_nosplit_probe.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/exp1_K10_nosplit
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from run_uniform_boundary_vs_frame import (
    Oracle, BudgetExhausted, labels_to_clips, eval_metrics,
    expbin_expand_boundary, clip_iou, length_bucket,
)


def run_nosplit_expbin(N, oracle, budget, min_len, rng):
    """Run expbin without post-split. Return raw expanded intervals."""
    intervals = []
    seed_calls = 0

    while oracle.calls < budget:
        candidates = list(range(N))
        batch_size = max(1, min(budget - oracle.calls, len(candidates)))
        if batch_size <= 0:
            break
        sampled = rng.choice(candidates, size=min(100, batch_size), replace=False)
        found = False

        for idx in sampled:
            if oracle.calls >= budget:
                break
            try:
                val = oracle.query(int(idx), phase="seed")
            except BudgetExhausted:
                break
            seed_calls += 1
            if val == 1:
                left, right = expbin_expand_boundary(oracle, int(idx), N)
                intervals.append((left, right))
                found = True
                break

        if not found and oracle.calls >= budget:
            break

    ps = oracle.get_phase_summary()
    return intervals, ps


def strict_check(interval, labels):
    """Check if interval contains any label==0 frames."""
    left, right = interval
    for k in range(left, right + 1):
        if labels[k] == 0:
            return False
    return True


def evaluate_nosplit(intervals, labels, true_clips, min_len, N):
    """Evaluate no-split intervals with strict and tolerant metrics."""
    # Filter intervals by min_len
    long_intervals = [(l, r) for l, r in intervals if r - l + 1 >= min_len]

    # --- Strict legality ---
    valid_intervals = [(l, r) for l, r in long_intervals if strict_check((l, r), labels)]
    invalid_count = len(long_intervals) - len(valid_intervals)
    invalid_rate = invalid_count / len(long_intervals) if long_intervals else 0.0

    # Strict recall: how many true clips have a valid interval with IoU >= 0.5
    strict_hits = 0
    for tc in true_clips:
        for vi in valid_intervals:
            if clip_iou(tc, vi) >= 0.5:
                strict_hits += 1
                break
    strict_recall = strict_hits / len(true_clips) if true_clips else 0.0
    strict_precision = len(valid_intervals) / len(long_intervals) if long_intervals else 0.0

    # --- Tolerant hit ---
    # Any interval (even invalid) counts as hit if IoU >= 0.5 with true clip
    tolerant_hits = 0
    per_clip_tolerant = []
    for tc in true_clips:
        hit = False
        for li in long_intervals:
            if clip_iou(tc, li) >= 0.5:
                hit = True
                break
        per_clip_tolerant.append(hit)
        if hit:
            tolerant_hits += 1
    tolerant_recall = tolerant_hits / len(true_clips) if true_clips else 0.0

    # Tolerant precision: among long_intervals, how many hit at least one true clip
    interval_hits = 0
    for li in long_intervals:
        for tc in true_clips:
            if clip_iou(tc, li) >= 0.5:
                interval_hits += 1
                break
    tolerant_precision = interval_hits / len(long_intervals) if long_intervals else 0.0

    # Average IoU of best-matching true clip for each interval
    ious = []
    for li in long_intervals:
        best_iou = max((clip_iou(tc, li) for tc in true_clips), default=0.0)
        ious.append(best_iou)
    avg_iou = np.mean(ious) if ious else 0.0

    return {
        "strict_recall": strict_recall,
        "tolerant_recall": tolerant_recall,
        "invalid_rate": invalid_rate,
        "strict_precision": strict_precision,
        "tolerant_precision": tolerant_precision,
        "avg_iou": avg_iou,
        "num_intervals": len(intervals),
        "num_long_intervals": len(long_intervals),
        "num_valid_intervals": len(valid_intervals),
        "per_clip_tolerant": per_clip_tolerant,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]
    df = pd.read_csv(args.csv)
    labels = df[args.label_col].astype(int).tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    print(f"Loaded {N} frames, {len(true_clips)} true clips")
    print(f"Budgets: {budgets}, Trials: {args.trials}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    # Also run frame_stitch as baseline
    from run_uniform_boundary_vs_frame import frame_stitch

    all_rows = []
    interval_rows = []

    for budget in budgets:
        print(f"  budget={budget:<6d} ...", end="", flush=True)

        for t in range(args.trials):
            rng = np.random.RandomState(args.seed + t)

            # --- no-split expbin ---
            oracle = Oracle(labels, budget=budget + 2)
            intervals, ps = run_nosplit_expbin(N, oracle, budget, args.min_len, rng)
            ev = evaluate_nosplit(intervals, labels, true_clips, args.min_len, N)
            all_rows.append({
                "method": "expbin_nosplit", "budget": budget, "trial": t,
                "oracle_calls": oracle.calls,
                "seed_calls": ps["seed_calls"],
                "boundary_calls": ps["boundary_calls"],
                "split_calls": ps["split_calls"],
                "num_intervals": ev["num_intervals"],
                "num_long_intervals": ev["num_long_intervals"],
                "num_valid_intervals": ev["num_valid_intervals"],
                "strict_recall": ev["strict_recall"],
                "tolerant_recall": ev["tolerant_recall"],
                "invalid_rate": ev["invalid_rate"],
                "strict_precision": ev["strict_precision"],
                "tolerant_precision": ev["tolerant_precision"],
                "avg_iou": ev["avg_iou"],
                "per_clip_tolerant": ev["per_clip_tolerant"],
            })
            for ci, (cs, ce) in enumerate(intervals):
                interval_rows.append({
                    "method": "expbin_nosplit", "budget": budget, "trial": t,
                    "clip_id": ci, "start": cs, "end": ce, "length": ce - cs + 1,
                    "is_valid": strict_check((cs, ce), labels),
                })

            # --- frame_stitch baseline ---
            rng2 = np.random.RandomState(args.seed + t)
            oracle2 = Oracle(labels)
            m2, clips2 = frame_stitch(oracle2, N, budget, 10, rng2, true_clips)
            all_rows.append({
                "method": "frame_stitch", "budget": budget, "trial": t,
                "oracle_calls": oracle2.calls,
                "seed_calls": 0, "boundary_calls": 0, "split_calls": 0,
                "num_intervals": len(clips2), "num_long_intervals": len(clips2),
                "num_valid_intervals": len(clips2),
                "strict_recall": m2["recall"],
                "tolerant_recall": m2["recall"],
                "invalid_rate": 0.0,
                "strict_precision": m2["precision"],
                "tolerant_precision": m2["precision"],
                "avg_iou": 0.0,
                "per_clip_hit": m2["per_clip_hit"],
            })

        print(" done")

    # Save
    trials_df = pd.DataFrame(all_rows)
    trials_df.drop(columns=["per_clip_tolerant"], errors="ignore").drop(
        columns=["per_clip_hit"], errors="ignore").to_csv(
        os.path.join(args.out_dir, "trials.csv"), index=False)

    if interval_rows:
        pd.DataFrame(interval_rows).to_csv(
            os.path.join(args.out_dir, "predicted_intervals.csv"), index=False)

    # Summary
    summary = (trials_df.groupby(["method", "budget"])
               .agg(mean_strict_recall=("strict_recall", "mean"),
                    mean_tolerant_recall=("tolerant_recall", "mean"),
                    mean_invalid_rate=("invalid_rate", "mean"),
                    mean_strict_precision=("strict_precision", "mean"),
                    mean_tolerant_precision=("tolerant_precision", "mean"),
                    mean_avg_iou=("avg_iou", "mean"),
                    mean_oracle_calls=("oracle_calls", "mean"),
                    mean_seed_calls=("seed_calls", "mean"),
                    mean_boundary_calls=("boundary_calls", "mean"),
                    mean_split_calls=("split_calls", "mean"),
                    mean_num_intervals=("num_intervals", "mean"),
                    mean_num_valid_intervals=("num_valid_intervals", "mean"))
               .reset_index())
    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)

    # Terminal output
    print()
    hdr = (f"{'method':<25s}  {'budget':>6s}  {'str_rec':>8s}  {'hit_rec':>8s}  "
           f"{'invld%':>7s}  {'str_prec':>8s}  {'hit_prec':>8s}  "
           f"{'avg_iou':>7s}  {'calls':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for _, r in summary.iterrows():
        print(f"{r['method']:<25s}  {int(r['budget']):>6d}  "
              f"{r['mean_strict_recall']:>8.3f}  {r['mean_tolerant_recall']:>8.3f}  "
              f"{r['mean_invalid_rate']:>7.1%}  {r['mean_strict_precision']:>8.3f}  "
              f"{r['mean_tolerant_precision']:>8.3f}  "
              f"{r['mean_avg_iou']:>7.3f}  {r['mean_oracle_calls']:>6.0f}")

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
