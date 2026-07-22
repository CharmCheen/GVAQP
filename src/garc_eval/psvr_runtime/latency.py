"""Auditable physical latency profiles for hard-deadline PSVR execution."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, TypeVar

import numpy as np


T = TypeVar("T")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("profile timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RuntimeIdentity:
    workload_id: str
    hardware_id: str
    oracle_model_id: str
    proxy_model_id: str
    video_sha256: str
    query_id: str
    oracle_contract_hash: str
    proxy_config_hash: str
    batch_size: int
    resident_model_set: tuple[str, ...]
    serving_config_hash: str


@dataclass(frozen=True)
class LatencyObservation:
    observation_id: str
    duration_seconds: float
    recorded_at_utc: str
    physical_execution: bool
    cache_replay: bool
    cuda_synchronized: bool
    success: bool
    stage_names: tuple[str, ...]
    source_artifact_sha256: str

    def validation_errors(self, required_stages: tuple[str, ...], require_cuda_sync: bool) -> list[str]:
        errors: list[str] = []
        if not math.isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            errors.append("non_positive_or_non_finite_duration")
        try:
            parse_utc(self.recorded_at_utc)
        except (TypeError, ValueError):
            errors.append("invalid_observation_timestamp")
        if not self.physical_execution:
            errors.append("non_physical_observation")
        if self.cache_replay:
            errors.append("cache_replay_observation")
        if not self.success:
            errors.append("failed_observation")
        if require_cuda_sync and not self.cuda_synchronized:
            errors.append("cuda_not_synchronized")
        missing = sorted(set(required_stages) - set(self.stage_names))
        if missing:
            errors.append("missing_stages:" + ",".join(missing))
        if (len(self.source_artifact_sha256) != 64 or
                any(character not in "0123456789abcdef" for character in self.source_artifact_sha256)):
            errors.append("invalid_source_artifact_sha256")
        return errors


@dataclass(frozen=True)
class TailBound:
    sample_count: int
    median_seconds: float
    observed_max_seconds: float
    positive_residual_quantile_seconds: float
    epsilon_seconds: float
    upper_seconds: float
    quantile_alpha: float
    estimator: str = "observed_max_plus_positive_residual_quantile_plus_epsilon"


@dataclass(frozen=True)
class TailLatencyProfile:
    profile_version: str
    operator_kind: str
    identity: RuntimeIdentity
    created_at_utc: str
    minimum_samples: int
    maximum_age_seconds: float
    quantile_alpha: float
    epsilon_seconds: float
    require_cuda_sync: bool
    required_stages: tuple[str, ...]
    observations: tuple[LatencyObservation, ...]

    def profile_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def validation_errors(
        self,
        expected_operator_kind: str,
        expected_identity: RuntimeIdentity,
        now_utc: str,
    ) -> list[str]:
        errors: list[str] = []
        if self.operator_kind != expected_operator_kind:
            errors.append("wrong_operator_kind")
        if self.identity != expected_identity:
            errors.append("wrong_runtime_identity")
        if len(self.observations) < self.minimum_samples:
            errors.append("insufficient_samples")
        if not 0.5 <= self.quantile_alpha < 1.0:
            errors.append("invalid_quantile_alpha")
        if self.epsilon_seconds < 0 or not math.isfinite(self.epsilon_seconds):
            errors.append("invalid_epsilon")
        try:
            age = (parse_utc(now_utc) - parse_utc(self.created_at_utc)).total_seconds()
            if age < 0:
                errors.append("profile_from_future")
            if age > self.maximum_age_seconds:
                errors.append("stale_profile")
        except (TypeError, ValueError):
            errors.append("invalid_profile_timestamp")
        for observation in self.observations:
            for error in observation.validation_errors(self.required_stages, self.require_cuda_sync):
                errors.append(f"observation:{observation.observation_id}:{error}")
        observation_ids = [observation.observation_id for observation in self.observations]
        source_ids = [observation.source_artifact_sha256 for observation in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            errors.append("duplicate_observation_id")
        if len(source_ids) != len(set(source_ids)):
            errors.append("duplicate_source_artifact")
        return sorted(set(errors))

    def policy_validation_errors(
        self,
        *,
        expected_profile_version: str,
        minimum_samples: int,
        maximum_age_seconds: float,
        minimum_quantile_alpha: float,
        minimum_epsilon_seconds: float,
        require_cuda_sync: bool,
        required_stages: tuple[str, ...],
        now_utc: str,
    ) -> list[str]:
        """Validate against launcher-owned policy; profile metadata cannot weaken it."""
        errors: list[str] = []
        if self.profile_version != expected_profile_version:
            errors.append("wrong_profile_version")
        if minimum_samples <= 0 or not math.isfinite(maximum_age_seconds) or maximum_age_seconds <= 0:
            raise ValueError("invalid launcher profile policy")
        if len(self.observations) < minimum_samples:
            errors.append("policy_insufficient_samples")
        if self.minimum_samples < minimum_samples:
            errors.append("profile_declares_weak_minimum_samples")
        if not math.isfinite(self.maximum_age_seconds) or self.maximum_age_seconds > maximum_age_seconds:
            errors.append("profile_declares_weak_maximum_age")
        if self.quantile_alpha < minimum_quantile_alpha:
            errors.append("profile_declares_weak_quantile")
        if self.epsilon_seconds < minimum_epsilon_seconds:
            errors.append("profile_declares_weak_epsilon")
        if require_cuda_sync and not self.require_cuda_sync:
            errors.append("profile_disables_required_cuda_sync")
        if not set(required_stages).issubset(self.required_stages):
            errors.append("profile_omits_policy_required_stages")
        try:
            now = parse_utc(now_utc)
            created_age = (now - parse_utc(self.created_at_utc)).total_seconds()
            if created_age < 0:
                errors.append("profile_from_future")
            if created_age > maximum_age_seconds:
                errors.append("stale_profile")
            for observation in self.observations:
                observation_age = (now - parse_utc(observation.recorded_at_utc)).total_seconds()
                if observation_age < 0:
                    errors.append(f"observation:{observation.observation_id}:from_future")
                if observation_age > maximum_age_seconds:
                    errors.append(f"observation:{observation.observation_id}:stale")
        except (TypeError, ValueError):
            errors.append("invalid_policy_timestamp_comparison")
        for observation in self.observations:
            for error in observation.validation_errors(required_stages, require_cuda_sync):
                errors.append(f"observation:{observation.observation_id}:{error}")
        observation_ids = [observation.observation_id for observation in self.observations]
        source_ids = [observation.source_artifact_sha256 for observation in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            errors.append("duplicate_observation_id")
        if len(source_ids) != len(set(source_ids)):
            errors.append("duplicate_source_artifact")
        return sorted(set(errors))

    def tail_bound(self) -> TailBound:
        durations = np.asarray([item.duration_seconds for item in self.observations], dtype=float)
        if durations.size == 0:
            raise ValueError("cannot estimate a tail bound from an empty profile")
        median = float(np.median(durations))
        positive_residuals = durations[durations > median] - median
        residual_quantile = 0.0 if positive_residuals.size == 0 else float(
            np.quantile(positive_residuals, self.quantile_alpha, method="higher")
        )
        maximum = float(np.max(durations))
        upper = maximum + residual_quantile + self.epsilon_seconds
        return TailBound(
            sample_count=int(durations.size),
            median_seconds=median,
            observed_max_seconds=maximum,
            positive_residual_quantile_seconds=residual_quantile,
            epsilon_seconds=float(self.epsilon_seconds),
            upper_seconds=float(upper),
            quantile_alpha=float(self.quantile_alpha),
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "profile_id": self.profile_id(), "tail_bound": asdict(self.tail_bound())}

    @classmethod
    def from_dict(cls, value: dict) -> "TailLatencyProfile":
        fields = dict(value)
        fields.pop("profile_id", None)
        fields.pop("tail_bound", None)
        identity = dict(fields["identity"])
        identity["resident_model_set"] = tuple(identity["resident_model_set"])
        fields["identity"] = RuntimeIdentity(**identity)
        fields["required_stages"] = tuple(fields["required_stages"])
        fields["observations"] = tuple(
            LatencyObservation(**{**row, "stage_names": tuple(row["stage_names"])})
            for row in fields["observations"]
        )
        return cls(**fields)


def measure_cuda_synchronized(
    operation: Callable[[], T],
    synchronize: Callable[[], None],
    clock_ns: Callable[[], int],
) -> tuple[T, float]:
    """Measure a CUDA stage without admitting queued work before or after it."""

    synchronize()
    start = clock_ns()
    result = operation()
    synchronize()
    end = clock_ns()
    return result, (end - start) / 1e9


def observations_from_durations(
    durations: Iterable[float],
    *,
    prefix: str,
    recorded_at_utc: str,
    stage_names: tuple[str, ...],
    cuda_synchronized: bool,
) -> tuple[LatencyObservation, ...]:
    return tuple(
        LatencyObservation(
            observation_id=f"{prefix}_{index:04d}",
            duration_seconds=float(duration),
            recorded_at_utc=recorded_at_utc,
            physical_execution=True,
            cache_replay=False,
            cuda_synchronized=cuda_synchronized,
            success=True,
            stage_names=stage_names,
            source_artifact_sha256=hashlib.sha256(
                f"{prefix}:{index}:{float(duration):.17g}".encode()
            ).hexdigest(),
        )
        for index, duration in enumerate(durations)
    )
