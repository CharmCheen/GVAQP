from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, TypeVar


class ActionType(str, Enum):
    PROBE_CORE = "PROBE_CORE"
    PROBE_RELATION = "PROBE_RELATION"
    EXPLORE_CELL = "EXPLORE_CELL"
    HARD_NEGATIVE_GAP = "HARD_NEGATIVE_GAP"


class ObservationOutcome(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    SAME = "SAME"
    DISTINCT = "DISTINCT"
    AMBIGUOUS = "AMBIGUOUS"
    ABSTAIN = "ABSTAIN"


class RelationState(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    SAME = "SAME"
    DISTINCT = "DISTINCT"
    AMBIGUOUS = "AMBIGUOUS"


class HypothesisStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


T = TypeVar("T", bound="SerializableModel")


class SerializableModel:
    """JSON/CSV serialization that preserves enums, tuples, and structured fields."""

    _enum_fields: dict[str, type[Enum]] = {}
    _tuple_fields: set[str] = set()
    _json_fields: set[str] = set()

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        for key, value in list(raw.items()):
            if isinstance(value, Enum):
                raw[key] = value.value
            elif isinstance(value, tuple):
                raw[key] = list(value)
        return raw

    @classmethod
    def from_dict(cls: type[T], payload: dict[str, Any]) -> T:
        data = dict(payload)
        for key, enum_cls in cls._enum_fields.items():
            if key in data and data[key] not in (None, ""):
                data[key] = enum_cls(data[key])
        for key in cls._tuple_fields:
            if key in data:
                value = data[key]
                if isinstance(value, str):
                    value = json.loads(value) if value else []
                data[key] = tuple(value)
        for key in cls._json_fields:
            if key in data and isinstance(data[key], str):
                data[key] = json.loads(data[key]) if data[key] else {}
        numeric_types = {f.name: f.type for f in fields(cls)}
        for key, value in list(data.items()):
            if value in (None, ""):
                continue
            annotation = numeric_types.get(key)
            if annotation in (int, "int"):
                data[key] = int(value)
            elif annotation in (float, "float"):
                data[key] = float(value)
        return cls(**data)


@dataclass(frozen=True)
class AtomicUnit(SerializableModel):
    unit_id: str
    start_time: float
    end_time: float
    cheap_score: float
    structural_score: float
    coverage_prior: float


@dataclass(frozen=True)
class OracleObservation(SerializableModel):
    action_id: str
    action_type: ActionType
    target_ids: tuple[str, ...]
    outcome: ObservationOutcome
    confidence: float
    cost: float
    timestamp: float
    source: str

    _enum_fields = {"action_type": ActionType, "outcome": ObservationOutcome}
    _tuple_fields = {"target_ids"}


@dataclass(frozen=True)
class EventHypothesis(SerializableModel):
    hypothesis_id: str
    candidate_start: float
    candidate_end: float
    positive_anchor_ids: tuple[str, ...]
    negative_observation_ids: tuple[str, ...]
    existence_probability: float
    boundary_uncertainty: float
    status: HypothesisStatus

    _enum_fields = {"status": HypothesisStatus}
    _tuple_fields = {"positive_anchor_ids", "negative_observation_ids"}


@dataclass(frozen=True)
class AdjacentRelation(SerializableModel):
    left_hypothesis_id: str
    right_hypothesis_id: str
    same_event_probability: float
    relation_state: RelationState
    supporting_observations: tuple[str, ...]

    _enum_fields = {"relation_state": RelationState}
    _tuple_fields = {"supporting_observations"}


@dataclass(frozen=True)
class MaterializedEvent(SerializableModel):
    event_id: str
    start_time: float
    end_time: float
    anchor_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float

    _tuple_fields = {"anchor_ids", "evidence_ids"}


@dataclass(frozen=True)
class GroundTruthEvent(SerializableModel):
    event_id: str
    start_time: float
    end_time: float
    canonical_anchor_time: float
    actor_id: str
    schema: str


@dataclass(frozen=True)
class PlannerAction(SerializableModel):
    action_id: str
    action_type: ActionType
    target_ids: tuple[str, ...]
    estimated_cost: float
    selection_reason: str

    _enum_fields = {"action_type": ActionType}
    _tuple_fields = {"target_ids"}


@dataclass(frozen=True)
class ActionLineage(SerializableModel):
    action_id: str
    budget_step: int
    planner: str
    action_type: ActionType
    target: tuple[str, ...]
    pre_partition: tuple[dict[str, Any], ...]
    outcome: ObservationOutcome
    post_partition: tuple[dict[str, Any], ...]
    pre_event_count: int
    post_event_count: int
    matched_event_delta: int
    returned_seconds_delta: float
    selection_reason: str

    _enum_fields = {"action_type": ActionType, "outcome": ObservationOutcome}
    _tuple_fields = {"target", "pre_partition", "post_partition"}


def write_json(path: Path, records: Iterable[SerializableModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.to_dict() for r in records], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, model: type[T]) -> list[T]:
    return [model.from_dict(row) for row in json.loads(path.read_text(encoding="utf-8"))]


def write_csv(path: Path, records: Iterable[SerializableModel]) -> None:
    rows = [record.to_dict() for record in records]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    names = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict, tuple)) else v for k, v in row.items()})


def read_csv(path: Path, model: type[T]) -> list[T]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [model.from_dict(row) for row in csv.DictReader(handle)]
