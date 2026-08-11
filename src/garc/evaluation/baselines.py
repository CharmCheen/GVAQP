"""Evaluation-only SCAN baselines; none is selected by video identity."""

from garc.scan.policy import EVALUATION_BASELINES, SafeCoverageConfig, SafeCoveragePolicy


def make_baseline(name: str) -> SafeCoveragePolicy:
    if name not in EVALUATION_BASELINES:
        raise ValueError(f"not an evaluation baseline: {name}")
    return SafeCoveragePolicy(SafeCoverageConfig(name))
