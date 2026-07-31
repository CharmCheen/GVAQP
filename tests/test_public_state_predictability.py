from __future__ import annotations

import math

import numpy as np

from public_state_predictability import expected_metrics, sigmoid


def test_oracle_action_has_zero_regret_and_perfect_weighted_accuracy():
    delta = np.asarray([0.2, -0.1, 0.0])
    probability_scan = np.asarray([1.0, 0.0, 0.0])
    metrics = expected_metrics(delta, probability_scan)
    assert metrics["decision_regret"] == 0.0
    assert metrics["weighted_sign_accuracy"] == 1.0


def test_wrong_action_regret_is_absolute_advantage():
    metrics = expected_metrics(np.asarray([0.2, -0.1]), np.asarray([0.0, 1.0]))
    assert math.isclose(metrics["decision_regret"], 0.15)
    assert metrics["weighted_sign_accuracy"] == 0.0


def test_sigmoid_is_bounded_and_monotonic():
    values = sigmoid(np.asarray([-1.0, 0.0, 1.0]), 0.1)
    assert 0.0 < values[0] < values[1] < values[2] < 1.0
