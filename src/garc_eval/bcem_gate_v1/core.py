"""Reference-free legal EventRelation partition engine.

This module has no reference-table path or evaluator import.  It defines the
shared legal space and exact additive path optimizer used by runnable code.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import pandas as pd


SCHEMA_VERSION = "bcem_legal_partition_v1"


@dataclass(frozen=True)
class BCEMConfig:
    core_cap_seconds: float = 40.0
    output_cap_seconds: float = 60.0
    unit_seconds: float = 10.0
    objective_id: str = "legal_space_only"

    def canonical(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "core_cap_seconds": float(self.core_cap_seconds),
            "output_cap_seconds": float(self.output_cap_seconds),
            "unit_seconds": float(self.unit_seconds),
            "objective_id": self.objective_id,
        }


@dataclass(frozen=True)
class ObservationState:
    positives: tuple[int, ...]
    negatives: tuple[int, ...]
    abstains: tuple[int, ...] = ()


@dataclass(frozen=True)
class Group:
    start_anchor_index: int
    end_anchor_index: int
    anchors: tuple[int, ...]
    start_time: float
    end_time: float
    unknown_internal_units: tuple[int, ...]

    @property
    def span_seconds(self) -> float:
        return self.end_time - self.start_time


@dataclass(frozen=True)
class Partition:
    groups: tuple[Group, ...]

    @property
    def cuts(self) -> tuple[int, ...]:
        return tuple(g.end_anchor_index + 1 for g in self.groups)

    @property
    def anchor_tuples(self) -> tuple[tuple[int, ...], ...]:
        return tuple(g.anchors for g in self.groups)


@dataclass
class IncrementalLegalState:
    """Observation-maintenance interface with an exact batch fallback.

    Phase 2 uses this to verify transition semantics.  It deliberately makes
    no incremental-complexity claim; a local optimized DP is conditional on a
    positive headroom gate.
    """
    units: pd.DataFrame
    config: BCEMConfig
    observations: dict[int, str]
    state: ObservationState
    edges: dict[int, tuple[Group, ...]]
    transition_count: int = 0
    full_recompute_fallbacks: int = 0

    @classmethod
    def empty(cls, units: pd.DataFrame, config: BCEMConfig) -> "IncrementalLegalState":
        checked = validate_units(units)
        state = ObservationState((), (), ())
        return cls(checked, config, {}, state, {}, 0, 0)

    def apply(self, unit_id: int, label: str) -> None:
        uid = int(unit_id)
        normalized = str(label).strip().lower()
        if normalized not in {"positive", "negative", "abstain"}:
            raise ValueError(f"unknown observation label: {label!r}")
        if normalized == "abstain":
            raise ValueError("abstain requires an explicit frozen policy")
        if uid in self.observations and self.observations[uid] != normalized:
            raise ValueError(f"conflicting duplicate observation for unit {uid}")
        self.observations[uid] = normalized
        frame = pd.DataFrame([{"unit_id": u, "oracle_label_after_query": y}
                              for u, y in sorted(self.observations.items())])
        self.state = parse_observations(frame)
        self.edges = legal_group_edges(self.units, self.state, self.config) if self.state.positives else {}
        self.transition_count += 1
        self.full_recompute_fallbacks += 1


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_units(units: pd.DataFrame) -> pd.DataFrame:
    required = {"unit_id", "start_time", "end_time"}
    if not required <= set(units):
        raise ValueError(f"UnitTable missing columns: {sorted(required - set(units))}")
    out = units[["unit_id", "start_time", "end_time"]].copy()
    out["unit_id"] = out.unit_id.astype(int)
    out = out.sort_values("unit_id").drop_duplicates("unit_id", keep=False)
    if len(out) != units.unit_id.nunique() or out.empty:
        raise ValueError("UnitTable has duplicate IDs or is empty")
    if not (out.end_time.astype(float) > out.start_time.astype(float)).all():
        raise ValueError("UnitTable contains non-positive intervals")
    starts = out.start_time.astype(float).to_numpy()
    ends = out.end_time.astype(float).to_numpy()
    if any(starts[i] < starts[i - 1] or ends[i] < ends[i - 1] for i in range(1, len(out))):
        raise ValueError("UnitTable is not temporally ordered")
    return out.reset_index(drop=True)


def parse_observations(trace: pd.DataFrame) -> ObservationState:
    """Canonicalize explicit observations; never coerce abstain or unknown."""
    required = {"unit_id", "oracle_label_after_query"}
    if not required <= set(trace):
        raise ValueError(f"trace missing columns: {sorted(required - set(trace))}")
    observations: dict[int, str] = {}
    for row in trace[["unit_id", "oracle_label_after_query"]].itertuples(index=False):
        uid = int(row.unit_id)
        label = str(row.oracle_label_after_query).strip().lower()
        if label not in {"positive", "negative", "abstain"}:
            raise ValueError(f"unknown observation label for unit {uid}: {label!r}")
        if uid in observations and observations[uid] != label:
            raise ValueError(f"conflicting duplicate observation for unit {uid}")
        observations[uid] = label
    abstains = tuple(sorted(u for u, y in observations.items() if y == "abstain"))
    if abstains:
        raise ValueError(f"abstain requires an explicit frozen policy; units={abstains}")
    return ObservationState(
        positives=tuple(sorted(u for u, y in observations.items() if y == "positive")),
        negatives=tuple(sorted(u for u, y in observations.items() if y == "negative")),
        abstains=(),
    )


def _group(
    anchors: tuple[int, ...], i: int, j: int, unit_by_id: pd.DataFrame,
    positives: set[int], negatives: set[int], config: BCEMConfig,
) -> Group | None:
    first, last = anchors[i], anchors[j]
    if first not in unit_by_id.index or last not in unit_by_id.index:
        raise ValueError("observation references unknown unit ID")
    if any(first < n < last for n in negatives):
        return None
    start = float(unit_by_id.loc[first, "start_time"])
    end = float(unit_by_id.loc[last, "end_time"])
    span = end - start
    if span > config.core_cap_seconds + 1e-9 or span > config.output_cap_seconds + 1e-9:
        return None
    unknown = tuple(u for u in range(first + 1, last) if u not in positives and u not in negatives)
    return Group(i, j, anchors[i:j + 1], start, end, unknown)


def legal_group_edges(
    units: pd.DataFrame, state: ObservationState, config: BCEMConfig,
) -> dict[int, tuple[Group, ...]]:
    units = validate_units(units)
    unit_by_id = units.set_index("unit_id")
    anchors = state.positives
    positives, negatives = set(anchors), set(state.negatives)
    if positives & negatives:
        raise ValueError("positive and negative evidence overlap")
    if state.abstains:
        raise ValueError("abstain has no frozen BCEM semantics")
    unknown_ids = (positives | negatives) - set(unit_by_id.index.astype(int))
    if unknown_ids:
        raise ValueError(f"observations reference unknown units: {sorted(unknown_ids)}")
    edges: dict[int, tuple[Group, ...]] = {}
    for i in range(len(anchors)):
        # A cut before anchor i is legal only when the two minimal anchor
        # intervals do not overlap.  Unit IDs are time ordered, but the final
        # benchmark units are allowed to overlap, so ID order alone does not
        # prove non-crossing output events.
        if i > 0:
            previous_end = float(unit_by_id.loc[anchors[i - 1], "end_time"])
            current_start = float(unit_by_id.loc[anchors[i], "start_time"])
            if previous_end > current_start + 1e-9:
                edges[i] = ()
                continue
        candidates: list[Group] = []
        for j in range(i, len(anchors)):
            first, last = anchors[i], anchors[j]
            start = float(unit_by_id.loc[first, "start_time"])
            end = float(unit_by_id.loc[last, "end_time"])
            if end - start > min(config.core_cap_seconds, config.output_cap_seconds) + 1e-9:
                break
            group = _group(anchors, i, j, unit_by_id, positives, negatives, config)
            if group is None:
                # A barrier between first and last remains crossed by every
                # later endpoint, so no later group from i can be legal.
                if any(first < n < last for n in negatives):
                    break
                continue
            candidates.append(group)
        if not candidates:
            raise RuntimeError(f"isolated positive anchor {anchors[i]} is unexpectedly infeasible")
        edges[i] = tuple(candidates)
    return edges


def count_legal_partitions(edges: Mapping[int, Sequence[Group]], anchor_count: int) -> int:
    count = [0] * (anchor_count + 1)
    count[0] = 1
    for i in range(anchor_count):
        for group in edges.get(i, ()):
            count[group.end_anchor_index + 1] += count[i]
    return count[anchor_count]


def enumerate_legal_partitions(
    edges: Mapping[int, Sequence[Group]], anchor_count: int, *, limit: int | None = None,
) -> list[Partition]:
    out: list[Partition] = []
    def visit(i: int, groups: list[Group]) -> None:
        if limit is not None and len(out) >= limit:
            raise OverflowError(f"partition enumeration exceeded limit={limit}")
        if i == anchor_count:
            out.append(Partition(tuple(groups)))
            return
        for group in edges.get(i, ()):
            groups.append(group)
            visit(group.end_anchor_index + 1, groups)
            groups.pop()
    visit(0, [])
    return out


def optimize_additive_partition(
    edges: Mapping[int, Sequence[Group]], anchor_count: int,
    group_cost: Callable[[Group], float],
) -> tuple[Partition, float]:
    """Exact shortest path with deterministic anchor-tuple ties."""
    best: list[tuple[float, tuple[tuple[int, ...], ...], tuple[Group, ...]] | None] = [None] * (anchor_count + 1)
    best[0] = (0.0, (), ())
    for i in range(anchor_count):
        if best[i] is None:
            continue
        prior_cost, prior_key, prior_groups = best[i]
        for group in edges.get(i, ()):
            t = group.end_anchor_index + 1
            candidate = (prior_cost + float(group_cost(group)), prior_key + (group.anchors,), prior_groups + (group,))
            current = best[t]
            if current is None or (candidate[0], candidate[1]) < (current[0], current[1]):
                best[t] = candidate
    if best[anchor_count] is None:
        raise RuntimeError("legal partition DAG has no source-to-sink path")
    cost, _, groups = best[anchor_count]
    return Partition(groups), float(cost)


def relation_hash(state: ObservationState, partition: Partition, config: BCEMConfig) -> str:
    return canonical_hash({
        **config.canonical(),
        "positives": state.positives,
        "negatives": state.negatives,
        "abstains": state.abstains,
        "groups": partition.anchor_tuples,
    })


def build_event_relation(
    partition: Partition,
    state: ObservationState,
    config: BCEMConfig,
    run_meta: Mapping[str, object] | None = None,
    *,
    materializer: str = "bcem_legal_partition",
    prior_relation_hash: str = "",
    transition_type: str = "batch",
) -> pd.DataFrame:
    meta = dict(run_meta or {})
    rhash = relation_hash(state, partition, config)
    cfg_hash = canonical_hash(config.canonical())
    negative = set(state.negatives)
    if any(left.end_time > right.start_time + 1e-9
           for left, right in zip(partition.groups, partition.groups[1:])):
        raise RuntimeError("non-crossing safety violated during EventRelation emission")
    rows = []
    for idx, group in enumerate(partition.groups):
        inside_negative = sorted(n for n in negative if group.anchors[0] < n < group.anchors[-1])
        if inside_negative:
            raise RuntimeError("barrier safety violated during EventRelation emission")
        rows.append({
            **meta,
            "event_id": f"bcem_{rhash[:16]}_event_{idx:04d}",
            "start_time": group.start_time,
            "core_start_time": group.start_time,
            "core_end_time": group.end_time,
            "end_time": group.end_time,
            "anchor_unit_ids": "|".join(map(str, group.anchors)),
            "evidence_unit_ids": "|".join(map(str, group.anchors)),
            "num_positive_anchors": len(group.anchors),
            "num_negative_barriers": 0,
            "verification_state": "oracle_confirmed_anchors",
            "confidence": 1.0,
            "returned_seconds": group.span_seconds,
            "materializer": materializer,
            "materializer_config_hash": cfg_hash,
            "relation_hash": rhash,
            "prior_relation_hash": prior_relation_hash,
            "transition_type": transition_type,
            "unknown_internal_unit_ids": "|".join(map(str, group.unknown_internal_units)),
        })
    return pd.DataFrame(rows)


def barrier_block_count(state: ObservationState) -> int:
    if not state.positives:
        return 0
    negatives = set(state.negatives)
    blocks = 1
    for a, b in zip(state.positives, state.positives[1:]):
        if any(a < n < b for n in negatives):
            blocks += 1
    return blocks


def assert_partition_invariants(
    partition: Partition, state: ObservationState, config: BCEMConfig,
) -> None:
    flattened = tuple(a for g in partition.groups for a in g.anchors)
    if flattened != state.positives:
        raise AssertionError("positive-anchor coverage/order failure")
    if any(left.end_time > right.start_time + 1e-9
           for left, right in zip(partition.groups, partition.groups[1:])):
        raise AssertionError("output event non-crossing failure")
    for group in partition.groups:
        if not group.anchors:
            raise AssertionError("empty event group")
        if group.span_seconds > config.core_cap_seconds + 1e-9:
            raise AssertionError("core cap violation")
        if group.span_seconds > config.output_cap_seconds + 1e-9:
            raise AssertionError("output cap violation")
        if any(group.anchors[0] < n < group.anchors[-1] for n in state.negatives):
            raise AssertionError("barrier violation")
