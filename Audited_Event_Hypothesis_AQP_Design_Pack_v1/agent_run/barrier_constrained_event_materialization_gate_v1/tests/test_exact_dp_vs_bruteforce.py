import numpy as np
import pandas as pd

from garc_eval.bcem_gate_v1.ceiling import exact_ceiling_partition, score_partition_ordered
from garc_eval.bcem_gate_v1.core import (
    BCEMConfig, ObservationState, count_legal_partitions,
    enumerate_legal_partitions, legal_group_edges, optimize_additive_partition,
)


def units(n=10):
    return pd.DataFrame({"unit_id": range(n), "start_time": [10.0*i for i in range(n)],
                         "end_time": [10.0*(i+1) for i in range(n)]})


def brute_ceiling(partitions, reference):
    candidates = []
    r = len(reference)
    for partition in partitions:
        matched, iou, matching = score_partition_ordered(partition, reference)
        pred = len(partition.groups)
        f1 = 2.0 * matched / (pred + r) if pred + r else 0.0
        returned = sum(g.span_seconds for g in partition.groups)
        key = (-f1, -iou, returned, partition.anchor_tuples, matching)
        candidates.append((key, partition, f1, matched, iou))
    return min(candidates, key=lambda x: x[0])


def test_deterministic_additive_tie_break():
    state = ObservationState((0, 1), (), ())
    edges = legal_group_edges(units(), state, BCEMConfig())
    partition, cost = optimize_additive_partition(edges, 2, lambda g: 0.0)
    assert cost == 0.0
    assert partition.anchor_tuples == ((0,), (1,))


def test_exact_additive_dp_vs_bruteforce_random():
    rng = np.random.default_rng(20260711)
    for _ in range(100):
        positive = tuple(sorted(rng.choice(8, size=int(rng.integers(0, 6)), replace=False).tolist()))
        remaining = [u for u in range(8) if u not in positive]
        negative = tuple(sorted(u for u in remaining if rng.random() < 0.3))
        state = ObservationState(positive, negative, ())
        edges = legal_group_edges(units(8), state, BCEMConfig()) if positive else {}
        partitions = enumerate_legal_partitions(edges, len(positive), limit=10000)
        cost = lambda g: 1.0 + 0.13*len(g.unknown_internal_units) + 0.001*g.span_seconds
        dp, dp_cost = optimize_additive_partition(edges, len(positive), cost)
        brute = min(((sum(cost(g) for g in p.groups), p.anchor_tuples, p) for p in partitions), key=lambda x: (x[0], x[1]))
        assert abs(dp_cost - brute[0]) < 1e-12
        assert dp.anchor_tuples == brute[2].anchor_tuples


def test_exact_reference_ceiling_dp_vs_bruteforce_random():
    rng = np.random.default_rng(20260712)
    for _ in range(100):
        positive = tuple(sorted(rng.choice(8, size=int(rng.integers(0, 7)), replace=False).tolist()))
        remaining = [u for u in range(8) if u not in positive]
        negative = tuple(sorted(u for u in remaining if rng.random() < 0.25))
        state = ObservationState(positive, negative, ())
        edges = legal_group_edges(units(8), state, BCEMConfig()) if positive else {}
        partitions = enumerate_legal_partitions(edges, len(positive), limit=10000)
        starts = sorted(rng.choice(8, size=int(rng.integers(1, 5)), replace=False).tolist())
        refs = pd.DataFrame({"start_time": [10.0*s for s in starts],
                             "end_time": [10.0*min(8, s+int(rng.integers(1, 3))) for s in starts]})
        # Make random references ordered and non-overlapping, matching benchmark assumptions.
        rows = []
        last_end = -1.0
        for r in refs.sort_values("start_time").itertuples():
            start = max(float(r.start_time), last_end)
            end = max(start + 1.0, float(r.end_time))
            rows.append({"start_time": start, "end_time": end})
            last_end = end
        refs = pd.DataFrame(rows)
        result = exact_ceiling_partition(edges, len(positive), refs)
        brute = brute_ceiling(partitions, refs)
        assert abs(result.event_f1 - brute[2]) < 1e-12
        assert result.matched_count == brute[3]
        assert abs(result.total_iou - brute[4]) < 1e-12
        assert result.partition.anchor_tuples == brute[1].anchor_tuples
        assert count_legal_partitions(edges, len(positive)) == len(partitions)

