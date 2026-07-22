"""Canonical serialization and durable-snapshot helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from .schema import Episode, Event, Region, Witness


def _default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_default).encode("utf-8")


def sha256_value(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False, default=_default) + "\n", encoding="utf-8")


def episode_from_dict(value: dict) -> Episode:
    """Strictly reconstruct an immutable Episode from its canonical mapping."""

    expected = {
        "episode_id", "seed", "split", "split_index", "horizon", "query_id",
        "process", "cost_regime", "cost_variance", "standard_confirm_reserve",
        "regions", "events", "witnesses", "construction_hash",
        "parameter_hash", "named_scenario",
    }
    missing = expected - set(value)
    extra = set(value) - expected
    if missing or extra:
        raise ValueError(f"Episode keys mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
    regions = tuple(
        Region(
            region_id=row["region_id"],
            start=float(row["start"]),
            end=float(row["end"]),
            scan_core_duration=float(row["scan_core_duration"]),
            scan_support_upper=float(row["scan_support_upper"]),
            witness_ids=tuple(row["witness_ids"]),
        )
        for row in value["regions"]
    )
    events = tuple(
        Event(
            event_id=row["event_id"],
            region_ids=tuple(row["region_ids"]),
            start=float(row["start"]),
            end=float(row["end"]),
            actor_id=row["actor_id"],
            detectability=float(row["detectability"]),
            multiplicity=int(row["multiplicity"]),
        )
        for row in value["events"]
    )
    witnesses = tuple(
        Witness(
            witness_id=row["witness_id"],
            hypothesis_id=row["hypothesis_id"],
            region_id=row["region_id"],
            query_id=row["query_id"],
            interval=tuple(float(item) for item in row["interval"]),
            proxy_features=tuple(float(item) for item in row["proxy_features"]),
            raw_score=float(row["raw_score"]),
            creation_order=int(row["creation_order"]),
            confirm_core_duration=float(row["confirm_core_duration"]),
            confirm_support_upper=float(row["confirm_support_upper"]),
            latent_event_id=row["latent_event_id"],
        )
        for row in value["witnesses"]
    )
    return Episode(
        episode_id=value["episode_id"],
        seed=int(value["seed"]),
        split=value["split"],
        split_index=int(value["split_index"]),
        horizon=float(value["horizon"]),
        query_id=value["query_id"],
        process=value["process"],
        cost_regime=value["cost_regime"],
        cost_variance=float(value["cost_variance"]),
        standard_confirm_reserve=float(value["standard_confirm_reserve"]),
        regions=regions,
        events=events,
        witnesses=witnesses,
        construction_hash=value["construction_hash"],
        parameter_hash=value["parameter_hash"],
        named_scenario=value["named_scenario"],
    )
