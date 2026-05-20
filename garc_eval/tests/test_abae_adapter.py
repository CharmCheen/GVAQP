"""Tests for ABae adapter and related modules.

Tests:
1. Quantile stratification does not lose records.
2. ABae returns finite estimates and CI on a small DataFrame.
3. Bootstrap CI lower <= estimate <= upper (or at least lower <= upper).
4. Uniform baseline runs without error.
5. Fixed random_seed produces reproducible results.
"""

import sys
import pathlib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def _make_small_df(n=200, seed=42):
    """Create a small test DataFrame."""
    rng = np.random.RandomState(seed)
    proxy_score = rng.beta(2, 5, size=n)
    label_prob = 1.0 / (1.0 + np.exp(-8.0 * (proxy_score - 0.4)))
    label = rng.binomial(1, label_prob).astype(int)
    statistic_value = proxy_score + rng.normal(0, 0.1, size=n)
    statistic_value = np.maximum(statistic_value, 0.0)

    return pd.DataFrame({
        "id": np.arange(n),
        "proxy_score": proxy_score,
        "label": label,
        "statistic_value": statistic_value,
    })


def test_quantile_stratification_no_loss():
    """Quantile stratification should not lose any records."""
    from garc_eval.adapters.abae_adapter import quantile_stratify

    df = _make_small_df(n=500)
    num_strata = 10
    df_strat = quantile_stratify(df, num_strata)

    assert len(df_strat) == len(df), f"Lost records: {len(df_strat)} vs {len(df)}"
    assert "stratum" in df_strat.columns
    assert df_strat["stratum"].nunique() <= num_strata
    assert df_strat["stratum"].min() >= 0
    assert df_strat["stratum"].max() < num_strata


def test_quantile_stratification_small_n():
    """Stratification works even when N < num_strata."""
    from garc_eval.adapters.abae_adapter import quantile_stratify

    df = _make_small_df(n=5)
    num_strata = 10
    df_strat = quantile_stratify(df, num_strata)

    assert len(df_strat) == len(df)
    # Should have at most N strata used
    assert df_strat["stratum"].nunique() <= len(df)


def test_abae_finite_estimates():
    """ABae should return finite estimates and CI on a small DataFrame."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=300, seed=123)
    result = run_abae(
        df, num_strata=5, stage1_per_stratum=10,
        total_budget=50, n_bootstrap=100, alpha=0.05, seed=42,
    )

    assert np.isfinite(result["avg_estimate"]), f"avg not finite: {result['avg_estimate']}"
    assert np.isfinite(result["count_estimate"]), f"count not finite: {result['count_estimate']}"
    assert np.isfinite(result["avg_ci_lower"]), f"avg_ci_lower not finite"
    assert np.isfinite(result["avg_ci_upper"]), f"avg_ci_upper not finite"
    assert np.isfinite(result["count_ci_lower"]), f"count_ci_lower not finite"
    assert np.isfinite(result["count_ci_upper"]), f"count_ci_upper not finite"


def test_bootstrap_ci_ordering():
    """Bootstrap CI should satisfy lower <= upper."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=300, seed=456)
    result = run_abae(
        df, num_strata=5, stage1_per_stratum=10,
        total_budget=50, n_bootstrap=100, alpha=0.05, seed=42,
    )

    assert result["avg_ci_lower"] <= result["avg_ci_upper"], \
        f"AVG CI: lower={result['avg_ci_lower']} > upper={result['avg_ci_upper']}"
    assert result["count_ci_lower"] <= result["count_ci_upper"], \
        f"COUNT CI: lower={result['count_ci_lower']} > upper={result['count_ci_upper']}"


def test_abae_estimate_reasonable():
    """ABae estimate should be in the right ballpark."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=1000, seed=789)
    positives = df[df["label"] == 1]
    if len(positives) == 0:
        pytest.skip("No positives in test data")

    exact_avg = positives["statistic_value"].mean()
    exact_count = float(len(positives))

    result = run_abae(
        df, num_strata=5, stage1_per_stratum=20,
        total_budget=100, n_bootstrap=200, alpha=0.05, seed=42,
    )

    # Estimates should be within 50% of exact (generous for small budget)
    if exact_avg > 0:
        assert abs(result["avg_estimate"] - exact_avg) / exact_avg < 0.5, \
            f"AVG estimate {result['avg_estimate']:.4f} too far from {exact_avg:.4f}"
    assert abs(result["count_estimate"] - exact_count) / max(exact_count, 1) < 0.5, \
        f"COUNT estimate {result['count_estimate']:.0f} too far from {exact_count:.0f}"


def test_uniform_baseline_runs():
    """Uniform baseline should run without error on a small DataFrame."""
    from garc_eval.baselines.uniform_aggregation import run_uniform_aggregation

    df = _make_small_df(n=200, seed=42)
    result = run_uniform_aggregation(
        df, total_budget=30, n_bootstrap=50, alpha=0.05, seed=42,
    )

    assert np.isfinite(result["avg_estimate"])
    assert np.isfinite(result["count_estimate"])
    assert result["avg_ci_lower"] <= result["avg_ci_upper"]
    assert result["count_ci_lower"] <= result["count_ci_upper"]


def test_fixed_seed_reproducibility():
    """Same seed should produce identical results."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=300, seed=42)

    result1 = run_abae(df, num_strata=5, stage1_per_stratum=10,
                       total_budget=50, n_bootstrap=100, alpha=0.05, seed=42)
    result2 = run_abae(df, num_strata=5, stage1_per_stratum=10,
                       total_budget=50, n_bootstrap=100, alpha=0.05, seed=42)

    assert result1["avg_estimate"] == result2["avg_estimate"], \
        f"avg_estimate not reproducible: {result1['avg_estimate']} vs {result2['avg_estimate']}"
    assert result1["count_estimate"] == result2["count_estimate"], \
        f"count_estimate not reproducible: {result1['count_estimate']} vs {result2['count_estimate']}"
    assert result1["avg_ci_lower"] == result2["avg_ci_lower"]
    assert result1["avg_ci_upper"] == result2["avg_ci_upper"]


def test_abae_exact_answers():
    """ABae should return correct exact answers from the full table."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=500, seed=42)
    positives = df[df["label"] == 1]
    exact_avg = float(positives["statistic_value"].mean()) if len(positives) > 0 else 0.0
    exact_count = float(len(positives))

    result = run_abae(df, num_strata=5, stage1_per_stratum=10,
                      total_budget=50, n_bootstrap=50, alpha=0.05, seed=42)

    assert abs(result["exact_avg"] - exact_avg) < 1e-10, \
        f"exact_avg mismatch: {result['exact_avg']} vs {exact_avg}"
    assert abs(result["exact_count"] - exact_count) < 1e-10, \
        f"exact_count mismatch: {result['exact_count']} vs {exact_count}"


def test_aggregation_metrics():
    """Test aggregation metrics computation."""
    from garc_eval.metrics.aggregation_metrics import compute_aggregation_metrics, summarize_trials_metrics

    result = {
        "avg_estimate": 0.5, "count_estimate": 100.0,
        "exact_avg": 0.48, "exact_count": 95.0,
        "avg_ci_lower": 0.4, "avg_ci_upper": 0.6,
        "count_ci_lower": 80.0, "count_ci_upper": 120.0,
    }
    metrics = compute_aggregation_metrics(result)

    assert abs(metrics["avg_abs_error"] - 0.02) < 1e-10
    assert metrics["avg_ci_covers_exact"] is True
    assert metrics["count_ci_covers_exact"] is True
    assert abs(metrics["avg_ci_width"] - 0.2) < 1e-10

    summary = summarize_trials_metrics([metrics])
    assert summary["n_trials"] == 1
    assert summary["avg_coverage_rate"] == 1.0
    assert summary["avg_failure_rate"] == 0.0


def test_paper_allocation_mode_weights():
    """Paper mode should produce weights proportional to sqrt(p*sigma)."""
    from garc_eval.adapters.abae_adapter import compute_allocation_weights

    # Create stratum_info with known p and sigma values
    stratum_info = [
        {"stratum": 0, "n_k": 100, "n1_sampled": 10, "positive_count": 5,
         "p_hat": 0.5, "mu_hat": 2.0, "sigma_hat": 1.0},
        {"stratum": 1, "n_k": 100, "n1_sampled": 10, "positive_count": 8,
         "p_hat": 0.8, "mu_hat": 3.0, "sigma_hat": 0.5},
        {"stratum": 2, "n_k": 100, "n1_sampled": 10, "positive_count": 3,
         "p_hat": 0.3, "mu_hat": 1.5, "sigma_hat": 2.0},
    ]

    weights = compute_allocation_weights(stratum_info, allocation_mode="paper")

    # Paper mode: T_k ∝ sqrt(p_k * sigma_k)
    expected_0 = np.sqrt(0.5 * 1.0)
    expected_1 = np.sqrt(0.8 * 0.5)
    expected_2 = np.sqrt(0.3 * 2.0)

    # Check weights are proportional to expected values
    ratios = weights / weights[0]
    expected_ratios = np.array([expected_0, expected_1, expected_2]) / expected_0

    np.testing.assert_allclose(ratios, expected_ratios, rtol=1e-10,
        err_msg="Paper mode weights not proportional to sqrt(p*sigma)")


def test_full_variance_allocation_mode_weights():
    """Full variance mode should produce weights proportional to n_k * sqrt(p*sigma^2 + p*(1-p)*mu^2)."""
    from garc_eval.adapters.abae_adapter import compute_allocation_weights

    stratum_info = [
        {"stratum": 0, "n_k": 100, "n1_sampled": 10, "positive_count": 5,
         "p_hat": 0.5, "mu_hat": 2.0, "sigma_hat": 1.0},
        {"stratum": 1, "n_k": 100, "n1_sampled": 10, "positive_count": 8,
         "p_hat": 0.8, "mu_hat": 3.0, "sigma_hat": 0.5},
        {"stratum": 2, "n_k": 100, "n1_sampled": 10, "positive_count": 3,
         "p_hat": 0.3, "mu_hat": 1.5, "sigma_hat": 2.0},
    ]

    weights = compute_allocation_weights(stratum_info, allocation_mode="full_variance")

    # Full variance: w_k = n_k * sqrt(p*sigma^2 + p*(1-p)*mu^2)
    def fv_weight(p, sigma, mu, n_k):
        var_y = p * sigma**2 + p * (1 - p) * mu**2
        return n_k * np.sqrt(var_y)

    expected_0 = fv_weight(0.5, 1.0, 2.0, 100)
    expected_1 = fv_weight(0.8, 0.5, 3.0, 100)
    expected_2 = fv_weight(0.3, 2.0, 1.5, 100)

    ratios = weights / weights[0]
    expected_ratios = np.array([expected_0, expected_1, expected_2]) / expected_0

    np.testing.assert_allclose(ratios, expected_ratios, rtol=1e-10,
        err_msg="Full variance mode weights not proportional to n_k*sqrt(p*sigma^2 + p*(1-p)*mu^2)")


def test_paper_is_default_allocation_mode():
    """Paper mode should be the default allocation mode."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=300, seed=42)
    result = run_abae(
        df, num_strata=5, stage1_per_stratum=10,
        total_budget=50, n_bootstrap=50, alpha=0.05, seed=42,
    )

    assert result["allocation_mode"] == "paper", \
        f"Default allocation_mode should be 'paper', got '{result['allocation_mode']}'"


def test_count_estimator_finite():
    """COUNT estimate and CI should be finite."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=500, seed=42)
    result = run_abae(
        df, num_strata=5, stage1_per_stratum=10,
        total_budget=50, n_bootstrap=100, alpha=0.05, seed=42,
    )

    assert np.isfinite(result["count_estimate"]), \
        f"COUNT estimate not finite: {result['count_estimate']}"
    assert np.isfinite(result["count_ci_lower"]), \
        f"COUNT CI lower not finite: {result['count_ci_lower']}"
    assert np.isfinite(result["count_ci_upper"]), \
        f"COUNT CI upper not finite: {result['count_ci_upper']}"


def test_count_ci_lower_leq_upper():
    """COUNT CI lower should be <= upper."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=500, seed=42)
    result = run_abae(
        df, num_strata=5, stage1_per_stratum=10,
        total_budget=50, n_bootstrap=100, alpha=0.05, seed=42,
    )

    assert result["count_ci_lower"] <= result["count_ci_upper"], \
        f"COUNT CI lower={result['count_ci_lower']} > upper={result['count_ci_upper']}"


def test_abae_allocation_mode_propagated():
    """allocation_mode should be returned in result dict."""
    from garc_eval.adapters.abae_adapter import run_abae

    df = _make_small_df(n=300, seed=42)
    for mode in ["paper", "full_variance"]:
        result = run_abae(
            df, num_strata=5, stage1_per_stratum=10,
            total_budget=50, n_bootstrap=50, alpha=0.05, seed=42,
            allocation_mode=mode,
        )
        assert result["allocation_mode"] == mode, \
            f"Expected allocation_mode='{mode}', got '{result['allocation_mode']}'"
