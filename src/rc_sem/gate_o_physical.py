"""Fail-closed execution primitives for the frozen Gate-O policy set.

This module deliberately knows nothing about evaluator references, labels, or
oracle caches.  A physical launcher supplies one complete SCAN callback and
one single-unit VERIFY callback; both callbacks must include their durable
commit tails before returning.  The runner refuses to invoke either callback
until a separate execution authorization is explicitly true.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping


class GateOPolicyId(str, Enum):
    CHRONOLOGICAL_FIXED_SCAN1_VERIFY1 = "A_CHRONOLOGICAL_FIXED_SCAN1_VERIFY1"
    TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1 = "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1"
    CHRONOLOGICAL_SCAN_THEN_VERIFY = "C_CHRONOLOGICAL_SCAN_THEN_VERIFY"


class GateOActionKind(str, Enum):
    SCAN = "SCAN"
    VERIFY = "VERIFY"
    STOP = "STOP"


@dataclass(frozen=True)
class GateOAction:
    kind: GateOActionKind
    target_id: int | None
    reason: str


@dataclass
class GateOPublicState:
    cell_count: int
    scanned_cells: set[int] = field(default_factory=set)
    frontier_scores: dict[int, float] = field(default_factory=dict)
    verified_units: set[int] = field(default_factory=set)
    scan_count: int = 0
    verify_count: int = 0


def temporal_bisection_order(cell_count: int) -> tuple[int, ...]:
    if cell_count <= 0:
        raise ValueError("cell_count must be positive")
    queue = [(0, cell_count - 1)]
    result: list[int] = []
    while queue:
        left, right = queue.pop(0)
        if left > right:
            continue
        middle = (left + right) // 2
        result.append(middle)
        queue.append((left, middle - 1))
        queue.append((middle + 1, right))
    return tuple(result)


def _next_unscanned(state: GateOPublicState, order: tuple[int, ...]) -> int | None:
    return next((cell for cell in order if cell not in state.scanned_cells), None)


def _next_verify(state: GateOPublicState) -> int | None:
    candidates = set(state.frontier_scores) - state.verified_units
    return max(candidates, key=lambda unit: (state.frontier_scores[unit], -unit)) if candidates else None


def choose_action(policy: GateOPolicyId, state: GateOPublicState) -> GateOAction:
    """Choose using only durably public SCAN outputs and previous VERIFY ids."""

    if state.cell_count <= 0 or state.scanned_cells - set(range(state.cell_count)):
        raise ValueError("invalid public Gate-O cell state")
    chronological = tuple(range(state.cell_count))
    temporal = temporal_bisection_order(state.cell_count)
    if policy is GateOPolicyId.CHRONOLOGICAL_SCAN_THEN_VERIFY:
        scan = _next_unscanned(state, chronological)
        if scan is not None:
            return GateOAction(GateOActionKind.SCAN, scan, "scan_then_verify_scan_phase")
        verify = _next_verify(state)
        return GateOAction(GateOActionKind.VERIFY, verify, "scan_then_verify_verify_phase") if verify is not None else GateOAction(GateOActionKind.STOP, None, "no_legal_action")
    order = chronological if policy is GateOPolicyId.CHRONOLOGICAL_FIXED_SCAN1_VERIFY1 else temporal
    scan = _next_unscanned(state, order)
    verify = _next_verify(state)
    # Start with SCAN and then alternate whenever both action kinds are legal.
    scan_due = state.scan_count == state.verify_count
    if scan_due and scan is not None:
        return GateOAction(GateOActionKind.SCAN, scan, "fixed_scan_verify_scan")
    if not scan_due and verify is not None:
        return GateOAction(GateOActionKind.VERIFY, verify, "fixed_scan_verify_verify")
    if scan is not None:
        return GateOAction(GateOActionKind.SCAN, scan, "legal_fallback_scan")
    if verify is not None:
        return GateOAction(GateOActionKind.VERIFY, verify, "legal_fallback_verify")
    return GateOAction(GateOActionKind.STOP, None, "no_legal_action")


@dataclass(frozen=True)
class GateORunResult:
    policy_id: GateOPolicyId
    actions: tuple[GateOAction, ...]
    stop_reason: str


ScanCallback = Callable[[int], Mapping[int, float]]
VerifyCallback = Callable[[int], None]
AdmissionCallback = Callable[[GateOAction], bool]


def run_policy(
    *,
    policy: GateOPolicyId,
    cell_count: int,
    execution_authorized: bool,
    scan: ScanCallback,
    verify: VerifyCallback,
    admit: AdmissionCallback,
    deadline_seconds: float,
    clock: Callable[[], float] = time.monotonic,
) -> GateORunResult:
    """Run one policy with per-action fail-closed deadline admission.

    ``admit`` is a physical admission guard supplied by the launcher.  It
    must reserve the action's full budget and durable-commit tail; a rejected
    action returns before either SCAN or VERIFY is invoked.
    """

    if execution_authorized is not True:
        raise PermissionError("Gate-O execution is not authorized")
    if deadline_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")
    state = GateOPublicState(cell_count=cell_count)
    start = clock()
    actions: list[GateOAction] = []
    while True:
        if clock() - start >= deadline_seconds:
            return GateORunResult(policy, tuple(actions), "hard_deadline_reached")
        action = choose_action(policy, state)
        if action.kind is GateOActionKind.STOP:
            return GateORunResult(policy, tuple(actions), action.reason)
        if admit(action) is not True:
            return GateORunResult(policy, tuple(actions), "deadline_admission_rejected")
        # The callbacks include their durable commit tails.  The runner never
        # exposes a future frontier to VERIFY.
        if action.kind is GateOActionKind.SCAN:
            exposed = dict(scan(int(action.target_id)))
            if any(not isinstance(unit, int) for unit in exposed):
                raise RuntimeError("SCAN exposed a non-integer unit id")
            state.scanned_cells.add(int(action.target_id))
            state.frontier_scores.update({int(unit): float(score) for unit, score in exposed.items()})
            state.scan_count += 1
        else:
            unit = int(action.target_id)
            if unit not in state.frontier_scores or unit in state.verified_units:
                raise RuntimeError("VERIFY attempted a non-public or duplicate unit")
            verify(unit)
            state.verified_units.add(unit)
            state.verify_count += 1
        actions.append(action)


def nonsemantic_dry_run(*, cell_count: int, execution_authorized: bool) -> dict[str, object]:
    """Resolve the exact policy set without calling SCAN, VERIFY, or an oracle."""

    if cell_count <= 0:
        raise ValueError("cell_count must be positive")
    orders = {
        GateOPolicyId.CHRONOLOGICAL_FIXED_SCAN1_VERIFY1.value: tuple(range(cell_count)),
        GateOPolicyId.TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.value: temporal_bisection_order(cell_count),
        GateOPolicyId.CHRONOLOGICAL_SCAN_THEN_VERIFY.value: tuple(range(cell_count)),
    }
    return {
        "status": "EXECUTION_BLOCKED" if execution_authorized is not True else "DRY_RUN_ONLY",
        "execution_authorized": execution_authorized,
        "oracle_calls": 0,
        "scan_calls": 0,
        "verify_calls": 0,
        "policies": [policy.value for policy in GateOPolicyId],
        "cell_orders": {name: list(order) for name, order in orders.items()},
    }
