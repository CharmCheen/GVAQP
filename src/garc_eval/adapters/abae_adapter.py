"""ABae minimal adapter: single-predicate stratified sampling for aggregation.

Supports AVG(statistic_value) WHERE label=1 and COUNT(*) WHERE label=1.

Algorithm (faithful to ABae paper, Algorithm 1):
1. Sort by proxy_score, split into K quantile strata.
2. Stage 1: sample N1 per stratum without replacement.
   Estimate p_hat_k (positive rate), mu_hat_k (mean statistic | positive),
   sigma_hat_k (std statistic | positive) per stratum.
3. Stage 2: allocate remaining budget using plug-in optimal allocation.
   Default ("paper") mode: T_k ∝ sqrt(p_hat_k * sigma_hat_k)
   This matches ABae Algorithm 1 single-predicate allocation.
4. Final estimates from pooled stage1+stage2 samples.
5. Bootstrap percentile CI from sampled records only.

Allocation modes:
- "paper" (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.
- "full_variance": w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.
- "uniform": equal weight per stratum (baseline only).
"""

import numpy as np
import pandas as pd
from typing import Optional


def quantile_stratify(
    df: pd.DataFrame,
    num_strata: int,
    score_col: str = "proxy_score",
) -> pd.DataFrame:
    """Assign each row to a quantile stratum based on score_col.

    Returns a copy of df with an added 'stratum' column (0-indexed).
    Handles ties by using rank-based quantile assignment.
    """
    df = df.copy()
    # Use rank to handle ties, then assign quantile strata
    ranks = df[score_col].rank(method="first")
    # Assign strata: 0..K-1 based on quantile
    df["stratum"] = ((ranks - 1) / len(df) * num_strata).astype(int)
    df["stratum"] = df["stratum"].clip(0, num_strata - 1)
    return df


def stage1_sample(
    df: pd.DataFrame,
    num_strata: int,
    n1_per_stratum: int,
    rng: np.random.RandomState,
) -> tuple[pd.DataFrame, list]:
    """Stage 1: sample n1_per_stratum records from each stratum without replacement.

    Returns (sampled_df, stratum_info_list).
    """
    sampled_parts = []
    stratum_info = []
    for k in range(num_strata):
        stratum_df = df[df["stratum"] == k]
        n_k = len(stratum_df)
        if n_k == 0:
            stratum_info.append({
                "stratum": k, "n_k": 0, "n1_sampled": 0,
                "positive_count": 0, "p_hat": 0.0, "mu_hat": 0.0, "sigma_hat": 0.0,
            })
            continue
        n1 = min(n1_per_stratum, n_k)
        sampled_idx = rng.choice(stratum_df.index.values, size=n1, replace=False)
        sampled = stratum_df.loc[sampled_idx]
        sampled_parts.append(sampled)

        # Compute stage 1 estimates
        positives = sampled[sampled["label"] == 1]
        positive_count = len(positives)
        if positive_count > 0:
            p_hat = positive_count / n1
            mu_hat = float(positives["statistic_value"].mean())
            sigma_hat = float(positives["statistic_value"].std(ddof=1)) if positive_count > 1 else 0.0
        else:
            p_hat = 0.0
            mu_hat = 0.0
            sigma_hat = 0.0

        stratum_info.append({
            "stratum": k, "n_k": n_k, "n1_sampled": n1,
            "positive_count": positive_count,
            "p_hat": p_hat, "mu_hat": mu_hat, "sigma_hat": sigma_hat,
        })

    if sampled_parts:
        sampled_df = pd.concat(sampled_parts, ignore_index=False)
    else:
        sampled_df = pd.DataFrame(columns=df.columns)
    return sampled_df, stratum_info


def allocate_stage2(
    stratum_info: list,
    total_budget: int,
    stage1_total: int,
    rng: np.random.RandomState,
    allocation_mode: str = "paper",
) -> list:
    """Compute stage 2 allocation per stratum using plug-in optimal allocation.

    Allocation modes:
    - "paper" (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.
    - "full_variance": w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.
    - "uniform": equal weight per stratum (baseline only).

    Edge cases (all modes except uniform):
    - When sigma_hat_k = 0 but p_hat_k > 0: small discovery weight.
    - When p_hat_k = 0: small discovery weight proportional to n_k.

    Returns list of (stratum, n2_allocation) tuples and fallback flag.
    """
    stage2_remaining = total_budget - stage1_total
    if stage2_remaining <= 0:
        return [(info["stratum"], 0) for info in stratum_info]

    weights = []
    for info in stratum_info:
        if info["n_k"] == 0:
            weights.append(0.0)
            continue
        p = info["p_hat"]
        mu = info["mu_hat"]
        sigma = info["sigma_hat"]

        if allocation_mode == "uniform":
            w = float(info["n_k"])
        elif allocation_mode == "paper":
            # ABae Algorithm 1: T_k ∝ sqrt(p_k * sigma_k)
            if p > 0 and sigma > 0:
                w = np.sqrt(p * sigma)
            elif p > 0:
                # p>0 but sigma=0: small discovery weight
                w = np.sqrt(p * 1e-6)
            else:
                # p=0: no positives seen, use small discovery weight
                w = 1e-6
        elif allocation_mode == "full_variance":
            # Exploratory variant: full variance of Y = statistic_value * I(label=1)
            # Var(Y_k) = p_k * sigma_k^2 + p_k * (1 - p_k) * mu_k^2
            if p > 0 and (sigma > 0 or mu > 0):
                var_y = p * sigma**2 + p * (1 - p) * mu**2
                w = info["n_k"] * np.sqrt(var_y)
            elif p > 0:
                w = info["n_k"] * np.sqrt(p * (1 - p))
            else:
                w = info["n_k"] * 0.01
        else:
            raise ValueError(f"Unknown allocation_mode: {allocation_mode}")
        weights.append(w)

    weights = np.array(weights, dtype=float)
    total_w = weights.sum()

    fallback = False
    if total_w <= 0:
        # Fallback: uniform allocation proportional to n_k
        weights = np.array([info["n_k"] for info in stratum_info], dtype=float)
        total_w = weights.sum()
        fallback = True

    if total_w <= 0:
        return [(info["stratum"], 0) for info in stratum_info]

    # Proportional allocation, respecting stratum capacity
    raw_alloc = weights / total_w * stage2_remaining
    alloc = []
    for i, info in enumerate(stratum_info):
        # Can't sample more than remaining unsampled records
        max_n2 = info["n_k"] - info["n1_sampled"]
        n2 = min(int(round(raw_alloc[i])), max(0, max_n2))
        alloc.append((info["stratum"], n2))

    return alloc, fallback


def stage2_sample(
    df: pd.DataFrame,
    stage1_indices: set,
    allocation: list,
    rng: np.random.RandomState,
) -> pd.DataFrame:
    """Stage 2: sample additional records from each stratum, avoiding stage 1 samples."""
    sampled_parts = []
    for stratum_id, n2 in allocation:
        if n2 <= 0:
            continue
        stratum_df = df[df["stratum"] == stratum_id]
        # Exclude stage 1 samples
        available = stratum_df[~stratum_df.index.isin(stage1_indices)]
        if len(available) == 0:
            continue
        n2 = min(n2, len(available))
        sampled_idx = rng.choice(available.index.values, size=n2, replace=False)
        sampled_parts.append(available.loc[sampled_idx])

    if sampled_parts:
        return pd.concat(sampled_parts, ignore_index=False)
    return pd.DataFrame(columns=df.columns)


def compute_final_estimates(
    df: pd.DataFrame,
    sampled_df: pd.DataFrame,
    num_strata: int,
) -> dict:
    """Compute final AVG and COUNT estimates from pooled samples.

    AVG = sum_k n_k * p_hat_k * mu_hat_k / sum_k n_k * p_hat_k
    COUNT = sum_k n_k * p_hat_k
    """
    total_n = len(df)
    avg_num = 0.0
    avg_den = 0.0
    count_hat = 0.0

    for k in range(num_strata):
        stratum_full = df[df["stratum"] == k]
        stratum_sampled = sampled_df[sampled_df["stratum"] == k]
        n_k = len(stratum_full)
        n_sampled = len(stratum_sampled)

        if n_k == 0 or n_sampled == 0:
            continue

        positives = stratum_sampled[stratum_sampled["label"] == 1]
        positive_count = len(positives)
        p_hat = positive_count / n_sampled

        if positive_count > 0:
            mu_hat = float(positives["statistic_value"].mean())
        else:
            mu_hat = 0.0

        avg_num += n_k * p_hat * mu_hat
        avg_den += n_k * p_hat
        count_hat += n_k * p_hat

    avg_hat = avg_num / avg_den if avg_den > 0 else 0.0

    return {
        "avg_estimate": avg_hat,
        "count_estimate": count_hat,
    }


def bootstrap_ci(
    df: pd.DataFrame,
    sampled_df: pd.DataFrame,
    num_strata: int,
    n_bootstrap: int = 500,
    alpha: float = 0.05,
    rng: np.random.RandomState = None,
) -> dict:
    """Compute bootstrap percentile CI for AVG and COUNT.

    Resamples within each stratum from the already-sampled records.
    No oracle/model calls during bootstrap.
    """
    if rng is None:
        rng = np.random.RandomState(0)

    avg_samples = []
    count_samples = []

    for _ in range(n_bootstrap):
        # Resample within each stratum
        resampled_parts = []
        for k in range(num_strata):
            stratum_sampled = sampled_df[sampled_df["stratum"] == k]
            n_sampled = len(stratum_sampled)
            if n_sampled == 0:
                continue
            # Resample with replacement
            resample_idx = rng.choice(stratum_sampled.index.values, size=n_sampled, replace=True)
            resampled_parts.append(stratum_sampled.loc[resample_idx])

        if resampled_parts:
            resampled_df = pd.concat(resampled_parts, ignore_index=False)
        else:
            resampled_df = pd.DataFrame(columns=sampled_df.columns)

        est = compute_final_estimates(df, resampled_df, num_strata)
        avg_samples.append(est["avg_estimate"])
        count_samples.append(est["count_estimate"])

    avg_samples = np.array(avg_samples)
    count_samples = np.array(count_samples)

    ci_lower_alpha = alpha / 2 * 100
    ci_upper_alpha = (1 - alpha / 2) * 100

    return {
        "avg_ci_lower": float(np.percentile(avg_samples, ci_lower_alpha)),
        "avg_ci_upper": float(np.percentile(avg_samples, ci_upper_alpha)),
        "count_ci_lower": float(np.percentile(count_samples, ci_lower_alpha)),
        "count_ci_upper": float(np.percentile(count_samples, ci_upper_alpha)),
        "avg_bootstrap_std": float(np.std(avg_samples)),
        "count_bootstrap_std": float(np.std(count_samples)),
    }


def compute_allocation_weights(
    stratum_info: list,
    allocation_mode: str = "paper",
) -> np.ndarray:
    """Compute raw allocation weights for testing/inspection.

    Returns array of weights (not normalized) for each stratum.
    Useful for verifying that a given mode produces the expected formula.
    """
    weights = []
    for info in stratum_info:
        if info["n_k"] == 0:
            weights.append(0.0)
            continue
        p = info["p_hat"]
        mu = info["mu_hat"]
        sigma = info["sigma_hat"]

        if allocation_mode == "uniform":
            w = float(info["n_k"])
        elif allocation_mode == "paper":
            if p > 0 and sigma > 0:
                w = np.sqrt(p * sigma)
            elif p > 0:
                w = np.sqrt(p * 1e-6)
            else:
                w = 1e-6
        elif allocation_mode == "full_variance":
            if p > 0 and (sigma > 0 or mu > 0):
                var_y = p * sigma**2 + p * (1 - p) * mu**2
                w = info["n_k"] * np.sqrt(var_y)
            elif p > 0:
                w = info["n_k"] * np.sqrt(p * (1 - p))
            else:
                w = info["n_k"] * 0.01
        else:
            raise ValueError(f"Unknown allocation_mode: {allocation_mode}")
        weights.append(w)
    return np.array(weights, dtype=float)


def run_abae(
    df: pd.DataFrame,
    num_strata: int = 10,
    stage1_per_stratum: int = 10,
    total_budget: int = 1000,
    n_bootstrap: int = 500,
    alpha: float = 0.05,
    seed: int = 42,
    allocation_mode: str = "paper",
) -> dict:
    """Run the full ABae algorithm on a materialized table.

    Input df must have columns: id, proxy_score, label, statistic_value.

    Returns dict with estimates, CI, bootstrap info, and allocation details.
    """
    rng = np.random.RandomState(seed)
    required_cols = {"id", "proxy_score", "label", "statistic_value"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # Step 1: Stratification
    df_strat = quantile_stratify(df, num_strata)
    stage1_total = 0

    # Step 2: Stage 1 pilot sampling
    stage1_df, stratum_info = stage1_sample(
        df_strat, num_strata, stage1_per_stratum, rng
    )
    stage1_total = len(stage1_df)
    stage1_indices = set(stage1_df.index.values)

    # Step 3: Stage 2 allocation
    alloc_result = allocate_stage2(stratum_info, total_budget, stage1_total, rng, allocation_mode)
    if isinstance(alloc_result, tuple):
        allocation, fallback = alloc_result
    else:
        allocation = alloc_result
        fallback = False

    # Step 4: Stage 2 sampling
    stage2_df = stage2_sample(df_strat, stage1_indices, allocation, rng)

    # Pool samples
    if len(stage2_df) > 0:
        sampled_df = pd.concat([stage1_df, stage2_df], ignore_index=False)
    else:
        sampled_df = stage1_df

    # Step 5: Final estimates
    estimates = compute_final_estimates(df_strat, sampled_df, num_strata)

    # Step 6: Bootstrap CI
    boot_rng = np.random.RandomState(seed + 1000)
    ci = bootstrap_ci(df_strat, sampled_df, num_strata, n_bootstrap, alpha, boot_rng)

    # Exact answers from full table
    positives_full = df[df["label"] == 1]
    exact_avg = float(positives_full["statistic_value"].mean()) if len(positives_full) > 0 else 0.0
    exact_count = float(len(positives_full))

    return {
        "avg_estimate": estimates["avg_estimate"],
        "count_estimate": estimates["count_estimate"],
        "exact_avg": exact_avg,
        "exact_count": exact_count,
        "avg_ci_lower": ci["avg_ci_lower"],
        "avg_ci_upper": ci["avg_ci_upper"],
        "count_ci_lower": ci["count_ci_lower"],
        "count_ci_upper": ci["count_ci_upper"],
        "avg_bootstrap_std": ci["avg_bootstrap_std"],
        "count_bootstrap_std": ci["count_bootstrap_std"],
        "total_sampled": len(sampled_df),
        "stage1_sampled": stage1_total,
        "stage2_sampled": len(stage2_df),
        "allocation_fallback": fallback,
        "allocation_mode": allocation_mode,
        "stratum_info": stratum_info,
        "num_strata": num_strata,
        "seed": seed,
    }
