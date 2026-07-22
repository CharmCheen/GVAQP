import json
from pathlib import Path

import pytest

from garc_eval.psvr_rollout_toy.environment import (
    ToyEnvironment,
    generate_episode,
    load_named_scenario,
)
from garc_eval.psvr_rollout_toy.invariants import audit_environment
from garc_eval.psvr_rollout_toy.policies import CapacityMatching, RatioPSVR, ShieldedPi0
from garc_eval.psvr_rollout_toy.schema import Action, TraceEntry
from garc_eval.psvr_rollout_toy.rollout import ClairvoyantSmallDP
from garc_eval.psvr_rollout_toy.serialization import canonical_bytes, episode_from_dict, sha256_value
from garc_eval.psvr_rollout_toy.utility import jump_identity_auc, metrics_from_trace


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/psvr_rollout_preimplementation"


def named_ids():
    value = json.loads((OUT / "TOY_NAMED_SCENARIOS.json").read_text())
    return [row["scenario_id"] for row in value["scenarios"]]


def commit_entry(sequence, event_id, completed_at, horizon, outcome="NEW_COMMIT"):
    return TraceEntry(
        sequence=sequence,
        action=Action.confirm(f"h{sequence}", f"w{sequence}"),
        started_at=max(0.0, completed_at - 1.0),
        completed_at=completed_at,
        duration=min(1.0, completed_at),
        mode_before="INITIAL" if sequence == 0 else "CONFIRM",
        mode_after="CONFIRM",
        committed_before=sequence if outcome == "NEW_COMMIT" else sequence,
        committed_after=sequence + 1 if outcome == "NEW_COMMIT" else sequence,
        outcome=outcome,
        witness_event_id=event_id,
        suppressed_witness_ids=(),
        durable_snapshot_hash=f"snapshot-{sequence}",
    )


def test_development_seed_list_is_frozen_without_opening_contaminated_heldout_universe():
    dev = json.loads((OUT / "TOY_DEVELOPMENT_SEEDS.json").read_text())["ordered_seeds"]
    assert dev == list(range(11000, 11128))


def test_episode_manifest_is_bit_stable_for_same_seed():
    first = generate_episode(11000, "development", 0)
    second = generate_episode(11000, "development", 0)
    assert sha256_value(first.canonical_dict()) == sha256_value(second.canonical_dict())
    assert first.episode_id != generate_episode(11001, "development", 1).episode_id


def test_episode_schema_round_trip_preserves_latent_manifest_and_hash():
    episode = generate_episode(11000, "development", 0)
    encoded = canonical_bytes(episode.canonical_dict())
    restored = episode_from_dict(json.loads(encoded))
    assert restored == episode
    assert canonical_bytes(restored.canonical_dict()) == encoded
    assert sha256_value(restored.canonical_dict()) == sha256_value(episode.canonical_dict())


def test_episode_schema_round_trip_rejects_unknown_or_missing_fields():
    value = generate_episode(11000, "development", 0).canonical_dict()
    with pytest.raises(ValueError, match="missing"):
        episode_from_dict({key: item for key, item in value.items() if key != "seed"})
    with pytest.raises(ValueError, match="extra"):
        episode_from_dict({**value, "future_secret": 1})


def test_policy_projection_does_not_expose_seed_identity():
    state = ToyEnvironment(generate_episode(11000, "development", 0)).visible_state()
    assert "11000" not in repr(state)


def test_policy_projection_has_no_latent_or_future_fields():
    state = ToyEnvironment(generate_episode(11000, "development", 0)).visible_state()
    for name in (
        "latent_event_id", "latent_events", "events", "witnesses",
        "unscanned_emissions", "future_cost_draws", "future_oracle_draws",
        "cost_realizations",
    ):
        with pytest.raises(AttributeError):
            getattr(state, name)


def test_generated_actions_obey_exact_support_on_development_prefix():
    for index, seed in enumerate(range(11000, 11016)):
        episode = generate_episode(seed, "development", index)
        assert all(0 <= r.scan_core_duration <= r.scan_support_upper <= 56.5 for r in episode.regions)
        assert all(0 <= w.confirm_core_duration <= w.confirm_support_upper <= 13.75 for w in episode.witnesses)


def test_pi0_deadline_and_productive_scan_reserve_on_development_prefix():
    for index, seed in enumerate(range(11000, 11016)):
        env = ToyEnvironment(generate_episode(seed, "development", index))
        while not env.stopped:
            state = env.visible_state()
            safe = env.safe_actions()
            for action in safe:
                if action.kind == "SCAN":
                    assert state.scan_bound + state.confirm_reserve <= state.remaining + 1e-12
            action = ShieldedPi0().choose(state, safe)
            entry = env.execute(action)
            assert entry.completed_at <= env.episode.horizon + 1e-12
        assert audit_environment(env)["status"] == "PASS"


@pytest.mark.parametrize("scenario_id", named_ids())
def test_named_pi0_is_proper_atomic_and_trace_recomputable(scenario_id):
    env = ToyEnvironment(load_named_scenario(scenario_id))
    env.run(ShieldedPi0())
    audit = audit_environment(env)
    assert audit["status"] == "PASS", audit
    assert env.trace[-1].action.kind == "STOP"


def test_scan_never_commits_and_confirm_commits_at_completion():
    scan_env = ToyEnvironment(load_named_scenario("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE"))
    scan = next(a for a in scan_env.safe_actions() if a.kind == "SCAN")
    entry = scan_env.execute(scan)
    assert entry.committed_before == entry.committed_after == 0
    confirm = next(a for a in scan_env.safe_actions() if a.kind == "CONFIRM")
    entry = scan_env.execute(confirm)
    assert entry.outcome == "NEW_COMMIT"
    assert len(scan_env.committed) == 1
    assert scan_env.committed[0].committed_at == entry.completed_at


def test_failed_confirm_does_not_commit():
    env = ToyEnvironment(load_named_scenario("VERIFY_FIRST_FAILURE"))
    action = next(a for a in env.safe_actions() if a.kind == "CONFIRM")
    entry = env.execute(action)
    assert entry.outcome == "ORACLE_NEGATIVE"
    assert entry.committed_after == entry.committed_before == 0
    assert not env.committed


def test_auc_integral_equals_jump_identity_and_surrogate_is_separate():
    episode = load_named_scenario("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE")
    trace = [commit_entry(0, "e1", 2.0, episode.horizon), commit_entry(1, "e2", 6.0, episode.horizon)]
    metrics = metrics_from_trace(episode, trace)
    assert metrics["AnytimeAUC_F1"] == pytest.approx(jump_identity_auc(episode, metrics["commit_jumps"]))
    assert metrics["AnytimeAUC_F1"] != metrics["time_weighted_unique_event_utility"]


def test_duplicate_has_zero_incremental_reward():
    episode = load_named_scenario("DUPLICATE_HEAVY_FRONTIER")
    first = commit_entry(0, "e1", 2.0, episode.horizon)
    duplicate = commit_entry(1, "e1", 4.0, episode.horizon, outcome="DUPLICATE")
    assert metrics_from_trace(episode, [first])["time_weighted_unique_event_utility"] == metrics_from_trace(episode, [first, duplicate])["time_weighted_unique_event_utility"]
    assert metrics_from_trace(episode, [first, duplicate])["duplicate_CONFIRM_count"] == 1


def test_commit_at_horizon_has_zero_surrogate_reward():
    episode = load_named_scenario("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE")
    metrics = metrics_from_trace(episode, [commit_entry(0, "e1", episode.horizon, episode.horizon)])
    assert metrics["time_weighted_unique_event_utility"] == 0


def test_f1_increment_is_state_dependent():
    episode = load_named_scenario("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE")
    metrics = metrics_from_trace(episode, [commit_entry(0, "e1", 2.0, episode.horizon), commit_entry(1, "e2", 4.0, episode.horizon)])
    jumps = metrics["commit_jumps"]
    assert jumps[0]["delta_f1"] != jumps[1]["delta_f1"]


def test_late_horizon_closure_has_only_stop():
    env = ToyEnvironment(load_named_scenario("LATE_HORIZON_CLOSURE"))
    assert [a.kind for a in env.safe_actions()] == ["STOP"]


def test_pi0_prefers_fifo_confirm_and_scans_without_frontier():
    confirm_env = ToyEnvironment(load_named_scenario("SCAN_FIRST_FAILURE"))
    assert ShieldedPi0().choose(confirm_env.visible_state(), confirm_env.safe_actions()).kind == "CONFIRM"
    scan_env = ToyEnvironment(load_named_scenario("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE"))
    assert ShieldedPi0().choose(scan_env.visible_state(), scan_env.safe_actions()).kind == "SCAN"


def test_capacity_matching_can_fail_low_quality_frontier_fixture():
    env = ToyEnvironment(load_named_scenario("CAPACITY_MATCHING_LOW_QUALITY_FAILURE"))
    env.run(CapacityMatching())
    assert "r2" not in {entry.action.region_id for entry in env.trace if entry.action.kind == "SCAN"}
    assert not env.committed


def test_high_value_candidate_is_not_overridden_by_scan_floor():
    env = ToyEnvironment(load_named_scenario("SINGLE_HIGH_VALUE_FRONTIER"))
    action = RatioPSVR().choose(env.visible_state(), env.safe_actions())
    assert action.kind == "CONFIRM"
    assert action.witness_id == "e1w"


def test_c0_uses_recursive_clairvoyant_dp_not_pi0_continuation():
    env = ToyEnvironment(load_named_scenario("HETEROGENEOUS_CONFIRM_COST"))
    policy = ClairvoyantSmallDP(env, max_safe_actions=4, max_states=100)
    action = policy.choose(env.visible_state(), env.safe_actions())
    assert action.kind == "CONFIRM"
    assert action.witness_id == "fast"
    assert policy.last_diagnostics["continuation"] == "EXACT_RECURSIVE_DP"
    assert policy.last_diagnostics["states_expanded"] > 1


def test_verify_first_fixture_retains_its_preregistered_scan_counterfactual():
    env = ToyEnvironment(load_named_scenario("VERIFY_FIRST_FAILURE"))
    assert any(a.kind == "SCAN" and a.region_id == "r0" for a in env.safe_actions())
