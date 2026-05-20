"""Metrics for aggregation query evaluation.

Computes absolute/relative error, CI width, and CI coverage for
AVG and COUNT aggregation estimates.
"""

import numpy as np


def compute_aggregation_metrics(result: dict) -> dict:
    """Compute error metrics from a single trial result.

    Input result must have keys:
        avg_estimate, count_estimate, exact_avg, exact_count,
        avg_ci_lower, avg_ci_upper, count_ci_lower, count_ci_upper

    Returns dict with per-trial error metrics.
    """
    exact_avg = result["exact_avg"]
    exact_count = result["exact_count"]

    avg_est = result["avg_estimate"]
    count_est = result["count_estimate"]

    avg_abs_error = abs(avg_est - exact_avg)
    count_abs_error = abs(count_est - exact_count)

    avg_rel_error = avg_abs_error / abs(exact_avg) if abs(exact_avg) > 1e-10 else 0.0
    count_rel_error = count_abs_error / abs(exact_count) if abs(exact_count) > 1e-10 else 0.0

    avg_ci_width = result["avg_ci_upper"] - result["avg_ci_lower"]
    count_ci_width = result["count_ci_upper"] - result["count_ci_lower"]

    avg_ci_covers = result["avg_ci_lower"] <= exact_avg <= result["avg_ci_upper"]
    count_ci_covers = result["count_ci_lower"] <= exact_count <= result["count_ci_upper"]

    return {
        "avg_abs_error": avg_abs_error,
        "avg_rel_error": avg_rel_error,
        "avg_ci_width": avg_ci_width,
        "avg_ci_covers_exact": avg_ci_covers,
        "count_abs_error": count_abs_error,
        "count_rel_error": count_rel_error,
        "count_ci_width": count_ci_width,
        "count_ci_covers_exact": count_ci_covers,
    }


def summarize_trials_metrics(trial_metrics: list[dict]) -> dict:
    """Aggregate metrics across multiple trials.

    Returns dict with mean error, mean CI width, coverage rate, failure rate.
    """
    n_trials = len(trial_metrics)
    if n_trials == 0:
        return {}

    def mean_of(key):
        vals = [m[key] for m in trial_metrics]
        return float(np.mean(vals))

    def rate_of(key):
        vals = [m[key] for m in trial_metrics]
        return float(np.mean(vals))

    return {
        "n_trials": n_trials,
        "avg_mean_abs_error": mean_of("avg_abs_error"),
        "avg_mean_rel_error": mean_of("avg_rel_error"),
        "avg_mean_ci_width": mean_of("avg_ci_width"),
        "avg_coverage_rate": rate_of("avg_ci_covers_exact"),
        "avg_failure_rate": 1.0 - rate_of("avg_ci_covers_exact"),
        "count_mean_abs_error": mean_of("count_abs_error"),
        "count_mean_rel_error": mean_of("count_rel_error"),
        "count_mean_ci_width": mean_of("count_ci_width"),
        "count_coverage_rate": rate_of("count_ci_covers_exact"),
        "count_failure_rate": 1.0 - rate_of("count_ci_covers_exact"),
    }
