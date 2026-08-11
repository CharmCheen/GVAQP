"""Event-level primitives for the accelerated event-query research line."""

from .incremental_k3 import IncrementalK3, K3Config, K3Update
from .k3_unit_event_adapter import K3UnitEventAdapter, K3UnitEventConfig, K3UnitEventUpdate
from .matching import EventMatch, MatchConfig, match_events, summarize_matches
from .model_relative_event_relation import ModelRelativeEventRelation, model_relative_event_metrics
from .model_relative_labels import ModelRelativeLabelStore, ModelRelativeUnitLabel, unit_label_from_parse
from .oracle_v3_parser import OracleV3ParseResult, parse_oracle_v3_response
from .types import CandidateObservation, EventRecord, VerificationRecord

__all__ = [
    "CandidateObservation",
    "EventMatch",
    "EventRecord",
    "IncrementalK3",
    "K3UnitEventAdapter",
    "K3UnitEventConfig",
    "K3UnitEventUpdate",
    "K3Config",
    "K3Update",
    "MatchConfig",
    "ModelRelativeEventRelation",
    "ModelRelativeLabelStore",
    "ModelRelativeUnitLabel",
    "OracleV3ParseResult",
    "VerificationRecord",
    "match_events",
    "model_relative_event_metrics",
    "parse_oracle_v3_response",
    "summarize_matches",
    "unit_label_from_parse",
]
