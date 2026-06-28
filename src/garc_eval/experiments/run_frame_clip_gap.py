"""Frame-to-clip gap analysis experiment.

Runs SUPG and baselines on temporal video data, then measures
whether frame-level recall translates to clip-level recall.

Usage:
    python -m garc_eval.experiments.run_frame_clip_gap \\
        --source-csv path/to/supg_source.csv \\
        --frames-parquet path/to/frames.parquet \\
        --budget 500 --gamma 0.9 --delta 0.05 --trials 10 \\
        --iou-threshold 0.5 --min-clip-frames 3 --gap-tolerance 0 \\
        --outdir path/to/output
"""

import argparse
import json
import pathlib

import numpy as np
import pandas as pd

from garc_eval.baselines.u_noci import u_noci_rt, u_noci_pt
from garc_eval.baselines.u_ci import u_ci_rt
from garc_eval.adapters.supg_adapter import run_supg_rt, run_supg_pt
from garc_eval.metrics.frame_to_clip import (
    build_gt_clips,
    compute_frame_level_metrics,
    compute_clip_level_metrics,
    analyze_temporal_misses,
)


def run_single_trial(
    df: pd.DataFrame,
    method_name: str,
    budget: int,
    gamma: float,
    delta: float,
    seed: int,
) -> dict:
    """Run a single method for a single seed."""
    try:
        if method_name == "U-NOCI-RT":
            result = u_noci_rt(df, budget, gamma, seed)
        elif method_name == "U-CI-RT":
            result = u_ci_rt(df, budget, gamma, delta, seed)
        elif method_name == "SUPG-RT":
            result = run_supg_rt(df=df, budget=budget, gamma=gamma, delta=delta, seed=seed)
        elif method_name == "SUPG-PT":
            result = run_supg_pt(df=df, budget=budget, gamma=gamma, delta=delta, seed=seed)
        elif method_name == "U-NOCI-PT":
            result = u_noci_pt(df, budget, gamma, seed)
        else:
            raise ValueError(f"Unknown method: {method_name}")

        selected_ids = result["selected_ids"]
        return {
            "selected_ids": selected_ids,
            "error": None,
        }
    except Exception as e:
        return {
            "selected_ids": np.array([], dtype=int),
            "error": f"{type(e).__name__}: {e}",
        }


def main():
    parser = argparse.ArgumentParser(description="Frame-to-clip gap analysis")
    parser.add_argument("--source-csv", required=True, help="SUPG source CSV (id, label, proxy_score)")
    parser.add_argument("--frames-parquet", required=True, help="Frames parquet with temporal columns")
    parser.add_argument("--budget", type=int, default=500)
    parser.add_argument("--gamma", type=float, default=0.9)
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--min-clip-frames", type=int, default=3)
    parser.add_argument("--gap-tolerance", type=int, default=0)
    parser.add_argument("--methods", nargs="+",
                        default=["U-NOCI-RT", "U-CI-RT", "SUPG-RT"],
                        help="Methods to run")
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load data
    source_df = pd.read_csv(args.source_csv)
    frames_df = pd.read_parquet(args.frames_parquet)

    print(f"Loaded {len(source_df)} source rows, {len(frames_df)} frames")
    print(f"Sequences: {frames_df['video_id'].nunique()}")
    print(f"Positive rate: {source_df['label'].mean():.4f}")

    # Build GT clips
    gt_clips = build_gt_clips(frames_df, args.min_clip_frames, args.gap_tolerance)
    print(f"GT clips: {len(gt_clips)}")
    if len(gt_clips) > 0:
        print(f"  Mean duration: {gt_clips['duration_sec'].mean():.2f}s")
        print(f"  Min duration: {gt_clips['duration_sec'].min():.2f}s")
        print(f"  Max duration: {gt_clips['duration_sec'].max():.2f}s")

    # Save config
    config = {
        "source_csv": args.source_csv,
        "frames_parquet": args.frames_parquet,
        "budget": args.budget,
        "gamma": args.gamma,
        "delta": args.delta,
        "trials": args.trials,
        "iou_threshold": args.iou_threshold,
        "min_clip_frames": args.min_clip_frames,
        "gap_tolerance": args.gap_tolerance,
        "n_frames": len(source_df),
        "n_gt_clips": len(gt_clips),
        "positive_rate": float(source_df["label"].mean()),
    }
    with open(outdir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Save GT clips
    if len(gt_clips) > 0:
        gt_clips.to_csv(outdir / "gt_clips.csv", index=False)

    # Run experiments
    all_results = []
    for method_name in args.methods:
        print(f"\n=== {method_name} ({args.trials} trials) ===")
        for seed in range(args.trials):
            trial_result = run_single_trial(
                source_df, method_name, args.budget, args.gamma, args.delta, seed
            )

            if trial_result["error"]:
                print(f"  seed={seed}: ERROR - {trial_result['error']}")
                all_results.append({
                    "method": method_name, "seed": seed, "error": trial_result["error"],
                })
                continue

            selected_ids = trial_result["selected_ids"]

            # Frame-level metrics
            frame_metrics = compute_frame_level_metrics(source_df, selected_ids)

            # Clip-level metrics (using frame coverage approach)
            clip_metrics = compute_clip_level_metrics(
                gt_clips, frames_df, selected_ids,
                coverage_threshold=0.5, iou_threshold=args.iou_threshold,
            )

            # Temporal miss analysis
            miss_analysis = analyze_temporal_misses(
                frames_df, selected_ids, gt_clips
            )

            # Compute gap
            frame_recall = frame_metrics["frame_recall"]
            clip_recall = clip_metrics["clip_recall_coverage"]
            gap = frame_recall - clip_recall

            row = {
                "method": method_name,
                "seed": seed,
                "frame_recall": frame_recall,
                "frame_precision": frame_metrics["frame_precision"],
                "clip_recall_coverage": clip_metrics["clip_recall_coverage"],
                "clip_recall_iou": clip_metrics["clip_recall_iou"],
                "clip_precision": clip_metrics["clip_precision"],
                "mIoU": clip_metrics["mIoU"],
                "mean_coverage": clip_metrics["mean_coverage"],
                "frame_clip_gap": gap,
                "selected_n": frame_metrics["selected_n"],
                "n_gt_clips": clip_metrics["n_gt_clips"],
                "n_gt_hit_coverage": clip_metrics["n_gt_hit_coverage"],
                "n_gt_hit_iou": clip_metrics["n_gt_hit_iou"],
                "n_fully_hit": miss_analysis["n_fully_hit"],
                "n_fully_missed": miss_analysis["n_fully_missed"],
                "n_sparse_miss": miss_analysis["n_sparse_miss"],
                "n_consecutive_miss": miss_analysis["n_consecutive_miss"],
                "n_boundary_miss": miss_analysis["n_boundary_miss"],
                "error": None,
            }
            all_results.append(row)

            if (seed + 1) % max(1, args.trials // 5) == 0 or seed == 0:
                print(f"  seed={seed}: frame_recall={frame_recall:.3f} "
                      f"clip_recall={clip_recall:.3f} gap={gap:+.3f} "
                      f"n_pred_clips={clip_metrics['n_pred_clips']}")

    # Save per-trial results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(outdir / "per_trial_results.csv", index=False)
    print(f"\nSaved per_trial_results.csv")

    # Summarize
    summary_rows = []
    for method_name in args.methods:
        method_df = results_df[results_df["method"] == method_name]
        valid_df = method_df[method_df["error"].isna()]

        if len(valid_df) == 0:
            summary_rows.append({"method": method_name, "trials": len(method_df), "errors": len(method_df)})
            continue

        summary_rows.append({
            "method": method_name,
            "trials": len(valid_df),
            "errors": len(method_df) - len(valid_df),
            "mean_frame_recall": float(valid_df["frame_recall"].mean()),
            "mean_clip_recall": float(valid_df["clip_recall_coverage"].mean()),
            "mean_clip_recall_iou": float(valid_df["clip_recall_iou"].mean()),
            "mean_frame_clip_gap": float(valid_df["frame_clip_gap"].mean()),
            "max_frame_clip_gap": float(valid_df["frame_clip_gap"].max()),
            "mean_mIoU": float(valid_df["mIoU"].mean()),
            "mean_coverage": float(valid_df["mean_coverage"].mean()),
            "mean_selected_n": float(valid_df["selected_n"].mean()),
            "mean_n_gt_hit": float(valid_df["n_gt_hit_coverage"].mean()),
            "mean_n_fully_hit": float(valid_df["n_fully_hit"].mean()),
            "mean_n_fully_missed": float(valid_df["n_fully_missed"].mean()),
            "mean_n_consecutive_miss": float(valid_df["n_consecutive_miss"].mean()),
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(outdir / "summary.csv", index=False)
    print("Saved summary.csv")

    # Print summary
    print("\n" + "=" * 80)
    print("FRAME-TO-CLIP GAP ANALYSIS")
    print("=" * 80)
    for _, row in summary_df.iterrows():
        if "mean_frame_recall" not in row:
            continue
        print(f"\n{row['method']}:")
        print(f"  Frame recall:      {row['mean_frame_recall']:.3f}")
        print(f"  Clip recall (cov): {row['mean_clip_recall']:.3f}")
        print(f"  Clip recall (IoU): {row.get('mean_clip_recall_iou', 'N/A')}")
        print(f"  Gap:               {row['mean_frame_clip_gap']:+.3f}")
        print(f"  Mean coverage:     {row.get('mean_coverage', 'N/A')}")
        print(f"  mIoU:              {row['mean_mIoU']:.3f}")
        print(f"  GT clips hit:      {row['mean_n_gt_hit']:.1f} / {config['n_gt_clips']}")
        print(f"  Fully missed:      {row['mean_n_fully_missed']:.1f}")
        print(f"  Consec misses:     {row['mean_n_consecutive_miss']:.1f}")


if __name__ == "__main__":
    main()
