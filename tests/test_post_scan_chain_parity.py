import json

import pytest

from frozen_reference import source_final_snapshot, source_materialize, source_materialize_result
from garc.confirm import (
    ConfirmAdapter, ConfirmParseError, DurableCommitLog, MaterializationError, materialize_candidate,
    materialize_confirm_result, parse_confirm_result,
)
from garc.controller import Candidate, CandidateGenerationError, FrozenCandidateGenerator
from garc.controller.runner import ReplayControllerRunner


def candidate(unit=1, score=.8, track=2, name="candidate-1", payload=None):
    return Candidate(name, unit, track, score, 1.0, 0, payload or {"clip": [10, 20]})


def test_candidate_generation_binds_top_track_and_reemits_visible_prefix():
    generator = FrozenCandidateGenerator()
    visible = generator.observe_scan(4, [
        {"candidate_id": "low", "track_id": 1, "score": .2},
        {"candidate_id": "tie-high-id", "track_id": 3, "score": .9},
        {"candidate_id": "winner", "track_id": 2, "score": .9},
    ], elapsed_sec=2.0, scan_index=0)
    assert [(row.unit_id, row.track_id, row.candidate_id) for row in visible] == [(4, 2, "winner")]
    visible = generator.observe_scan(7, [
        {"candidate_id": "other", "track_id": 5, "score": .5},
    ], elapsed_sec=4.0, scan_index=1)
    assert [(row.unit_id, row.candidate_id) for row in visible] == [(4, "winner"), (7, "other")]
    assert visible[0].created_elapsed_sec == 2.0


def test_materialization_and_result_parsing_parity():
    row = candidate()
    assert materialize_candidate(row) == source_materialize(row)
    request = materialize_candidate(row)
    parsed = parse_confirm_result({
        "completed": True, "positive": True,
        "distinct_utility_ids": ["e2", "e1", "e2"], "actual_cost_sec": 2.5,
    }, row, request)
    assert parsed.raw_utility_ids == ("e2", "e1", "e2")
    assert materialize_confirm_result(parsed.positive, parsed.raw_utility_ids) == source_materialize_result(
        True, ["e2", "e1", "e2"]
    )
    negative = parse_confirm_result({
        "positive": False, "distinct_utility_ids": ["must-not-count"], "actual_cost_sec": 1,
    }, row, request)
    assert materialize_confirm_result(negative.positive, negative.raw_utility_ids) == source_materialize_result(
        False, ["must-not-count"]
    )
    with pytest.raises(ConfirmParseError):
        parse_confirm_result({"actual_cost_sec": "not-a-cost"}, row, request)
    with pytest.raises(ConfirmParseError):
        parse_confirm_result({"actual_cost_sec": 1, "distinct_utility_ids": "not-a-sequence"}, row, request)


def test_bound_candidate_may_not_silently_change_or_disappear():
    generator = FrozenCandidateGenerator()
    generator.observe_scan(1, [{"track_id": 4, "score": .7}], elapsed_sec=1, scan_index=0)
    with pytest.raises(CandidateGenerationError, match="disappeared"):
        generator.observe_scan(1, [{"track_id": 8, "score": .9}], elapsed_sec=2, scan_index=1)


def test_durable_final_result_parity(tmp_path):
    path = tmp_path / "durable.json"
    log = DurableCommitLog(path)
    action = {"action": "CONFIRM", "completed": True, "elapsed_sec": 2.0,
              "new_distinct_utility": 1, "cumulative_utility": 1}
    log.append(action, ("event-1", "event-1"))
    final = {"distinct_utility_count": 1, "actions_completed": 1}
    log.finalize(final, stop_reason="no_complete_action_fits")
    assert json.loads(path.read_text()) == source_final_snapshot(
        [action], ["event-1"], final, "no_complete_action_fits"
    )


def _single_candidate_units():
    return [{"unit_id": 0, "start_sec": 0, "end_sec": 10, "scan_cost_sec": 1,
             "candidates": [{"candidate_id": "c0", "track_id": 2, "score": .9}]}]


def test_confirm_execution_failure_returns_last_durable_snapshot(tmp_path):
    outcome = {0: {"completed": False, "status": "failed", "error": "replay failure",
                   "actual_cost_sec": .5}}
    path = tmp_path / "failed.json"
    summary = ReplayControllerRunner(_single_candidate_units(), 10, outcome, commit_path=path).run()
    durable = json.loads(path.read_text())
    assert durable["status"] == "FINAL" and durable["stop_reason"] == "action_failed"
    assert durable["error"]["error_type"] == "ConfirmExecutionError"
    assert [row["action"] for row in durable["actions"]] == ["SCAN"]
    assert summary["elapsed_sec"] == 1.5 and summary["frontier_size"] == 1


def test_materialization_failure_returns_last_durable_snapshot(tmp_path):
    def fail_materialization(_candidate):
        raise MaterializationError("cannot materialize")

    backend = {0: {"positive": True, "distinct_utility_ids": ["e1"], "actual_cost_sec": 1}}
    adapter = ConfirmAdapter(backend, materializer=fail_materialization)
    path = tmp_path / "materialize-failed.json"
    summary = ReplayControllerRunner(_single_candidate_units(), 10, backend, commit_path=path,
                                     confirm_adapter=adapter).run()
    durable = json.loads(path.read_text())
    assert durable["stop_reason"] == "action_failed"
    assert durable["error"]["error_type"] == "MaterializationError"
    assert summary["distinct_utility_count"] == 0 and summary["frontier_size"] == 1
    assert summary["elapsed_sec"] == 1


def test_post_result_materialization_failure_returns_last_durable_snapshot(tmp_path):
    def fail_event_materialization(_positive, _ids):
        raise MaterializationError("K3 replay materialization failed")

    backend = {0: {"positive": True, "distinct_utility_ids": ["e1"], "actual_cost_sec": 1}}
    adapter = ConfirmAdapter(backend, event_materializer=fail_event_materialization)
    path = tmp_path / "event-materialize-failed.json"
    summary = ReplayControllerRunner(_single_candidate_units(), 10, backend, commit_path=path,
                                     confirm_adapter=adapter).run()
    durable = json.loads(path.read_text())
    assert durable["stop_reason"] == "action_failed"
    assert durable["error"]["error_type"] == "MaterializationError"
    assert summary["distinct_utility_count"] == 0 and summary["frontier_size"] == 1
    assert summary["elapsed_sec"] == 2


def test_duplicate_candidate_clusters_and_events_are_counted_once(tmp_path):
    units = [
        {"unit_id": 0, "start_sec": 0, "end_sec": 10, "scan_cost_sec": 1,
         "candidates": [{"candidate_id": "c0-low", "track_id": 9, "score": .1},
                        {"candidate_id": "c0", "track_id": 1, "score": .9}]},
        {"unit_id": 1, "start_sec": 10, "end_sec": 20, "scan_cost_sec": 1, "candidates": []},
        {"unit_id": 2, "start_sec": 20, "end_sec": 30, "scan_cost_sec": 1,
         "candidates": [{"candidate_id": "c2", "track_id": 2, "score": .8}]},
        {"unit_id": 3, "start_sec": 30, "end_sec": 40, "scan_cost_sec": 1, "candidates": []},
    ]
    outcomes = {
        0: {"positive": True, "distinct_utility_ids": ["event-1"], "actual_cost_sec": 1},
        2: {"positive": True, "distinct_utility_ids": ["event-1"], "actual_cost_sec": 1},
    }
    path = tmp_path / "dedup.json"
    summary = ReplayControllerRunner(units, 20, outcomes, commit_path=path).run()
    durable = json.loads(path.read_text())
    confirms = [row for row in durable["actions"] if row["action"] == "CONFIRM"]
    assert [row["new_distinct_utility"] for row in confirms] == [1, 0]
    assert durable["distinct_utility_ids"] == ["event-1"]
    assert summary["distinct_utility_count"] == 1


def test_commit_state_changes_only_after_atomic_write_succeeds(tmp_path):
    log = DurableCommitLog(tmp_path / "never-written.json")
    log._write = lambda _value: (_ for _ in ()).throw(OSError("disk failure"))
    try:
        log.append({"action": "SCAN", "completed": True}, ())
    except OSError:
        pass
    else:
        raise AssertionError("commit failure was hidden")
    assert log.rows == [] and log.utility_ids == set()
