"""Immutable latent schema and deliberately narrower policy-visible schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Event:
    event_id: str
    region_ids: tuple[str, ...]
    start: float
    end: float
    actor_id: str
    detectability: float
    multiplicity: int


@dataclass(frozen=True)
class Witness:
    witness_id: str
    hypothesis_id: str
    region_id: str
    query_id: str
    interval: tuple[float, float]
    proxy_features: tuple[float, ...]
    raw_score: float
    creation_order: int
    confirm_core_duration: float
    confirm_support_upper: float
    latent_event_id: str | None = field(repr=False)

    def visible(self) -> "VisibleWitness":
        return VisibleWitness(
            self.witness_id, self.hypothesis_id, self.region_id, self.query_id,
            self.interval, self.proxy_features, self.raw_score,
            self.creation_order, self.confirm_support_upper,
        )


@dataclass(frozen=True)
class VisibleWitness:
    witness_id: str
    hypothesis_id: str
    region_id: str
    query_id: str
    interval: tuple[float, float]
    proxy_features: tuple[float, ...]
    raw_score: float
    creation_order: int
    confirm_support_upper: float


@dataclass(frozen=True)
class Region:
    region_id: str
    start: float
    end: float
    scan_core_duration: float
    scan_support_upper: float
    witness_ids: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class Episode:
    episode_id: str
    seed: int
    split: Literal["development", "heldout", "named"]
    split_index: int
    horizon: float
    query_id: str
    process: str
    cost_regime: str
    cost_variance: float
    standard_confirm_reserve: float
    regions: tuple[Region, ...]
    events: tuple[Event, ...] = field(repr=False)
    witnesses: tuple[Witness, ...] = field(repr=False)
    construction_hash: str
    parameter_hash: str
    named_scenario: str | None = None

    def canonical_dict(self, include_latent: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_latent:
            value.pop("events", None)
            for witness in value.pop("witnesses", []):
                witness.pop("latent_event_id", None)
        return value


@dataclass(frozen=True)
class CommittedEvent:
    commit_id: str
    event_id: str | None
    interval: tuple[float, float]
    committed_at: float
    false_positive: bool


@dataclass(frozen=True)
class Action:
    kind: Literal["SCAN", "CONFIRM", "STOP"]
    region_id: str | None = None
    hypothesis_id: str | None = None
    witness_id: str | None = None

    @staticmethod
    def scan(region_id: str) -> "Action":
        return Action("SCAN", region_id=region_id)

    @staticmethod
    def confirm(hypothesis_id: str, witness_id: str) -> "Action":
        return Action("CONFIRM", hypothesis_id=hypothesis_id, witness_id=witness_id)

    @staticmethod
    def stop() -> "Action":
        return Action("STOP")

    @property
    def identifier(self) -> str:
        return f"{self.kind}:{self.region_id or ''}:{self.hypothesis_id or ''}:{self.witness_id or ''}"


@dataclass(frozen=True)
class VisibleState:
    elapsed: float
    remaining: float
    mode: str
    scanned_region_ids: tuple[str, ...]
    next_region_id: str | None
    unscanned_region_count: int
    frontier: tuple[VisibleWitness, ...]
    terminal_witness_ids: tuple[str, ...]
    committed_events: tuple[CommittedEvent, ...]
    scan_bound: float
    confirm_bound: float
    confirm_reserve: float
    query_id: str

    def __getattr__(self, name: str):
        if name.startswith("latent") or name.startswith("future") or name in {"events", "witnesses", "cost_realizations", "regime_family"}:
            raise AttributeError(f"policy-visible state forbids {name}")
        raise AttributeError(name)


@dataclass(frozen=True)
class TraceEntry:
    sequence: int
    action: Action
    started_at: float
    completed_at: float
    duration: float
    mode_before: str
    mode_after: str
    committed_before: int
    committed_after: int
    outcome: str
    witness_event_id: str | None
    suppressed_witness_ids: tuple[str, ...]
    durable_snapshot_hash: str
