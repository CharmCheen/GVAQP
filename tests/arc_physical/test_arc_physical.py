from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from garc_eval.arc_cached_replay import ARCConfig
from garc_eval.arc_physical import (
    ARC_PHYSICAL_METHOD,
    CURRENT_ACCELERATED_METHOD,
    ARCPhysicalPolicy,
    ARCPhysicalRuntime,
    CalibrationContractError,
    ProxyPassIncompleteError,
    TestIdentityCalibrator,
    audit_shared_contract,
    load_deployable_calibrator,
)
from garc_eval.arc_physical.policy import physical_outcome


REPO = Path(__file__).resolve().parents[2]
READINESS = (
    REPO
    / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a"
    / "modeling/STAGE_A_MODEL_READINESS_DECISION.json"
)


def _policy(scores: list[float], *, seed: int = 0) -> ARCPhysicalPolicy:
    policy = ARCPhysicalPolicy(
        range(len(scores)),
        query_id="Q1",
        seed=seed,
        calibrator=TestIdentityCalibrator(),
        config=ARCConfig(confidence=2.0),
    )
    for unit_id, score in enumerate(scores):
        policy.observe_proxy_score(unit_id, score)
    return policy


def _result(unit_id: int, label: str, parse_status: str = "ok") -> dict:
    return {
        "unit_id": unit_id,
        "parsed_label": label,
        "parse_status": parse_status,
        "physical_oracle_invocation": True,
        "cache_replay": False,
    }


def test_non_deployable_stage_a_calibrator_fails_closed_before_use() -> None:
    with pytest.raises(CalibrationContractError, match="not deployable"):
        load_deployable_calibrator(
            READINESS,
            expected_proxy_family="Y8",
            expected_proxy_config_hash="irrelevant-because-gate-is-first",
        )


def test_deployable_piecewise_calibrator_schema_and_mapping(tmp_path: Path) -> None:
    artifact = tmp_path / "calibrator.json"
    artifact.write_text(json.dumps({
        "artifact_id": "frozen-test-calibrator",
        "deployable": True,
        "model_type": "piecewise_linear_v1",
        "proxy_family": "Y8",
        "proxy_config_hash": "proxy-hash",
        "heldout_opened": False,
        "query_knots": {
            "Q1": [[0.0, 0.1], [0.5, 0.4], [1.0, 0.9]],
            "Q2": [[0.0, 0.2], [1.0, 0.8]],
        },
    }))
    calibrator = load_deployable_calibrator(
        artifact,
        expected_proxy_family="Y8",
        expected_proxy_config_hash="proxy-hash",
    )
    assert calibrator.predict("Q1", [0.0, 0.5, 1.0]).tolist() == [0.1, 0.4, 0.9]


def test_refinement_requires_complete_online_proxy_pass() -> None:
    policy = ARCPhysicalPolicy(
        range(3), query_id="Q1", seed=0, calibrator=TestIdentityCalibrator()
    )
    policy.observe_proxy_score(0, 0.9)
    policy.observe_proxy_score(1, 0.8)
    with pytest.raises(ProxyPassIncompleteError, match="complete proxy pass"):
        policy.finish_proxy_pass()
    with pytest.raises(ProxyPassIncompleteError):
        policy.select_next()
    assert policy.diagnostics()["logical_oracle_calls"] == 0


def test_probability_vector_js_cluster_and_tau_contract() -> None:
    policy = _policy([0.1, 0.1, 0.9])
    summary = policy.finish_proxy_pass()
    assert summary["bernoulli_vectors"] == [[0.9, 0.1], [0.9, 0.1], [0.09999999999999998, 0.9]]
    assert summary["cluster_labels"] == [0, 0, 1]
    assert policy.config.tau_units == 1


@pytest.mark.parametrize(
    ("label", "parse_status", "expected"),
    [
        ("negative", "failed", "parse_failure"),
        ("abstain", "ok", "abstain"),
        ("unexpected", "ok", "unusable"),
    ],
)
def test_unknown_parse_semantics_are_not_coerced_negative(
    label: str, parse_status: str, expected: str
) -> None:
    assert physical_outcome(_result(0, label, parse_status)).outcome == expected


def test_propagated_labels_are_diagnostics_only() -> None:
    policy = _policy([0.9, 0.9, 0.9, 0.2], seed=1)
    policy.finish_proxy_pass()
    selection = policy.select_next()
    assert selection is not None
    policy.observe_verify(selection, _result(selection.unit_id, "positive"))
    diagnostics = policy.diagnostics()["selector"]
    assert diagnostics["propagated_positive_unit_ids"]
    assert policy.comparable_queried_rows() == [
        {"unit_id": selection.unit_id, "parsed_label": "positive"}
    ]


class _Clock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> int:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += int(seconds * 1e9)


def test_incomplete_proxy_deadline_never_starts_refinement_and_keeps_last_commit() -> None:
    clock = _Clock()
    policy = ARCPhysicalPolicy(
        range(4), query_id="Q1", seed=0, calibrator=TestIdentityCalibrator()
    )
    queried: list[int] = []
    commits: list[str] = []

    def scan(unit):
        clock.advance(1.0)
        return {"unit_id": unit["unit_id"]}

    def commit(rows, action, raw):
        del rows, raw
        clock.advance(0.5)
        commits.append(action)
        return {"snapshot_path": f"snapshot_{len(commits)}.json", "confirmed_events": 0}

    runtime = ARCPhysicalRuntime(
        policy=policy,
        units=[{"unit_id": i} for i in range(4)],
        deadline_seconds=5.0,
        run_start_ns=0,
        scan_upper_seconds=1.0,
        commit_upper_seconds=0.5,
        scan_unit=scan,
        finalize_proxy_scores=lambda scans: pytest.fail("partial proxy was finalized"),
        query_oracle=lambda unit_id: queried.append(unit_id),
        commit_snapshot=commit,
        admit_verify=lambda elapsed: {"admitted": True},
        final_synchronize=lambda: clock.advance(0.1),
        clock_ns=clock.now,
    ).run()
    assert runtime.stop_reason == "insufficient_scan_and_commit_reservation"
    assert runtime.proxy_pass_complete is False
    assert runtime.refinement_started is False
    assert runtime.logical_oracle_calls == 0
    assert queried == []
    assert runtime.checkpoints[-1]["confirmed_events"] == 0
    assert runtime.snapshot_elapsed_seconds <= runtime.deadline_seconds


def _deterministic_runtime_trace() -> tuple[list[int], dict]:
    clock = _Clock()
    policy = ARCPhysicalPolicy(
        range(4),
        query_id="Q1",
        seed=7,
        calibrator=TestIdentityCalibrator(),
        config=ARCConfig(confidence=2.0),
    )
    queried: list[int] = []

    def scan(unit):
        clock.advance(0.1)
        return {"unit_id": unit["unit_id"]}

    def query(unit_id):
        queried.append(unit_id)
        clock.advance(0.1)
        return _result(unit_id, "negative")

    def commit(rows, action, raw):
        del rows, action, raw
        clock.advance(0.01)
        return {"snapshot_path": "snapshot.json", "confirmed_events": 0}

    result = ARCPhysicalRuntime(
        policy=policy,
        units=[{"unit_id": i} for i in range(4)],
        deadline_seconds=100.0,
        run_start_ns=0,
        scan_upper_seconds=0.2,
        commit_upper_seconds=0.02,
        scan_unit=scan,
        finalize_proxy_scores=lambda scans: [0.9, 0.8, 0.7, 0.6],
        query_oracle=query,
        commit_snapshot=commit,
        admit_verify=lambda elapsed: {"admitted": True, "reason": "admitted"},
        final_synchronize=lambda: clock.advance(0.01),
        clock_ns=clock.now,
    ).run()
    return queried, result.to_dict()


def test_physical_policy_deduplicates_and_replay_is_deterministic() -> None:
    left_queries, left = _deterministic_runtime_trace()
    right_queries, right = _deterministic_runtime_trace()
    assert left_queries == right_queries
    assert len(left_queries) == len(set(left_queries))
    assert left["actions"] == right["actions"]


def test_shared_contract_binds_runner_tasks_k3_deadline_and_evaluator() -> None:
    contract = audit_shared_contract(REPO)
    assert contract["baseline_id"] == ARC_PHYSICAL_METHOD
    assert contract["current_method"] == CURRENT_ACCELERATED_METHOD
    assert contract["task_ids"] == ["V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"]
    assert contract["smoke_cell"]["task_id"] == "V0_Q1"
    assert contract["smoke_cell"]["deadline_name"] == "T_transition"
    assert contract["K3"] == {
        "mode": "k3_bridge_safe", "g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0
    }
    assert Path(contract["current_runner"]).name == "run_psvr_stage1_physical.py"
    assert Path(contract["shared_base_runner"]).name == "run_psvr_two_video_physical.py"
    assert Path(contract["evaluator"]).name == "evaluate_psvr_two_video_physical.py"
    assert contract["reference_visible_to_runtime"] is False


def test_policy_and_runtime_apis_expose_no_reference_inputs() -> None:
    for target in (ARCPhysicalPolicy.__init__, ARCPhysicalRuntime.__init__):
        names = set(inspect.signature(target).parameters)
        assert not ({"reference", "references", "current_selections", "oracle_labels"} & names)
