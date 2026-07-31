from rc_sem import (
    Action,
    ActionOption,
    ControllerConfig,
    ControllerState,
    PublicationSnapshot,
    RCSEMController,
)


EMPTY = PublicationSnapshot((), 0, 0, 0, 1.0, 0.0)


def state(*, elapsed: float = 0.0, deadline: float = 10.0, frontier: int = 1):
    return ControllerState(elapsed, deadline, frontier, EMPTY)


def option(action: Action, value: float, uncertainty: float, cost: float = 1.0):
    return ActionOption(action, action.value.lower(), cost, value, uncertainty, action is Action.SCAN)


def test_scan_selected_only_with_conservative_advantage():
    controller = RCSEMController(ControllerConfig(uncertainty_beta=1.0, fallback_action=Action.VERIFY))
    decision = controller.choose(
        state(),
        [option(Action.SCAN, 3.0, 0.1), option(Action.VERIFY, 1.0, 0.1)],
    )
    assert decision.action is Action.SCAN
    assert decision.reason == "scan_conservative_advantage"


def test_uncertain_advantage_uses_frozen_fallback():
    controller = RCSEMController(ControllerConfig(uncertainty_beta=1.0, fallback_action=Action.VERIFY))
    decision = controller.choose(
        state(),
        [option(Action.SCAN, 1.1, 1.0), option(Action.VERIFY, 1.0, 1.0)],
    )
    assert decision.action is Action.VERIFY
    assert decision.reason == "uncertain_advantage_frozen_fallback"


def test_no_complete_action_fits_stops():
    decision = RCSEMController().choose(
        state(elapsed=9.5, deadline=10.0),
        [option(Action.SCAN, 10.0, 0.0, cost=1.0), option(Action.VERIFY, 10.0, 0.0, cost=1.0)],
    )
    assert decision.action is Action.STOP
    assert decision.reason == "no_complete_action_fits"


def test_scan_can_be_final_action_without_verify_reserve():
    controller = RCSEMController(ControllerConfig(scan_requires_verify_reserve=False))
    decision = controller.choose(
        state(elapsed=8.0, deadline=10.0, frontier=0),
        [option(Action.SCAN, 1.0, 0.0, cost=1.5), option(Action.VERIFY, 2.0, 0.0, cost=1.0)],
    )
    assert decision.action is Action.SCAN


def test_scan_without_direct_materialization_still_reserves_verify():
    controller = RCSEMController(ControllerConfig(scan_requires_verify_reserve=False))
    scan = ActionOption(Action.SCAN, "region", 1.5, 1.0, 0.0, False)
    verify = ActionOption(Action.VERIFY, "unit", 1.0, 2.0, 0.0, False)
    decision = controller.choose(
        state(elapsed=8.0, deadline=10.0, frontier=1),
        [scan, verify],
    )
    assert decision.action is Action.VERIFY
    assert decision.safe_actions == (Action.VERIFY,)


def test_target_selection_uses_conservative_value():
    controller = RCSEMController(ControllerConfig(uncertainty_beta=1.0))
    risky = ActionOption(Action.SCAN, "risky", 1.0, 5.0, 5.0, True)
    stable = ActionOption(Action.SCAN, "stable", 1.0, 1.0, 0.1, True)
    decision = controller.choose(state(frontier=0), [risky, stable])
    assert decision.target_id == "stable"


def test_verify_is_unavailable_with_empty_frontier():
    decision = RCSEMController().choose(
        state(frontier=0),
        [option(Action.SCAN, 1.0, 0.0), option(Action.VERIFY, 100.0, 0.0)],
    )
    assert decision.action is Action.SCAN
