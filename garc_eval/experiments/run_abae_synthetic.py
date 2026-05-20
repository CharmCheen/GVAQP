"""ABae synthetic smoke experiment.

Generates synthetic data with proxy-label correlation and compares
ABae stratified sampling against uniform random sampling for
AVG and COUNT aggregation queries.

Usage:
    python -m garc_eval.experiments.run_abae_synthetic [--outdir path/to/output]
"""

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from garc_eval.adapters.abae_adapter import run_abae
from garc_eval.baselines.uniform_aggregation import run_uniform_aggregation
from garc_eval.metrics.aggregation_metrics import compute_aggregation_metrics, summarize_trials_metrics


def generate_synthetic_data(
    n: int = 100000,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic data with proxy-label correlation.

    proxy_score ~ Beta(2, 5) (skewed toward low values)
    Pr(label=1 | proxy_score=s) = sigmoid(a*(s - b))
    statistic_value = proxy_score + noise (correlated with proxy)
    """
    rng = np.random.RandomState(seed)

    # Proxy scores: Beta distribution skewed toward 0
    proxy_score = rng.beta(2, 5, size=n)

    # Label probability: sigmoid of proxy_score
    # a=10, b=0.55 gives ~13.5% positive rate with good stratum spread
    a, b = 10.0, 0.55
    label_prob = 1.0 / (1.0 + np.exp(-a * (proxy_score - b)))
    label = rng.binomial(1, label_prob).astype(int)

    # Statistic value: correlated with proxy + noise
    noise = rng.normal(0, 0.1, size=n)
    statistic_value = proxy_score + noise
    # Ensure non-negative
    statistic_value = np.maximum(statistic_value, 0.0)

    df = pd.DataFrame({
        "id": np.arange(n),
        "proxy_score": proxy_score,
        "label": label,
        "statistic_value": statistic_value,
    })

    positive_rate = label.mean()
    print(f"Generated synthetic data: N={n}, positive_rate={positive_rate:.4f}")
    return df


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
    parser = argparse.ArgumentParser(description="ABae synthetic smoke experiment")
    parser.add_argument("--n", type=int, default=100000, help="Dataset size")
    parser.add_argument("--budgets", type=int, nargs="+", default=[500, 1000, 2000])
    parser.add_argument("--num-strata", type=int, default=10)
    parser.add_argument("--stage1-per-stratum", type=int, default=None,
                        help="Stage 1 samples per stratum (default: max(20, budget*0.15/num_strata))")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--bootstrap-trials", type=int, default=300)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", type=str, default="garc_eval/outputs/abae_synthetic_smoke")
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Generate data
    print("=== Generating synthetic data ===")
    df = generate_synthetic_data(n=args.n, seed=args.seed)

    exact_positives = df[df["label"] == 1]
    exact_avg = float(exact_positives["statistic_value"].mean())
    exact_count = float(len(exact_positives))
    positive_rate = exact_count / len(df)
    print(f"Exact AVG (label=1): {exact_avg:.6f}")
    print(f"Exact COUNT (label=1): {exact_count:.0f}")
    print(f"Positive rate: {positive_rate:.4f}")

    # Save config
    config = {
        "n": args.n,
        "budgets": args.budgets,
        "num_strata": args.num_strata,
        "trials": args.trials,
        "bootstrap_trials": args.bootstrap_trials,
        "alpha": args.alpha,
        "seed": args.seed,
        "exact_avg": exact_avg,
        "exact_count": exact_count,
        "positive_rate": positive_rate,
    }
    with open(outdir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Run experiments
    methods = ["Uniform", "ABae-paper", "ABae-full_variance"]
    all_results = []

    for budget in args.budgets:
        s1_per = args.stage1_per_stratum
        if s1_per is None:
            s1_per = max(20, int(budget * 0.15 / args.num_strata))

        print(f"\n=== Budget={budget}, stage1_per_stratum={s1_per} ===")
        for method in methods:
            print(f"  Running {method} ({args.trials} trials)...")
            for trial in range(args.trials):
                seed = args.seed + trial * 100 + budget
                result = run_single_trial(
                    df, method,
                    num_strata=args.num_strata,
                    stage1_per_stratum=s1_per,
                    total_budget=budget,
                    n_bootstrap=args.bootstrap_trials,
                    alpha=args.alpha,
                    seed=seed,
                )
                result["budget"] = budget
                result["stage1_per_stratum"] = s1_per
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
    for budget in args.budgets:
        for method in methods:
            mask = (results_df["budget"] == budget) & (results_df["method"] == method)
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
            summary["budget"] = budget
            summary_rows.append(summary)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(outdir / "summary.csv", index=False)
    print("Saved summary.csv")

    # Generate report
    report_lines = [
        "# ABae Synthetic Smoke Report\n",
        "\n## Allocation Modes\n",
        "- **ABae-paper** (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.",
        "- **ABae-full_variance**: w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.",
        "- **Uniform**: baseline random sampling.\n",
        f"\n## Data Generation Parameters\n",
        f"- N: {args.n}",
        f"- proxy_score ~ Beta(2, 5)",
        f"- label_prob = sigmoid(10*(proxy_score - 0.55))",
        f"- statistic_value = proxy_score + N(0, 0.1)",
        f"- positive_rate: {positive_rate:.4f}",
        f"- seed: {args.seed}\n",
        f"\n## Exact Answers\n",
        f"- AVG(statistic_value | label=1): {exact_avg:.6f}",
        f"- COUNT(label=1): {exact_count:.0f}\n",
        f"\n## Experiment Parameters\n",
        f"- num_strata: {args.num_strata}",
        f"- trials: {args.trials}",
        f"- bootstrap_trials: {args.bootstrap_trials}",
        f"- alpha: {args.alpha}\n",
    ]

    for budget in args.budgets:
        s1_per = args.stage1_per_stratum or max(20, int(budget * 0.15 / args.num_strata))
        report_lines.append(f"\n## Budget={budget} (stage1_per_stratum={s1_per})\n")
        report_lines.append("| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |")
        report_lines.append("|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|")

        for method in methods:
            mask = (summary_df["budget"] == budget) & (summary_df["method"] == method)
            row = summary_df[mask].iloc[0]
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

    # Qualitative check: compare ABae-paper vs Uniform
    report_lines.append("\n## Qualitative Assessment (ABae-paper vs Uniform)\n")
    for budget in args.budgets:
        abae_row = summary_df[(summary_df["budget"] == budget) & (summary_df["method"] == "ABae-paper")].iloc[0]
        uni_row = summary_df[(summary_df["budget"] == budget) & (summary_df["method"] == "Uniform")].iloc[0]

        avg_improved = abae_row["avg_mean_ci_width"] < uni_row["avg_mean_ci_width"]
        count_improved = abae_row["count_mean_ci_width"] < uni_row["count_mean_ci_width"]

        report_lines.append(f"### Budget={budget}")
        report_lines.append(f"- ABae-paper AVG CI width < Uniform: {avg_improved} "
                            f"({abae_row['avg_mean_ci_width']:.4f} vs {uni_row['avg_mean_ci_width']:.4f})")
        report_lines.append(f"- ABae-paper COUNT CI width < Uniform: {count_improved} "
                            f"({abae_row['count_mean_ci_width']:.1f} vs {uni_row['count_mean_ci_width']:.1f})")

        if avg_improved and count_improved:
            report_lines.append("- **Result**: ABae-paper improves over uniform sampling as expected.\n")
        elif avg_improved or count_improved:
            report_lines.append("- **Result**: ABae-paper partially improves over uniform sampling.\n")
        else:
            report_lines.append("- **Result**: ABae-paper does not improve over uniform. "
                                "Check proxy-label correlation and allocation.\n")

    # ABae-paper vs ABae-full_variance comparison
    report_lines.append("\n## ABae-paper vs ABae-full_variance\n")
    for budget in args.budgets:
        paper_row = summary_df[(summary_df["budget"] == budget) & (summary_df["method"] == "ABae-paper")].iloc[0]
        fv_row = summary_df[(summary_df["budget"] == budget) & (summary_df["method"] == "ABae-full_variance")].iloc[0]

        report_lines.append(f"### Budget={budget}")
        report_lines.append(f"- paper AVG CI width: {paper_row['avg_mean_ci_width']:.4f}, "
                            f"full_variance: {fv_row['avg_mean_ci_width']:.4f}")
        report_lines.append(f"- paper COUNT CI width: {paper_row['count_mean_ci_width']:.1f}, "
                            f"full_variance: {fv_row['count_mean_ci_width']:.1f}")
        report_lines.append(f"- paper AVG coverage: {paper_row['avg_coverage_rate']:.2%}, "
                            f"full_variance: {fv_row['avg_coverage_rate']:.2%}")
        report_lines.append(f"- paper COUNT coverage: {paper_row['count_coverage_rate']:.2%}, "
                            f"full_variance: {fv_row['count_coverage_rate']:.2%}\n")

    # COUNT coverage warnings
    report_lines.append("\n## COUNT Coverage Warnings\n")
    any_warning = False
    for budget in args.budgets:
        for method in methods:
            mask = (summary_df["budget"] == budget) & (summary_df["method"] == method)
            row = summary_df[mask].iloc[0]
            count_cov = row["count_coverage_rate"]
            if count_cov < 0.95:
                any_warning = True
                report_lines.append(
                    f"- **WARNING**: {method} at budget={budget}: COUNT coverage = {count_cov:.2%} < 95%. "
                    f"CI is anti-conservative (too narrow). Interpret COUNT CI with caution."
                )
    if not any_warning:
        report_lines.append("- All methods/budgets have COUNT coverage >= 95%.\n")
    else:
        report_lines.append(
            "\n**Note**: Percentile bootstrap CI for COUNT can be anti-conservative with "
            "stratified sampling, especially when allocation is non-uniform. The paper mode "
            "(T_k ∝ sqrt(p_hat_k * sigma_hat_k)) allocates more samples to high-positive strata, "
            "which reduces CI width but can under-estimate between-stratum variability in bootstrap.\n"
        )

    report_lines.append(f"\n---\nGenerated: {pd.Timestamp.now().isoformat()}\n")
    (outdir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print("Saved report.md")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
