"""Application-level deadline accounting shared by Replay and Physical."""
from __future__ import annotations

from typing import Mapping


VALIDATION_OVERHEAD_FIELDS = (
    "policy_request_serialize_sec",
    "ipc_send_sec",
    "policy_decision_sec",
    "ipc_receive_sec",
    "policy_response_validate_sec",
    "environment_action_validate_sec",
)


def remaining_budget_at_validation(
    remaining_before_step_sec: float, timings: Mapping[str, float]
) -> float:
    """Subtract scheduler overhead exactly once, without clamping the ledger."""
    return float(remaining_before_step_sec) - sum(
        float(timings.get(name, 0.0)) for name in VALIDATION_OVERHEAD_FIELDS
    )


def action_admitted(
    estimated_post_validation_completion_sec: float,
    remaining_at_validation_sec: float,
) -> bool:
    return float(estimated_post_validation_completion_sec) <= float(
        remaining_at_validation_sec
    )
