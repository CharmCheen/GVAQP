from garc_eval.scan_confirm_controller.common_utility import (
    CommonUtilityModel, FixedUpperCostEstimator, SafeTraceReplayEnvironment,
    predicted_common_values,
)


def test_safe_bound_exceeds_all_development_samples():
    estimator = FixedUpperCostEstimator([1.0, 2.0, 5.0])
    assert estimator.estimate() == 5.25


def test_common_values_use_terminal_utility_units():
    env = SafeTraceReplayEnvironment("V0_Q1", 60)
    env.step(__import__("garc_eval.scan_confirm_controller.action", fromlist=["Action"]).Action.SCAN)
    model = CommonUtilityModel([])
    values = predicted_common_values(env, model)
    assert 0 <= values["predicted_scan_value"] <= 10
    assert 0 <= values["predicted_confirm_value"] <= 1
    assert values["service_slots_after_scan"] <= values["service_slots_before"]

