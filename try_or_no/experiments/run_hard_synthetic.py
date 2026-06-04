"""
Hard synthetic benchmark for stress-testing clip reconstruction.

Tests propagation strategies under harder nonstationary perturbation regimes
designed to break nearest-neighbor interpolation.

Usage:
    python -m experiments.run_hard_synthetic \
        --sample-size 100 \
        --seeds 5 \
        --output-dir outputs/hard_synthetic
"""

import argparse
import csv
import json
import pathlib
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.data_interface import load_or_generate_dataset, VideoAnnotation
from pipeline.clip_gt import build_ground_truth_clips
from pipeline.hard_perturbation import (
    HardPerturbationConfig, perturb_video_hard, HARD_REGIMES, apply_oracle_noise,
)
from pipeline.propagation import PROPAGATION_STRATEGIES
from pipeline.allocation import uniform_allocation
from pipeline.metrics import (
    compute_hard_experiment_metrics, HardExperimentMetrics,
    compute_frame_metrics, compute_clip_metrics,
)


# Default parameter grid
TAU_VALUES = [10, 20, 30, 60]
BUDGET_VALUES = [0.05, 0.1, 0.2]
PROPAGATION_STRATS = [
    "strict_threshold_stitching",
    "nearest_neighbor_interpolation",
    "conservative_boundary_expansion",
    "gap_tolerant_merge",
    "risk_aware_gap_bridge",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Hard synthetic benchmark for clip reconstruction"
    )
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--K", type=int, default=3)
    parser.add_argument("--output-dir", type=str, default="outputs/hard_synthetic")
    parser.add_argument("--num-frames", type=int, default=300)
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: fewer tau/budget values")
    parser.add_argument("--oracle-noise", type=float, default=0.15,
                        help="Oracle noise rate (probability of wrong label)")
    return parser.parse_args()


def get_hard_config(regime: str, tau: int, oracle_noise_rate: float = 0.15) -> HardPerturbationConfig:
    """Get perturbation config for a given regime, tuned to be challenging.

    Oracle noise is only applied in regimes where the oracle itself is unreliable
    (regime_shift, mixed_hard). Other regimes have pure proxy/label noise.
    """
    config = HardPerturbationConfig(regime=regime)

    if regime == "regime_shift":
        config.regime_length = max(30, tau)
        config.fn_rate = 0.45
        config.fp_rate = 0.25
        config.transition_sharpness = 0.7
        # Oracle is unreliable in high-risk regimes
        config.oracle_noise_rate = oracle_noise_rate
        config.oracle_noise_regime_only = True

    elif regime == "long_gap":
        config.gap_lengths = [
            max(3, tau // 10),
            max(5, tau // 6),
            max(10, tau // 3),
            max(20, tau // 2),
            min(40, tau),
        ]
        config.gap_positions = ["interior", "boundary", "tau_critical"]
        # Oracle is reliable; only proxy has gaps
        config.oracle_noise_rate = 0.0

    elif regime == "close_merge":
        config.negative_gap_lengths = [
            max(2, tau // 15),
            max(5, tau // 6),
            max(10, tau // 3),
            max(15, tau // 2),
            tau,
            tau + 5,
        ]
        # Oracle is reliable; challenge is merge/split
        config.oracle_noise_rate = 0.0

    elif regime == "boundary_ambig":
        config.boundary_noise_width = max(5, tau // 3)
        config.boundary_score_fluctuation = 0.4
        # Oracle is reliable; challenge is boundary precision
        config.oracle_noise_rate = 0.0

    elif regime == "mixed_hard":
        config.regime_length = max(30, tau)
        config.fn_rate = 0.35
        config.fp_rate = 0.20
        config.transition_sharpness = 0.6
        config.boundary_noise_width = max(5, tau // 4)
        config.boundary_score_fluctuation = 0.3
        config.gap_lengths = [max(3, tau // 10), max(10, tau // 3), max(20, tau // 2)]
        # Oracle is moderately unreliable
        config.oracle_noise_rate = oracle_noise_rate * 0.7
        config.oracle_noise_regime_only = True

    return config


def run_single_combination(
    video: VideoAnnotation,
    regime: str,
    propagation_name: str,
    K: int,
    tau: int,
    budget: float,
    seed: int,
    vid_idx: int,
    oracle_noise_rate: float = 0.15,
) -> HardExperimentMetrics:
    """Run a single regime × propagation × tau × budget combination."""
    rng = np.random.default_rng(seed * 100000 + vid_idx * 1000 + hash(regime + propagation_name) % 1000)

    # Ground truth
    gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
    gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
    gt_frame_labels = (video.frame_counts() >= K).astype(bool)

    # Apply hard perturbation
    config = get_hard_config(regime, tau, oracle_noise_rate=oracle_noise_rate)
    perturbed = perturb_video_hard(video, K=K, tau=tau, config=config, rng=rng)

    perturbed_labels = perturbed["perturbed_labels"]

    # Create a PerturbedSequence-like object for allocation
    from pipeline.perturbation import PerturbedSequence
    perturbed_seq = PerturbedSequence(
        video_id=video.video_id,
        original_counts=perturbed["original_counts"],
        perturbed_counts=perturbed["perturbed_counts"],
        original_labels=perturbed["original_labels"],
        perturbed_labels=perturbed_labels,
        perturbed_frame_annotations=perturbed["perturbed_frame_annotations"],
        num_oracle_calls=perturbed["num_oracle_calls"],
    )

    # Use uniform allocation (allocation is secondary per factorial results)
    alloc_rng = np.random.default_rng(seed * 100000 + vid_idx * 1000)
    sampled_indices, alloc_labels = uniform_allocation(perturbed_seq, budget, alloc_rng)

    # Apply oracle noise: only in regimes where oracle is unreliable
    # This simulates unreliable human annotation in difficult conditions
    oracle_rng = np.random.default_rng(seed * 100000 + vid_idx * 1000 + hash(propagation_name) % 997)
    risk_mask = perturbed["info"].get("risk_mask", None)
    effective_oracle_noise = config.oracle_noise_rate
    sampled_indices, noisy_oracle_labels = apply_oracle_noise(
        gt_frame_labels, sampled_indices, oracle_rng,
        noise_rate=effective_oracle_noise,
        risk_mask=risk_mask if config.oracle_noise_regime_only else None,
    )

    # Apply propagation strategy using noisy oracle labels
    prop_fn = PROPAGATION_STRATEGIES[propagation_name]
    pred_frame_labels, pred_clips = prop_fn(
        noisy_oracle_labels, sampled_indices, tau, K=K
    )

    # Compute metrics
    metrics = compute_hard_experiment_metrics(
        video_id=video.video_id,
        method=propagation_name,
        regime=regime,
        tau=tau,
        budget=budget,
        seed=seed,
        gt_frame_labels=gt_frame_labels,
        pred_frame_labels=pred_frame_labels,
        gt_clips=gt_clip_ranges,
        pred_clips=pred_clips,
        oracle_calls=len(sampled_indices),
        total_frames=len(gt_frame_labels),
    )

    return metrics


def main():
    args = parse_args()
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tau_values = [10, 30, 60] if args.quick else TAU_VALUES
    budget_values = [0.1, 0.2] if args.quick else BUDGET_VALUES

    print("=" * 60)
    print("HARD SYNTHETIC BENCHMARK")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  sample_size={args.sample_size}, seeds={args.seeds}, K={args.K}")
    print(f"  regimes={HARD_REGIMES}")
    print(f"  propagation={PROPAGATION_STRATS}")
    print(f"  tau={tau_values}")
    print(f"  budget={budget_values}")
    print(f"  oracle_noise={args.oracle_noise}")
    print(f"  output_dir={output_dir}")

    total_combos = (len(HARD_REGIMES) * len(PROPAGATION_STRATS) *
                    len(tau_values) * len(budget_values))
    total_runs = total_combos * args.sample_size * args.seeds
    print(f"  total_combinations={total_combos}")
    print(f"  total_runs={total_runs}")
    print()

    all_metrics: List[HardExperimentMetrics] = []
    run_count = 0

    for seed_idx in range(args.seeds):
        seed = args.base_seed + seed_idx
        print(f"--- Seed {seed_idx + 1}/{args.seeds} (seed={seed}) ---")

        videos = load_or_generate_dataset(
            annotation_dir=None,
            sample_size=args.sample_size,
            num_frames=args.num_frames,
            seed=seed,
        )

        for vid_idx, video in enumerate(videos):
            if (vid_idx + 1) % 25 == 0 or vid_idx == 0:
                print(f"  Video {vid_idx + 1}/{len(videos)}")

            for regime in HARD_REGIMES:
                for prop_name in PROPAGATION_STRATS:
                    for tau in tau_values:
                        for budget in budget_values:
                            metrics = run_single_combination(
                                video=video,
                                regime=regime,
                                propagation_name=prop_name,
                                K=args.K,
                                tau=tau,
                                budget=budget,
                                seed=seed,
                                vid_idx=vid_idx,
                                oracle_noise_rate=args.oracle_noise,
                            )
                            all_metrics.append(metrics)
                            run_count += 1

    print(f"\nTotal runs completed: {run_count}")

    # Write outputs
    print("\nWriting outputs...")

    # 1. hard_metrics.csv (all raw data)
    hard_csv_path = output_dir / "hard_metrics.csv"
    write_hard_metrics_csv(all_metrics, str(hard_csv_path))
    print(f"  {hard_csv_path}")

    # 2. regime_summary.csv
    regime_csv_path = output_dir / "regime_summary.csv"
    write_regime_summary(all_metrics, str(regime_csv_path))
    print(f"  {regime_csv_path}")

    # 3. nn_stress_test.md
    nn_stress_path = output_dir / "nn_stress_test.md"
    write_nn_stress_test(all_metrics, PROPAGATION_STRATS, str(nn_stress_path))
    print(f"  {nn_stress_path}")

    # 4. report.md
    report_path = output_dir / "report.md"
    write_final_report(all_metrics, PROPAGATION_STRATS, tau_values, budget_values, str(report_path))
    print(f"  {report_path}")

    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)


def write_hard_metrics_csv(metrics: List[HardExperimentMetrics], path: str):
    """Write all metrics to CSV."""
    if not metrics:
        return
    fieldnames = list(metrics[0].to_dict().keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics:
            writer.writerow(m.to_dict())


def write_regime_summary(metrics: List[HardExperimentMetrics], path: str):
    """Write summary by regime × propagation."""
    # Group by (regime, propagation)
    groups: Dict[tuple, List[HardExperimentMetrics]] = {}
    for m in metrics:
        key = (m.regime, m.method)
        groups.setdefault(key, []).append(m)

    fieldnames = [
        "regime", "propagation", "n",
        "mean_clip_recall", "std_clip_recall",
        "mean_clip_precision", "std_clip_precision",
        "mean_iou", "std_iou",
        "mean_fragmentation", "std_fragmentation",
        "mean_false_merge", "mean_false_split",
        "mean_over_extension", "mean_under_coverage",
        "mean_frame_recall", "std_frame_recall",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for (regime, prop), mlist in sorted(groups.items()):
            n = len(mlist)
            row = {
                "regime": regime,
                "propagation": prop,
                "n": n,
                "mean_clip_recall": np.mean([m.clip_recall for m in mlist]),
                "std_clip_recall": np.std([m.clip_recall for m in mlist]),
                "mean_clip_precision": np.mean([m.clip_precision for m in mlist]),
                "std_clip_precision": np.std([m.clip_precision for m in mlist]),
                "mean_iou": np.mean([m.mean_iou for m in mlist]),
                "std_iou": np.std([m.mean_iou for m in mlist]),
                "mean_fragmentation": np.mean([m.fragmentation_rate for m in mlist]),
                "std_fragmentation": np.std([m.fragmentation_rate for m in mlist]),
                "mean_false_merge": np.mean([m.false_merge_count for m in mlist]),
                "mean_false_split": np.mean([m.false_split_count for m in mlist]),
                "mean_over_extension": np.mean([m.over_extension_length for m in mlist]),
                "mean_under_coverage": np.mean([m.under_coverage_length for m in mlist]),
                "mean_frame_recall": np.mean([m.frame_recall for m in mlist]),
                "std_frame_recall": np.std([m.frame_recall for m in mlist]),
            }
            writer.writerow(row)


def write_nn_stress_test(
    metrics: List[HardExperimentMetrics],
    prop_strats: List[str],
    path: str,
):
    """Write detailed NN stress test analysis."""
    lines = [
        "# Nearest-Neighbor Stress Test",
        "",
        "## Overview",
        "",
        "This report analyzes when and how nearest-neighbor interpolation fails",
        "under harder nonstationary perturbation regimes.",
        "",
    ]

    # Group by (regime, propagation)
    groups: Dict[tuple, List[HardExperimentMetrics]] = {}
    for m in metrics:
        key = (m.regime, m.method)
        groups.setdefault(key, []).append(m)

    # Compute NN stats per regime
    nn_by_regime: Dict[str, List[HardExperimentMetrics]] = {}
    for m in metrics:
        if m.method == "nearest_neighbor_interpolation":
            nn_by_regime.setdefault(m.regime, []).append(m)

    lines.extend([
        "## NN Performance by Regime",
        "",
        "| Regime | Clip Recall | Clip Prec | IoU | Frag | False Merge | False Split |",
        "|--------|-------------|-----------|-----|------|-------------|-------------|",
    ])

    for regime in HARD_REGIMES:
        mlist = nn_by_regime.get(regime, [])
        if not mlist:
            continue
        lines.append(
            f"| {regime} | "
            f"{np.mean([m.clip_recall for m in mlist]):.3f} | "
            f"{np.mean([m.clip_precision for m in mlist]):.3f} | "
            f"{np.mean([m.mean_iou for m in mlist]):.3f} | "
            f"{np.mean([m.fragmentation_rate for m in mlist]):.3f} | "
            f"{np.mean([m.false_merge_count for m in mlist]):.2f} | "
            f"{np.mean([m.false_split_count for m in mlist]):.2f} |"
        )

    # Identify failure cases
    lines.extend([
        "",
        "## Failure Analysis",
        "",
        "Cases where NN clip recall < 0.8:",
        "",
    ])

    nn_failures = [m for m in metrics if m.method == "nearest_neighbor_interpolation" and m.clip_recall < 0.8]
    if nn_failures:
        lines.append(f"Total failure cases: {len(nn_failures)} / {len([m for m in metrics if m.method == 'nearest_neighbor_interpolation'])}")
        lines.append("")

        # Group failures by regime
        failure_by_regime: Dict[str, int] = {}
        total_by_regime: Dict[str, int] = {}
        for m in metrics:
            if m.method == "nearest_neighbor_interpolation":
                total_by_regime[m.regime] = total_by_regime.get(m.regime, 0) + 1
                if m.clip_recall < 0.8:
                    failure_by_regime[m.regime] = failure_by_regime.get(m.regime, 0) + 1

        lines.append("| Regime | Failures | Total | Failure Rate |")
        lines.append("|--------|----------|-------|--------------|")
        for regime in HARD_REGIMES:
            fails = failure_by_regime.get(regime, 0)
            total = total_by_regime.get(regime, 0)
            rate = fails / total if total > 0 else 0
            lines.append(f"| {regime} | {fails} | {total} | {rate:.3f} |")

        # Analyze what metric fails most
        lines.extend([
            "",
            "### Failure Mode Distribution",
            "",
            "For NN failures (clip recall < 0.8), which metrics are worst:",
            "",
        ])

        # Check which metric is most degraded
        recall_failures = [m for m in nn_failures if m.clip_recall < 0.8]
        precision_failures = [m for m in nn_failures if m.clip_precision < 0.8]
        iou_failures = [m for m in nn_failures if m.mean_iou < 0.6]
        merge_failures = [m for m in nn_failures if m.false_merge_count > 0.5]
        split_failures = [m for m in nn_failures if m.false_split_count > 0.5]

        lines.append(f"- Recall failures (< 0.8): {len(recall_failures)}")
        lines.append(f"- Precision failures (< 0.8): {len(precision_failures)}")
        lines.append(f"- IoU failures (< 0.6): {len(iou_failures)}")
        lines.append(f"- False merge issues (> 0.5): {len(merge_failures)}")
        lines.append(f"- False split issues (> 0.5): {len(split_failures)}")
    else:
        lines.append("**No failure cases found.** NN clip recall >= 0.8 in all conditions.")

    # Per-regime, per-tau analysis
    lines.extend([
        "",
        "## NN Performance: Regime × Tau",
        "",
        "| Regime | Tau | Clip Recall | Clip Prec | IoU | Frag |",
        "|--------|-----|-------------|-----------|-----|------|",
    ])

    for regime in HARD_REGIMES:
        for tau in sorted(set(m.tau for m in metrics if m.method == "nearest_neighbor_interpolation")):
            mlist = [m for m in metrics
                     if m.method == "nearest_neighbor_interpolation"
                     and m.regime == regime and m.tau == tau]
            if not mlist:
                continue
            lines.append(
                f"| {regime} | {tau} | "
                f"{np.mean([m.clip_recall for m in mlist]):.3f} | "
                f"{np.mean([m.clip_precision for m in mlist]):.3f} | "
                f"{np.mean([m.mean_iou for m in mlist]):.3f} | "
                f"{np.mean([m.fragmentation_rate for m in mlist]):.3f} |"
            )

    report = "\n".join(lines)
    with open(path, "w") as f:
        f.write(report)


def write_final_report(
    metrics: List[HardExperimentMetrics],
    prop_strats: List[str],
    tau_values: List[int],
    budget_values: List[float],
    path: str,
):
    """Write final comprehensive report."""
    lines = [
        "# Hard Synthetic Benchmark Report",
        "",
        "## Research Question",
        "",
        "Was the previous synthetic benchmark too easy? Does nearest-neighbor",
        "still dominate under harder nonstationary perturbation regimes?",
        "",
        "## Configuration",
        "",
        f"- Regimes: {HARD_REGIMES}",
        f"- Propagation strategies: {prop_strats}",
        f"- Tau values: {tau_values}",
        f"- Budget values: {budget_values}",
        f"- Total observations: {len(metrics)}",
        "",
    ]

    # Overall propagation comparison
    lines.extend([
        "## 1. Propagation Strategy Comparison (All Regimes)",
        "",
        "| Propagation | Clip Recall | Clip Prec | IoU | Frag | False Merge | False Split |",
        "|-------------|-------------|-----------|-----|------|-------------|-------------|",
    ])

    for prop in prop_strats:
        mlist = [m for m in metrics if m.method == prop]
        if not mlist:
            continue
        lines.append(
            f"| {prop} | "
            f"{np.mean([m.clip_recall for m in mlist]):.3f} | "
            f"{np.mean([m.clip_precision for m in mlist]):.3f} | "
            f"{np.mean([m.mean_iou for m in mlist]):.3f} | "
            f"{np.mean([m.fragmentation_rate for m in mlist]):.3f} | "
            f"{np.mean([m.false_merge_count for m in mlist]):.2f} | "
            f"{np.mean([m.false_split_count for m in mlist]):.2f} |"
        )

    # Per-regime analysis
    lines.extend([
        "",
        "## 2. Per-Regime Analysis",
        "",
    ])

    for regime in HARD_REGIMES:
        lines.extend([
            f"### Regime: {regime}",
            "",
            "| Propagation | Clip Recall | Clip Prec | IoU | Frag |",
            "|-------------|-------------|-----------|-----|------|",
        ])

        for prop in prop_strats:
            mlist = [m for m in metrics if m.method == prop and m.regime == regime]
            if not mlist:
                continue
            lines.append(
                f"| {prop} | "
                f"{np.mean([m.clip_recall for m in mlist]):.3f} | "
                f"{np.mean([m.clip_precision for m in mlist]):.3f} | "
                f"{np.mean([m.mean_iou for m in mlist]):.3f} | "
                f"{np.mean([m.fragmentation_rate for m in mlist]):.3f} |"
            )
        lines.append("")

    # Answer the key questions
    lines.extend([
        "## 3. Key Questions",
        "",
    ])

    # Q1: Was previous benchmark too easy?
    nn_metrics = [m for m in metrics if m.method == "nearest_neighbor_interpolation"]
    nn_mean_recall = np.mean([m.clip_recall for m in nn_metrics]) if nn_metrics else 0
    nn_recall_below_90 = sum(1 for m in nn_metrics if m.clip_recall < 0.9) / len(nn_metrics) if nn_metrics else 0

    lines.extend([
        "### Q1: Was the previous synthetic benchmark too easy?",
        "",
        f"- NN mean clip recall across all hard regimes: {nn_mean_recall:.3f}",
        f"- Fraction of cases where NN recall < 0.9: {nn_recall_below_90:.3f}",
        "",
    ])

    if nn_mean_recall > 0.95:
        lines.append("**Answer: Still too easy.** NN maintains >95% recall even under hard regimes.")
    elif nn_mean_recall > 0.85:
        lines.append("**Answer: Somewhat harder.** NN recall drops but remains >85%.")
    else:
        lines.append("**Answer: Yes, significantly harder.** NN recall drops below 85%.")

    # Q2: Does NN still dominate?
    lines.extend([
        "",
        "### Q2: Does nearest-neighbor still dominate?",
        "",
    ])

    # Compute rank of NN per regime
    for regime in HARD_REGIMES:
        regime_metrics = [m for m in metrics if m.regime == regime]
        prop_recalls: Dict[str, List[float]] = {}
        for m in regime_metrics:
            prop_recalls.setdefault(m.method, []).append(m.clip_recall)

        prop_means = {p: np.mean(v) for p, v in prop_recalls.items()}
        sorted_props = sorted(prop_means.items(), key=lambda x: x[1], reverse=True)
        nn_rank = next(i + 1 for i, (p, _) in enumerate(sorted_props) if p == "nearest_neighbor_interpolation")

        lines.append(f"- **{regime}**: NN rank = {nn_rank}/{len(sorted_props)}, "
                     f"NN recall = {prop_means.get('nearest_neighbor_interpolation', 0):.3f}, "
                     f"Best = {sorted_props[0][0]} ({sorted_props[0][1]:.3f})")

    # Q3: Which failure mode is most relevant?
    lines.extend([
        "",
        "### Q3: Which failure mode is most relevant?",
        "",
    ])

    nn_failures = [m for m in nn_metrics if m.clip_recall < 0.85]
    if nn_failures:
        # Analyze what fails
        avg_recall = np.mean([m.clip_recall for m in nn_failures])
        avg_precision = np.mean([m.clip_precision for m in nn_failures])
        avg_iou = np.mean([m.mean_iou for m in nn_failures])
        avg_frag = np.mean([m.fragmentation_rate for m in nn_failures])
        avg_merge = np.mean([m.false_merge_count for m in nn_failures])
        avg_split = np.mean([m.false_split_count for m in nn_failures])

        lines.extend([
            f"For NN failures (recall < 0.85, n={len(nn_failures)}):",
            f"- Mean clip recall: {avg_recall:.3f}",
            f"- Mean clip precision: {avg_precision:.3f}",
            f"- Mean IoU: {avg_iou:.3f}",
            f"- Mean fragmentation: {avg_frag:.3f}",
            f"- Mean false merges: {avg_merge:.3f}",
            f"- Mean false splits: {avg_split:.3f}",
            "",
        ])

        # Determine primary failure mode
        if avg_recall < avg_precision:
            lines.append("**Primary failure mode: Recall** (missing clips)")
        elif avg_merge > 0.5:
            lines.append("**Primary failure mode: False merges** (merging separate clips)")
        elif avg_frag > 0.5:
            lines.append("**Primary failure mode: Fragmentation** (splitting single clips)")
        elif avg_iou < 0.6:
            lines.append("**Primary failure mode: IoU loss** (boundary drift)")
        else:
            lines.append("**Primary failure mode: Mixed**")
    else:
        lines.append("No significant NN failures found.")

    # Q4: Is there a research gap?
    lines.extend([
        "",
        "### Q4: Is there still a research gap in robust clip reconstruction?",
        "",
    ])

    # Check if any regime clearly breaks NN
    nn_breaking_regimes = []
    for regime in HARD_REGIMES:
        regime_nn = [m for m in nn_metrics if m.regime == regime]
        if regime_nn and np.mean([m.clip_recall for m in regime_nn]) < 0.85:
            nn_breaking_regimes.append(regime)

    if nn_breaking_regimes:
        lines.extend([
            f"**Yes, there is a research gap.** NN fails significantly on: {nn_breaking_regimes}",
            "",
            "These regimes create conditions where simple nearest-neighbor interpolation",
            "cannot correctly reconstruct clips. A robust method would need to:",
            "- Handle nonstationary proxy reliability",
            "- Detect and bridge visibility gaps without over-merging",
            "- Maintain boundary precision under ambiguity",
        ])
    else:
        lines.extend([
            "**Unclear.** NN maintains reasonable performance across all hard regimes.",
            "The synthetic perturbations may still not be realistic enough.",
            "",
            "Options:",
            "1. Design even harder perturbations",
            "2. Move to real data (BDD100K)",
            "3. Pivot to a different research angle",
        ])

    # Q5: Recommendation
    lines.extend([
        "",
        "### Q5: Should the project continue to real BDD100K data, pivot to semantics, or stop?",
        "",
    ])

    if nn_mean_recall > 0.95 and not nn_breaking_regimes:
        lines.extend([
            "**Recommendation: Pivot or stop.**",
            "",
            "The synthetic perturbation approach has not produced conditions where",
            "simple methods fail convincingly. Options:",
            "1. **Pivot to semantics**: Focus on query types beyond count(vehicle) >= K",
            "2. **Move to real data**: Use BDD100K dashcam videos with real detection noise",
            "3. **Stop**: If neither pivot produces a clear gap, reconsider the research direction",
        ])
    elif nn_mean_recall > 0.85:
        lines.extend([
            "**Recommendation: Move to real data.**",
            "",
            "Some failure modes are emerging but synthetic perturbation is limited.",
            "Real moving-camera data (BDD100K) would provide authentic nonstationary noise.",
        ])
    else:
        lines.extend([
            "**Recommendation: Continue development.**",
            "",
            "Clear failure modes have been identified. Next steps:",
            "1. Develop robust reconstruction methods targeting identified failure modes",
            "2. Validate on real data",
        ])

    # Appendix: detailed stats
    lines.extend([
        "",
        "## Appendix: Detailed Statistics",
        "",
        "### By Regime × Tau × Budget",
        "",
        "| Regime | Tau | Budget | NN Recall | NN Prec | NN IoU | NN Frag |",
        "|--------|-----|--------|-----------|---------|--------|---------|",
    ])

    for regime in HARD_REGIMES:
        for tau in sorted(set(m.tau for m in nn_metrics)):
            for budget in sorted(set(m.budget for m in nn_metrics)):
                mlist = [m for m in nn_metrics
                         if m.regime == regime and m.tau == tau and m.budget == budget]
                if not mlist:
                    continue
                lines.append(
                    f"| {regime} | {tau} | {budget} | "
                    f"{np.mean([m.clip_recall for m in mlist]):.3f} | "
                    f"{np.mean([m.clip_precision for m in mlist]):.3f} | "
                    f"{np.mean([m.mean_iou for m in mlist]):.3f} | "
                    f"{np.mean([m.fragmentation_rate for m in mlist]):.3f} |"
                )

    report = "\n".join(lines)
    with open(path, "w") as f:
        f.write(report)


if __name__ == "__main__":
    main()
