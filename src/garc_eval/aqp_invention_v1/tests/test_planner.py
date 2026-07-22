from __future__ import annotations

import itertools
import unittest

from garc_eval.aqp_invention_v1.planner import PlanEdge, assign_owner, optimize_cover


class PlannerTests(unittest.TestCase):
    def test_dense_fallback_is_available(self):
        edges = [PlanEdge(i, i + 1, "DENSE_UNIT", 1.0, 0.0, i, i + 1) for i in range(4)]
        plan = optimize_cover(4, edges, max_risk=0.0, risk_quantum=0.01)
        self.assertEqual(plan.predicted_cost, 4.0)
        self.assertEqual(plan.logical_calls, 4)

    def test_enumeration_beats_dense_when_feasible(self):
        edges = [PlanEdge(i, i + 1, "DENSE_UNIT", 1.0, 0.0, i, i + 1) for i in range(4)]
        edges += [PlanEdge(0, 2, "ENUM", 0.8, 0.1, 0, 3), PlanEdge(2, 4, "ENUM", 0.8, 0.1, 1, 4)]
        plan = optimize_cover(4, edges, max_risk=0.2, risk_quantum=0.1)
        self.assertEqual([e.operator for e in plan.edges], ["ENUM", "ENUM"])
        self.assertAlmostEqual(plan.predicted_cost, 1.6)

    def test_risk_rounds_up(self):
        edges = [PlanEdge(0, 2, "ENUM", 0.1, 0.11, 0, 2)]
        with self.assertRaises(RuntimeError):
            optimize_cover(2, edges, max_risk=0.1, risk_quantum=0.1)

    def test_dp_matches_bruteforce_small(self):
        n = 5
        edges = []
        for i in range(n):
            edges.append(PlanEdge(i, i + 1, "D", 1.0, 0.0, i, i + 1))
            if i + 2 <= n:
                edges.append(PlanEdge(i, i + 2, "E2", 1.2, 0.1, i, i + 2))
            if i + 3 <= n:
                edges.append(PlanEdge(i, i + 3, "E3", 1.5, 0.2, i, i + 3))
        plan = optimize_cover(n, edges, max_risk=0.3, risk_quantum=0.1)
        paths = []
        def walk(pos, path):
            if pos == n:
                if sum(e.predicted_risk for e in path) <= 0.3 + 1e-12:
                    paths.append(tuple(path))
                return
            for e in edges:
                if e.start == pos:
                    walk(e.end, path + [e])
        walk(0, [])
        brute = min(sum(e.predicted_cost for e in p) for p in paths)
        self.assertAlmostEqual(plan.predicted_cost, brute)

    def test_unique_ownership(self):
        edges = [PlanEdge(0, 2, "E", 1, 0, 0, 3), PlanEdge(2, 5, "E", 1, 0, 1, 5)]
        self.assertEqual(assign_owner(1.5, edges).start, 0)
        self.assertEqual(assign_owner(2.0, edges).start, 2)


if __name__ == "__main__":
    unittest.main()
