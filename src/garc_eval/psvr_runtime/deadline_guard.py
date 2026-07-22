"""Fail-closed, tail-aware action admission for hard wall-clock deadlines."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .latency import RuntimeIdentity, TailLatencyProfile


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason: str
    remaining_seconds: float
    action_upper_seconds: float | None
    commit_upper_seconds: float | None
    required_seconds: float | None
    action_profile_id: str | None
    commit_profile_id: str | None
    validation_errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProfilePolicy:
    profile_version: str
    operator_kind: str
    minimum_samples: int
    maximum_age_seconds: float
    minimum_quantile_alpha: float
    minimum_epsilon_seconds: float
    require_cuda_sync: bool
    required_stages: tuple[str, ...]


def default_action_policy() -> ProfilePolicy:
    return ProfilePolicy(
        profile_version="tail_upper_v1", operator_kind="physical_verify", minimum_samples=10,
        maximum_age_seconds=86400.0, minimum_quantile_alpha=0.90, minimum_epsilon_seconds=0.25,
        require_cuda_sync=True,
        required_stages=("clip_extraction", "oracle_preprocess", "oracle_inference",
                         "oracle_postprocess", "oracle_parse", "cleanup"),
    )


def default_commit_policy() -> ProfilePolicy:
    return ProfilePolicy(
        profile_version="tail_upper_v1", operator_kind="materialize_and_durable_snapshot",
        minimum_samples=10, maximum_age_seconds=86400.0, minimum_quantile_alpha=0.90,
        minimum_epsilon_seconds=0.05, require_cuda_sync=False,
        required_stages=("observation_persist", "materialize", "serialize", "fsync", "atomic_replace"),
    )


@dataclass(frozen=True)
class TailAwareDeadlineGuard:
    expected_identity: RuntimeIdentity
    action_policy: ProfilePolicy = field(default_factory=default_action_policy)
    commit_policy: ProfilePolicy = field(default_factory=default_commit_policy)

    def decide(
        self,
        *,
        deadline_seconds: float,
        elapsed_seconds: float,
        now_utc: str,
        action_profile: TailLatencyProfile | None,
        commit_profile: TailLatencyProfile | None,
    ) -> AdmissionDecision:
        remaining = float(deadline_seconds - elapsed_seconds)
        if action_profile is None or commit_profile is None:
            missing = []
            if action_profile is None:
                missing.append("missing_action_profile")
            if commit_profile is None:
                missing.append("missing_commit_profile")
            return AdmissionDecision(False, "profile_unavailable", remaining, None, None, None,
                                     None if action_profile is None else action_profile.profile_id(),
                                     None if commit_profile is None else commit_profile.profile_id(), tuple(missing))

        errors = action_profile.validation_errors(self.action_policy.operator_kind, self.expected_identity, now_utc)
        errors += action_profile.policy_validation_errors(
            expected_profile_version=self.action_policy.profile_version,
            minimum_samples=self.action_policy.minimum_samples,
            maximum_age_seconds=self.action_policy.maximum_age_seconds,
            minimum_quantile_alpha=self.action_policy.minimum_quantile_alpha,
            minimum_epsilon_seconds=self.action_policy.minimum_epsilon_seconds,
            require_cuda_sync=self.action_policy.require_cuda_sync,
            required_stages=self.action_policy.required_stages,
            now_utc=now_utc,
        )
        errors += commit_profile.validation_errors(self.commit_policy.operator_kind, self.expected_identity, now_utc)
        errors += commit_profile.policy_validation_errors(
            expected_profile_version=self.commit_policy.profile_version,
            minimum_samples=self.commit_policy.minimum_samples,
            maximum_age_seconds=self.commit_policy.maximum_age_seconds,
            minimum_quantile_alpha=self.commit_policy.minimum_quantile_alpha,
            minimum_epsilon_seconds=self.commit_policy.minimum_epsilon_seconds,
            require_cuda_sync=self.commit_policy.require_cuda_sync,
            required_stages=self.commit_policy.required_stages,
            now_utc=now_utc,
        )
        errors = sorted(set(errors))
        if errors:
            return AdmissionDecision(False, "profile_invalid", remaining, None, None, None,
                                     action_profile.profile_id(), commit_profile.profile_id(), tuple(errors))

        action_upper = action_profile.tail_bound().upper_seconds
        commit_upper = commit_profile.tail_bound().upper_seconds
        required = action_upper + commit_upper
        admitted = remaining > required
        return AdmissionDecision(
            admitted=admitted,
            reason="admitted" if admitted else "insufficient_tail_reservation",
            remaining_seconds=remaining,
            action_upper_seconds=action_upper,
            commit_upper_seconds=commit_upper,
            required_seconds=required,
            action_profile_id=action_profile.profile_id(),
            commit_profile_id=commit_profile.profile_id(),
            validation_errors=(),
        )
