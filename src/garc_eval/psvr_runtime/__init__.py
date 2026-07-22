"""Leakage-safe runtime capabilities for PSVR.

This package intentionally does not import the evaluator or any reference
provider.  Selectors receive :class:`SelectorView`, never an oracle accessor.
"""

from .capabilities import OracleAccessor, OracleServiceHandle, start_oracle_service
from .deadline_guard import AdmissionDecision, ProfilePolicy, TailAwareDeadlineGuard
from .latency import LatencyObservation, RuntimeIdentity, TailLatencyProfile, measure_cuda_synchronized
from .physical_oracle import PhysicalOracleServiceHandle, start_physical_oracle_service
from .two_video_physical_oracle import (
    TwoVideoPhysicalOracleHandle,
    project_generic_label,
    start_two_video_physical_oracle_service,
    verify_two_video_configuration,
)
from .runner import (
    ActionLedger,
    attempt_artifact_indices,
    durable_json,
    materialize_and_commit,
    strict_indexed_json_paths,
    verify_action_ledger,
)
from .sandbox import (
    adversarial_sandbox_probe,
    isolated_materialize,
    start_materializer_service,
    start_selector_service,
)
from .views import EvidenceLedger, RuntimeConfig, SelectorView

__all__ = [
    "EvidenceLedger",
    "OracleAccessor",
    "OracleServiceHandle",
    "RuntimeConfig",
    "SelectorView",
    "start_oracle_service",
    "adversarial_sandbox_probe",
    "isolated_materialize",
    "start_materializer_service",
    "start_selector_service",
    "AdmissionDecision",
    "TailAwareDeadlineGuard",
    "ProfilePolicy",
    "LatencyObservation",
    "RuntimeIdentity",
    "TailLatencyProfile",
    "measure_cuda_synchronized",
    "PhysicalOracleServiceHandle",
    "start_physical_oracle_service",
    "TwoVideoPhysicalOracleHandle",
    "project_generic_label",
    "start_two_video_physical_oracle_service",
    "verify_two_video_configuration",
    "ActionLedger",
    "durable_json",
    "materialize_and_commit",
    "strict_indexed_json_paths",
    "attempt_artifact_indices",
    "verify_action_ledger",
]
