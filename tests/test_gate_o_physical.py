from __future__ import annotations

import pytest

from rc_sem.gate_o_physical import (
    GateOActionKind,
    GateOPolicyId,
    GateOPublicState,
    choose_action,
    nonsemantic_dry_run,
    run_policy,
    temporal_bisection_order,
)


def test_temporal_policy_order_is_the_frozen_permutation() -> None:
    order = temporal_bisection_order(35)
    assert order[:6] == (17, 8, 26, 3, 12, 21)
    assert len(order) == len(set(order)) == 35


def test_fixed_policies_use_only_exposed_frontier_for_verify() -> None:
    state = GateOPublicState(cell_count=35)
    first = choose_action(GateOPolicyId.TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1, state)
    assert first.kind is GateOActionKind.SCAN and first.target_id == 17
    state.scanned_cells.add(17); state.scan_count = 1; state.frontier_scores = {8: 0.2, 9: 0.9}
    second = choose_action(GateOPolicyId.TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1, state)
    assert second.kind is GateOActionKind.VERIFY and second.target_id == 9


def test_scan_then_verify_never_verifies_before_all_cells_are_scanned() -> None:
    state = GateOPublicState(cell_count=2, scanned_cells={0}, frontier_scores={1: 1.0}, scan_count=1)
    action = choose_action(GateOPolicyId.CHRONOLOGICAL_SCAN_THEN_VERIFY, state)
    assert action.kind is GateOActionKind.SCAN and action.target_id == 1


def test_unauthorized_run_makes_no_scan_or_verify_call() -> None:
    calls: list[str] = []
    with pytest.raises(PermissionError, match="not authorized"):
        run_policy(
            policy=GateOPolicyId.CHRONOLOGICAL_FIXED_SCAN1_VERIFY1,
            cell_count=1,
            execution_authorized=False,
            scan=lambda _: calls.append("scan") or {},
            verify=lambda _: calls.append("verify"),
            admit=lambda _: calls.append("admit") or True,
            deadline_seconds=1.0,
        )
    assert calls == []


def test_rejected_admission_makes_no_scan_or_verify_call() -> None:
    calls: list[str] = []
    result = run_policy(
        policy=GateOPolicyId.CHRONOLOGICAL_FIXED_SCAN1_VERIFY1,
        cell_count=1,
        execution_authorized=True,
        scan=lambda _: calls.append("scan") or {},
        verify=lambda _: calls.append("verify"),
        admit=lambda _: calls.append("admit") or False,
        deadline_seconds=1.0,
    )
    assert result.stop_reason == "deadline_admission_rejected"
    assert calls == ["admit"]


def test_dry_run_has_exact_policies_and_zero_oracle_calls() -> None:
    report = nonsemantic_dry_run(cell_count=35, execution_authorized=False)
    assert report["status"] == "EXECUTION_BLOCKED"
    assert report["oracle_calls"] == report["scan_calls"] == report["verify_calls"] == 0
    assert report["policies"] == [policy.value for policy in GateOPolicyId]
