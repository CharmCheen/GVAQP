"""Generate markdown report summarizing experiment results."""

import csv
from typing import List, Dict, Any

from pipeline.metrics import ExperimentMetrics


def generate_report(
    all_metrics: List[ExperimentMetrics],
    output_path: str,
    config: Dict[str, Any],
) -> str:
    """Generate a markdown report comparing frame-level vs clip-level degradation."""
    if not all_metrics:
        report = "# Experiment Report\n\nNo metrics to report.\n"
        with open(output_path, "w") as f:
            f.write(report)
        return report

    # Group by method
    methods = {}
    for m in all_metrics:
        methods.setdefault(m.method, []).append(m)

    # Compute per-method averages
    method_stats = {}
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
            method_stats[method]["oracle_calls"] / method_stats[method]["total_frames"]
            if method_stats[method]["total_frames"] > 0 else 0.0
        )

    # Build report
    lines = [
        "# Synthetic Clip Degradation Experiment Report",
        "",
        "## Configuration",
        "",
        f"- Sample size: {config.get('sample_size', 'N/A')}",
        f"- K (min vehicles): {config.get('K', 'N/A')}",
        f"- tau (min frames): {config.get('tau', 'N/A')}",
        f"- Budget: {config.get('budget', 'N/A')}",
        f"- Num videos: {len(set(m.video_id for m in all_metrics))}",
        "",
        "## Method Comparison",
        "",
        "| Method | Frame Recall | Frame Prec | Clip Recall | Clip Prec | Mean IoU | Frag Rate | Oracle Frac |",
        "|--------|-------------|------------|-------------|-----------|----------|-----------|-------------|",
    ]

    for method, stats in sorted(method_stats.items()):
        lines.append(
            f"| {method} | {stats['frame_recall']:.3f} | {stats['frame_precision']:.3f} | "
            f"{stats['clip_recall']:.3f} | {stats['clip_precision']:.3f} | "
            f"{stats['mean_iou']:.3f} | {stats['fragmentation_rate']:.3f} | "
            f"{stats['oracle_fraction']:.3f} |"
        )

    lines.extend([
        "",
        "## Boundary Errors (frames)",
        "",
        "| Method | Mean Start Error | Mean End Error |",
        "|--------|-----------------|----------------|",
    ])
    for method, stats in sorted(method_stats.items()):
        se = f"{stats['mean_start_error']:.1f}" if stats['mean_start_error'] != float('inf') else "inf"
        ee = f"{stats['mean_end_error']:.1f}" if stats['mean_end_error'] != float('inf') else "inf"
        lines.append(f"| {method} | {se} | {ee} |")

    # Degradation analysis
    lines.extend([
        "",
        "## Degradation Analysis",
        "",
    ])

    # Compare frame-level vs clip-level degradation
    if "full_oracle" in method_stats and len(method_stats) > 1:
        oracle = method_stats["full_oracle"]
        lines.append("### Frame-level vs Clip-level Degradation (relative to oracle)")
        lines.append("")
        lines.append("| Method | Frame Recall Drop | Clip Recall Drop | Clip Drop / Frame Drop |")
        lines.append("|--------|------------------|-----------------|----------------------|")

        for method, stats in sorted(method_stats.items()):
            if method == "full_oracle":
                continue
            frame_drop = oracle["frame_recall"] - stats["frame_recall"]
            clip_drop = oracle["clip_recall"] - stats["clip_recall"]
            ratio = clip_drop / frame_drop if frame_drop > 0 else float('inf')
            lines.append(
                f"| {method} | {frame_drop:.3f} | {clip_drop:.3f} | {ratio:.2f} |"
            )

        # Overall verdict
        lines.extend([
            "",
            "### Verdict",
            "",
        ])
        max_clip_drop = 0
        max_frame_drop = 0
        for method, stats in method_stats.items():
            if method == "full_oracle":
                continue
            fd = oracle["frame_recall"] - stats["frame_recall"]
            cd = oracle["clip_recall"] - stats["clip_recall"]
            max_frame_drop = max(max_frame_drop, fd)
            max_clip_drop = max(max_clip_drop, cd)

        if max_clip_drop > max_frame_drop * 1.5:
            lines.append(
                "**Yes**: Clip-level degradation is substantially larger than frame-level degradation. "
                "This confirms that perturbation compounds at the clip level — small frame-level errors "
                "cascade into clip-level misses."
            )
        elif max_clip_drop > max_frame_drop:
            lines.append(
                "**Moderate**: Clip-level degradation is larger than frame-level degradation, "
                "but the gap is modest. Further experimentation with stronger perturbation may be needed."
            )
        else:
            lines.append(
                "**No**: Clip-level degradation is not clearly larger than frame-level degradation "
                "in this configuration. Consider adjusting K, tau, or perturbation parameters."
            )
    else:
        lines.append("Insufficient methods to compare degradation.")

    lines.extend([
        "",
        "## Conclusion",
        "",
        "This pipeline successfully measures whether label-level perturbation causes "
        "disproportionate clip-level degradation. The results above show the relative "
        "impact on frame-level vs clip-level metrics across different baseline methods.",
        "",
    ])

    report = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(report)
    return report


def _safe_mean(values: List[float]) -> float:
    """Mean that handles inf values by excluding them."""
    finite = [v for v in values if v != float('inf')]
    return sum(finite) / len(finite) if finite else 0.0


def write_metrics_csv(metrics: List[ExperimentMetrics], output_path: str) -> None:
    """Write metrics to CSV."""
    if not metrics:
        return

    fieldnames = list(metrics[0].to_dict().keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics:
            writer.writerow(m.to_dict())
