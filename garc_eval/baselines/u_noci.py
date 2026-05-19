"""U-NOCI baseline: uniform sampling + empirical threshold, no confidence interval.

This corresponds to the NOSCOPE / probabilistic predicates style baseline
in the SUPG paper — no statistical guarantees.
"""

import numpy as np
import pandas as pd


def u_noci_rt(
    df: pd.DataFrame,
    budget: int,
    gamma: float,
    seed: int = 0,
) -> dict:
    """U-NOCI for recall target (RT).

    1. Uniform random sample `budget` rows.
    2. Read oracle labels on sample.
    3. Sort by proxy_score descending.
    4. Find the largest threshold tau such that empirical recall >= gamma
       on the sample.
    5. Return ids in the full dataset with proxy_score >= tau,
       union sample positives.

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
    total_pos = np.sum(sample_labels)
    if total_pos == 0:
        return {
            "selected_ids": np.array([], dtype=df["id"].dtype),
            "tau": 1.0,
            "sampled_ids": sampled_ids,
        }

    target = gamma * total_pos
    cum_pos = 0
    tau_idx = sample_size
    for i in range(sample_size):
        cum_pos += sample_labels[i]
        if cum_pos >= target:
            tau_idx = i
            break

    tau = float(sample_df["proxy_score"].values[tau_idx])

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


def u_noci_pt(
    df: pd.DataFrame,
    budget: int,
    gamma: float,
    seed: int = 0,
) -> dict:
    """U-NOCI for precision target (PT).

    1. Uniform random sample `budget` rows.
    2. Read oracle labels on sample.
    3. Sort by proxy_score descending.
    4. Scan thresholds to find the one where empirical precision >= gamma
       and returns the most results.
    5. Return ids in the full dataset with proxy_score >= tau,
       union sample positives.

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

    # Find threshold: scan from top, find the largest prefix with precision >= gamma
    best_tau_idx = 0
    for i in range(sample_size):
        k = i + 1
        prec = np.sum(sample_labels[:k]) / k
        if prec >= gamma:
            best_tau_idx = i

    if best_tau_idx == 0 and np.sum(sample_labels[:1]) / 1 < gamma:
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
