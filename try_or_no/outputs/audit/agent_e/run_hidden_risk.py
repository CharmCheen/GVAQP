"""
Hidden-risk-aware oracle allocation baseline experiment.

Implements a baseline that uses hidden risk labels from the synthetic perturbation
generator to allocate oracle budget more wisely. Tests whether risk-aware allocation
can recover clip-level quality.

Usage:
    python outputs/audit/agent_e/run_hidden_risk.py
"""

import json
import csv
import pathlib
import sys

import numpy as np

# Add project root to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))

from pipeline.data_interface import (
    load_or_generate_dataset,
    FrameAnnotation,
    VideoAnnotation,
)
from pipeline.clip_gt import build_ground_truth_clips
from pipeline.perturbation import PerturbationConfig, perturb_video
from pipeline.baselines import (
    full_oracle_baseline,
    uniform_random_sampling_baseline,
    proxy_threshold_baseline,
    arc_temporal_clustering_baseline,
    BaselineResult,
    _labels_to_clips,
    _labels_to_segment_list,
)
from pipeline.metrics import compute_experiment_metrics, ExperimentMetrics


# ---------------------------------------------------------------------------
# Hidden Risk Baseline (implemented here, not in baselines.py)
# ---------------------------------------------------------------------------

def risk_aware_oracle_allocation_hidden(
    perturbed,
    K: int,
    tau: int,
    budget: float = 0.1,
    rng: np.random.Generator | None = None,
) -> BaselineResult:
    """Hidden-risk-aware oracle allocation baseline.

    Computes per-frame risk scores using only perturbed-side information
    (never touches original_labels).  Oracle budget is allocated
    proportional to risk; non-oracle frames use the proxy decision
    (perturbed_count >= K).

    Risk components
    ---------------
    1. motion_risk  : |perturbed_count[t] - perturbed_count[t-1]| (temporal derivative)
    2. boundary_risk: inverse distance to nearest label-transition boundary
       inferred from perturbed_labels (high near transitions)
    3. threshold_risk: |perturbed_count[t] - K| inverted (closer to K => riskier)
    4. visibility_drop_risk: deviation from local running average
       (large negative deviation => likely visibility drop)

    Parameters
    ----------
    perturbed : PerturbedSequence
    K : int   threshold
    tau : int  minimum clip length
    budget : float  fraction of frames that may be oracle-queried
    rng : np.random.Generator

    Returns
    -------
    BaselineResult
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(perturbed.perturbed_counts)
    num_oracle_budget = max(1, int(n * budget))
    counts = perturbed.perturbed_counts.astype(float)
    perturbed_labels = perturbed.perturbed_labels.astype(bool)

    # ------------------------------------------------------------------
    # 1. Motion risk: absolute temporal derivative of perturbed counts
    # ------------------------------------------------------------------
    deriv = np.abs(np.diff(counts, prepend=counts[0]))
    motion_risk = deriv / (deriv.max() + 1e-6)  # normalize to [0, 1]

    # ------------------------------------------------------------------
    # 2. Boundary proximity risk: distance to nearest label transition
    #    inferred from perturbed_labels (NOT original_labels)
    # ------------------------------------------------------------------
    # Find transition points in perturbed labels
    label_changes = np.abs(np.diff(perturbed_labels.astype(int)))
    transition_indices = np.where(label_changes > 0)[0]

    if len(transition_indices) > 0:
        # For each frame, compute min distance to any transition
        all_frames = np.arange(n)
        distances = np.min(
            np.abs(all_frames[:, None] - transition_indices[None, :]),
            axis=1,
        )
        # Convert distance to risk: closer to boundary => higher risk
        # Use exponential decay: risk = exp(-distance / scale)
        boundary_scale = max(1, n * 0.05)  # 5% of video length
        boundary_risk = np.exp(-distances / boundary_scale)
    else:
        boundary_risk = np.zeros(n)

    # ------------------------------------------------------------------
    # 3. Threshold proximity risk: |perturbed_count - K|
    #    Closer to K => riskier (uncertain)
    # ------------------------------------------------------------------
    threshold_dist = np.abs(counts - K)
    # Invert: lower distance => higher risk
    threshold_risk = 1.0 - threshold_dist / (threshold_dist.max() + 1e-6)

    # ------------------------------------------------------------------
    # 4. Visibility drop risk: deviation from local running average
    #    A sudden dip relative to local context suggests a visibility drop
    # ------------------------------------------------------------------
    window = 15
    local_avg = np.convolve(counts, np.ones(window) / window, mode="same")
    deviation = local_avg - counts  # positive when counts dip below average
    deviation = np.clip(deviation, 0, None)  # only penalize dips
    vis_risk = deviation / (deviation.max() + 1e-6)

    # ------------------------------------------------------------------
    # Composite risk score (weighted sum)
    # ------------------------------------------------------------------
    risk_score = (
        0.30 * motion_risk
        + 0.30 * boundary_risk
        + 0.20 * threshold_risk
        + 0.20 * vis_risk
    )

    # Ensure minimum risk so every frame has some chance
    risk_score = np.clip(risk_score, 1e-4, None)

    # Normalize to allocation probability
    alloc_prob = risk_score / risk_score.sum()

    # ------------------------------------------------------------------
    # Sample oracle frames proportional to risk
    # ------------------------------------------------------------------
    oracle_indices = set(
        rng.choice(n, size=min(num_oracle_budget, n), replace=False, p=alloc_prob)
    )

    # Build frame labels: oracle for sampled, proxy for the rest
    frame_labels = (counts >= K).astype(bool)  # proxy decision
    oracle_calls = 0
    for idx in oracle_indices:
        frame_labels[idx] = perturbed.original_labels[idx]
        oracle_calls += 1

    clips = _labels_to_clips(frame_labels, tau)
    return BaselineResult(
        method="risk_aware_hidden",
        predicted_clips=clips,
        oracle_calls=oracle_calls,
        frame_labels=frame_labels,
    )


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def run_single_video(
    video: VideoAnnotation,
    K: int,
    tau: int,
    budget: float,
    perturb_config: PerturbationConfig,
    rng: np.random.Generator,
) -> list[ExperimentMetrics]:
    """Run all baselines on a single video and return metrics."""
    gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
    gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
    gt_frame_labels = (video.frame_counts() >= K).astype(bool)

    perturbed = perturb_video(
        video, K=K, config=perturb_config, rng=rng, boundary_clips=gt_clip_ranges
    )

    results = []

    # 1. Full oracle (upper bound)
    oracle_result = full_oracle_baseline(perturbed, K=K, tau=tau)
    results.append(("full_oracle", oracle_result))

    # 2. Uniform random sampling
    random_result = uniform_random_sampling_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("uniform_random", random_result))

    # 3. Proxy-threshold
    proxy_result = proxy_threshold_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("proxy_threshold", proxy_result))

    # 4. ARC-style temporal clustering
    arc_result = arc_temporal_clustering_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("arc_clustering", arc_result))

    # 5. Hidden risk-aware allocation
    risk_result = risk_aware_oracle_allocation_hidden(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("risk_aware_hidden", risk_result))

    all_metrics = []
    for method_name, baseline in results:
        metrics = compute_experiment_metrics(
            video_id=video.video_id,
            method=method_name,
            gt_frame_labels=gt_frame_labels,
            pred_frame_labels=baseline.frame_labels,
            gt_clips=gt_clip_ranges,
            pred_clips=baseline.predicted_clips,
            oracle_calls=baseline.oracle_calls,
            total_frames=len(gt_frame_labels),
        )
        all_metrics.append(metrics)

    return all_metrics


def main():
    output_dir = pathlib.Path(__file__).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Configuration
    sample_size = 50
    K = 3
    tau = 30
    budget = 0.1
    num_frames = 300
    seed = 42

    print("Configuration:")
    print(f"  sample_size={sample_size}, K={K}, tau={tau}, budget={budget}")
    print(f"  num_frames={num_frames}, seed={seed}")
    print(f"  output_dir={output_dir}")
    print()

    # Generate dataset
    print("Generating synthetic dataset...")
    videos = load_or_generate_dataset(
        annotation_dir=None,
        sample_size=sample_size,
        num_frames=num_frames,
        seed=seed,
    )
    print(f"  Generated {len(videos)} videos")

    # Perturbation config (defaults)
    perturb_config = PerturbationConfig()

    # Run experiments
    print("\nRunning experiments...")
    all_metrics = []
    per_video_results = []

    for i, video in enumerate(videos):
        print(f"  [{i + 1}/{len(videos)}] {video.video_id}")
        video_rng = np.random.default_rng(seed + i)

        video_metrics = run_single_video(
            video=video,
            K=K,
            tau=tau,
            budget=budget,
            perturb_config=perturb_config,
            rng=video_rng,
        )
        all_metrics.extend(video_metrics)

        per_video_results.append({
            "video_id": video.video_id,
            "num_frames": video.num_frames,
            "gt_clips": len(build_ground_truth_clips(video, K=K, tau=tau)),
            "metrics": [m.to_dict() for m in video_metrics],
        })

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    print("\nWriting outputs...")

    # hidden_risk_metrics.csv
    metrics_csv_path = output_dir / "hidden_risk_metrics.csv"
    if all_metrics:
        fieldnames = list(all_metrics[0].to_dict().keys())
        with open(metrics_csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in all_metrics:
                writer.writerow(m.to_dict())
    print(f"  {metrics_csv_path}")

    # hidden_risk_results.jsonl
    results_jsonl_path = output_dir / "hidden_risk_results.jsonl"
    with open(results_jsonl_path, "w") as f:
        for result in per_video_results:
            f.write(json.dumps(result) + "\n")
    print(f"  {results_jsonl_path}")

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    report_path = output_dir / "hidden_risk_summary.md"
    report = generate_summary_report(all_metrics)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"  {report_path}")

    # Print summary
    print("\n" + "=" * 70)
    print("EXPERIMENT COMPLETE")
    print("=" * 70)
    print(report)


def generate_summary_report(all_metrics: list[ExperimentMetrics]) -> str:
    """Generate a markdown summary comparing all methods."""
    # Group by method
    methods: dict[str, list[ExperimentMetrics]] = {}
    for m in all_metrics:
        methods.setdefault(m.method, []).append(m)

    # Compute per-method averages
    method_stats: dict[str, dict] = {}
    for method, metrics_list in methods.items():
        n = len(metrics_list)
        method_stats[method] = {
            "frame_recall": sum(m.frame_recall for m in metrics_list) / n,
            "frame_precision": sum(m.frame_precision for m in metrics_list) / n,
            "clip_recall": sum(m.clip_recall for m in metrics_list) / n,
            "clip_precision": sum(m.clip_precision for m in metrics_list) / n,
            "mean_iou": sum(m.mean_iou for m in metrics_list) / n,
            "mean_start_error": _safe_mean([m.mean_start_error for m in metrics_list]),
            "mean_end_error": _safe_mean([m.mean_end_error for m in metrics_list]),
            "fragmentation_rate": sum(m.fragmentation_rate for m in metrics_list) / n,
            "oracle_calls": sum(m.oracle_calls for m in metrics_list),
            "total_frames": sum(m.total_frames for m in metrics_list),
        }
        method_stats[method]["oracle_fraction"] = (
            method_stats[method]["oracle_calls"]
            / method_stats[method]["total_frames"]
            if method_stats[method]["total_frames"] > 0
            else 0.0
        )

    # Build report
    lines = [
        "# Hidden-Risk-Aware Oracle Allocation -- Summary Report",
        "",
        "## Configuration",
        "",
        f"- Sample size: 50 synthetic videos",
        f"- K (min vehicles): 3",
        f"- tau (min clip frames): 30",
        f"- Oracle budget: 0.1 (10% of frames)",
        f"- Frames per video: 300",
        f"- Seed: 42",
        "",
        "## Method Comparison",
        "",
        "| Method | Frame Recall | Frame Prec | Clip Recall | Clip Prec | Mean IoU | Frag Rate | Oracle Frac |",
        "|--------|-------------|------------|-------------|-----------|----------|-----------|-------------|",
    ]

    # Order: full_oracle, then others
    order = ["full_oracle", "uniform_random", "proxy_threshold", "arc_clustering", "risk_aware_hidden"]
    for method in order:
        if method in method_stats:
            s = method_stats[method]
            lines.append(
                f"| {method} | {s['frame_recall']:.3f} | {s['frame_precision']:.3f} | "
                f"{s['clip_recall']:.3f} | {s['clip_precision']:.3f} | "
                f"{s['mean_iou']:.3f} | {s['fragmentation_rate']:.3f} | "
                f"{s['oracle_fraction']:.3f} |"
            )

    # Boundary errors
    lines.extend([
        "",
        "## Boundary Errors (frames)",
        "",
        "| Method | Mean Start Error | Mean End Error |",
        "|--------|-----------------|----------------|",
    ])
    for method in order:
        if method in method_stats:
            s = method_stats[method]
            se = f"{s['mean_start_error']:.1f}" if s['mean_start_error'] != float('inf') else "inf"
            ee = f"{s['mean_end_error']:.1f}" if s['mean_end_error'] != float('inf') else "inf"
            lines.append(f"| {method} | {se} | {ee} |")

    # Degradation analysis relative to oracle
    if "full_oracle" in method_stats:
        oracle = method_stats["full_oracle"]
        lines.extend([
            "",
            "## Degradation Analysis (relative to full oracle)",
            "",
            "| Method | Frame Recall Drop | Clip Recall Drop | Clip Drop / Frame Drop |",
            "|--------|------------------|-----------------|----------------------|",
        ])
        for method in order:
            if method == "full_oracle" or method not in method_stats:
                continue
            s = method_stats[method]
            frame_drop = oracle["frame_recall"] - s["frame_recall"]
            clip_drop = oracle["clip_recall"] - s["clip_recall"]
            ratio = clip_drop / frame_drop if frame_drop > 0 else float("inf")
            lines.append(
                f"| {method} | {frame_drop:.3f} | {clip_drop:.3f} | {ratio:.2f} |"
            )

    # Analysis of risk-aware hidden vs other budget-constrained methods
    lines.extend([
        "",
        "## Analysis: Risk-Aware Hidden vs Other Budget-Constrained Methods",
        "",
    ])

    if "risk_aware_hidden" in method_stats:
        risk = method_stats["risk_aware_hidden"]
        budget_methods = ["uniform_random", "proxy_threshold", "arc_clustering"]

        lines.append("### Can hidden risk-aware allocation recover clip-level quality?")
        lines.append("")

        # Find the best competing method for each metric
        best_clip_recall = 0
        best_method = ""
        for m in budget_methods:
            if m in method_stats and method_stats[m]["clip_recall"] > best_clip_recall:
                best_clip_recall = method_stats[m]["clip_recall"]
                best_method = m

        if risk["clip_recall"] >= best_clip_recall:
            lines.append(
                "**Yes.** The hidden-risk-aware baseline achieves the highest clip recall "
                "among budget-constrained methods. Risk-weighted oracle allocation successfully "
                "focuses queries on the frames most likely to cause clip-level errors."
            )
        elif risk["clip_recall"] >= best_clip_recall - 0.05:
            lines.append(
                "**Partially.** The hidden-risk-aware baseline is competitive with the best "
                "budget-constrained method on clip recall. The risk heuristics provide a useful "
                "signal for oracle allocation, though the margin is modest."
            )
        else:
            lines.append(
                "**Not clearly.** The hidden-risk-aware baseline does not outperform the best "
                "competing budget-constrained method on clip recall. The risk heuristics may "
                "need refinement, or the risk information available from perturbed data alone "
                "may be insufficient to guide allocation effectively."
            )

        lines.extend([
            "",
            "### Is the oracle budget being used effectively?",
            "",
            f"- risk_aware_hidden oracle calls: {risk['oracle_calls']:.0f} "
            f"(fraction: {risk['oracle_fraction']:.3f})",
            "",
        ])

        for m in budget_methods:
            if m in method_stats:
                s = method_stats[m]
                lines.append(
                    f"- {m} oracle calls: {s['oracle_calls']:.0f} "
                    f"(fraction: {s['oracle_fraction']:.3f}), "
                    f"clip_recall: {s['clip_recall']:.3f}"
                )

        lines.extend([
            "",
            "The risk-aware method allocates its oracle budget proportional to composite "
            "risk scores derived from: (1) motion (temporal derivative of perturbed counts), "
            "(2) proximity to label-transition boundaries, (3) threshold proximity "
            "(how close perturbed counts are to K), and (4) visibility drop detection "
            "(deviation from local average). This targets the oracle at frames where "
            "perturbation is most likely to cause errors.",
        ])

    # Conclusion
    lines.extend([
        "",
        "## Conclusion",
        "",
        "This experiment tests whether heuristic risk signals derived from perturbed "
        "data can guide oracle budget allocation to recover clip-level quality. "
        "The hidden-risk baseline combines motion, boundary, threshold, and visibility "
        "risk components to focus oracle queries on the most error-prone frames.",
        "",
    ])

    return "\n".join(lines)


def _safe_mean(values: list[float]) -> float:
    """Mean that handles inf values by excluding them."""
    finite = [v for v in values if v != float("inf")]
    return sum(finite) / len(finite) if finite else 0.0


if __name__ == "__main__":
    main()
