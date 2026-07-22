import pytest

from garc_eval.psvr_rollout_toy.costs import ToyBounds
from garc_eval.psvr_rollout_toy.environment import ToyEnvironment, generate_episode
from garc_eval.psvr_rollout_toy.rollout import ExactToyRolloutEvaluator, ProtocolBlocked
from garc_eval.psvr_rollout_toy.rng import SplitMix64
from garc_eval.psvr_rollout_toy.schema import Action


def test_splitmix64_fixture():
    expected = [
        10451216379200822465, 13757245211066428519,
        17911839290282890590, 8196980753821780235,
        8195237237126968761, 14072917602864530048,
        16184226688143867045, 9648886400068060533,
    ]
    rng = SplitMix64(1)
    assert [rng.next_uint64() for _ in expected] == expected


def test_exact_support_constants():
    bounds = ToyBounds()
    assert bounds.scan == 56.5
    assert bounds.confirm == 13.75
    assert bounds.standard_confirm_reserve == 13.75


def test_generated_durations_are_within_exact_support():
    episode = generate_episode(11000, "development", 0)
    assert all(r.scan_core_duration <= r.scan_support_upper <= 56.5 for r in episode.regions)
    assert all(w.confirm_core_duration <= w.confirm_support_upper <= 13.75 for w in episode.witnesses)


def test_m1_fails_closed_instead_of_reading_realized_future():
    env = ToyEnvironment(generate_episode(11000, "development", 0))
    evaluator = ExactToyRolloutEvaluator(env)
    with pytest.raises(ProtocolBlocked, match="conditional"):
        evaluator(Action.stop(), env.visible_state())

