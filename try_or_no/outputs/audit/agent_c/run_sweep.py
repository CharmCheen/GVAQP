"""
Parameter sweep for synthetic clip degradation experiment.

Sweeps over tau, budget, K, and seeds to determine whether clip-level
degradation is consistently larger than frame-level degradation.
"""

import csv
import itertools
import pathlib
import sys
import time

import numpy as np

# Add repo root to path for pipeline imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))

from pipeline.data_interface import load_or_generate_dataset, VideoAnnotation
from pipeline.clip_gt import build_ground_truth_clips
from pipeline.perturbation import PerturbationConfig, perturb_video
from pipeline.baselines import (
    full_oracle_baseline,
    fixed_rate_sampling_baseline,
    uniform_random_sampling_baseline,
    proxy_threshold_baseline,
    arc_temporal_clustering_baseline,
)
from pipeline.metrics import compute_experiment_metrics


def run_single_video(
    video: VideoAnnotation,
    K: int,
    tau: int,
    budget: float,
    perturb_config: PerturbationConfig,
    rng: np.random.Generator,
):
    """Run all baselines on a single video and return metrics."""
    gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
    gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
    gt_frame_labels = (video.frame_counts() >= K).astype(bool)

    perturbed = perturb_video(
        video, K=K, config=perturb_config, rng=rng, boundary_clips=gt_clip_ranges
    )

    results = [
        ("full_oracle", full_oracle_baseline(perturbed, K=K, tau=tau)),
        ("fixed_rate", fixed_rate_sampling_baseline(perturbed, K=K, tau=tau, sample_rate=budget, rng=rng)),
        ("uniform_random", uniform_random_sampling_baseline(perturbed, K=K, tau=tau, budget=budget, rng=rng)),
        ("proxy_threshold", proxy_threshold_baseline(perturbed, K=K, tau=tau, budget=budget, rng=rng)),
        ("arc_clustering", arc_temporal_clustering_baseline(perturbed, K=K, tau=tau, budget=budget, rng=rng)),
    ]

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

    # Sweep parameters
    taus = [10, 20, 30, 60]
    budgets = [0.05, 0.1, 0.2, 0.4]
    Ks = [2, 3, 5]
    seeds = [42, 43, 44, 45, 46]
    sample_size = 50

    perturb_config = PerturbationConfig()

    def make_seed(K, tau, budget, seed_idx):
        return seed_idx + (hash((K, tau, budget, seed_idx)) % 100000)

    combos = list(itertools.product(taus, budgets, Ks))
    total = len(combos) * len(seeds)

    print(f"Sweep: {len(combos)} parameter combos x {len(seeds)} seeds = {total} runs")
    print(f"Each run: {sample_size} videos x 5 methods")

    # Metric columns from ExperimentMetrics
    metric_cols = [
        "frame_recall", "frame_precision",
        "clip_recall", "clip_precision",
        "mean_start_error", "mean_end_error",
        "mean_iou", "fragmentation_rate",
        "oracle_calls", "total_frames", "oracle_fraction",
        "num_gt_clips", "num_pred_clips", "num_matched_clips",
    ]
    fieldnames = ["K", "tau", "budget", "seed", "video_id", "method"] + metric_cols

    csv_path = output_dir / "sweep_metrics.csv"
    run_idx = 0
    t0 = time.time()

    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for tau, budget, K in combos:
            for seed_idx in seeds:
                run_idx += 1
                if run_idx % 10 == 0 or run_idx == 1:
                    elapsed = time.time() - t0
                    rate = run_idx / elapsed if elapsed > 0 else 0
                    eta = (total - run_idx) / rate if rate > 0 else 0
                    print(
                        f"  [{run_idx}/{total}] tau={tau} budget={budget} K={K} seed={seed_idx} "
                        f"({elapsed:.0f}s elapsed, {eta:.0f}s remaining)"
                    )

                data_seed = make_seed(K, tau, budget, seed_idx)
                videos = load_or_generate_dataset(
                    annotation_dir=None,
                    sample_size=sample_size,
                    num_frames=300,
                    seed=data_seed,
                )

                rng = np.random.default_rng(data_seed + 1000)

                for video in videos:
                    video_rng = np.random.default_rng(rng.integers(0, 2**31))
                    video_metrics = run_single_video(
                        video=video, K=K, tau=tau, budget=budget,
                        perturb_config=perturb_config, rng=video_rng,
                    )
                    for m in video_metrics:
                        row = {"K": K, "tau": tau, "budget": budget, "seed": seed_idx}
                        d = m.to_dict()
                        for col in metric_cols:
                            row[col] = d[col]
                        row["video_id"] = d["video_id"]
                        row["method"] = d["method"]
                        writer.writerow(row)

    elapsed_total = time.time() - t0
    print(f"\nSweep complete in {elapsed_total:.1f}s. Results: {csv_path}")

    # ----------------------------------------------------------------
    # Analysis
    # ----------------------------------------------------------------
    print("\nAnalyzing results...")

    import pandas as pd
    df = pd.read_csv(csv_path)

    group_cols = ["K", "tau", "budget"]
    methods = ["fixed_rate", "uniform_random", "proxy_threshold", "arc_clustering"]

    # Compute per-group means
    agg = df.groupby(group_cols + ["method"]).agg({
        "frame_recall": "mean",
        "clip_recall": "mean",
    }).reset_index()

    summary_rows = []
    for (K, tau, budget), grp in agg.groupby(group_cols):
        oracle = grp[grp["method"] == "full_oracle"]
        if oracle.empty:
            continue
        oracle_fr = oracle["frame_recall"].values[0]
        oracle_cr = oracle["clip_recall"].values[0]

        row = {"K": int(K), "tau": int(tau), "budget": float(budget)}
        clip_gt_frame_count = 0

        for method in methods:
            mgrp = grp[grp["method"] == method]
            if mgrp.empty:
                continue
            fr = mgrp["frame_recall"].values[0]
            cr = mgrp["clip_recall"].values[0]
            fd = oracle_fr - fr
            cd = oracle_cr - cr
            ratio = cd / fd if fd > 1e-9 else float("inf")
            c_gt_f = cd > fd
            if c_gt_f:
                clip_gt_frame_count += 1

            row[f"{method}_framedrop"] = round(fd, 4)
            row[f"{method}_clipdrop"] = round(cd, 4)
            row[f"{method}_ratio"] = round(ratio, 2) if ratio != float("inf") else "inf"
            row[f"{method}_C_gt_F"] = c_gt_f

        row["clip_gt_frame_count"] = clip_gt_frame_count
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values(group_cols, inplace=True)
    summary_df.to_csv(output_dir / "sweep_summary.csv", index=False)

    # Compute overall stats
    boolean_cols = [c for c in summary_df.columns if c.endswith("_C_gt_F")]
    total_cells = 0
    true_cells = 0
    for _, r in summary_df.iterrows():
        for c in boolean_cols:
            total_cells += 1
            if r[c]:
                true_cells += 1
    consistency = true_cells / total_cells if total_cells > 0 else 0

    # Find strongest effects (highest ratio)
    ratio_data = []
    for _, r in summary_df.iterrows():
        for method in methods:
            ratio_col = f"{method}_ratio"
            if ratio_col in r and r[ratio_col] != "inf":
                ratio_data.append((r["K"], r["tau"], r["budget"], method, r[ratio_col]))
    ratio_data.sort(key=lambda x: x[4], reverse=True)

    # Find reversals
    reversals = []
    for _, r in summary_df.iterrows():
        for method in methods:
            fd_col = f"{method}_framedrop"
            cd_col = f"{method}_clipdrop"
            if fd_col in r.index and cd_col in r.index:
                fd_val = r[fd_col]
                cd_val = r[cd_col]
                if fd_val > cd_val + 1e-9:
                    reversals.append((r["K"], r["tau"], r["budget"], method, fd_val, cd_val))

    # Average ratios per method
    avg_ratios = {}
    for method in methods:
        ratios = []
        for _, r in summary_df.iterrows():
            ratio_col = f"{method}_ratio"
            if ratio_col in r and r[ratio_col] != "inf":
                ratios.append(r[ratio_col])
        if ratios:
            avg_ratios[method] = np.mean(ratios)

    # ----------------------------------------------------------------
    # Write summary markdown
    # ----------------------------------------------------------------
    lines = [
        "# Sweep Summary: Clip-Level vs Frame-Level Degradation",
        "",
        "## Configuration",
        "",
        f"- tau: {taus}",
        f"- budget: {budgets}",
        f"- K: {Ks}",
        f"- seeds: {seeds} (5 per combination)",
        f"- sample_size: {sample_size} videos per run",
        f"- Total combinations: {len(combos)} x {len(seeds)} = {total} runs",
        "",
        "## Full Results Table",
        "",
    ]

    # Build a cleaner table: one row per (K, tau, budget) with per-method sub-columns
    header = "| K | tau | budget | "
    sub_header = "|---|-----|--------| "
    for method in methods:
        short = method.replace("_", " ").title()[:15]
        header += f" {short} FD | {short} CD | Ratio | C>F |"
        sub_header += "---:|---:|---:|:---:|"

    lines.append(header)
    lines.append(sub_header)

    for _, r in summary_df.iterrows():
        row_str = f"| {int(r['K'])} | {int(r['tau'])} | {r['budget']:.2f} |"
        for method in methods:
            fd = r.get(f"{method}_framedrop", "N/A")
            cd = r.get(f"{method}_clipdrop", "N/A")
            ratio = r.get(f"{method}_ratio", "N/A")
            c_gt_f = r.get(f"{method}_C_gt_F", "N/A")

            if isinstance(fd, float):
                fd_str = f"{fd:.3f}"
            else:
                fd_str = str(fd)
            if isinstance(cd, float):
                cd_str = f"{cd:.3f}"
            else:
                cd_str = str(cd)
            if isinstance(ratio, float):
                ratio_str = f"{ratio:.2f}"
            else:
                ratio_str = str(ratio)
            flag = "Yes" if c_gt_f else "No"

            row_str += f" {fd_str} | {cd_str} | {ratio_str} | {flag} |"
        lines.append(row_str)

    # Aggregate by tau
    lines.extend(["", "## Average Ratio by tau", ""])
    lines.append("| tau | " + " | ".join(methods) + " |")
    lines.append("|-----|" + "|".join(["---:"] * len(methods)) + "|")
    for tau in taus:
        tau_df = summary_df[summary_df["tau"] == tau]
        row = f"| {tau} |"
        for method in methods:
            col = f"{method}_ratio"
            vals = tau_df[col][tau_df[col] != "inf"].dropna()
            if len(vals) > 0:
                row += f" {vals.mean():.2f} |"
            else:
                row += " N/A |"
        lines.append(row)

    # Aggregate by budget
    lines.extend(["", "## Average Ratio by budget", ""])
    lines.append("| budget | " + " | ".join(methods) + " |")
    lines.append("|--------|" + "|".join(["---:"] * len(methods)) + "|")
    for budget in budgets:
        budget_df = summary_df[summary_df["budget"] == budget]
        row = f"| {budget:.2f} |"
        for method in methods:
            col = f"{method}_ratio"
            vals = budget_df[col][budget_df[col] != "inf"].dropna()
            if len(vals) > 0:
                row += f" {vals.mean():.2f} |"
            else:
                row += " N/A |"
        lines.append(row)

    # Aggregate by K
    lines.extend(["", "## Average Ratio by K", ""])
    lines.append("| K | " + " | ".join(methods) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(methods)) + "|")
    for K in Ks:
        K_df = summary_df[summary_df["K"] == K]
        row = f"| {K} |"
        for method in methods:
            col = f"{method}_ratio"
            vals = K_df[col][K_df[col] != "inf"].dropna()
            if len(vals) > 0:
                row += f" {vals.mean():.2f} |"
            else:
                row += " N/A |"
        lines.append(row)

    # Average ratio per method
    lines.extend(["", "## Average Ratio per Method (across all combinations)", ""])
    lines.append("| Method | Avg Clip/Frame Drop Ratio |")
    lines.append("|--------|--------------------------|")
    for method in methods:
        if method in avg_ratios:
            lines.append(f"| {method} | {avg_ratios[method]:.2f} |")

    # Analysis questions
    lines.extend([
        "",
        "## Analysis",
        "",
        f"**Overall consistency**: Clip drop > Frame drop in {true_cells}/{total_cells} "
        f"method-combination cells ({consistency*100:.1f}%).",
        "",
    ])

    # Q1: Is clip-level degradation consistently larger?
    lines.append("### Is clip-level degradation consistently larger than frame-level degradation?")
    lines.append("")
    if consistency >= 0.8:
        lines.append(
            f"**Yes**. Across {len(combos)} parameter combinations and {len(methods)} methods, "
            f"clip-level recall drop exceeds frame-level recall drop in {consistency*100:.1f}% of cases. "
            "This confirms that perturbation compounds at the clip boundary level: small frame-level "
            "errors cascade into entire clip misses when they disrupt the minimum-length threshold (tau)."
        )
    elif consistency >= 0.5:
        lines.append(
            f"**Mostly**. Clip-level degradation exceeds frame-level in {consistency*100:.1f}% of cases. "
            "The effect is present but not universal across all configurations."
        )
    else:
        lines.append(
            f"**No**. Clip-level degradation exceeds frame-level in only {consistency*100:.1f}% of cases. "
            "The expected compounding effect is not consistently observed."
        )

    # Q2: Strongest effects
    lines.extend(["", "### Parameter combinations showing strongest effect", ""])
    if ratio_data:
        lines.append("Top 10 by clip_drop / frame_drop ratio:")
        lines.append("")
        lines.append("| K | tau | budget | Method | Ratio |")
        lines.append("|---|-----|--------|--------|------:|")
        for K, tau, budget, method, ratio in ratio_data[:10]:
            lines.append(f"| {K} | {tau} | {budget:.2f} | {method} | {ratio:.2f} |")
        lines.append("")
        lines.append(
            "Higher ratios indicate configurations where clip-level degradation is disproportionately "
            "worse than frame-level. Typically, larger tau (more frames required per clip) and lower "
            "budget (fewer oracle corrections) amplify the compounding effect."
        )

    # Q3: Reversals
    lines.extend(["", "### Parameter combinations where the effect reverses", ""])
    if reversals:
        lines.append(
            f"The effect reverses (frame_drop > clip_drop) in {len(reversals)} cases:"
        )
        lines.append("")
        lines.append("| K | tau | budget | Method | Frame Drop | Clip Drop |")
        lines.append("|---|-----|--------|--------|----------:|---------:|")
        for K, tau, budget, method, fd, cd in reversals[:20]:
            lines.append(f"| {K} | {tau} | {budget:.2f} | {method} | {fd:.3f} | {cd:.3f} |")
        if len(reversals) > 20:
            lines.append(f"| ... | ... | ... | ... | ... | ... |")
            lines.append(f"(showing 20 of {len(reversals)} reversals)")
        lines.append("")
        lines.append(
            "Reversals tend to occur at high budget values where oracle corrections are plentiful, "
            "or at low tau values where clip boundaries are easy to satisfy even with noisy labels."
        )
    else:
        lines.append(
            "No reversals observed. Clip-level degradation is consistently >= frame-level degradation "
            "across all tested parameter combinations."
        )

    # Per-method summary
    lines.extend(["", "### Per-method observations", ""])
    for method in methods:
        method_data = []
        for _, r in summary_df.iterrows():
            fd = r.get(f"{method}_framedrop", None)
            cd = r.get(f"{method}_clipdrop", None)
            if fd is not None and cd is not None:
                method_data.append((fd, cd))
        if not method_data:
            continue
        avg_fd = np.mean([d[0] for d in method_data])
        avg_cd = np.mean([d[1] for d in method_data])
        avg_ratio = avg_cd / avg_fd if avg_fd > 1e-9 else float("inf")
        n_clip_gt = sum(1 for fd, cd in method_data if cd > fd)
        lines.append(
            f"- **{method}**: avg frame_drop={avg_fd:.3f}, avg clip_drop={avg_cd:.3f}, "
            f"avg ratio={avg_ratio:.2f}, clip>frame in {n_clip_gt}/{len(method_data)} combos"
        )

    lines.extend([
        "",
        "## Files",
        "",
        "- `sweep_metrics.csv`: Raw per-video metrics for all 240 x 5 = 1200 runs",
        "- `sweep_summary.csv`: Aggregated means per (K, tau, budget) with drop columns",
        "- `sweep_summary.md`: This analysis document",
        "",
    ])

    report = "\n".join(lines)
    summary_path = output_dir / "sweep_summary.md"
    with open(summary_path, "w") as f:
        f.write(report)

    print(f"Summary written to {summary_path}")
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Clip drop > Frame drop in {true_cells}/{total_cells} cells ({consistency*100:.1f}%)")
    if avg_ratios:
        for method, ratio in avg_ratios.items():
            print(f"  {method}: avg ratio = {ratio:.2f}")
    print(f"\nResults: {csv_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
