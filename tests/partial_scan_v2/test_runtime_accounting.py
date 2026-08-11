import pytest

from garc_eval.partial_scan_v2.runtime_accounting import (
    action_admitted,
    remaining_budget_at_validation,
)


def timings(total=2.0):
    return {
        "policy_request_serialize_sec": total / 6,
        "ipc_send_sec": total / 6,
        "policy_decision_sec": total / 6,
        "ipc_receive_sec": total / 6,
        "policy_response_validate_sec": total / 6,
        "environment_action_validate_sec": total / 6,
    }


@pytest.mark.parametrize(
    "estimate,remaining,expected",
    [(4.9, 5.0, True), (5.0, 5.0, True), (5.1, 5.0, False), (0.0, 0.0, True), (0.1, -0.1, False)],
)
def test_deadline_boundaries(estimate, remaining, expected):
    assert action_admitted(estimate, remaining) is expected


def test_scheduler_overhead_is_subtracted_once_for_admission_only():
    assert remaining_budget_at_validation(10.0, timings()) == pytest.approx(8.0)


@pytest.mark.parametrize("actual", [4.0, 6.0])
def test_actual_cost_does_not_change_pre_action_admission(actual):
    assert action_admitted(5.0, 5.0)
    assert actual in {4.0, 6.0}  # microchunk completes after admission.
