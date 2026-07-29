"""Event-level primitives for the accelerated event-query research line."""

from .incremental_k3 import IncrementalK3, K3Config, K3Update
from .matching import EventMatch, MatchConfig, match_events, summarize_matches
from .types import CandidateObservation, EventRecord, VerificationRecord

__all__ = [
    "CandidateObservation",
    "EventMatch",
    "EventRecord",
    "IncrementalK3",
    "K3Config",
    "K3Update",
    "MatchConfig",
    "VerificationRecord",
    "match_events",
    "summarize_matches",
]
