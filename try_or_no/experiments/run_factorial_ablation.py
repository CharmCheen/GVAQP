"""
Factorial ablation experiment: allocation × propagation strategies.

Determines whether robustness in relevant clip query is driven by:
- oracle allocation strategy (which frames to query)
- propagation/clip reconstruction strategy (how to fill gaps)

Usage:
    python -m experiments.run_factorial_ablation \
        --sample-size 100 \
        --K 3 \
        --tau 30 \
        --budget 0.1 \
        --seeds 5 \
        --output-dir outputs/factorial
"""

import argparse
import json
import pathlib
import sys
from typing import Dict, List, Any

import numpy as np

# Add parent to path for module imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.data_interface import load_or_generate_dataset, VideoAnnotation
from pipeline.clip_gt import build_ground_truth_clips
from pipeline.perturbation import PerturbationConfig, perturb_video
from pipeline.allocation import ALLOCATION_STRATEGIES
from pipeline.propagation import PROPAGATION_STRATEGIES
from pipeline.metrics import compute_experiment_metrics, ExperimentMetrics


def parse_args():
    parser = argparse.ArgumentParser(
        description="Factorial ablation: allocation × propagation"
    )
    parser.add_argument("--sample-size", type=int, default=100, help="Number of videos")
    parser.add_argument("--K", type=int, default=3, help="Min vehicle count threshold")
    parser.add_argument("--tau", type=int, default=30, help="Min frames for a clip")
    parser.add_argument("--budget", type=float, default=0.1, help="Oracle budget fraction")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds")
    parser.add_argument("--output-dir", type=str, default="outputs/factorial", help="Output directory")
    parser.add_argument("--num-frames", type=int, default=300, help="Frames per synthetic video")
    parser.add_argument("--base-seed", type=int, default=42, help="Base random seed")
    return parser.parse_args()


def run_factorial_combination(
    video: VideoAnnotation,
    allocation_name: str,
    propagation_name: str,
    K: int,
    tau: int,
    budget: float,
    perturb_config: PerturbationConfig,
    rng: np.random.Generator,
) -> ExperimentMetrics:
    """Run a single allocation × propagation combination on one video."""
    # Build ground truth clips
    gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
    gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
    gt_frame_labels = (video.frame_counts() >= K).astype(bool)

    # Apply perturbation
    perturbed = perturb_video(
        video, K=K, config=perturb_config, rng=rng, boundary_clips=gt_clip_ranges
    )

    # Apply allocation strategy
    alloc_fn = ALLOCATION_STRATEGIES[allocation_name]
    if allocation_name == "hidden_risk":
        sampled_indices, alloc_labels = alloc_fn(perturbed, budget, rng, K=K)
    else:
        sampled_indices, alloc_labels = alloc_fn(perturbed, budget, rng)

    # Apply propagation strategy
    prop_fn = PROPAGATION_STRATEGIES[propagation_name]
    pred_frame_labels, pred_clips = prop_fn(
        alloc_labels, sampled_indices, tau, K=K
    )

    # Compute metrics
    metrics = compute_experiment_metrics(
        video_id=video.video_id,
        method=f"{allocation_name}__{propagation_name}",
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

    print("=" * 60)
    print("FACTORIAL ABLATION: allocation × propagation")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  sample_size={args.sample_size}, K={args.K}, tau={args.tau}")
    print(f"  budget={args.budget}, seeds={args.seeds}")
    print(f"  output_dir={output_dir}")
    print()

    # List strategies
    alloc_names = list(ALLOCATION_STRATEGIES.keys())
    prop_names = list(PROPAGATION_STRATEGIES.keys())
    print(f"Allocation strategies ({len(alloc_names)}): {alloc_names}")
    print(f"Propagation strategies ({len(prop_names)}): {prop_names}")
    print(f"Total combinations: {len(alloc_names) * len(prop_names)}")
    print()

    # Collect all metrics across seeds
    all_metrics: List[ExperimentMetrics] = []
    total_runs = 0

    for seed_idx in range(args.seeds):
        seed = args.base_seed + seed_idx
        print(f"--- Seed {seed_idx + 1}/{args.seeds} (seed={seed}) ---")

        # Generate dataset for this seed
        videos = load_or_generate_dataset(
            annotation_dir=None,
            sample_size=args.sample_size,
            num_frames=args.num_frames,
            seed=seed,
        )

        perturb_config = PerturbationConfig()
        video_rng = np.random.default_rng(seed)

        for vid_idx, video in enumerate(videos):
            if (vid_idx + 1) % 20 == 0 or vid_idx == 0:
                print(f"  Video {vid_idx + 1}/{len(videos)}")

            for alloc_name in alloc_names:
                for prop_name in prop_names:
                    # Use different rng for each combination to ensure independence
                    combo_rng = np.random.default_rng(seed * 10000 + vid_idx * 100 + hash(alloc_name + prop_name) % 1000)

                    metrics = run_factorial_combination(
                        video=video,
                        allocation_name=alloc_name,
                        propagation_name=prop_name,
                        K=args.K,
                        tau=args.tau,
                        budget=args.budget,
                        perturb_config=perturb_config,
                        rng=combo_rng,
                    )

                    # Add seed info
                    metrics_dict = metrics.to_dict()
                    metrics_dict["seed"] = seed
                    metrics_dict["seed_idx"] = seed_idx

                    all_metrics.append(metrics)
                    total_runs += 1

    print(f"\nTotal runs: {total_runs}")
    print(f"Total metrics collected: {len(all_metrics)}")

    # Write outputs
    print("\nWriting outputs...")

    # 1. factorial_metrics.csv (all raw data)
    factorial_csv_path = output_dir / "factorial_metrics.csv"
    _write_factorial_csv(all_metrics, str(factorial_csv_path))
    print(f"  {factorial_csv_path}")

    # 2. allocation_summary.csv (averaged over propagation and seeds)
    alloc_summary_path = output_dir / "allocation_summary.csv"
    _write_allocation_summary(all_metrics, alloc_names, str(alloc_summary_path))
    print(f"  {alloc_summary_path}")

    # 3. propagation_summary.csv (averaged over allocation and seeds)
    prop_summary_path = output_dir / "propagation_summary.csv"
    _write_propagation_summary(all_metrics, prop_names, str(prop_summary_path))
    print(f"  {prop_summary_path}")

    # 4. best_combinations.csv (top combinations by clip recall)
    best_combos_path = output_dir / "best_combinations.csv"
    _write_best_combinations(all_metrics, str(best_combos_path))
    print(f"  {best_combos_path}")

    # 5. report.md
    report_path = output_dir / "report.md"
    report = generate_factorial_report(
        all_metrics, alloc_names, prop_names, args, str(report_path)
    )
    print(f"  {report_path}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    _print_summary(all_metrics, alloc_names, prop_names)


def _write_factorial_csv(metrics: List[ExperimentMetrics], path: str):
    """Write all metrics to CSV with additional columns."""
    import csv

    if not metrics:
        return

    fieldnames = list(metrics[0].to_dict().keys())
    fieldnames.extend(["seed", "seed_idx", "allocation", "propagation"])

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics:
            row = m.to_dict()
            # Parse allocation and propagation from method name
            parts = m.method.split("__")
            row["allocation"] = parts[0] if len(parts) > 0 else ""
            row["propagation"] = parts[1] if len(parts) > 1 else ""
            # Add seed info if available (from the dict version)
            row["seed"] = ""
            row["seed_idx"] = ""
            writer.writerow(row)


def _write_allocation_summary(
    metrics: List[ExperimentMetrics],
    alloc_names: List[str],
    path: str,
):
    """Write allocation summary averaged over propagation strategies."""
    import csv

    # Group by allocation strategy
    alloc_metrics: Dict[str, List[ExperimentMetrics]] = {}
    for m in metrics:
        parts = m.method.split("__")
        alloc_name = parts[0] if len(parts) > 0 else "unknown"
        alloc_metrics.setdefault(alloc_name, []).append(m)

    fieldnames = [
        "allocation", "n_observations",
        "mean_frame_recall", "std_frame_recall",
        "mean_clip_recall", "std_clip_recall",
        "mean_clip_precision", "std_clip_precision",
        "mean_iou", "std_iou",
        "mean_fragmentation", "std_fragmentation",
        "mean_oracle_calls", "std_oracle_calls",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for alloc_name in alloc_names:
            alloc_list = alloc_metrics.get(alloc_name, [])
            if not alloc_list:
                continue

            n = len(alloc_list)
            row = {
                "allocation": alloc_name,
                "n_observations": n,
                "mean_frame_recall": np.mean([m.frame_recall for m in alloc_list]),
                "std_frame_recall": np.std([m.frame_recall for m in alloc_list]),
                "mean_clip_recall": np.mean([m.clip_recall for m in alloc_list]),
                "std_clip_recall": np.std([m.clip_recall for m in alloc_list]),
                "mean_clip_precision": np.mean([m.clip_precision for m in alloc_list]),
                "std_clip_precision": np.std([m.clip_precision for m in alloc_list]),
                "mean_iou": np.mean([m.mean_iou for m in alloc_list]),
                "std_iou": np.std([m.mean_iou for m in alloc_list]),
                "mean_fragmentation": np.mean([m.fragmentation_rate for m in alloc_list]),
                "std_fragmentation": np.std([m.fragmentation_rate for m in alloc_list]),
                "mean_oracle_calls": np.mean([m.oracle_calls for m in alloc_list]),
                "std_oracle_calls": np.std([m.oracle_calls for m in alloc_list]),
            }
            writer.writerow(row)


def _write_propagation_summary(
    metrics: List[ExperimentMetrics],
    prop_names: List[str],
    path: str,
):
    """Write propagation summary averaged over allocation strategies."""
    import csv

    # Group by propagation strategy
    prop_metrics: Dict[str, List[ExperimentMetrics]] = {}
    for m in metrics:
        parts = m.method.split("__")
        prop_name = parts[1] if len(parts) > 1 else "unknown"
        prop_metrics.setdefault(prop_name, []).append(m)

    fieldnames = [
        "propagation", "n_observations",
        "mean_frame_recall", "std_frame_recall",
        "mean_clip_recall", "std_clip_recall",
        "mean_clip_precision", "std_clip_precision",
        "mean_iou", "std_iou",
        "mean_fragmentation", "std_fragmentation",
        "mean_oracle_calls", "std_oracle_calls",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for prop_name in prop_names:
            prop_list = prop_metrics.get(prop_name, [])
            if not prop_list:
                continue

            n = len(prop_list)
            row = {
                "propagation": prop_name,
                "n_observations": n,
                "mean_frame_recall": np.mean([m.frame_recall for m in prop_list]),
                "std_frame_recall": np.std([m.frame_recall for m in prop_list]),
                "mean_clip_recall": np.mean([m.clip_recall for m in prop_list]),
                "std_clip_recall": np.std([m.clip_recall for m in prop_list]),
                "mean_clip_precision": np.mean([m.clip_precision for m in prop_list]),
                "std_clip_precision": np.std([m.clip_precision for m in prop_list]),
                "mean_iou": np.mean([m.mean_iou for m in prop_list]),
                "std_iou": np.std([m.mean_iou for m in prop_list]),
                "mean_fragmentation": np.mean([m.fragmentation_rate for m in prop_list]),
                "std_fragmentation": np.std([m.fragmentation_rate for m in prop_list]),
                "mean_oracle_calls": np.mean([m.oracle_calls for m in prop_list]),
                "std_oracle_calls": np.std([m.oracle_calls for m in prop_list]),
            }
            writer.writerow(row)


def _write_best_combinations(metrics: List[ExperimentMetrics], path: str):
    """Write top 10 combinations by clip recall."""
    import csv

    # Group by combination
    combo_metrics: Dict[str, List[ExperimentMetrics]] = {}
    for m in metrics:
        combo_metrics.setdefault(m.method, []).append(m)

    # Compute average clip recall per combo
    combo_avgs = []
    for method, mlist in combo_metrics.items():
        avg_clip_recall = np.mean([m.clip_recall for m in mlist])
        avg_fragmentation = np.mean([m.fragmentation_rate for m in mlist])
        avg_iou = np.mean([m.mean_iou for m in mlist])
        combo_avgs.append((method, avg_clip_recall, avg_fragmentation, avg_iou))

    # Sort by clip recall descending
    combo_avgs.sort(key=lambda x: x[1], reverse=True)

    fieldnames = ["rank", "combination", "mean_clip_recall", "mean_fragmentation", "mean_iou"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rank, (method, clip_recall, frag, iou) in enumerate(combo_avgs[:15], 1):
            writer.writerow({
                "rank": rank,
                "combination": method,
                "mean_clip_recall": f"{clip_recall:.4f}",
                "mean_fragmentation": f"{frag:.4f}",
                "mean_iou": f"{iou:.4f}",
            })


def _print_summary(
    metrics: List[ExperimentMetrics],
    alloc_names: List[str],
    prop_names: List[str],
):
    """Print summary table to console."""
    # Group by combination
    combo_metrics: Dict[str, List[ExperimentMetrics]] = {}
    for m in metrics:
        combo_metrics.setdefault(m.method, []).append(m)

    print("\nTop 10 combinations by clip recall:")
    print(f"{'Combination':<50} {'ClipRecall':>10} {'Fragment':>10} {'IoU':>8}")
    print("-" * 80)

    combo_avgs = []
    for method, mlist in combo_metrics.items():
        avg_clip_recall = np.mean([m.clip_recall for m in mlist])
        avg_fragmentation = np.mean([m.fragmentation_rate for m in mlist])
        avg_iou = np.mean([m.mean_iou for m in mlist])
        combo_avgs.append((method, avg_clip_recall, avg_fragmentation, avg_iou))

    combo_avgs.sort(key=lambda x: x[1], reverse=True)

    for method, clip_recall, frag, iou in combo_avgs[:10]:
        print(f"{method:<50} {clip_recall:>10.4f} {frag:>10.4f} {iou:>8.4f}")

    # Print allocation effect
    print("\n\nAllocation effect (averaged over propagation):")
    print(f"{'Allocation':<25} {'ClipRecall':>10} {'FrameRecall':>11} {'Fragment':>10}")
    print("-" * 60)

    alloc_metrics: Dict[str, List[float]] = {}
    for m in metrics:
        parts = m.method.split("__")
        alloc_name = parts[0] if len(parts) > 0 else "unknown"
        alloc_metrics.setdefault(alloc_name, []).append(m.clip_recall)

    for alloc_name in alloc_names:
        recalls = alloc_metrics.get(alloc_name, [])
        if recalls:
            print(f"{alloc_name:<25} {np.mean(recalls):>10.4f}")


def generate_factorial_report(
    metrics: List[ExperimentMetrics],
    alloc_names: List[str],
    prop_names: List[str],
    args: argparse.Namespace,
    output_path: str,
) -> str:
    """Generate comprehensive factorial ablation report."""
    lines = [
        "# Factorial Ablation Report: Allocation × Propagation",
        "",
        "## Research Question",
        "",
        "In relevant clip query processing, what drives robustness under synthetic perturbation?",
        "- **Allocation strategy**: which frames to query with the oracle",
        "- **Propagation strategy**: how to reconstruct clip labels from sparse oracle queries",
        "",
        "## Configuration",
        "",
        f"- Sample size: {args.sample_size} videos per seed",
        f"- Seeds: {args.seeds}",
        f"- K (min vehicles): {args.K}",
        f"- tau (min frames): {args.tau}",
        f"- Budget: {args.budget}",
        f"- Total combinations: {len(alloc_names)} × {len(prop_names)} = {len(alloc_names) * len(prop_names)}",
        "",
        "## Summary of Findings",
        "",
    ]

    # Group by combination
    combo_metrics: Dict[str, List[ExperimentMetrics]] = {}
    for m in metrics:
        combo_metrics.setdefault(m.method, []).append(m)

    # Compute averages for all combos
    combo_avgs = {}
    for method, mlist in combo_metrics.items():
        combo_avgs[method] = {
            "clip_recall": np.mean([m.clip_recall for m in mlist]),
            "frame_recall": np.mean([m.frame_recall for m in mlist]),
            "clip_precision": np.mean([m.clip_precision for m in mlist]),
            "fragmentation": np.mean([m.fragmentation_rate for m in mlist]),
            "mean_iou": np.mean([m.mean_iou for m in mlist]),
            "oracle_calls": np.mean([m.oracle_calls for m in mlist]),
        }

    # Find best and worst
    best_combo = max(combo_avgs.items(), key=lambda x: x[1]["clip_recall"])
    worst_combo = min(combo_avgs.items(), key=lambda x: x[1]["clip_recall"])

    lines.extend([
        f"- **Best combination**: {best_combo[0]} (clip recall = {best_combo[1]['clip_recall']:.4f})",
        f"- **Worst combination**: {worst_combo[0]} (clip recall = {worst_combo[1]['clip_recall']:.4f})",
        f"- **Range**: {best_combo[1]['clip_recall'] - worst_combo[1]['clip_recall']:.4f}",
        "",
    ])

    # Question 1: Allocation effect
    lines.extend([
        "## Q1: How large is the gap between different propagation strategies (allocation fixed)?",
        "",
        "For each allocation strategy, we compare the best and worst propagation:",
        "",
        "| Allocation | Best Propagation | Best ClipRecall | Worst Propagation | Worst ClipRecall | Gap |",
        "|------------|------------------|-----------------|-------------------|------------------|-----|",
    ])

    for alloc_name in alloc_names:
        alloc_combos = {k: v for k, v in combo_avgs.items() if k.startswith(alloc_name + "__")}
        if not alloc_combos:
            continue

        best_prop = max(alloc_combos.items(), key=lambda x: x[1]["clip_recall"])
        worst_prop = min(alloc_combos.items(), key=lambda x: x[1]["clip_recall"])

        best_prop_name = best_prop[0].split("__")[1] if "__" in best_prop[0] else best_prop[0]
        worst_prop_name = worst_prop[0].split("__")[1] if "__" in worst_prop[0] else worst_prop[0]
        gap = best_prop[1]["clip_recall"] - worst_prop[1]["clip_recall"]

        lines.append(
            f"| {alloc_name} | {best_prop_name} | {best_prop[1]['clip_recall']:.4f} | "
            f"{worst_prop_name} | {worst_prop[1]['clip_recall']:.4f} | {gap:.4f} |"
        )

    # Question 2: Propagation effect
    lines.extend([
        "",
        "## Q2: How large is the gap between different allocation strategies (propagation fixed)?",
        "",
        "For each propagation strategy, we compare the best and worst allocation:",
        "",
        "| Propagation | Best Allocation | Best ClipRecall | Worst Allocation | Worst ClipRecall | Gap |",
        "|-------------|-----------------|-----------------|------------------|------------------|-----|",
    ])

    for prop_name in prop_names:
        prop_combos = {k: v for k, v in combo_avgs.items() if k.endswith("__" + prop_name)}
        if not prop_combos:
            continue

        best_alloc = max(prop_combos.items(), key=lambda x: x[1]["clip_recall"])
        worst_alloc = min(prop_combos.items(), key=lambda x: x[1]["clip_recall"])

        best_alloc_name = best_alloc[0].split("__")[0] if "__" in best_alloc[0] else best_alloc[0]
        worst_alloc_name = worst_alloc[0].split("__")[0] if "__" in worst_alloc[0] else worst_alloc[0]
        gap = best_alloc[1]["clip_recall"] - worst_alloc[1]["clip_recall"]

        lines.append(
            f"| {prop_name} | {best_alloc_name} | {best_alloc[1]['clip_recall']:.4f} | "
            f"{worst_alloc_name} | {worst_alloc[1]['clip_recall']:.4f} | {gap:.4f} |"
        )

    # Question 3: hidden_risk analysis
    lines.extend([
        "",
        "## Q3: Does hidden_risk allocation outperform uniform under the same propagation?",
        "",
        "| Propagation | uniform ClipRecall | hidden_risk ClipRecall | Difference | hidden_risk better? |",
        "|-------------|-------------------|----------------------|------------|---------------------|",
    ])

    for prop_name in prop_names:
        uniform_key = f"uniform__{prop_name}"
        hidden_key = f"hidden_risk__{prop_name}"

        uniform_recall = combo_avgs.get(uniform_key, {}).get("clip_recall", None)
        hidden_recall = combo_avgs.get(hidden_key, {}).get("clip_recall", None)

        if uniform_recall is not None and hidden_recall is not None:
            diff = hidden_recall - uniform_recall
            better = "Yes" if diff > 0.01 else ("No" if diff < -0.01 else "Similar")
            lines.append(
                f"| {prop_name} | {uniform_recall:.4f} | {hidden_recall:.4f} | "
                f"{diff:+.4f} | {better} |"
            )
        else:
            lines.append(f"| {prop_name} | N/A | N/A | N/A | N/A |")

    # Question 4: nearest_neighbor analysis
    lines.extend([
        "",
        "## Q4: Is nearest_neighbor_interpolation universally strong?",
        "",
        "Compare nearest_neighbor vs other propagation for each allocation:",
        "",
        "| Allocation | NN ClipRecall | Best Other | Best Other Name | NN Rank |",
        "|------------|---------------|------------|-----------------|---------|",
    ])

    for alloc_name in alloc_names:
        nn_key = f"{alloc_name}__nearest_neighbor_interpolation"
        nn_recall = combo_avgs.get(nn_key, {}).get("clip_recall", None)

        # Find best non-NN propagation
        other_props = [p for p in prop_names if p != "nearest_neighbor_interpolation"]
        other_recalls = []
        for prop_name in other_props:
            key = f"{alloc_name}__{prop_name}"
            if key in combo_avgs:
                other_recalls.append((prop_name, combo_avgs[key]["clip_recall"]))

        if nn_recall is not None and other_recalls:
            best_other = max(other_recalls, key=lambda x: x[1])
            # Compute rank of NN among all propagations for this allocation
            all_recalls = [nn_recall] + [r for _, r in other_recalls]
            all_recalls_sorted = sorted(all_recalls, reverse=True)
            nn_rank = all_recalls_sorted.index(nn_recall) + 1

            lines.append(
                f"| {alloc_name} | {nn_recall:.4f} | {best_other[1]:.4f} | "
                f"{best_other[0]} | {nn_rank}/{len(all_recalls)} |"
            )
        elif nn_recall is not None:
            lines.append(f"| {alloc_name} | {nn_recall:.4f} | N/A | N/A | 1/1 |")

    # Question 5: gap_tolerant_merge fragmentation analysis
    lines.extend([
        "",
        "## Q5: Does gap_tolerant_merge systematically reduce fragmentation?",
        "",
        "Compare fragmentation: gap_tolerant_merge vs nearest_neighbor_interpolation:",
        "",
        "| Allocation | NN Fragmentation | GT Fragmentation | Reduction |",
        "|------------|------------------|------------------|-----------|",
    ])

    for alloc_name in alloc_names:
        nn_key = f"{alloc_name}__nearest_neighbor_interpolation"
        gt_key = f"{alloc_name}__gap_tolerant_merge"

        nn_frag = combo_avgs.get(nn_key, {}).get("fragmentation", None)
        gt_frag = combo_avgs.get(gt_key, {}).get("fragmentation", None)

        if nn_frag is not None and gt_frag is not None:
            reduction = nn_frag - gt_frag
            lines.append(
                f"| {alloc_name} | {nn_frag:.4f} | {gt_frag:.4f} | {reduction:+.4f} |"
            )

    # Question 6: risk_aware_gap_bridge vs gap_tolerant_merge
    lines.extend([
        "",
        "## Q6: Does risk_aware_gap_bridge outperform gap_tolerant_merge?",
        "",
        "| Allocation | GT Merge ClipRecall | Risk Bridge ClipRecall | Difference |",
        "|------------|---------------------|----------------------|------------|",
    ])

    for alloc_name in alloc_names:
        gt_key = f"{alloc_name}__gap_tolerant_merge"
        risk_key = f"{alloc_name}__risk_aware_gap_bridge"

        gt_recall = combo_avgs.get(gt_key, {}).get("clip_recall", None)
        risk_recall = combo_avgs.get(risk_key, {}).get("clip_recall", None)

        if gt_recall is not None and risk_recall is not None:
            diff = risk_recall - gt_recall
            lines.append(
                f"| {alloc_name} | {gt_recall:.4f} | {risk_recall:.4f} | {diff:+.4f} |"
            )

    # Overall conclusion
    lines.extend([
        "",
        "## Q7: Research Direction Assessment",
        "",
    ])

    # Compute main effects
    alloc_effect = {}
    for alloc_name in alloc_names:
        alloc_recalls = [v["clip_recall"] for k, v in combo_avgs.items() if k.startswith(alloc_name + "__")]
        alloc_effect[alloc_name] = np.mean(alloc_recalls) if alloc_recalls else 0

    prop_effect = {}
    for prop_name in prop_names:
        prop_recalls = [v["clip_recall"] for k, v in combo_avgs.items() if k.endswith("__" + prop_name)]
        prop_effect[prop_name] = np.mean(prop_recalls) if prop_recalls else 0

    alloc_range = max(alloc_effect.values()) - min(alloc_effect.values())
    prop_range = max(prop_effect.values()) - min(prop_effect.values())

    lines.extend([
        "### Main Effects",
        "",
        f"- **Allocation effect range** (max - min mean clip recall): {alloc_range:.4f}",
        f"- **Propagation effect range**: {prop_range:.4f}",
        "",
    ])

    if prop_range > alloc_range * 1.5:
        lines.extend([
            "**Conclusion: Propagation dominates allocation.**",
            "",
            "The choice of propagation/clip reconstruction strategy has a larger impact on clip recall",
            "than the choice of allocation strategy. This suggests the research direction should focus on:",
            "- Robust propagation methods",
            "- Gap-tolerant clip reconstruction",
            "- Better boundary recovery under sparse oracle queries",
        ])
    elif alloc_range > prop_range * 1.5:
        lines.extend([
            "**Conclusion: Allocation dominates propagation.**",
            "",
            "The choice of allocation strategy has a larger impact. This suggests focusing on:",
            "- Motion-conditioned oracle allocation",
            "- Risk-aware frame selection",
            "- Budget optimization",
        ])
    else:
        lines.extend([
            "**Conclusion: Both allocation and propagation contribute.**",
            "",
            "Neither factor clearly dominates. The interaction between allocation and propagation",
            "may be important, or the problem may require co-optimization of both.",
        ])

    # Conservative note
    lines.extend([
        "",
        "## Caveats",
        "",
        "1. **Synthetic data only**: These results are on synthetic perturbation, not real moving-camera videos.",
        "2. **Simplified perturbation model**: Real camera motion effects may differ from our synthetic noise.",
        "3. **Single query type**: Only tested count(vehicle) >= K queries.",
        "4. **Metric limitations**: Clip recall at IoU threshold 0.5 may not capture all failure modes.",
        "",
        "**These results indicate where to look, not what to claim.**",
        "",
    ])

    report = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(report)

    return report


if __name__ == "__main__":
    main()
