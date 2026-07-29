"""Authoritative unit labels and a capability-safe V3 label store."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Literal

from .oracle_v3_parser import OracleV3ParseResult


UnitOutcome = Literal["relevant", "not_relevant", "unknown", "parse_failure"]


@dataclass(frozen=True, order=True)
class ModelRelativeUnitLabel:
    unit_id: str
    query_id: str
    video_id: str
    start_time: float
    end_time: float
    outcome: UnitOutcome
    confidence: str | None = None
    evidence: str | None = None

    def __post_init__(self) -> None:
        if not self.unit_id or not self.query_id or not self.video_id:
            raise ValueError("unit, query, and video identifiers must be nonempty")
        if self.start_time < 0 or self.end_time <= self.start_time:
            raise ValueError("unit boundaries must have positive duration")
        if self.outcome not in {"relevant", "not_relevant", "unknown", "parse_failure"}:
            raise ValueError("invalid model-relative unit outcome")
        if self.outcome == "parse_failure" and (self.confidence is not None or self.evidence is not None):
            raise ValueError("parse_failure cannot carry parsed diagnostics")

    @property
    def is_positive(self) -> bool:
        return self.outcome == "relevant"

    @property
    def is_negative(self) -> bool:
        return self.outcome == "not_relevant"

    @property
    def is_indeterminate(self) -> bool:
        return self.outcome in {"unknown", "parse_failure"}

    def without_diagnostics(self) -> "ModelRelativeUnitLabel":
        return replace(self, confidence=None, evidence=None)


def unit_label_from_parse(
    *,
    unit_id: str,
    query_id: str,
    video_id: str,
    start_time: float,
    end_time: float,
    result: OracleV3ParseResult,
) -> ModelRelativeUnitLabel:
    if result.parse_status != "ok":
        return ModelRelativeUnitLabel(
            unit_id, query_id, video_id, start_time, end_time, "parse_failure"
        )
    return ModelRelativeUnitLabel(
        unit_id=unit_id,
        query_id=query_id,
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
        outcome=result.effective_label,
        confidence=result.parsed["confidence"],
        evidence=result.parsed["evidence"],
    )


class ModelRelativeLabelStore:
    """Evaluator-owned labels revealed only through explicit queried IDs."""

    def __init__(self, labels: Iterable[ModelRelativeUnitLabel]):
        rows = list(labels)
        if len({row.unit_id for row in rows}) != len(rows):
            raise ValueError("duplicate unit identifier")
        self._labels = {row.unit_id: row for row in rows}

    def reveal(self, queried_unit_ids: Iterable[str]) -> tuple[ModelRelativeUnitLabel, ...]:
        requested = set(queried_unit_ids)
        missing = requested - set(self._labels)
        if missing:
            raise KeyError(f"unknown queried unit IDs: {sorted(missing)}")
        return tuple(self._labels[unit_id] for unit_id in sorted(requested))

    def controller_view(self, queried_unit_ids: Iterable[str]) -> tuple[dict, ...]:
        return tuple({
            "unit_id": row.unit_id,
            "query_id": row.query_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "label": row.outcome,
        } for row in self.reveal(queried_unit_ids))
