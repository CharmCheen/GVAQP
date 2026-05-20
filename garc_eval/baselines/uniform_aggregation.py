"""Uniform random sampling baseline for aggregation queries.

Provides the same AVG/COUNT estimation and bootstrap CI as ABae,
but uses simple uniform random sampling instead of stratified sampling.
"""

import numpy as np
import pandas as pd


def run_uniform_aggregation(
    df: pd.DataFrame,
    total_budget: int = 1000,
    n_bootstrap: int = 500,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """Run uniform random sampling for aggregation.

    Input df must have columns: id, proxy_score, label, statistic_value.

    Returns dict with estimates, CI, and metadata.
    """
    rng = np.random.RandomState(seed)
    required_cols = {"id", "proxy_score", "label", "statistic_value"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    n = len(df)
    sample_size = min(total_budget, n)

    # Uniform sample without replacement
    sampled_idx = rng.choice(n, size=sample_size, replace=False)
    sampled_df = df.iloc[sampled_idx].copy()

    # Compute estimates from sample
    positives = sampled_df[sampled_df["label"] == 1]
    positive_count = len(positives)
    total_sampled = len(sampled_df)

    if positive_count > 0:
        p_hat = positive_count / total_sampled
        mu_hat = float(positives["statistic_value"].mean())
        avg_hat = mu_hat  # For AVG over positives, just use sample mean
        count_hat = p_hat * n  # Extrapolate to full population
    else:
        p_hat = 0.0
        mu_hat = 0.0
        avg_hat = 0.0
        count_hat = 0.0

    # Bootstrap CI
    boot_rng = np.random.RandomState(seed + 1000)
    avg_samples = []
    count_samples = []

    for _ in range(n_bootstrap):
        # Resample with replacement from the sampled records
        boot_idx = boot_rng.choice(total_sampled, size=total_sampled, replace=True)
        boot_df = sampled_df.iloc[boot_idx]

        boot_positives = boot_df[boot_df["label"] == 1]
        boot_positive_count = len(boot_positives)

        if boot_positive_count > 0:
            boot_p_hat = boot_positive_count / total_sampled
            boot_mu_hat = float(boot_positives["statistic_value"].mean())
            avg_samples.append(boot_mu_hat)
            count_samples.append(boot_p_hat * n)
        else:
            avg_samples.append(0.0)
            count_samples.append(0.0)

    avg_samples = np.array(avg_samples)
    count_samples = np.array(count_samples)

    ci_lower_alpha = alpha / 2 * 100
    ci_upper_alpha = (1 - alpha / 2) * 100

    # Exact answers
    positives_full = df[df["label"] == 1]
    exact_avg = float(positives_full["statistic_value"].mean()) if len(positives_full) > 0 else 0.0
    exact_count = float(len(positives_full))

    return {
        "avg_estimate": avg_hat,
        "count_estimate": count_hat,
        "exact_avg": exact_avg,
        "exact_count": exact_count,
        "avg_ci_lower": float(np.percentile(avg_samples, ci_lower_alpha)),
        "avg_ci_upper": float(np.percentile(avg_samples, ci_upper_alpha)),
        "count_ci_lower": float(np.percentile(count_samples, ci_lower_alpha)),
        "count_ci_upper": float(np.percentile(count_samples, ci_upper_alpha)),
        "avg_bootstrap_std": float(np.std(avg_samples)),
        "count_bootstrap_std": float(np.std(count_samples)),
        "total_sampled": total_sampled,
        "positive_count": positive_count,
        "seed": seed,
    }
