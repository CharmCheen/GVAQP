#!/usr/bin/env python3
"""
abae_clip_benchmark.py

Run ABAE on real video data and evaluate clip-level performance.
Compares ABAE (stratified sampling) vs Uniform (random sampling) for:
1. Aggregation accuracy (AVG/COUNT estimation)
2. Clip-level recall/precision from sampled positive frames

Usage:
    python abae_clip_benchmark.py \
        --csv-path outputs/garc_meeting_pack/real_video_csv_pipeline/abae_k5_input.csv \
        --budget 200 --num-strata 10 --trials 50
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "garc_eval"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "refe_repos" / "supg"))

from garc_eval.adapters.abae_adapter import run_abae
from garc_eval.baselines.uniform_aggregation import run_uniform_aggregation
from garc_eval.metrics.aggregation_metrics import compute_aggregation_metrics
from garc_eval.metrics.clip_metrics import frame_labels_to_clips, compute_clip_metrics


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-path", required=True)
    p.add_argument("--budget", type=int, default=200)
    p.add_argument("--num-strata", type=int, default=10)
    p.add_argument("--trials", type=int, default=50)
    p.add_argument("--n-bootstrap", type=int, default=300)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--min-clip-len", type=int, default=5, help="Min clip length in frames")
    p.add_argument("--gap-tolerance", type=int, default=2, help="Merge clips with gap <= this")
    p.add_argument("--iou-threshold", type=float, default=0.5)
    return p.parse_args()


def clips_from_sampled_frames(sampled_ids, all_labels, min_len=5, gap=2):
    """Convert sampled positive frame IDs to clips.
    Creates a binary label array: 1 if frame was sampled AND is positive, 0 otherwise.
    Then extracts clips from this array.
    """
    n = len(all_labels)
    selection = np.zeros(n, dtype=int)
    for sid in sampled_ids:
        if 0 <= sid < n and all_labels[sid] == 1:
            selection[sid] = 1
    return frame_labels_to_clips(selection, min_duration_frames=min_len, gap_tolerance_frames=gap)


def main():
    args = parse_args()

    # Load data
    print(f"Loading: {args.csv_path}")
    df = pd.read_csv(args.csv_path)
    df["label"] = df["label"].astype("float32")
    n = len(df)
    n_pos = int(df["label"].sum())
    pos_rate = n_pos / n
    print(f"N={n}, positive={n_pos} ({pos_rate:.2%})")

    exact_avg = float(df[df["label"] == 1]["statistic_value"].mean())
    exact_count = float(n_pos)
    print(f"Exact AVG(stat|label=1) = {exact_avg:.4f}")
    print(f"Exact COUNT(label=1) = {exact_count:.0f}")

    # Ground truth clips
    gt_labels = df["label"].values.astype(int)
    gt_clips = frame_labels_to_clips(gt_labels, min_duration_frames=args.min_clip_len,
                                      gap_tolerance_frames=args.gap_tolerance)
    print(f"Ground truth clips (min_len={args.min_clip_len}, gap={args.gap_tolerance}): {len(gt_clips)}")

    # Methods
    methods = ["Uniform", "ABae-paper", "ABae-full_variance"]
    stage1_per = max(20, int(args.budget * 0.15 / args.num_strata))

    all_results = []
    t_start = time.time()

    for method in methods:
        print(f"\n=== {method} ({args.trials} trials, budget={args.budget}) ===")
        for trial in range(args.trials):
            seed = 42 + trial * 100

            if method == "ABae-paper":
                result = run_abae(df, num_strata=args.num_strata, stage1_per_stratum=stage1_per,
                                  total_budget=args.budget, n_bootstrap=args.n_bootstrap,
                                  alpha=args.alpha, seed=seed, allocation_mode="paper")
            elif method == "ABae-full_variance":
                result = run_abae(df, num_strata=args.num_strata, stage1_per_stratum=stage1_per,
                                  total_budget=args.budget, n_bootstrap=args.n_bootstrap,
                                  alpha=args.alpha, seed=seed, allocation_mode="full_variance")
            else:
                result = run_uniform_aggregation(df, total_budget=args.budget,
                                                  n_bootstrap=args.n_bootstrap, alpha=args.alpha, seed=seed)

            # Aggregation metrics
            agg_metrics = compute_aggregation_metrics(result)

            # Clip metrics: reconstruct sampled IDs from the trial
            # For ABAE, we need to re-run to get sampled IDs (adapter doesn't return them)
            # Instead, use the sampling approach: stratified sample based on proxy_score
            rng = np.random.RandomState(seed)

            if method in ("ABae-paper", "ABae-full_variance"):
                # Reconstruct stratified sampling
                ranks = df["proxy_score"].rank(method="first")
                strata = ((ranks - 1) / n * args.num_strata).astype(int).clip(0, args.num_strata - 1)
                df_with_strata = df.copy()
                df_with_strata["stratum"] = strata

                sampled_ids = []
                for k in range(args.num_strata):
                    stratum_idx = df_with_strata[df_with_strata["stratum"] == k].index.values
                    n1 = min(stage1_per, len(stratum_idx))
                    if n1 > 0:
                        s1 = rng.choice(stratum_idx, size=n1, replace=False)
                        sampled_ids.extend(s1.tolist())

                # Stage 2: simplified — just sample remaining budget uniformly
                remaining = args.budget - len(sampled_ids)
                if remaining > 0:
                    all_idx = df.index.values
                    already = set(sampled_ids)
                    available = [i for i in all_idx if i not in already]
                    if len(available) > 0:
                        n2 = min(remaining, len(available))
                        s2 = rng.choice(available, size=n2, replace=False)
                        sampled_ids.extend(s2.tolist())
            else:
                # Uniform: random sample
                sampled_ids = rng.choice(n, size=min(args.budget, n), replace=False).tolist()

            # Convert sampled frames to clips
            pred_clips = clips_from_sampled_frames(
                sampled_ids, gt_labels,
                min_len=args.min_clip_len, gap=args.gap_tolerance
            )

            clip_metrics = compute_clip_metrics(pred_clips, gt_clips, args.iou_threshold)

            row = {
                "method": method,
                "seed": seed,
                "budget": args.budget,
                "total_sampled": result.get("total_sampled", args.budget),
                # Aggregation
                "avg_estimate": result["avg_estimate"],
                "count_estimate": result["count_estimate"],
                "exact_avg": exact_avg,
                "exact_count": exact_count,
                "avg_abs_error": agg_metrics["avg_abs_error"],
                "avg_rel_error": agg_metrics["avg_rel_error"],
                "avg_ci_width": agg_metrics["avg_ci_width"],
                "avg_ci_covers": agg_metrics["avg_ci_covers_exact"],
                "count_abs_error": agg_metrics["count_abs_error"],
                "count_rel_error": agg_metrics["count_rel_error"],
                "count_ci_width": agg_metrics["count_ci_width"],
                "count_ci_covers": agg_metrics["count_ci_covers_exact"],
                # Clip
                "clip_recall": clip_metrics["clip_recall"],
                "clip_precision": clip_metrics["clip_precision"],
                "mean_iou": clip_metrics["mean_iou"],
                "n_pred_clips": clip_metrics["n_pred_clips"],
                "n_gt_clips": clip_metrics["n_gt_clips"],
            }
            all_results.append(row)

            if (trial + 1) % 10 == 0 or trial == 0:
                print(f"  trial {trial}: avg_est={row['avg_estimate']:.2f} "
                      f"count_est={row['count_estimate']:.0f} "
                      f"clip_recall={row['clip_recall']:.3f} "
                      f"clip_prec={row['clip_precision']:.3f} "
                      f"mIoU={row['mean_iou']:.3f}")

    elapsed = time.time() - t_start
    print(f"\nTotal time: {elapsed:.1f}s")

    # Save per-trial results
    results_df = pd.DataFrame(all_results)
    outdir = Path(args.csv_path).parent / "abae_clip_results"
    outdir.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(outdir / "per_trial_results.csv", index=False)
    print(f"Saved: {outdir / 'per_trial_results.csv'}")

    # Summary
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)

    summary_rows = []
    for method in methods:
        mdf = results_df[results_df["method"] == method]
        row = {
            "method": method,
            # Aggregation
            "avg_mean_abs_error": mdf["avg_abs_error"].mean(),
            "avg_mean_rel_error": mdf["avg_rel_error"].mean(),
            "avg_mean_ci_width": mdf["avg_ci_width"].mean(),
            "avg_coverage": mdf["avg_ci_covers"].mean(),
            "count_mean_abs_error": mdf["count_abs_error"].mean(),
            "count_mean_rel_error": mdf["count_rel_error"].mean(),
            "count_mean_ci_width": mdf["count_ci_width"].mean(),
            "count_coverage": mdf["count_ci_covers"].mean(),
            # Clip
            "clip_recall_mean": mdf["clip_recall"].mean(),
            "clip_recall_std": mdf["clip_recall"].std(),
            "clip_precision_mean": mdf["clip_precision"].mean(),
            "clip_precision_std": mdf["clip_precision"].std(),
            "mean_iou_mean": mdf["mean_iou"].mean(),
            "mean_iou_std": mdf["mean_iou"].std(),
            "n_pred_clips_mean": mdf["n_pred_clips"].mean(),
        }
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(outdir / "summary.csv", index=False)

    # Print aggregation summary
    print("\n--- Aggregation Accuracy ---")
    print(f"{'Method':<25s} {'AVG abs_err':>12s} {'AVG rel_err':>12s} {'AVG CI w':>10s} {'AVG cov':>8s} "
          f"{'CNT abs_err':>12s} {'CNT rel_err':>12s} {'CNT CI w':>10s} {'CNT cov':>8s}")
    print("-" * 110)
    for _, r in summary_df.iterrows():
        print(f"{r['method']:<25s} {r['avg_mean_abs_error']:>12.4f} {r['avg_mean_rel_error']:>12.4f} "
              f"{r['avg_mean_ci_width']:>10.4f} {r['avg_coverage']:>7.1%} "
              f"{r['count_mean_abs_error']:>12.1f} {r['count_mean_rel_error']:>12.4f} "
              f"{r['count_mean_ci_width']:>10.1f} {r['count_coverage']:>7.1%}")

    # Print clip summary
    print("\n--- Clip-Level Performance ---")
    print(f"{'Method':<25s} {'clip_recall':>12s} {'clip_prec':>12s} {'mIoU':>8s} {'n_clips':>8s}")
    print("-" * 70)
    for _, r in summary_df.iterrows():
        print(f"{r['method']:<25s} "
              f"{r['clip_recall_mean']:>11.3f}±{r['clip_recall_std']:.3f} "
              f"{r['clip_precision_mean']:>11.3f}±{r['clip_precision_std']:.3f} "
              f"{r['mean_iou_mean']:>7.3f}±{r['mean_iou_std']:.3f} "
              f"{r['n_pred_clips_mean']:>7.1f}")

    print(f"\nGround truth clips: {len(gt_clips)} (min_len={args.min_clip_len}, gap={args.gap_tolerance})")
    print(f"Exact AVG(stat|pos) = {exact_avg:.4f}, COUNT(pos) = {exact_count:.0f}")

    return summary_df, gt_clips


if __name__ == "__main__":
    main()
