from itertools import product

from frozen_reference import source_fixed_ratio
from garc.controller import Action, ActionResult, FixedRatioController, PublicState


def state(remaining=10, scan=1, confirm=1, frontier=1):
    return PublicState(remaining_budget_sec=remaining, frontier_size=frontier,
                       estimated_scan_cost_sec=scan, estimated_confirm_cost_sec=confirm).to_dict()


def test_fixed_ratio_action_parity_grid():
    comparisons = 0
    for scan_time, confirm_time, remaining, scan_cost, confirm_cost, frontier in product(
            (0.0, 1.0, 3.0, 10.0), (0.0, 1.0, 3.0, 10.0), (0.0, 1.0, 5.0),
            (0.5, 1.0, 6.0), (0.5, 1.0, 6.0), (0, 1, 4)):
        public = state(remaining, scan_cost, confirm_cost, frontier)
        controller = FixedRatioController()
        controller.reset(20, public)
        controller.scan_time, controller.confirm_time = scan_time, confirm_time
        assert controller.choose_action(public)["action"] == source_fixed_ratio(public, scan_time, confirm_time)
        comparisons += 1
    assert comparisons == 1296


def test_only_completed_actual_wallclock_changes_ratio():
    controller = FixedRatioController()
    controller.reset(20, state())
    controller.observe(ActionResult(Action.SCAN, 99, 2, False))
    assert controller.scan_time == 0
    controller.observe(ActionResult(Action.SCAN, 99, 2, True))
    controller.observe(ActionResult(Action.CONFIRM, 1, 6, True))
    assert controller.scan_time == 2 and controller.confirm_time == 6
    assert controller.realized_scan_fraction == .25


def test_empty_frontier_fallback_and_stop():
    controller = FixedRatioController()
    empty = state(frontier=0)
    controller.reset(10, empty)
    assert controller.choose_action(empty)["action"] == "SCAN"
    no_fit = state(remaining=.1, scan=1, confirm=1, frontier=1)
    assert controller.choose_action(no_fit) == {"action": "STOP", "reason": "no_complete_action_fits"}


def test_explicit_frozen_legality_and_ratio_cases():
    controller = FixedRatioController()
    both = state(remaining=10, scan=2, confirm=3, frontier=1)
    controller.reset(10, both)
    assert controller.choose_action(both)["action"] == "SCAN"  # zero time / SCAN share不足
    controller.scan_time, controller.confirm_time = 1, 9
    assert controller.choose_action(both)["action"] == "SCAN"
    controller.scan_time, controller.confirm_time = 9, 1
    assert controller.choose_action(both)["action"] == "CONFIRM"
    assert controller.choose_action(state(remaining=2, scan=2, confirm=3, frontier=1))["action"] == "SCAN"
    assert controller.choose_action(state(remaining=3, scan=4, confirm=3, frontier=1))["action"] == "CONFIRM"
    assert controller.choose_action(state(remaining=1, scan=2, confirm=3, frontier=1))["action"] == "STOP"
