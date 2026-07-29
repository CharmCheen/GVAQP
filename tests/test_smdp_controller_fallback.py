from __future__ import annotations

import pytest

from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.smdp_controller import HeadroomGateFallbackController
from garc_eval.scan_confirm_controller.state import PublicState


def state(*, remaining: float, frontier: int) -> dict:
    return PublicState(
        remaining_budget_sec=remaining,
        frontier_size=frontier,
        estimated_scan_cost_sec=1.0,
        estimated_confirm_cost_sec=1.0,
    ).to_dict()


def controller(initial: dict) -> HeadroomGateFallbackController:
    value = HeadroomGateFallbackController(scan_cost_upper_sec=3.0, verify_cost_upper_sec=7.0)
    value.reset(float(initial["remaining_budget_sec"]), initial)
    return value


def test_gate_stop_uses_r4_when_both_productive_actions_are_legal():
    initial = state(remaining=30.0, frontier=2)
    decision = controller(initial).choose_action(initial)
    assert decision["baseline_action"] == Action.SCAN.value
    assert decision["final_action"] == Action.SCAN.value
    assert decision["shield_triggered"] is False
    assert decision["delta_mean"] is None
    assert decision["ood_status"] == "LEARNING_NOT_AUTHORIZED_HEADROOM_GATE_FAILED"


def test_productive_scan_is_blocked_without_reserved_verify_budget():
    initial = state(remaining=8.0, frontier=2)
    decision = controller(initial).choose_action(initial)
    assert decision["baseline_action"] == Action.SCAN.value
    assert decision["final_action"] == Action.CONFIRM.value
    assert decision["shield_triggered"] is True


def test_only_scan_is_selected_when_frontier_is_empty_and_reserve_fits():
    initial = state(remaining=10.0, frontier=0)
    decision = controller(initial).choose_action(initial)
    assert decision["final_action"] == Action.SCAN.value


def test_no_complete_action_fitting_upper_bound_stops():
    initial = state(remaining=6.0, frontier=3)
    decision = controller(initial).choose_action(initial)
    assert decision["final_action"] == Action.STOP.value
    assert decision["shield_triggered"] is True


def test_fallback_rejects_future_or_evaluator_only_fields():
    initial = state(remaining=30.0, frontier=2)
    value = controller(initial)
    initial["future_confirm_outcomes"] = [1]
    with pytest.raises(ValueError):
        value.choose_action(initial)


def test_cost_bounds_must_be_finite_and_nonnegative():
    with pytest.raises(ValueError):
        HeadroomGateFallbackController(scan_cost_upper_sec=float("inf"), verify_cost_upper_sec=7.0)
    with pytest.raises(ValueError):
        HeadroomGateFallbackController(scan_cost_upper_sec=3.0, verify_cost_upper_sec=-1.0)
