from __future__ import annotations

from dataclasses import replace
import json

from garc_eval.psvr_runtime.deadline_guard import TailAwareDeadlineGuard
from garc_eval.psvr_runtime.latency import (
    LatencyObservation,
    RuntimeIdentity,
    TailLatencyProfile,
    measure_cuda_synchronized,
    observations_from_durations,
)


NOW = "2026-07-14T16:00:00+00:00"
CREATED = "2026-07-14T15:00:00+00:00"
IDENTITY = RuntimeIdentity(
    workload_id="warm_oracle_cold_proxy:v1",
    hardware_id="NVIDIA_A800-SXM4-80GB:gpu0",
    oracle_model_id="qwen3-vl-32b:c8104b",
    proxy_model_id="yolov8n:batch4",
    video_sha256="bad229",
    query_id="enter_ego_path",
    oracle_contract_hash="model_prompt_parser_sampling:c8104b:121874:9a7413:5b038a",
    proxy_config_hash="yolov8n_batch4_grid30",
    batch_size=4,
    resident_model_set=("qwen3-vl-32b", "yolov8n"),
    serving_config_hash="single_process_gpu0_bf16_v1",
)
VERIFY_STAGES = (
    "clip_extraction", "oracle_preprocess", "oracle_inference", "oracle_postprocess",
    "oracle_parse", "cleanup",
)
COMMIT_STAGES = ("observation_persist", "materialize", "serialize", "fsync", "atomic_replace")


def profile(kind: str, durations, *, stages, cuda=True, identity=IDENTITY, created=CREATED):
    return TailLatencyProfile(
        profile_version="tail_upper_v1",
        operator_kind=kind,
        identity=identity,
        created_at_utc=created,
        minimum_samples=10,
        maximum_age_seconds=7200,
        quantile_alpha=0.90,
        epsilon_seconds=0.25,
        require_cuda_sync=cuda,
        required_stages=stages,
        observations=observations_from_durations(
            durations, prefix=kind, recorded_at_utc=CREATED, stage_names=stages,
            cuda_synchronized=cuda,
        ),
    )


def valid_profiles():
    action = profile("physical_verify", [11, 12, 12, 13, 13, 14, 15, 16, 17, 21], stages=VERIFY_STAGES)
    commit = profile("materialize_and_durable_snapshot", [0.01] * 9 + [0.04], stages=COMMIT_STAGES, cuda=False)
    return action, commit


def test_unsafe_tail_action_is_rejected_and_commit_is_reserved():
    action, commit = valid_profiles()
    guard = TailAwareDeadlineGuard(IDENTITY)
    required = action.tail_bound().upper_seconds + commit.tail_bound().upper_seconds
    # Action alone fits, but the independently reserved commit path does not.
    remaining = action.tail_bound().upper_seconds + commit.tail_bound().upper_seconds / 2
    decision = guard.decide(deadline_seconds=remaining, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert remaining > action.tail_bound().upper_seconds
    assert remaining < required
    assert decision.admitted is False
    assert decision.reason == "insufficient_tail_reservation"
    assert decision.required_seconds == required


def test_missing_or_stale_profile_defaults_to_reject():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    missing = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                           action_profile=None, commit_profile=commit)
    assert not missing.admitted and "missing_action_profile" in missing.validation_errors
    stale = replace(action, created_at_utc="2026-07-13T00:00:00+00:00")
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=stale, commit_profile=commit)
    assert not decision.admitted and "stale_profile" in decision.validation_errors


def test_cache_latency_and_nonphysical_samples_cannot_enter_profile():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    poisoned = replace(action.observations[0], cache_replay=True, physical_execution=False)
    action = replace(action, observations=(poisoned,) + action.observations[1:])
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted
    assert any("cache_replay_observation" in error for error in decision.validation_errors)
    assert any("non_physical_observation" in error for error in decision.validation_errors)


def test_wrong_workload_profile_cannot_be_reused():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    other = replace(IDENTITY, workload_id="warm_oracle_warm_proxy:v1")
    action = replace(action, identity=other)
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted
    assert "wrong_runtime_identity" in decision.validation_errors


def test_same_trace_gives_deterministic_admission_result():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    arguments = dict(deadline_seconds=60, elapsed_seconds=13.5, now_utc=NOW,
                     action_profile=action, commit_profile=commit)
    first = guard.decide(**arguments)
    second = guard.decide(**arguments)
    assert first == second
    assert first.admitted
    assert first.action_profile_id == action.profile_id()


def test_cuda_asynchronous_timing_cannot_undercount_stage_latency():
    calls = []
    ticks = iter([1_000_000_000, 4_000_000_000])

    def synchronize():
        calls.append("sync")

    def operation():
        calls.append("operation")
        return "result"

    result, duration = measure_cuda_synchronized(operation, synchronize, lambda: next(ticks))
    assert result == "result"
    assert duration == 3.0
    assert calls == ["sync", "operation", "sync"]

    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    unsynchronized = replace(action.observations[0], cuda_synchronized=False)
    action = replace(action, observations=(unsynchronized,) + action.observations[1:])
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted
    assert any("cuda_not_synchronized" in error for error in decision.validation_errors)


def test_incomplete_stage_and_insufficient_sample_profiles_reject():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    incomplete = replace(action.observations[0], stage_names=("oracle_inference",))
    action = replace(action, observations=(incomplete,) + action.observations[1:])
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted
    assert any("missing_stages" in error for error in decision.validation_errors)

    action, commit = valid_profiles()
    action = replace(action, observations=action.observations[:9])
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted and "insufficient_samples" in decision.validation_errors


def test_profile_round_trip_preserves_bound_and_identity():
    action, _ = valid_profiles()
    restored = TailLatencyProfile.from_dict(json.loads(json.dumps(action.to_dict())))
    assert restored == action
    assert restored.profile_id() == action.profile_id()
    assert restored.tail_bound() == action.tail_bound()


def test_profile_cannot_weaken_launcher_owned_validation_policy():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    weak = replace(
        action,
        minimum_samples=0,
        maximum_age_seconds=1e12,
        quantile_alpha=0.5,
        epsilon_seconds=0.0,
        require_cuda_sync=False,
        required_stages=(),
    )
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=weak, commit_profile=commit)
    assert not decision.admitted
    for error in (
        "profile_declares_weak_minimum_samples", "profile_declares_weak_maximum_age",
        "profile_declares_weak_quantile", "profile_declares_weak_epsilon",
        "profile_disables_required_cuda_sync", "profile_omits_policy_required_stages",
    ):
        assert error in decision.validation_errors


def test_future_or_stale_observation_rejects_even_when_profile_date_is_valid():
    action, commit = valid_profiles(); guard = TailAwareDeadlineGuard(IDENTITY)
    future = replace(action.observations[0], recorded_at_utc="2026-07-15T00:00:00+00:00")
    action = replace(action, observations=(future,) + action.observations[1:])
    decision = guard.decide(deadline_seconds=100, elapsed_seconds=0, now_utc=NOW,
                            action_profile=action, commit_profile=commit)
    assert not decision.admitted
    assert any(error.endswith(":from_future") for error in decision.validation_errors)
