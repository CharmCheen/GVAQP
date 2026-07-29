import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash


ROOT = Path(__file__).resolve().parents[2]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = load_script("aeq_v2_runner_test", "scripts/run_accelerated_event_query_oracle_preflight_v2.py")
ANALYZER = load_script("aeq_v2_analyzer_test", "scripts/analyze_accelerated_event_query_oracle_preflight_v2.py")
FINALIZER = load_script("aeq_v2_finalizer_test", "scripts/finalize_accelerated_event_query_oracle_preflight_v2.py")


def raw_for(label):
    common = {"confidence": "medium", "evidence": "visible evidence"}
    if label == "relevant":
        value = {"label": label, "event_start_sec": 1.0, "event_end_sec": 2.0,
                 "required_response": ["slowdown"], "cause": "visible hazard",
                 **common, "unknown_reason": None}
    elif label == "not_relevant":
        value = {"label": label, "event_start_sec": None, "event_end_sec": None,
                 "required_response": [], "cause": None, **common, "unknown_reason": None}
    else:
        value = {"label": label, "event_start_sec": None, "event_end_sec": None,
                 "required_response": [], "cause": "possible hazard", **common,
                 "unknown_reason": "motion ambiguous"}
    return json.dumps(value, sort_keys=True)


def synthetic_records(labels, sensitivity_overrides=None):
    prereg, _, selection, _, _ = RUNNER.frozen_context()
    records = {}
    sensitivity_overrides = sensitivity_overrides or {}
    for shard in RUNNER.SHARDS:
        for call in RUNNER.schedule_for_shard(prereg, selection, shard):
            candidate = call["clip"]["candidate_id"]
            label = sensitivity_overrides.get(candidate, labels[candidate]) \
                if call["variant"] == "fps_sensitivity" else labels[candidate]
            raw = raw_for(label)
            records[(shard, RUNNER.artifact_name(call))] = {
                "model_input_identity_sha256": f"{candidate}:2" if call["sampling_fps"] == 2.0 else f"{candidate}:4",
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "parse_status": "ok",
                "effective_label": label,
                "parsed": json.loads(raw),
            }
    return prereg, selection, records


def review_consensus(prereg):
    return json.loads((ROOT / prereg["bindings"]["review_consensus_path"]).read_text())


@pytest.mark.parametrize("collapsed_label", ["unknown", "not_relevant", "relevant"])
def test_degenerate_single_class_oracles_cannot_pass(collapsed_label):
    prereg, selection, records = synthetic_records({
        clip["candidate_id"]: collapsed_label
        for clip in RUNNER.frozen_context()[2]["clips"]
    })
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["class_support_pass"] is False
    assert result["numeric_gate_pass"] is False
    assert result["overall_gate_status"] == "FAIL_NUMERIC_OR_SUPPORT_GATE"


def aligned_labels(selection):
    labels = {clip["candidate_id"]: "not_relevant" for clip in selection["clips"]}
    labels.update({
        "DALI_u0501": "unknown",
        "DALI_u0548": "relevant",
        "DALI_u0555": "relevant",
        "HANGZHOU_u0280": "unknown",
        "WUHAN_u0134": "unknown",
        "WUHAN_u0171": "relevant",
        "WUHAN_u0217": "relevant",
    })
    return labels


def test_valid_numeric_mix_still_cannot_auto_pass_claim_grounding():
    selection = RUNNER.frozen_context()[2]
    prereg, selection, records = synthetic_records(aligned_labels(selection))
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["numeric_gate_pass"] is True
    assert result["semantic_contradictions"] == []
    assert result["overall_gate_status"] == "PENDING_INDEPENDENT_CLAIM_GROUNDING_REVIEW"
    assert len(result["positive_claims_pending_grounding"]) == 7
    assert any("fps4_sensitivity" in source
               for claim in result["positive_claims_pending_grounding"]
               for source in claim["source_artifacts"])


def test_unknown_sampling_transition_requires_review():
    selection = RUNNER.frozen_context()[2]
    labels = aligned_labels(selection)
    prereg, selection, records = synthetic_records(
        labels, sensitivity_overrides={"DALI_u0555": "unknown"}
    )
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["sampling_unknown_transitions"] == 1
    assert result["overall_gate_status"] == "REVIEW_REQUIRED"


def test_relevant_sampling_boundary_and_response_changes_fail_numeric_gate():
    selection = RUNNER.frozen_context()[2]
    prereg, selection, records = synthetic_records(aligned_labels(selection))
    dense = records[("DALI", "DALI_u0555_fps4_sensitivity.json")]
    dense["parsed"]["event_end_sec"] = 3.5
    dense["parsed"]["required_response"] = ["swerve"]
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["sampling_boundary_failures"] == 1
    assert result["sampling_response_set_failures"] == 1
    assert result["overall_gate_status"] == "FAIL_NUMERIC_OR_SUPPORT_GATE"


def test_systematic_bidirectional_semantic_contradictions_fail():
    selection = RUNNER.frozen_context()[2]
    labels = aligned_labels(selection)
    labels.update({"DALI_u0437": "relevant", "HANGZHOU_u0140": "relevant"})
    prereg, selection, records = synthetic_records(labels)
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["numeric_gate_pass"] is True
    assert result["systematic_semantic_failure"] is True
    assert result["overall_gate_status"] == "FAIL_SYSTEMATIC_SEMANTIC_GATE"


def test_explicit_call_manifest_prevents_prereg_count_mutation():
    prereg, _, selection, _, _ = RUNNER.frozen_context()
    mutated = deepcopy(prereg)
    mutated["workload"]["total_physical_calls"] = 999
    with pytest.raises(RuntimeError, match="arithmetic mismatch"):
        RUNNER.schedule_for_shard(mutated, selection, "DALI")


def test_model_audit_must_report_current_pass(monkeypatch):
    prereg = RUNNER.frozen_context()[0]
    original_load = RUNNER.load

    def altered(path):
        value = original_load(path)
        if path.name == "MODEL_IDENTITY_AUDIT_V1.json":
            value = deepcopy(value)
            value["status"] = "STALE"
        return value

    monkeypatch.setattr(RUNNER, "load", altered)
    with pytest.raises(RuntimeError, match="model audit"):
        RUNNER.validate_bindings(prereg)


def test_compute_approval_must_bind_exact_seal_and_32_call_scope(monkeypatch, tmp_path):
    prereg = RUNNER.frozen_context()[0]
    monkeypatch.setattr(RUNNER, "OUT", tmp_path)
    approval_path = tmp_path / "operational_oracle/preflight_v2/COMPUTE_APPROVAL_V2.json"
    approval_path.parent.mkdir(parents=True)
    approval = {
        "status": "APPROVED_BY_USER",
        "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": RUNNER.sha256_file(RUNNER.SEAL),
        "authorized_call_manifest_sha256": prereg["bindings"]["authorized_call_manifest_sha256"],
        "approved_physical_call_count": 32,
        "approval_scope": "exactly the 32 manifest calls; no automatic physical-generation retry; no representative or full oracle",
        "user_approval_evidence": "User explicitly approved the reviewed targeted pilot.",
    }
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    assert RUNNER.validate_compute_approval(approval_path, prereg) == RUNNER.sha256_file(approval_path)
    approval["approved_physical_call_count"] = 33
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not authorize"):
        RUNNER.validate_compute_approval(approval_path, prereg)
    duplicate = json.dumps({**approval, "approved_physical_call_count": 32}).replace(
        '"status": "APPROVED_BY_USER"',
        '"status": "AWAITING_EXPLICIT_USER_APPROVAL", "status": "APPROVED_BY_USER"',
    )
    approval_path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        RUNNER.validate_compute_approval(approval_path, prereg)


def authenticated_record_fixture(monkeypatch):
    runner, prereg, _, _, calls = ANALYZER.expected_calls()
    expected = calls[0]
    raw = raw_for("not_relevant")
    parsed = json.loads(raw)
    model_hash = runner.model_input_identity(expected["identity"], [
        {**frame, "rgb": None} for frame in expected["frame_set"]["frames"]
    ])
    approval_hash = "approved-scope-hash"
    monkeypatch.setattr(runner, "validate_compute_approval", lambda path, prereg: approval_hash)
    record = {
        "identity": expected["identity"],
        "input_identity_sha256": canonical_hash(expected["identity"]),
        "model_input_identity_sha256": model_hash,
        "frames": expected["frame_set"]["frames"],
        "parse_status": "ok",
        "effective_label": "not_relevant",
        "parsed": parsed,
        "raw": raw,
        "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "attempt_id": "attempt-0",
        "processed_input_sha256": "input-tensor-hash",
        "generated_token_ids_sha256": "generated-token-hash",
        "runtime": {"declared_physical_gpus": [0, 1],
                    "gpu_identities": ["0, NVIDIA A100, GPU-a", "1, NVIDIA A100, GPU-b"],
                    "runner_source_sha256": json.loads(RUNNER.SEAL.read_text())["sources"]["runner_source_sha256"],
                    "execution_seal_sha256": RUNNER.sha256_file(RUNNER.SEAL),
                    "model_file_manifest_sha256": json.loads(RUNNER.PREREG.read_text())["bindings"]["model_file_manifest_sha256"],
                    "parameter_dtypes": ["torch.bfloat16"],
                    "logical_cuda_devices": [0, 1],
                    "hf_device_map": {"model.layers.0": "0", "model.layers.63": "1"},
                    "cublas_workspace_config": ":4096:8",
                    "deterministic_algorithms_enabled": True},
    }
    record["runtime"]["compute_approval_path"] = "outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/COMPUTE_APPROVAL_V2.json"
    record["runtime"]["compute_approval_sha256"] = approval_hash
    record["record_sha256"] = canonical_hash(record)
    return runner, expected, record


def test_record_validator_rejects_raw_tampering(monkeypatch):
    runner, expected, record = authenticated_record_fixture(monkeypatch)
    ANALYZER.validate_record(runner, expected, record)
    record["raw"] += " "
    with pytest.raises(RuntimeError, match="self-hash"):
        ANALYZER.validate_record(runner, expected, record)


def test_record_validator_rejects_frame_tampering_even_with_new_self_hash(monkeypatch):
    runner, expected, record = authenticated_record_fixture(monkeypatch)
    record["frames"] = [dict(frame) for frame in record["frames"]]
    record["frames"][0]["decoded_index"] += 1
    record["record_sha256"] = canonical_hash({key: value for key, value in record.items()
                                               if key != "record_sha256"})
    with pytest.raises(RuntimeError, match="frame identity"):
        ANALYZER.validate_record(runner, expected, record)


def test_authorized_accounting_rejects_wrong_accepted_triple():
    _, _, _, _, calls = ANALYZER.expected_calls()
    records = {}
    events = []
    for index, row in enumerate(calls):
        input_hash = canonical_hash(row["identity"])
        attempt = f"attempt-{index}"
        record = {"input_identity_sha256": input_hash, "record_sha256": f"record-{index}",
                  "attempt_id": attempt, "generated_token_ids_sha256": f"tokens-{index}"}
        records[(row["shard"], row["artifact"])] = record
        common = {"artifact": row["artifact"], "call_spec_sha256": row["call"]["call_spec_sha256"],
                  "input_identity_sha256": input_hash, "attempt_id": attempt}
        events.extend([
            {"event": "INFERENCE_STARTED", **common},
            {"event": "INFERENCE_COMPLETED", **common,
             "generated_token_ids_sha256": record["generated_token_ids_sha256"]},
            {"event": "ACCEPTED", **common, "record_sha256": record["record_sha256"]},
        ])
    ANALYZER.validate_authorized_accounting(calls, records, events)
    events[-1]["record_sha256"] = "wrong-record"
    with pytest.raises(RuntimeError, match="accepted artifact/input/record triple"):
        ANALYZER.validate_authorized_accounting(calls, records, events)


def test_finalizer_has_no_pass_path_for_missing_unsupported_or_indeterminate_claims():
    expected = {"a", "b"}
    pending = "PENDING_INDEPENDENT_CLAIM_GROUNDING_REVIEW"
    assert FINALIZER.derive_final_status(pending, {"a": "SUPPORTED"}, expected) == "REVIEW_REQUIRED"
    assert FINALIZER.derive_final_status(
        pending, {"a": "SUPPORTED", "b": "INDETERMINATE"}, expected
    ) == "REVIEW_REQUIRED"
    assert FINALIZER.derive_final_status(
        pending, {"a": "SUPPORTED", "b": "UNSUPPORTED"}, expected
    ) == "FAIL_CLAIM_GROUNDING_GATE"
    assert FINALIZER.derive_final_status(
        pending, {"a": "SUPPORTED", "b": "SUPPORTED"}, expected
    ) == "PASS_TARGETED_PILOT"


def test_shard_lock_rejects_concurrent_runner(monkeypatch, tmp_path):
    monkeypatch.setattr(RUNNER, "LOCKS", tmp_path / "locks")
    first = RUNNER.acquire_shard_lock("DALI")
    try:
        with pytest.raises(RuntimeError, match="already locked"):
            RUNNER.acquire_shard_lock("DALI")
    finally:
        first.close()


def test_reconcile_marks_started_generation_uncertain_and_forbids_retry(monkeypatch, tmp_path):
    prereg, _, selection, _, frame_sets = RUNNER.frozen_context()
    schedule = RUNNER.schedule_for_shard(prereg, selection, "DALI")
    monkeypatch.setattr(RUNNER, "ATTEMPTS", tmp_path / "attempts")
    monkeypatch.setattr(RUNNER, "RAW", tmp_path / "raw")
    call = schedule[0]
    frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
    input_hash = canonical_hash(RUNNER.identity_payload(prereg, call, frame_set))
    identity = RUNNER.event_identity(call, input_hash, "attempt-crashed")
    RUNNER.append_attempt("DALI", {"event": "PREPARED", **identity,
                                    "processed_input_sha256": "processed"})
    RUNNER.append_attempt("DALI", {"event": "INFERENCE_STARTED", **identity,
                                    "processed_input_sha256": "processed"})
    with pytest.raises(RuntimeError, match="approval required"):
        RUNNER.reconcile_shard(schedule, prereg, frame_sets, "DALI")
    assert RUNNER.read_attempts("DALI")[-1]["event"] == "UNCERTAIN_INTERRUPTION"


def test_reconcile_recovers_durable_raw_after_completed_generation(monkeypatch, tmp_path):
    runner, prereg, _, _, calls = ANALYZER.expected_calls()
    expected = calls[0]
    call = expected["call"]
    raw = raw_for("not_relevant")
    record = {
        "identity": expected["identity"],
        "input_identity_sha256": canonical_hash(expected["identity"]),
        "model_input_identity_sha256": runner.model_input_identity(expected["identity"], [
            {**frame, "rgb": None} for frame in expected["frame_set"]["frames"]
        ]),
        "frames": expected["frame_set"]["frames"],
        "parse_status": "ok", "effective_label": "not_relevant", "parsed": json.loads(raw),
        "raw": raw, "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "attempt_id": "attempt-completed", "processed_input_sha256": "processed",
        "generated_token_ids_sha256": "tokens", "runtime": {},
    }
    record["record_sha256"] = canonical_hash(record)
    monkeypatch.setattr(runner, "ATTEMPTS", tmp_path / "attempts")
    monkeypatch.setattr(runner, "RAW", tmp_path / "raw")
    destination = runner.RAW / "DALI" / expected["artifact"]
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(record), encoding="utf-8")
    identity = runner.event_identity(call, record["input_identity_sha256"], record["attempt_id"])
    runner.append_attempt("DALI", {"event": "PREPARED", **identity,
                                    "processed_input_sha256": "processed"})
    runner.append_attempt("DALI", {"event": "INFERENCE_STARTED", **identity,
                                    "processed_input_sha256": "processed"})
    runner.append_attempt("DALI", {"event": "INFERENCE_COMPLETED", **identity,
                                    "generated_token_ids_sha256": "tokens"})
    _, _, selection, _, frame_sets = runner.frozen_context()
    schedule = runner.schedule_for_shard(prereg, selection, "DALI")
    pending = runner.reconcile_shard(schedule, prereg, frame_sets, "DALI")
    assert len(pending) == len(schedule) - 1
    accepted = runner.read_attempts("DALI")[-1]
    assert accepted["event"] == "ACCEPTED"
    assert accepted["record_sha256"] == record["record_sha256"]
