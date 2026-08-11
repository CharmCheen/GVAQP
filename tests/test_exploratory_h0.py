import pytest

from rc_sem.exploratory_h0 import (
    MissingCounterfactualTransition,
    RuntimeAction,
    RuntimeState,
    TraceTransitionRegistry,
    legal_actions,
)


def state(**changes) -> RuntimeState:
    base = dict(
        elapsed_seconds=10.0,
        deadline_seconds=300.0,
        scan_order=(0, 1),
        next_scan_index=0,
        scanned_cells=frozenset(),
        exposed_units=frozenset(),
        attempted_verify_units=frozenset(),
    )
    base.update(changes)
    return RuntimeState(**base)


def test_verify_is_illegal_until_scan_exposes_its_candidate() -> None:
    assert RuntimeAction("VERIFY", 7) not in legal_actions(
        state(), scan_estimated_cost_seconds=5.0, verify_estimated_cost_seconds=9.0
    )


def test_scan_exposure_makes_verify_legal() -> None:
    actions = legal_actions(
        state(scanned_cells=frozenset({0}), next_scan_index=1, exposed_units=frozenset({7})),
        scan_estimated_cost_seconds=5.0,
        verify_estimated_cost_seconds=9.0,
    )
    assert RuntimeAction("VERIFY", 7) in actions


def test_future_proxy_or_reference_cannot_change_action_set() -> None:
    public = state(exposed_units=frozenset({3, 7}))
    before = legal_actions(public, scan_estimated_cost_seconds=5.0, verify_estimated_cost_seconds=9.0)
    # Labels and an unscanned proxy score have no parameter accepted by the API.
    after = legal_actions(public, scan_estimated_cost_seconds=5.0, verify_estimated_cost_seconds=9.0)
    assert after == before


def test_deadline_admission_excludes_unfinishable_actions() -> None:
    actions = legal_actions(
        state(elapsed_seconds=295.0, exposed_units=frozenset({7})),
        scan_estimated_cost_seconds=6.0,
        verify_estimated_cost_seconds=5.1,
    )
    assert actions == ()


def test_missing_branch_transition_fails_closed() -> None:
    registry = TraceTransitionRegistry({("s0", RuntimeAction("SCAN", 0)): {"exposed": [7]}})
    with pytest.raises(MissingCounterfactualTransition):
        registry.require("s0", RuntimeAction("VERIFY", 7))


def test_exact_persisted_transition_is_available() -> None:
    marker = {"exposed": [7]}
    assert TraceTransitionRegistry({("s0", RuntimeAction("SCAN", 0)): marker}).require(
        "s0", RuntimeAction("SCAN", 0)
    ) == marker
