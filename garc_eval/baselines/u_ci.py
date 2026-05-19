"""U-CI baseline: uniform sampling + normal-approximation confidence interval.

NOTE: U-CI-RT implemented as best-effort baseline; verify formula before
publication use.  The normal-approximation CI for recall threshold selection
is a standard approach but the exact conservative correction may differ from
the original NOSCOPE paper.
"""

import math

import numpy as np
import pandas as pd


def u_ci_rt(
    df: pd.DataFrame,
    budget: int,
    gamma: float,
    delta: float = 0.05,
    seed: int = 0,
) -> dict:
    """U-CI for recall target (RT).

    1. Uniform random sample `budget` rows.
    2. Read oracle labels on sample.
    3. Sort by proxy_score descending.
    4. Use normal-approximation CI to find conservative recall threshold:
       at each candidate threshold, compute recall estimate and its CI lower
       bound; select the largest threshold where the CI lower bound >= gamma.

    Returns dict with keys: selected_ids, tau, sampled_ids
    """
    rng = np.random.RandomState(seed)
    n = len(df)
    sample_size = min(budget, n)
    sampled_idx = rng.choice(n, size=sample_size, replace=False)
    sampled_ids = df["id"].values[sampled_idx]

    sample_df = df.iloc[sampled_idx].copy()
    sample_df = sample_df.sort_values("proxy_score", ascending=False).reset_index(drop=True)

    sample_labels = sample_df["label"].values
    sample_scores = sample_df["proxy_score"].values

    total_pos = np.sum(sample_labels)
    if total_pos == 0:
        return {
            "selected_ids": np.array([], dtype=df["id"].dtype),
            "tau": 1.0,
            "sampled_ids": sampled_ids,
        }

    # z-value for 1-delta confidence
    from scipy.stats import norm
    z = norm.ppf(1 - delta / 2)

    # For each prefix of size k, the recall estimate is:
    #   recall_hat = (cum_pos_k / total_pos_sample) where total_pos_sample
    #   is estimated as total_pos * (n / sample_size).
    # We use the CI on the fraction of positives in the prefix relative to
    # the total positives in the sample, adjusted by the finite-population
    # correction.

    best_tau_idx = 0
    found = False
    for i in range(sample_size):
        k = i + 1
        cum_pos = np.sum(sample_labels[: k])
        # proportion of selected positives among all sampled positives
        p_hat = cum_pos / total_pos
        # standard error with finite population correction
        se = math.sqrt(p_hat * (1 - p_hat) / total_pos) if total_pos > 1 else 0
        ci_lower = p_hat - z * se
        if ci_lower >= gamma:
            best_tau_idx = i
            found = True

    if not found:
        # If no threshold passes the CI test, return empty set
        return {
            "selected_ids": np.array([], dtype=df["id"].dtype),
            "tau": 1.0,
            "sampled_ids": sampled_ids,
        }

    tau = float(sample_scores[best_tau_idx])

    full_mask = df["proxy_score"].values >= tau
    proxy_selected = df["id"].values[full_mask]

    sample_pos_mask = sample_df["label"].values == 1
    sample_pos_ids = sample_df["id"].values[sample_pos_mask]

    selected_ids = np.unique(np.concatenate([proxy_selected, sample_pos_ids]))

    return {
        "selected_ids": selected_ids,
        "tau": tau,
        "sampled_ids": sampled_ids,
    }
