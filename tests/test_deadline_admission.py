import math

from frozen_reference import source_admission, source_linear_quantile
from garc.controller.deadline import CausalCostEstimator, action_fits, linear_quantile


def test_deadline_parity_for_frozen_valid_cost_domain():
    for estimate in (0.0, .1, 1.0, 10.0, math.inf):
        for remaining in (0.0, .1, 1.0, 10.0):
            assert action_fits(estimate, remaining) == source_admission(estimate, remaining)


def test_invalid_negative_estimate_is_rejected():
    assert not action_fits(-1, 10)


def test_cost_quantile_and_global_fallback_parity():
    samples = [1.0, 2.0, 4.0, 10.0]
    for quantile in (0.0, .25, .5, .9, 1.0):
        assert linear_quantile(samples, quantile) == source_linear_quantile(samples, quantile)
    estimator = CausalCostEstimator(samples)
    assert estimator.estimate() == source_linear_quantile(samples, .9)
    estimator.observe(3.0)
    estimator.observe(7.0)
    assert estimator.estimate() == source_linear_quantile([3.0, 7.0], .9)
