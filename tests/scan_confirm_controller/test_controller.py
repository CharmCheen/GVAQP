from garc_eval.scan_confirm_controller.action import Action, ActionResult
from garc_eval.scan_confirm_controller.myopic_controller import MyopicVPSController
from garc_eval.scan_confirm_controller.runner import TraceReplayEnvironment, largest_gap_order


def test_largest_gap_is_deterministic_and_complete():
    order = largest_gap_order(17)
    assert order == largest_gap_order(17)
    assert sorted(order) == list(range(17))
    assert order[0] == 8


def test_empty_frontier_scans_when_legal():
    env = TraceReplayEnvironment("V0_Q1", 30)
    controller = MyopicVPSController()
    controller.reset(30, env.public_state())
    assert controller.choose_action(env.public_state())["action"] == "SCAN"


def test_no_action_fits_stops():
    env = TraceReplayEnvironment("V0_Q1", .001)
    controller = MyopicVPSController()
    controller.reset(.001, env.public_state())
    assert controller.choose_action(env.public_state())["action"] == "STOP"


def test_future_field_rejected():
    env = TraceReplayEnvironment("V0_Q1", 30)
    state = env.public_state(); state["future_confirm_outcomes"] = [1]
    controller = MyopicVPSController()
    try:
        controller.choose_action(state)
    except ValueError:
        pass
    else:
        raise AssertionError("future field was accepted")


def test_post_deadline_commit_excluded_from_summary():
    env = TraceReplayEnvironment("V0_Q1", 30)
    env.ledger.append({
        "action": "CONFIRM", "actual_action_cost_sec": 31.0,
        "cumulative_wallclock": 31.0, "utility": 1, "positive": 1,
        "new_distinct_utility": 1, "deadline_overrun": True,
    })
    assert env.summary("test", 0)["utility"] == 0
