import pytest

from rc_sem import (
    Action,
    ActionOption,
    EventHypothesis,
    EventStatus,
    RCSEMAlgorithm,
)


def hypothesis() -> EventHypothesis:
    return EventHypothesis(
        event_id="event_0",
        start_time=0.0,
        end_time=10.0,
        probability_mean=0.95,
        probability_uncertainty=0.05,
    )


def test_end_to_end_step_publishes_probable_and_selects_scan():
    step = RCSEMAlgorithm().step(
        hypotheses=[hypothesis()],
        action_options=[
            ActionOption(Action.SCAN, "region_1", 1.0, 3.0, 0.1, True),
            ActionOption(Action.VERIFY, "unit_0", 1.0, 1.0, 0.1),
        ],
        elapsed_sec=1.0,
        deadline_sec=10.0,
        frontier_size=1,
    )
    assert step.publication.events[0].status is EventStatus.PROBABLE
    assert step.decision.action is Action.SCAN


def test_end_to_end_step_forbids_postdeadline_materialization():
    with pytest.raises(ValueError, match="post-deadline"):
        RCSEMAlgorithm().step(
            hypotheses=[hypothesis()],
            action_options=[],
            elapsed_sec=10.1,
            deadline_sec=10.0,
            frontier_size=0,
        )
