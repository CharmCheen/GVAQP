"""Barrier-Constrained Event Materialization gate v1."""

from .core import (
    BCEMConfig,
    Group,
    ObservationState,
    Partition,
    build_event_relation,
    count_legal_partitions,
    enumerate_legal_partitions,
    legal_group_edges,
    optimize_additive_partition,
    parse_observations,
)

__all__ = [
    "BCEMConfig", "Group", "ObservationState", "Partition",
    "build_event_relation", "count_legal_partitions",
    "enumerate_legal_partitions", "legal_group_edges",
    "optimize_additive_partition", "parse_observations",
]

