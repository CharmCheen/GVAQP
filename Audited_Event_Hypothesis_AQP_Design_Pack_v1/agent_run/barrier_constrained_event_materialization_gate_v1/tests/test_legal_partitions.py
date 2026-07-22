import pandas as pd
import pytest

from garc_eval.bcem_gate_v1.core import (
    BCEMConfig, ObservationState, count_legal_partitions,
    enumerate_legal_partitions, legal_group_edges, parse_observations,
)


def units(n=12):
    return pd.DataFrame({"unit_id": range(n), "start_time": [10.0*i for i in range(n)],
                         "end_time": [10.0*(i+1) for i in range(n)]})


def state(positive=(), negative=()):
    return ObservationState(tuple(sorted(positive)), tuple(sorted(negative)), ())


def test_isolated_adjacent_and_unknown_gap():
    cfg = BCEMConfig()
    isolated = legal_group_edges(units(), state([3]), cfg)
    assert count_legal_partitions(isolated, 1) == 1
    adjacent = legal_group_edges(units(), state([2, 3]), cfg)
    assert count_legal_partitions(adjacent, 2) == 2
    unknown = legal_group_edges(units(), state([2, 4]), cfg)
    joined = [g for g in unknown[0] if len(g.anchors) == 2][0]
    assert joined.unknown_internal_units == (3,)
    assert count_legal_partitions(unknown, 2) == 2


def test_several_feasible_partitions_and_independent_blocks():
    cfg = BCEMConfig()
    edges = legal_group_edges(units(), state([0, 1, 2]), cfg)
    assert count_legal_partitions(edges, 3) == 4
    blocked = legal_group_edges(units(), state([0, 2, 4], [1, 3]), cfg)
    assert count_legal_partitions(blocked, 3) == 1
    assert all(len(g.anchors) == 1 for p in enumerate_legal_partitions(blocked, 3) for g in p.groups)


def test_all_positive_and_no_positive_trace():
    cfg = BCEMConfig()
    s = state(range(5))
    edges = legal_group_edges(units(), s, cfg)
    # Groups may span at most four 10-second units.
    assert count_legal_partitions(edges, 5) == 15
    assert count_legal_partitions({}, 0) == 1
    assert enumerate_legal_partitions({}, 0)[0].groups == ()


def test_abstain_is_explicit_error():
    trace = pd.DataFrame({"unit_id": [1], "oracle_label_after_query": ["abstain"]})
    with pytest.raises(ValueError, match="abstain"):
        parse_observations(trace)


def test_row_order_invariance():
    cfg = BCEMConfig()
    trace = pd.DataFrame({"unit_id": [6, 2, 4, 3],
                          "oracle_label_after_query": ["positive", "positive", "positive", "negative"]})
    a = parse_observations(trace)
    b = parse_observations(trace.sample(frac=1, random_state=91))
    assert a == b
    ea, eb = legal_group_edges(units(), a, cfg), legal_group_edges(units().sample(frac=1, random_state=7), b, cfg)
    assert {i: tuple(g.anchors for g in gs) for i, gs in ea.items()} == {i: tuple(g.anchors for g in gs) for i, gs in eb.items()}

