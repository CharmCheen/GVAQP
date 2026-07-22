import ast
from collections import Counter
from pathlib import Path

import pytest

from garc_eval.psvr_rollout_toy.r2 import (
    ActionR2,
    ExactConditionalRollout,
    ExactPosterior,
    CONFIRM_SUPPORT_TICKS,
    HORIZON_TICKS,
    R2Environment,
    SCAN_SUPPORT_TICKS,
    ShieldedPi0R2,
    finite_world_library,
    replay,
)
from garc_eval.psvr_rollout_toy.r2_rng import stream
from garc_eval.psvr_rollout_toy.r2_splits import (
    ContaminatedHeldoutUniverseError,
    LEGACY_HELDOUT,
    LEGACY_HELDOUT_SHA256,
    load_development_universe,
    load_fixture_universe,
    reject_contaminated,
)


def test_visible_history_round_trip_and_no_latent_identity():
    env = R2Environment(finite_world_library()[0])
    action = next(a for a in env.safe_actions() if a.kind == "SCAN")
    env.execute(action)
    history = env.history
    assert replay(finite_world_library()[0], history) is not None
    assert "world-" not in repr(history)
    assert not hasattr(history, "seed")


def test_deterministic_visible_state_is_history_function():
    world = finite_world_library()[1]
    env = R2Environment(world)
    env.execute(next(a for a in env.safe_actions() if a.kind == "SCAN"))
    replayed = replay(world, env.history)
    assert replayed is not None
    assert replayed.visible_state() == env.visible_state()


def test_likelihood_is_interventional_and_binary():
    worlds = finite_world_library()
    env = R2Environment(worlds[0])
    env.execute(next(a for a in env.safe_actions() if a.kind == "SCAN"))
    posterior = ExactPosterior(worlds)
    weights = posterior.weights(env.history)
    assert set(weights.values()) <= {0.0, 1.0 / sum(value > 0 for value in weights.values())}
    assert posterior.verify(env.history)["all_supported_reproduce_history"]


def test_empty_history_recovers_uniform_prior_and_incremental_equals_full():
    worlds = finite_world_library()
    posterior = ExactPosterior(worlds)
    empty = R2Environment(worlds[0]).history
    assert set(posterior.weights(empty).values()) == {1 / len(worlds)}
    env = R2Environment(worlds[0])
    env.execute(next(a for a in env.safe_actions() if a.kind == "SCAN"))
    direct = posterior.weights(env.history)
    rebuilt = ExactPosterior(worlds).weights(env.history)
    assert direct == rebuilt
    prior = R2Environment(worlds[0]).history
    action, observation = env.history.actions[0], env.history.observations[0]
    assert posterior.incremental_weights(prior, action, observation) == direct


def test_d2_t_admission_uses_frozen_complete_action_support_not_realized_duration():
    env = R2Environment(finite_world_library()[0])
    env._elapsed = HORIZON_TICKS - (SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS) + 1
    assert all(action.kind != "SCAN" for action in env.safe_actions())


def test_exact_rollout_uses_same_posterior_and_closed_loop_pi0():
    worlds = finite_world_library()
    env = R2Environment(worlds[0])
    posterior = ExactPosterior(worlds)
    rollout = ExactConditionalRollout(posterior, ShieldedPi0R2())
    actions = env.safe_actions()
    scan = next(a for a in actions if a.kind == "SCAN")
    assert rollout.value(env.history, scan) >= 0
    selected = rollout.choose(env.history, actions)
    assert selected in actions
    assert rollout.last_diagnostics["full_horizon"] is True
    assert rollout.last_diagnostics["continuation"] == "B1_SHIELDED_PI0"


def test_stop_value_is_current_durable_value():
    world = finite_world_library()[0]
    env = R2Environment(world)
    posterior = ExactPosterior(finite_world_library())
    rollout = ExactConditionalRollout(posterior)
    assert rollout.value(env.history, ActionR2.stop()) == 0


def test_rng_namespaces_are_independent_and_key_stable():
    master = b"r2-test-master" * 4
    a = stream(master, "DEVELOPMENT_EXECUTION_RNG", "dev-0").next_uint64()
    b = stream(master, "DEVELOPMENT_PLANNING_RNG", "dev-0").next_uint64()
    assert a != b
    assert a == stream(master, "DEVELOPMENT_EXECUTION_RNG", "dev-0").next_uint64()


def test_finite_library_preserves_frozen_neighborhood_support_counts():
    worlds = finite_world_library()
    assert len(worlds) == 288
    sparse = Counter(world.density_bin for world in worlds if world.process == "UNIFORM_SPARSE")
    bursty = Counter(world.density_bin for world in worlds if world.process == "BURSTY_CLUSTERED")
    heterogeneous = Counter(world.density_bin for world in worlds if world.cost_variance_bin >= 2)
    assert set(sparse.values()) == {12}
    assert set(bursty.values()) == {12}
    assert set(heterogeneous.values()) == {18}


def test_fixture_and_development_are_explicit_and_contamination_is_rejected():
    assert len(load_fixture_universe()) == 3
    assert len(load_development_universe(2)) == 2
    with pytest.raises(ContaminatedHeldoutUniverseError):
        reject_contaminated(LEGACY_HELDOUT)
    with pytest.raises(ContaminatedHeldoutUniverseError):
        reject_contaminated(LEGACY_HELDOUT_SHA256)
    with pytest.raises(ContaminatedHeldoutUniverseError):
        reject_contaminated(91000)


def test_tests_do_not_import_confirmatory_generator():
    root = Path(__file__).resolve().parents[1]
    for path in root.glob("test_*.py"):
        tree = ast.parse(path.read_text())
        names = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not any("r2_confirmatory" in name for name in names), path
