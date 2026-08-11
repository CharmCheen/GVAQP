import json

from garc.controller.runner import ReplayControllerRunner


def test_controller_runner_integrates_complete_actions_and_durable_commit(tmp_path):
    units = [
        {"unit_id": 0, "start_sec": 0, "end_sec": 10, "scan_cost_sec": 1, "candidates": []},
        {"unit_id": 1, "start_sec": 10, "end_sec": 20, "scan_cost_sec": 1,
         "candidates": [{"candidate_id": "c1", "track_id": 1, "score": .8}]},
        {"unit_id": 2, "start_sec": 20, "end_sec": 30, "scan_cost_sec": 1, "candidates": []},
    ]
    outcomes = {1: {"positive": True, "distinct_utility_ids": ["e1"], "actual_cost_sec": 2}}
    path = tmp_path / "commit.json"
    summary = ReplayControllerRunner(units, 10, outcomes, commit_path=path).run()
    durable = json.loads(path.read_text())
    assert summary["distinct_utility_count"] == 1
    assert durable["distinct_utility_ids"] == ["e1"]
    assert durable["status"] == "FINAL"
    assert durable["final_result"] == summary
    assert durable["stop_reason"] == "no_complete_action_fits"
    assert all(row["completed"] for row in durable["actions"])
