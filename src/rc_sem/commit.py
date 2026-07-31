from __future__ import annotations

import math
from dataclasses import dataclass

from .types import Action


@dataclass(frozen=True)
class StagedAction:
    action_id: str
    action: Action
    admitted_at_sec: float
    cost_upper_sec: float
    deadline_sec: float


@dataclass(frozen=True)
class CommitResult:
    action_id: str
    committed: bool
    reason: str
    post_deadline_commit: bool = False


class TwoPhaseCommitGuard:
    """Fail-closed staging and commit guard for public runtime state."""

    def __init__(self) -> None:
        self._staged: dict[str, StagedAction] = {}
        self._finished: set[str] = set()

    def stage(
        self,
        *,
        action_id: str,
        action: Action,
        admitted_at_sec: float,
        cost_upper_sec: float,
        deadline_sec: float,
    ) -> StagedAction:
        if not action_id:
            raise ValueError("action_id must be nonempty")
        if action is Action.STOP:
            raise ValueError("STOP has no physical stage")
        if action_id in self._staged or action_id in self._finished:
            raise ValueError(f"duplicate action attempt: {action_id}")
        for name, value in (
            ("admitted_at_sec", admitted_at_sec),
            ("cost_upper_sec", cost_upper_sec),
            ("deadline_sec", deadline_sec),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if admitted_at_sec < 0 or cost_upper_sec <= 0 or deadline_sec <= 0:
            raise ValueError("invalid time or cost")
        if admitted_at_sec + cost_upper_sec > deadline_sec:
            raise ValueError("complete action does not fit conservative deadline bound")
        row = StagedAction(action_id, action, admitted_at_sec, cost_upper_sec, deadline_sec)
        self._staged[action_id] = row
        return row

    def commit(
        self,
        *,
        action_id: str,
        completed_at_sec: float,
        integrity_passed: bool,
    ) -> CommitResult:
        if action_id in self._finished:
            raise ValueError(f"duplicate action completion: {action_id}")
        row = self._staged.pop(action_id, None)
        if row is None:
            raise ValueError(f"unknown staged action: {action_id}")
        self._finished.add(action_id)
        if not integrity_passed:
            return CommitResult(action_id, False, "integrity_failed")
        if not math.isfinite(completed_at_sec) or completed_at_sec < row.admitted_at_sec:
            return CommitResult(action_id, False, "invalid_completion_time")
        if completed_at_sec > row.deadline_sec:
            return CommitResult(action_id, False, "completed_after_deadline")
        return CommitResult(action_id, True, "committed_before_deadline")

    @property
    def unfinished_action_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._staged))
