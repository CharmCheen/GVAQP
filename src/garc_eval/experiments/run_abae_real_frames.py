"""ABae real-frame BDD100K smoke experiment.

Uses cached BDD100K data (supg_source.csv, oracle_scores.parquet, proxy_scores.parquet)
to run ABae vs Uniform aggregation on the predicate: count_car(frame) >= 13.

Does NOT rerun YOLO. Reads cached oracle/proxy labels only for sampled records.

Usage:
    python -m garc_eval.experiments.run_abae_real_frames [--config path/to/config.yaml]
"""

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from garc_eval.adapters.abae_adapter import run_abae
from garc_eval.baselines.uniform_aggregation import run_uniform_aggregation
from garc_eval.metrics.aggregation_metrics import compute_aggregation_metrics, summarize_trials_metrics


def load_bdd100k_data(
    supg_source_path: str,
    oracle_scores_path: str,
    proxy_scores_path: str,
    statistic_value_col: str = "oracle_count",
) -> pd.DataFrame:
    """Load and merge BDD100K cached data into ABae input format.

    Returns DataFrame with columns: id, proxy_score, label, statistic_value.
    """
    supg = pd.read_csv(supg_source_path)
    oracle = pd.read_parquet(oracle_scores_path)
    proxy = pd.read_parquet(proxy_scores_path)

    # Merge on id
    merged = supg[["id", "label", "proxy_score"]].copy()
    merged = merged.merge(oracle[["id", "oracle_count"]], on="id", how="left")
    merged = merged.merge(proxy[["id", "proxy_count"]], on="id", how="left")

    # Select statistic_value
    if statistic_value_col == "oracle_count" and "oracle_count" in merged.columns:
        merged["statistic_value"] = merged["oracle_count"]
        source = "oracle_count"
    elif statistic_value_col == "proxy_count" and "proxy_count" in merged.columns:
        merged["statistic_value"] = merged["proxy_count"]
        source = "proxy_count"
    else:
        merged["statistic_value"] = merged["label"].astype(float)
        source = "label"

    # Drop rows with NaN statistic_value
    before = len(merged)
    merged = merged.dropna(subset=["statistic_value"])
    after = len(merged)
    if after < before:
        print(f"Warning: dropped {before - after} rows with NaN statistic_value")

    return merged[["id", "proxy_score", "label", "statistic_value"]], source


def run_single_trial(
    df: pd.DataFrame,
    method: str,
    num_strata: int,
    stage1_per_stratum: int,
    total_budget: int,
    n_bootstrap: int,
    alpha: float,
    seed: int,
) -> dict:
    """Run a single trial for Uniform, ABae-paper, or ABae-full_variance."""
    if method == "ABae-paper":
        result = run_abae(
            df, num_strata=num_strata,
            stage1_per_stratum=stage1_per_stratum,
            total_budget=total_budget,
            n_bootstrap=n_bootstrap,
            alpha=alpha,
            seed=seed,
            allocation_mode="paper",
        )
    elif method == "ABae-full_variance":
        result = run_abae(
            df, num_strata=num_strata,
            stage1_per_stratum=stage1_per_stratum,
            total_budget=total_budget,
            n_bootstrap=n_bootstrap,
            alpha=alpha,
            seed=seed,
            allocation_mode="full_variance",
        )
    elif method == "Uniform":
        result = run_uniform_aggregation(
            df, total_budget=total_budget,
            n_bootstrap=n_bootstrap,
            alpha=alpha,
            seed=seed,
        )
    else:
        raise ValueError(f"Unknown method: {method}")

    metrics = compute_aggregation_metrics(result)
    result.update(metrics)
    result["method"] = method
    result["seed"] = seed
    return result


def main():
    parser = argparse.ArgumentParser(description="ABae BDD100K real-frame smoke experiment")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    parser.add_argument("--supg-source", type=str, default=None)
    parser.add_argument("--oracle-scores", type=str, default=None)
    parser.add_argument("--proxy-scores", type=str, default=None)
    parser.add_argument("--statistic-value-col", type=str, default="oracle_count")
    parser.add_argument("--budget", type=int, default=1000)
    parser.add_argument("--num-strata", type=int, default=10)
    parser.add_argument("--stage1-per-stratum", type=int, default=None)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--bootstrap-trials", type=int, default=300)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", type=str, default="garc_eval/outputs/abae_bdd100k_smoke")
    args = parser.parse_args()

    # Load config if provided
    if args.config:
        with open(args.config) as f:
            cfg = yaml.safe_load(f)
        for k, v in cfg.items():
            if hasattr(args, k.replace("-", "_")):
                setattr(args, k.replace("-", "_"), v)

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Default paths
    base = pathlib.Path("garc_eval/outputs/bdd100k_smoke")
    supg_source = args.supg_source or str(base / "supg_source.csv")
    oracle_scores = args.oracle_scores or str(base / "oracle_scores.parquet")
    proxy_scores = args.proxy_scores or str(base / "proxy_scores.parquet")

    # Verify files exist
    for p, name in [(supg_source, "supg_source"), (oracle_scores, "oracle_scores"), (proxy_scores, "proxy_scores")]:
        if not pathlib.Path(p).exists():
            print(f"ERROR: {name} not found at {p}")
            sys.exit(1)

    # Load data
    print("=== Loading BDD100K cached data ===")
    df, stat_source = load_bdd100k_data(
        supg_source, oracle_scores, proxy_scores,
        statistic_value_col=args.statistic_value_col,
    )
    print(f"Loaded {len(df)} rows")
    print(f"Statistic value source: {stat_source}")
    print(f"Positive rate: {df['label'].mean():.4f}")

    # Stage 1 per stratum default
    s1_per = args.stage1_per_stratum
    if s1_per is None:
        s1_per = max(20, int(args.budget * 0.15 / args.num_strata))

    # Exact answers
    positives = df[df["label"] == 1]
    exact_avg = float(positives["statistic_value"].mean()) if len(positives) > 0 else 0.0
    exact_count = float(len(positives))
    print(f"Exact AVG({stat_source} | label=1): {exact_avg:.4f}")
    print(f"Exact COUNT(label=1): {exact_count:.0f}")

    # Save config
    config = {
        "supg_source": supg_source,
        "oracle_scores": oracle_scores,
        "proxy_scores": proxy_scores,
        "statistic_value_col": args.statistic_value_col,
        "statistic_value_source": stat_source,
        "N": len(df),
        "K_predicate": 13,
        "positive_rate": float(df["label"].mean()),
        "exact_avg": exact_avg,
        "exact_count": exact_count,
        "budget": args.budget,
        "num_strata": args.num_strata,
        "stage1_per_stratum": s1_per,
        "trials": args.trials,
        "bootstrap_trials": args.bootstrap_trials,
        "alpha": args.alpha,
        "seed": args.seed,
        "yolo_rerun": False,
    }
    with open(outdir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Run experiments
    methods = ["Uniform", "ABae-paper", "ABae-full_variance"]
    all_results = []

    print(f"\n=== Running experiments (budget={args.budget}, strata={args.num_strata}, s1={s1_per}) ===")
    for method in methods:
        print(f"  Running {method} ({args.trials} trials)...")
        for trial in range(args.trials):
            seed = args.seed + trial * 100
            result = run_single_trial(
                df, method,
                num_strata=args.num_strata,
                stage1_per_stratum=s1_per,
                total_budget=args.budget,
                n_bootstrap=args.bootstrap_trials,
                alpha=args.alpha,
                seed=seed,
            )
            result["budget"] = args.budget
            all_results.append(result)

            if (trial + 1) % max(1, args.trials // 5) == 0 or trial == 0:
                print(f"    trial {trial}: avg_est={result['avg_estimate']:.4f} "
                      f"count_est={result['count_estimate']:.0f} "
                      f"avg_ci=[{result['avg_ci_lower']:.4f}, {result['avg_ci_upper']:.4f}]")

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(outdir / "per_trial_results.csv", index=False)
    print(f"\nSaved per_trial_results.csv")

    # Summarize
    summary_rows = []
    for method in methods:
        mask = results_df["method"] == method
        trial_data = results_df[mask]
        trial_metrics = []
        for _, row in trial_data.iterrows():
            trial_metrics.append({
                "avg_abs_error": row["avg_abs_error"],
                "avg_rel_error": row["avg_rel_error"],
                "avg_ci_width": row["avg_ci_width"],
                "avg_ci_covers_exact": row["avg_ci_covers_exact"],
                "count_abs_error": row["count_abs_error"],
                "count_rel_error": row["count_rel_error"],
                "count_ci_width": row["count_ci_width"],
                "count_ci_covers_exact": row["count_ci_covers_exact"],
            })
        summary = summarize_trials_metrics(trial_metrics)
        summary["method"] = method
        summary["budget"] = args.budget
        summary_rows.append(summary)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(outdir / "summary.csv", index=False)
    print("Saved summary.csv")

    # Generate report
    paper_row = summary_df[summary_df["method"] == "ABae-paper"].iloc[0]
    uni_row = summary_df[summary_df["method"] == "Uniform"].iloc[0]
    fv_row = summary_df[summary_df["method"] == "ABae-full_variance"].iloc[0]

    report_lines = [
        "# ABae BDD100K Real-Frame Smoke Report\n",
        "\n## Allocation Modes\n",
        "- **ABae-paper** (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.",
        "- **ABae-full_variance**: w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.",
        "- **Uniform**: baseline random sampling.\n",
        "\n## Data Source\n",
        f"- supg_source: `{supg_source}`",
        f"- oracle_scores: `{oracle_scores}`",
        f"- proxy_scores: `{proxy_scores}`",
        f"- **YOLO rerun: NO** (using cached data only)\n",
        "\n## Query\n",
        f"- predicate: count_car(frame) >= 13",
        f"- N: {len(df)}",
        f"- positive rate: {df['label'].mean():.4f} ({int(exact_count)} / {len(df)})",
        f"- statistic_value source: {stat_source}\n",
        "\n## Exact Answers\n",
        f"- AVG({stat_source} | label=1): {exact_avg:.4f}",
        f"- COUNT(label=1): {exact_count:.0f}\n",
        "\n## Experiment Parameters\n",
        f"- budget: {args.budget}",
        f"- num_strata: {args.num_strata}",
        f"- stage1_per_stratum: {s1_per}",
        f"- trials: {args.trials}",
        f"- bootstrap_trials: {args.bootstrap_trials}",
        f"- alpha: {args.alpha}\n",
        "\n## Results\n",
        "| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |",
        "|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|",
    ]

    for method in methods:
        row = summary_df[summary_df["method"] == method].iloc[0]
        report_lines.append(
            f"| {method} "
            f"| {row['avg_mean_abs_error']:.4f} "
            f"| {row['avg_mean_rel_error']:.4f} "
            f"| {row['avg_mean_ci_width']:.4f} "
            f"| {row['avg_coverage_rate']:.2%} "
            f"| {row['count_mean_abs_error']:.1f} "
            f"| {row['count_mean_rel_error']:.4f} "
            f"| {row['count_mean_ci_width']:.1f} "
            f"| {row['count_coverage_rate']:.2%} |"
        )

    avg_improved = paper_row["avg_mean_ci_width"] < uni_row["avg_mean_ci_width"]
    count_improved = paper_row["count_mean_ci_width"] < uni_row["count_mean_ci_width"]

    report_lines.extend([
        "\n## Qualitative Assessment (ABae-paper vs Uniform)\n",
        f"- ABae-paper AVG CI width < Uniform: {avg_improved} "
        f"({paper_row['avg_mean_ci_width']:.4f} vs {uni_row['avg_mean_ci_width']:.4f})",
        f"- ABae-paper COUNT CI width < Uniform: {count_improved} "
        f"({paper_row['count_mean_ci_width']:.1f} vs {uni_row['count_mean_ci_width']:.1f})",
    ])

    if avg_improved and count_improved:
        report_lines.append("- **ABae-paper improves over uniform sampling** on this benchmark.\n")
    elif avg_improved or count_improved:
        report_lines.append("- **ABae-paper partially improves** over uniform sampling.\n")
    else:
        report_lines.append("- **ABae-paper does not improve** over uniform. "
                            "Check proxy-label correlation and allocation.\n")

    report_lines.extend([
        "\n## ABae-paper vs ABae-full_variance\n",
        f"- paper AVG CI width: {paper_row['avg_mean_ci_width']:.4f}, "
        f"full_variance: {fv_row['avg_mean_ci_width']:.4f}",
        f"- paper COUNT CI width: {paper_row['count_mean_ci_width']:.1f}, "
        f"full_variance: {fv_row['count_mean_ci_width']:.1f}",
        f"- paper AVG coverage: {paper_row['avg_coverage_rate']:.2%}, "
        f"full_variance: {fv_row['avg_coverage_rate']:.2%}",
        f"- paper COUNT coverage: {paper_row['count_coverage_rate']:.2%}, "
        f"full_variance: {fv_row['count_coverage_rate']:.2%}\n",
    ])

    # COUNT coverage warnings
    report_lines.append("\n## COUNT Coverage Warnings\n")
    any_warning = False
    for method in methods:
        row = summary_df[summary_df["method"] == method].iloc[0]
        count_cov = row["count_coverage_rate"]
        if count_cov < 0.95:
            any_warning = True
            report_lines.append(
                f"- **WARNING**: {method}: COUNT coverage = {count_cov:.2%} < 95%. "
                f"CI is anti-conservative (too narrow). Interpret COUNT CI with caution."
            )
    if not any_warning:
        report_lines.append("- All methods have COUNT coverage >= 95%.\n")
    else:
        report_lines.append(
            "\n**Note**: Percentile bootstrap CI for COUNT can be anti-conservative with "
            "stratified sampling. ABae-paper mode (T_k ∝ sqrt(p_hat_k * sigma_hat_k)) allocates "
            "more samples to high-positive strata, reducing CI width but potentially under-estimating "
            "between-stratum variability in bootstrap resampling.\n"
        )

    report_lines.extend([
        "\n## Limitations\n",
        "- BDD100K is an image-level road-scene benchmark, not a temporal clip benchmark.",
        "- The cached oracle is YOLOv8x pseudo-oracle, not human ground truth.",
        "- ABae is for aggregation with expensive predicates, not selection or clip queries.",
        f"- statistic_value source ({stat_source}) is cached oracle-derived for offline reproduction; "
        "ABae sampling simulates oracle access by reading cached labels/counts only for sampled records.",
        "- refe_repos/abae not found; implementation based on paper description only.",
        "- COUNT bootstrap CI may be anti-conservative with stratified sampling.\n",
        f"\n---\nGenerated: {pd.Timestamp.now().isoformat()}\n",
    ])

    (outdir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print("Saved report.md")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
