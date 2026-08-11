from types import SimpleNamespace

from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.frontier_adapter import Candidate
from garc_eval.scan_confirm_controller.runner import TraceReplayEnvironment
from garc_eval.scan_confirm_controller.smdp_oracle import anytime_auc


def test_anytime_auc_integrates_only_on_time_atomic_commits():
    env = SimpleNamespace(
        budget_sec=10.0,
        ledger=[
            {"action_index": 0, "cumulative_wallclock": 2.0, "utility": 1, "deadline_overrun": False},
            {"action_index": 1, "cumulative_wallclock": 6.0, "utility": 2, "deadline_overrun": False},
        ],
    )
    assert anytime_auc(env) == (1 * 4 + 2 * 4) / 10


def test_post_deadline_event_does_not_enter_anytime_auc():
    env = SimpleNamespace(
        budget_sec=10.0,
        ledger=[
            {"action_index": 0, "cumulative_wallclock": 2.0, "utility": 1, "deadline_overrun": False},
            {"action_index": 1, "cumulative_wallclock": 11.0, "utility": 2, "deadline_overrun": True},
        ],
    )
    assert anytime_auc(env) == 0.8


class _UnderBound:
    def estimate(self) -> float:
        return 0.01

    def observe(self, value: float) -> None:
        raise AssertionError("overrun action must not update the estimator")


def test_real_scan_overrun_has_no_frontier_or_coverage_commit():
    env = TraceReplayEnvironment("V1_Q1", 1.0)
    env.scan_estimator = _UnderBound()
    before_frontier = env.frontier.rows()
    result = env.step(Action.SCAN)
    assert result.completed
    assert env.elapsed > env.budget_sec
    assert env.scan_cursor == 0
    assert not env.observed
    assert env.frontier.rows() == before_frontier
    assert env.ledger[-1]["deadline_overrun"]
    assert env.ledger[-1]["post_deadline_commit"] is False


def test_real_verify_overrun_has_no_event_or_frontier_commit():
    env = TraceReplayEnvironment("V1_Q1", 1.0)
    positive_unit = next(unit for unit, label in env.labels.items() if label == "positive")
    env.frontier.update([
        Candidate("forced", positive_unit, 0, 1.0, 0.0, 0)
    ])
    env.confirm_estimator = _UnderBound()
    before = env.frontier.rows()
    result = env.step(Action.CONFIRM)
    assert result.completed
    assert env.elapsed > env.budget_sec
    assert not env.confirmed_events
    assert env.frontier.rows() == before
    assert env.ledger[-1]["new_distinct_utility"] == 0
    assert env.ledger[-1]["post_deadline_commit"] is False
