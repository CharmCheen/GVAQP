"""Fail-closed causal-action scaffold for the Guangzhou H0 audit.

This module deliberately contains no oracle policy.  It defines the public
runtime action space and refuses to replay an action whose transition was not
persisted for the exact causally reached state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, order=True)
class RuntimeAction:
    kind: str
    target: int | None = None


@dataclass(frozen=True)
class RuntimeState:
    """Only fields visible to the policy before its next action starts."""

    elapsed_seconds: float
    deadline_seconds: float
    scan_order: tuple[int, ...]
    next_scan_index: int
    scanned_cells: frozenset[int]
    exposed_units: frozenset[int]
    attempted_verify_units: frozenset[int]

    @property
    def remaining_seconds(self) -> float:
        return self.deadline_seconds - self.elapsed_seconds


class MissingCounterfactualTransition(RuntimeError):
    """Raised instead of fabricating an unobserved branch transition."""


def legal_actions(
    state: RuntimeState,
    *,
    scan_estimated_cost_seconds: float | None,
    verify_estimated_cost_seconds: float | None,
    admission_mode: str = "estimated_complete_cost",
) -> tuple[RuntimeAction, ...]:
    """Return executable public actions under the existing admission rule.

    Candidate labels, evaluator reference labels, future proxy scores, and
    unscanned cells are intentionally absent from this generator.
    """
    if admission_mode not in {"estimated_complete_cost", "exploratory_start_before_deadline"}:
        raise ValueError(f"unknown admission mode: {admission_mode}")
    result: list[RuntimeAction] = []
    remaining = state.remaining_seconds
    scan_admitted = (
        remaining > 0.0
        if admission_mode == "exploratory_start_before_deadline"
        else scan_estimated_cost_seconds is not None and 0.0 <= scan_estimated_cost_seconds <= remaining
    )
    verify_admitted = (
        remaining > 0.0
        if admission_mode == "exploratory_start_before_deadline"
        else verify_estimated_cost_seconds is not None and 0.0 <= verify_estimated_cost_seconds <= remaining
    )
    if (
        state.next_scan_index < len(state.scan_order)
        and scan_admitted
    ):
        result.append(RuntimeAction("SCAN", state.scan_order[state.next_scan_index]))
    if verify_admitted:
        for unit in sorted(state.exposed_units - state.attempted_verify_units):
            result.append(RuntimeAction("VERIFY", unit))
    return tuple(result)


class TraceTransitionRegistry:
    """Exact-state transition cache used only when a branch is persisted."""

    def __init__(self, transitions: Mapping[tuple[str, RuntimeAction], object]):
        self._transitions = dict(transitions)

    def require(self, state_id: str, action: RuntimeAction) -> object:
        try:
            return self._transitions[(state_id, action)]
        except KeyError as error:
            raise MissingCounterfactualTransition(
                f"no persisted transition for state={state_id!r}, action={action!r}"
            ) from error
