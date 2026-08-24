import json
import tempfile
import unittest
from pathlib import Path

from garc.datb_sv import DatbSVConfig, DatbSVReplayRunner, bisection_order


def units(scan_cost=1.0):
    return [
        {
            "unit_id": index,
            "start_sec": index * 10.0,
            "end_sec": (index + 1) * 10.0,
            "scan_cost_sec": scan_cost,
            "candidates": [{"candidate_id": f"c{index}", "track_id": 0, "score": 1.0 - index / 10}],
        }
        for index in range(4)
    ]


def outcomes(cost=2.0):
    return {
        0: {"positive": True, "distinct_utility_ids": ["event-shared"], "actual_cost_sec": cost},
        1: {"positive": True, "distinct_utility_ids": ["event-shared"], "actual_cost_sec": cost},
        2: {"positive": True, "distinct_utility_ids": ["event-2"], "actual_cost_sec": cost},
        3: {"positive": False, "distinct_utility_ids": [], "actual_cost_sec": cost},
    }


class DatbSVTest(unittest.TestCase):
    def run_case(self, rows=None, backend=None, config=None, source="VLM"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runner = DatbSVReplayRunner(
            rows or units(),
            backend or outcomes(),
            config or DatbSVConfig(20, 1, 2, 0.25),
            commit_path=Path(temporary.name) / "durable.json",
            oracle_metadata={"label_source": source},
        )
        summary = runner.run()
        durable = json.loads((Path(temporary.name) / "durable.json").read_text())
        return runner, summary, durable

    def test_frozen_bisection_order(self):
        self.assertEqual(bisection_order(0), ())
        self.assertEqual(bisection_order(4), (1, 0, 2, 3))
        self.assertEqual(bisection_order(35)[:6], (17, 8, 26, 3, 12, 21))
        self.assertEqual(sorted(bisection_order(35)), list(range(35)))

    def test_fixed_scan_verify_interleaving_and_event_dedup(self):
        runner, summary, _ = self.run_case()
        self.assertEqual([row["action"] for row in runner.trace[:4]], ["SCAN", "CONFIRM", "SCAN", "CONFIRM"])
        self.assertEqual([row["unit_id"] for row in runner.trace[:4]], [1, 1, 0, 0])
        self.assertEqual(summary["distinct_utility_ids"].count("event-shared"), 1)
        self.assertIn("event-2", summary["distinct_utility_ids"])
        self.assertEqual(summary["scan_actions"], summary["verify_actions"])

    def test_commit_reserve_and_safe_fallback_stop(self):
        config = DatbSVConfig(4.5, 1, 2, 0.5)
        runner, summary, durable = self.run_case(config=config)
        self.assertEqual([row["action"] for row in runner.trace], ["SCAN", "CONFIRM", "SCAN"])
        self.assertEqual(summary["stop_reason"], "NO_COMPLETE_ACTION_FITS")
        self.assertEqual(len(durable["actions"]), 3)
        self.assertLessEqual(durable["actions"][-1]["complete_sec"] + config.commit_reserve_sec, config.deadline_sec)

    def test_post_deadline_action_is_diagnostic_only(self):
        config = DatbSVConfig(2.5, 1, 2, 0.0)
        runner, summary, durable = self.run_case(rows=units(scan_cost=3.0), config=config)
        self.assertEqual(summary["durable_actions"], 0)
        self.assertEqual(summary["diagnostic_actions"], 1)
        self.assertEqual(summary["stop_reason"], "POST_DEADLINE_DIAGNOSTIC_ONLY")
        self.assertEqual(durable["actions"], [])
        self.assertEqual(durable["distinct_utility_ids"], [])
        self.assertFalse(runner.trace[0]["completed_by_deadline"])

    def test_oracle_source_is_not_used_by_scheduling(self):
        left, left_summary, _ = self.run_case(source="HUMAN")
        right, right_summary, _ = self.run_case(source="HEAVY_VLM")
        left_actions = [(row["action"], row["unit_id"]) for row in left.trace]
        right_actions = [(row["action"], row["unit_id"]) for row in right.trace]
        self.assertEqual(left_actions, right_actions)
        self.assertEqual(left_summary["distinct_utility_ids"], right_summary["distinct_utility_ids"])
        self.assertNotEqual(
            left_summary["oracle_metadata_recorded_not_inspected"],
            right_summary["oracle_metadata_recorded_not_inspected"],
        )

    def test_declared_cost_bound_violation_stops_after_durable_action(self):
        config = DatbSVConfig(10, 1, 2, 0)
        runner, summary, durable = self.run_case(rows=units(scan_cost=1.5), config=config)
        self.assertEqual(summary["stop_reason"], "DECLARED_COST_BOUND_VIOLATED")
        self.assertEqual(len(durable["actions"]), 1)
        self.assertTrue(runner.trace[0]["cost_bound_violation"])


if __name__ == "__main__":
    unittest.main()
