"""Runnable reference-free BCEM-DP operator."""

from __future__ import annotations

import bisect
import time
from dataclasses import dataclass, field
from typing import Literal, Mapping

import pandas as pd

from .core import (
    BCEMConfig, Group, ObservationState, Partition, assert_partition_invariants,
    build_event_relation, legal_group_edges, optimize_additive_partition,
    parse_observations, validate_units,
)


ObjectiveVariant = Literal["full", "without_duration", "without_gap"]


def public_group_cost(group: Group, config: BCEMConfig, variant: ObjectiveVariant = "full") -> float:
    event_open = 1.0
    duration = group.span_seconds / config.core_cap_seconds if variant != "without_duration" else 0.0
    gap = (len(group.unknown_internal_units) * config.unit_seconds / config.core_cap_seconds
           if variant != "without_gap" else 0.0)
    return float(event_open + duration + gap)


def batch_partition_from_state(
    units: pd.DataFrame, state: ObservationState, config: BCEMConfig,
    variant: ObjectiveVariant = "full",
) -> tuple[Partition, float, int]:
    if not state.positives:
        return Partition(()), 0.0, 0
    edges = legal_group_edges(units, state, config)
    partition, cost = optimize_additive_partition(
        edges, len(state.positives), lambda group: public_group_cost(group, config, variant)
    )
    assert_partition_invariants(partition, state, config)
    edge_count = sum(len(groups) for groups in edges.values())
    return partition, cost, edge_count


def batch_materialize(
    units: pd.DataFrame, trace: pd.DataFrame, config: BCEMConfig,
    run_meta: Mapping[str, object] | None = None, variant: ObjectiveVariant = "full",
) -> tuple[pd.DataFrame, Partition, dict]:
    start = time.perf_counter()
    state = parse_observations(trace)
    partition, cost, edges = batch_partition_from_state(units, state, config, variant)
    relation = build_event_relation(partition, state, config, run_meta,
                                    materializer=f"public_bcem_dp_{variant}")
    return relation, partition, {"objective_cost": cost, "legal_edges": edges,
        "cpu_seconds": time.perf_counter() - start, "observed_region_size": len(trace),
        "full_video_units_scanned_after_initialization": 0}


@dataclass
class IncrementalBCEM:
    """Stateful exact updates over observed evidence, not the full video table.

    Unit geometry is indexed once. Each update reconstructs the small observed
    evidence table and exact bounded anchor DAG. This is a full-state fallback
    over observations, but it never rescans or rematerializes the entire video.
    The 40-second cap bounds legal lookback; diagnostics expose the actual
    observed region and affected-anchor suffix.
    """
    units: pd.DataFrame
    config: BCEMConfig
    variant: ObjectiveVariant = "full"
    observations: dict[int, str] = field(default_factory=dict)
    prior_relation_hash: str = ""
    partition: Partition = field(default_factory=lambda: Partition(()))
    objective_cost: float = 0.0
    transitions: int = 0
    batch_fallbacks: int = 0

    def __post_init__(self) -> None:
        checked = validate_units(self.units)
        self.units = checked
        self._unit_rows = {int(r.unit_id): {"unit_id": int(r.unit_id),
            "start_time": float(r.start_time), "end_time": float(r.end_time)}
            for r in checked.itertuples(index=False)}

    def _state(self) -> ObservationState:
        frame = pd.DataFrame([{"unit_id": u, "oracle_label_after_query": y}
                              for u, y in sorted(self.observations.items())],
                             columns=["unit_id", "oracle_label_after_query"])
        return parse_observations(frame)

    def apply(self, unit_id: int, label: str,
              run_meta: Mapping[str, object] | None = None) -> tuple[pd.DataFrame, dict]:
        start = time.perf_counter()
        uid = int(unit_id)
        normalized = str(label).strip().lower()
        if uid not in self._unit_rows:
            raise ValueError(f"unknown unit ID {uid}")
        if normalized not in {"positive", "negative", "abstain"}:
            raise ValueError(f"unknown observation label {label!r}")
        if normalized == "abstain":
            raise ValueError("abstain requires an explicit frozen policy")
        if uid in self.observations and self.observations[uid] != normalized:
            raise ValueError(f"conflicting duplicate observation for unit {uid}")
        prior_positives = sorted(u for u, y in self.observations.items() if y == "positive")
        observed_end = self._unit_rows[uid]["end_time"]
        threshold = observed_end - self.config.core_cap_seconds
        prior_starts = [self._unit_rows[u]["start_time"] for u in prior_positives]
        affected_start = bisect.bisect_left(prior_starts, threshold)
        self.observations[uid] = normalized
        state = self._state()
        # Build a compact table containing observed units only. Legal groups
        # need anchor geometry and explicit barrier IDs; unknown gaps remain IDs.
        compact = pd.DataFrame([self._unit_rows[u] for u in sorted(self.observations)])
        self.partition, self.objective_cost, edge_count = batch_partition_from_state(
            compact, state, self.config, self.variant
        )
        relation = build_event_relation(self.partition, state, self.config, run_meta,
            materializer=f"public_bcem_dp_{self.variant}", prior_relation_hash=self.prior_relation_hash,
            transition_type="incremental_observation_update")
        current_hash = str(relation.relation_hash.iloc[0]) if len(relation) else ""
        self.prior_relation_hash = current_hash
        self.transitions += 1
        return relation, {"objective_cost": self.objective_cost, "legal_edges": edge_count,
            "cpu_seconds": time.perf_counter() - start, "observed_region_size": len(compact),
            "affected_anchor_suffix_size": max(0, len(state.positives) - affected_start),
            "maximum_lookback_seconds": self.config.core_cap_seconds,
            "full_video_units_scanned_after_initialization": 0, "batch_fallback": False}

    def full_recompute_fallback(self, run_meta: Mapping[str, object] | None = None) -> pd.DataFrame:
        state = self._state()
        compact = pd.DataFrame([self._unit_rows[u] for u in sorted(self.observations)])
        self.partition, self.objective_cost, _ = batch_partition_from_state(compact, state, self.config, self.variant)
        self.batch_fallbacks += 1
        return build_event_relation(self.partition, state, self.config, run_meta,
                                    materializer=f"public_bcem_dp_{self.variant}",
                                    transition_type="full_recompute_fallback")

