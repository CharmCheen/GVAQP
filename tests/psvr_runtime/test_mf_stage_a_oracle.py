from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from garc_eval.mf_psvr.stage_a_oracle import (
    append_hash_chain,
    evaluate_support_gates,
    execution_spec,
    k3_bridge_safe_groups,
    seed_for_call,
    validate_attempt_events,
)


def test_stage_a_seed_mapping_and_execution_policy_are_exact() -> None:
    assert seed_for_call("mf_psvr_stage_a_001") == 20260710
    assert seed_for_call("mf_psvr_stage_a_096") == 20260805
    with pytest.raises(ValueError):
        seed_for_call("mf_psvr_stage_a_097")
    with pytest.raises(ValueError, match="non-canonical"):
        seed_for_call("mf_psvr_stage_a_1")
    spec = execution_spec({"runner_source_sha256": "a" * 64})
    assert spec["maximum_physical_calls"] == 96
    assert "never retries or replaces" in spec["interruption_policy"]
    assert spec["call_accounting"]["query_projected_label_rows"] == 192


def test_attempt_chain_forbids_retry_of_a_started_call() -> None:
    events = []
    started = append_hash_chain(events, {
        "event": "STARTED",
        "attempt_id": "attempt_1",
        "physical_call_id": "mf_psvr_stage_a_001",
    })
    events.append(started)
    accepted = append_hash_chain(events, {
        "event": "ACCEPTED",
        "attempt_id": "attempt_1",
        "physical_call_id": "mf_psvr_stage_a_001",
    })
    events.append(accepted)
    assert validate_attempt_events(events)["accepted_durable_calls"] == 1
    with pytest.raises(ValueError, match="retry prohibited"):
        append_hash_chain(events, {
            "event": "STARTED",
            "attempt_id": "attempt_2",
            "physical_call_id": "mf_psvr_stage_a_001",
        })


def synthetic_protocol() -> dict:
    split_gate = {
        "model_train": {
            "minimum_positive_units": 4,
            "minimum_positive_source_videos": 3,
            "minimum_negative_units": 8,
            "minimum_negative_source_videos": 5,
        },
        "model_calibration": {
            "minimum_positive_units": 2,
            "minimum_positive_source_videos": 2,
            "minimum_negative_units": 4,
            "minimum_negative_source_videos": 3,
        },
        "pool_audit": {
            "minimum_positive_units": 2,
            "minimum_positive_source_videos": 2,
            "minimum_negative_units": 4,
            "minimum_negative_source_videos": 3,
        },
    }
    return {
        "stage_a_support_pilot": {
            "split_quotas": {
                "model_train": 64,
                "model_calibration": 16,
                "pool_audit": 16,
            },
            "support_existence_gate": {
                "Q1": {"minimum_positive_units": 8, "minimum_positive_source_videos": 5},
                "Q2": {"minimum_positive_units": 8, "minimum_positive_source_videos": 5},
            },
            "split_specific_usability_gates_per_query": split_gate,
        }
    }


def synthetic_labels_and_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = []
    scores = []
    for ordinal in range(2654):
        session = f"video_{ordinal:04d}"
        for query_id in ("Q1", "Q2"):
            scores.append({
                "source_dataset": "synthetic",
                "session_id": session,
                "unit_id": 0,
                "query_id": query_id,
                "unit_score": ordinal / 2653,
            })
    for ordinal in range(96):
        if ordinal < 64:
            split = "model_train"
            positive = ordinal < 8
        elif ordinal < 80:
            split = "model_calibration"
            positive = ordinal < 66
        else:
            split = "pool_audit"
            positive = ordinal < 82
        for query_id in ("Q1", "Q2"):
            labels.append({
                "physical_call_id": f"mf_psvr_stage_a_{ordinal + 1:03d}",
                "source_dataset": "synthetic",
                "session_id": f"video_{ordinal:04d}",
                "model_split_role": split,
                "unit_id": 0,
                "unit_start_seconds": 0.0,
                "unit_end_seconds": 10.0,
                "query_id": query_id,
                "verification_key": f"synthetic|video_{ordinal:04d}|{query_id}|0",
                "projected_label": "positive" if positive else "negative",
                "parse_status": "ok",
            })
    return pd.DataFrame(labels), pd.DataFrame(scores)


def test_support_gates_separate_existence_and_frozen_split_usability() -> None:
    labels, scores = synthetic_labels_and_scores()
    passed = evaluate_support_gates(labels, scores, synthetic_protocol())
    assert passed["decision"] == "STAGE_A_PASS_STAGE_B_REQUIRES_SEPARATE_AUTHORITY"
    assert passed["support_existence_all_queries_pass"] is True
    assert passed["frozen_evaluation_splits_all_queries_pass"] is True

    failed_labels = labels.copy()
    mask = (
        (failed_labels["query_id"] == "Q2")
        & (failed_labels["model_split_role"] == "model_calibration")
        & (failed_labels["projected_label"] == "positive")
    )
    failed_labels.loc[mask, "projected_label"] = "negative"
    failed = evaluate_support_gates(failed_labels, scores, synthetic_protocol())
    assert failed["support_existence_all_queries_pass"] is True
    assert failed["frozen_evaluation_splits_all_queries_pass"] is False
    assert failed["decision"] == "STOP_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE"


def test_support_gates_reject_cross_query_call_identity_mismatch() -> None:
    labels, scores = synthetic_labels_and_scores()
    row = labels.index[
        (labels["physical_call_id"] == "mf_psvr_stage_a_001")
        & (labels["query_id"] == "Q2")
    ][0]
    labels.loc[row, "session_id"] = "different_video"
    labels.loc[row, "verification_key"] = "synthetic|different_video|Q2|0"
    with pytest.raises(ValueError, match="shared physical-call identity"):
        evaluate_support_gates(labels, scores, synthetic_protocol())


def test_source_video_counts_use_dataset_and_session_compound_identity() -> None:
    labels, scores = synthetic_labels_and_scores()
    # Reuse a session ID across providers. These remain two distinct source videos.
    for call_id, source in (
        ("mf_psvr_stage_a_001", "provider_a"),
        ("mf_psvr_stage_a_002", "provider_b"),
    ):
        mask = labels["physical_call_id"] == call_id
        old_session = labels.loc[mask, "session_id"].iloc[0]
        labels.loc[mask, "source_dataset"] = source
        labels.loc[mask, "session_id"] = "shared_session"
        labels.loc[mask, "verification_key"] = labels.loc[mask, "query_id"].map(
            lambda query_id: f"{source}|shared_session|{query_id}|0"
        )
        score_mask = (scores["source_dataset"] == "synthetic") & (scores["session_id"] == old_session)
        scores.loc[score_mask, "source_dataset"] = source
        scores.loc[score_mask, "session_id"] = "shared_session"
    report = evaluate_support_gates(labels, scores, synthetic_protocol())
    assert report["per_query"]["Q1"]["positive_source_videos"] == 12


def test_k3_bridge_safe_groups_only_directly_adjacent_positives() -> None:
    frame = pd.DataFrame([
        {
            "source_dataset": "s", "session_id": "v", "query_id": "Q1",
            "unit_id": 1, "unit_start_seconds": 10.0, "unit_end_seconds": 20.0,
            "projected_label": "positive",
        },
        {
            "source_dataset": "s", "session_id": "v", "query_id": "Q1",
            "unit_id": 2, "unit_start_seconds": 20.0, "unit_end_seconds": 30.0,
            "projected_label": "positive",
        },
        {
            "source_dataset": "s", "session_id": "v", "query_id": "Q1",
            "unit_id": 4, "unit_start_seconds": 40.0, "unit_end_seconds": 50.0,
            "projected_label": "positive",
        },
    ])
    groups = k3_bridge_safe_groups(frame)
    assert [row["unit_ids"] for row in groups] == [[1, 2], [4]]


def load_stage_a_runner():
    path = Path(__file__).resolve().parents[2] / "scripts/run_mf_psvr_stage_a_oracle.py"
    module_spec = importlib.util.spec_from_file_location("mf_stage_a_runner_test", path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_raw_envelope_must_link_to_exact_started_event(tmp_path: Path, monkeypatch) -> None:
    runner = load_stage_a_runner()
    runtime = {"runtime": "frozen"}
    runtime["resolved_inference_runtime_sha256"] = runner.canonical_hash(runtime)
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    monkeypatch.setattr(runner, "RESOLVED_RUNTIME", runtime_path)

    contents = ["a" * 64]
    identity = {
        "physical_call_id": "mf_psvr_stage_a_001",
        "oracle_build_id": "build_1",
        "cache_input_identity_sha256": "b" * 64,
        "decoded_frame_indices": [10],
        "decoded_frame_content_sha256": runner.canonical_hash(contents),
        "decoded_frame_count": 1,
        "rng_seed": 20260710,
        "unit_id": 3,
        "unit_start_seconds": 0.0,
        "unit_end_seconds": 10.0,
        "source_sha256": "c" * 64,
    }
    generation = {"do_sample": False, "max_new_tokens": 256}
    model_input = {"prompt_text_sha256": "d" * 64, "tensors": []}
    model_input["model_input_identity_sha256"] = runner.canonical_hash(model_input)
    rng = {
        "numpy_seed": 20260710,
        "python_seed": 20260710,
        "torch_seed": 20260710,
        "torch_cuda_seed_all": 20260710,
        "torch_initial_seed": 20260710,
        "deterministic_algorithms_enabled": True,
        "warn_only": False,
        "cublas_workspace_config": ":4096:8",
    }
    rng["rng_state_identity_sha256"] = runner.canonical_hash(rng)
    attempt_id = "build_1__mf_psvr_stage_a_001__a001"
    record = {
        "physical_call_id": "mf_psvr_stage_a_001",
        "attempt_id": attempt_id,
        "oracle_build_id": "build_1",
        "cache_input_identity_sha256": "b" * 64,
        "decoded_frame_indices": [10],
        "decoded_frame_timestamps_seconds": [1.0],
        "per_frame_content_sha256": contents,
        "generation_config": generation,
        "physical_vlm_call": True,
        "rng_seed": 20260710,
        "resolved_inference_runtime_sha256": runtime["resolved_inference_runtime_sha256"],
        "model_input_manifest": model_input,
        "rng_identity": rng,
        "unit_id": 3,
        "unit_start_seconds": 0.0,
        "unit_end_seconds": 10.0,
        "source_sha256": "c" * 64,
        "generation_runtime_seconds": 1.25,
        "model_load_seconds": 2.5,
        "model_loaded_this_invocation": True,
        "call_started_at_utc": "2026-07-18T00:00:00Z",
        "call_completed_at_utc": "2026-07-18T00:00:02Z",
        "raw": '{"label":"negative","confidence":"high"}',
    }
    record["raw_response_sha256"] = runner.sha256_text(record["raw"])
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(record), encoding="utf-8")
    started = {
        "event": "STARTED",
        "attempt_id": attempt_id,
        "physical_call_id": "mf_psvr_stage_a_001",
        "cache_input_identity_sha256": "b" * 64,
        "model_input_identity_sha256": model_input["model_input_identity_sha256"],
        "resolved_inference_runtime_sha256": runtime["resolved_inference_runtime_sha256"],
        "rng_state_identity_sha256": rng["rng_state_identity_sha256"],
        "timestamp": "2026-07-18T00:00:00Z",
    }
    assert runner.raw_links_started_event(raw_path, identity, {"bindings": {"generation_config": generation}}, started)
    started["rng_state_identity_sha256"] = "e" * 64
    assert not runner.raw_links_started_event(raw_path, identity, {"bindings": {"generation_config": generation}}, started)


@pytest.mark.parametrize("stage", ["prepare", "infer"])
def test_authority_gate_precedes_prepare_or_infer(stage: str, monkeypatch) -> None:
    runner = load_stage_a_runner()
    monkeypatch.setattr(sys, "argv", ["run_mf_psvr_stage_a_oracle.py", stage])
    monkeypatch.setattr(runner, "prepare", lambda: pytest.fail("prepare was reached"))
    monkeypatch.setattr(runner, "infer", lambda _: pytest.fail("infer was reached"))
    with pytest.raises(SystemExit, match="not authorized"):
        runner.main()
