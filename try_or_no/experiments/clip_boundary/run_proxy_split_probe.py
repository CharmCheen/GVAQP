#!/usr/bin/env python3
"""Proxy-assisted split probe for expbin.

Uses proxy_score to identify potential zero-gap points in expanded intervals,
then only queries oracle at those candidates (± radius) instead of all frames.

Usage:
    python experiments/clip_boundary/run_proxy_split_probe.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/exp1_K10_proxy_split
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


def run_expbin_with_proxy_split(N, oracle, budget, min_len, rng,
                                 proxy_scores, quantile, radius):
    """Run expbin + proxy-assisted split.

    1. Sample random seed
    2. If positive, expbin expand
    3. Use proxy to find candidate zero-gap points
    4. Query oracle only at candidate ± radius
    5. Split at confirmed zero-gaps
    """
    # Pre-compute proxy threshold
    proxy_arr = np.array(proxy_scores)
    threshold = np.quantile(proxy_arr, quantile)

    covered = set()
    pred_clips = []

    while oracle.calls < budget:
        candidates = [i for i in range(N) if i not in covered]
        if not candidates:
            break
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
            if val == 1:
                left, right = expbin_expand_boundary(oracle, int(idx), N)
                # Proxy-assisted split
                clips = proxy_split_interval(
                    oracle, left, right, proxy_scores, threshold,
                    radius, budget, N)
                for sc in clips:
                    for k in range(sc[0], sc[1] + 1):
                        covered.add(k)
                    if sc[1] - sc[0] + 1 >= min_len:
                        pred_clips.append(sc)
                found = True
                break

        if not found and oracle.calls >= budget:
            break

    ps = oracle.get_phase_summary()
    return pred_clips, ps


def proxy_split_interval(oracle, left, right, proxy_scores, threshold,
                          radius, budget, N):
    """Split expanded interval using proxy-assisted oracle queries."""
    region_proxy = proxy_scores[left:right + 1]

    # Find candidate zero-gap points: proxy below threshold
    candidates = []
    for i, p in enumerate(region_proxy):
        if p < threshold:
            abs_idx = left + i
            candidates.append(abs_idx)

    # Query oracle at candidates ± radius
    confirmed_zeros = set()
    for c in candidates:
        for offset in range(-radius, radius + 1):
            q = c + offset
            if q < left or q > right:
                continue
            if q in oracle.cache:
                continue
            if oracle.calls >= budget:
                break
            try:
                oracle.query(q, phase="split")
            except BudgetExhausted:
                break
        # Check if candidate itself is zero
        if c in oracle.cache and oracle.cache[c] == 0:
            confirmed_zeros.add(c)

    # Also query all frames that are already in oracle.cache to get positives
    # Build clip list from oracle cache + confirmed zeros
    pos_frames = []
    for k in range(left, right + 1):
        if k in oracle.cache:
            if oracle.cache[k] == 1:
                pos_frames.append(k)
        # Frames not in cache are unknown — we don't assume

    # Split at confirmed zero gaps
    clips = []
    if pos_frames:
        seg_start = pos_frames[0]
        for j in range(1, len(pos_frames)):
            if pos_frames[j] - pos_frames[j - 1] > 1:
                # Check if gap contains a confirmed zero
                gap_has_zero = any(
                    pos_frames[j - 1] < z < pos_frames[j]
                    for z in confirmed_zeros)
                if gap_has_zero:
                    clips.append((seg_start, pos_frames[j - 1]))
                    seg_start = pos_frames[j]
        clips.append((seg_start, pos_frames[-1]))

    return clips


def run_dense_split(N, oracle, budget, min_len, rng, true_clips):
    """Run expbin with dense oracle split (baseline from no-leak code)."""
    from run_uniform_boundary_vs_frame import seed_boundary, expbin_expand_boundary
    return seed_boundary(N, oracle, budget, min_len, rng, true_clips, expbin_expand_boundary)


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
    proxy_scores = df["proxy_score"].tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    quantiles = [0.1, 0.2, 0.3]
    radii = [1, 2, 3]

    print(f"Loaded {N} frames, {len(true_clips)} true clips")
    print(f"Budgets: {budgets}, Trials: {args.trials}")
    print(f"Proxy quantiles: {quantiles}, Radii: {radii}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    # Also run baselines
    from run_uniform_boundary_vs_frame import frame_stitch

    all_rows = []

    for budget in budgets:
        print(f"  budget={budget:<6d} ...", end="", flush=True)

        for t in range(args.trials):
            rng = np.random.RandomState(args.seed + t)

            # --- frame_stitch baseline ---
            oracle_fs = Oracle(labels)
            m_fs, clips_fs = frame_stitch(oracle_fs, N, budget, 10, rng, true_clips)
            all_rows.append({
                "method": "frame_stitch", "budget": budget, "trial": t,
                "oracle_calls": oracle_fs.calls,
                "seed_calls": 0, "boundary_calls": 0, "split_calls": 0,
                "recall": m_fs["recall"], "precision": m_fs["precision"],
                "num_pred_clips": m_fs["num_pred_clips"],
            })

            # --- dense split (no-leak expbin) ---
            rng2 = np.random.RandomState(args.seed + t)
            oracle_ds = Oracle(labels, budget=budget + 2)
            m_ds, clips_ds = run_dense_split(N, oracle_ds, budget, args.min_len, rng2, true_clips)
            ps_ds = oracle_ds.get_phase_summary()
            all_rows.append({
                "method": "expbin_dense_split", "budget": budget, "trial": t,
                "oracle_calls": oracle_ds.calls,
                "seed_calls": ps_ds["seed_calls"],
                "boundary_calls": ps_ds["boundary_calls"],
                "split_calls": ps_ds["split_calls"],
                "recall": m_ds["recall"], "precision": m_ds["precision"],
                "num_pred_clips": m_ds["num_pred_clips"],
            })

            # --- proxy-assisted split ---
            for q in quantiles:
                for r in radii:
                    rng3 = np.random.RandomState(args.seed + t)
                    oracle_ps = Oracle(labels, budget=budget + 2)
                    clips_ps, ps = run_expbin_with_proxy_split(
                        N, oracle_ps, budget, args.min_len, rng3,
                        proxy_scores, q, r)
                    ev = eval_metrics(clips_ps, true_clips)
                    all_rows.append({
                        "method": f"expbin_proxy_q{q}_r{r}",
                        "budget": budget, "trial": t,
                        "oracle_calls": oracle_ps.calls,
                        "seed_calls": ps["seed_calls"],
                        "boundary_calls": ps["boundary_calls"],
                        "split_calls": ps["split_calls"],
                        "recall": ev["recall"], "precision": ev["precision"],
                        "num_pred_clips": ev["num_pred_clips"],
                    })

        print(" done")

    # Save trials
    trials_df = pd.DataFrame(all_rows)
    trials_df.to_csv(os.path.join(args.out_dir, "trials.csv"), index=False)

    # Summary
    summary = (trials_df.groupby(["method", "budget"])
               .agg(mean_recall=("recall", "mean"),
                    std_recall=("recall", "std"),
                    mean_precision=("precision", "mean"),
                    mean_num_pred_clips=("num_pred_clips", "mean"),
                    mean_oracle_calls=("oracle_calls", "mean"),
                    mean_seed_calls=("seed_calls", "mean"),
                    mean_boundary_calls=("boundary_calls", "mean"),
                    mean_split_calls=("split_calls", "mean"))
               .reset_index())
    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)

    # Terminal output — selected methods
    print()
    hdr = (f"{'method':<30s}  {'budget':>6s}  {'recall':>7s}  {'prec':>6s}  "
           f"{'calls':>6s}  {'seed':>5s}  {'bnd':>5s}  {'splt':>5s}")
    print(hdr)
    print("-" * len(hdr))

    # Show: frame_stitch, dense_split, and best proxy configs
    show_methods = ["frame_stitch", "expbin_dense_split"]
    # Add proxy methods for q=0.2 r=2 as representative
    for q in quantiles:
        for r in radii:
            show_methods.append(f"expbin_proxy_q{q}_r{r}")

    for _, r in summary.iterrows():
        if r["method"] not in show_methods:
            continue
        print(f"{r['method']:<30s}  {int(r['budget']):>6d}  "
              f"{r['mean_recall']:>7.3f}  {r['mean_precision']:>6.3f}  "
              f"{r['mean_oracle_calls']:>6.0f}  {r['mean_seed_calls']:>5.0f}  "
              f"{r['mean_boundary_calls']:>5.0f}  {r['mean_split_calls']:>5.0f}")

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
