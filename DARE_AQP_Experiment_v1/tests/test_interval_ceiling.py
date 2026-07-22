import math
import itertools
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))

from dare_aqp.interval_ceiling import (
    any_binary_full,
    count_guided,
    count_root_any_best_first,
    split_interval,
    trace_cost,
)


class IntervalCeilingTests(unittest.TestCase):
    def setUp(self):
        self.n = 17
        self.anchors = {1, 4, 9, 16}
        self.proxy = [float(i % 5) for i in range(self.n)]

    def test_split_partitions_odd_interval(self):
        left, right = split_interval(0, 17)
        self.assertEqual(left, (0, 8))
        self.assertEqual(right, (8, 17))

    def test_binary_full_recovers_all_anchors(self):
        _, found = any_binary_full(self.n, self.anchors)
        self.assertEqual(found, self.anchors)

    def test_count_guided_meets_each_target(self):
        for target in (0.5, 0.8, 1.0):
            _, found = count_guided(self.n, self.anchors, self.proxy, target)
            self.assertGreaterEqual(len(found), math.ceil(target * len(self.anchors)))
            self.assertTrue(found.issubset(self.anchors))

    def test_best_first_public_and_oracle_meet_target(self):
        for oracle in (False, True):
            _, found = count_root_any_best_first(
                self.n, self.anchors, self.proxy, 0.8, oracle_priority=oracle
            )
            self.assertGreaterEqual(len(found), 4)

    def test_linear_interval_cost_cannot_hide_scanned_length(self):
        queries, found = any_binary_full(self.n, self.anchors)
        linear = trace_cost(queries, 0.0, certify_count=len(found))
        constant = trace_cost(queries, 1.0, certify_count=len(found))
        self.assertGreater(linear, constant)

    def test_small_population_exhaustive_count_recovery(self):
        n = 7
        proxy = [0.1 * i for i in range(n)]
        for size in range(1, n + 1):
            for subset in itertools.combinations(range(n), size):
                queries, found = count_guided(n, set(subset), proxy, 1.0)
                self.assertEqual(found, set(subset))
                self.assertTrue(all(q.operator == "COUNT_EVENTS" for q in queries))
                self.assertTrue(all(0 <= q.lo < q.hi <= n for q in queries))

    def test_cost_matches_closed_form(self):
        queries, found = count_guided(self.n, self.anchors, self.proxy, 0.8)
        alpha, multiplier = 0.37, 1.25
        expected = multiplier * sum(
            alpha + (1 - alpha) * q.length for q in queries
        ) + len(found)
        self.assertAlmostEqual(
            trace_cost(queries, alpha, multiplier, len(found), 1.0), expected
        )


if __name__ == "__main__":
    unittest.main()
