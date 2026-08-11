from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


EvidenceStatus = Literal[
    "UNVERIFIED",
    "VERIFIED_POSITIVE",
    "VERIFIED_NEGATIVE",
    "INSUFFICIENT_EVIDENCE",
]
ReturnStatus = Literal["VERIFIED_EVENT", "PROBABLE_EVENT", "EVENT_HYPOTHESIS"]


@dataclass(frozen=True, order=True)
class VerificationRecord:
    elapsed_sec: float
    label: Literal["positive", "negative", "unknown", "parse_failure"]
    raw_output_sha256: str
    inference_sec: float | None = None


@dataclass(frozen=True)
class CandidateObservation:
    candidate_id: str
    query_id: str
    video_id: str
    start_time: float
    end_time: float
    proxy_score: float
    calibrated_probability: float
    evidence_status: EvidenceStatus = "UNVERIFIED"
    verification_history: tuple[VerificationRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.query_id or not self.video_id:
            raise ValueError("candidate, query, and video identifiers must be nonempty")
        if self.start_time < 0 or self.end_time <= self.start_time:
            raise ValueError("candidate boundaries must have positive duration")
        if not 0.0 <= self.calibrated_probability <= 1.0:
            raise ValueError("calibrated_probability must be in [0, 1]")


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    query_id: str
    video_id: str
    start_time: float
    end_time: float
    event_score: float
    evidence_status: ReturnStatus
    source_candidate_ids: tuple[str, ...]
    verification_history: tuple[VerificationRecord, ...]
    k3_group: str
    commit_time: float | None

    @property
    def returnable(self) -> bool:
        return self.evidence_status in {"VERIFIED_EVENT", "PROBABLE_EVENT"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
