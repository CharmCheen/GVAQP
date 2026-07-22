from dataclasses import replace

import pytest

from garc_eval.psvr_rollout_toy.conditional import (
    SymmetricConditionalRolloutEvaluator,
    VisibleHistory,
)
from garc_eval.psvr_rollout_toy.environment import ToyEnvironment, load_named_scenario
from garc_eval.psvr_rollout_toy.schema import Action


class FreshDeterministicFixtureKernel:
    kernel_id = "TEST_ONLY_DEGENERATE_KERNEL"
    realized_episode_access = False

    def __init__(self, episode):
        self.episode = episode

    def sample(self, history, action, sample_index):
        return ToyEnvironment(self.episode)


class ForbiddenRealizedKernel(FreshDeterministicFixtureKernel):
    realized_episode_access = True


def test_evaluator_rejects_sampler_with_realized_truth_access():
    episode = load_named_scenario("SINGLE_HIGH_VALUE_FRONTIER")
    env = ToyEnvironment(episode)
    history = VisibleHistory(0, env.visible_state(), ())
    with pytest.raises(ValueError, match="realized episode"):
        SymmetricConditionalRolloutEvaluator(ForbiddenRealizedKernel(episode), history, 1e-8)


def test_degenerate_model_converges_without_estimator_noise():
    episode = load_named_scenario("SINGLE_HIGH_VALUE_FRONTIER")
    env = ToyEnvironment(episode)
    history = VisibleHistory(0, env.visible_state(), ())
    evaluator = SymmetricConditionalRolloutEvaluator(
        FreshDeterministicFixtureKernel(episode), history, 1e-8, max_samples=4
    )
    action = next(a for a in env.safe_actions() if a.kind == "CONFIRM")
    assert evaluator(action, env.visible_state()) > 0
    estimate = evaluator.estimates[action.identifier]
    assert estimate.samples == 2
    assert estimate.ci99_half_width == 0
    assert estimate.continuation_policy == "B1_SHIELDED_PI0"
    assert estimate.full_horizon is True


def test_model_world_must_match_visible_history():
    episode = load_named_scenario("SINGLE_HIGH_VALUE_FRONTIER")
    env = ToyEnvironment(episode)
    wrong = replace(env.visible_state(), elapsed=1.0)
    history = VisibleHistory(0, wrong, ())
    evaluator = SymmetricConditionalRolloutEvaluator(
        FreshDeterministicFixtureKernel(episode), history, 1e-8, max_samples=2
    )
    with pytest.raises(ValueError, match="does not match"):
        evaluator(Action.stop(), wrong)

