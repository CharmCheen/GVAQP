from copy import deepcopy

import pytest

from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.runner import TraceReplayEnvironment
from garc_eval.scan_confirm_controller.smdp_oracle import evaluator_state_hash
from garc_eval.scan_confirm_controller.smdp_oracle import (
    ExternalCalibrationSafeTraceReplayEnvironment,
    conditioned_action_value,
)
from garc_eval.scan_confirm_controller.state import validate_public_state


def test_public_state_rejects_evaluator_only_future_fields():
    env = TraceReplayEnvironment("V0_Q1", 60.0)
    public = env.public_state()
    public["future_labels"] = env.labels
    with pytest.raises(ValueError):
        validate_public_state(public)


def test_real_trace_deepcopy_does_not_share_mutable_state():
    env = TraceReplayEnvironment("V0_Q1", 60.0)
    branch = deepcopy(env)
    before = evaluator_state_hash(env)
    branch.step(Action.SCAN)
    assert evaluator_state_hash(env) == before
    assert env.observed != branch.observed
    assert env.frontier is not branch.frontier


def test_conditioned_oracle_rejects_within_task_future_cost_initialization():
    env = TraceReplayEnvironment("V1_Q1", 60.0)
    env.step(Action.SCAN)
    with pytest.raises(ValueError, match="externally calibrated"):
        conditioned_action_value(env, Action.SCAN, beam_width=8)


def test_external_cost_calibration_excludes_evaluated_video():
    env = ExternalCalibrationSafeTraceReplayEnvironment("V1_Q1", 60.0)
    assert env.cost_calibration_tasks
    assert all(not task.startswith("V1_") for task in env.cost_calibration_tasks)
    with pytest.raises(ValueError, match="leaks evaluated video"):
        ExternalCalibrationSafeTraceReplayEnvironment(
            "V1_Q1", 60.0, calibration_tasks=("V1_Q2",)
        )
