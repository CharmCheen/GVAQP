"""Canonical V3 EventRelation built only from model-relative unit labels."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .matching import MatchConfig, match_events, summarize_matches
from .types import EventRecord


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelRelativeEventRelation:
    query_id: str
    k3_config_sha256: str
    events: tuple[EventRecord, ...]
    negative_unit_ids: tuple[str, ...]
    unknown_unit_ids: tuple[str, ...]
    parse_failure_unit_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "k3_config_sha256": self.k3_config_sha256,
            "events": [event.to_dict() for event in self.events],
            "negative_unit_ids": list(self.negative_unit_ids),
            "unknown_unit_ids": list(self.unknown_unit_ids),
            "parse_failure_unit_ids": list(self.parse_failure_unit_ids),
        }

    @property
    def relation_sha256(self) -> str:
        return canonical_hash(self.to_dict())


def model_relative_event_metrics(
    predicted: Iterable[EventRecord],
    reference: ModelRelativeEventRelation,
    config: MatchConfig | None = None,
) -> dict[str, float | int]:
    predicted_rows = tuple(predicted)
    matches = match_events(predicted_rows, reference.events, config)
    inherited = summarize_matches(predicted_rows, reference.events, matches)
    return {
        "predicted_events": inherited["predicted_events"],
        "32B-relative_reference_events": inherited["reference_events"],
        "matched_events": inherited["matched_events"],
        "32B-relative_event_precision": inherited[
            "32b_operational_oracle_relative_event_precision"
        ],
        "32B-relative_event_recall": inherited[
            "32b_operational_oracle_relative_event_recall"
        ],
        "32B-relative_event_f1": inherited["event_f1"],
        "mean_event_boundary_tiou": inherited["mean_event_boundary_tiou"],
    }
