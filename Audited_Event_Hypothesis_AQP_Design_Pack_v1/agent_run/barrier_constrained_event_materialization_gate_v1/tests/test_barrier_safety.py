import pandas as pd
import pytest

from garc_eval.bcem_gate_v1.ceiling import exact_ceiling_partition
from garc_eval.bcem_gate_v1.core import (
    BCEMConfig, ObservationState, assert_partition_invariants,
    enumerate_legal_partitions, legal_group_edges,
)


def units(n=12):
    return pd.DataFrame({"unit_id": range(n), "start_time": [10.0*i for i in range(n)],
                         "end_time": [10.0*(i+1) for i in range(n)]})


def test_positive_pair_separated_by_queried_negative():
    state = ObservationState((0, 2), (1,), ())
    edges = legal_group_edges(units(), state, BCEMConfig())
    partitions = enumerate_legal_partitions(edges, 2)
    assert len(partitions) == 1
    assert partitions[0].anchor_tuples == ((0,), (2,))
    assert_partition_invariants(partitions[0], state, BCEMConfig())


def test_multiple_negative_barriers():
    state = ObservationState((0, 2, 4, 6), (1, 3, 5), ())
    edges = legal_group_edges(units(), state, BCEMConfig())
    partition = enumerate_legal_partitions(edges, 4)[0]
    assert partition.anchor_tuples == ((0,), (2,), (4,), (6,))
    assert_partition_invariants(partition, state, BCEMConfig())


def test_duration_cap_boundary():
    cfg = BCEMConfig(core_cap_seconds=40.0, output_cap_seconds=60.0)
    exact = legal_group_edges(units(), ObservationState((0, 3), (), ()), cfg)
    assert any(g.anchors == (0, 3) and g.span_seconds == 40.0 for g in exact[0])
    over = legal_group_edges(units(), ObservationState((0, 4), (), ()), cfg)
    assert not any(g.anchors == (0, 4) for g in over[0])

    # IDs and endpoints may both be monotone while consecutive unit intervals
    # overlap (the frozen UnitTable has this shape at its terminal pair).  Such
    # anchors may merge, but the overlap is not a legal output-event cut.
    overlapping_units = pd.DataFrame({
        "unit_id": [0, 1], "start_time": [0.0, 9.0], "end_time": [10.0, 19.0]
    })
    overlap_state = ObservationState((0, 1), (), ())
    overlap_edges = legal_group_edges(overlapping_units, overlap_state, cfg)
    overlap_partitions = enumerate_legal_partitions(overlap_edges, 2)
    assert [p.anchor_tuples for p in overlap_partitions] == [((0, 1),)]
    assert_partition_invariants(overlap_partitions[0], overlap_state, cfg)

    infeasible_units = pd.DataFrame({
        "unit_id": [0, 1], "start_time": [0.0, 20.0], "end_time": [30.0, 50.0]
    })
    infeasible_edges = legal_group_edges(infeasible_units, overlap_state, cfg)
    assert enumerate_legal_partitions(infeasible_edges, 2) == []
    with pytest.raises(RuntimeError, match="no source-to-sink path"):
        exact_ceiling_partition(infeasible_edges, 2, pd.DataFrame({"start_time": [0.0], "end_time": [1.0]}))
