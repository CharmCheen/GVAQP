from __future__ import annotations

import pytest

from rc_sem.sequential import (
    LabelIsolatedSequentialEnv,
    SequentialAction,
    SequentialActionType,
    SequentialCostConfig,
    strict_k3_groups,
    validate_public_state_no_evaluator_leakage,
)
from rc_sem.sequential_policies import (
    CrossVideoProfile,
    DynamicValuePolicy,
    FixedCyclePolicy,
    space_filling_order,
)


def environment(budget: float = 3.0):
    windows = {i: (10.0 * i, 10.0 * (i + 1)) for i in range(12)}
    return LabelIsolatedSequentialEnv(
        unit_windows=windows,
        proxy_scores={i: i / 12 for i in windows},
        oracle_labels={i: "positive" if i in {4, 5} else "negative" for i in windows},
        budget=budget,
        costs=SequentialCostConfig(scan_cost=0.1, verify_cost=1.0, scan_cell_units=4),
    )


def test_scan_reveals_proxy_but_never_label():
    env = environment()
    observation = env.step(SequentialAction(SequentialActionType.SCAN, 0, "test"))
    assert set(observation.revealed_proxy_scores) == {0, 1, 2, 3}
    assert observation.revealed_label is None
    assert env.state.verified_labels == {}
    validate_public_state_no_evaluator_leakage(env.state)


def test_verify_before_scan_fails_closed():
    env = environment()
    with pytest.raises(RuntimeError, match="not been scanned"):
        env.step(SequentialAction(SequentialActionType.VERIFY, 4, "illegal"))


def test_verify_reveals_only_selected_label_and_updates_k3():
    env = environment(4.0)
    env.step(SequentialAction(SequentialActionType.SCAN, 1, "scan"))
    first = env.step(SequentialAction(SequentialActionType.VERIFY, 4, "verify"))
    assert first.revealed_label == "positive"
    assert env.state.verified_labels == {4: "positive"}
    env.step(SequentialAction(SequentialActionType.VERIFY, 5, "verify"))
    assert env.state.event_groups == ((4, 5),)


def test_duplicate_actions_and_budget_overrun_fail_closed():
    env = environment(1.1)
    env.step(SequentialAction(SequentialActionType.SCAN, 0, "scan"))
    with pytest.raises(RuntimeError, match="duplicate action"):
        env.step(SequentialAction(SequentialActionType.SCAN, 0, "scan"))
    env.step(SequentialAction(SequentialActionType.VERIFY, 0, "verify"))
    with pytest.raises(RuntimeError, match="exceeds budget"):
        env.step(SequentialAction(SequentialActionType.SCAN, 1, "late"))


def test_unknown_and_parse_failure_are_not_positive():
    windows = {0: (0.0, 10.0), 1: (10.0, 20.0)}
    assert strict_k3_groups({0: "unknown", 1: "parse_failure"}, windows) == ()


def test_space_filling_order_is_complete_deterministic_and_label_blind():
    order = space_filling_order(9)
    assert order == space_filling_order(9)
    assert sorted(order) == list(range(9))
    assert order[0] == 4


def test_fixed_policy_recomputes_after_each_observation():
    env = environment(3.0)
    policy = FixedCyclePolicy(env.costs, verifies_per_scan=1)
    action = policy.choose(env.state)
    assert action.action_type is SequentialActionType.SCAN
    prior = env.state
    obs = env.step(action)
    policy.observe(prior, obs, env.state)
    assert policy.choose(env.state).action_type is SequentialActionType.VERIFY


def test_dynamic_policy_uses_only_public_proxy_and_revealed_labels():
    env = environment(3.0)
    profile = CrossVideoProfile(
        intercept=-1.0,
        proxy_coefficient=2.0,
        positive_prior=0.2,
        cell_max_posteriors=(0.4, 0.6, 0.8),
    )
    policy = DynamicValuePolicy(costs=env.costs, profile=profile, mode="adaptive")
    action = policy.choose(env.state)
    assert action.action_type is SequentialActionType.SCAN
    prior = env.state
    obs = env.step(action)
    policy.observe(prior, obs, env.state)
    second = policy.choose(env.state)
    assert second.action_type in {SequentialActionType.SCAN, SequentialActionType.VERIFY}
    validate_public_state_no_evaluator_leakage(env.state)


def test_policy_choice_is_invariant_to_hidden_labels_before_verify():
    windows = {i: (10.0 * i, 10.0 * (i + 1)) for i in range(12)}
    common = {
        "unit_windows": windows,
        "proxy_scores": {i: i / 12 for i in windows},
        "budget": 3.0,
        "costs": SequentialCostConfig(scan_cost=0.1, verify_cost=1.0, scan_cell_units=4),
    }
    negative = LabelIsolatedSequentialEnv(
        **common, oracle_labels={i: "negative" for i in windows}
    )
    positive = LabelIsolatedSequentialEnv(
        **common, oracle_labels={i: "positive" for i in windows}
    )
    profile = CrossVideoProfile(-1.0, 2.0, 0.2, (0.4, 0.6, 0.8))
    left = DynamicValuePolicy(costs=negative.costs, profile=profile, mode="adaptive")
    right = DynamicValuePolicy(costs=positive.costs, profile=profile, mode="adaptive")
    first_left = left.choose(negative.state)
    first_right = right.choose(positive.state)
    assert first_left == first_right
    negative.step(first_left)
    positive.step(first_right)
    assert left.choose(negative.state) == right.choose(positive.state)
