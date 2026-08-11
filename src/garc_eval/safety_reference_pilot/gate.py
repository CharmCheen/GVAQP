from __future__ import annotations

from typing import Any


LOWER_IS_BETTER = {
    "hard_negative_false_positive_rate_max",
    "multi_event_miss_rate_max",
    "high_confidence_error_rate_max",
    "boundary_mae_frames_max",
}


def evaluate_gate(
    thresholds: dict[str, float],
    observed: dict[str, float],
    automatic_failures: dict[str, bool],
) -> dict[str, Any]:
    """Evaluate already-computed audit metrics without silently imputing data."""
    missing = sorted(set(thresholds) - set(observed))
    checks: dict[str, bool] = {}
    for name, threshold in thresholds.items():
        if name not in observed:
            continue
        value = observed[name]
        checks[name] = value <= threshold if name in LOWER_IS_BETTER else value >= threshold
    active_failures = sorted(name for name, active in automatic_failures.items() if active)
    passed = not missing and all(checks.values()) and not active_failures
    return {
        "status": "PASS" if passed else "BLOCK",
        "metric_checks": checks,
        "missing_metrics": missing,
        "active_automatic_failures": active_failures,
    }

