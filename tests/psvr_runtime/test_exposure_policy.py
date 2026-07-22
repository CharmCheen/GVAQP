import copy

import pytest

from garc_eval.psvr_exposure.policy_service import decide_frontier


def payload(method: str) -> dict:
    return {
        "method": method,
        "public_units": [
            {
                "unit_id": index,
                "start_time": float(index * 10),
                "end_time": float((index + 1) * 10),
                "duration_seconds": 10.0,
            }
            for index in range(4)
        ],
        "candidate_rows": [
            {
                "candidate_id": "u0_t1",
                "unit_id": 0,
                "track_id": 1,
                "proxy_score": 0.95,
                "creation_scan_index": 0,
                "score_availability_seconds": 1.0,
            },
            {
                "candidate_id": "u0_t2",
                "unit_id": 0,
                "track_id": 2,
                "proxy_score": 0.90,
                "creation_scan_index": 0,
                "score_availability_seconds": 1.0,
            },
            {
                "candidate_id": "u3_t1",
                "unit_id": 3,
                "track_id": 1,
                "proxy_score": 0.10,
                "creation_scan_index": 1,
                "score_availability_seconds": 2.0,
            },
        ],
        "queried_rows": [],
        "pending_unit_ids": [],
        "candidate_capacity": 2,
        "current_scan_index": 2,
        "parameters": {},
    }


def test_score_only_retains_two_highest_scores_even_in_same_cell():
    result = decide_frontier(payload("score_only"))
    assert result["retained_candidate_ids"] == ["u0_t1", "u0_t2"]
    assert result["frontier_unique_temporal_cells"] == 1


def test_exposure_suppression_retains_temporally_distinct_candidate():
    result = decide_frontier(payload("exposure_aware"))
    assert result["retained_candidate_ids"] == ["u0_t1", "u3_t1"]
    assert result["frontier_unique_temporal_cells"] == 2


def test_fifo_and_exposure_decisions_are_deterministic():
    for method in (
        "fifo",
        "score_only",
        "exposure_aware",
        "cell_diverse_conservative",
    ):
        first = decide_frontier(payload(method))
        second = decide_frontier(copy.deepcopy(payload(method)))
        assert first == second


def test_policy_rejects_reference_or_future_fields():
    invalid = payload("score_only")
    invalid["public_units"][0]["parsed_label"] = "positive"
    with pytest.raises(ValueError, match="forbidden"):
        decide_frontier(invalid)


def test_cell_diverse_uses_cell_fifo_not_global_proxy_score():
    value = payload("cell_diverse_conservative")
    result = decide_frontier(value)
    assert result["retained_candidate_ids"] == ["u0_t1", "u3_t1"]
    assert result["selected_candidate_id"] == "u0_t1"
    assert result["priority_rows"][0]["confirmed_exclusion_window_seconds"] == 10.0


def test_cell_diverse_suppresses_confirmed_neighbor_without_tuning():
    value = payload("cell_diverse_conservative")
    value["queried_rows"] = [{"unit_id": 0, "parsed_label": "positive"}]
    value["candidate_rows"] = [
        row for row in value["candidate_rows"] if int(row["unit_id"]) != 0
    ]
    value["candidate_rows"].append({
        "candidate_id": "u1_t1",
        "unit_id": 1,
        "track_id": 1,
        "proxy_score": 0.99,
        "creation_scan_index": 1,
        "score_availability_seconds": 2.0,
    })
    result = decide_frontier(value)
    assert result["selected_candidate_id"] == "u3_t1"
